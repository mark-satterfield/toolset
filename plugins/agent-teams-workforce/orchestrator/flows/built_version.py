"""Compare deployed Story code with architecture and reconcile independently reviewed built views."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
from matrixquery import StoryScope, story_scope
from matrixstore import Matrix, as_entry_id, matrix_path, read_matrix
from step_journal_contract import StepId
from typeguard import check_type

from orchestrator.core import step_journal, tool_locks
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import Registry
from orchestrator.core.journal_steps import Completion, NewStep, StepGroup, StepRun, file_artifact, value_artifact
from orchestrator.core.models import RunContext, StepError
from orchestrator.flows.build_sessions import OutputContract, latest, reasoned
from orchestrator.flows.build_state import built_rounds
from orchestrator.flows.deploy_support import (
    PLUGIN,
    SCHEMAS,
    addition,
    arguments,
    command,
    depscore,
    execute,
    handback,
    recorded,
)
from orchestrator.flows.design_gaps import decided_at_build
from orchestrator.flows.elaboration_files import SPEC_FILES

if TYPE_CHECKING:
    from collections.abc import Callable

    from matrix_contract import EntryId

MATRIX_QUERIES: Final = "matrixQueries"
"""The value artifact counting the stack scopes that the step's one in-process matrix read served."""

CONCURRENT_WRITES: Final = "concurrentWrites"
"""The value artifact naming measured architecture changes that this Story's agents did not write."""

BUILT_VERSION_LOCK: Final = "ops/sdlc-automation/state/built-version.lock"
"""The lock file, under the control repository, that lets one Story's built-version write built/ at a time."""

LOCK_WAIT_ENV: Final = "ATW_BUILT_VERSION_LOCK_WAIT"
"""The environment variable bounding the seconds a built-version run waits for another to finish."""

LOCK_WAIT_SECONDS: Final = 3600.0
"""The default wait for the built-version lock."""

REPORTED_KEYS: Final = ("changedFiles", "createdFiles", "deletedFiles")
"""The file lists an architecture maintainer reports."""

EFFECTIVE_FOLDERS: Final = ("arc42", "detailed")
"""The folders of the architecture root that hold effective architecture."""

MIRRORED_PARTS: Final = 3
"""The fewest path parts under built/ that mirror an effective folder: subject, one folder, file name."""

MEASURED_KEYS: Final = ("created", "changed", "deleted")
"""The kinds of measured difference an architecture snapshot reports."""

CARRIED_FINDINGS: Final = "carriedFindings"
"""The value artifact holding the review findings still open when the correction rounds are spent."""

CARRIED_FILE: Final = "carriedFindingsFile"
"""The file artifact naming the JSON document that records the carried findings."""

RETAINED_VIEWS: Final = "retainedBuiltViews"
"""The value artifact naming built views kept because the carried findings leave them unmatched."""

CARRIED_NAME: Final = "built-version-carried.json"
"""The file name, in the Story's built-version artifact folder, of the carried findings record."""


def _args(run: StepRun) -> dict[str, JsonValue]:
    """Read validated built-version inputs.

    Returns:
        The leaf's declared arguments.

    """
    return arguments(run.context, "BuiltVersionArgs")


def _root(run: StepRun) -> Path:
    """Read the absolute architecture root.

    Returns:
        Its resolved path.

    """
    return Path(check_type(_args(run)["archPath"], str)).resolve()


def _ds(run: StepRun, tail: list[str]) -> dict[str, JsonValue]:
    """Execute an architecture portfolio operation directly.

    Returns:
        Its checked JSON object.

    """
    return depscore(run.tools, run.step.get("script", "built-version"), _args(run), tail)


def _strings(value: JsonValue) -> list[str]:
    """Validate a recorded list of paths or names.

    Returns:
        Nonempty trimmed strings.

    """
    return [text.strip() for text in check_type(value or [], list[str]) if text.strip()]


def _object(run: StepRun, name: str) -> dict[str, JsonValue]:
    """Read an accepted object artifact, otherwise an empty object.

    Returns:
        Its validated fields.

    """
    return json_object(latest(run, name) or {})


def _next(key: str) -> NewStep:
    """Plan an internal deterministic consumer after a reasoning agent.

    Returns:
        A journal step with a registered implementation.

    """
    return NewStep({"description": key, "purpose": "Validate the accepted architecture result", "script": key})


