"""Build a Task through Python journal steps, direct commands and bounded reasoning sessions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from driver_surface_types import REGRESSION_TIMEOUT_DEFAULT, REGRESSION_TIMEOUT_ENV

# step_journal installs the canonical generated contract's import path.
from step_journal_contract import BEAD_TYPE_TASK, BeadId, Step
from typeguard import check_type

from orchestrator.core import pipeline_steps, step_journal
from orchestrator.core.agents import AgentRunner
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_registry import Registry
from orchestrator.core.journal_run import JournalRunner
from orchestrator.core.journal_steps import (
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    directory_artifact,
    value_artifact,
)
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tool_locks import seconds
from orchestrator.core.tools import Tools
from orchestrator.flows.build_reviews import attach_reviews
from orchestrator.flows.build_sessions import OutputContract, attach, latest, reasoned
from orchestrator.flows.build_state import (
    CONTRACTS,
    PLUGIN,
    REGRESSION,
    build_rounds,
)
from orchestrator.flows.build_state import (
    argument_object as _object,
)
from orchestrator.flows.build_state import (
    artifact_document as _document,
)
from orchestrator.flows.build_state import (
    artifact_file as _file,
)
from orchestrator.flows.build_state import (
    count_in_dispatch as _count,
)
from orchestrator.flows.build_state import (
    new_step as _new,
)
from orchestrator.flows.build_state import (
    workspace_of as _workspace,
)
from orchestrator.flows.build_suite import declared_command, run_suite
from orchestrator.flows.build_workspace import Workspace, checkpoint, git_operation, provision


def _suite(run: StepRun, name: str) -> dict[str, JsonValue]:
    """Run the declared suite directly and retain its full output.

    Returns:
        The suite artifact.

    """
    command: str = check_type(latest(run, "suiteCommand"), str)
    evidence: Path = run.context.work / "build" / str(run.step["id"]) / f"{name}.json"
    return run_suite(run.tools, _workspace(run).tree, command, evidence, run.step["script"]).document()


def _workspace_step(run: StepRun) -> Completion:
    """Establish and independently verify the existing Story workspace.

    Returns:
        The actual tree and branch artifacts.

    """
    bead: dict[str, JsonValue] = _object(run, "bead")
    story: dict[str, JsonValue] = _object(run, "story")
    workspace: Workspace = provision(run.tools, Path(check_type(bead["repoPath"], str)), check_type(story["id"], str))
    vocabulary: dict[str, JsonValue] = json_object(run.context.args["infraVocabulary"])
    labels: list[str] = check_type(bead.get("labels", []), list[str])
    types: list[str] = check_type(vocabulary["types"], list[str])
    infrastructure_labels: list[str] = check_type(vocabulary["labels"], list[str])
    infrastructure: bool = bead.get("type") in types or bool(set(labels) & set(infrastructure_labels))
    additions: list[NewStep] = []
    if bead.get("designSource") in {"bundle", "cds"}:
        additions.append(_new("build:design-source", "Carry the Task's recorded UI design source"))
    if infrastructure:
        additions.append(_new("build:infra-intent", "Author concrete infrastructure intent"))
    return Completion(
        artifacts=(
            directory_artifact("worktree", workspace.tree),
            value_artifact("branch", workspace.branch),
            value_artifact("defaultBranch", workspace.default_branch),
        ),
        add=(StepGroup(tuple(additions)),) if additions else (),
    )


def _baseline(run: StepRun) -> Completion:
    """Record the existing suite before changing tests, then select subject-specific test writers.

    Returns:
        Baseline evidence and real reasoning steps.

    """
    approved: JsonValue = latest(run, "regressionPlan")
    if isinstance(approved, str):
        _setup_suite(run, Path(approved))
    supplied: JsonValue = latest(run, "suiteCommand") or run.context.args.get("suiteCommand", "")
    command: str | None = declared_command(_workspace(run).tree, check_type(supplied, str))
    if command is None:
        return reasoned(
            run,
            "test-command-resolver",
            OutputContract(CONTRACTS / "build-command.schema.json", "suiteDeclaration"),
            "Resolve conflicting or unstructured repository test declarations into the suite-command contract",
            followups=(_new("build:baseline-resolved", "Record the resolved suite declaration and baseline"),),
        )
    return _baseline_command(run, command)


def _setup_suite(run: StepRun, approved: Path) -> None:
    """Apply the reviewed regression plan's setup before measuring the baseline.

    Raises:
        StepError: The reviewed setup cannot prepare the repository.

    """
    workspace: Workspace = _workspace(run)
    output: Path = run.context.work / "build" / str(run.step["id"]) / "setup.json"
    repository: str = check_type(_object(run, "bead")["repoPath"], str)
    result = run.tools.command(
        [
            sys.executable,
            str(REGRESSION),
            "setup",
            "--plan",
            str(approved),
            "--ledger",
            str(workspace.tree / ".agent-workforce" / "regression.json"),
            "--output",
            str(output),
            "--tree",
            str(workspace.tree),
            "--repo",
            repository,
        ],
        stage="build:baseline",
        timeout=seconds(REGRESSION_TIMEOUT_ENV, float(REGRESSION_TIMEOUT_DEFAULT)),
        check=False,
    )
    document: dict[str, JsonValue] = json_object(json.loads(result.stdout))
    if result.exit != 0 or document.get("ok") is not True:
        msg = "build:baseline"
        raise StepError(msg, OTHER_CAUSE, (str(output),))


def _baseline_command(run: StepRun, command: str) -> Completion:
    """Run a known declaration and plan the suite work.

    Returns:
        Baseline and specialist-selection steps.

    """
    evidence: Path = run.context.work / "build" / str(run.step["id"]) / "baseline.json"
    baseline: dict[str, JsonValue] = run_suite(
        run.tools,
        _workspace(run).tree,
        command,
        evidence,
        "build:baseline",
    ).document()
    planned: Completion = reasoned(
        run,
        "test-strategy-decider",
        OutputContract(CONTRACTS / "build-selection.schema.json", "testSelection"),
        "Select test specialists for this Task's existing suite and required behavioral coverage",
        followups=(_new("build:plan-tests", "Plan the selected test writers in suite context"),),
    )
    return Completion(
        artifacts=(*planned.artifacts, value_artifact("suiteCommand", command), value_artifact("baseline", baseline)),
        add=planned.add,
    )


def _resolved_baseline(run: StepRun) -> Completion:
    """Run a declaration selected through a genuine configuration judgment.

    Returns:
        Baseline and test-selection work.

    """
    return _baseline_command(run, check_type(_document(run, "suiteDeclaration")["command"], str))


def _plan_tests(run: StepRun) -> Completion:
    """Schedule the selected test writers, not a code-based fixed roster.

    Returns:
        Sequential test-writer steps and their suite check.

    """
    if latest(run, "testSelection") is None:
        return reasoned(
            run,
            "test-strategy-decider",
            OutputContract(CONTRACTS / "build-selection.schema.json", "testSelection"),
            "Select test specialists for the existing suite's required corrections",
            followups=(_new("build:plan-tests", "Plan the selected suite corrections"),),
        )
    agents: list[str] = check_type(_document(run, "testSelection")["agents"], list[str])
    children: tuple[NewStep, ...] = tuple(
        _new("build:red-write", f"Review and improve suite tests with {agent}", {"testAgent": agent})
        for agent in agents
    )
    return Completion(add=(StepGroup((*children, _new("build:red-check", "Run the suite after test work"))),))


def _tests(run: StepRun) -> Completion:
    """Review and change tests as code within the existing suite.

    Returns:
        The selected test writer's genuine reasoning session.

    """
    agent: str = check_type(run.params().get("testAgent") or "tdd-unit-test-generator", str)
    return reasoned(
        run,
        agent,
        OutputContract(CONTRACTS / "build-tests.schema.json", "testWork"),
        "Review and improve this suite's happy, negative, edge and boundary coverage against the full contract",
        followups=(_new("build:tests-authored", "Record the test author's accepted suite file versions"),),
    )


def _tests_authored(run: StepRun) -> Completion:
    """Accept legitimate test-author updates before later implementation ownership checks.

    Returns:
        The exact current versions of the test-author files.

    """
    return Completion(artifacts=(value_artifact("testPrint", _test_fingerprint(run)),))


def _red_check(run: StepRun) -> Completion:
    """Accept passing tests as evidence and preserve failing-suite evidence for implementation.

    Returns:
        Suite facts without a manufactured-Red success condition.

    """
    suite: dict[str, JsonValue] = _suite(run, "tests")
    fingerprint: dict[str, JsonValue] = _test_fingerprint(run)
    if suite["exitCode"] == 0:
        return Completion(artifacts=(value_artifact("redRun", suite), value_artifact("testPrint", fingerprint)))
    judgment: Completion = reasoned(
        run,
        "acceptance-criteria-coverage-assessor",
        OutputContract(CONTRACTS / "build-suite-review.schema.json", "suiteReview"),
        "Judge suite quality and classify failures as test defects, product defects or environment failures",
        followups=(_new("build:suite-reviewed", "Act on the suite-quality review before implementation"),),
    )
    return Completion(
        artifacts=(*judgment.artifacts, value_artifact("redRun", suite), value_artifact("testPrint", fingerprint)),
        add=judgment.add,
    )


def _test_fingerprint(run: StepRun) -> dict[str, JsonValue]:
    """Fingerprint the suite files authored by every test specialist, including missing files.

    Returns:
        Exact blob hashes and worktree digest from the existing git utility.

    """
    paths: set[str] = set()
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        if step["id"] == run.step["id"]:
            break
        paths.update(_step_test_files(step))
    return git_operation(
        run.tools,
        run.step["script"],
        ["hash-files", "--tree", str(_workspace(run).tree), *sorted(paths)],
    )


def _step_test_files(step: Step) -> list[str]:
    """Read the completed test specialists' declared file names.

    Returns:
        Every test file recorded by this completed step.

    """
    if step["status"] != "done":
        return []
    return [
        path
        for artifact in step["artifacts"]
        if artifact["name"] == "testFiles" and artifact["kind"] == "value"
        for path in check_type(artifact["value"], list[str])
    ]


def _suite_reviewed(run: StepRun) -> Completion:
    """Repair poor tests before interpreting their failure as missing product behavior.

    Returns:
        Test corrections when needed; genuine product defects proceed to implementation review.

    Raises:
        StepError: An environment failure prevents meaningful suite execution, or corrections exhaust their bound.

    """
    review: dict[str, JsonValue] = _document(run, "suiteReview")
    route: str = check_type(review["route"], str)
    if route == "implementation":
        if latest(run, "implementationSelection") is not None or latest(run, "implementers") is not None:
            return Completion(add=(StepGroup((_new("build:plan-code", "Correct the validated product failure"),)),))
        return Completion()
    if route == "environment" or _count(run, "build:suite-reviewed") >= build_rounds() - 1:
        msg = "build:suite-reviewed"
        raise StepError(msg, OTHER_CAUSE, (check_type(review["evidence"], str),))
    return Completion(add=(StepGroup((_new("build:plan-tests", "Repair the suite's test defects"),)),))


def _select_implementers(run: StepRun) -> Completion:
    """Review architecture and code quality even when the entire suite already passes.

    Returns:
        Independent code review followed by a deterministic implementation decision.

    """
    return reasoned(
        run,
        "code-correctness-reviewer",
        OutputContract(CONTRACTS / "build-review.schema.json", "codeReview"),
        "Review this Task's code and tests against architecture, requirements, quality and best practices",
        followups=(_new("build:code-reviewed", "Decide what code work the suite and code review require"),),
    )


def _code_reviewed(run: StepRun) -> Completion:
    """Keep working on review findings even when the tests pass.

    Returns:
        Specialist selection when improvements or failing tests require implementation.

    """
    review: dict[str, JsonValue] = _document(run, "codeReview")
    suite: dict[str, JsonValue] = _latest_suite(run)
    findings: list[JsonValue] = check_type(review["findings"], list[JsonValue])
    improvements: bool = any(json_object(finding)["severity"] != "note" for finding in findings)
    if suite.get("exitCode") == 0 and review["approved"] is True and not improvements:
        return Completion(artifacts=(value_artifact("greenRun", suite),))
    return reasoned(
        run,
        "implementation-lead",
        OutputContract(CONTRACTS / "build-selection.schema.json", "implementationSelection"),
        "Select the implementation specialists needed for the suite failures and code review findings",
        followups=(_new("build:plan-code", "Plan the selected code specialists and suite check"),),
    )


def _latest_suite(run: StepRun) -> dict[str, JsonValue]:
    """Read the newest accepted suite result by journal order, including correction runs.

    Returns:
        The latest factual suite artifact, not a stale baseline or earlier Red result.

    """
    suite: dict[str, JsonValue] = {}
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        if step["id"] == run.step["id"]:
            break
        suite = _suite_from_step(step, suite)
    return suite


def _suite_from_step(step: Step, previous: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Read a completed step's latest suite evidence.

    Returns:
        New evidence when present, otherwise the previous result.

    """
    if step["status"] != "done":
        return previous
    matches = [
        artifact
        for artifact in step["artifacts"]
        if artifact["name"] in {"baseline", "redRun", "greenRun", "refactorRun", "finalRun"}
        and artifact["kind"] == "value"
    ]
    return json_object(matches[-1]["value"]) if matches else previous


