"""Validate cumulative requirement coverage and confirm fresh JUnit execution evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

KINDS = {"unit", "contract", "integration", "nonfunctional"}


def read(path):
    """Read an authoritative artifact, including publication receipts when present."""
    from jsonartifact import read_artifact

    return read_artifact(Path(path))


def write(path, value):
    """Publish deterministic state atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def source_hashes(paths):
    """Bind the actual source bytes, independent of model-authored evidence prose."""
    result = {}
    for value in paths:
        path = Path(value)
        if not path.is_absolute() or not path.is_file():
            raise ValueError(
                f"Requirement source is not an absolute readable file: {value}"
            )
        result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def scope(plan):
    """Only mapping and execution configuration may change after scope approval."""
    return {
        k: plan[k] for k in ("components", "discovery", "requirements", "sourceFiles")
    }


def validate(plan, previous=None, complete=False):
    """Reject incomplete discovery, missing old obligations, and unmapped layers."""
    errors = []
    discovery = plan["discovery"]
    if (
        not discovery["priorRequirementsSearched"]
        or not discovery["sourceRefs"]
        or not discovery["evidence"].strip()
    ):
        errors.append(
            "Prior product requirements and affected dependencies were not evidenced"
        )
    if not plan["sourceFiles"]:
        errors.append("Requirement discovery has no physical source files")
    requirements = plan["requirements"]
    if not any(
        r["impacted"] and any(a["required"] for a in r["applicability"])
        for r in requirements
    ):
        errors.append("Build has no impacted requirement with required test coverage")
    ids = [r["id"] for r in requirements]
    if not ids or len(ids) != len(set(ids)):
        errors.append("Requirement IDs must be nonempty, source-qualified and unique")
    component_ids = {c["id"] for c in plan["components"]}
    for r in requirements:
        if (
            not r["sourceRef"].strip()
            or not r["componentIds"]
            or not set(r["componentIds"]) <= component_ids
        ):
            errors.append(f"{r['id']}: missing source or component binding")
        layers = r["applicability"]
        if {a["kind"] for a in layers} != KINDS or len(layers) != len(KINDS):
            errors.append(
                f"{r['id']}: every test layer needs an applicability disposition"
            )
        if any(not a["reason"].strip() or not a["sourceRefs"] for a in layers):
            errors.append(f"{r['id']}: applicability lacks source evidence")
    old = {r["id"]: r for r in (previous or {}).get("requirements", [])}
    superseded = {
        s["id"]
        for r in requirements
        for s in r["supersedes"]
        if s["sourceRef"].strip() and s["reason"].strip()
    }
    for missing in old.keys() - set(ids) - superseded:
        errors.append(
            f"{missing}: prior requirement dropped without explicit supersession"
        )
    if old and discovery["greenfield"]:
        errors.append(
            "Existing cumulative requirements contradict greenfield declaration"
        )
    if complete:
        runs = {r["id"]: r for r in plan["runs"]}
        if len(runs) != len(plan["runs"]):
            errors.append("Duplicate run IDs")
        for req in requirements:
            if not req["impacted"]:
                continue
            for layer in req["applicability"]:
                if not layer["required"]:
                    continue
                mappings = [
                    m
                    for m in plan["mappings"]
                    if m["requirementId"] == req["id"] and m["kind"] == layer["kind"]
                ]
                if not mappings or any(not m["testIds"] for m in mappings):
                    errors.append(f"{req['id']}/{layer['kind']}: no concrete tests")
                for m in mappings:
                    run = runs.get(m["runId"])
                    if not run or run["repoPath"] != req["repoPath"]:
                        errors.append(
                            f"{req['id']}: mapping has no matching repository execution"
                        )
        for m in plan["mappings"]:
            if m["requirementId"] not in ids or m["runId"] not in runs:
                errors.append("Mapping references unknown requirement/run")
        for mapping in (previous or {}).get("mappings", []):
            if mapping["requirementId"] in superseded:
                continue
            retained = {
                test
                for m in plan["mappings"]
                if m["requirementId"] == mapping["requirementId"]
                and m["kind"] == mapping["kind"]
                for test in m["testIds"]
            }
            replaced = {
                replacement["oldTestId"]
                for replacement in plan.get("replacements", [])
                if replacement["requirementId"] == mapping["requirementId"]
                and replacement["kind"] == mapping["kind"]
                and replacement["reason"].strip()
                and replacement["newTestIds"]
                and set(replacement["newTestIds"]) <= retained
            }
            if not set(mapping["testIds"]) <= retained | replaced:
                errors.append(
                    f"{mapping['requirementId']}: prior test mapping removed without explicit supersession"
                )
        for req_id in old.keys() & set(ids):
            now = next(r for r in requirements if r["id"] == req_id)
            authorized = req_id in superseded
            for layer in old[req_id]["applicability"]:
                if (
                    layer["required"]
                    and not any(
                        a["kind"] == layer["kind"] and a["required"]
                        for a in now["applicability"]
                    )
                    and not authorized
                ):
                    errors.append(
                        f"{req_id}: previously required layer removed without supersession"
                    )
    return errors