def _snapshot(run: StepRun, name: str, against: list[str]) -> tuple[Path, dict[str, JsonValue]]:
    """Save a measured architecture tree with one difference per earlier snapshot.

    Returns:
        Snapshot path and its checked differences.

    Raises:
        ValueError: A requested comparison is absent.

    """
    path = run.context.work / "built-version" / str(run.step["id"]) / f"{name}.json"
    tail = ["arch-snapshot", "--arch-root", str(_root(run)), "--save", str(path)]
    compared = _ds(run, [*tail, *(word for saved in against for word in ("--against", saved))])
    if len(check_type(compared.get("diffs") or [], list[JsonValue])) != len(against):
        msg = "architecture snapshot omitted a requested comparison"
        raise ValueError(msg)
    return path, compared


def _changed(run: StepRun, snapshot: dict[str, JsonValue], index: int = 0) -> dict[str, list[str]]:
    """Resolve measured differences relative to the architecture root.

    Returns:
        Created, changed and deleted absolute paths.

    """
    differences = check_type(snapshot["diffs"], list[dict[str, JsonValue]])
    return {
        key: [str(_root(run) / path) for path in _strings(differences[index].get(key))]
        for key in ("created", "changed", "deleted")
    }


def _guard(run: StepRun) -> None:
    """Restore section 2 and fail whenever its content or git state changed.

    Raises:
        StepError: Constraints changed, after restoration was attempted.

    """
    before = _object(run, "constraintsBefore")
    after = _ds(run, ["arch-constraints", "--arch-root", str(_root(run))])
    if all(before.get(key) == after.get(key) for key in ("exists", "digest", "gitStatus")):
        return
    kept = check_type(before["kept"], str)
    _ds(run, ["arch-constraints-restore", "--arch-root", str(_root(run)), "--kept", kept])
    msg = "constraints-written"
    raise StepError(msg, OTHER_CAUSE, ("section 2 changed; its saved version was restored",))


def _under(path: str, roots: tuple[Path, ...]) -> bool:
    """Report whether an absolute path lies under one of the roots.

    Returns:
        True when the path is absolute and inside a root.

    """
    return Path(path).is_absolute() and any(Path(path).resolve().is_relative_to(root) for root in roots)


def _inside(roots: tuple[Path, ...], files: list[str]) -> None:
    """Reject paths outside the allowed architecture subtrees.

    Raises:
        StepError: A reported or measured path escapes every subtree.

    """
    outside = [path for path in files if not _under(path, roots)]
    if outside:
        msg = "built:bounds"
        named = ", ".join(str(root) for root in roots)
        raise StepError(msg, OTHER_CAUSE, (f"architecture writes outside {named}: {outside}",))


def _effective(run: StepRun) -> tuple[Path, ...]:
    """Name the effective architecture folders a correction may write.

    Returns:
        The arc42 and detailed folders of the architecture root.

    """
    return tuple(_root(run) / folder for folder in EFFECTIVE_FOLDERS)


def _split(measured: dict[str, list[str]], own: Callable[[str], bool]) -> tuple[dict[str, list[str]], list[str]]:
    """Separate the measured changes this Story's agents own from concurrent writes by other sessions.

    Returns:
        The owned changes by kind, and every other measured path.

    """
    owned = {key: [path for path in measured[key] if own(path)] for key in MEASURED_KEYS}
    others = sorted({path for key in MEASURED_KEYS for path in measured[key] if not own(path)})
    return owned, others


def _mirrored_folder(root: Path, built_file: str) -> Path | None:
    """Locate the effective folder a built view describes (built/<subject>/<path> mirrors <path>).

    Returns:
        The folder of the mirrored effective document, or None for a file directly under a subject.

    """
    parts = Path(built_file).resolve().relative_to(root / "built").parts
    if len(parts) < MIRRORED_PARTS:
        return None
    return root.joinpath(*parts[1:]).parent


def _correction_owner(run: StepRun, reported: list[str]) -> Callable[[str], bool]:
    """Build the test of whether a measured effective change belongs to this Story's correction.

    A change belongs to it when it lies in effective architecture, in the folder of a file the
    maintainer reported or of the effective document a built view mirrors.

    Returns:
        The ownership test for one absolute path.

    """
    root = _root(run)
    effective = _effective(run)
    built = [path for path in _strings(latest(run, "builtFiles")) if _under(path, (root / "built",))]
    mirrored = {folder for path in built if (folder := _mirrored_folder(root, path)) is not None}
    folders = {Path(path).resolve().parent for path in reported} | mirrored
    return lambda path: _under(path, effective) and Path(path).resolve().parent in folders


