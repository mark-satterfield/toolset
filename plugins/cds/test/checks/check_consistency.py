#!/usr/bin/env python3
"""
check_consistency — halt-code + env-var consistency for the cds plugin.

This module asserts two cross-file PROPERTIES of the live cds plugin tree. It
hardcodes no theme names, counts, halt-code lists, or env-var lists — it reads
whatever the repo currently declares and checks internal agreement.

PROPERTY 1 — halt-code propagation (command Notes -> matching skill).
    Every command (`commands/<name>.md`) delegates to a skill of the same name
    (`skills/<name>/SKILL.md`). The command's `## Notes` section advertises, in
    backticks, the halt codes a user may see. Each such halt code MUST also be
    declared in that skill's `## Halt conditions` section — otherwise the command
    promises a halt the skill cannot produce. Codes are compared by their BASE
    (the UPPER_SNAKE_CASE name before any `:{...}` / `:concrete` suffix), so
    `MISSING_COMPONENT` in Notes matches `MISSING_COMPONENT:{name}` in the skill.

PROPERTY 2 — env-var name hygiene.
    Every `CUSTOMIZABLE_DESIGN_SYSTEM_*` name used anywhere across skills,
    commands, agents, and the README must be drawn from one consistent set with
    no near-duplicate typo variants (a name that differs from another by a single
    character edit — the signature of a typo'd duplicate of the same variable).

Conservative by design: a halt code merely *mentioned* in prose (not in a
command's Notes block) is never required of a skill; an env-var name is only
flagged when a second, almost-identical name also exists.

Entry point:
    run(repo_root) -> list[str]   # empty list == all checks passed
"""

import os
import re

try:
    import yaml  # noqa: F401  (kept for parity with the existing linter's deps)
except ImportError:  # pragma: no cover - yaml is a declared dependency
    yaml = None


PLUGIN_SUBPATH = os.path.join("plugins", "cds")

# An UPPER_SNAKE_CASE token, optionally followed by a `:suffix` or `:{placeholder}`.
HALT_TOKEN = re.compile(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)(:\{?[A-Za-z0-9_-]*\}?)?`")
ENV_TOKEN = re.compile(r"CUSTOMIZABLE_DESIGN_SYSTEM(?:_[A-Z0-9]+)*")
# Env-var name that is a bare prefix / placeholder fragment, not a real variable
# (e.g. a sentence that says "CUSTOMIZABLE_DESIGN_SYSTEM_" with nothing after).
ENV_BARE_PREFIX = "CUSTOMIZABLE_DESIGN_SYSTEM"


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def _section(text, heading):
    """Return the body of a `## <heading>` markdown section, or '' if absent.

    Captures from the heading line up to the next heading of equal-or-higher
    level (a line beginning with one or two '#').
    """
    lines = text.splitlines()
    out = []
    capturing = False
    want = heading.strip().lower()
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip().lower()
            if capturing:
                # Stop at the next sibling-or-higher heading (## or #).
                if level <= 2:
                    break
                # A deeper heading (### …) stays inside the section.
                out.append(line)
                continue
            if level <= 2 and title.startswith(want):
                capturing = True
            continue
        if capturing:
            out.append(line)
    return "\n".join(out)


def _base(code):
    """Strip a `:{...}`/`:concrete` suffix, leaving the bare UPPER_SNAKE base."""
    return code.split(":", 1)[0]


def _halt_codes_in(text):
    """Backtick-quoted halt-code BASES found in `text`. Returns a set of bases."""
    return {_base(m.group(1)) for m in HALT_TOKEN.finditer(text)}


def _iter_files(root, exts):
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in exts:
                yield os.path.join(dirpath, fn)


def _edit_distance_le_1(a, b):
    """True iff strings differ by at most a single insert/delete/substitution."""
    if a == b:
        return False  # identical is not a "near-duplicate"
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:  # at most one substitution
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    # lengths differ by exactly 1 -> check for a single insertion/deletion
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    i = j = 0
    edited = False
    while i < la and j < lb:
        if a[i] == b[j]:
            i += 1
            j += 1
        else:
            if edited:
                return False
            edited = True
            j += 1  # skip the extra char in the longer string
    return True


def run(repo_root):
    failures = []
    plugin_root = os.path.join(repo_root, PLUGIN_SUBPATH)

    if not os.path.isdir(plugin_root):
        return [f"cds plugin directory not found at {plugin_root}"]

    commands_dir = os.path.join(plugin_root, "commands")
    skills_dir = os.path.join(plugin_root, "skills")

    # ---- PROPERTY 1: halt codes in a command's Notes appear in its skill ----
    if os.path.isdir(commands_dir):
        for fn in sorted(os.listdir(commands_dir)):
            if not fn.endswith(".md"):
                continue
            name = fn[:-3]
            cmd_path = os.path.join(commands_dir, fn)
            skill_path = os.path.join(skills_dir, name, "SKILL.md")

            notes = _section(_read(cmd_path), "Notes")
            if not notes.strip():
                continue
            notes_codes = _halt_codes_in(notes)
            if not notes_codes:
                continue

            if not os.path.isfile(skill_path):
                failures.append(
                    f"command '{name}' Notes references halt codes "
                    f"{sorted(notes_codes)} but no matching skill exists at "
                    f"skills/{name}/SKILL.md"
                )
                continue

            halt_section = _section(_read(skill_path), "Halt conditions")
            skill_codes = _halt_codes_in(halt_section)
            missing = sorted(notes_codes - skill_codes)
            for code in missing:
                failures.append(
                    f"halt code '{code}' is advertised in commands/{fn} Notes "
                    f"but is not declared in skills/{name}/SKILL.md "
                    f"'## Halt conditions'"
                )

    # ---- PROPERTY 2: env-var names form one set with no typo variants ----
    env_names = set()
    for path in _iter_files(plugin_root, {".md"}):
        # Skip this test harness's own files so example/illustrative names there
        # never masquerade as plugin contract.
        rel = os.path.relpath(path, plugin_root)
        if rel.split(os.sep)[0] == "test":
            continue
        for m in ENV_TOKEN.finditer(_read(path)):
            tok = m.group(0)
            if tok == ENV_BARE_PREFIX:
                continue  # bare prefix used illustratively, not a real var
            env_names.add(tok)

    names = sorted(env_names)
    reported_pairs = set()
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _edit_distance_le_1(a, b):
                key = (a, b)
                if key not in reported_pairs:
                    reported_pairs.add(key)
                    failures.append(
                        f"env-var names '{a}' and '{b}' differ by a single "
                        f"character — likely a typo variant of the same variable"
                    )

    return failures


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    for f in run(root):
        print("FAIL:", f)
