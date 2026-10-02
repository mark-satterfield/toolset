"""The single-artifact cds bundles the owner supplied, read from the packages directory.

The host passes the pipeline one packages directory (`designSystem.packagesDir`). It holds zero
or more cds bundles, each a directory `<change-slug>-<timestamp>/` that packages exactly one
artifact (a Page, a Shell or a View) with its own `styles/`, `spec/build-spec.md`,
`design/<kind>.html` and a `bundle.json`:

    {"kind": "page" | "shell" | "view", "slug": str, "shell": {"name", "modified"} | null,
     "created_at": ISO-8601 UTC, "build_spec": "spec/build-spec.md"}

A directory without a readable `bundle.json` is not a bundle and is listed under `ignored`.
When several bundles package the same kind and slug, the one with the newest `created_at` is
the supplied one; the others are listed under `superseded`.

A ui delta item takes one design source:

- `bundle`: a supplied bundle packages the item; it is cited and audited against.
- `cds`: the item changes design and no bundle packages it; it is designed with the CDS
  design system and audited against the live design system.
- `none`: the item changes no design (copy, or data wired into an existing element); it
  is built like any other code change.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

#: The kinds of artifact a bundle packages.
KINDS = ("page", "shell", "view")

#: The design sources a ui delta item, and a web-ui Task, takes.
DESIGN_SOURCES = ("bundle", "cds", "none")

#: The file that marks a directory as a bundle.
BUNDLE_FILE = "bundle.json"


def _created(value: object) -> datetime | None:
    """Return an ISO-8601 timestamp as an aware datetime, or None when it is not one.

    Args:
        value: The `created_at` value.

    Returns:
        The datetime, or None.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else None


def read_bundle(path: Path) -> dict | None:
    """Return a bundle's facts, or None when the directory holds no usable `bundle.json`.

    Args:
        path: The bundle directory.

    Returns:
        `path`, `kind`, `slug`, `shell`, `createdAt`, `buildSpec` (absolute), `design`
        (absolute `design/<kind>.html`) and `styles` (absolute `styles/`), or None.
    """
    marker = path / BUNDLE_FILE
    if not marker.is_file():
        return None
    try:
        body = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(body, dict):
        return None
    kind = str(body.get("kind") or "").strip()
    slug = str(body.get("slug") or "").strip()
    spec = str(body.get("build_spec") or "").strip()
    created = _created(body.get("created_at"))
    if kind not in KINDS or not slug or not spec or created is None:
        return None
    root = path.resolve()
    build_spec = (root / spec).resolve()
    if not build_spec.is_relative_to(root):
        return None
    shell = body.get("shell") if isinstance(body.get("shell"), dict) else None
    return {
        "path": str(root),
        "kind": kind,
        "slug": slug,
        "shell": shell,
        "createdAt": created.astimezone(timezone.utc).isoformat(),
        "buildSpec": str(build_spec),
        "buildSpecExists": build_spec.is_file(),
        "design": str(root / "design" / f"{kind}.html"),
        "styles": str(root / "styles"),
    }


def list_bundles(packages_dir: str | Path | None) -> dict:
    """Return the supplied bundles in a packages directory, newest per kind and slug.

    An absent, empty or unset directory supplies no bundle.

    Args:
        packages_dir: The packages directory, or None.

    Returns:
        `packagesDir`, `bundles` (the supplied ones, by kind then slug), `superseded`
        (older bundles of a kind and slug) and `ignored` (directories with no usable
        `bundle.json`).
    """
    text = str(packages_dir or "").strip()
    root = Path(text).expanduser().resolve() if text else None
    out: dict = {
        "packagesDir": str(root) if root else None,
        "bundles": [],
        "superseded": [],
        "ignored": [],
    }
    if root is None or not root.is_dir():
        return out
    newest: dict[tuple[str, str], dict] = {}
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        bundle = read_bundle(child)
        if bundle is None:
            out["ignored"].append(str(child))
            continue
        key = (bundle["kind"], bundle["slug"])
        held = newest.get(key)
        if held is None or bundle["createdAt"] > held["createdAt"]:
            if held is not None:
                out["superseded"].append(held["path"])
            newest[key] = bundle
        else:
            out["superseded"].append(bundle["path"])
    out["bundles"] = [newest[k] for k in sorted(newest)]
    return out


def bundle_problem(bundle_dir: str, build_spec: str | None) -> str | None:
    """Return why a cited bundle and build spec cannot be built from, or None when they can.

    The bundle must hold a usable `bundle.json`, be the newest bundle of its kind and slug
    in its packages directory, and the build spec must be the one its `bundle.json` names,
    present on disk.

    Args:
        bundle_dir: The cited bundle directory.
        build_spec: The cited build spec, or None to check the bundle alone.

    Returns:
        The problem, or None.
    """
    if not bundle_dir or not Path(bundle_dir).is_absolute():
        return f"the bundle {bundle_dir or '(none)'} is not an absolute path"
    path = Path(bundle_dir).resolve()
    bundle = read_bundle(path)
    if bundle is None:
        return f"{path} holds no usable {BUNDLE_FILE}"
    supplied = next(
        (
            b
            for b in list_bundles(path.parent)["bundles"]
            if (b["kind"], b["slug"]) == (bundle["kind"], bundle["slug"])
        ),
        None,
    )
    if supplied and supplied["path"] != bundle["path"]:
        return (
            f"{path} is superseded by the newer bundle of {bundle['kind']} "
            f"{bundle['slug']}: {supplied['path']}"
        )
    if build_spec is None:
        return None
    if Path(build_spec).resolve() != Path(bundle["buildSpec"]):
        return f"{build_spec} is not the build spec {path}/{BUNDLE_FILE} names ({bundle['buildSpec']})"
    if not bundle["buildSpecExists"]:
        return f"the build spec {bundle['buildSpec']} does not exist"
    return None
