#!/usr/bin/env python3
"""Master QA test runner for all plugins, skills, and marketplace registration."""

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).parent
DEFAULT_REPO_ROOT = SCRIPTS_DIR.parent.parent.parent
LAST_RUN_PATH = Path("/tmp/qa_last_run.json")


def run_validator(
    script: Path,
    target: Path,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    """Run a validator script against a target path and return parsed JSON result.

    Falls back to an error dict if the subprocess fails or produces invalid JSON.
    """
    cmd = [sys.executable, str(script), str(target), "--json"]
    if extra_args:
        cmd.extend(extra_args)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
        )
        if proc.stdout.strip():
            return json.loads(proc.stdout)
        return {
            "target": str(target),
            "result": "FAIL",
            "checks": [],
            "warnings": 0,
            "failures": 1,
            "error": proc.stderr.strip() or "No output from validator",
        }
    except subprocess.TimeoutExpired:
        return {
            "target": str(target),
            "result": "FAIL",
            "checks": [],
            "warnings": 0,
            "failures": 1,
            "error": "Validator timed out",
        }
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "target": str(target),
            "result": "FAIL",
            "checks": [],
            "warnings": 0,
            "failures": 1,
            "error": str(exc),
        }


def discover_plugins(repo_root: Path) -> list[Path]:
    """Return plugin directories that have a .claude-plugin/plugin.json manifest."""
    plugins_dir = repo_root / "plugins"
    if not plugins_dir.exists():
        return []
    return sorted(
        p for p in plugins_dir.iterdir()
        if p.is_dir()
        and not p.name.startswith(".")
        and (p / ".claude-plugin" / "plugin.json").exists()
    )


def discover_skills(repo_root: Path) -> list[Path]:
    """Return all skill directories under <repo_root>/skills/ that contain SKILL.md."""
    skills_dir = repo_root / "skills"
    if not skills_dir.exists():
        return []
    return sorted(
        p for p in skills_dir.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
    )


def format_result_row(name: str, result_dict: dict[str, Any]) -> str:
    """Format a single result row for human output."""
    r = result_dict.get("result", "FAIL")
    if r == "PASS":
        icon = "✓"
    elif result_dict.get("failures", 0) > 0:
        icon = "✗"
    else:
        icon = "⚠"

    notes = ""
    f = result_dict.get("failures", 0)
    w = result_dict.get("warnings", 0)
    if f:
        notes += f"  {f} failure(s)"
    if w:
        notes += f"  {w} warning(s)"
    if "error" in result_dict:
        notes += f"  — {result_dict['error']}"

    return f"  {icon} {name:<22} {r}{notes}"


