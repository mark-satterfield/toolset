"""Build a Task through Python journal steps, direct commands and bounded reasoning sessions."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from driver_surface_types import REGRESSION_TIMEOUT_DEFAULT, REGRESSION_TIMEOUT_ENV

# step_journal installs the canonical generated contract's import path.
from step_journal_contract import BEAD_TYPE_TASK, BeadId, Journal, Step, ValueArtifact
from typeguard import check_type

from orchestrator.core import pipeline_steps, step_journal
from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_registry import Registry
from orchestrator.core.journal_run import JournalRunner, require_handled
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
from orchestrator.flows import build_policy, build_prerequisite_work, build_prerequisites
from orchestrator.flows.build_reviews import attach_reviews
from orchestrator.flows.build_sessions import OutputContract, accepted_steps, attach, latest, reasoned, view_of
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

if TYPE_CHECKING:
    from orchestrator.core.journal_views import AcceptedArtifact, AcceptedView

TEST_SELECTION: Final = "testSelection"
TEST_STRATEGY: Final = "testStrategy"
TEST_LEAD: Final = "test-design-lead"
STRATEGY_DECIDER: Final = "test-strategy-decider"
REVIEWER: Final = "code-correctness-reviewer"
CODE_REVIEW_TREE: Final = "codeReviewTree"
FINAL_REVIEW_TREE: Final = "finalReviewTree"


def _suite(run: StepRun, name: str, *, fresh: bool = False) -> dict[str, JsonValue]:
    """Run the declared suite directly and retain its full output, or reuse identical accepted evidence.

    A passing accepted result stands for this run only when the accepted execution policy marks the
    suite reusable and its evidence key equals this run's; otherwise the suite runs and its result
    records the key and why it was not reused.

    Returns:
        The suite artifact.

    """
    command: str = check_type(latest(run, "suiteCommand"), str)
    key: dict[str, JsonValue] = build_policy.evidence_key(run, command)
    reused, why = build_policy.reusable_suite(run, key, fresh=fresh)
    if reused is not None:
        return reused
    evidence: Path = run.context.work / "build" / str(run.step["id"]) / f"{name}.json"
    document: dict[str, JsonValue] = run_suite(
        run.tools,
        _workspace(run).tree,
        command,
        evidence,
        run.step["script"],
    ).document()
    return {**document, "evidenceKey": key, "reuseRefused": why}


def _suite_artifacts(name: str, suite: dict[str, JsonValue], stage: str) -> tuple[ValueArtifact, ...]:
    """Record a suite result with whether it ran or reused accepted evidence.

    Returns:
        The suite artifact and its stage decision.

    """
    return (value_artifact(name, suite), build_policy.suite_decision(suite, stage))


def _workspace_step(run: StepRun) -> Completion:
    """Establish and independently verify the existing Story workspace.

    Returns:
        The actual tree and branch artifacts.

    """
    bead: dict[str, JsonValue] = _object(run, "bead")
    story: dict[str, JsonValue] = json_object(bead["story"])
    workspace: Workspace = provision(run.tools, Path(check_type(bead["repoPath"], str)), check_type(story["id"], str))
    vocabulary: dict[str, JsonValue] = json_object(run.context.args["infraVocabulary"])
    labels: list[str] = check_type(bead.get("labels", []), list[str])
    types: list[str] = check_type(vocabulary["types"], list[str])
    infrastructure_labels: list[str] = check_type(vocabulary["labels"], list[str])
    infrastructure: bool = bead.get("type") in types or bool(set(labels) & set(infrastructure_labels))
    additions: list[NewStep] = []
    if bead.get("cdsDesignSource") in {"bundle", "cds"}:
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
    recorded: tuple[ValueArtifact, ...] = (
        value_artifact("suiteCommand", command),
        value_artifact("baseline", {**baseline, "evidenceKey": build_policy.evidence_key(run, command)}),
    )
    decision: build_policy.Decision = build_policy.decide(run, "tests")
    if decision.action == "omit":
        return Completion(artifacts=(*recorded, decision.artifact()))
    planned: Completion = _select_tests(
        run,
        "Select the test specialists this Task's existing suite and required behavioral coverage need",
        _new("build:plan-tests", "Plan the selected test writers in suite context"),
    )
    return Completion(artifacts=(*planned.artifacts, *recorded, decision.artifact()), add=planned.add)


def _select_tests(run: StepRun, action: str, followup: NewStep) -> Completion:
    """Have the test design lead route the required behavior to test specialists.

    Returns:
        The lead's selection session and its consumer.

    """
    return reasoned(
        run,
        TEST_LEAD,
        OutputContract(CONTRACTS / "build-selection.schema.json", TEST_SELECTION),
        f"{action}. Route only to the verification methods the accepted executionPolicy names, following the "
        "Task's recorded testStrategy and any accepted testStrategy decision; an infrastructure change takes "
        "CDK assertion and synthesis checks, not invented application unit tests; an empty selection is valid "
        "when existing tests already cover the required behavior. Name strategyConflicts only for a concern "
        "accepted strategy evidence leaves unresolved",
        followups=(followup,),
    )


def _after(view: AcceptedView, later: AcceptedArtifact, earlier: AcceptedArtifact) -> bool:
    """Tell whether one accepted artifact was produced after another.

    Returns:
        True when its producing step comes later in walk order.

    """
    return view.boundary.index(later.step) > view.boundary.index(earlier.step)


def _resolved_baseline(run: StepRun) -> Completion:
    """Run a declaration selected through a genuine configuration judgment.

    Returns:
        Baseline and test-selection work.

    """
    return _baseline_command(run, check_type(_document(run, "suiteDeclaration")["command"], str))


def _plan_tests(run: StepRun) -> Completion:
    """Schedule the selected test writers, not a code-based fixed roster.

    The test design lead selects; the test strategy decider is brought in only for a strategy
    concern the selection names as unresolved, and the lead then selects again under its decision.

    Returns:
        Sequential test-writer steps and their suite check, or the selection work they need first.

    """
    view: AcceptedView = view_of(run)
    selection: AcceptedArtifact | None = view.artifact(TEST_SELECTION)
    strategy: AcceptedArtifact | None = view.artifact(TEST_STRATEGY)
    if selection is None or (strategy is not None and _after(view, strategy, selection)):
        return _select_tests(
            run,
            "Select the test specialists the suite's required corrections need",
            _new("build:plan-tests", "Plan the selected suite corrections"),
        )
    conflicts: JsonValue = _document(run, TEST_SELECTION).get("strategyConflicts")
    if isinstance(conflicts, list) and conflicts and strategy is None:
        return reasoned(
            run,
            STRATEGY_DECIDER,
            OutputContract(CONTRACTS / "build-test-strategy.schema.json", TEST_STRATEGY),
            "Decide the test strategy concerns the test specialist selection names in strategyConflicts, from the "
            "conflicting accepted evidence it cites",
            followups=(_new("build:plan-tests", "Select the test writers under the decided strategy"),),
        )
    agents: list[str] = check_type(_document(run, TEST_SELECTION)["agents"], list[str])
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
    recorded: tuple[ValueArtifact, ...] = (*_suite_artifacts("redRun", suite, "red-check"),)
    if suite["exitCode"] == 0:
        return Completion(artifacts=(*recorded, value_artifact("testPrint", fingerprint)))
    judgment: Completion = reasoned(
        run,
        "acceptance-criteria-coverage-assessor",
        OutputContract(CONTRACTS / "build-suite-review.schema.json", "suiteReview"),
        "Judge suite quality and classify failures as test defects, product defects or environment failures",
        followups=(_new("build:suite-reviewed", "Act on the suite-quality review before implementation"),),
    )
    return Completion(
        artifacts=(*judgment.artifacts, *recorded, value_artifact("testPrint", fingerprint)),
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
    if route == "pass":
        return _passed_review(run, review)
    if route == "implementation":
        if latest(run, "implementationSelection") is not None or latest(run, "implementers") is not None:
            return Completion(add=(StepGroup((_new("build:plan-code", "Correct the validated product failure"),)),))
        return Completion()
    if route == "environment":
        return build_prerequisites.diagnose(run, "build:suite-reviewed")
    if _count(run, "build:suite-reviewed") >= build_rounds() - 1:
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


def _passed_review(run: StepRun, review: dict[str, JsonValue]) -> Completion:
    """Accept a pass judgment only for the latest completed factual suite.

    Returns:
        An empty completion once exact current execution establishes the pass.

    Raises:
        StepError: The judgment does not name the current successfully executed suite.

    """
    suite: dict[str, JsonValue] = _latest_suite(run)
    if suite.get("exitCode") != 0 or review.get("suiteEvidence") != suite.get("evidence"):
        raise StepError(run.step["script"], OTHER_CAUSE, ("Pass judgment does not match current suite execution",))
    return Completion()


def _code_reviewed(run: StepRun) -> Completion:
    """Keep working on review findings even when the tests pass.

    Returns:
        Specialist selection when improvements or failing tests require implementation.

    """
    review: dict[str, JsonValue] = _document(run, "codeReview")
    suite: dict[str, JsonValue] = _latest_suite(run)
    findings: list[JsonValue] = check_type(review["findings"], list[JsonValue])
    improvements: bool = any(json_object(finding)["severity"] != "note" for finding in findings)
    reviewed: ValueArtifact = value_artifact(CODE_REVIEW_TREE, build_policy.content_tree(run))
    if suite.get("exitCode") == 0 and review["approved"] is True and not improvements:
        return Completion(artifacts=(value_artifact("greenRun", suite), reviewed))
    selected: Completion = reasoned(
        run,
        "implementation-lead",
        OutputContract(CONTRACTS / "build-selection.schema.json", "implementationSelection"),
        "Select the implementation specialists needed for the suite failures and code review findings",
        followups=(_new("build:plan-code", "Plan the selected code specialists and suite check"),),
    )
    return Completion(artifacts=(*selected.artifacts, reviewed), add=selected.add)


def _latest_suite(run: StepRun) -> dict[str, JsonValue]:
    """Read the newest accepted suite result by journal order, including correction runs.

    Returns:
        The latest factual suite artifact, not a stale baseline or earlier Red result.

    """
    suite: dict[str, JsonValue] = {}
    step: Step
    for step in accepted_steps(run):
        suite = _suite_from_step(step, suite)
    return suite


def _suite_from_step(step: Step, previous: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Read an accepted earlier step's latest suite evidence.

    Returns:
        New evidence when present, otherwise the previous result.

    """
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

    """
    selection: JsonValue = latest(run, "implementationSelection")
    agents: list[str] = (
        check_type(_document(run, "implementationSelection")["agents"], list[str])
        if selection is not None
        else check_type(latest(run, "implementers"), list[str])
    )
    if not agents:
        return _empty_selection(run, selection)
    additions: tuple[NewStep, ...] = tuple(
        _new("build:implement", f"Build and improve the Task with {agent}", {"implementer": agent}) for agent in agents
    )
    return Completion(
        artifacts=(value_artifact("implementers", list(agents)),),
        add=(StepGroup((*additions, _new("build:green-check", "Run the whole suite after implementation"))),),
    )


def _empty_selection(run: StepRun, selection: JsonValue) -> Completion:
    """Reassess an empty selection once when the recorded repository state changed.

    Returns:
        Fresh verification work for an observable change.

    Raises:
        StepError: No change justifies reassessment, or its correction allowance is spent.

    """
    fingerprint: dict[str, JsonValue] = _test_fingerprint(run)
    prior: JsonValue = latest(run, "testPrint")
    changed: bool = isinstance(prior, dict) and prior.get("treeDigest") != fingerprint["treeDigest"]
    recovered: bool = latest(run, "implementationRecovery") == fingerprint["treeDigest"]
    if changed and not recovered and _count(run, "build:implementation-recheck") < build_rounds():
        return Completion(add=(StepGroup((_new("build:implementation-recheck", "Reassess the changed repository"),)),))
    evidence: tuple[str, ...] = ("The unresolved work has no selected implementer",)
    if selection is not None:
        evidence += (check_type(_document(run, "implementationSelection")["rationale"], str),)
    stage: str = "build:plan-code"
    raise StepError(stage, OTHER_CAUSE, evidence)


def _implementation_recheck(run: StepRun) -> Completion:
    """Append current suite evidence and independent review after a repository change.

    Returns:
        Accepted state facts and a fresh review followed by normal specialist selection.

    """
    fingerprint: dict[str, JsonValue] = _test_fingerprint(run)
    suite: dict[str, JsonValue] = _suite(run, "implementation-recheck")
    return Completion(
        artifacts=(
            value_artifact("implementationRecovery", fingerprint["treeDigest"]),
            value_artifact("testPrint", fingerprint),
            *_suite_artifacts("greenRun", suite, "implementation-recheck"),
        ),
        add=(StepGroup((_new("build:select-implementers", "Review the changed repository independently"),)),),
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
    artifacts = (*_suite_artifacts("greenRun", suite, "green-check"), value_artifact("testPrint", fingerprint))
    if suite["exitCode"] == 0:
        return Completion(artifacts=artifacts)
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
        StepError: Product or test corrections exhaust their configured allowance.

    """
    review: dict[str, JsonValue] = _document(run, "suiteReview")
    route: str = check_type(review["route"], str)
    if route == "pass":
        return _passed_review(run, review)
    if route == "environment":
        return build_prerequisites.diagnose(run, "build:green-reviewed")
    if _count(run, "build:green-check") >= build_rounds() - 1:
        stage: str = "build:green-reviewed"
        raise StepError(stage, OTHER_CAUSE, (check_type(review["evidence"], str),))
    key: str = "build:plan-tests" if route == "test-repair" else "build:plan-code"
    return Completion(add=(StepGroup((_new(key, "Correct the judged suite failure"),)),))


