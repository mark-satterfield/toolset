#!/usr/bin/env python3
"""
audit_plugin.py — audit a Claude Code plugin directory.

Walks .claude/agents/*.md and .claude/skills/*/SKILL.md, runs structural and
content checks, emits findings as JSON to stdout.

Usage:
    python scripts/audit_plugin.py <plugin-root> [--pretty]

Exit codes:
    0  clean (or info-only findings)
    1  at least one warn-severity finding
    2  at least one error-severity finding
    3  scan failed

Stdlib only. No third-party dependencies.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------- Frontmatter parsing (minimal, single-line scalar + list) ----------

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def parse_frontmatter(text):
    """Return (frontmatter_dict, body_str). Returns (None, text) if no frontmatter."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    raw_fm, body = m.group(1), m.group(2)
    fm = {}
    current_list = None
    for line in raw_fm.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list is not None:
            current_list.append(stripped[2:].strip().strip('"\''))
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if not value:
                current_list = []
                fm[key] = current_list
            else:
                fm[key] = value.strip('"\'')
                current_list = None
    return fm, body


# ---------- Body analysis helpers ----------

CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def prose_line_count(body):
    """Count non-blank lines in body, excluding fenced code blocks."""
    no_code = CODE_FENCE_RE.sub("", body)
    return sum(1 for line in no_code.splitlines() if line.strip())


def extract_headings(body):
    """Return list of heading lines (lines starting with #)."""
    no_code = CODE_FENCE_RE.sub("", body)
    return [line.strip() for line in no_code.splitlines() if line.strip().startswith("#")]


def mentions_any(body, keywords):
    body_lower = body.lower()
    return any(kw.lower() in body_lower for kw in keywords)


def heading_set(text):
    fm, body = parse_frontmatter(text)
    if fm is None:
        body = text
    return {h.lower().lstrip("#").strip() for h in extract_headings(body) if h.lstrip("#").strip()}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------- Finding constructor ----------


def finding(file_path, severity, code, message, suggestion):
    return {
        "file": str(file_path),
        "severity": severity,
        "code": code,
        "message": message,
        "suggestion": suggestion,
    }


# ---------- Subagent checks ----------

OUTPUT_CONTRACT_KEYWORDS = [
    "## output",
    "## return",
    "## response",
    "output format",
    "return format",
    "respond with",
    "output contract",
    "return a",
    "responds with",
]


def check_subagent(rel_path, text):
    findings = []
    fm, body = parse_frontmatter(text)
    if fm is None:
        findings.append(finding(
            rel_path, "error", "subagent-missing-frontmatter",
            "Subagent file has no YAML frontmatter block.",
            "Add a `---` block at the top with `name` and `description`."
        ))
        return findings
    if "name" not in fm or not fm.get("name"):
        findings.append(finding(
            rel_path, "error", "subagent-missing-name",
            "Frontmatter lacks `name` field.",
            "Add `name: <activity-first-lowercase-name>`."
        ))
    desc = str(fm.get("description", "") or "")
    if not desc or len(desc) < 30:
        findings.append(finding(
            rel_path, "error", "subagent-missing-description",
            "Frontmatter description missing or under 30 characters.",
            "Write a description covering what the subagent does and when to delegate to it."
        ))
    has_tools = "tools" in fm and fm["tools"]
    has_model = "model" in fm and fm["model"]
    lines = prose_line_count(body)
    if not has_tools and not has_model and lines < 20:
        findings.append(finding(
            rel_path, "warn", "subagent-no-constraints",
            "No `tools` allowlist, no `model` override, and body under 20 lines.",
            "If the subagent has no role-specific identity, convert it to a forking skill."
        ))
    if lines > 50:
        findings.append(finding(
            rel_path, "warn", "subagent-body-too-long",
            f"Body is {lines} prose lines (limit 50). Likely embedded playbook content.",
            "Extract methodology to a skill, leave role declaration in the subagent."
        ))
    if not mentions_any(body, OUTPUT_CONTRACT_KEYWORDS):
        findings.append(finding(
            rel_path, "info", "subagent-no-output-contract",
            "No section describing return/output format detected.",
            "Add an explicit output contract so the parent can reliably parse the result."
        ))
    if lines < 5:
        findings.append(finding(
            rel_path, "warn", "subagent-hollow",
            f"Body is only {lines} lines.",
            "Either expand the role declaration or remove the subagent and call the skill directly."
        ))
    return findings


# ---------- Skill checks ----------

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TRIGGER_KEYWORDS = [
    "use when", "triggers", " when ", " for ", "use this",
    "auto-activate", "invoke", "trigger on",
]
MACRO_KEYWORDS = [
    "read input", "write output", "transform", "batch",
    "process the", "rewrite", "convert", "generate a file",
    "produce a file", "emit a", "extract from",
]


