#!/usr/bin/env python3
"""package-change — write the hand-off bundle for ONE approved cds artifact.

The deterministic body of the `package-change` skill. Given the `output_path` of
one composer output (a Page HTML, a Shell, or a View), it finds the composer
state record whose `output_path` equals it, confirms the generated stylesheet
set is current, and writes one bundle holding that one artifact:

  <package-root>/<slug>-<UTC timestamp>/
    bundle.json            the machine-readable contract
    README.md              index + how-to-build note
    spec/build-spec.md     derived from the state record (Sections table)
    spec/decisions.md      copy of the composer's decision log
    spec/wireframe.txt     copy of the composer's wireframe
    design/<kind>.html     page.html | shell.html | view.html
    styles/                tokens.css components.css themes.css manifest.json
    assets/                the record's assets + artwork-manifest.yaml
    state/<record>.yaml    the state record, verbatim
    update/                only when mode == update

bundle.json:
  {"kind": "page"|"shell"|"view", "slug": str,
   "shell": {"name": str, "modified": bool} | null,
   "created_at": UTC ISO-8601, "build_spec": "spec/build-spec.md"}
`shell` is non-null only for a View.

Usage
-----
  package-change.py <target-output-path> [--package-root DIR] [--state-root DIR]

  target          the composer output's `output_path`
  --package-root  bundle root; default $CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR
  --state-root    a directory holding compose-page/ compose-shell/
                  compose-view/; repeatable. Default: the state directories
                  $CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE selects.

Exit status
-----------
  0  bundle written; its path is printed on stdout
  1  halt; a `STOP: package-change: <CODE>: ...` surface is printed on stderr
  2  usage or IO error
  3  the stylesheet set is stale or missing: run generate-css, then rerun
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))
import cds_hash  # noqa: E402

REFERENCE_DIR = PLUGIN_ROOT / "reference"
KINDS = {"compose-page": "page", "compose-shell": "shell", "compose-view": "view"}
STYLESHEETS = ("tokens.css", "components.css", "themes.css")
HASH_KEYS = (
    "elements_semantic_sha256",
    "reference_tree_sha256",
    "extensions_tree_sha256",
)
EXIT_HALT = 1
EXIT_USAGE = 2
EXIT_STALE = 3


class Halt(Exception):
    """A named halt condition from the skill's halt list."""

    def __init__(self, code: str, summary: str, detail: str, ref: str = "") -> None:
        """Hold the halt code, summary, detail and reference pointer."""
        super().__init__(code)
        self.code = code
        self.summary = summary
        self.detail = detail
        self.ref = ref or "skills/package-change/SKILL.md, Halt conditions"


class Stale(Exception):
    """The stylesheet set does not match the live input fingerprints."""


def env(name: str) -> str | None:
    """Return a non-empty environment variable, or None."""
    value = os.environ.get(name, "").strip()
    return value or None


# ---------------------------------------------------------------- discovery


def _project_state_root() -> Path | None:
    """Find <project-root>/.claude/customizable-design-system/state upward."""
    rel = Path(".claude/customizable-design-system/state")
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / rel).is_dir():
            return d / rel
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except OSError:
        top = ""
    if top and (Path(top) / rel).is_dir():
        return Path(top) / rel
    return None


def state_roots(explicit: list[str] | None) -> list[Path]:
    """The state roots to search, per --state-root or the install mode."""
    if explicit:
        return [Path(p).expanduser() for p in explicit]
    mode = (env("CUSTOMIZABLE_DESIGN_SYSTEM_INSTALL_MODE") or "").lower()
    global_root = Path.home() / ".claude/customizable-design-system/state"
    project_root = _project_state_root()
    roots: list[Path] = []
    if mode == "project":
        roots = [project_root] if project_root else []
    elif mode == "global":
        roots = [global_root]
    else:
        roots = [r for r in (project_root, global_root) if r]
    return roots


def _same_path(a: str, b: Path) -> bool:
    """Strict output_path equality, after resolving both paths."""
    try:
        return Path(a).expanduser().resolve() == b
    except (OSError, ValueError):
        return False