def _plan_code(run: StepRun) -> Completion:
    """Schedule selected implementers followed by factual suite verification.

    Returns:
        Code-work steps in the selected order.

    Raises:
        StepError: The operation cannot proceed with the supplied evidence.

    """
    selection: JsonValue = latest(run, "implementationSelection")
    agents: list[str] = (
        check_type(_document(run, "implementationSelection")["agents"], list[str])
        if selection is not None
        else check_type(latest(run, "implementers"), list[str])
    )
    if not agents:
        msg = "build:plan-code"
        raise StepError(msg, OTHER_CAUSE, ("The unresolved work has no selected implementer",))
    additions: tuple[NewStep, ...] = tuple(
        _new("build:implement", f"Build and improve the Task with {agent}", {"implementer": agent}) for agent in agents
    )
    return Completion(
        artifacts=(value_artifact("implementers", list(agents)),),
        add=(StepGroup((*additions, _new("build:green-check", "Run the whole suite after implementation"))),),
    )


def _implement(run: StepRun) -> Completion:
    """Implement behavior and missing prerequisites while leaving test rulings to test writers.

    Returns:
        One specialist's real code-work session.

    """
    agent: str = check_type(run.params()["implementer"], str)
    return reasoned(
        run,
        agent,
        OutputContract(CONTRACTS / "build-implementation.schema.json", "codeWork"),
        "Implement and improve this Task, including its unbuilt prerequisite dependencies",
    )


