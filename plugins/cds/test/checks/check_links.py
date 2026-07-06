#!/usr/bin/env python3
"""
check_links — cross-reference + link resolution for the CDS plugin.

PROPERTY ASSERTED
    Every intra-repo file pointer written in any *.md under the plugin resolves
    to a file that actually exists on disk. A pointer is a "dead link" if it
    names a repo file (by markdown link target or by a path-shaped inline code
    span) that cannot be found relative to either the document that mentions it
    or the plugin root.

This is the check that catches dead pointers such as the README "cheat sheet"
referencing `reference/vocabulary.md` after that file was deleted, or a
component spec citing `foundations/type.md` when the real file is
`typography.md`.

WHAT COUNTS AS A REFERENCE
    1. Markdown links  [text](target)  — when the target is a relative path to
       a repo file (not an http(s) URL and not a pure in-page #anchor).
    2. Inline code spans  `path/to/file.ext`  — only when the span is clearly a
       *path*: it contains a "/" separator AND ends in a known repo file
       extension. Bare filenames (`README.md`, `tokens.css`) are NOT treated as
       pointers — in this corpus they appear as runtime artifacts or as prose
       shorthand whose directory context is established elsewhere, so resolving
       them would manufacture false positives. Requiring a separator keeps the
       check to genuine "this file lives over there" pointers.

WHAT IS DELIBERATELY IGNORED
    - External URLs (http://, https://, mailto:, etc.).
    - Pure in-page anchors (#section).
    - Glob / brace / placeholder forms that are not concrete paths:
      anything containing  * ? { } < > $ ~ | (space)  — e.g.
      `foundations/*.md`, `commands/{a,b}.md`, `<project-root>/x.yaml`,
      `~/.claude/settings.json`. These are patterns or user-supplied paths, not
      claims about a file shipped in the repo.
    - Absolute paths (leading "/") — they describe install locations, not repo
      files, and cannot be checked against the repo deterministically.

RESOLUTION
    The corpus mixes pointer conventions, so resolution is split by form:

    - Dot-relative paths (`./x`, `../x`) are explicit traversals from the
      document. They resolve ONLY relative to the document's own directory —
      that is exactly what the author wrote, so it is checked literally.

    - Non-dot paths (`reference/vocabulary.md`, `foundations/type.md`) are
      written against an implicit base that varies: the README cheat sheet
      means "from the plugin root", while a SKILL.md may mean "from the
      `reference/` directory named in nearby prose". To avoid manufacturing
      false positives from that ambiguity, a non-dot path resolves if it exists
      under the document's directory, the plugin root, OR ANY directory in the
      plugin tree. It is reported dead only when no directory anywhere in the
      plugin contains that relative path — which is precisely the signature of
      a renamed/deleted target (e.g. `foundations/type.md` when the real file
      is `foundations/typography.md`).

    A pointer is dead only when it fails under every applicable base.

This reads the LIVE files each run and asserts the existence property; it
hardcodes no expected filenames, counts, or link targets, so a different but
internally consistent plugin layout still passes.

Public entry point:
    run(repo_root) -> list[str]   (empty list == all checks passed)
"""

import os
import re

# File extensions that denote a concrete repo artifact a pointer can name.
_REPO_EXTS = (
    ".md", ".json", ".yaml", ".yml", ".css", ".html", ".py", ".sh",
    ".js", ".jsx", ".ts", ".tsx", ".svg", ".txt", ".schema.json",
)

# Characters that mean a code span is a pattern / placeholder / user path,
# not a concrete in-repo pointer.
_NON_PATH_CHARS = set("*?{}<>$~| ")

# Inline code spans: `...` (non-greedy, single line).
_CODE_SPAN = re.compile(r"`([^`\n]+)`")

# Markdown links: [text](target)  — target captured up to the first space or ).
_MD_LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)")


def _is_external_or_anchor(target):
    if target.startswith("#"):
        return True
    # scheme:// or mailto: etc.
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", target):
        return True
    return False


def _strip_anchor(target):
    """Drop a trailing #fragment so `foo.md#section` checks `foo.md`."""
    return target.split("#", 1)[0]


def _looks_like_repo_path(token):
    """True if `token` is a concrete relative path to a repo file extension."""
    if not token:
        return False
    if any(c in _NON_PATH_CHARS for c in token):
        return False
    if token.startswith("/"):  # absolute install path, not a repo file
        return False
    if "/" not in token:  # bare filename — not a directional pointer
        return False
    return token.lower().endswith(_REPO_EXTS)


def _md_link_targets(text):
    out = []
    for m in _MD_LINK.finditer(text):
        target = _strip_anchor(m.group(1).strip())
        if not target or _is_external_or_anchor(target):
            continue
        if target.startswith("/"):
            continue
        out.append(target)
    return out


def _code_span_paths(text):
    out = []
    for m in _CODE_SPAN.finditer(text):
        token = _strip_anchor(m.group(1).strip())
        if _looks_like_repo_path(token):
            out.append(token)
    return out


def _is_dot_relative(target):
    return target.startswith("./") or target.startswith("../")


def _resolves(target, doc_dir, all_dirs):
    """A target resolves per its form (see module docstring, RESOLUTION)."""
    if _is_dot_relative(target):
        # Explicit traversal: check exactly what was written, from the doc dir.
        return os.path.exists(os.path.normpath(os.path.join(doc_dir, target)))
    # Non-dot path: implicit base. Resolves if it exists under the doc dir or
    # under ANY directory in the plugin tree.
    for base in all_dirs:
        if os.path.exists(os.path.normpath(os.path.join(base, target))):
            return True
    return os.path.exists(os.path.normpath(os.path.join(doc_dir, target)))


def run(repo_root):
    failures = []
    plugin_root = os.path.join(repo_root, "plugins", "cds")

    if not os.path.isdir(plugin_root):
        return [f"plugin root not found: {plugin_root}"]

    md_files = []
    all_dirs = []
    for dirpath, _dirs, files in os.walk(plugin_root):
        # analysis/ is the historical migration record and cites deleted files by design.
        _dirs[:] = [d for d in _dirs if not (dirpath == plugin_root and d == "analysis")]
        all_dirs.append(dirpath)
        for fn in files:
            if fn.lower().endswith(".md"):
                md_files.append(os.path.join(dirpath, fn))
    md_files.sort()

    for path in md_files:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as e:
            failures.append(f"{os.path.relpath(path, repo_root)}: unreadable ({e})")
            continue

        doc_dir = os.path.dirname(path)
        rel_doc = os.path.relpath(path, repo_root)

        # De-duplicate references within a single file so one repeated dead
        # pointer is reported once per file.
        seen = set()
        for target in _md_link_targets(text) + _code_span_paths(text):
            if target in seen:
                continue
            seen.add(target)
            if not _resolves(target, doc_dir, all_dirs):
                where = (
                    "relative to its own directory"
                    if _is_dot_relative(target)
                    else "anywhere in the plugin tree"
                )
                failures.append(
                    f"{rel_doc}: dead reference '{target}' (no such file {where})"
                )

    return failures


if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    for line in run(os.path.abspath(root)):
        print(line)
