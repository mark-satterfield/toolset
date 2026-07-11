# SPDX-License-Identifier: Apache-2.0
# Adapted from the OKF reference agent (Google Cloud Knowledge Catalog),
# licensed under Apache License 2.0:
# https://github.com/GoogleCloudPlatform/knowledge-catalog
# Modifications for the okf Claude Code plugin:
#   - directory summaries are deterministic (no LLM / no network);
#   - title fallback also honors `phrase` (glossary term notes);
#   - runnable as a CLI that regenerates every directory in one pass.
# See NOTICE.md in this directory.
"""Regenerate `index.md` for every directory in a bundle.

One call walks the whole tree, writes a conformant (frontmatter-free) index
per directory grouped by `type`, and propagates a one-line summary of each
subdirectory up into its parent's listing. Overwrites index files — hand-edited
index prose is not preserved; put durable prose in a concept, not an index.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from okf_tools.document import OKFDocument  # noqa: E402

_INDEX_FILE = "index.md"
_RESERVED = {"index.md", "log.md"}


def _load_doc(path: Path) -> OKFDocument | None:
    try:
        return OKFDocument.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _dir_summary(rel_path: str, children: list[tuple[str, str]]) -> str:
    """Deterministic one-line summary of a directory from its children's titles."""
    names = [t for t, _ in children if t]
    n = len(children)
    if not names:
        return f"{n} entries."
    shown = ", ".join(names[:3])
    more = f", and {len(names) - 3} more" if len(names) > 3 else ""
    return f"{n} entries: {shown}{more}."


def _build_index_text(entries: list[tuple[str, str, str, str]]) -> str:
    # entries: (type, title, relative_link, description)
    grouped: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for typ, title, link, desc in entries:
        grouped[typ or "Other"].append((title, link, desc))

    sections: list[str] = []
    for typ in sorted(grouped):
        lines = [f"# {typ}", ""]
        for title, link, desc in sorted(grouped[typ], key=lambda e: e[0].lower()):
            suffix = f" - {desc}" if desc else ""
            lines.append(f"* [{title}]({link}){suffix}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


def _directories_to_index(bundle_root: Path) -> list[Path]:
    dirs: set[Path] = set()
    for md in bundle_root.rglob("*.md"):
        cur = md.parent
        while cur != bundle_root.parent:
            dirs.add(cur)
            if cur == bundle_root:
                break
            cur = cur.parent
    return sorted(dirs)


def regenerate_indexes(
    bundle_root: Path,
    *,
    synthesize: Callable[[str, list[tuple[str, str]]], str] = _dir_summary,
    okf_version: str = "0.1",
    root_title: str | None = None,
) -> list[Path]:
    bundle_root = Path(bundle_root)
    written: list[Path] = []
    if not bundle_root.exists():
        return written

    # Deepest directories first, so each subdir's summary is known before its
    # parent's index is built.
    directories = sorted(
        _directories_to_index(bundle_root),
        key=lambda p: (-len(p.relative_to(bundle_root).parts), str(p)),
    )

    dir_descriptions: dict[Path, str] = {}

    for directory in directories:
        entries: list[tuple[str, str, str, str]] = []

        for child in sorted(directory.iterdir()):
            if child.is_file() and child.suffix == ".md" and child.name not in _RESERVED:
                doc = _load_doc(child)
                if doc is None:
                    continue
                fm = doc.frontmatter
                title = str(fm.get("title") or fm.get("phrase") or child.stem)
                desc = str(fm.get("description") or "")
                typ = str(fm.get("type") or "")
                entries.append((typ, title, child.name, desc))
            elif child.is_dir():
                desc = dir_descriptions.get(child, "")
                entries.append(
                    ("Subdirectories", child.name, f"{child.name}/{_INDEX_FILE}", desc)
                )

        if not entries:
            continue

        index_path = directory / _INDEX_FILE
        body = _build_index_text(entries)
        if directory == bundle_root:
            # The root index is the one place frontmatter is allowed; keep the
            # spec-version declaration and a title.
            title = root_title or bundle_root.resolve().name
            body = f'---\nokf_version: "{okf_version}"\n---\n\n# {title}\n\n' + body
        index_path.write_text(body, encoding="utf-8")
        written.append(index_path)

        if directory == bundle_root:
            continue

        pairs = [(title, desc) for _, title, _, desc in entries]
        if len(pairs) == 1 and pairs[0][1]:
            dir_descriptions[directory] = pairs[0][1]
        else:
            rel = str(directory.relative_to(bundle_root))
            dir_descriptions[directory] = synthesize(rel, pairs)

    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="okf-reindex",
        description="Regenerate index.md for every directory in an OKF bundle.",
    )
    p.add_argument("bundle", type=Path, help="Path to the bundle root directory.")
    args = p.parse_args(argv)
    written = regenerate_indexes(args.bundle)
    print(f"Wrote {len(written)} index.md file(s) in {args.bundle}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
