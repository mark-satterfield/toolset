#!/usr/bin/env python3
"""
check_token_coverage — every token the components reference must be defined.

A silent, high-impact failure mode: `components.css` references a custom property
(e.g. `var(--sp-2)`, `var(--radius-lg)`) that the generated stylesheet set never
defines. The browser then resolves it to nothing, and the component collapses
(padding 0, radius 0) — rendering as a bare box while every file looks fine in
isolation. This check makes that failure loud.

PROPERTY — closed token graph.
    Every `var(--token)` referenced in the generated `components.css` MUST be
    defined (`--token: ...`) somewhere in the generated stylesheet set
    (`tokens.css`, `themes.css`, or `components.css` itself). Definitions found
    under any selector count (role tokens are theme-scoped in `themes.css`; the
    spacing/radius/section-pad scales are in `tokens.css`). CSS comments are
    stripped first, so documentation like `var(--role-*)` is not mistaken for a
    reference.

Config-agnostic: it reads whatever the generated set currently declares and
references — no token name, count, or theme is hardcoded. If the generated
styles are not present (artifacts not built), the check skips cleanly.

Entry point:
    run(repo_root) -> list[str]   # empty list == passed (or skipped)
"""

import os
import re

STYLES_SUBPATH = os.path.join("plugins", "cds", "test", "visual-proof-out", "styles")
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_DEF_RE = re.compile(r"(--[a-z0-9-]+)\s*:")
_REF_RE = re.compile(r"var\(\s*(--[a-z0-9-]+)")


def _strip_comments(css):
    return _COMMENT_RE.sub("", css)


def run(repo_root):
    styles = os.path.join(repo_root, STYLES_SUBPATH)
    components = os.path.join(styles, "components.css")
    if not os.path.isfile(components):
        # Render artifacts not built — nothing to check, not a failure.
        return []

    defined = set()
    for name in ("tokens.css", "themes.css", "components.css"):
        p = os.path.join(styles, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                defined |= set(_DEF_RE.findall(_strip_comments(f.read())))

    with open(components, encoding="utf-8") as f:
        referenced = set(_REF_RE.findall(_strip_comments(f.read())))

    missing = sorted(referenced - defined)
    return [
        f"TOKEN-COVERAGE: components.css references {tok} but it is defined "
        f"nowhere in the generated stylesheet set (tokens.css / themes.css). "
        f"generate-stylesheets must emit it; otherwise the component renders "
        f"with that property collapsed."
        for tok in missing
    ]


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    out = run(root)
    print("PASS" if not out else "FAIL")
    for f in out:
        print("  -", f)