_OUTPUT_LINE = re.compile(r"^output_path:\s*['\"]?(.+?)['\"]?\s*(#.*)?$", re.M)


def find_record(target: Path, roots: list[Path]) -> tuple[Path, str, dict]:
    """Return (record path, composer, parsed record) for the target."""
    matches: list[tuple[Path, str, dict | None, str]] = []
    for root in roots:
        for composer in KINDS:
            folder = root / composer
            if not folder.is_dir():
                continue
            for f in sorted(folder.glob("*.y*ml")):
                text = f.read_text(encoding="utf-8")
                try:
                    data = yaml.safe_load(text)
                except yaml.YAMLError as e:
                    m = _OUTPUT_LINE.search(text)
                    if m and _same_path(m.group(1), target):
                        matches.append((f, composer, None, str(e).splitlines()[0]))
                    continue
                if isinstance(data, dict) and _same_path(
                    str(data.get("output_path", "")), target
                ):
                    matches.append((f, composer, data, ""))
    if not matches:
        searched = ", ".join(str(r) for r in roots) or "(no state root resolved)"
        raise Halt(
            "STATE_RECORD_NOT_FOUND",
            f"no state record has output_path {target}",
            f"Searched compose-page/, compose-shell/ and compose-view/ under: "
            f"{searched}. Package an output a composer wrote, or pass "
            f"--state-root.",
        )
    if len(matches) > 1:
        names = ", ".join(str(m[0]) for m in matches)
        raise Halt(
            "STATE_RECORD_AMBIGUOUS",
            f"{len(matches)} state records have output_path {target}",
            f"Records: {names}. One artifact has one state record; remove the "
            f"stale one and rerun.",
        )
    path, composer, data, err = matches[0]
    if data is None:
        raise Halt(
            "STATE_RECORD_UNREADABLE",
            f"the state record for {target} is not valid YAML",
            f"{path}: {err}. Fix the record (quote the offending value) and rerun.",
            ref=str(path),
        )
    return path, composer, data


# ------------------------------------------------------------------ fields


def view_shell(record: dict) -> dict[str, Any] | None:
    """The View's Shell as {name, modified}, read from any recorded shape.

    Order: a `shell` mapping, a plain-string `shell`, then the flat
    `shell_name` / `shell_modified` keys. A record that does not state
    `modified` gets False: compose-view never edits a stored Shell.
    """
    raw = record.get("shell")
    name: Any = None
    modified: Any = None
    if isinstance(raw, dict):
        name, modified = raw.get("name"), raw.get("modified")
    elif isinstance(raw, str):
        name = raw
    if not (isinstance(name, str) and name.strip()):
        name = record.get("shell_name")
    if modified is None:
        modified = record.get("shell_modified")
    if not (isinstance(name, str) and name.strip()):
        return None
    return {"name": name.strip(), "modified": modified is True}


def view_shell_path(record: dict, name: str) -> Path:
    """Where the View's stored Shell file lives."""
    raw = record.get("shell")
    for value in (
        raw.get("path") if isinstance(raw, dict) else None,
        record.get("shell_path"),
    ):
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser()
    shells = env("CUSTOMIZABLE_DESIGN_SYSTEM_SHELLS_DIR")
    if shells:
        return Path(shells) / f"{name}.html"
    mocks = env("CUSTOMIZABLE_DESIGN_SYSTEM_MOCKS_DIR") or "."
    return Path(mocks).parent / "shells" / f"{name}.html"


def sections(record: dict) -> list[dict]:
    """The recorded Sections, flattened, each with a unique stable ID."""
    raw = record.get("sections")
    rows: list[dict] = []
    if isinstance(raw, dict):
        for group, items in raw.items():
            for item in items or []:
                row = dict(item) if isinstance(item, dict) else {"section": item}
                row.setdefault("origin", group)
                rows.append(row)
    elif isinstance(raw, list):
        for item in raw:
            rows.append(dict(item) if isinstance(item, dict) else {"section": item})
    seen: set[str] = set()
    for n, row in enumerate(rows, 1):
        sid = str(row.get("id") or f"S{n}")
        if sid in seen:
            sid = f"{row.get('origin', 'section')}-{sid}"
        if sid in seen:
            sid = f"{sid}-{n}"
        seen.add(sid)
        row["id"] = sid
    return rows


