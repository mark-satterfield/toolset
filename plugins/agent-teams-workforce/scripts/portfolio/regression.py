"""Validate cumulative requirement coverage and confirm fresh JUnit execution evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - The tool exists to run the mapped suite commands.
import sys
import time
import xml.etree.ElementTree as ET  # ruff: ignore[suspicious-xml-etree-import] - Bundled expat 2.7.4 mitigates entity expansion and external entities are never resolved.
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from contracts import JsonObject, JsonValue, json_object
from gitutils import cmd_hash_files
from jsonartifact import read_artifact

KINDS: Final[frozenset[str]] = frozenset({"unit", "contract", "integration", "nonfunctional"})
EXECUTION_BUDGET_SECONDS: Final[int] = 500

type Mode = Literal["prepare", "validate", "verify"]
MODES: Final[dict[str, Mode]] = {"prepare": "prepare", "validate": "validate", "verify": "verify"}


@dataclass(frozen=True, slots=True)
class CliArgs:
    """The validated command line."""

    mode: Mode
    plan: str
    ledger: str
    review: str | None
    source: list[str]
    approved_plan: str | None
    output: str


def _str(obj: JsonObject, key: str) -> str:
    """Read a required string field.

    Returns:
        The field's string value.

    Raises:
        TypeError: The field is not a string.

    """
    value: JsonValue = obj[key]
    if not isinstance(value, str):
        message: str = f"{key}: expected a string"
        raise TypeError(message)
    return value


def _obj(obj: JsonObject, key: str) -> JsonObject:
    """Read a required object field.

    Returns:
        The field's object value.

    Raises:
        TypeError: The field is not an object.

    """
    value: JsonValue = obj[key]
    if not isinstance(value, dict):
        message: str = f"{key}: expected an object"
        raise TypeError(message)
    return value


def _objs(obj: JsonObject, key: str) -> list[JsonObject]:
    """Read a required list-of-objects field.

    Returns:
        The field's objects.

    Raises:
        TypeError: The field is not a list of objects.

    """
    value: JsonValue = obj[key]
    if not isinstance(value, list):
        message: str = f"{key}: expected a list"
        raise TypeError(message)
    result: list[JsonObject] = []
    for item in value:
        if not isinstance(item, dict):
            message = f"{key}: expected a list of objects"
            raise TypeError(message)
        result.append(item)
    return result


def _strs(obj: JsonObject, key: str) -> list[str]:
    """Read a required list-of-strings field.

    Returns:
        The field's strings.

    Raises:
        TypeError: The field is not a list of strings.

    """
    value: JsonValue = obj[key]
    if not isinstance(value, list):
        message: str = f"{key}: expected a list"
        raise TypeError(message)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            message = f"{key}: expected a list of strings"
            raise TypeError(message)
        result.append(item)
    return result


def _optional_objs(obj: JsonObject | None, key: str) -> list[JsonObject]:
    """Read an optional list-of-objects field, absent meaning empty.

    Returns:
        The field's objects, or an empty list when the object or field is absent.

    """
    if obj is None or key not in obj:
        return []
    return _objs(obj, key)


def _optional_strs(obj: JsonObject | None, key: str) -> list[str]:
    """Read an optional list-of-strings field, absent meaning empty.

    Returns:
        The field's strings, or an empty list when the object or field is absent.

    """
    if obj is None or key not in obj:
        return []
    return _strs(obj, key)


def _flag(obj: JsonObject, key: str) -> bool:
    """Read a required field by its JSON truthiness.

    Returns:
        Whether the field's value is truthy.

    """
    return bool(obj[key])


def read(path: str | Path) -> JsonObject:
    """Read an authoritative artifact, including publication receipts when present.

    Returns:
        The artifact's JSON object.

    """
    return json_object(read_artifact(Path(path)))


def write(path: str | Path, value: JsonValue) -> None:
    """Publish deterministic state atomically."""
    target: Path = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)


def source_hashes(paths: list[str]) -> dict[str, str]:
    """Bind the actual source bytes, independent of model-authored evidence prose.

    Returns:
        The SHA-256 of each source file, keyed by its path.

    Raises:
        ValueError: A source is not an absolute readable file.

    """
    result: dict[str, str] = {}
    for value in paths:
        path: Path = Path(value)
        if not path.is_absolute() or not path.is_file():
            message: str = f"Requirement source is not an absolute readable file: {value}"
            raise ValueError(message)
        result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def scope(plan: JsonObject) -> JsonObject:
    """Only mapping and execution configuration may change after scope approval.

    Returns:
        The plan fields that fix the approved scope.

    """
    return {k: plan[k] for k in ("components", "discovery", "requirements", "sourceFiles")}


def _discovery_errors(plan: JsonObject, requirements: list[JsonObject]) -> list[str]:
    """Check that discovery is evidenced and some impacted requirement needs tests.

    Returns:
        The discovery errors.

    """
    errors: list[str] = []
    discovery: JsonObject = _obj(plan, "discovery")
    if (
        not _flag(discovery, "priorRequirementsSearched")
        or not _flag(discovery, "sourceRefs")
        or not _str(discovery, "evidence").strip()
    ):
        errors.append("Prior product requirements and affected dependencies were not evidenced")
    if not _flag(plan, "sourceFiles"):
        errors.append("Requirement discovery has no physical source files")
    if not any(
        _flag(r, "impacted") and any(_flag(a, "required") for a in _objs(r, "applicability")) for r in requirements
    ):
        errors.append("Build has no impacted requirement with required test coverage")
    return errors


def _requirement_errors(plan: JsonObject, requirements: list[JsonObject], ids: list[str]) -> list[str]:
    """Check requirement identity, bindings and layer dispositions.

    Returns:
        The requirement errors.

    """
    errors: list[str] = []
    if not ids or len(ids) != len(set(ids)):
        errors.append("Requirement IDs must be nonempty, source-qualified and unique")
    component_ids: set[str] = {_str(c, "id") for c in _objs(plan, "components")}
    for r in requirements:
        rid: str = _str(r, "id")
        if (
            not _str(r, "sourceRef").strip()
            or not _flag(r, "componentIds")
            or not set(_strs(r, "componentIds")) <= component_ids
        ):
            errors.append(f"{rid}: missing source or component binding")
        layers: list[JsonObject] = _objs(r, "applicability")
        if {_str(a, "kind") for a in layers} != KINDS or len(layers) != len(KINDS):
            errors.append(f"{rid}: every test layer needs an applicability disposition")
        if any(not _str(a, "reason").strip() or not _flag(a, "sourceRefs") for a in layers):
            errors.append(f"{rid}: applicability lacks source evidence")
    return errors


def _coverage_errors(plan: JsonObject, requirements: list[JsonObject], ids: list[str]) -> list[str]:
    """Check that every required impacted layer maps to concrete tests in a matching run.

    Returns:
        The coverage errors.

    """
    errors: list[str] = []
    plan_runs: list[JsonObject] = _objs(plan, "runs")
    runs: dict[str, JsonObject] = {_str(r, "id"): r for r in plan_runs}
    if len(runs) != len(plan_runs):
        errors.append("Duplicate run IDs")
    mappings: list[JsonObject] = _objs(plan, "mappings")
    for req in requirements:
        if not _flag(req, "impacted"):
            continue
        req_id: str = _str(req, "id")
        for layer in _objs(req, "applicability"):
            if not _flag(layer, "required"):
                continue
            kind: str = _str(layer, "kind")
            matched: list[JsonObject] = [
                m for m in mappings if _str(m, "requirementId") == req_id and _str(m, "kind") == kind
            ]
            if not matched or any(not _flag(m, "testIds") for m in matched):
                errors.append(f"{req_id}/{kind}: no concrete tests")
            for m in matched:
                run: JsonObject | None = runs.get(_str(m, "runId"))
                if not run or run["repoPath"] != req["repoPath"]:
                    errors.append(f"{req_id}: mapping has no matching repository execution")
        errors.extend(
            "Mapping references unknown requirement/run"
            for m in mappings
            if _str(m, "requirementId") not in ids or _str(m, "runId") not in runs
        )
    return errors


def _prior_mapping_errors(plan: JsonObject, previous: JsonObject | None, superseded: set[str]) -> list[str]:
    """Check that prior test mappings survive unless explicitly replaced or superseded.

    Returns:
        The prior-mapping errors.

    """
    errors: list[str] = []
    mappings: list[JsonObject] = _objs(plan, "mappings")
    for mapping in _optional_objs(previous, "mappings"):
        requirement_id: str = _str(mapping, "requirementId")
        if requirement_id in superseded:
            continue
        kind: str = _str(mapping, "kind")
        retained: set[str] = {
            test
            for m in mappings
            if _str(m, "requirementId") == requirement_id and _str(m, "kind") == kind
            for test in _strs(m, "testIds")
        }
        replaced: set[str] = {
            _str(replacement, "oldTestId")
            for replacement in _optional_objs(plan, "replacements")
            if _str(replacement, "requirementId") == requirement_id
            and _str(replacement, "kind") == kind
            and _str(replacement, "reason").strip()
            and _flag(replacement, "newTestIds")
            and set(_strs(replacement, "newTestIds")) <= retained
        }
        if not set(_strs(mapping, "testIds")) <= retained | replaced:
            errors.append(f"{requirement_id}: prior test mapping removed without explicit supersession")
    return errors


def _prior_layer_errors(
    requirements: list[JsonObject],
    old: dict[str, JsonObject],
    ids: list[str],
    superseded: set[str],
) -> list[str]:
    """Check that a previously required layer stays required unless superseded.

    Returns:
        The prior-layer errors.

    """
    errors: list[str] = []
    for req_id in old.keys() & set(ids):
        now: JsonObject = next(r for r in requirements if _str(r, "id") == req_id)
        authorized: bool = req_id in superseded
        now_layers: list[JsonObject] = _objs(now, "applicability")
        errors.extend(
            f"{req_id}: previously required layer removed without supersession"
            for layer in _objs(old[req_id], "applicability")
            if _flag(layer, "required")
            and not any(_str(a, "kind") == _str(layer, "kind") and _flag(a, "required") for a in now_layers)
            and not authorized
        )
    return errors


def validate(plan: JsonObject, previous: JsonObject | None = None, *, complete: bool = False) -> list[str]:
    """Reject incomplete discovery, missing old obligations, and unmapped layers.

    Returns:
        Every validation error; empty when the plan is acceptable.

    """
    requirements: list[JsonObject] = _objs(plan, "requirements")
    errors: list[str] = _discovery_errors(plan, requirements)
    ids: list[str] = [_str(r, "id") for r in requirements]
    errors.extend(_requirement_errors(plan, requirements, ids))
    old: dict[str, JsonObject] = {_str(r, "id"): r for r in _optional_objs(previous, "requirements")}
    superseded: set[str] = {
        _str(s, "id")
        for r in requirements
        for s in _objs(r, "supersedes")
        if _str(s, "sourceRef").strip() and _str(s, "reason").strip()
    }
    errors.extend(
        f"{missing}: prior requirement dropped without explicit supersession"
        for missing in old.keys() - set(ids) - superseded
    )
    if old and _flag(_obj(plan, "discovery"), "greenfield"):
        errors.append("Existing cumulative requirements contradict greenfield declaration")
    if complete:
        errors.extend(_coverage_errors(plan, requirements, ids))
        errors.extend(_prior_mapping_errors(plan, previous, superseded))
        errors.extend(_prior_layer_errors(requirements, old, ids, superseded))
    return errors


def junit_results(report: Path, run_id: str) -> tuple[set[str], list[str]]:
    """Parse only executed passing cases; collection errors and duplicates fail closed.

    Returns:
        The IDs of passing tests and the report errors.

    """
    tree: ET.ElementTree[ET.Element] = ET.parse(report)  # ruff: ignore[suspicious-xml-element-tree-usage] - Bundled expat 2.7.4 mitigates entity expansion and external entities are never resolved.
    passed: set[str] = set()
    all_ids: set[str] = set()
    errors: list[str] = []
    if tree.getroot().tag not in {"testsuites", "testsuite"}:
        errors.append(f"{run_id}: unsupported JUnit root")
    if any(case.find(tag) is not None for case in tree.iter("testcase") for tag in ("failure", "error")):
        errors.append(f"{run_id}: report contains failed/error tests despite command exit zero")
    errors.extend(
        f"{run_id}: suite reports failures or errors"
        for suite in (node for node in tree.iter() if node.tag in {"testsuite", "testsuites"})
        if any(bool(float(suite.get(key, "0"))) for key in ("errors", "failures")) or suite.find("error") is not None
    )
    for case in tree.iter("testcase"):
        test_id: str = f"{case.get('classname', '')}::{case.get('name', '')}"
        if test_id in all_ids:
            errors.append(f"{run_id}: ambiguous duplicate test ID {test_id}")
        all_ids.add(test_id)
        executed: bool = case.get("status", "run").lower() in {"run", "passed", "success"} and case.get(
            "result",
            "completed",
        ).lower() in {"completed", "passed", "success"}
        if executed and not any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
            passed.add(test_id)
    return passed, errors


def _report_path(run: JsonObject, root: Path) -> Path:
    """Resolve and check the run's JUnit report path.

    Returns:
        The resolved report path under the repository's report folder.

    Raises:
        ValueError: The report is not a regular XML file under the report folder, or the run is not JUnit.

    """
    report: Path = Path(_str(run, "reportPath"))
    if not report.is_absolute():
        report = root / report
    report = report.resolve()
    if (
        not report.is_relative_to(root / ".agent-workforce" / "reports")
        or report.suffix != ".xml"
        or (report.exists() and not report.is_file())
    ):
        message: str = "JUnit report must be a regular XML file under .agent-workforce/reports"
        raise ValueError(message)
    if run["format"] != "junit":
        message = "Unsupported test report format; configure a JUnit reporter"
        raise ValueError(message)
    return report


def _tree_digest(root: Path) -> str:
    """Hash the repository tree as tested.

    Returns:
        The tree digest gitutils reports.

    """
    return cmd_hash_files(argparse.Namespace(tree=str(root), files=[]))["treeDigest"]


def execute(plan: JsonObject, folder: Path) -> tuple[list[str], list[JsonValue]]:
    """Run mapped suites; exit zero alone never establishes per-test coverage.

    Returns:
        The execution errors and the per-run evidence records.

    """
    deadline: float = time.monotonic() + EXECUTION_BUDGET_SECONDS
    evidence: list[JsonValue] = []
    errors: list[str] = []
    mappings: list[JsonObject] = _objs(plan, "mappings")
    impacted: set[str] = {_str(r, "id") for r in _objs(plan, "requirements") if _flag(r, "impacted")}
    needed: set[str] = {_str(m, "runId") for m in mappings if _str(m, "requirementId") in impacted}
    for index, run in enumerate(_objs(plan, "runs")):
        if _str(run, "id") not in needed:
            continue
        run_errors, record = _execute_run(run, index, folder, deadline, mappings)
        errors.extend(run_errors)
        evidence.append(record)
    return errors, evidence


def _execute_run(
    run: JsonObject,
    index: int,
    folder: Path,
    deadline: float,
    mappings: list[JsonObject],
) -> tuple[list[str], JsonObject]:
    """Run one mapped suite and archive its output and JUnit report.

    Returns:
        The run's errors and its evidence record.

    Raises:
        ValueError: The report path or format is invalid, or the time budget is exhausted.

    """
    errors: list[str] = []
    run_id: str = _str(run, "id")
    root: Path = Path(_str(run, "repoPath")).resolve()
    report: Path = _report_path(run, root)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    remaining: int = int(deadline - time.monotonic())
    if remaining <= 0:
        message: str = "Regression execution time budget exhausted; evidence retained"
        raise ValueError(message)
    revision: str = _tree_digest(root)
    result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - The reviewed plan's suite command runs by design.
        ["/bin/sh", "-c", _str(run, "command")],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=remaining,
        check=False,
    )
    output: Path = folder / f"run-{index}.json"
    write(output, {"run": run, "exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
    passed: set[str] = set()
    if result.returncode != 0 or not report.is_file():
        errors.append(f"{run_id}: failed command or missing fresh JUnit report")
    else:
        passed, report_errors = junit_results(report, run_id)
        errors.extend(report_errors)
        expected: set[str] = {test for m in mappings if _str(m, "runId") == run_id for test in _strs(m, "testIds")}
        errors.extend(f"{run_id}: mapped test not executed successfully: {test}" for test in expected - passed)
    archived_report: Path = folder / f"run-{index}.xml"
    if report.is_file():
        archived_report.write_bytes(report.read_bytes())
        report.unlink()
    passed_ids: list[JsonValue] = [*sorted(passed)]
    record: JsonObject = {
        "runId": run_id,
        "output": str(output),
        "testedTreeDigest": revision,
        "report": str(archived_report),
        "reportSha256": hashlib.sha256(archived_report.read_bytes()).hexdigest() if archived_report.is_file() else "",
        "passedTestIds": passed_ids,
    }
    return errors, record


def _optional_arg(value: object, name: str) -> str | None:
    """Narrow an optional string command-line value.

    Returns:
        The value, or None when it was not given.

    Raises:
        TypeError: The value is neither a string nor None.

    """
    if value is None or isinstance(value, str):
        return value
    message: str = f"--{name}: expected a string"
    raise TypeError(message)


def _parse_args() -> CliArgs:
    """Parse and narrow the command line.

    Returns:
        The validated command line.

    Raises:
        TypeError: argparse produced a value outside the declared types.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(__doc__)
    parser.add_argument("mode", choices=list(MODES))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--review")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--approved-plan")
    parser.add_argument("--output", required=True)
    args: argparse.Namespace = parser.parse_args()
    mode: object = args.mode
    plan: str | None = _optional_arg(args.plan, "plan")
    ledger: str | None = _optional_arg(args.ledger, "ledger")
    output: str | None = _optional_arg(args.output, "output")
    source: object = args.source
    if plan is None or ledger is None or output is None:
        message: str = "--plan, --ledger and --output are required"
        raise TypeError(message)
    if not isinstance(source, list) or not all(isinstance(s, str) for s in source):
        message = "--source: expected strings"
        raise TypeError(message)
    sources: list[str] = [s for s in source if isinstance(s, str)]
    resolved: Mode | None = MODES.get(mode) if isinstance(mode, str) else None
    if resolved is not None:
        return CliArgs(
            mode=resolved,
            plan=plan,
            ledger=ledger,
            review=_optional_arg(args.review, "review"),
            source=sources,
            approved_plan=_optional_arg(args.approved_plan, "approved-plan"),
            output=output,
        )
    message = f"unsupported mode: {mode}"
    raise TypeError(message)