def junit_results(report, run_id):
    """Parse only executed passing cases; collection errors and duplicates fail closed."""
    tree = ET.parse(report)
    passed, all_ids, errors = set(), set(), []
    if tree.getroot().tag not in {"testsuites", "testsuite"}:
        errors.append(f"{run_id}: unsupported JUnit root")
    if any(
        case.find(tag) is not None
        for case in tree.iter("testcase")
        for tag in ("failure", "error")
    ):
        errors.append(
            f"{run_id}: report contains failed/error tests despite command exit zero"
        )
    for suite in (
        node for node in tree.iter() if node.tag in {"testsuite", "testsuites"}
    ):
        if (
            any(float(suite.get(key, "0")) != 0 for key in ("errors", "failures"))
            or suite.find("error") is not None
        ):
            errors.append(f"{run_id}: suite reports failures or errors")
    for case in tree.iter("testcase"):
        test_id = f"{case.get('classname', '')}::{case.get('name', '')}"
        if test_id in all_ids:
            errors.append(f"{run_id}: ambiguous duplicate test ID {test_id}")
        all_ids.add(test_id)
        executed = case.get("status", "run").lower() in {
            "run",
            "passed",
            "success",
        } and case.get("result", "completed").lower() in {
            "completed",
            "passed",
            "success",
        }
        if executed and not any(
            case.find(tag) is not None for tag in ("failure", "error", "skipped")
        ):
            passed.add(test_id)
    return passed, errors