def _prerequisites_ready(run: StepRun) -> Completion:
    """Observe current readiness after producer work reaches its recorded required stage.

    Returns:
        A fresh read-only observation, followed by the original suite and its assessment.

    """
    return build_prerequisites.observe(run, check_type(run.params()["again"], str))


def _prerequisites_rediagnose(run: StepRun) -> Completion:
    """Reassess actual new producer identities within the persistent correction allowance.

    Returns:
        One diagnosis of the observably changed Task graph.

    """
    return build_prerequisites.diagnose(run, check_type(run.params()["again"], str))


def _prerequisites_suite(run: StepRun) -> Completion:
    """Rerun the exact recorded suite and append an independent assessment.

    Returns:
        Fresh suite facts and a new assessor session in the original red or green phase.

    Raises:
        StepError: Tests changed during a green-phase prerequisite wait without author review.

    """
    again: str = check_type(run.params()["again"], str)
    fingerprint: dict[str, JsonValue] = _test_fingerprint(run)
    previous: JsonValue = latest(run, "testPrint")
    if again == "build:green-reviewed" and isinstance(previous, dict) and previous.get("files") != fingerprint["files"]:
        stage: str = "green-modified-tests"
        raise StepError(stage, OTHER_CAUSE, ("Tests changed during prerequisite work; their author must rule",))
    suite: dict[str, JsonValue] = _suite(run, "prerequisites", fresh=True)
    return Completion(
        artifacts=(
            *_suite_artifacts("greenRun" if again == "build:green-reviewed" else "redRun", suite, "prerequisites"),
            value_artifact("testPrint", fingerprint),
        ),
        add=(
            StepGroup((
                _new(
                    "build:prerequisites-assess",
                    "Assess the fresh suite independently",
                    {"again": again},
                ),
            )),
        ),
    )