def _text(value: Any) -> str:
    """One table-safe line for a recorded value."""
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        return ", ".join(_text(v) for v in value if v not in (None, ""))
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_text(v)}" for k, v in value.items())
    return " ".join(str(value).split()).replace("|", "\\|")


_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


def library_entry(kind: str, value: Any) -> str | None:
    """Plugin- or extension-relative path of a library entry, when one exists."""
    if not isinstance(value, str):
        return None
    m = _NAME.match(value.strip().lower())
    if not m:
        return None
    name = m.group(0)
    ext = env("CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR")
    if ext and (Path(ext) / kind / f"{name}.md").is_file():
        return f"$CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR/{kind}/{name}.md"
    if (REFERENCE_DIR / kind / f"{name}.md").is_file():
        return f"reference/{kind}/{name}.md"
    return None


def asset_paths(record: dict) -> list[Path]:
    """Every asset path the record names (strings or {path: ...} mappings)."""
    assets_dir = env("CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR")
    out: list[Path] = []
    for item in record.get("assets") or []:
        raw = item.get("path") if isinstance(item, dict) else item
        if not isinstance(raw, str) or not raw.strip():
            continue
        p = Path(raw).expanduser()
        if not p.is_absolute() and assets_dir:
            p = Path(assets_dir) / p
        if p not in out:
            out.append(p)
    return out


def sidecar(record: dict, key: str, artifact: Path, suffix: str) -> Path:
    """The recorded sidecar path, else the pipeline's default beside the artifact."""
    cars = record.get("sidecars")
    raw = cars.get(key) if isinstance(cars, dict) else None
    if isinstance(raw, str) and raw.strip():
        return Path(raw).expanduser()
    return artifact.with_name(artifact.stem + suffix)


# -------------------------------------------------------------- freshness


def check_stylesheets(styles_dir: Path) -> dict:
    """Return the manifest when the stylesheet set is current; else raise Stale."""
    elements = env("CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS")
    if not elements:
        raise Halt(
            "ELEMENTS_YAML_UNSET",
            "$CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS is not set",
            "Run /cds:setup to configure the elements YAML path.",
        )
    manifest_path = styles_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Stale(f"{manifest_path}: {e}") from e
    live = {
        "elements_semantic_sha256": cds_hash.semantic_hash(elements),
        "reference_tree_sha256": cds_hash.tree_hash(str(REFERENCE_DIR)),
        "extensions_tree_sha256": cds_hash.extensions_tree_hash(
            env("CUSTOMIZABLE_DESIGN_SYSTEM_EXTENSIONS_DIR") or "NONE"
        ),
    }
    moved = [k for k in HASH_KEYS if manifest.get(k) != live[k]]
    if moved:
        raise Stale(f"input fingerprints changed: {', '.join(moved)}")
    files = manifest.get("files") or {}
    for name in STYLESHEETS:
        sheet = styles_dir / name
        if not sheet.is_file():
            raise Stale(f"{sheet} is missing")
        want = files.get(name)
        if want and cds_hash._sha256_hex(sheet.read_bytes()) != want:
            raise Stale(f"{sheet} does not match manifest.json")
    return manifest


# ----------------------------------------------------------------- writing


