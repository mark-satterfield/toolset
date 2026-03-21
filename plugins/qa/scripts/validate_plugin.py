#!/usr/bin/env python3
"""Validate a Claude Code plugin directory for structural correctness."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
PROHIBITED_PATTERNS = [
    re.compile(r".*\.html$"),
    re.compile(r".*\.log$"),
    re.compile(r".*\.txt$"),
    re.compile(r"tmp.*"),
    re.compile(r"debug.*"),
    re.compile(r"BUILD_STATUS.*"),
]


def make_check(
    check_id: str,
    level: str,
    status: str,
    message: str,
) -> dict[str, str]:
    """Construct a check result dict."""
    return {"id": check_id, "level": level, "status": status, "message": message}


def validate_plugin(plugin_dir: Path) -> dict[str, Any]:
    """Validate a plugin directory.

    Returns a result dict with keys: plugin, result, checks, warnings, failures, commands.
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

    plugin_name = plugin_dir.name
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"

    # Check 1: .claude-plugin/plugin.json exists
    if not manifest_path.exists():
        add("manifest_exists", "REQUIRED", "FAIL",
            f".claude-plugin/plugin.json does not exist at {manifest_path}")
    else:
        add("manifest_exists", "REQUIRED", "PASS", ".claude-plugin/plugin.json exists")

    # Check 2: manifest is valid JSON
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            add("manifest_json", "REQUIRED", "PASS", "plugin.json is valid JSON")
        except (json.JSONDecodeError, OSError) as exc:
            add("manifest_json", "REQUIRED", "FAIL", f"plugin.json is invalid JSON: {exc}")

    # Check 3: required fields
    if manifest:
        missing = [f for f in ("name", "version", "description") if f not in manifest]
        if missing:
            add("manifest_fields", "REQUIRED", "FAIL",
                f"Missing required fields: {', '.join(missing)}")
        else:
            add("manifest_fields", "REQUIRED", "PASS",
                "Required fields present (name, version, description)")

    # Check 4: version matches semver
    if manifest and "version" in manifest:
        version = str(manifest.get("version", ""))
        if not SEMVER_RE.match(version):
            add("semver", "REQUIRED", "FAIL",
                f"version '{version}' does not match semver (X.Y.Z)")
        else:
            add("semver", "REQUIRED", "PASS", f"Version follows semver ({version})")

    # Check 5: commands/ directory exists
    commands_dir = plugin_dir / "commands"
    if not commands_dir.exists() or not commands_dir.is_dir():
        add("commands_dir", "REQUIRED", "FAIL", "commands/ directory does not exist")
    else:
        add("commands_dir", "REQUIRED", "PASS", "commands/ directory exists")

    # Check 6: commands/ contains at least one .md file
    command_files: list[Path] = []
    if commands_dir.exists():
        command_files = list(commands_dir.glob("*.md"))
        if not command_files:
            add("commands_not_empty", "REQUIRED", "FAIL",
                "commands/ directory contains no .md files")
        else:
            add("commands_not_empty", "REQUIRED", "PASS",
                f"commands/ contains {len(command_files)} command file(s)")

    # Check 7: plugin.json at root — BEST_PRACTICE
    root_plugin_json = plugin_dir / "plugin.json"
    if not root_plugin_json.exists():
        add("root_plugin_json", "BEST_PRACTICE", "FAIL",
            "plugin.json does not exist at plugin root (recommended)")
    else:
        add("root_plugin_json", "BEST_PRACTICE", "PASS",
            "plugin.json exists at plugin root")

    # Check 8: root plugin.json has author, license, keywords — BEST_PRACTICE
    if root_plugin_json.exists():
        try:
            root_manifest = json.loads(root_plugin_json.read_text(encoding="utf-8"))
            missing_bp = [
                f for f in ("author", "license", "keywords")
                if f not in root_manifest
            ]
            if missing_bp:
                add("root_plugin_json_fields", "BEST_PRACTICE", "FAIL",
                    f"plugin.json missing recommended fields: {', '.join(missing_bp)}")
            else:
                add("root_plugin_json_fields", "BEST_PRACTICE", "PASS",
                    "plugin.json has recommended fields (author, license, keywords)")
        except (json.JSONDecodeError, OSError) as exc:
            add("root_plugin_json_fields", "BEST_PRACTICE", "FAIL",
                f"Cannot parse root plugin.json: {exc}")

    # Check 9: package.json exists — BEST_PRACTICE
    package_json = plugin_dir / "package.json"
    if not package_json.exists():
        add("package_json", "BEST_PRACTICE", "FAIL",
            "package.json does not exist (recommended)")
    else:
        add("package_json", "BEST_PRACTICE", "PASS", "package.json exists")

    # Check 10: package.json name matches @mark-satterfield/plugin-<dir-name> — BEST_PRACTICE
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text(encoding="utf-8"))
            expected_name = f"@mark-satterfield/plugin-{plugin_name}"
            actual_name = pkg.get("name", "")
            if actual_name != expected_name:
                add("package_json_name", "BEST_PRACTICE", "FAIL",
                    f"package.json name '{actual_name}' should be '{expected_name}'")
            else:
                add("package_json_name", "BEST_PRACTICE", "PASS",
                    f"package.json name matches expected ({expected_name})")
        except (json.JSONDecodeError, OSError) as exc:
            add("package_json_name", "BEST_PRACTICE", "FAIL",
                f"Cannot parse package.json: {exc}")

    # Check 11: no prohibited root files
    prohibited_found: list[str] = []
    if plugin_dir.exists():
        for item in plugin_dir.iterdir():
            if item.is_file():
                for pat in PROHIBITED_PATTERNS:
                    if pat.match(item.name):
                        prohibited_found.append(item.name)
                        break
    if prohibited_found:
        add("no_prohibited_files", "REQUIRED", "FAIL",
            f"Prohibited files found: {', '.join(prohibited_found)}")
    else:
        add("no_prohibited_files", "REQUIRED", "PASS", "No prohibited root files found")

    # Validate each command file
    command_results: list[dict[str, Any]] = []
    validate_cmd_script = Path(__file__).parent / "validate_command.py"

    for cmd_file in sorted(command_files):
        try:
            proc = subprocess.run(
                [sys.executable, str(validate_cmd_script), str(cmd_file), "--json"],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
            )
            if proc.stdout.strip():
                cmd_result = json.loads(proc.stdout)
            else:
                cmd_result = {
                    "file": str(cmd_file),
                    "result": "FAIL",
                    "checks": [],
                    "warnings": 0,
                    "failures": 1,
                    "error": proc.stderr.strip() or "No output from validator",
                }
        except subprocess.TimeoutExpired:
            cmd_result = {
                "file": str(cmd_file),
                "result": "FAIL",
                "checks": [],
                "warnings": 0,
                "failures": 1,
                "error": "Validator timed out",
            }
        except (OSError, json.JSONDecodeError) as exc:
            cmd_result = {
                "file": str(cmd_file),
                "result": "FAIL",
                "checks": [],
                "warnings": 0,
                "failures": 1,
                "error": str(exc),
            }
        command_results.append(cmd_result)
        if cmd_result.get("failures", 0) > 0:
            failures += 1
        if cmd_result.get("warnings", 0) > 0:
            warnings += 1

    result = "FAIL" if failures > 0 else ("WARN" if warnings > 0 else "PASS")
    return {
        "plugin": plugin_name,
        "result": result,
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
        "commands": command_results,
    }