def _green_check(run: StepRun) -> Completion:
    """Use actual suite exits and bounded correction work, not an agent's success assertion.

    Returns:
        Accepted suite evidence or another selected implementation round.

    Raises:
        StepError: The suite remains failing after the permitted rounds.

    """
    fingerprint: dict[str, JsonValue] = _test_fingerprint(run)
    previous: JsonValue = latest(run, "testPrint")
    if isinstance(previous, dict) and previous.get("files") != fingerprint["files"]:
        msg = "green-modified-tests"
        raise StepError(
            msg,
            OTHER_CAUSE,
            ("Implementation changed test-author files; tests require their author's ruling",),
        )
    suite: dict[str, JsonValue] = _suite(run, "green")
    artifacts = (value_artifact("greenRun", suite), value_artifact("testPrint", fingerprint))
    if suite["exitCode"] == 0:
        return Completion(artifacts=artifacts)
    if _count(run, "build:green-check") >= build_rounds() - 1:
        msg = "build:green-check"
        raise StepError(msg, OTHER_CAUSE, (str(suite["evidence"]),))
    judgment: Completion = reasoned(
        run,
        "acceptance-criteria-coverage-assessor",
        OutputContract(CONTRACTS / "build-suite-review.schema.json", "suiteReview"),
        "Judge whether the failing suite needs test repair, product correction or environment recovery",
        followups=(_new("build:green-reviewed", "Route the judged suite failure to its owning specialist"),),
    )
    return Completion(artifacts=(*artifacts, *judgment.artifacts), add=judgment.add)