def _start(run: StepRun) -> Completion:
    """Keep constraints and fingerprint the architecture before any session writes.

    Returns:
        The protected constraints and initial tree artifacts.

    """
    before = _ds(run, ["arch-constraints", "--arch-root", str(_root(run)), "--keep"])
    tree, _ = _snapshot(run, "tree-start", [])
    return Completion(artifacts=(value_artifact("constraintsBefore", before), file_artifact("treeStart", tree)))


def _story_scopes(requests: list[tuple[str, list[str]]]) -> list[StoryScope]:
    """Read every stack's story scope from one read of the matrix.

    Args:
        requests: Each stack id with the ids the Story built in it, in the order ``built`` listed the stacks.

    Returns:
        One scope per stack, as ``atw-matrix story-scope`` prints it, in the same order.

    """
    matrix: Matrix = read_matrix(matrix_path(None, os.environ))
    built: list[tuple[EntryId, list[EntryId]]] = [
        (as_entry_id(stack), [as_entry_id(stated) for stated in ids]) for stack, ids in requests
    ]
    return [story_scope(matrix, stack, ids) for stack, ids in built]


def _decided(run: StepRun) -> list[str]:
    """List the details the Story's spec documents left to the build, as the elaboration handed them on.

    Returns:
        Each decided-at-build row, naming its spec document; empty when the Story's journal holds
        no spec document or none leaves a detail to the build.

    """
    held: list[Path] = [Path(check_type(path, str)) for name in SPEC_FILES if (path := latest(run, name)) is not None]
    return [f"{path}: {row}" for path in held for row in decided_at_build(path)]


def _compare(run: StepRun) -> Completion:
    """Read the Story's recorded build scope and launch its architecture comparison.

    Returns:
        A genuine comparer session, or empty comparison artifacts for empty scope.

    Raises:
        StepError: Built entries have no architecture stack.

    """
    matrix = str(PLUGIN / "bin" / "atw-matrix")
    built = command(run.tools, "built:scope", [matrix, "built", "--story", run.context.bead])
    stacks = check_type(built["stacks"], list[dict[str, JsonValue]])
    entries = check_type(built["entries"], list[dict[str, JsonValue]])
    if not stacks and not entries:
        return Completion(artifacts=(value_artifact("differences", []), value_artifact("builtFiles", [])))
    if not stacks:
        msg = "compare"
        raise StepError(msg, OTHER_CAUSE, ("Story names built entries but no architecture stack",))
    requests: list[tuple[str, list[str]]] = [
        (check_type(stack["id"], str), [check_type(row["id"], str) for row in (entries or [stack])]) for stack in stacks
    ]
    scopes: list[StoryScope] = run.tools.portfolio_read("built:scope", _story_scopes, requests)
    request = (
        f"Compare deployed Story {run.context.bead} in {run.context.args['repoPath']} with effective "
        f"architecture {_root(run)}/arc42. Record differences only in {_root(run)}/built; "
        "do not edit effective architecture or section 2. Use the exact scope and headings below. "
        "Each row under decidedAtBuild is a detail the Story's spec left to the build because no approved "
        "document stated it: record the value the code chose for each as a difference.\n"
        + json.dumps(
            {"stacks": stacks, "entries": entries, "scopes": scopes, "decidedAtBuild": _decided(run)},
            ensure_ascii=False,
        )
    )
    planned: Completion = reasoned(
        run,
        "built-architecture-comparer",
        OutputContract(SCHEMAS / "built-comparison.schema.json", "comparison"),
        request,
        followups=(_next("built:accept-comparison"),),
    )
    queries: dict[str, JsonValue] = {"stackScopes": len(scopes)}
    return Completion(artifacts=(*planned.artifacts, value_artifact(MATRIX_QUERIES, queries)), add=planned.add)


