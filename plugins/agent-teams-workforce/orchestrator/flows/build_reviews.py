"""Regression, reuse and documentation work in the Task's Python journal."""

from __future__ import annotations

import json
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Final

from driver_surface_types import REGRESSION_TIMEOUT_DEFAULT, REGRESSION_TIMEOUT_ENV
from regression import HARNESS_CONFIGURATION
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import Registry
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, file_artifact, value_artifact
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import seconds
from orchestrator.flows import build_carried, build_policy
from orchestrator.flows.build_sessions import OutputContract, accepted_steps, latest, reasoned
from orchestrator.flows.build_state import (
    ARTIFACT_CONTRACTS,
    CONTRACTS,
    REGRESSION,
    TEST_LEAD,
    TEST_SELECTION,
    build_rounds,
    regression_rounds,
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
from orchestrator.flows.elaboration_files import project_root

if TYPE_CHECKING:
    from step_journal_contract import ValueArtifact

RESCOPE: Final = ("build:regression-reassess", "build:regression-review", "build:regression-validate")
"""The steps that assess, review and validate the regression scope again."""
REMAP: Final = ("build:regression-remap", "build:regression-map-review", "build:regression-verify")
"""The steps that map, review and verify the final regression evidence again."""
VALIDATE: Final = "build:regression-validate"
"""The step that validates the reviewed regression scope."""
VERIFY: Final = "build:regression-verify"
"""The step that verifies the reviewed final regression evidence."""
EVIDENCE_WORK: Final = ("build:regression-tests", "build:final-suite")
"""The steps that write the tests and behaviour a failed final verification found missing, and review them."""
HARNESS_FILES: Final = "harnessFiles"
"""The dependency manifests and configuration files a step changed so the tests run; harness for the replay base."""
HARNESS_NAMES: Final = frozenset({"testFiles", HARNESS_FILES})
"""The handback fields and journal values that name a build's test and harness files."""
HANDBACK: Final = "result.json"
"""The file each agent step of a build writes its handback to, in its own folder of the build's artifacts."""
VERIFY_RUNS: Final = 2
"""Verification runs the mapped runs on the tree and may replay them on the base, each within its own budget."""


def _regression(run: StepRun, mode: str, plan: Path, extra: list[str]) -> tuple[Path, dict[str, JsonValue]]:
    """Call the existing regression contract checker without a model session.

    Returns:
        Evidence file and its exact result, including failure facts.

    """
    tree: Path = _workspace(run).tree
    folder: Path = run.context.work / "build" / str(run.step["id"])
    output: Path = folder / f"{run.step['id']}-regression-{mode}.json"
    phases: int = VERIFY_RUNS if mode == "verify" else 1
    result = run.tools.command(
        [
            sys.executable,
            str(REGRESSION),
            mode,
            "--plan",
            str(plan),
            "--ledger",
            str(tree / ".agent-workforce" / "regression.json"),
            "--output",
            str(output),
            *extra,
        ],
        stage=run.step["script"],
        timeout=phases * seconds(REGRESSION_TIMEOUT_ENV, float(REGRESSION_TIMEOUT_DEFAULT)),
        check=False,
    )
    document: dict[str, JsonValue] = json_object(json.loads(result.stdout))
    return output, document


def _scope(run: StepRun, final: bool) -> Completion:
    """Have the regression specialist assess prior obligations or map their final evidence.

    Returns:
        The actual assessor session, with the shared regression schema.

    """
    name: str = "regressionMapped" if final else "regressionPlan"
    action: str = (
        "Map final test evidence against the approved regression scope"
        if final
        else "Assess cumulative regression scope from existing obligations and the Task's full sources"
    )
    if latest(run, HARNESS_FILES) is not None:
        action += (
            ". This build corrected the repository's own declarations (harnessFiles); each run's setup installs the "
            "repository's declared dependencies with its locked install (for example npm ci), with no ad-hoc install "
            "of a package the repository now declares"
        )
    return reasoned(
        run,
        "regression-impact-assessor",
        OutputContract(ARTIFACT_CONTRACTS / "regression-plan.schema.json", name),
        action,
    )


def task_sources(run: StepRun) -> list[str]:
    """Resolve the current Task's source citations to their backing paths.

    Returns:
        Unique absolute paths, without section citations.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    carried: list[str] = list(check_type(bead.get("specPaths", []), list[str]))
    carried.extend(check_type(bead[key], str) for key in ("specPath", "prdPath") if bead.get(key))
    root: Path = project_root()
    return list(dict.fromkeys(str(root / source.split("#", 1)[0]) for source in carried))


def refresh_sources(run: StepRun) -> Completion | None:
    """Reassess downstream evidence when the Task names new governing sources.

    Returns:
        Appended assessment, policy, baseline and review work, or None when covered.

    Raises:
        StepError: A reassessment still omitted the same current source paths.

    """
    sources: list[str] = sorted(task_sources(run))
    covered: list[str] = (
        check_type(_document(run, "regressionPlan")["sourceFiles"], list[str])
        if latest(run, "regressionPlan") is not None
        else []
    )
    missing: list[str] = [source for source in sources if source not in covered]
    if not missing:
        return None
    if latest(run, "regressionSourcesRefresh") == sources:
        raise StepError(
            run.step["script"],
            OTHER_CAUSE,
            ("Reassessed regression scope omitted current Task sources", *missing),
        )
    keys: tuple[str, ...] = (
        "build:regression-reassess",
        "build:regression-review",
        "build:regression-validate",
        "build:execution-policy",
        "build:baseline",
        "build:select-implementers",
    )
    return Completion(
        artifacts=(value_artifact("regressionSourcesRefresh", list(sources)),),
        add=(StepGroup(tuple(_new(key, "Refresh evidence for the Task's current governing sources") for key in keys)),),
    )


def _scope_initial(run: StepRun) -> Completion:
    """Assess regression scope before suite work.

    Returns:
        The assessor's journal children.

    Raises:
        StepError: The operation cannot proceed with the supplied evidence.

    """
    sources: list[str] = list(
        dict.fromkeys(
            task_sources(run)
            + [
                artifact["path"]
                for step in step_journal.steps_in_order(run.journal())
                for artifact in step["artifacts"]
                if artifact["kind"] == "file" and artifact["name"] in {"spec", "criteria", "TRD", "data model"}
            ],
        ),
    )
    plan: Path = run.context.work / "build" / str(run.step["id"]) / "pending-plan.json"
    output, prepared = _regression(
        run,
        "prepare",
        plan,
        [value for source in sources for value in ("--source", source)],
    )
    if prepared.get("ok") is not True:
        errors: list[str] = check_type(prepared.get("errors", []), list[str])
        raise StepError(run.step["script"], OTHER_CAUSE, tuple(errors or ["Regression source preparation failed"]))
    assessed: Completion = _scope(run, False)
    return Completion(artifacts=(*assessed.artifacts, file_artifact("regressionPrevious", output)), add=assessed.add)


def _scope_final(run: StepRun) -> Completion:
    """Map the complete approved scope to the resulting suite.

    Returns:
        The mapper's journal children.

    """
    return _scope(run, True)


def _review(run: StepRun, final: bool) -> Completion:
    """Keep regression review separate from the author that produced its scope or mapping.

    Returns:
        The independent reviewer session.

    """
    name: str = "regressionMappedReview" if final else "regressionPlanReview"
    action: str = (
        "Review the final regression evidence mapping against the approved scope"
        if final
        else "Review cumulative regression source coverage and supersession evidence"
    )
    return reasoned(
        run,
        "regression-coverage-reviewer",
        OutputContract(ARTIFACT_CONTRACTS / "regression-review.schema.json", name),
        action,
    )


def _review_initial(run: StepRun) -> Completion:
    """Review regression scope.

    Returns:
        The reviewer's journal children.

    """
    return _review(run, False)


def _review_final(run: StepRun) -> Completion:
    """Review final evidence mapping.

    Returns:
        The reviewer's journal children.

    """
    return _review(run, True)


def _validate(run: StepRun, final: bool) -> Completion:
    """Validate or verify the exact regression schema, source seal and independent review.

    Returns:
        Required evidence, or bounded scope correction steps.

    Raises:
        StepError: Validation still fails after the permitted correction rounds.

    """
    plan: Path = _file(run, "regressionMapped" if final else "regressionPlan")
    review: Path = _file(run, "regressionMappedReview" if final else "regressionPlanReview")
    extra: list[str] = ["--review", str(review)]
    if final:
        extra.extend(["--approved-plan", str(_file(run, "regressionPlan"))])
        extra.extend(["--bindings", str(_file(run, "regressionScope").parent / "source-bindings.json")])
        extra.extend(["--citations", str(_citations(run))])
        extra.extend(_base_arguments(run))
    output, document = _regression(run, "verify" if final else "validate", plan, extra)
    if document.get("ok") is True and final:
        return Completion(
            artifacts=(
                file_artifact("regressionEvidence", output),
                *_unmet_artifacts(document),
                *_origin_artifacts(document),
            ),
        )
    if document.get("ok") is True:
        return Completion(artifacts=(file_artifact("regressionScope", output),))
    if final:
        return _verify_correction(run, output, document)
    if _scope_corrections(run) >= regression_rounds():
        errors: list[str] = check_type(document.get("errors", []), list[str])
        raise StepError(VALIDATE, OTHER_CAUSE, (*errors, str(output)))
    purpose: str = "Correct the regression scope and validate it again"
    return Completion(
        artifacts=(file_artifact("regressionCorrection", output),),
        add=(StepGroup(tuple(_new(kind, purpose) for kind in RESCOPE)),),
    )


def _citations(run: StepRun) -> Path:
    """Write the Task's contract citations, from which regression.py verify derives each requirement's origin.

    Returns:
        The citations file: the bead's ``requirementIds``, its spec paths (``specPaths`` and ``specPath``), and
        its own ``acceptanceCriteria`` and ``definitionOfDone`` ids.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    specs: list[str] = list(check_type(bead.get("specPaths", []), list[str]))
    specs.extend([check_type(bead["specPath"], str)] if bead.get("specPath") else [])
    path: Path = run.context.work / "build" / str(run.step["id"]) / "citations.json"
    lists: tuple[str, ...] = ("requirementIds", "acceptanceCriteria", "definitionOfDone")
    write_json(
        path,
        {
            **{key: list(check_type(bead.get(key, []), list[str])) for key in lists},
            "specPaths": list(dict.fromkeys(specs)),
        },
    )
    return path


def _handback_harness(run: StepRun) -> list[str]:
    """Read the test and harness files every handback of the build names, those of removed steps included.

    A restart removes steps from the journal but keeps their edits in the worktree, so the handback a removed
    test writer left in the build's artifact folder is still the record of the files it wrote.

    Returns:
        Every path a handback's ``testFiles`` or ``harnessFiles`` names, in folder order; a field that is not a
        list of strings raises TypeCheckError.

    """
    documents: list[JsonValue] = [
        json.loads(handback.read_text(encoding="utf-8"))
        for handback in sorted((run.context.work / "build").glob(f"*/{HANDBACK}"))
    ]
    return [
        path
        for document in documents
        if isinstance(document, dict)
        for name in sorted(HARNESS_NAMES & document.keys())
        for path in check_type(document[name], list[str])
    ]


def _implementation_changes(run: StepRun) -> list[tuple[list[str], list[str]]]:
    """Read what each implementation changed and what of it it declared as harness, removed steps included.

    The accepted steps' ``changedFiles`` and ``harnessFiles`` values, and the same fields of every handback in the
    build's artifact folder that carries ``changedFiles``. A repository-setup correction records its own
    ``harnessFiles`` on the step that resumes the build, so a change made only to dependency manifests and test
    configuration, as such a correction makes, is no product change and is left out.

    Returns:
        Each implementation's changed files and declared harness files; a field that is not a list of strings raises
        TypeCheckError.

    """
    changes: list[tuple[list[str], list[str]]] = [
        (
            check_type(artifacts["changedFiles"], list[str]),
            check_type(artifacts.get(HARNESS_FILES, []), list[str]),
        )
        for artifacts in (
            {artifact["name"]: artifact["value"] for artifact in step["artifacts"] if artifact["kind"] == "value"}
            for step in accepted_steps(run)
        )
        if "changedFiles" in artifacts
    ]
    documents: list[JsonValue] = [
        json.loads(handback.read_text(encoding="utf-8"))
        for handback in sorted((run.context.work / "build").glob(f"*/{HANDBACK}"))
    ]
    changes.extend(
        (check_type(document["changedFiles"], list[str]), check_type(document.get(HARNESS_FILES, []), list[str]))
        for document in documents
        if isinstance(document, dict) and "changedFiles" in document
    )
    return [(changed, harness) for changed, harness in changes if not all(map(_declaration, changed))]


def _declaration(path: str) -> bool:
    """Report whether a changed file is a dependency manifest or test configuration (regression.py's list).

    Returns:
        True when its file name matches one of regression.py's HARNESS_CONFIGURATION patterns.

    """
    name: str = Path(path).name
    return any(fnmatch(name, pattern) for pattern in HARNESS_CONFIGURATION)


def _product_files(run: StepRun, tree: Path) -> list[str]:
    """List the files an implementation changed without declaring them as harness, relative to the build's tree.

    regression.py verify keeps such a dependency manifest or test configuration as it was before the change when
    no test writer declared it, and cannot replay on it when one did (declared and also changed for the product).

    Returns:
        The tree-relative paths, each once, sorted; a path outside the tree is left out.

    """
    listed: list[str] = [
        path for changed, harness in _implementation_changes(run) for path in changed if path not in harness
    ]
    root: Path = tree.resolve()
    resolved: list[Path] = [(tree / path).resolve() for path in listed]
    return sorted({str(path.relative_to(root)) for path in resolved if path.is_relative_to(root)})


def _harness_files(run: StepRun, tree: Path) -> list[str]:
    """List the test and harness files the build recorded, relative to its tree.

    Returns:
        The union of every accepted ``testFiles`` (the test writers') and ``harnessFiles`` (implementers' and
        repository-setup corrections'), and of the same fields of every handback in the build's artifact folder
        (:func:`_handback_harness`), each once, sorted; a path outside the tree is left out.

    """
    listed: list[str] = [
        path
        for step in accepted_steps(run)
        for artifact in step["artifacts"]
        if artifact["kind"] == "value" and artifact["name"] in HARNESS_NAMES
        for path in check_type(artifact["value"], list[str])
    ]
    listed.extend(_handback_harness(run))
    root: Path = tree.resolve()
    resolved: list[Path] = [(tree / path).resolve() for path in listed]
    return sorted({str(path.relative_to(root)) for path in resolved if path.is_relative_to(root)})


def _base_arguments(run: StepRun) -> list[str]:
    """Name the code before the Task's change, on which verification replays failing tests of existing requirements.

    The Task commits only at build:commit, so the worktree's HEAD is the revision it builds on. The replay base
    takes only the recorded test and harness files from the tree, less those an implementation also changed for
    the product; a changed dependency manifest or test configuration that none of them names, or that is both
    declared and changed for the product, leaves the replay unproven.

    Returns:
        The ``--tree``, ``--base-ref``, ``--harness-file`` and ``--product-file`` arguments of regression.py verify.

    """
    tree: Path = _workspace(run).tree
    head: str = run.tools.command(["git", "rev-parse", "HEAD"], stage=run.step["script"], cwd=tree).stdout.strip()
    harness: list[str] = [value for path in _harness_files(run, tree) for value in ("--harness-file", path)]
    product: list[str] = [value for path in _product_files(run, tree) for value in ("--product-file", path)]
    return ["--tree", str(tree), "--base-ref", head, *harness, *product]


def _origin_artifacts(document: dict[str, JsonValue]) -> tuple[ValueArtifact, ...]:
    """Record the origins verification derived or raised from the Task's contract, when there are any.

    Returns:
        The ``regressionOriginCorrections`` value, or nothing.

    """
    corrections: list[JsonValue] = check_type(document.get("originCorrections", []), list[JsonValue])
    return (value_artifact("regressionOriginCorrections", corrections),) if corrections else ()


def _unmet_artifacts(document: dict[str, JsonValue]) -> tuple[ValueArtifact, ...]:
    """Report the existing requirements the code did not meet before this Task, for the Epics that own them.

    Returns:
        The ``regressionUnmetBefore`` value and the same gaps carried as contract findings, or nothing.

    """
    unmet: list[JsonValue] = check_type(document.get("unmetBefore", []), list[JsonValue])
    if not unmet:
        return ()
    findings: list[JsonValue] = [
        {
            "severity": "improvement",
            "owner": "contract",
            "detail": f"{pair['requirementId']}: test {pair['testId']} fails before and after this Task; the code "
            "this Task builds on does not meet the requirement, and building it is the work of the Epic that "
            "owns it, not of this Task",
        }
        for pair in (json_object(entry) for entry in unmet)
    ]
    return (
        value_artifact("regressionUnmetBefore", unmet),
        build_carried.carry(
            "regressionEvidence",
            findings,
            "an existing requirement the code did not meet before this Task",
        ),
    )


def _corrections(run: StepRun) -> list[tuple[str, Path]]:
    """List the failure evidence each accepted step recorded as its regressionCorrection.

    Returns:
        Each correcting step's kind and evidence file, in walk order.

    """
    recorded: list[tuple[str, Path]] = []
    for step in accepted_steps(run):
        recorded.extend(
            (step["script"], Path(artifact["path"]))
            for artifact in step["artifacts"]
            if artifact["kind"] == "file" and artifact["name"] == "regressionCorrection"
        )
    return recorded


def _scope_corrections(run: StepRun) -> int:
    """Count the scope corrections since a corrected final verification last reopened the scope.

    A corrected final verification assesses the scope again for the changed tree, so the scope
    corrections before it, the ones made before implementation included, are spent on another scope.

    Returns:
        The corrected scope validations after the latest corrected final verification, or since
        the build began when no final verification was corrected.

    """
    kinds: list[str] = [kind for kind, _ in _corrections(run)]
    reopened: int = len(kinds) - kinds[::-1].index(VERIFY) if VERIFY in kinds else 0
    return kinds[reopened:].count(VALIDATE)


def _drift_only(failed: dict[str, JsonValue]) -> bool:
    """Report whether changed requirement source bytes are a failed final verification's only error.

    The checker adds the changed-bytes error last and runs no evidence while it stands, so a single
    error with ``sourcesChanged`` means the mapping review is approved and every required layer is
    mapped.

    Returns:
        True when the scope only needs assessing again for the current bytes.

    """
    return failed.get("sourcesChanged") is True and len(check_type(failed.get("errors", []), list[str])) == 1


def _verify_corrections(run: StepRun) -> tuple[int, int]:
    """Count the final verifications already corrected, by what their correction answered.

    Returns:
        The reassessments for changed source bytes alone, and the corrections of the mapping or the
        evidence it needs.

    """
    failures: list[dict[str, JsonValue]] = [
        json_object(json.loads(evidence.read_text(encoding="utf-8")))
        for kind, evidence in _corrections(run)
        if kind == VERIFY
    ]
    rescopes: int = sum(_drift_only(failed) for failed in failures)
    return rescopes, len(failures) - rescopes


def _verify_correction(run: StepRun, output: Path, document: dict[str, JsonValue]) -> Completion:
    """Correct a failed final verification inside the step, within its allowances.

    When changed source bytes, the build's own changes included, are the only error, the scope is
    assessed again for them before the evidence is mapped again; that is no correction of the
    mapping, so it has its own allowance. Any other failure, a blocking mapping review or an unmapped
    required layer included and whether or not the bytes also changed, is a correction: the test
    design lead selects the test writers for the tests the review found missing or not asserting
    their requirement, implementers make a failing new test pass, the final review covers the changed
    tree, and the scope is assessed for the changed tree before it is mapped, reviewed and verified
    again, which covers changed bytes too. The mapping alone cannot write a test that does not exist.

    Returns:
        The reassessment or correction steps.

    Raises:
        StepError: The failure's allowance is spent; it names every error and the evidence file.

    """
    changed: bool = _drift_only(document)
    rescopes, corrections = _verify_corrections(run)
    if (rescopes if changed else corrections) >= regression_rounds():
        errors: list[str] = check_type(document.get("errors", []), list[str])
        raise StepError(VERIFY, OTHER_CAUSE, (*errors, str(output)))
    keys: tuple[str, ...] = (*RESCOPE, *REMAP) if changed else (*EVIDENCE_WORK, *RESCOPE, *REMAP)
    purpose: str = (
        "Assess the regression scope for the changed sources, then map and verify its evidence"
        if changed
        else "Write the tests the regression mapping review found missing, then map and verify the evidence"
    )
    return Completion(
        artifacts=(file_artifact("regressionCorrection", output),),
        add=(StepGroup(tuple(_new(kind, purpose) for kind in keys)),),
    )


def _regression_tests(run: StepRun) -> Completion:
    """Have the test design lead select the writers of the tests a failed final verification needs.

    Returns:
        The lead's selection session, then the selected test writers and their suite check.

    """
    return reasoned(
        run,
        TEST_LEAD,
        OutputContract(CONTRACTS / "build-selection.schema.json", TEST_SELECTION),
        "Select the test specialists that write or change the tests the blocking findings of the latest "
        "regressionMappedReview and the failed verification in regressionCorrection need: a required layer of "
        "an impacted requirement with no test, and a mapped test that is absent, fails, or does not assert its "
        "requirement. A test of the Task's own requirement (origin task) that the current code fails is written "
        "all the same; implementation makes it pass. A test of an existing requirement that the code before this "
        "Task did not meet is not this Task's work: verification records it as unmetBefore, and no implementer "
        "changes product code for it. When the failed verification names undeclaredConfiguration (changed "
        "dependency manifests or test configuration no step declared, so its runs could not be replayed on the "
        "code before this Task), select a test specialist to read each file's change and declare in its testFiles "
        "each one changed only so the tests run, even when an earlier step changed it; a file whose change the "
        "product needs is never declared. Do not change governing requirements. An empty selection is valid only "
        "when every finding is corrected by the mapping alone and no undeclaredConfiguration is named",
        followups=(_new("build:plan-tests", "Write the tests the regression mapping needs"),),
    )


def _validate_initial(run: StepRun) -> Completion:
    """Validate reviewed scope.

    Returns:
        Validation evidence or corrections.

    """
    return _validate(run, False)


def _validate_final(run: StepRun) -> Completion:
    """Verify reviewed final evidence.

    Returns:
        Verification evidence or corrections.

    """
    return _validate(run, True)


def _reuse(run: StepRun) -> Completion:
    """Review use of shared capabilities instead of duplicating their implementation.

    Returns:
        The shared-capability specialist's independent review, or the policy's recorded omission.

    """
    decision: build_policy.Decision = build_policy.decide(run, "reuse-audit")
    if decision.action == "omit":
        return Completion(artifacts=(decision.artifact(),))
    reviewed: Completion = reasoned(
        run,
        "shared-capability-reviewer",
        OutputContract(CONTRACTS / "build-review.schema.json", "reuseReview"),
        "Review changed code against the shared capabilities the Task's matrix ids require",
        followups=(
            _new(
                "build:audit-reviewed",
                "Resolve the shared-capability review",
                {"review": "reuseReview", "again": "build:reuse-audit"},
            ),
        ),
    )
    return Completion(artifacts=(*reviewed.artifacts, decision.artifact()), add=reviewed.add)


def _cds(run: StepRun) -> Completion:
    """Review UI changes against the design source the Task actually records.

    Returns:
        A semantic CDS review and bounded correction consumer.

    """
    return reasoned(
        run,
        "cds-live-auditor",
        OutputContract(CONTRACTS / "build-review.schema.json", "cdsReview"),
        "Review changed UI against its recorded supplied bundle or live CDS design system",
        followups=(
            _new("build:audit-reviewed", "Resolve the CDS review", {"review": "cdsReview", "again": "build:cds-audit"}),
        ),
    )


def _design(run: StepRun) -> Completion:
    """Carry the Task's already-selected design source into its build journal.

    Returns:
        The stated source, bundle and build-spec paths without inventing another design.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    return Completion(
        artifacts=(
            value_artifact(
                "design",
                {
                    "designSource": bead.get("cdsDesignSource", "none"),
                    "bundle": bead.get("cdsBundlePath"),
                    "buildSpecs": bead.get("cdsBuildSpecs", []),
                },
            ),
        ),
    )


def _infrastructure(run: StepRun) -> Completion:
    """Make infrastructure implementation detail explicit through its real design specialist.

    Returns:
        A concrete provisioning-intent session.

    """
    return reasoned(
        run,
        "cdk-infrastructure-designer",
        OutputContract(CONTRACTS / "build-infrastructure.schema.json", "provisioning"),
        "Define concrete resources, stacks and cross-stack references for the Task's approved architecture",
    )


def _audit_reviewed(run: StepRun) -> Completion:
    """Correct the review's findings within the allowance, and never stop on a finding.

    Findings owned by the contract or the tooling are carried at once; findings still open when
    the correction allowance is spent are carried too, and the build continues.

    Returns:
        A clean review, the carried findings recorded, or implementation and repeat-review work.

    """
    params = run.params()
    name: str = check_type(params["review"], str)
    review: dict[str, JsonValue] = _document(run, name)
    required: list[JsonValue] = build_carried.required(check_type(review["findings"], list[JsonValue]))
    work: list[JsonValue] = build_carried.owned_here(required)
    reason: str = "its correction belongs to the contract or the tooling, or its correction allowance is spent"
    carried: tuple[ValueArtifact, ...] = (build_carried.carry(name, required, reason),) if required else ()
    if not work and (review["approved"] is True or required):
        return Completion(artifacts=carried)
    again: str = check_type(params["again"], str)
    if _count(run, again, name) >= build_rounds():
        return Completion(artifacts=carried)
    return Completion(
        add=(
            StepGroup((
                _new("build:correct-findings", "Resolve the independent review findings", {"review": name}),
                _new(again, "Re-review the corrected work against its prior findings"),
            )),
        ),
    )


def _correct(run: StepRun) -> Completion:
    """Select implementers for one review's unresolved findings, without a fresh whole-Task review.

    Returns:
        The implementation lead's selection for those findings and its plan.

    """
    review: str = check_type(run.params()["review"], str)
    return reasoned(
        run,
        "implementation-lead",
        OutputContract(CONTRACTS / "build-selection.schema.json", "implementationSelection"),
        f"Select the implementation specialists needed to resolve only the unresolved findings of the {review} "
        "review and the artifacts they name; accepted unrelated work stays as it is. Findings owned by the "
        "contract or the tooling are carried as recorded residuals and are not implementation work",
        followups=(_new("build:plan-code", "Plan the selected code specialists and suite check"),),
    )


def _docs(run: StepRun) -> Completion:
    """Select documentation specialists only for documents this change makes stale.

    Returns:
        The documentation lead's bounded subject judgment, or the policy's recorded omission.

    """
    decision: build_policy.Decision = build_policy.decide(run, "docs")
    if decision.action == "omit":
        return Completion(artifacts=(decision.artifact(),))
    selected: Completion = reasoned(
        run,
        "documentation-lead",
        OutputContract(CONTRACTS / "build-selection.schema.json", "documentationSelection"),
        "Select documentation specialists for the actual public and internal contracts changed by this Task",
        followups=(_new("build:docs-write", "Update the documentation this Task made stale"),),
    )
    return Completion(artifacts=(*selected.artifacts, decision.artifact()), add=selected.add)


def _docs_write(run: StepRun) -> Completion:
    """Plan the selected real documentation writers.

    Returns:
        Writer steps; no command relay or universal fixed documentation roster.

    """
    agents: list[str] = check_type(_document(run, "documentationSelection")["agents"], list[str])
    if not agents:
        return Completion()
    steps = tuple(
        _new("build:docs-specialist", f"Update stale documentation with {agent}", {"agent": agent}) for agent in agents
    )
    return Completion(add=(StepGroup(steps),))


def _docs_specialist(run: StepRun) -> Completion:
    """Start the documentation specialist chosen for the changed subject.

    Returns:
        Its genuine writing session.

    """
    agent: str = check_type(run.params()["agent"], str)
    return reasoned(
        run,
        agent,
        OutputContract(CONTRACTS / "build-implementation.schema.json", "documentationWork"),
        "Update the documents this Task's code and tests made stale",
    )


def attach_reviews(registry: Registry) -> None:
    """Register migration-compatible regression and documentation handler keys.

    Args:
        registry: The build flow's registry.

    Raises:
        TypeError: The registry is invalid.

    """
    if not isinstance(registry, Registry):
        message: str = "build reviews require Registry"
        raise TypeError(message)
    handlers = {
        "build:regression-assess": _scope_initial,
        "build:regression-reassess": _scope_initial,
        "build:regression-review": _review_initial,
        "build:regression-validate": _validate_initial,
        "build:regression-map": _scope_final,
        "build:regression-remap": _scope_final,
        "build:regression-map-review": _review_final,
        "build:regression-verify": _validate_final,
        "build:regression-tests": _regression_tests,
        "build:reuse-audit": _reuse,
        "build:cds-audit": _cds,
        "build:design-source": _design,
        "build:infra-intent": _infrastructure,
        "build:audit-reviewed": _audit_reviewed,
        "build:correct-findings": _correct,
        "build:docs-audit": _docs,
        "build:docs-write": _docs_write,
        "build:docs-specialist": _docs_specialist,
    }
    for key, handler in handlers.items():
        registry.script_step(key)(handler)