def _green_reviewed(run: StepRun) -> Completion:
    """Give valid product failures to implementers and poor tests back to their authors.

    Returns:
        The next bounded correction, chosen from the explicit suite judgment.

    Raises:
        StepError: The environment cannot support meaningful verification.

    """
    review: dict[str, JsonValue] = _document(run, "suiteReview")
    route: str = check_type(review["route"], str)
    if route == "environment":
        msg = "build:green-reviewed"
        raise StepError(msg, OTHER_CAUSE, (check_type(review["evidence"], str),))
    key: str = "build:plan-tests" if route == "test-repair" else "build:plan-code"
    return Completion(add=(StepGroup((_new(key, "Correct the judged suite failure"),)),))


def _snapshot(run: StepRun) -> Completion:
    """Keep a recoverable Green tree before refactoring code or tests.

    Returns:
        The existing git utility's complete snapshot.

    """
    workspace: Workspace = _workspace(run)
    checkpoint(run.tools, workspace, f"feat(build): checkpoint {run.bead}")
    snapshot: dict[str, JsonValue] = git_operation(
        run.tools,
        "build:refactor-snapshot",
        ["snapshot", "--tree", str(workspace.tree)],
    )
    return Completion(artifacts=(value_artifact("refactorSnapshot", check_type(snapshot["tree"], str)),))