def _accept_comparison(run: StepRun) -> Completion:
    """Measure comparison writes and require complete in-review built views.

    Returns:
        Comparison artifacts and the correction and review steps when differences exist.

    Raises:
        StepError: Measured writes or built view states violate the comparison contract.

    """
    _guard(run)
    saved, snapshot = _snapshot(run, "tree-compared", [check_type(latest(run, "treeStart"), str)])
    built = (_root(run) / "built",)
    measured, concurrent = _split(_changed(run, snapshot), lambda path: _under(path, built))
    differences = check_type(latest(run, "differences") or [], list[dict[str, JsonValue]])
    files = sorted(
        set(
            _strings(latest(run, "files"))
            + [check_type(row["file"], str) for row in differences]
            + measured["created"]
            + measured["changed"],
        ),
    )
    _inside(built, files)
    if bool(files) != bool(differences):
        msg = "compare"
        raise StepError(msg, OTHER_CAUSE, ("comparison must record both differences and built views",))
    if files:
        state = _ds(run, ["arch-state", "--arch-root", str(_root(run)), "--arch-files", ",".join(files)])
        bad_states = any(value != "in-review" for value in json_object(state["states"]).values())
        if state.get("refused") or state.get("failed") or bad_states:
            msg = "compare"
            raise StepError(msg, OTHER_CAUSE, (f"built views must be in-review: {state}",))
    additions = (addition("deploy:built-correct"), addition("deploy:built-review")) if files else ()
    artifacts = (
        value_artifact("differences", list(differences)),
        value_artifact("builtFiles", list(files)),
        value_artifact(CONCURRENT_WRITES, list(concurrent)),
        file_artifact("treeCompared", saved),
    )
    return Completion(artifacts=artifacts, add=(StepGroup(additions),) if additions else ())


def _correct(run: StepRun) -> Completion:
    """Launch a bounded architecture-maintainer correction of measured built views.

    Returns:
        Its real agent child followed by deterministic write validation.

    """
    request = (
        f"Make effective architecture {_root(run)}/arc42 and {_root(run)}/detailed describe these built views: "
        f"{_strings(latest(run, 'builtFiles'))}. Preserve section 2 and write nowhere else. "
        "Report every changed, created or deleted file and matched built view. "
        f"Answer these findings: {json.dumps(run.params().get('findings') or [])}"
    )
    return reasoned(
        run,
        "architecture-maintainer",
        OutputContract(SCHEMAS / "built-maintenance.schema.json", "maintenance"),
        request,
        followups=(_next("built:accept-correction"),),
    )


def _accept_correction(run: StepRun) -> Completion:
    """Accept the maintainer's reported changes and the measured changes in the folders it works in.

    Measured changes elsewhere were written by other sessions (for example an elaboration's
    architecture maintainer) and are recorded as concurrent writes, never reviewed or promoted here.

    Returns:
        Cumulative update and fingerprints for independent review.

    Raises:
        StepError: Corrections change constraints or make no progress against findings.

    """
    _guard(run)
    earlier = _object(run, "architectureUpdate")
    against = [check_type(latest(run, "treeCompared"), str)]
    previous = latest(run, "treeLast")
    if previous:
        against.append(check_type(previous, str))
    saved, snapshot = _snapshot(run, "tree-last", against)
    reported = {key: _strings(earlier.get(key)) + _strings(latest(run, key)) for key in REPORTED_KEYS}
    own = _correction_owner(run, [path for paths in reported.values() for path in paths])
    measured, concurrent = _split(_changed(run, snapshot), own)
    update = json_object({
        **{
            key: sorted(set(reported[key] + measured[measurement]))
            for key, measurement in (
                ("changedFiles", "changed"),
                ("createdFiles", "created"),
                ("deletedFiles", "deleted"),
            )
        },
        "matched": sorted(set(_strings(earlier.get("matched")) + _strings(latest(run, "matched")))),
    })
    touched = [path for key in ("changedFiles", "createdFiles", "deletedFiles") for path in _strings(update[key])]
    _inside(_effective(run), touched)
    constraints = _root(run) / "arc42" / "02-architecture-constraints"
    if any(Path(path).resolve().is_relative_to(constraints) for path in touched):
        msg = "constraints-written"
        raise StepError(msg, OTHER_CAUSE, ("correction reports writing section 2",))
    since_last = _split(_changed(run, snapshot, 1), own)[0] if previous else {}
    changed_since = [path for paths in since_last.values() for path in paths]
    if previous and not changed_since:
        msg = "correct"
        raise StepError(msg, OTHER_CAUSE, ("correction changed no file in response to findings",))
    return Completion(
        artifacts=(
            value_artifact("architectureUpdate", update),
            value_artifact("changedSinceLast", list(changed_since)),
            value_artifact(CONCURRENT_WRITES, list(concurrent)),
            file_artifact("treeLast", saved),
        ),
    )