def check_skill(rel_path, text, skill_dir):
    findings = []
    fm, body = parse_frontmatter(text)
    if fm is None:
        findings.append(finding(
            rel_path, "error", "skill-missing-frontmatter",
            "SKILL.md has no YAML frontmatter block.",
            "Add a `---` block with `name` and `description`."
        ))
        return findings
    name = str(fm.get("name", "") or "")
    desc = str(fm.get("description", "") or "")
    if not name:
        findings.append(finding(
            rel_path, "error", "skill-missing-name",
            "Frontmatter lacks `name`.",
            "Add `name: <activity-first-lowercase-name>`."
        ))
    elif not NAME_RE.match(name) or len(name) > 64:
        findings.append(finding(
            rel_path, "error", "skill-name-invalid",
            f"Name `{name}` is invalid (lowercase, hyphenated, max 64 chars).",
            "Rename to match pattern: lowercase letters, digits, hyphens only."
        ))
    if not desc:
        findings.append(finding(
            rel_path, "error", "skill-missing-description",
            "Frontmatter lacks `description`.",
            "Add a description covering what the skill does and when it triggers."
        ))
    else:
        if len(desc) < 60:
            findings.append(finding(
                rel_path, "warn", "skill-description-too-short",
                f"Description is {len(desc)} characters; classifier text is typically 100+.",
                "Expand to cover what it does, when to trigger, and any exclusions."
            ))
        if not mentions_any(desc, TRIGGER_KEYWORDS):
            findings.append(finding(
                rel_path, "warn", "skill-description-no-trigger",
                "Description lacks trigger language.",
                "Include phrases like 'Use when...', 'Triggers on...', or specific contexts."
            ))
    lines = prose_line_count(body)
    if lines > 250:
        findings.append(finding(
            rel_path, "warn", "skill-body-too-long",
            f"Body is {lines} prose lines. Consider moving detail to references/.",
            "Identify content used only sometimes and extract to references/<topic>.md."
        ))
    refs_dir = skill_dir / "references"
    refs_has_content = refs_dir.is_dir() and any(refs_dir.iterdir())
    if refs_has_content and "references/" not in body.lower():
        findings.append(finding(
            rel_path, "warn", "skill-references-dir-unused",
            "references/ directory exists but is not mentioned in SKILL.md.",
            "Add explicit references with guidance on when to load each."
        ))
    scripts_dir = skill_dir / "scripts"
    scripts_has_content = scripts_dir.is_dir() and any(scripts_dir.iterdir())
    if scripts_has_content and "scripts/" not in body.lower():
        findings.append(finding(
            rel_path, "warn", "skill-scripts-dir-unused",
            "scripts/ directory exists but is not mentioned in SKILL.md.",
            "Document when to run which script and the expected I/O."
        ))
    if str(fm.get("disable-model-invocation", "")).lower() == "true":
        if not re.search(r"/[a-z][a-z0-9_-]+", body):
            findings.append(finding(
                rel_path, "warn", "skill-disabled-invocation-undocumented",
                "`disable-model-invocation: true` set but no /command usage documented.",
                "Document the slash command users should type, or remove the flag."
            ))
    if str(fm.get("context", "")).lower() == "fork":
        if lines < 20 and not refs_has_content and not scripts_has_content:
            findings.append(finding(
                rel_path, "info", "skill-fork-on-thin-body",
                f"`context: fork` on a thin body ({lines} lines, no references/scripts).",
                "Spawn cost likely dominates; consider removing the fork directive."
            ))
    else:
        if mentions_any(body, MACRO_KEYWORDS) and lines > 30:
            findings.append(finding(
                rel_path, "info", "skill-no-fork-on-macro-body",
                "Body has macro-shape keywords but no `context: fork`.",
                "Consider adding `context: fork` to keep parent context clean."
            ))
    return findings


# ---------- Cross-file checks ----------


def cross_file_checks(agent_files, skill_files, root):
    findings = []
    skill_dirs_by_name = {sp.parent.name: sp for sp in skill_files}
    for ap, atext in agent_files.items():
        astem = ap.stem
        if astem in skill_dirs_by_name:
            matching_skill = skill_dirs_by_name[astem]
            a_heads = heading_set(atext)
            s_heads = heading_set(skill_files[matching_skill])
            if a_heads and s_heads:
                sim = jaccard(a_heads, s_heads)
                if sim > 0.4:
                    rel = ap.relative_to(root)
                    findings.append(finding(
                        rel, "warn", "paired-files-duplication",
                        f"Subagent and skill `{astem}` share heading similarity {sim:.2f}.",
                        "Move methodology into the skill and reference it from the subagent."
                    ))
    return findings


# ---------- Driver ----------


def scan_plugin(root_str):
    root = Path(root_str).resolve()
    if not root.is_dir():
        return None, f"Plugin root not found or not a directory: {root}"
    agents_dir = root / ".claude" / "agents"
    skills_dir = root / ".claude" / "skills"
    agent_files = {}
    skill_files = {}
    if agents_dir.is_dir():
        for p in sorted(agents_dir.glob("*.md")):
            try:
                agent_files[p] = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                try:
                    skill_files[skill_md] = skill_md.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
    findings = []
    for p, t in agent_files.items():
        findings.extend(check_subagent(p.relative_to(root), t))
    for p, t in skill_files.items():
        findings.extend(check_skill(p.relative_to(root), t, p.parent))
    findings.extend(cross_file_checks(agent_files, skill_files, root))
    report = {
        "plugin_root": str(root),
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files_scanned": len(agent_files) + len(skill_files),
        "findings": findings,
    }
    return report, None


def main():
    parser = argparse.ArgumentParser(description="Audit a Claude Code plugin layout.")
    parser.add_argument("plugin_root", help="Path to plugin root (parent of .claude/)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()
    report, err = scan_plugin(args.plugin_root)
    if err:
        print(json.dumps({"error": err}), file=sys.stderr)
        sys.exit(3)
    indent = 2 if args.pretty else None
    print(json.dumps(report, indent=indent))
    severities = {f["severity"] for f in report["findings"]}
    if "error" in severities:
        sys.exit(2)
    if "warn" in severities:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