def _refactor(run: StepRun) -> Completion:
    """Consider worthwhile architecture, code and suite improvements.

    Returns:
        A refactoring session, whose no-change result must explain why no improvement is warranted.

    """
    return reasoned(
        run,
        "code-refactoring-specialist",
        OutputContract(CONTRACTS / "build-implementation.schema.json", "refactorWork"),
        "Review and improve architecture conformance, code quality and tests while preserving required behavior",
    )


def _refactor_check(run: StepRun) -> Completion:
    """Keep successful refactoring and restore a regressing refactor to its Green snapshot.

    Returns:
        Suite evidence and a restoration step when needed.

    """
    suite: dict[str, JsonValue] = _suite(run, "refactor")
    additions: tuple[StepGroup, ...] = ()
    if suite["exitCode"] != 0:
        additions = (
            StepGroup((_new("build:refactor-restore", "Restore the Green snapshot after regressing refactor"),)),
        )
    design: JsonValue = latest(run, "design")
    if isinstance(design, dict) and design.get("designSource") in {"bundle", "cds"}:
        additions = (
            *additions,
            StepGroup((_new("build:cds-audit", "Audit the changed UI against its design source"),)),
        )
    return Completion(artifacts=(value_artifact("refactorRun", suite),), add=additions)


def _restore(run: StepRun) -> Completion:
    """Restore using the utility's snapshot tree id, then verify Green again.

    Returns:
        The restoration evidence.

    Raises:
        StepError: Restoring the snapshot does not restore a passing suite.

    """
    snapshot: str = check_type(latest(run, "refactorSnapshot"), str)
    restored: dict[str, JsonValue] = git_operation(
        run.tools,
        "build:refactor-restore",
        ["restore", "--tree", str(_workspace(run).tree), "--to", snapshot],
    )
    suite: dict[str, JsonValue] = _suite(run, "restored")
    if suite["exitCode"] != 0:
        msg = "build:refactor-restore"
        raise StepError(msg, OTHER_CAUSE, (str(suite["evidence"]),))
    return Completion(artifacts=(value_artifact("refactorRestore", restored), value_artifact("greenRun", suite)))


def _final_suite(run: StepRun) -> Completion:
    """Require the complete repository suite to pass before the Task can commit.

    Returns:
        Factual whole-suite evidence.

    Raises:
        StepError: The final suite does not pass.

    """
    if latest(run, "finalCodeReview") is None:
        return reasoned(
            run,
            "code-correctness-reviewer",
            OutputContract(CONTRACTS / "build-review.schema.json", "finalCodeReview"),
            "Review the resulting code and test diff for correctness, architecture and quality "
            "before final verification",
            followups=(
                _new("build:final-review-checked", "Require the final code and test review to pass"),
                _new("build:final-suite-checked", "Run the final suite after independent code review"),
            ),
        )
    suite: dict[str, JsonValue] = _suite(run, "final")
    if suite["exitCode"] != 0:
        msg = "build:final-suite"
        raise StepError(msg, OTHER_CAUSE, (str(suite["evidence"]),))
    return Completion(artifacts=(value_artifact("finalRun", suite),))


def _final_review(run: StepRun) -> Completion:
    """Review final code and tests after a correction of the final review findings.

    Returns:
        An independent final review and its enforcing consumer.

    """
    return reasoned(
        run,
        "code-correctness-reviewer",
        OutputContract(CONTRACTS / "build-review.schema.json", "finalCodeReview"),
        "Re-review the final code and tests against the prior review findings and full contract",
        followups=(_new("build:final-review-checked", "Require the corrected final code review to pass"),),
    )