def _review(run: StepRun) -> Completion:
    """Launch independent review of every measured effective architecture write.

    Returns:
        Its reviewer session and deterministic review adjudication.

    """
    request = (
        f"Review the effective architecture correction at {_root(run)} against built views "
        f"{_strings(latest(run, 'builtFiles'))}. Review every created and changed file; "
        "name reviewedFiles and matchedBuiltViews. Do not write architecture.\n"
        + json.dumps(_object(run, "architectureUpdate"), ensure_ascii=False)
    )
    return reasoned(
        run,
        "architecture-conformance-reviewer",
        OutputContract(SCHEMAS / "built-conformance.schema.json", "review"),
        request,
        followups=(_next("built:accept-review"),),
    )


def _approval() -> tuple[StepGroup, ...]:
    """Plan the promotion of the reviewed correction and the removal of matched built views.

    Returns:
        The approve and remove steps as one group.

    """
    return (StepGroup((addition("deploy:built-approve"), addition("deploy:built-remove"))),)


def _corrections(run: StepRun) -> int:
    """Count the correction passes the Story's built-version step has planned.

    Returns:
        The number of ``deploy:built-correct`` steps under the dispatched step.

    """
    reference = json_object(_args(run)["journal"])
    parent = step_journal.find_step(run.journal(), StepId(check_type(reference["step"], str)))
    return sum(step.get("script") == "deploy:built-correct" for step in step_journal.steps_in_order_from(parent))


def _carry(run: StepRun, findings: list[dict[str, JsonValue]], retained: list[str]) -> Path:
    """Write the record of the findings and built views the Story carries to its pull request.

    Returns:
        The record's path in the Story's built-version artifact folder.

    """
    path = run.context.work / "built-version" / CARRIED_NAME
    write_json(path, {"story": run.context.bead, CARRIED_FINDINGS: findings, RETAINED_VIEWS: retained})
    return path


def _carried(run: StepRun) -> list[dict[str, JsonValue]]:
    """Read the findings the review carried when its correction rounds were spent.

    Returns:
        The carried findings; empty when the review approved the correction.

    """
    return check_type(latest(run, CARRIED_FINDINGS) or [], list[dict[str, JsonValue]])


def _accept_review(run: StepRun) -> Completion:
    """Reject omitted review coverage, bound repeated correction passes and carry what is left.

    When the correction rounds are spent and findings remain, the latest correction stands: the
    findings are carried, as a value and a file, and the approval steps follow as for a
    conforming review.

    Returns:
        Review artifact and the next correction or approval steps.

    """
    _guard(run)
    update = _object(run, "architectureUpdate")
    touched = set(_strings(update.get("changedFiles")) + _strings(update.get("createdFiles")))
    findings = check_type(latest(run, "findings") or [], list[dict[str, JsonValue]])
    missed = touched - set(_strings(latest(run, "reviewedFiles")))
    findings.extend(
        {"file": path, "finding": "changed file was not reviewed", "evidence": "absent from reviewedFiles"}
        for path in sorted(missed)
    )
    conformance = json_object({
        "conforms": latest(run, "conforms") is True and not findings,
        "findings": list(findings),
        "reviewedFiles": _strings(latest(run, "reviewedFiles")),
        "matchedBuiltViews": _strings(latest(run, "matchedBuiltViews")),
    })
    if conformance["conforms"] is True:
        return Completion(artifacts=(value_artifact("conformance", conformance),), add=_approval())
    if _corrections(run) > built_rounds():
        carried: list[dict[str, JsonValue]] = list(findings)
        return Completion(
            artifacts=(
                value_artifact("conformance", conformance),
                value_artifact(CARRIED_FINDINGS, list(carried)),
                file_artifact(CARRIED_FILE, _carry(run, carried, [])),
            ),
            add=_approval(),
        )
    return Completion(
        artifacts=(value_artifact("conformance", conformance),),
        add=(
            StepGroup((
                addition("deploy:built-correct", {"findings": list(findings)}),
                addition("deploy:built-review"),
            )),
        ),
    )