def build_spec(
    kind: str,
    slug: str,
    record: dict,
    record_path: Path,
    artifact: Path,
    shell: dict | None,
    shell_path: Path | None,
) -> str:
    """The developer-agent build spec, derived from the state record."""
    page = record.get("page") if isinstance(record.get("page"), dict) else {}
    family = record.get("page_family") or page.get("page_family")
    lines = [
        f"# Build spec — {slug}",
        "",
        f"- Artifact kind: {kind}",
        f"- Design artifact: `design/{kind}.html` (from `{artifact}`)",
        f"- State record: `state/{record_path.name}`",
        f"- Run mode: {record.get('mode') or 'generate'}",
    ]
    if family:
        lines.append(f"- Page family: {_text(family)}")
    if shell is not None:
        lines.append(f"- Shell: {shell['name']} (`{shell_path}`)")
        lines.append(
            f"- Shell modified by this View: {'yes' if shell['modified'] else 'no'}"
        )
        page_path = page.get("path") or record.get("page_path")
        if not page_path and isinstance(record.get("page_paths"), list):
            page_path = ", ".join(map(str, record["page_paths"]))
        if page_path:
            lines.append(f"- Page nested in the Shell: `{page_path}`")
    brief = _text(record.get("brief_snapshot"))
    if brief:
        lines += ["", "## Brief", "", brief]

    rows = sections(record)
    lines += [
        "",
        "## Sections",
        "",
        "Section IDs are stable: cite them as `<slug>#<Section ID>`.",
        "",
        "| Section ID | Origin | Section | Shape | Components | Ground | Resolution |",
        "|---|---|---|---|---|---|---|",
    ]
    cited: dict[str, set[str]] = {
        "libraries/sections": set(),
        "libraries/shapes": set(),
        "libraries/components": set(),
        "libraries/pages": set(),
        "rules/shape-selection": set(),
        "rules/page-constraints": set(),
    }
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["id"],
                    _text(row.get("origin") or row.get("source")),
                    _text(row.get("section")),
                    _text(row.get("shape")),
                    _text(row.get("components")),
                    _text(row.get("ground") or row.get("theme")),
                    _text(row.get("resolution_rung") or row.get("rung")),
                ]
            )
            + " |"
        )
        for kind_dir, value in (
            ("libraries/sections", row.get("section")),
            ("libraries/shapes", row.get("shape")),
            ("libraries/shapes", row.get("base_shape")),
            ("rules/shape-selection", row.get("rule_fired") or row.get("rule")),
        ):
            entry = library_entry(kind_dir, value)
            if entry:
                cited[kind_dir].add(entry)
        for comp in row.get("components") or []:
            entry = library_entry("libraries/components", comp)
            if entry:
                cited["libraries/components"].add(entry)
    for comp in record.get("components_used") or []:
        entry = library_entry("libraries/components", comp)
        if entry:
            cited["libraries/components"].add(entry)
    for rule in record.get("page_constraints_applied") or []:
        entry = library_entry("rules/page-constraints", rule)
        if entry:
            cited["rules/page-constraints"].add(entry)
    for value in (record.get("library_entry"), page.get("library_entry")):
        entry = library_entry("libraries/pages", value)
        if entry:
            cited["libraries/pages"].add(entry)

    lines += [
        "",
        "## Library entries applied",
        "",
        "Paths are relative to the cds plugin root unless they name the "
        "extensions directory. Each Component entry carries its markup, ARIA "
        "and token contract; build to the entry, not to a restatement of it.",
        "",
    ]
    any_cited = False
    for kind_dir, entries in cited.items():
        for entry in sorted(entries):
            lines.append(f"- {kind_dir}: `{entry}`")
            any_cited = True
    if not any_cited:
        lines.append("- No recorded name resolves to a library entry.")
    lines += [
        "- compliance: `reference/compliance.md`",
        "",
        "## Token and class contract",
        "",
        "Style only with the classes and custom properties the stylesheets in "
        "`styles/` ship; `styles/manifest.json` fingerprints them. "
        "`design/` shows the approved result and is the visual reference.",
        "",
    ]
    return "\n".join(lines)