def execute(plan, folder):
    """Run mapped suites; exit zero alone never establishes per-test coverage."""
    deadline = time.monotonic() + 500
    evidence = []
    errors = []
    impacted = {r["id"] for r in plan["requirements"] if r["impacted"]}
    needed = {m["runId"] for m in plan["mappings"] if m["requirementId"] in impacted}
    for index, run in enumerate(plan["runs"]):
        if run["id"] not in needed:
            continue
        root = Path(run["repoPath"]).resolve()
        report = Path(run["reportPath"])
        if not report.is_absolute():
            report = root / report
        report = report.resolve()
        if (
            not report.is_relative_to(root / ".agent-workforce" / "reports")
            or report.suffix != ".xml"
            or (report.exists() and not report.is_file())
        ):
            raise ValueError(
                "JUnit report must be a regular XML file under .agent-workforce/reports"
            )
        if run["format"] != "junit":
            raise ValueError(
                "Unsupported test report format; configure a JUnit reporter"
            )
        report.parent.mkdir(parents=True, exist_ok=True)
        report.unlink(missing_ok=True)
        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            raise ValueError(
                "Regression execution time budget exhausted; evidence retained"
            )
        from gitfacts import cmd_hash_files

        revision = cmd_hash_files(argparse.Namespace(tree=str(root), files=[]))[
            "treeDigest"
        ]
        result = subprocess.run(
            ["/bin/sh", "-c", run["command"]],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=remaining,
            check=False,
        )
        output = Path(folder) / f"run-{index}.json"
        write(
            output,
            {
                "run": run,
                "exitCode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )
        passed = set()
        if result.returncode != 0 or not report.is_file():
            errors.append(f"{run['id']}: failed command or missing fresh JUnit report")
        else:
            passed, report_errors = junit_results(report, run["id"])
            errors.extend(report_errors)
            expected = {
                test
                for m in plan["mappings"]
                if m["runId"] == run["id"]
                for test in m["testIds"]
            }
            for missing in expected - passed:
                errors.append(
                    f"{run['id']}: mapped test not executed successfully: {missing}"
                )
        archived_report = Path(folder) / f"run-{index}.xml"
        if report.is_file():
            archived_report.write_bytes(report.read_bytes())
            report.unlink()
        evidence.append(
            {
                "runId": run["id"],
                "output": str(output),
                "testedTreeDigest": revision,
                "report": str(archived_report),
                "reportSha256": hashlib.sha256(archived_report.read_bytes()).hexdigest()
                if archived_report.is_file()
                else "",
                "passedTestIds": sorted(passed),
            }
        )
    return errors, evidence


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("mode", choices=["prepare", "validate", "verify"])
    parser.add_argument("--plan", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--review")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--approved-plan")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    previous = read(args.ledger) if Path(args.ledger).is_file() else None
    if args.mode == "prepare":
        write(args.output, previous or {"requirements": [], "mappings": [], "runs": []})
        saved = (
            read(args.approved_plan or args.plan)
            if Path(args.approved_plan or args.plan).is_file()
            else {}
        )
        hashes = source_hashes(
            sorted(
                set(
                    args.source
                    + saved.get("sourceFiles", [])
                    + (previous or {}).get("sourceFiles", [])
                )
            )
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "path": args.output,
                    "sourceRevision": hashlib.sha256(
                        json.dumps(hashes, sort_keys=True).encode()
                    ).hexdigest(),
                }
            )
        )
        return
    plan = read(args.plan)
    errors = validate(plan, previous, complete=args.mode == "verify")
    review = read(args.review) if args.review else {}
    if (
        review.get("approved") is not True
        or review.get("findings")
        or not review.get("evidence")
    ):
        errors.append("Independent source/coverage/supersession review is not approved")
    if args.approved_plan and scope(plan) != scope(read(args.approved_plan)):
        errors.append("Final mapping changed the approved impact scope")
    bindings = Path(args.output).parent / "source-bindings.json"
    hashes = source_hashes(plan["sourceFiles"])
    if args.mode == "verify" and (not bindings.is_file() or read(bindings) != hashes):
        errors.append(
            "Requirement source bytes changed since scope approval; reassess scope before building"
        )
    if args.mode == "validate" and not errors:
        write(bindings, hashes)
    evidence = []
    if not errors and args.mode == "verify":
        errors, evidence = execute(plan, Path(args.output).parent)
    result = {"ok": not errors, "errors": errors, "evidence": evidence}
    write(args.output, result)
    if not errors and args.mode == "verify":
        write(args.ledger, {**plan, "execution": evidence})
    print(
        json.dumps(
            {
                "ok": not errors,
                "errors": errors,
                "path": args.output,
                "ledger": args.ledger,
                "requiredKinds": sorted(
                    {
                        a["kind"]
                        for r in plan["requirements"]
                        if r["impacted"]
                        for a in r["applicability"]
                        if a["required"]
                    }
                ),
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        OSError,
        KeyError,
        ET.ParseError,
        subprocess.TimeoutExpired,
    ) as error:
        print(json.dumps({"ok": False, "errors": [str(error)]}))
        raise SystemExit(1) from error