def _approve(run: StepRun) -> Completion:
    """Promote only independently reviewed effective architecture files.

    A file the review did not cover is left unpromoted without failing when the review carried
    it as a finding.

    Returns:
        The actual architecture promotion result.

    Raises:
        StepError: Promotion refuses an invalid file or an unreviewed file that is not carried.

    """
    _guard(run)
    update = _object(run, "architectureUpdate")
    files = sorted(set(_strings(update.get("changedFiles")) + _strings(update.get("createdFiles"))))
    review = _object(run, "conformance")
    if not files:
        return Completion(artifacts=(value_artifact("approval", {"promoted": 0, "unchanged": 0}),))
    result = _ds(
        run,
        [
            "arch-approve",
            "--arch-root",
            str(_root(run)),
            "--arch-files",
            ",".join(files),
            "--reviewed-files",
            ",".join(_strings(review.get("reviewedFiles"))),
        ],
    )
    carried = {str(Path(check_type(row.get("file"), str)).resolve()) for row in _carried(run)}
    uncarried = [path for path in _strings(result.get("unreviewed")) if path not in carried]
    if uncarried or result.get("refused") or result.get("failed"):
        msg = "approve"
        raise StepError(msg, OTHER_CAUSE, (f"architecture promotion refused: {result}",))
    return Completion(artifacts=(value_artifact("approval", json_object(result["summary"])),))


def _remove(run: StepRun) -> Completion:
    """Remove a built view only when both maintainer and reviewer say it now matches.

    When the review carried findings, the built views left unmatched are kept and carried with
    them instead of failing the Story.

    Returns:
        The removed built view paths, and any retained views with their carried record.

    Raises:
        StepError: A built view remains unmatched and the review carried no findings.

    """
    built = _strings(latest(run, "builtFiles"))
    matched = set(_strings(_object(run, "architectureUpdate").get("matched")))
    reviewed = set(_strings(_object(run, "conformance").get("matchedBuiltViews")))
    removable = [path for path in built if path in matched & reviewed]
    if removable:
        _ds(
            run,
            [
                "arch-built-remove",
                "--arch-root",
                str(_root(run)),
                "--files",
                ",".join(removable),
                "--message",
                f"docs(architecture): remove matched built views of Story {run.context.bead}",
            ],
        )
    unmatched = sorted(set(built) - set(removable))
    carried = _carried(run)
    if unmatched and not carried:
        msg = "correct"
        raise StepError(msg, OTHER_CAUSE, (f"unmatched built views retained: {unmatched}",))
    removed = value_artifact("removedBuiltViews", list(removable))
    if not unmatched:
        return Completion(artifacts=(removed,))
    record = _carry(run, carried, unmatched)
    return Completion(
        artifacts=(removed, value_artifact(RETAINED_VIEWS, list(unmatched)), file_artifact(CARRIED_FILE, record)),
    )


def run(context: RunContext) -> dict[str, JsonValue]:
    """Run the Story's architecture reconciliation in its existing scoped journal.

    Returns:
        The driver's built-version result and accepted architecture artifacts.

    """
    args = arguments(context, "BuiltVersionArgs")
    registry = Registry()
    handlers = {
        "deploy:built-snapshot": _start,
        "deploy:built-compare": _compare,
        "built:accept-comparison": _accept_comparison,
        "deploy:built-correct": _correct,
        "built:accept-correction": _accept_correction,
        "deploy:built-review": _review,
        "built:accept-review": _accept_review,
        "deploy:built-approve": _approve,
        "deploy:built-remove": _remove,
    }
    for key, handler in handlers.items():
        registry.script_step(key)(handler)
    lock = tool_locks.control_repo() / BUILT_VERSION_LOCK
    wait = tool_locks.seconds(LOCK_WAIT_ENV, LOCK_WAIT_SECONDS)
    with tool_locks.file_lock(lock, wait, f"built-version {context.bead}"):
        runner = execute(context, args, "deploy:built-version", registry)
    results = recorded(
        runner,
        (
            "differences",
            "builtFiles",
            "architectureUpdate",
            "conformance",
            "approval",
            "removedBuiltViews",
            CARRIED_FINDINGS,
            CARRIED_FILE,
            RETAINED_VIEWS,
        ),
    )
    if "removedBuiltViews" in results:
        results["removal"] = results.pop("removedBuiltViews")
    return handback(
        context,
        "recorded" if results.get("builtFiles") else "matches",
        _headline(context.bead, results),
        **results,
    )


def _headline(bead: str, results: dict[str, JsonValue]) -> str:
    """Say how the Story's architecture reconciliation ended, naming any carried findings.

    Returns:
        The handback headline.

    """
    headline = f"Story {bead}: built architecture compared and reconciled"
    carried = check_type(results.get(CARRIED_FINDINGS) or [], list[JsonValue])
    if not carried:
        return headline
    return f"{headline}; {len(carried)} review findings carried to the pull request in {results.get(CARRIED_FILE)}"