def _final_review_checked(run: StepRun) -> Completion:
    """Enforce independent final review with bounded correction and re-review.

    Returns:
        Approval or implementation and re-review steps.

    Raises:
        StepError: The final review is unresolved after its correction allowance.

    """
    review: dict[str, JsonValue] = _document(run, "finalCodeReview")
    findings: list[JsonValue] = check_type(review["findings"], list[JsonValue])
    needed: bool = any(json_object(finding)["severity"] != "note" for finding in findings)
    if review["approved"] is True and not needed:
        return Completion()
    if _count(run, "build:final-review-checked") >= build_rounds() - 1:
        msg = "build:final-review"
        raise StepError(msg, OTHER_CAUSE, (str(_file(run, "finalCodeReview")),))
    return Completion(
        add=(
            StepGroup((
                _new("build:select-implementers", "Resolve final code review findings"),
                _new("build:final-review", "Independently review the final corrections"),
            )),
        ),
    )


def _commit(run: StepRun) -> Completion:
    """Use normal repository hooks when committing the completed Task.

    Returns:
        The actual resulting HEAD.

    """
    bead: dict[str, JsonValue] = _object(run, "bead")
    title: str = check_type(bead.get("title") or run.bead, str)
    commit: str = checkpoint(run.tools, _workspace(run), f"feat(build): {run.bead} {title}")
    return Completion(artifacts=(value_artifact("commit", commit),))


def _registry() -> Registry:
    """Register every current and migration-compatible build script key.

    Returns:
        A registry isolated from elaboration and deploy.

    """
    registry: Registry = Registry()
    attach_reviews(registry)
    attach(registry, PLUGIN)
    handlers = {
        "build:workspace": _workspace_step,
        "build:baseline": _baseline,
        "build:baseline-resolved": _resolved_baseline,
        "build:plan-tests": _plan_tests,
        "build:red-write": _tests,
        "build:tests-authored": _tests_authored,
        "build:red-check": _red_check,
        "build:suite-reviewed": _suite_reviewed,
        "build:test-ruling": _tests,
        "build:select-implementers": _select_implementers,
        "build:code-reviewed": _code_reviewed,
        "build:plan-code": _plan_code,
        "build:implement": _implement,
        "build:green-check": _green_check,
        "build:green-reviewed": _green_reviewed,
        "build:refactor-snapshot": _snapshot,
        "build:refactor": _refactor,
        "build:refactor-check": _refactor_check,
        "build:refactor-restore": _restore,
        "build:final-suite": _final_suite,
        "build:final-suite-checked": _final_suite,
        "build:final-review": _final_review,
        "build:final-review-checked": _final_review_checked,
        "build:commit": _commit,
    }
    for key, handler in handlers.items():
        registry.script_step(key)(handler)
    return registry


def run(context: RunContext) -> dict[str, JsonValue]:
    """Resume one Task's Python build from its existing journal.

    Args:
        context: The driver's validated dispatch context.

    Returns:
        The build handback assembled from journal evidence.

    Raises:
        TypeError: The context or journal arguments violate the shared contract.

    """
    if not isinstance(context, RunContext):
        message: str = "Task build requires RunContext"
        raise TypeError(message)
    given: dict[str, JsonValue] = json_object(context.args["journal"])
    path: Path = Path(check_type(given["path"], str))
    bead: BeadId = BeadId(context.bead)
    agents: AgentRunner = AgentRunner(context)
    tools: Tools = Tools(context.work / "build-evidence")
    context.args["buildDispatchStarted"] = step_journal.timestamp()
    pipeline_steps.open_journal(path.parent, bead, BEAD_TYPE_TASK)
    runner: JournalRunner = JournalRunner(path, agents, tools, _registry())
    runner.run()
    journal = step_journal.read_journal(path)
    artifacts: dict[str, JsonValue] = {
        artifact["name"]: artifact["value"] if artifact["kind"] == "value" else artifact["path"]
        for step in step_journal.steps_in_order(journal)
        for artifact in step["artifacts"]
        if step["status"] == "done"
    }
    return {
        "ok": True,
        "stage": "committed",
        "beadId": context.bead,
        "headline": f"{context.bead} built with its whole suite passing",
        "worktree": artifacts.get("worktree"),
        "branch": artifacts.get("branch"),
        "commit": artifacts.get("commit"),
        "suite": artifacts.get("finalRun"),
    }
