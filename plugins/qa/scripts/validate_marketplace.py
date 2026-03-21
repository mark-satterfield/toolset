#!/usr/bin/env python3
"""Validate a Claude Code marketplace.json registration file."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def make_check(
    check_id: str,
    level: str,
    status: str,
    message: str,
) -> dict[str, str]:
    """Construct a check result dict."""
    return {"id": check_id, "level": level, "status": status, "message": message}


def validate_marketplace(marketplace_path: Path) -> dict[str, Any]:
    """Validate a marketplace.json file.

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

    # Check 1: file exists
    if not marketplace_path.exists():
        add("file_exists", "REQUIRED", "FAIL",
            f"marketplace.json does not exist: {marketplace_path}")
        return {
            "file": str(marketplace_path),
            "result": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }
    add("file_exists", "REQUIRED", "PASS", "marketplace.json exists")

    # Check 2: valid JSON
    try:
        data = json.loads(marketplace_path.read_text(encoding="utf-8"))
        add("valid_json", "REQUIRED", "PASS", "marketplace.json is valid JSON")
    except (json.JSONDecodeError, OSError) as exc:
        add("valid_json", "REQUIRED", "FAIL", f"marketplace.json is invalid JSON: {exc}")
        return {
            "file": str(marketplace_path),
            "result": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }

    # Check 3: top-level has plugins array
    if not isinstance(data.get("plugins"), list):
        add("plugins_array", "REQUIRED", "FAIL",
            "Top-level 'plugins' array is missing or not an array")
        return {
            "file": str(marketplace_path),
            "result": "FAIL",
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
        }
    add("plugins_array", "REQUIRED", "PASS",
        f"'plugins' array present ({len(data['plugins'])} entries)")

    # If the marketplace.json lives inside a .claude-plugin/ directory,
    # source paths (e.g. "./plugins/qa") are relative to the repo root,
    # which is the parent of that directory.
    parent = marketplace_path.parent
    base_dir = parent.parent if parent.name == ".claude-plugin" else parent
    seen_names: set[str] = set()

    for idx, entry in enumerate(data["plugins"]):
        prefix = f"entry[{idx}]"
        entry_name = entry.get("name", f"<unnamed #{idx}>")

        # Check 4a: required fields per entry
        required_fields = ("name", "description", "version", "source")
        missing = [f for f in required_fields if f not in entry]
        if missing:
            add(f"{prefix}_fields", "REQUIRED", "FAIL",
                f"Entry '{entry_name}' missing required fields: {', '.join(missing)}")
        else:
            add(f"{prefix}_fields", "REQUIRED", "PASS",
                f"Entry '{entry_name}' has all required fields")

        # Check 4b: source path exists
        if "source" in entry:
            source_path = (base_dir / entry["source"]).resolve()
            if not source_path.exists() or not source_path.is_dir():
                add(f"{prefix}_source", "REQUIRED", "FAIL",
                    f"Entry '{entry_name}' source path does not exist: {source_path}")
            else:
                add(f"{prefix}_source", "REQUIRED", "PASS",
                    f"Entry '{entry_name}' source path exists")

        # Check 4c: no duplicate names
        name = entry.get("name", "")
        if name and name in seen_names:
            add(f"{prefix}_no_dup", "REQUIRED", "FAIL",
                f"Duplicate plugin name: '{name}'")
        elif name:
            add(f"{prefix}_no_dup", "REQUIRED", "PASS",
                f"Entry '{name}' name is unique")
            seen_names.add(name)

        # Check 4d: version matches plugin manifest — BEST_PRACTICE
        if "source" in entry and "version" in entry:
            source_path = (base_dir / entry["source"]).resolve()
            plugin_manifest = source_path / ".claude-plugin" / "plugin.json"
            if plugin_manifest.exists():
                try:
                    pm = json.loads(plugin_manifest.read_text(encoding="utf-8"))
                    manifest_version = pm.get("version", "")
                    entry_version = str(entry.get("version", ""))
                    if manifest_version and manifest_version != entry_version:
                        add(f"{prefix}_version_sync", "BEST_PRACTICE", "FAIL",
                            f"Entry '{entry_name}' version '{entry_version}' does not match "
                            f"plugin manifest version '{manifest_version}'")
                    else:
                        add(f"{prefix}_version_sync", "BEST_PRACTICE", "PASS",
                            f"Entry '{entry_name}' version matches plugin manifest")
                except (json.JSONDecodeError, OSError):
                    add(f"{prefix}_version_sync", "BEST_PRACTICE", "FAIL",
                        f"Cannot read plugin manifest for '{entry_name}' to verify version")

    result = "FAIL" if failures > 0 else ("WARN" if warnings > 0 else "PASS")
    return {
        "file": str(marketplace_path),
        "result": result,
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
    }


def format_human(result: dict[str, Any]) -> str:
    """Format validation result as human-readable text."""
    lines = [f"Marketplace: {Path(result['file']).name}", "─" * 45]
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
        description="Validate a Claude Code marketplace.json"
    )
    parser.add_argument("marketplace_json", type=Path,
                        help="Path to marketplace.json")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of human-readable text")
    args = parser.parse_args()

    result = validate_marketplace(args.marketplace_json)

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