def _prerequisites_assess(run: StepRun) -> Completion:
    """Assess a completed factual suite step before resuming the original phase.

    Returns:
        A fresh assessor session and the original red or green judgment consumer.

    """
    again: str = check_type(run.params()["again"], str)
    return reasoned(
        run,
        "acceptance-criteria-coverage-assessor",
        OutputContract(CONTRACTS / "build-suite-review.schema.json", "suiteReview"),
        "Assess this freshly rerun whole suite and current readiness evidence; choose pass when sound tests pass, "
        "naming the exact suite JSON evidence path as suiteEvidence; otherwise distinguish test defects, product work "
        "and environment failures. Never reuse the old judgment.",
        followups=(_new(again, "Act on the fresh suite assessment"),),
    )


def _refactoring(run: StepRun) -> build_policy.Decision:
    """Decide whether the refactoring opportunity still needs a session.

    The accepted execution policy may omit it with its reason. Otherwise an accepted code review of
    this exact tree that approved with no improvement finding is the accepted assessment that no
    worthwhile refactoring exists.

    Returns:
        The decision.

    """
    decision: build_policy.Decision = build_policy.decide(run, "refactor")
    if decision.action == "omit":
        return decision
    view: AcceptedView = view_of(run)
    review: AcceptedArtifact | None = view.artifact("codeReview")
    tree: AcceptedArtifact | None = view.artifact(CODE_REVIEW_TREE)
    if review is None or tree is None or not _after(view, tree, review):
        return decision
    document: dict[str, JsonValue] = _document(run, "codeReview")
    findings: list[JsonValue] = check_type(document["findings"], list[JsonValue])
    clean: bool = document["approved"] is True and all(json_object(item)["severity"] == "note" for item in findings)
    if not clean or tree.value != build_policy.content_tree(run):
        return decision
    reason: str = "the accepted code review of this exact tree approved it with no improvement worth making"
    return build_policy.Decision("refactor", "reuse", reason, reused_from=review.step)


