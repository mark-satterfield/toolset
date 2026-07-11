"""OKF Sync — reconcile a bundle against its source tree(s).

Deterministic core: expand env-var source paths, hash sources, and diff them
against per-concept provenance (`source_path`, `source_sha`). Applies the
mechanical actions — adopt / stamp / remove / tombstone — and emits a JSON plan.
Converting new and changed source files into concepts needs judgment and is the
`okf-sync` agent's job; this module does everything that does not.

See design/okf-sync.md for the full spec.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from okf_tools.document import OKFDocument  # noqa: E402

PROVENANCE_KEYS = ("source_path", "source_sha", "timestamp")
_RESERVED = {"index.md", "log.md"}
_ENV_RE = re.compile(r"\$\{(\w+)\}|\$(\w+)")

# Convertible source extensions (mirrors what the converter handles). Used only
# to bound "new" detection when scanning a source tree.
_CONVERTIBLE = {
    ".md", ".markdown", ".txt", ".csv",
    ".pdf", ".docx", ".xlsx", ".pptx", ".mmd", ".gdoc",
}
# Directory names and files that are never bundle sources (Obsidian tooling etc.).
_EXCLUDE_DIRS = {".space", "_Views", ".obsidian", ".git"}
_EXCLUDE_NAMES = {".DS_Store", ".DS_Store 2", "def.json"}
_EXCLUDE_SUFFIXES = {".mdb"}


# --------------------------------------------------------------------------- #
# env-var source paths
# --------------------------------------------------------------------------- #
def referenced_vars(source_path: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in _ENV_RE.finditer(source_path)]


def expand_env_path(source_path: str, env: dict | None = None) -> str | None:
    """Expand $VAR / ${VAR}. Returns None if any referenced var is unset."""
    env = os.environ if env is None else env
    missing: list[str] = []

    def repl(m: re.Match) -> str:
        name = m.group(1) or m.group(2)
        val = env.get(name)
        if val is None:
            missing.append(name)
            return m.group(0)
        return val

    out = _ENV_RE.sub(repl, source_path)
    return None if missing else out


def to_env_path(abs_path: str, roots: dict[str, str]) -> str:
    """Rewrite an absolute path to `$VAR/rel` using the longest matching root."""
    absn = os.path.normpath(abs_path)
    best: tuple[str, str] | None = None
    for var, root in roots.items():
        rootn = os.path.normpath(root)
        if absn == rootn or absn.startswith(rootn + os.sep):
            if best is None or len(rootn) > len(best[1]):
                best = (var, rootn)
    if best is None:
        return abs_path
    var, rootn = best
    rel = os.path.relpath(absn, rootn)
    return f"${var}/{rel}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _included(path: Path) -> bool:
    if path.name in _EXCLUDE_NAMES or path.suffix in _EXCLUDE_SUFFIXES:
        return False
    if any(part in _EXCLUDE_DIRS for part in path.parts):
        return False
    return path.suffix.lower() in _CONVERTIBLE


# --------------------------------------------------------------------------- #
# concept + provenance loading
# --------------------------------------------------------------------------- #
@dataclass
class ConceptRec:
    concept_id: str
    rel_path: str            # bundle-relative posix path
    source_path: str | None  # env-var form, as stored
    source_sha: str | None


def load_concepts(bundle_root: Path) -> list[ConceptRec]:
    out: list[ConceptRec] = []
    for md in sorted(bundle_root.rglob("*.md")):
        if md.name in _RESERVED:
            continue
        try:
            doc = OKFDocument.parse(md.read_text(encoding="utf-8"))
        except Exception:
            continue
        fm = doc.frontmatter or {}
        rel = md.relative_to(bundle_root)
        out.append(
            ConceptRec(
                concept_id="/".join(rel.with_suffix("").parts),
                rel_path=rel.as_posix(),
                source_path=fm.get("source_path"),
                source_sha=fm.get("source_sha"),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# planning
# --------------------------------------------------------------------------- #
@dataclass
class SyncPlan:
    var: str
    root: str
    new: list[str] = field(default_factory=list)         # env-form source paths
    changed: list[dict] = field(default_factory=list)    # {concept, source_path}
    deleted: list[dict] = field(default_factory=list)     # {concept, source_path}
    unchanged: list[str] = field(default_factory=list)    # concept ids
    adoptable: list[dict] = field(default_factory=list)   # {concept, source_path}


def build_plan(bundle_root: Path, var: str, root: str) -> SyncPlan:
    """Reconcile concepts under a single source root (VAR -> absolute root)."""
    bundle_root = Path(bundle_root)
    root_abs = os.path.normpath(root)
    roots = {var: root_abs}
    plan = SyncPlan(var=var, root=root_abs)

    concepts = load_concepts(bundle_root)
    tracked: dict[str, ConceptRec] = {}   # expanded abs source path -> concept
    for c in concepts:
        if not c.source_path:
            continue
        exp = expand_env_path(c.source_path, {var: root_abs})
        if exp is not None:
            tracked[os.path.normpath(exp)] = c

    # Scan the source tree once.
    source_files: dict[str, Path] = {}    # abs -> path
    root_path = Path(root_abs)
    if root_path.is_dir():
        for f in root_path.rglob("*"):
            if f.is_file() and _included(f):
                source_files[os.path.normpath(str(f))] = f

    # Classify source files.
    concept_by_relpath = {c.rel_path: c for c in concepts}
    for abs_path, f in sorted(source_files.items()):
        env_path = to_env_path(abs_path, roots)
        if abs_path in tracked:
            c = tracked[abs_path]
            if c.source_sha == sha256_file(f):
                plan.unchanged.append(c.concept_id)
            else:
                plan.changed.append({"concept": c.concept_id, "source_path": env_path})
        else:
            # No provenance points here. Bootstrap: a concept mirroring this
            # source path (same relative path, .md) can be adopted; otherwise new.
            rel = os.path.relpath(abs_path, root_abs)
            mirror = Path(rel).with_suffix(".md").as_posix()
            c = concept_by_relpath.get(mirror)
            if c is not None and not c.source_path:
                plan.adoptable.append({"concept": c.concept_id, "source_path": env_path})
            else:
                plan.new.append(env_path)

    # Deleted: tracked concepts whose source no longer exists.
    for abs_path, c in sorted(tracked.items(), key=lambda kv: kv[1].concept_id):
        if abs_path not in source_files:
            plan.deleted.append(
                {"concept": c.concept_id, "source_path": c.source_path}
            )

    return plan


# --------------------------------------------------------------------------- #
# mutations
# --------------------------------------------------------------------------- #
def _concept_path(bundle_root: Path, concept_id: str) -> Path:
    return bundle_root.joinpath(*concept_id.split("/")).with_suffix(".md")


def stamp_provenance(
    bundle_root: Path, concept_id: str, source_path_env: str, sha: str
) -> None:
    """Add/refresh provenance frontmatter, preserving all other content."""
    path = _concept_path(bundle_root, concept_id)
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    doc.frontmatter["source_path"] = source_path_env
    doc.frontmatter["source_sha"] = sha
    doc.frontmatter["timestamp"] = now_iso()
    path.write_text(doc.serialize(), encoding="utf-8")


def remove_concept(bundle_root: Path, concept_id: str) -> None:
    _concept_path(bundle_root, concept_id).unlink(missing_ok=True)


def tombstone_concept(bundle_root: Path, concept_id: str) -> None:
    """Rewrite a concept to a Deprecated stub, keeping title/id for inbound links."""
    path = _concept_path(bundle_root, concept_id)
    doc = OKFDocument.parse(path.read_text(encoding="utf-8"))
    title = doc.frontmatter.get("title") or doc.frontmatter.get("phrase") or path.stem
    date = now_iso()[:10]
    # Deliberately drop provenance: a tombstone is a permanent stub, no longer
    # source-tracked, so future syncs leave it alone (like a hand-authored note).
    fm = {
        "type": "Deprecated",
        "title": title,
        "description": f"Source removed on {date}; kept as a tombstone.",
        "timestamp": now_iso(),
    }
    body = f"# {title}\n\nThe source for this concept was removed on {date}. " \
           "This stub remains so existing links resolve.\n"
    path.write_text(OKFDocument(frontmatter=fm, body=body).serialize(), encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_root(spec: str) -> tuple[str, str]:
    """Parse VAR=/abs/path, or a bare VAR (resolved from the environment)."""
    if "=" in spec:
        var, path = spec.split("=", 1)
        return var, os.path.expanduser(path)
    val = os.environ.get(spec)
    if val is None:
        raise SystemExit(f"Env var ${spec} is not set (needed to resolve source paths).")
    return spec, val


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="okf-sync", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("plan", "adopt"):
        sp = sub.add_parser(name)
        sp.add_argument("bundle", type=Path)
        sp.add_argument("--source-root", required=True,
                        help="VAR=/abs/path, or a bare VAR resolved from the environment.")

    dp = sub.add_parser("apply-deletions")
    dp.add_argument("bundle", type=Path)
    dp.add_argument("--source-root", required=True)
    dp.add_argument("--tombstone", action="store_true")

    args = p.parse_args(argv)
    var, root = _parse_root(args.source_root)
    plan = build_plan(args.bundle, var, root)

    if args.cmd == "plan":
        print(json.dumps({
            "var": plan.var, "root": plan.root,
            "new": plan.new, "changed": plan.changed, "deleted": plan.deleted,
            "unchanged": plan.unchanged, "adoptable": plan.adoptable,
        }, indent=2))
        return 0

    if args.cmd == "adopt":
        n = 0
        for item in plan.adoptable:
            src = expand_env_path(item["source_path"], {var: root})
            stamp_provenance(
                args.bundle, item["concept"], item["source_path"], sha256_file(Path(src))
            )
            n += 1
        print(f"Adopted (stamped provenance on) {n} concept(s).", file=sys.stderr)
        return 0

    if args.cmd == "apply-deletions":
        n = 0
        for item in plan.deleted:
            if args.tombstone:
                tombstone_concept(args.bundle, item["concept"])
            else:
                remove_concept(args.bundle, item["concept"])
            n += 1
        verb = "tombstoned" if args.tombstone else "removed"
        print(f"{verb.capitalize()} {n} deleted concept(s).", file=sys.stderr)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