def readme(kind: str, slug: str, has_update: bool, n_assets: int) -> str:
    """The bundle README: index plus a how-to-build note."""
    lines = [
        f"# cds hand-off bundle — {slug} ({kind})",
        "",
        "One approved artifact. `bundle.json` is the machine-readable contract.",
        "",
        "| Path | Holds |",
        "|---|---|",
        "| `bundle.json` | kind, slug, Shell (Views only), created_at, build spec path |",
        "| `spec/build-spec.md` | the build spec, with the stable Section IDs |",
        "| `spec/decisions.md` | the composer's decision log |",
        "| `spec/wireframe.txt` | the composer's wireframe |",
        f"| `design/{kind}.html` | the approved self-contained HTML artifact |",
        "| `styles/` | tokens.css, components.css, themes.css, manifest.json |",
        f"| `assets/` | {n_assets} asset file(s), plus artwork-manifest.yaml when present |",
        "| `state/` | the composer state record |",
    ]
    if has_update:
        lines.append(
            "| `update/` | `original/` snapshot and `change.diff` for a scoped update |"
        )
    lines += [
        "",
        "## How the app-repo agent builds this",
        "",
        "1. Read `spec/build-spec.md`; build each Section in its table, citing "
        "its Section ID.",
        "2. Use only the classes and custom properties in `styles/`; serve "
        "`assets/` from the same server as the page.",
        f"3. Match `design/{kind}.html` visually; `spec/decisions.md` explains "
        "each choice.",
    ]
    if has_update:
        lines.append(
            "4. Apply `update/change.diff` as a scoped change to the files in "
            "`update/original/`; do not rebuild from scratch."
        )
    return "\n".join(lines) + "\n"


