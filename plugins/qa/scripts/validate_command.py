#!/usr/bin/env python3
"""Validate a single Claude Code command .md file for structural correctness."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


VALID_TOOLS = {
    "Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task", "Agent",
    "WebFetch", "WebSearch", "NotebookRead", "NotebookEdit",
    "AskUserQuestion", "TodoWrite", "TodoRead",
    "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "TaskStop", "TaskOutput",
    "SendMessage", "TeamCreate", "TeamDelete",
    "EnterPlanMode", "ExitPlanMode", "EnterWorktree", "ExitWorktree",
    "LSP", "CronCreate", "CronDelete", "CronList", "Skill", "ToolSearch",
}


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body_text).
    frontmatter_dict keys are field names, values are raw strings.
    Handles YAML block scalars (>-, |, >, |-, etc.) by concatenating
    indented continuation lines into the field value.
    Raises ValueError if frontmatter block is malformed.
    """
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        raise ValueError("Unclosed frontmatter block")

    fm_text = content[3:end].strip()
    body = content[end + 4:].strip()

    fields: dict[str, str] = {}
    current_key: str | None = None
    current_value_parts: list[str] = []
    is_block_scalar = False

    def flush_current() -> None:
        """Save the accumulated value for the current key."""
        if current_key is not None:
            if is_block_scalar:
                fields[current_key] = " ".join(current_value_parts)
            else:
                fields[current_key] = current_value_parts[0] if current_value_parts else ""

    for line in fm_text.splitlines():
        # Continuation lines for block scalars start with whitespace
        if is_block_scalar and (line.startswith(" ") or line.startswith("\t")):
            stripped = line.strip()
            if stripped:
                current_value_parts.append(stripped)
            continue

        # Top-level key lines
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            flush_current()
            key, _, value = line.partition(":")
            current_key = key.strip()
            raw_value = value.strip()
            # Detect YAML block scalar indicators (>-, |-, >, |)
            if raw_value in (">-", ">", "|-", "|", ""):
                is_block_scalar = raw_value in (">-", ">", "|-", "|", "")
                current_value_parts = []
            else:
                is_block_scalar = False
                current_value_parts = [raw_value]

    flush_current()
    return fields, body


def parse_tools_list(value: str) -> list[str]:
    """Parse a YAML tools list in bracketed or bare comma-separated format.

    Handles both '[Read, Write, Bash]' and 'Read, Write, Bash'.
    """
    value = value.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [t.strip() for t in value.split(",") if t.strip()]


def is_valid_tool(tool: str) -> bool:
    """Return True if tool is in the valid tools set or matches mcp__* pattern."""
    return tool in VALID_TOOLS or tool.startswith("mcp__")


def make_check(
    check_id: str,
    level: str,
    status: str,
    message: str,
) -> dict[str, str]:
    """Construct a check result dict."""
    return {"id": check_id, "level": level, "status": status, "message": message}