def _snapshot(run: StepRun) -> Completion:
    """Keep a recoverable Green tree before refactoring code or tests.

    Returns:
        The existing git utility's complete snapshot, or the decision that no refactoring session runs.

    """
    decision: build_policy.Decision = _refactoring(run)
    if decision.action != "run":
        return Completion(artifacts=(decision.artifact(),))
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
        A refactoring session, whose no-change result must explain why no improvement is warranted,
        or the decision that the opportunity is already satisfied.

    """
    decision: build_policy.Decision = _refactoring(run)
    if decision.action != "run":
        return Completion(artifacts=(decision.artifact(),))
    return reasoned(
        run,
        "code-refactoring-specialist",
        OutputContract(CONTRACTS / "build-implementation.schema.json", "refactorWork"),
        "Review and improve architecture conformance, code quality and tests while preserving required behavior",
    )


def _refactor_check(run: StepRun) -> Completion:
    """Keep successful refactoring and restore a regressing refactor to its Green snapshot.

    Returns:
        Suite evidence, or reused identical evidence when the refactoring changed nothing, and a
        restoration step when needed; no suite when no refactoring session ran.

    """
    recorded: tuple[ValueArtifact, ...]
    additions: tuple[StepGroup, ...] = ()
    if latest(run, "refactorSnapshot") is None or latest(run, "refactorWork") is None:
        recorded = (_refactoring(run).artifact(),)
    else:
        suite: dict[str, JsonValue] = _suite(run, "refactor")
        recorded = _suite_artifacts("refactorRun", suite, "refactor-check")
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
    return Completion(artifacts=recorded, add=additions)


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
    return Completion(
        artifacts=(
            value_artifact("refactorRestore", restored),
            *_suite_artifacts("greenRun", suite, "refactor-restore"),
        ),
    )


def _final_review_covers(run: StepRun) -> bool:
    """Tell whether an accepted, approved final review covers the current tree.

    The presence of a final review alone is not enough: it covers the tree its enforcing check
    recorded, and only while that tree is unchanged.

    Returns:
        True when the latest final review was approved for exactly the current content tree.

    """
    view: AcceptedView = view_of(run)
    review: AcceptedArtifact | None = view.artifact("finalCodeReview")
    tree: AcceptedArtifact | None = view.artifact(FINAL_REVIEW_TREE)
    if review is None or tree is None or not _after(view, tree, review):
        return False
    return tree.value == build_policy.content_tree(run)


def _final_suite(run: StepRun) -> Completion:
    """Require the complete repository suite to pass before the Task can commit.

    Returns:
        Factual whole-suite evidence, or the independent final review it needs first.

    Raises:
        StepError: The final suite does not pass.

    """
    if not _final_review_covers(run):
        return reasoned(
            run,
            REVIEWER,
            OutputContract(CONTRACTS / "build-review.schema.json", "finalCodeReview"),
            "Review the resulting code and test diff for correctness, architecture and quality before final "
            "verification, and judge whether the evidence the accepted executionPolicy selected meets the "
            "acceptance criteria; a needed verification it omitted is a blocking finding. Accepted suite results "
            "whose evidenceKey names the current tree may be cited instead of being rerun",
            followups=(
                _new("build:final-review-checked", "Require the final code and test review to pass"),
                _new("build:final-suite-checked", "Run the final suite after independent code review"),
            ),
        )
    suite: dict[str, JsonValue] = _suite(run, "final")
    if suite["exitCode"] != 0:
        msg = "build:final-suite"
        raise StepError(msg, OTHER_CAUSE, (str(suite["evidence"]),))
    return Completion(artifacts=_suite_artifacts("finalRun", suite, "final-suite"))


def _final_review(run: StepRun) -> Completion:
    """Review final code and tests after a correction of the final review findings.

    Returns:
        An independent final review and its enforcing consumer.

    """
    return reasoned(
        run,
        REVIEWER,
        OutputContract(CONTRACTS / "build-review.schema.json", "finalCodeReview"),
        "Re-review the artifacts changed since your previous final review against its unresolved findings and "
        "the full contract; accepted unrelated work stays judged",
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
        return Completion(artifacts=(value_artifact(FINAL_REVIEW_TREE, build_policy.content_tree(run)),))
    if _count(run, "build:final-review-checked") >= build_rounds() - 1:
        msg = "build:final-review"
        raise StepError(msg, OTHER_CAUSE, (str(_file(run, "finalCodeReview")),))
    return Completion(
        add=(
            StepGroup((
                _new("build:correct-findings", "Resolve final code review findings", {"review": "finalCodeReview"}),
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
    return Completion(
        artifacts=(value_artifact("commit", commit), value_artifact("executionSummary", build_policy.summary(run))),
    )


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
        "build:execution-policy": build_policy.author,
        "build:execution-policy-checked": build_policy.checked,
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
        "build:implementation-recheck": _implementation_recheck,
        "build:prerequisites-diagnosed": build_prerequisites.diagnosed,
        "build:prerequisites-ready": _prerequisites_ready,
        "build:environment-observe": _prerequisites_ready,
        "build:prerequisite-author": build_prerequisite_work.author,
        "build:prerequisite-authored": build_prerequisite_work.authored,
        "build:prerequisites-rediagnose": _prerequisites_rediagnose,
        "build:prerequisites-observed": build_prerequisites.observed,
        "build:prerequisites-suite": _prerequisites_suite,
        "build:prerequisites-assess": _prerequisites_assess,
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
    require_handled(step_journal.read_journal(path), runner.registry)
    while True:
        journal = step_journal.read_journal(path)
        next_step: Step | None = step_journal.next_step(journal)
        if next_step is not None and next_step.get("script") == "build:prerequisites-ready":
            wait: dict[str, JsonValue] = _prerequisite_wait(journal)
            control: Path = Path(check_type(context.args[dispatch_arguments().KEY_BEADS_REPO_PATH], str))
            if tools.portfolio("build:prerequisites-ready", build_prerequisites.pending, wait, path.parent, control):
                return {
                    "ok": False,
                    "stage": "waiting-for-prerequisites",
                    "beadId": context.bead,
                    "headline": f"{context.bead} waits for its verified producer work",
                    "detailPath": str(path),
                    "sessions": json_object({"sessions": context.sessions})["sessions"],
                    "lifecycleDone": False,
                    "waitingForPrerequisites": wait,
                }
        if not runner.run_next():
            break
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
        "detailPath": str(path),
        "sessions": json_object({"sessions": context.sessions})["sessions"],
        "worktree": artifacts.get("worktree"),
        "branch": artifacts.get("branch"),
        "commit": artifacts.get("commit"),
        "suite": artifacts.get("finalRun"),
    }


def _prerequisite_wait(journal: Journal) -> dict[str, JsonValue]:
    """Read the latest accepted wait while leaving all previous journal evidence intact.

    Returns:
        The structured wait written by the validated additive edge step.

    """
    waits: list[JsonValue] = [
        artifact["value"]
        for step in step_journal.steps_in_order(journal)
        if step["status"] == "done"
        for artifact in step["artifacts"]
        if artifact["name"] == "prerequisiteWait" and artifact["kind"] == "value"
    ]
    return json_object(waits[-1])
