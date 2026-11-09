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

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
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

if TYPE_CHECKING:
    from matrix_contract import EntryId

MATRIX_QUERIES: Final = "matrixQueries"
"""The value artifact counting the matrix queries the scope read made: subprocess commands, in-process reads, stacks."""


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


def _inside(root: Path, files: list[str]) -> None:
    """Reject paths outside the allowed architecture subtree.

    Raises:
        StepError: A reported or measured path escapes the subtree.

    """
    outside = [path for path in files if not Path(path).is_absolute() or not Path(path).resolve().is_relative_to(root)]
    if outside:
        msg = "built:bounds"
        raise StepError(msg, OTHER_CAUSE, (f"architecture writes outside {root}: {outside}",))


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
    scopes: list[StoryScope] = run.tools.portfolio("built:scope", _story_scopes, requests)
    request = (
        f"Compare deployed Story {run.context.bead} in {run.context.args['repoPath']} with effective "
        f"architecture {_root(run)}/arc42. Record differences only in {_root(run)}/built; "
        "do not edit effective architecture or section 2. Use the exact scope and headings below.\n"
        + json.dumps({"stacks": stacks, "entries": entries, "scopes": scopes}, ensure_ascii=False)
    )
    planned: Completion = reasoned(
        run,
        "built-architecture-comparer",
        OutputContract(SCHEMAS / "built-comparison.schema.json", "comparison"),
        request,
        followups=(_next("built:accept-comparison"),),
    )
    queries: dict[str, JsonValue] = {"commands": 1, "matrixReads": 1, "stacks": len(stacks)}
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
    measured = _changed(run, snapshot)
    differences = check_type(latest(run, "differences") or [], list[dict[str, JsonValue]])
    files = sorted(
        set(
            _strings(latest(run, "files"))
            + [check_type(row["file"], str) for row in differences]
            + measured["created"]
            + measured["changed"],
        ),
    )
    _inside(_root(run) / "built", [*files, *measured["deleted"]])
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
        file_artifact("treeCompared", saved),
    )
    return Completion(artifacts=artifacts, add=(StepGroup(additions),) if additions else ())


def _correct(run: StepRun) -> Completion:
    """Launch a bounded architecture-maintainer correction of measured built views.

    Returns:
        Its real agent child followed by deterministic write validation.

    """
    request = (
        f"Make effective architecture {_root(run)}/arc42 describe these built views: "
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
    """Measure all effective architecture changes, including files the agent omitted.

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
    measured = _changed(run, snapshot)
    update = json_object({
        **{
            key: sorted(set(_strings(earlier.get(key)) + _strings(latest(run, key)) + measured[measurement]))
            for key, measurement in (
                ("changedFiles", "changed"),
                ("createdFiles", "created"),
                ("deletedFiles", "deleted"),
            )
        },
        "matched": sorted(set(_strings(earlier.get("matched")) + _strings(latest(run, "matched")))),
    })
    touched = [path for key in ("changedFiles", "createdFiles", "deletedFiles") for path in _strings(update[key])]
    _inside(_root(run) / "arc42", touched)
    constraints = _root(run) / "arc42" / "02-architecture-constraints"
    if any(Path(path).resolve().is_relative_to(constraints) for path in touched):
        msg = "constraints-written"
        raise StepError(msg, OTHER_CAUSE, ("correction reports writing section 2",))
    changed_since = [path for paths in _changed(run, snapshot, 1).values() for path in paths] if previous else []
    if previous and not changed_since:
        msg = "correct"
        raise StepError(msg, OTHER_CAUSE, ("correction changed no file in response to findings",))
    return Completion(
        artifacts=(
            value_artifact("architectureUpdate", update),
            value_artifact("changedSinceLast", list(changed_since)),
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


def _accept_review(run: StepRun) -> Completion:
    """Reject omitted review coverage and bound repeated correction passes.

    Returns:
        Review artifact and the next correction or approval steps.

    Raises:
        StepError: The configured correction limit is exhausted.

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
        return Completion(
            artifacts=(value_artifact("conformance", conformance),),
            add=(StepGroup((addition("deploy:built-approve"), addition("deploy:built-remove"))),),
        )
    reference = json_object(_args(run)["journal"])
    parent = step_journal.find_step(run.journal(), StepId(check_type(reference["step"], str)))
    corrections = sum(step.get("script") == "deploy:built-correct" for step in step_journal.steps_in_order_from(parent))
    if corrections > built_rounds():
        msg = "correct"
        raise StepError(msg, OTHER_CAUSE, (f"architecture correction still fails review: {findings}",))
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

    Returns:
        The actual architecture promotion result.

    Raises:
        StepError: Promotion refuses an unreviewed or invalid file.

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
    if result.get("unreviewed") or result.get("refused") or result.get("failed"):
        msg = "approve"
        raise StepError(msg, OTHER_CAUSE, (f"architecture promotion refused: {result}",))
    return Completion(artifacts=(value_artifact("approval", json_object(result["summary"])),))


def _remove(run: StepRun) -> Completion:
    """Remove a built view only when both maintainer and reviewer say it now matches.

    Returns:
        The removed built view paths.

    Raises:
        StepError: Any built view remains unmatched.

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
    unmatched = set(built) - set(removable)
    if unmatched:
        msg = "correct"
        raise StepError(msg, OTHER_CAUSE, (f"unmatched built views retained: {sorted(unmatched)}",))
    return Completion(artifacts=(value_artifact("removedBuiltViews", list(removable)),))


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
        ),
    )
    if "removedBuiltViews" in results:
        results["removal"] = results.pop("removedBuiltViews")
    return handback(
        context,
        "recorded" if results.get("builtFiles") else "matches",
        f"Story {context.bead}: built architecture compared and reconciled",
        **results,
    )
