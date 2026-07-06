#!/usr/bin/env python3
"""
check_topbar_nav — the topbar nav stays right-aligned
(reference/libraries/components/topbar.md).

A recurring regression: the compose step improvises the topbar with
`justify-content: space-between` across logo / nav / CTA, which strands the
`primary-nav` cluster in the CENTER. components/topbar.md is explicit that the
nav is "a cluster of nav links, right-aligned" — logo alone at the left, the
nav cluster + conversion CTA grouped at the right. This check makes that
contract enforceable instead of eyeball-only.

PROPERTY — topbar nav is right-aligned, never centered.
    In the rendered landing sample, the `class="topbar"` header MUST NOT use a
    distributing/centering `justify-content` (`space-between`, `center`,
    `space-around`, `space-evenly`) — those push the nav off the right edge — and
    MUST carry a positive right-alignment mechanism: `margin-left`/
    `margin-inline-start: auto` on the nav (or the header), or
    `justify-content: flex-end | end | right` on the header.

Render-dependent: if the landing sample is not built, the check skips cleanly
(artifact EXISTENCE is run-tests.sh tier 3's job; this guards CORRECTNESS when
present). No class name, theme, or count is hardcoded beyond the topbar contract.

Entry point:
    run(repo_root) -> list[str]   # empty list == passed (or skipped)
"""

import os
import re

LANDING_SUBPATH = os.path.join(
    "plugins", "cds", "test", "visual-proof-out", "landing.html")
_REL = os.path.join("test", "visual-proof-out", "landing.html")

_CENTERING = ("space-between", "center", "space-around", "space-evenly")
_RIGHTING = ("flex-end", "end", "right")
_MARGIN_AUTO = re.compile(r"margin-(?:left|inline-start):\s*auto")


def run(repo_root):
    path = os.path.join(repo_root, LANDING_SUBPATH)
    if not os.path.isfile(path):
        # Render sample not built — nothing to check, not a failure.
        return []

    with open(path, encoding="utf-8") as f:
        html = f.read()

    # Locate the topbar header element (its open tag may span multiple lines).
    m = re.search(r'<header\b[^>]*class="[^"]*\btopbar\b[^"]*"[^>]*>', html, re.S)
    if not m:
        # No topbar in this sample — nothing to assert.
        return []

    header_tag = " ".join(m.group(0).split())
    failures = []

    jc = re.search(r"justify-content:\s*([a-z-]+)", header_tag)
    jc_val = jc.group(1) if jc else None

    # 1) The topbar row must not center/distribute its children.
    if jc_val in _CENTERING:
        failures.append(
            f"{_REL}: topbar header uses `justify-content: {jc_val}`, which "
            f"strands the nav in the middle. components/topbar.md requires the "
            f"primary-nav right-aligned (logo left; nav + CTA grouped right) — "
            f"use `margin-inline-start: auto` on the nav or "
            f"`justify-content: flex-end` on the header.")
        return failures  # the centering bug is the failure; don't double-report

    # 2) There must be a positive right-alignment mechanism.
    end = html.find("</header>", m.end())
    inner = html[m.end():end] if end != -1 else html[m.end():m.end() + 2000]
    nav_m = re.search(r"<nav\b[^>]*>", inner, re.S)
    nav_tag = " ".join(nav_m.group(0).split()) if nav_m else ""

    right_aligned = (
        _MARGIN_AUTO.search(nav_tag)
        or _MARGIN_AUTO.search(header_tag)
        or (jc_val in _RIGHTING)
    )
    if not right_aligned:
        failures.append(
            f"{_REL}: topbar has no right-alignment mechanism for the nav "
            f"(expected `margin-inline-start: auto` on the nav, or "
            f"`justify-content: flex-end` on the header). components/topbar.md "
            f"requires the primary-nav cluster right-aligned.")

    return failures


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    out = run(root)
    print("PASS" if not out else "FAIL")
    for f in out:
        print("  -", f)