def format_human(result: dict[str, Any]) -> str:
    """Format validation result as human-readable text."""
    lines = [f"Plugin: {result['plugin']}", "─" * 45]
    for check in result["checks"]:
        if check["status"] == "PASS":
            icon = "✓"
        elif check["level"] == "REQUIRED":
            icon = "✗"
        else:
            icon = "⚠"
        lines.append(f"{icon} {check['message']}")

    # Command results
    for cmd in result.get("commands", []):
        cmd_name = Path(cmd["file"]).name
        if cmd["result"] == "PASS":
            icon = "  ✓"
        elif cmd.get("failures", 0) > 0:
            icon = "  ✗"
        else:
            icon = "  ⚠"
        suffix = ""
        if cmd.get("failures", 0):
            suffix += f" — {cmd['failures']} failure(s)"
        if cmd.get("warnings", 0):
            suffix += f" — {cmd['warnings']} warning(s)"
        lines.append(f"{icon} {cmd_name}{suffix}")
        if "error" in cmd:
            lines.append(f"      Error: {cmd['error']}")

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
        description="Validate a Claude Code plugin directory"
    )
    parser.add_argument("plugin_dir", type=Path, help="Path to the plugin directory")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of human-readable text")
    args = parser.parse_args()

    result = validate_plugin(args.plugin_dir)

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
