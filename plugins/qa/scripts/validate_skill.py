#!/usr/bin/env python3
"""Validate a Claude Code skill directory for structural correctness."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


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
        if is_block_scalar and (line.startswith(" ") or line.startswith("\t")):
            stripped = line.strip()
            if stripped:
                current_value_parts.append(stripped)
            continue

        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            flush_current()
            key, _, value = line.partition(":")
            current_key = key.strip()
            raw_value = value.strip()
            if raw_value in (">-", ">", "|-", "|", ""):
                is_block_scalar = raw_value in (">-", ">", "|-", "|", "")
                current_value_parts = []
            else:
                is_block_scalar = False
                current_value_parts = [raw_value]

    flush_current()
    return fields, body


def make_check(
    check_id: str,
    level: str,
    status: str,
    message: str,
) -> dict[str, str]:
    """Construct a check result dict."""
    return {"id": check_id, "level": level, "status": status, "message": message}


def validate_skill(skill_dir: Path) -> dict[str, Any]:
    """Validate a skill directory.

    Returns a result dict with keys: skill, result, checks, warnings, failures.
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

    skill_name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"

    # Check 1: SKILL.md exists
    if not skill_md.exists():
        add("skill_md_exists", "REQUIRED", "FAIL",
            f"SKILL.md does not exist in {skill_dir}")
        return {
            "skill": skill_name,
            "result": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }
    add("skill_md_exists", "REQUIRED", "PASS", "SKILL.md exists")

    # Check 2: SKILL.md is readable
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        add("skill_md_readable", "REQUIRED", "FAIL", f"Cannot read SKILL.md: {exc}")
        return {
            "skill": skill_name,
            "result": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }
    add("skill_md_readable", "REQUIRED", "PASS", "SKILL.md is readable")

    # Check 3: contains YAML frontmatter
    if not content.startswith("---"):
        add("has_frontmatter", "REQUIRED", "FAIL",
            "SKILL.md does not start with YAML frontmatter (---)")
        return {
            "skill": skill_name,
            "result": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }
    add("has_frontmatter", "REQUIRED", "PASS", "YAML frontmatter block present")

    # Parse frontmatter
    try:
        fields, body = parse_frontmatter(content)
    except ValueError as exc:
        add("frontmatter_valid", "REQUIRED", "FAIL", f"Frontmatter parse error: {exc}")
        return {
            "skill": skill_name,
            "result": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }

    # Check 4: name field present
    name_val = fields.get("name", "").strip()
    if not name_val:
        add("name_present", "REQUIRED", "FAIL", "Missing or empty 'name' field in frontmatter")
    else:
        add("name_present", "REQUIRED", "PASS", f"name field present ({name_val})")

    # Check 5: description present
    description = fields.get("description", "").strip()
    if not description:
        add("description_present", "REQUIRED", "FAIL",
            "Missing or empty 'description' field in frontmatter")
    else:
        add("description_present", "REQUIRED", "PASS", "description field present")

    # Check 6: description length >= 50
    if description:
        if len(description) < 50:
            add("description_length", "REQUIRED", "FAIL",
                f"description too short ({len(description)} chars, minimum 50 for trigger matching)")
        else:
            add("description_length", "REQUIRED", "PASS",
                f"description length OK ({len(description)} chars)")

    # Check 7: name matches directory name — BEST_PRACTICE
    if name_val:
        if name_val.lower() != skill_name.lower():
            add("name_matches_dir", "BEST_PRACTICE", "FAIL",
                f"name '{name_val}' does not match directory name '{skill_name}'")
        else:
            add("name_matches_dir", "BEST_PRACTICE", "PASS",
                f"name matches directory ({skill_name})")

    # Check 8: body non-empty >= 200 chars
    if len(body) < 200:
        add("body_content", "REQUIRED", "FAIL",
            f"Body too short ({len(body)} chars, minimum 200)")
    else:
        add("body_content", "REQUIRED", "PASS",
            f"Body has sufficient content ({len(body)} chars)")

    # Check 9: no inline version metadata
    if re.search(r"last\s+updated|last\s+modified", body, re.IGNORECASE):
        add("no_version_metadata", "REQUIRED", "FAIL",
            "Body contains prohibited inline version metadata ('Last updated' or 'Last modified')")
    else:
        add("no_version_metadata", "REQUIRED", "PASS",
            "No inline version metadata found")

    # Check 10: no mermaid fenced blocks
    if re.search(r"```mermaid", body):
        add("no_mermaid", "REQUIRED", "FAIL",
            "Body contains ```mermaid fenced block — use D2 format instead")
    else:
        add("no_mermaid", "REQUIRED", "PASS", "No mermaid blocks found")

    # Check 11: if scripts/ subdirectory exists, optionally run script_tester.py — BEST_PRACTICE
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists() and scripts_dir.is_dir():
        script_tester = (
            Path(__file__).parent.parent.parent.parent
            / "plugins"
            / "engineering"
            / "skill-tester"
            / "scripts"
            / "script_tester.py"
        )
        if not script_tester.exists():
            add("script_tester", "BEST_PRACTICE", "FAIL",
                f"scripts/ directory exists but script_tester.py not found at {script_tester}")
        else:
            py_files = list(scripts_dir.glob("*.py"))
            script_failures = 0
            for py_file in py_files:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script_tester), str(py_file)],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        encoding="utf-8",
                    )
                    if proc.returncode != 0:
                        script_failures += 1
                except (subprocess.TimeoutExpired, OSError):
                    script_failures += 1
            if script_failures > 0:
                add("script_tester", "BEST_PRACTICE", "FAIL",
                    f"script_tester reported failures for {script_failures} script(s)")
            else:
                add("script_tester", "BEST_PRACTICE", "PASS",
                    f"All {len(py_files)} script(s) passed script_tester checks")

    result = "FAIL" if failures > 0 else ("WARN" if warnings > 0 else "PASS")
    return {
        "skill": skill_name,
        "result": result,
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
    }


def format_human(result: dict[str, Any]) -> str:
    """Format validation result as human-readable text."""
    lines = [f"Skill: {result['skill']}", "─" * 45]
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
    suffix = f" ({', '.join(parts)})" if parts else ""
    lines.append(f"Result: {summary}{suffix}")
    return "\n".join(lines)


def main() -> None:
    """Entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Validate a Claude Code skill directory"
    )
    parser.add_argument("skill_dir", type=Path, help="Path to the skill directory")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of human-readable text")
    args = parser.parse_args()

    result = validate_skill(args.skill_dir)

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
