#!/usr/bin/env python3
"""Generate a Markdown test execution report from QA run results."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("/tmp/qa_last_run.json")


def load_results(input_path: Path) -> dict[str, Any]:
    """Load QA results from a JSON file.

    Raises SystemExit with a clear message if the file is missing or invalid.
    """
    if not input_path.exists():
        print(
            f"ERROR: Input file not found: {input_path}\n"
            "Run 'python3 run_tests.py --all' first to generate results.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return json.loads(input_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: Cannot parse input file {input_path}: {exc}", file=sys.stderr)
        sys.exit(1)


def result_icon(result: str) -> str:
    """Return a markdown-friendly result indicator."""
    return {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN"}.get(result, result)


def generate_report(data: dict[str, Any]) -> str:
    """Generate a Markdown report from QA run data."""
    run_date = data.get("date", "unknown")
    summary = data.get("summary", {})
    lines: list[str] = []

    # Header
    lines.append(f"# QA Test Report — {run_date}")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Total | Pass | Fail | Warn |")
    lines.append("|-------|------|------|------|")
    lines.append(
        f"| {summary.get('total', 0)} "
        f"| {summary.get('pass', 0)} "
        f"| {summary.get('fail', 0)} "
        f"| {summary.get('warn', 0)} |"
    )
    lines.append("")

    # Failures section
    all_components: list[dict[str, Any]] = (
        data.get("plugins", [])
        + data.get("skills", [])
        + data.get("commands", [])
    )
    marketplace = data.get("marketplace")
    if marketplace:
        all_components = all_components + [marketplace]

    failures = [c for c in all_components if c.get("failures", 0) > 0]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for comp in failures:
            name = comp.get("_display_name") or comp.get("plugin") or comp.get("skill") or comp.get("file", "unknown")
            lines.append(f"### {name}")
            lines.append("")
            for check in comp.get("checks", []):
                if check["status"] == "FAIL" and check["level"] == "REQUIRED":
                    lines.append(f"- **{check['id']}**: {check['message']}")
            # Nested command failures
            for cmd in comp.get("commands", []):
                if cmd.get("failures", 0) > 0:
                    cmd_name = Path(cmd.get("file", "?")).name
                    lines.append(f"- **{cmd_name}**:")
                    for check in cmd.get("checks", []):
                        if check["status"] == "FAIL" and check["level"] == "REQUIRED":
                            lines.append(f"  - {check['id']}: {check['message']}")
            lines.append("")

    # Warnings section
    warnings = [c for c in all_components if c.get("warnings", 0) > 0 and c.get("failures", 0) == 0]
    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for comp in warnings:
            name = comp.get("_display_name") or comp.get("plugin") or comp.get("skill") or comp.get("file", "unknown")
            lines.append(f"### {name}")
            lines.append("")
            for check in comp.get("checks", []):
                if check["status"] == "FAIL" and check["level"] != "REQUIRED":
                    lines.append(f"- **{check['id']}**: {check['message']}")
            lines.append("")

    # Full results table
    lines.append("## Full Results")
    lines.append("")
    lines.append("| Component | Type | Result | Notes |")
    lines.append("|-----------|------|--------|-------|")

    for comp in data.get("plugins", []):
        name = comp.get("_display_name", comp.get("plugin", "?"))
        r = comp.get("result", "?")
        notes = _build_notes(comp)
        lines.append(f"| {name} | plugin | {result_icon(r)} | {notes} |")

    for comp in data.get("skills", []):
        name = comp.get("_display_name", comp.get("skill", "?"))
        r = comp.get("result", "?")
        notes = _build_notes(comp)
        lines.append(f"| {name} | skill | {result_icon(r)} | {notes} |")

    for comp in data.get("commands", []):
        name = comp.get("_display_name", comp.get("file", "?"))
        r = comp.get("result", "?")
        notes = _build_notes(comp)
        lines.append(f"| {name} | command | {result_icon(r)} | {notes} |")

    if marketplace:
        r = marketplace.get("result", "?")
        notes = _build_notes(marketplace)
        lines.append(f"| marketplace.json | marketplace | {result_icon(r)} | {notes} |")

    lines.append("")
    return "\n".join(lines)


def _build_notes(comp: dict[str, Any]) -> str:
    """Build a short notes string for the results table."""
    parts = []
    f = comp.get("failures", 0)
    w = comp.get("warnings", 0)
    if f:
        parts.append(f"{f} failure(s)")
    if w:
        parts.append(f"{w} warning(s)")
    if "error" in comp:
        parts.append(comp["error"])
    return "; ".join(parts) if parts else "—"


def main() -> None:
    """Entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Generate a Markdown QA test execution report"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help=f"Input JSON file (default: {DEFAULT_INPUT})")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output Markdown file (default: stdout)")
    args = parser.parse_args()

    data = load_results(args.input)
    report = generate_report(data)

    if args.out:
        try:
            args.out.write_text(report, encoding="utf-8")
            print(f"Report written to: {args.out}")
        except OSError as exc:
            print(f"ERROR: Cannot write output file {args.out}: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(report)


if __name__ == "__main__":
    main()