def copy_file(src: Path, dst: Path, missing_code: str, what: str) -> None:
    """Copy one file, halting with missing_code when the source is absent."""
    if not src.is_file():
        raise Halt(
            missing_code, f"{what} not found: {src}", f"Expected {what} at {src}."
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def package(target: Path, package_root: Path, roots: list[Path]) -> Path:
    """Write the bundle for target; return the bundle directory."""
    record_path, composer, record = find_record(target, roots)
    kind = KINDS[composer]
    if not target.is_file():
        raise Halt(
            "TARGET_UNREADABLE",
            f"the artifact {target} cannot be read",
            "The state record names an artifact that is not on disk.",
        )

    shell = None
    shell_path = None
    if kind == "view":
        shell = view_shell(record)
        if shell is None:
            raise Halt(
                "VIEW_SHELL_UNRESOLVED",
                f"the View's state record names no Shell: {record_path}",
                "A View nests a Page in a stored Shell. Record it as "
                "`shell: {name: <stored shell name>, modified: <bool>}` "
                "(compose-view state record format) and rerun.",
                ref=str(record_path),
            )
        shell_path = view_shell_path(record, shell["name"])

    rows = sections(record)
    if not rows:
        raise Halt(
            "SECTIONS_UNRECORDED",
            f"the state record records no Sections: {record_path}",
            "The build spec's Sections table needs the resolved Sections. "
            "Iterate the artifact with its composer so the record carries them.",
            ref=str(record_path),
        )

    styles_dir = Path(
        env("CUSTOMIZABLE_DESIGN_SYSTEM_STYLESHEETS_DIR")
        or REFERENCE_DIR.parent / "stylesheets"
    )
    check_stylesheets(styles_dir)

    wireframe = sidecar(record, "wireframe", target, ".wireframe.txt")
    decisions = sidecar(record, "decisions", target, ".decisions.md")
    assets = asset_paths(record)
    for a in assets:
        if not a.is_file():
            raise Halt(
                "ASSETS_UNRESOLVABLE",
                f"asset not found: {a}",
                f"The state record {record_path} names {a}, which is not on disk.",
            )

    mode = record.get("mode") or "generate"
    update_sources: list[Path] = []
    if mode == "update":
        raw = record.get("update_source")
        raw_list = raw if isinstance(raw, list) else [raw]
        update_sources = [
            Path(str(s)).expanduser() for s in raw_list if isinstance(s, str) and s
        ]
        if not update_sources or not all(p.is_file() for p in update_sources):
            raise Halt(
                "UPDATE_SOURCE_UNRESOLVABLE",
                "mode is update but update_source is not a readable file",
                f"{record_path} records update_source {raw!r}. An update bundle "
                f"ships the original files; record them and rerun.",
                ref=str(record_path),
            )

    slug = target.stem
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    bundle = package_root / f"{slug}-{now.strftime('%Y%m%dT%H%M%SZ')}"
    if bundle.exists():
        raise Halt(
            "OUTPUT_PATH_UNRESOLVABLE",
            f"bundle directory already exists: {bundle}",
            "Rerun after a second; bundle names carry a UTC timestamp.",
        )
    try:
        bundle.mkdir(parents=True)
        copy_file(
            wireframe,
            bundle / "spec/wireframe.txt",
            "SIDECAR_UNRESOLVABLE",
            "wireframe sidecar",
        )
        copy_file(
            decisions,
            bundle / "spec/decisions.md",
            "SIDECAR_UNRESOLVABLE",
            "decisions sidecar",
        )
        copy_file(
            target, bundle / f"design/{kind}.html", "TARGET_UNREADABLE", "artifact"
        )
        for name in (*STYLESHEETS, "manifest.json"):
            copy_file(
                styles_dir / name,
                bundle / "styles" / name,
                "STYLESHEETS_REGEN_FAILED:MISSING",
                "stylesheet",
            )
        (bundle / "assets").mkdir()
        for a in assets:
            shutil.copy2(a, bundle / "assets" / a.name)
        assets_dir = env("CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR")
        art = Path(assets_dir) / "artwork-manifest.yaml" if assets_dir else None
        if art and art.is_file():
            shutil.copy2(art, bundle / "assets/artwork-manifest.yaml")
        copy_file(
            record_path,
            bundle / "state" / record_path.name,
            "STATE_RECORD_NOT_FOUND",
            "state record",
        )
        if update_sources:
            original = bundle / "update/original"
            original.mkdir(parents=True)
            diff: list[str] = []
            for src in update_sources:
                shutil.copy2(src, original / src.name)
                diff += difflib.unified_diff(
                    src.read_text(encoding="utf-8").splitlines(keepends=True),
                    target.read_text(encoding="utf-8").splitlines(keepends=True),
                    fromfile=f"original/{src.name}",
                    tofile=f"design/{kind}.html",
                )
            (bundle / "update/change.diff").write_text("".join(diff), encoding="utf-8")
        (bundle / "spec/build-spec.md").write_text(
            build_spec(kind, slug, record, record_path, target, shell, shell_path),
            encoding="utf-8",
        )
        (bundle / "README.md").write_text(
            readme(kind, slug, bool(update_sources), len(assets)), encoding="utf-8"
        )
        contract = {
            "kind": kind,
            "slug": slug,
            "shell": shell,
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "build_spec": "spec/build-spec.md",
        }
        (bundle / "bundle.json").write_text(
            json.dumps(contract, indent=2) + "\n", encoding="utf-8"
        )
    except BaseException:
        shutil.rmtree(bundle, ignore_errors=True)
        raise
    return bundle


def main(argv: list[str]) -> int:
    """Parse arguments, write the bundle, and map outcomes to exit codes."""
    ap = argparse.ArgumentParser(prog="package-change.py", add_help=True)
    ap.add_argument("target")
    ap.add_argument("--package-root")
    ap.add_argument("--state-root", action="append")
    args = ap.parse_args(argv)

    root = args.package_root or env("CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR")
    try:
        if not root:
            raise Halt(
                "OUTPUT_PATH_UNRESOLVABLE",
                "no bundle root",
                "Pass --package-root or set $CUSTOMIZABLE_DESIGN_SYSTEM_PACKAGE_DIR.",
            )
        target = Path(args.target).expanduser().resolve()
        bundle = package(target, Path(root).expanduser(), state_roots(args.state_root))
    except Halt as h:
        print(
            f"STOP: package-change: {h.code}: {h.summary}\n\n"
            f"Reference: {h.ref}\nDetail: {h.detail}",
            file=sys.stderr,
        )
        return EXIT_HALT
    except Stale as s:
        print(f"STYLESHEETS_STALE: {s}", file=sys.stderr)
        return EXIT_STALE
    except (OSError, yaml.YAMLError) as e:
        print(f"package-change: {e}", file=sys.stderr)
        return EXIT_USAGE
    print(bundle)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
