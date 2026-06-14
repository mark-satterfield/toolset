#!/usr/bin/env python3
"""Check a PRD for structural conformance to the canonical PRD template.

The template at ``references/prd-template.md`` is the single source of truth.
This linter reads it at runtime to derive the required section set and order,
so it never drifts from the template — change the template and the checks
follow automatically.

It validates only what is *mechanically* decidable:
  - the H1 title line is present
  - every required ``##`` section from the template is present, in order
  - ``Last Updated`` is a real YYYY-MM-DD date, not the placeholder
  - no template scaffolding remains (HTML comments, ``[placeholder]`` brackets,
    unfilled ``P0 | P1 | P2`` priority lines)
  - every P0 requirement carries an Acceptance Criteria block

It cannot judge *semantic* conformance — whether the Problem is stated from the
user's perspective, whether implementation detail (HOW) has leaked into a WHAT
document, or whether acceptance criteria are genuinely testable. A human or
agent reviewer must still make those calls (see SKILL.md, "Validate mode").

Usage:
    python3 check_prd.py <path-to-prd.md> [--template <path>] [--json]

Exit code 0 when there are no errors (warnings allowed), 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

H1_RE = re.compile(r"^#\s+(.*\S)\s*$")
H2_RE = re.compile(r"^##\s+(.*\S)\s*$")
TITLE_RE = re.compile(r"^#\s+Feature PRD:")
LAST_UPDATED_RE = re.compile(r"^\*\*Last Updated:\*\*\s*(.+?)\s*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRIORITY_RE = re.compile(r"\*\*Priority:\*\*\s*(.+?)\s*$")
ACCEPTANCE_RE = re.compile(r"\*\*Acceptance Criteria:?\*\*", re.IGNORECASE)
# A bracketed placeholder like [Feature Name] or [Goal], but not a markdown
# link [text](url) and not a task checkbox [ ] / [x].
PLACEHOLDER_RE = re.compile(r"(?<!\!)\[[^\]\n]+\](?!\()")
CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[[ xX]\]")


def iter_logical_lines(text: str):
    """Yield (lineno, line, in_code, in_comment) skipping nothing.

    Tracks fenced-code (```), tilde-fence (~~~) and HTML-comment state so callers
    can ignore headings/placeholders that live inside code or comments.
    """
    in_code = False
    fence = ""
    in_comment = False
    for i, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.lstrip()
        # Toggle fenced code blocks.
        if not in_comment and (stripped.startswith("```") or stripped.startswith("~~~")):
            token = stripped[:3]
            if not in_code:
                in_code, fence = True, token
            elif stripped.startswith(fence):
                in_code, fence = False, ""
            yield i, raw, in_code, in_comment
            continue
        # Track (possibly multi-line) HTML comments.
        comment_here = in_comment
        if not in_code:
            if in_comment:
                if "-->" in raw:
                    in_comment = False
            else:
                if "<!--" in raw and "-->" not in raw:
                    in_comment = True
                comment_here = comment_here or "<!--" in raw
        yield i, raw, in_code, comment_here


def extract_sections(text: str) -> list[str]:
    """Return the ordered list of top-level (##) section titles, ignoring code/comments."""
    sections: list[str] = []
    for _, line, in_code, in_comment in iter_logical_lines(text):
        if in_code or in_comment:
            continue
        m = H2_RE.match(line)
        if m:
            sections.append(m.group(1).strip())
    return sections


def order_violations(expected: list[str], actual: list[str]) -> list[str]:
    """Names present but out of template order relative to their predecessors."""
    present = [s for s in expected if s in actual]
    positions = [actual.index(s) for s in present]
    problems = []
    for idx in range(1, len(positions)):
        if positions[idx] < positions[idx - 1]:
            problems.append(present[idx])
    return problems


def check_prd(prd_path: Path, template_path: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    template_text = template_path.read_text(encoding="utf-8")
    prd_text = prd_path.read_text(encoding="utf-8")

    expected = extract_sections(template_text)
    actual = extract_sections(prd_text)

    # 1. Title.
    if not any(TITLE_RE.match(ln) for ln in prd_text.splitlines()):
        errors.append("Missing H1 title line: '# Feature PRD: <name>'")

    # 2. Required sections present.
    missing = [s for s in expected if s not in actual]
    if missing:
        errors.append("Missing required sections: " + ", ".join(missing))

    # 3. Section order.
    misordered = order_violations(expected, actual)
    if misordered:
        errors.append("Sections out of template order: " + ", ".join(misordered))

    # 4. Extra (non-template) sections — informational only.
    extra = [s for s in actual if s not in expected]
    if extra:
        warnings.append("Extra sections not in template: " + ", ".join(extra))

    # 5. Last Updated is a real date.
    last_updated = None
    for ln in prd_text.splitlines():
        m = LAST_UPDATED_RE.match(ln)
        if m:
            last_updated = m.group(1).strip()
            break
    if last_updated is None:
        errors.append("Missing '**Last Updated:** YYYY-MM-DD' line")
    elif last_updated == "YYYY-MM-DD" or not DATE_RE.match(last_updated):
        errors.append(f"'Last Updated' is not a valid date: {last_updated!r}")

    # 6. No leftover scaffolding: HTML comments and placeholders.
    comment_lines = []
    placeholder_hits = []
    priority_legend_lines = []
    for lineno, line, in_code, _ in iter_logical_lines(prd_text):
        if "<!--" in line:
            comment_lines.append(lineno)
        if in_code:
            continue
        if CHECKBOX_RE.match(line):
            continue
        for ph in PLACEHOLDER_RE.findall(line):
            placeholder_hits.append((lineno, ph))
        pm = PRIORITY_RE.search(line)
        if pm and "|" in pm.group(1):
            priority_legend_lines.append(lineno)
    if comment_lines:
        errors.append(
            "Template comments not deleted (lines "
            + ", ".join(map(str, comment_lines[:10]))
            + (", ..." if len(comment_lines) > 10 else "")
            + ")"
        )
    if priority_legend_lines:
        errors.append(
            "Unfilled '**Priority:** P0 | P1 | P2' line(s) — pick one (lines "
            + ", ".join(map(str, priority_legend_lines))
            + ")"
        )
    if placeholder_hits:
        sample = "; ".join(f"L{ln}:{ph}" for ln, ph in placeholder_hits[:8])
        warnings.append(
            f"Possible unfilled placeholders ({len(placeholder_hits)}): {sample}"
            + (" ..." if len(placeholder_hits) > 8 else "")
        )

    # 7. Every P0 requirement has Acceptance Criteria.
    errors.extend(_check_p0_acceptance(prd_text))

    ok = not errors
    return {
        "prd": str(prd_path),
        "template": str(template_path),
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "sections_found": actual,
    }


def _check_p0_acceptance(prd_text: str) -> list[str]:
    """For each requirement block whose priority is exactly P0, require an
    Acceptance Criteria marker before the next priority/section boundary."""
    lines = list(iter_logical_lines(prd_text))
    errors: list[str] = []
    last_heading = "(unnamed requirement)"
    i = 0
    n = len(lines)
    while i < n:
        lineno, line, in_code, in_comment = lines[i]
        if in_code or in_comment:
            i += 1
            continue
        if re.match(r"^#{3,4}\s+", line):
            last_heading = re.sub(r"^#{3,4}\s+", "", line).strip()
        pm = PRIORITY_RE.search(line)
        if pm:
            value = pm.group(1)
            tokens = re.findall(r"P[012]", value)
            is_single_p0 = "|" not in value and tokens == ["P0"]
            if is_single_p0:
                found = False
                j = i + 1
                while j < n:
                    _, l2, c2, m2 = lines[j]
                    if c2 or m2:
                        j += 1
                        continue
                    if H2_RE.match(l2) or PRIORITY_RE.search(l2):
                        break
                    if ACCEPTANCE_RE.search(l2):
                        found = True
                        break
                    j += 1
                if not found:
                    errors.append(
                        f"P0 requirement '{last_heading}' (line {lineno}) has no Acceptance Criteria"
                    )
        i += 1
    return errors


def format_report(result: dict) -> str:
    lines = [
        f"PRD Conformance Report: {result['prd']}",
        f"Template: {result['template']}",
        "",
    ]
    if not result["errors"] and not result["warnings"]:
        lines.append("PASS  All structural checks passed.")
    for e in result["errors"]:
        lines.append(f"FAIL  {e}")
    for w in result["warnings"]:
        lines.append(f"WARN  {w}")
    lines.append("")
    verdict = "PASS" if result["ok"] else "FAIL"
    lines.append(
        f"Result: {verdict} ({len(result['errors'])} error(s), {len(result['warnings'])} warning(s))"
    )
    lines.append(
        "Note: structural checks only — still verify WHAT-not-HOW, testable "
        "acceptance criteria, and evidence quality by hand (see SKILL.md)."
    )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check a PRD against the canonical template.")
    parser.add_argument("prd", help="Path to the PRD markdown file to check.")
    default_template = Path(__file__).resolve().parent.parent / "references" / "prd-template.md"
    parser.add_argument(
        "--template",
        default=str(default_template),
        help="Path to the PRD template (default: bundled references/prd-template.md).",
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    args = parser.parse_args(argv)

    prd_path = Path(args.prd)
    template_path = Path(args.template)
    if not prd_path.is_file():
        print(f"error: PRD not found: {prd_path}", file=sys.stderr)
        return 2
    if not template_path.is_file():
        print(f"error: template not found: {template_path}", file=sys.stderr)
        return 2

    result = check_prd(prd_path, template_path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_report(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
