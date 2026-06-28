#!/usr/bin/env python3
"""
check_nav_dropdown — a rendered nav dropdown trigger is well-formed (components.md §12.1/§12.2).

Dropdown panels are fully specified in components.md §12.2 (flat / mega /
lift-and-scale) and a §12.1 `primary-nav` item may be a dropdown trigger. When
the rendered landing sample includes such a trigger, it MUST carry the ARIA
contract — otherwise the dropdown is keyboard- and screen-reader-broken.

PROPERTY — every dropdown trigger present is well-formed.
    For each element carrying `aria-haspopup="menu"` in the rendered sample:
      * it also carries `aria-expanded` (the open/closed state), and
      * the document contains at least one `role="menu"` panel.
    This is a CORRECTNESS guard, not a presence requirement: a landing sample
    with no dropdown trigger passes cleanly (a page need not have a dropdown).

Render-dependent: if the landing sample is not built, the check skips cleanly
(artifact existence is run-tests.sh tier 3's job). No class name, label, theme,
or count is hardcoded — only the §12.2 ARIA contract.

Entry point:
    run(repo_root) -> list[str]   # empty list == passed (or skipped)
"""

import os
import re

LANDING_SUBPATH = os.path.join(
    "plugins", "cds", "test", "visual-proof-out", "landing.html")
_REL = os.path.join("test", "visual-proof-out", "landing.html")

# An element open-tag carrying aria-haspopup="menu" (single- or double-quoted).
_TRIGGER = re.compile(r"<([a-zA-Z][\w-]*)\b([^>]*\baria-haspopup\s*=\s*[\"']menu[\"'][^>]*)>", re.S)
_HAS_EXPANDED = re.compile(r"\baria-expanded\s*=\s*[\"'](?:true|false)[\"']")
_HAS_MENU = re.compile(r"\brole\s*=\s*[\"']menu[\"']")


def run(repo_root):
    path = os.path.join(repo_root, LANDING_SUBPATH)
    if not os.path.isfile(path):
        return []  # render sample not built — nothing to check

    with open(path, encoding="utf-8") as f:
        html = f.read()

    triggers = list(_TRIGGER.finditer(html))
    if not triggers:
        return []  # no dropdown in this sample — nothing to assert

    failures = []
    menu_present = bool(_HAS_MENU.search(html))
    for i, m in enumerate(triggers):
        attrs = m.group(2)
        if not _HAS_EXPANDED.search(attrs):
            failures.append(
                f"{_REL}: dropdown trigger #{i + 1} (<{m.group(1)} "
                f"aria-haspopup=\"menu\">) is missing `aria-expanded` "
                f"(components.md §12.2 keyboard/ARIA contract).")
    if not menu_present:
        failures.append(
            f"{_REL}: a dropdown trigger is present but no `role=\"menu\"` panel "
            f"exists in the document (components.md §12.2).")
    return failures


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    out = run(root)
    print("PASS" if not out else "FAIL")
    for f in out:
        print("  -", f)