def _emit(value: JsonValue) -> None:
    """Write one JSON line to standard output."""
    sys.stdout.write(json.dumps(value) + "\n")


def main() -> None:
    """Prepare, validate or verify a cumulative regression plan and report the result as JSON."""
    args: CliArgs = _parse_args()
    previous: JsonObject | None = read(args.ledger) if Path(args.ledger).is_file() else None
    if args.mode == "prepare":
        write(args.output, previous or {"requirements": [], "mappings": [], "runs": []})
        plan_path: str = args.approved_plan or args.plan
        saved: JsonObject | None = read(plan_path) if Path(plan_path).is_file() else None
        hashes: dict[str, str] = source_hashes(
            sorted(set(args.source + _optional_strs(saved, "sourceFiles") + _optional_strs(previous, "sourceFiles"))),
        )
        _emit(
            {
                "ok": True,
                "path": args.output,
                "sourceRevision": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            },
        )
        return
    plan: JsonObject = read(args.plan)
    errors: list[str] = validate(plan, previous, complete=args.mode == "verify")
    review: JsonObject = read(args.review) if args.review else {}
    if review.get("approved") is not True or review.get("findings") or not review.get("evidence"):
        errors.append("Independent source/coverage/supersession review is not approved")
    if args.approved_plan and scope(plan) != scope(read(args.approved_plan)):
        errors.append("Final mapping changed the approved impact scope")
    bindings: Path = Path(args.output).parent / "source-bindings.json"
    source_bytes: dict[str, str] = source_hashes(_strs(plan, "sourceFiles"))
    bound: JsonObject = {**source_bytes}
    if args.mode == "verify" and (not bindings.is_file() or read(bindings) != bound):
        errors.append("Requirement source bytes changed since scope approval; reassess scope before building")
    if args.mode == "validate" and not errors:
        write(bindings, bound)
    evidence: list[JsonValue] = []
    if not errors and args.mode == "verify":
        errors, evidence = execute(plan, Path(args.output).parent)
    error_values: list[JsonValue] = [*errors]
    write(args.output, {"ok": not errors, "errors": error_values, "evidence": evidence})
    if not errors and args.mode == "verify":
        write(args.ledger, {**plan, "execution": evidence})
    required_kinds: list[JsonValue] = [
        *sorted(
            {
                _str(a, "kind")
                for r in _objs(plan, "requirements")
                if _flag(r, "impacted")
                for a in _objs(r, "applicability")
                if _flag(a, "required")
            },
        ),
    ]
    _emit(
        {
            "ok": not errors,
            "errors": error_values,
            "path": args.output,
            "ledger": args.ledger,
            "requiredKinds": required_kinds,
        },
    )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        TypeError,
        OSError,
        KeyError,
        ET.ParseError,
        subprocess.TimeoutExpired,
    ) as error:
        _emit({"ok": False, "errors": [str(error)]})
        raise SystemExit(1) from error
