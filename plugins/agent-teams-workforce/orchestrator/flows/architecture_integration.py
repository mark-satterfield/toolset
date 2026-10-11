"""Serialize integration, verify measured files, then publish only reviewed views."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

# The architecture-artifact and target contracts are generated into the artifact-handoff skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import archfiles
import archrevision
import archstate
from architecture_artifacts import (
    CONFORMANCE_SCHEMA_PATH,
    ConformanceFinding,
    ConformanceResult,
    parse_conformance_result,
)
from target_contract import (
    KEY_APPROVAL_FILES,
    KEY_DESIGN_CHANGED,
    KEY_DOCUMENTATION_CHANGED,
    KEY_DRAFT_WRITTEN,
    KEY_TARGET_HASHES,
    TargetResult,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.handback_contract import (
    CONTENTION_CAUSE,
    OTHER_CAUSE,
    IntegrationOutsideNote,
    ReusedNote,
    integration_outside_note,
    reused_note,
)
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import LockTimeoutError, control_repo, file_lock, seconds
from orchestrator.flows.architecture_support import Architecture, ArchitectureStep, read
from orchestrator.flows.elaboration_support import emit_event

CONFORMANCE_SCHEMA: str = CONFORMANCE_SCHEMA_PATH.name.removesuffix(".schema.json")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def commit(flow: Architecture, files: list[str], message: str) -> None:
    """Commit and publish the reviewed architecture files.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)) or not (isinstance(files, list)) or not (isinstance(message, str)):
        argument_error: str = "commit: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    stage: str = "commit"
    if not files:
        return
    result: dict[str, JsonValue] = json_object(
        flow.call(
            "commit",
            archstate.commit_integration,
            str(flow.arch / "arc42"),
            files,
            message=message,
            execution_id=flow.context.run_id,
        ),
    )
    if result.get("ok"):
        return
    # Imported git writers report measured failures; Tools.git owns structural retry.
    if result.get("subcommand") == "push":
        flow.tools.git(flow.arch, ["push", "origin", "main"], stage="commit")
        return
    lock: str = flow.tools.command(
        ["git", "rev-parse", "--git-path", "index.lock"],
        cwd=flow.arch,
        stage="commit",
    ).stdout.strip()
    cause: str = CONTENTION_CAUSE if (flow.arch / lock).exists() else OTHER_CAUSE
    raise flow.tools.failure(stage, cause, result)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def integrate(flow: Architecture, target: TargetResult) -> dict[str, JsonValue]:
    """Integrate an approved target while holding the shared writer lock.

    Returns:
        The validated integration outcome.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)) or not (isinstance(target, dict)):
        argument_error: str = "integrate: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    stage: str = "integrate"

    def operation() -> dict[str, JsonValue]:
        try:
            with file_lock(
                control_repo() / "ops/sdlc-automation/state/arch-integrate.lock",
                seconds("ATW_ARCH_LOCK_WAIT", 120),
            ):
                return _integrate_locked(flow, target)
        except LockTimeoutError as exc:
            raise StepError(stage, CONTENTION_CAUSE, (str(exc),)) from exc

    return flow.tools.operation("integrate", operation)


def _integrate_locked(flow: Architecture, target: TargetResult) -> dict[str, JsonValue]:
    path: Path
    update: Path = flow.work / "architecture-update.json"
    inputs: tuple[str, ...] = (
        flow.base_inputs() + tuple(sorted(target.get(KEY_TARGET_HASHES, {}))) + (str(flow.work / "decision.json"),)
    )
    receipt: Path = flow.work / "integration-result.json"
    if flow.store.reusable(inputs, (receipt, update)):
        note: ReusedNote = reused_note(step="architecture:integration")
        emit_event(flow.runner.emit, note)
        return json_object(read(receipt))
    if receipt.exists():
        stale: Path = flow.work / ("stale-integration-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
        stale.mkdir()
        names: set[str] = {
            "integrate-before.json",
            "tree-last.json",
            "integration-files.json",
            "approved-coverage.json",
            "architecture-update.json",
            "integration-result.json",
        }
        for path in list(flow.work.iterdir()):
            if (
                path.name in names
                or path.name.removesuffix(".meta.json") in names
                or path.name.startswith("conformance-")
            ):
                path.rename(stale / path.name)
    json_object(
        flow.checked(
            flow.call("integrate", archrevision.mark, str(flow.arch), str(flow.work), "integrating"),
            "integrate",
        ),
    )
    if (
        not target.get(KEY_DESIGN_CHANGED)
        and not target.get(KEY_DOCUMENTATION_CHANGED)
        and not target.get(KEY_DRAFT_WRITTEN)
    ):
        files: list[str] = list(target.get(KEY_APPROVAL_FILES, []))
        promoted: dict[str, JsonValue] = json_object(
            flow.checked(
                flow.call("approve", archstate.promote, files, arch_root=str(flow.arch / "arc42"), reviewed=files),
                "approve",
            ),
        )
        commit(
            flow,
            files,
            f"docs(architecture): approve existing views for {flow.subject}",
        )
        publication: dict[str, JsonValue] = {
            "changedFiles": list(files),
            "createdFiles": [],
            "deletedFiles": [],
            "viewsChecked": [{"element": flow.subject, "view": path, "action": "updated"} for path in files],
            "constraintIssues": [],
            "contradictions": [],
            "summary": "Existing views approved.",
        }
        write_json(update, publication)
        flow.store.accept("architecture:integration", inputs, (update,))
        result: dict[str, JsonValue] = {**publication, "promotion": promoted}
    else:
        result = _full_integration(flow, inputs)
    json_object(
        flow.checked(
            flow.call("integrate", archrevision.mark, str(flow.arch), str(flow.work), "integrated"),
            "integrate",
        ),
    )
    write_json(receipt, result)
    flow.store.accept("architecture:integration", inputs, (receipt, update))
    return result


def _measure(flow: Architecture, update: Path, *, accumulate: bool) -> dict[str, JsonValue]:
    name: str
    text: str
    status: str
    stage: str = "integrate"
    last: Path = flow.work / "tree-last.json"
    result: dict[str, JsonValue] = json_object(
        flow.checked(
            flow.call(
                "integrate",
                archfiles.integration_files,
                str(flow.arch),
                archfiles.IntegrationOptions(
                    before=flow.work / "integrate-before.json",
                    report=update,
                    files_out=flow.work / "integration-files.json",
                    last=last if last.exists() else None,
                    save_last=last,
                    accumulate=accumulate,
                ),
            ),
            "integrate",
        ),
    )
    if result.get("section2"):
        raise flow.tools.failure(stage, OTHER_CAUSE, result)
    outside: JsonValue = result.get("outside")
    if isinstance(outside, list) and outside:
        note: IntegrationOutsideNote = integration_outside_note(files=outside)
        emit_event(flow.runner.emit, note)
    for name in check_type(result["touched"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS):
        path: Path = Path(name)
        if path.is_file() and path.is_relative_to(flow.arch / "arc42"):
            text, status = check_type(
                flow.call("integrate", archstate.set_state, path.read_text(encoding="utf-8"), "in-review"),
                tuple[str, str],
            )
            if status == "no-frontmatter":
                raise flow.tools.failure(
                    stage,
                    OTHER_CAUSE,
                    {
                        "file": name,
                        "error": "Integrated view has no lifecycle frontmatter",
                    },
                )
            path.write_text(text, encoding="utf-8")
    write_json(
        last,
        json_object(
            flow.checked(
                flow.call("integrate", archstate.snapshot_tree, str(flow.arch)),
                "integrate",
            ),
        ),
    )
    return result


def _full_integration(
    flow: Architecture,
    inputs: tuple[str, ...],
) -> dict[str, JsonValue]:
    correction: int
    before: Path = flow.work / "integrate-before.json"
    update: Path = flow.work / "architecture-update.json"
    if not before.exists():
        write_json(
            before,
            json_object(
                flow.checked(
                    flow.call("integrate", archstate.snapshot_tree, str(flow.arch)),
                    "integrate",
                ),
            ),
        )
    coverage: Path = flow.work / "approved-coverage.json"
    if not coverage.exists():
        write_json(coverage, {"result": flow.facts()})
    maint_inputs: tuple[str, ...] = (*inputs, str(flow.ledger_input("integration")))
    prior: list[Path] = sorted(flow.work.glob("conformance-*.json"))
    latest: Path | None = prior[-1] if prior else None
    conforming: bool = (
        latest is not None
        and parse_conformance_result(latest)["conforms"]
        and flow.store.reusable(maint_inputs, (update,))
    )
    if not conforming:
        extra: tuple[str] | tuple[()] = (str(latest),) if latest else ()
        json_object(
            flow.agent(
                ArchitectureStep(
                    "architecture-maintainer",
                    update,
                    "maintain",
                    maint_inputs + extra,
                    "Resume integration of the approved architecture."
                    if update.exists()
                    else "Integrate the approved architecture into effective views.",
                ),
            ),
        )
    measured: dict[str, JsonValue] = _measure(flow, update, accumulate=bool(prior))
    checked: dict[str, JsonValue] = {}
    review: ConformanceResult | None = None
    correction_limit: int = 3
    for correction in range(correction_limit):
        path: Path = flow.work / f"conformance-{correction}.json"
        review_inputs: tuple[str, ...] = (
            *inputs,
            str(update),
            str(flow.work / "integration-files.json"),
            str(coverage),
            str(flow.arch / "arc42"),
        )
        flow.agent(
            ArchitectureStep(
                "architecture-conformance-reviewer",
                path,
                CONFORMANCE_SCHEMA,
                review_inputs,
                "Check the integrated architecture against the approved target.",
            ),
        )
        review = parse_conformance_result(path)
        checked = json_object(
            flow.checked(
                flow.call(
                    "integrate",
                    archfiles.review_check,
                    path,
                    files=flow.work / "integration-files.json",
                    coverage_from=coverage,
                ),
                "integrate",
            ),
        )
        if checked["conforms"] and not checked["missed"] and not checked["coverageUnverified"]:
            break
        errors: Path = flow.work / f"conformance-{correction}.errors.json"
        write_json(errors, checked)
        if correction == correction_limit - 1:
            break
        json_object(
            flow.agent(
                ArchitectureStep(
                    "architecture-maintainer",
                    update,
                    "maintain",
                    (*maint_inputs, str(path), str(errors)),
                    "Correct the integration findings.",
                    stage=f"architecture:integration-correction-{correction + 1}",
                ),
            ),
        )
        measured = _measure(flow, update, accumulate=True)
        if not measured["changedSinceLast"]:
            break
    return _publish_integration(flow, measured, review, checked, maint_inputs)


def _publish_integration(
    flow: Architecture,
    measured: dict[str, JsonValue],
    review: ConformanceResult | None,
    checked: dict[str, JsonValue],
    maint_inputs: tuple[str, ...],
) -> dict[str, JsonValue]:
    update: Path = flow.work / "architecture-update.json"
    findings: list[ConformanceFinding] = review["findings"] if review is not None else []
    bad: set[str] = {finding["file"] for finding in findings}
    reviewed: list[str] = [p for p in (review["reviewedFiles"] if review is not None else []) if p not in bad]
    if checked.get("coverageUnverified"):
        reviewed = []
    promoted: dict[str, JsonValue] = json_object(
        flow.checked(
            flow.call(
                "approve",
                archstate.promote,
                check_type(measured["touched"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS),
                arch_root=str(flow.arch / "arc42"),
                reviewed=reviewed,
            ),
            "approve",
        ),
    )
    commit(
        flow,
        [
            p
            for p in check_type(measured["all"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
            if Path(p).is_relative_to(flow.arch / "arc42")
        ],
        f"docs(architecture): integrate the approved target for {flow.subject}",
    )
    flow.store.accept("architecture:integration", maint_inputs, (update,))
    return {
        "promotion": promoted,
        "openItems": {
            "findings": [json_object(finding) for finding in findings],
            "missed": checked.get("missed", []),
            "coverageUnverified": checked.get("coverageUnverified", []),
        },
        "changed": len(
            check_type(measured["touched"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS),
        ),
        "deleted": len(
            check_type(measured["deleted"], list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS),
        ),
    }