def run_all(
    repo_root: Path,
    plugin_filter: str | None = None,
    skill_filter: str | None = None,
    command_path: Path | None = None,
    as_json: bool = False,
) -> dict[str, Any]:
    """Run all configured validators and return aggregated results."""
    validate_plugin_script = SCRIPTS_DIR / "validate_plugin.py"
    validate_skill_script = SCRIPTS_DIR / "validate_skill.py"
    validate_command_script = SCRIPTS_DIR / "validate_command.py"
    validate_marketplace_script = SCRIPTS_DIR / "validate_marketplace.py"

    plugin_results: list[dict[str, Any]] = []
    skill_results: list[dict[str, Any]] = []
    marketplace_result: dict[str, Any] | None = None
    command_results: list[dict[str, Any]] = []

    total_failures = 0
    total_warnings = 0

    # Plugins
    if plugin_filter:
        plugin_dirs = [repo_root / "plugins" / plugin_filter]
    elif command_path is None:
        plugin_dirs = discover_plugins(repo_root)
    else:
        plugin_dirs = []

    for plugin_dir in plugin_dirs:
        res = run_validator(validate_plugin_script, plugin_dir)
        # Use directory name as key for display
        res["_display_name"] = plugin_dir.name
        plugin_results.append(res)
        total_failures += res.get("failures", 0)
        total_warnings += res.get("warnings", 0)

    # Skills
    if skill_filter:
        skill_dirs = [repo_root / "skills" / skill_filter]
    elif command_path is None and plugin_filter is None:
        skill_dirs = discover_skills(repo_root)
    else:
        skill_dirs = []

    for skill_dir in skill_dirs:
        res = run_validator(validate_skill_script, skill_dir)
        res["_display_name"] = skill_dir.name
        skill_results.append(res)
        total_failures += res.get("failures", 0)
        total_warnings += res.get("warnings", 0)

    # Marketplace
    if command_path is None and plugin_filter is None and skill_filter is None:
        marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
        if marketplace_path.exists():
            marketplace_result = run_validator(validate_marketplace_script, marketplace_path)
            total_failures += marketplace_result.get("failures", 0)
            total_warnings += marketplace_result.get("warnings", 0)

    # Single command
    if command_path is not None:
        res = run_validator(validate_command_script, command_path)
        res["_display_name"] = command_path.name
        command_results.append(res)
        total_failures += res.get("failures", 0)
        total_warnings += res.get("warnings", 0)

    overall = (
        "FAIL" if total_failures > 0
        else ("WARN" if total_warnings > 0 else "PASS")
    )

    aggregated: dict[str, Any] = {
        "date": str(date.today()),
        "result": overall,
        "plugins": plugin_results,
        "skills": skill_results,
        "marketplace": marketplace_result,
        "commands": command_results,
        "summary": {
            "total": len(plugin_results) + len(skill_results) + len(command_results) + (1 if marketplace_result else 0),
            "pass": sum(1 for r in plugin_results + skill_results + command_results if r.get("result") == "PASS")
                    + (1 if marketplace_result and marketplace_result.get("result") == "PASS" else 0),
            "fail": sum(1 for r in plugin_results + skill_results + command_results if r.get("failures", 0) > 0)
                    + (1 if marketplace_result and marketplace_result.get("failures", 0) > 0 else 0),
            "warn": sum(1 for r in plugin_results + skill_results + command_results
                        if r.get("warnings", 0) > 0 and r.get("failures", 0) == 0)
                    + (1 if marketplace_result and marketplace_result.get("warnings", 0) > 0
                       and marketplace_result.get("failures", 0) == 0 else 0),
        },
    }
    return aggregated


def format_human(aggregated: dict[str, Any]) -> str:
    """Format aggregated results as human-readable text."""
    lines = [
        f"QA Test Run — {aggregated['date']}",
        "═" * 51,
    ]

    plugins = aggregated.get("plugins", [])
    if plugins:
        lines.append(f"Plugins ({len(plugins)})")
        for r in plugins:
            lines.append(format_result_row(r.get("_display_name", "?"), r))

    skills = aggregated.get("skills", [])
    if skills:
        lines.append(f"Skills ({len(skills)})")
        for r in skills:
            lines.append(format_result_row(r.get("_display_name", "?"), r))

    commands = aggregated.get("commands", [])
    if commands:
        lines.append(f"Commands ({len(commands)})")
        for r in commands:
            lines.append(format_result_row(r.get("_display_name", "?"), r))

    marketplace = aggregated.get("marketplace")
    if marketplace:
        lines.append("Marketplace")
        lines.append(format_result_row("marketplace.json", marketplace))

    lines.append("═" * 51)
    s = aggregated["summary"]
    lines.append(
        f"Summary: {s['total']} total  "
        f"{s['pass']} PASS  {s['fail']} FAIL  {s['warn']} WARN"
    )
    return "\n".join(lines)


def main() -> None:
    """Entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Run QA validation against plugins, skills, and marketplace"
    )
    parser.add_argument("--all", action="store_true",
                        help="Validate all plugins, skills, and marketplace")
    parser.add_argument("--plugin", metavar="NAME",
                        help="Validate a single plugin by name")
    parser.add_argument("--skill", metavar="NAME",
                        help="Validate a single skill by name")
    parser.add_argument("--command", metavar="PATH", type=Path,
                        help="Validate a single command file")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of human-readable text")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT,
                        help="Repository root directory (default: 3 levels up from this script)")
    args = parser.parse_args()

    if not args.all and not args.plugin and not args.skill and not args.command:
        parser.print_help()
        sys.exit(0)

    aggregated = run_all(
        repo_root=args.repo_root,
        plugin_filter=args.plugin,
        skill_filter=args.skill,
        command_path=args.command,
        as_json=args.json,
    )

    # Write last run results
    try:
        LAST_RUN_PATH.write_text(json.dumps(aggregated, indent=2), encoding="utf-8")
    except OSError:
        pass  # Non-fatal: report generation will warn if file is missing

    if args.json:
        print(json.dumps(aggregated, indent=2))
    else:
        print(format_human(aggregated))

    if aggregated["summary"]["fail"] > 0:
        sys.exit(1)
    elif aggregated["summary"]["warn"] > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
