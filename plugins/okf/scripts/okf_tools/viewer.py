# SPDX-License-Identifier: Apache-2.0
# Adapted from the OKF reference agent (Google Cloud Knowledge Catalog),
# licensed under Apache License 2.0:
# https://github.com/GoogleCloudPlatform/knowledge-catalog
# Modifications for the okf Claude Code plugin:
#   - generic per-type color palette (not BigQuery-specific);
#   - link extraction resolves bundle-relative (/path.md) links, not just
#     doc-relative ones (OKF structure-patterns prefers absolute links);
#   - Cytoscape + marked are inlined from vendored copies -> the output HTML
#     is fully self-contained and offline/Artifact-safe (no CDN).
# See NOTICE.md in this directory.
"""Generate a single self-contained HTML graph view of an OKF bundle."""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from okf_tools.document import OKFDocument, OKFDocumentError  # noqa: E402

# Reserved files are not concepts and must not appear as graph nodes.
_RESERVED_NAMES = {"index.md", "log.md"}
_LINK_RE = re.compile(r"\]\(([^)\s]+\.md)(?:#[A-Za-z0-9_\-]*)?\)")

# A ring of visually distinct colors, assigned to types in sorted order so the
# same bundle always colors the same way. Works for any bundle, not just BQ.
_PALETTE_RING = [
    "#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4",
    "#ec4899", "#84cc16", "#6366f1", "#f97316", "#14b8a6", "#a855f7",
    "#eab308", "#0ea5e9", "#22c55e", "#f43f5e",
]
_DEFAULT_NODE_COLOR = "#94a3b8"


def _build_palette(types: list[str]) -> dict[str, str]:
    return {
        t: _PALETTE_RING[i % len(_PALETTE_RING)]
        for i, t in enumerate(sorted(types))
    }


@dataclass
class Concept:
    id: str
    type: str
    title: str
    description: str
    resource: str
    tags: list[str]
    body: str
    links_to: list[str] = field(default_factory=list)

    def to_node(self, palette: dict[str, str]) -> dict[str, Any]:
        color = palette.get(self.type, _DEFAULT_NODE_COLOR)
        return {
            "data": {
                "id": self.id,
                "label": self.title or self.id,
                "type": self.type,
                "description": self.description,
                "resource": self.resource,
                "tags": self.tags,
                "color": color,
                "size": 30 + min(60, len(self.body) // 200),
            }
        }


def _extract_links(body: str, doc_dir: Path, bundle_root: Path) -> list[str]:
    """Return the concept ids this body links to.

    Handles both OKF link styles: bundle-relative (`/glossary/Term.md`,
    resolved against the bundle root — OKF's preferred form) and doc-relative
    (`./sibling.md`). External (`https://…`) links are ignored.
    """
    out: list[str] = []
    seen: set[str] = set()
    root = bundle_root.resolve()
    for m in _LINK_RE.finditer(body):
        target = m.group(1)
        if "://" in target:
            continue
        try:
            if target.startswith("/"):
                resolved = (root / target.lstrip("/")).resolve().relative_to(root)
            else:
                resolved = (doc_dir / target).resolve().relative_to(root)
        except ValueError:
            continue
        rel = resolved.as_posix()
        if rel.endswith(".md"):
            rel = rel[:-3]
        if rel and rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def _walk_concepts(bundle_root: Path) -> list[Concept]:
    concepts: list[Concept] = []
    for md_path in sorted(bundle_root.rglob("*.md")):
        if md_path.name in _RESERVED_NAMES:
            continue
        rel = md_path.relative_to(bundle_root).with_suffix("")
        concept_id = "/".join(rel.parts)
        try:
            doc = OKFDocument.parse(md_path.read_text(encoding="utf-8"))
        except OKFDocumentError:
            continue
        fm = doc.frontmatter or {}
        tags = fm.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        concepts.append(
            Concept(
                id=concept_id,
                type=str(fm.get("type") or "Unknown"),
                title=str(fm.get("title") or fm.get("phrase") or rel.name),
                description=str(fm.get("description") or ""),
                resource=str(fm.get("resource") or ""),
                tags=[str(t) for t in tags],
                body=doc.body or "",
                links_to=_extract_links(doc.body or "", md_path.parent, bundle_root),
            )
        )
    return concepts


def _build_graph(concepts: list[Concept]) -> dict[str, Any]:
    ids = {c.id for c in concepts}
    types = sorted({c.type for c in concepts})
    palette = _build_palette(types)
    nodes = [c.to_node(palette) for c in concepts]
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    for c in concepts:
        for target in c.links_to:
            if target == c.id or target not in ids:
                continue
            key = (c.id, target)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({
                "data": {
                    "id": f"{c.id}__{target}",
                    "source": c.id,
                    "target": target,
                }
            })
    return {
        "nodes": nodes,
        "edges": edges,
        "bodies": {c.id: c.body for c in concepts},
        "types": types,
        "palette": palette,
    }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def generate_visualization(
    bundle_root: Path,
    out_path: Path,
    *,
    bundle_name: str | None = None,
) -> dict[str, int]:
    """Walk a bundle and write a single self-contained HTML visualization.

    Returns {'concepts': N, 'edges': M, 'bytes': K}.
    """
    bundle_root = Path(bundle_root)
    out_path = Path(out_path)
    if not bundle_root.is_dir():
        raise FileNotFoundError(f"Bundle directory not found: {bundle_root}")

    concepts = _walk_concepts(bundle_root)
    graph = _build_graph(concepts)

    template = _read(_HERE / "assets" / "viz.html")
    css = _read(_HERE / "assets" / "viz.css")
    js = _read(_HERE / "assets" / "viz.js")
    cytoscape_js = _read(_HERE / "vendor" / "cytoscape.min.js")
    marked_js = _read(_HERE / "vendor" / "marked.min.js")
    dompurify_js = _read(_HERE / "vendor" / "purify.min.js")
    name = bundle_name or bundle_root.resolve().name

    html = (
        template
        .replace("/*__CYTOSCAPE_JS__*/", cytoscape_js)
        .replace("/*__MARKED_JS__*/", marked_js)
        .replace("/*__DOMPURIFY_JS__*/", dompurify_js)
        .replace("/*__VIZ_CSS__*/", css)
        .replace("/*__VIZ_JS__*/", js)
        .replace("__BUNDLE_NAME__", json.dumps(name))
        .replace("__BUNDLE_DATA__", json.dumps(graph))
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    return {
        "concepts": len(concepts),
        "edges": len(graph["edges"]),
        "bytes": len(html.encode("utf-8")),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="okf-visualize",
        description="Generate a self-contained HTML graph view of an OKF bundle.",
    )
    p.add_argument("bundle", type=Path, help="Path to the bundle root directory.")
    p.add_argument(
        "--out", type=Path, default=None,
        help="Output HTML path (default: <bundle>/viz.html).",
    )
    p.add_argument(
        "--name", default=None,
        help="Display name for the bundle (default: bundle directory name).",
    )
    args = p.parse_args(argv)
    out = args.out or (args.bundle / "viz.html")
    stats = generate_visualization(args.bundle, out, bundle_name=args.name)
    print(
        f"Wrote {stats['concepts']} concept(s), {stats['edges']} edge(s), "
        f"{stats['bytes']} bytes -> {out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