def validate_command(file_path: Path) -> dict[str, Any]:
    """Validate a single command .md file.

    Returns a result dict with keys: file, result, checks, warnings, failures.
    """
    checks: list[dict[str, str]] = []
    failures = 0
    warnings = 0

    def add(check_id: str, level: str, status: str, message: str) -> None:
        nonlocal failures, warnings
        checks.append(make_check(check_id, level, status, message))
        if status == "FAIL":
            if level == "REQUIRED":
                failures += 1
            else:
                warnings += 1

    # Check 1: file exists and is readable
    if not file_path.exists() or not file_path.is_file():
        add("file_exists", "REQUIRED", "FAIL", f"File does not exist: {file_path}")
        result = "FAIL"
        return {
            "file": str(file_path),
            "result": result,
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        add("file_readable", "REQUIRED", "FAIL", f"Cannot read file: {exc}")
        return {
            "file": str(file_path),
            "result": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }

    add("file_exists", "REQUIRED", "PASS", "File exists and is readable")

    # Check 2: contains YAML frontmatter block
    if not content.startswith("---"):
        add("has_frontmatter", "REQUIRED", "FAIL", "File does not start with YAML frontmatter (---)")
        result = "FAIL"
        return {
            "file": str(file_path),
            "result": result,
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }
    add("has_frontmatter", "REQUIRED", "PASS", "YAML frontmatter block present")

    # Check 3: frontmatter is parseable
    try:
        fields, body = parse_frontmatter(content)
    except ValueError as exc:
        add("frontmatter_valid", "REQUIRED", "FAIL", f"Frontmatter parse error: {exc}")
        result = "FAIL"
        return {
            "file": str(file_path),
            "result": result,
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }
    add("frontmatter_valid", "REQUIRED", "PASS", "Frontmatter is valid")

    # Check 4: description present and non-empty
    description = fields.get("description", "").strip()
    if not description:
        add("description_present", "REQUIRED", "FAIL", "Missing or empty 'description' field")
    else:
        add("description_present", "REQUIRED", "PASS", "description field present")

    # Check 5: description length >= 20
    if description:
        if len(description) < 20:
            add("description_length", "REQUIRED", "FAIL",
                f"description too short ({len(description)} chars, minimum 20)")
        else:
            add("description_length", "REQUIRED", "PASS",
                f"description length OK ({len(description)} chars)")

    # Check 6: allowed-tools present
    tools_raw = fields.get("allowed-tools", "")
    if not tools_raw:
        add("allowed_tools_present", "REQUIRED", "FAIL", "Missing 'allowed-tools' field")
    else:
        add("allowed_tools_present", "REQUIRED", "PASS", "allowed-tools field present")

    # Check 7: allowed-tools contains only valid tools
    if tools_raw:
        tools = parse_tools_list(tools_raw)
        invalid = [t for t in tools if not is_valid_tool(t)]
        if invalid:
            add("allowed_tools_valid", "REQUIRED", "FAIL",
                f"Invalid tools: {', '.join(invalid)}")
        else:
            add("allowed_tools_valid", "REQUIRED", "PASS",
                f"All tools valid ({', '.join(tools)})")

    # Check 8: body non-empty (>= 100 chars) — BEST_PRACTICE
    if len(body) < 100:
        add("body_content", "BEST_PRACTICE", "FAIL",
            f"Body too short ({len(body)} chars, recommend >= 100)")
    else:
        add("body_content", "BEST_PRACTICE", "PASS",
            f"Body has sufficient content ({len(body)} chars)")

    # Check 9: if body uses $ARGUMENTS, argument-hint should be present — BEST_PRACTICE
    if "$ARGUMENTS" in body and not fields.get("argument-hint", "").strip():
        add("argument_hint", "BEST_PRACTICE", "FAIL",
            "Body uses $ARGUMENTS but 'argument-hint' frontmatter field is missing")
    else:
        add("argument_hint", "BEST_PRACTICE", "PASS",
            "argument-hint check OK")

    # Check 10: no inline version metadata
    if re.search(r"last\s+updated|last\s+modified", body, re.IGNORECASE):
        add("no_version_metadata", "REQUIRED", "FAIL",
            "Body contains prohibited inline version metadata ('Last updated' or 'Last modified')")
    else:
        add("no_version_metadata", "REQUIRED", "PASS",
            "No inline version metadata found")

    # Check 11: no mermaid fenced blocks
    if re.search(r"```mermaid", body):
        add("no_mermaid", "REQUIRED", "FAIL",
            "Body contains ```mermaid fenced block — use D2 format instead")
    else:
        add("no_mermaid", "REQUIRED", "PASS", "No mermaid blocks found")

    result = "FAIL" if failures > 0 else ("WARN" if warnings > 0 else "PASS")
    return {
        "file": str(file_path),
        "result": result,
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
    }


def format_human(result: dict[str, Any]) -> str:
    """Format validation result as human-readable text."""
    lines = [f"Command: {Path(result['file']).name}", "─" * 45]
    for check in result["checks"]:
        if check["status"] == "PASS":
            icon = "✓"
        elif check["level"] == "REQUIRED":
            icon = "✗"
        else:
            icon = "⚠"
        lines.append(f"{icon} {check['message']}")
    lines.append("─" * 45)
    summary = result["result"]
    w = result["warnings"]
    f = result["failures"]
    parts = []
    if f:
        parts.append(f"{f} failure(s)")
    if w:
        parts.append(f"{w} warning(s)")
    suffix = f"  ({', '.join(parts)})" if parts else ""
    lines.append(f"Result: {summary}{suffix}")
    return "\n".join(lines)


def main() -> None:
    """Entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Validate a Claude Code command .md file"
    )
    parser.add_argument("command_file", type=Path, help="Path to the command .md file")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable text")
    args = parser.parse_args()

    result = validate_command(args.command_file)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_human(result))

    if result["failures"] > 0:
        sys.exit(1)
    elif result["warnings"] > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
