"""Serialize integration, verify measured files, then publish only reviewed views."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator.core.tools import CommandResult

from datetime import UTC, datetime
from pathlib import Path

import archfiles
import archrevision
import archstate
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import LockTimeoutError, control_repo, file_lock, seconds
from orchestrator.flows.architecture_support import Architecture, ArchitectureStep, read


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
    lock: CommandResult = flow.tools.command(
        ["git", "rev-parse", "--git-path", "index.lock"],
        cwd=flow.arch,
        stage="commit",
    )
    cause: str = "contention" if (flow.arch / lock.stdout.strip()).exists() else "other"
    raise flow.tools.failure(stage, cause, result)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def integrate(flow: Architecture, target: dict[str, JsonValue]) -> dict[str, JsonValue]:
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
            raise StepError(stage, "contention", (str(exc),)) from exc

    return flow.tools.operation("integrate", operation)


def _integrate_locked(flow: Architecture, target: dict[str, JsonValue]) -> dict[str, JsonValue]:
    path: Path
    update: Path = flow.work / "architecture-update.json"
    inputs: tuple[str, ...] = (
        flow.base_inputs()
        + tuple(sorted(json_object(target.get("targetHashes", {}))))
        + (str(flow.work / "decision.json"),)
    )
    receipt: Path = flow.work / "integration-result.json"
    if flow.store.reusable(inputs, (receipt, update)):
        flow.runner.emit("note", kind="reused", step="architecture:integration")
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
    if not target.get("designChanged") and not target.get("documentationChanged") and not target.get("draftWritten"):
        files: list[str] = check_type(
            target.get("approvalFiles", []),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
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
        result: dict[str, JsonValue] = {
            "changedFiles": list(files),
            "createdFiles": [],
            "deletedFiles": [],
            "viewsChecked": [{"element": flow.subject, "view": path, "action": "updated"} for path in files],
            "constraintIssues": [],
            "contradictions": [],
            "summary": "Existing views approved.",
            "promotion": promoted,
        }
        write_json(update, result)
        flow.store.accept("architecture:integration", inputs, (update,))
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
        raise flow.tools.failure(stage, "other", result)
    if result.get("outside"):
        flow.runner.emit("note", kind="integration-outside", files=result["outside"])
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
                    "other",
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
    conforming: Path | bool | None = (
        latest and json_object(read(latest)).get("conforms") is True and flow.store.reusable(maint_inputs, (update,))
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
    review: dict[str, JsonValue] = {}
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
        review = json_object(
            flow.agent(
                ArchitectureStep(
                    "architecture-conformance-reviewer",
                    path,
                    "conformance",
                    review_inputs,
                    "Check the integrated architecture against the approved target.",
                ),
            ),
        )
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
    review: dict[str, JsonValue],
    checked: dict[str, JsonValue],
    maint_inputs: tuple[str, ...],
) -> dict[str, JsonValue]:
    update: Path = flow.work / "architecture-update.json"
    bad: set[str] = {
        check_type(f["file"], str)
        for f in check_type(
            review.get("findings", []),
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    }
    reviewed: list[str] = [
        p
        for p in check_type(
            review.get("reviewedFiles", []),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        if p not in bad
    ]
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
            "findings": review.get("findings", []),
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
