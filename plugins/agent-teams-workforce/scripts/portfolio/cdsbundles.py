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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import beadcontracts
from beadcontracts import BuildSelection, Bundle, BundleListing, DesignArtifact
from contracts import JsonObject, JsonValue, json_object
from typeguard import CollectionCheckStrategy, check_type, typechecked

#: The kinds of artifact a bundle packages.
_ARGUMENT_ERROR: str = "Arguments violate the cdsbundles input contract"


KINDS = ("page", "shell", "view")

#: The design sources a ui delta item, and a web-ui Task, takes.
DESIGN_SOURCES = ("bundle", "cds", "none")

#: The file that marks a directory as a bundle.
BUNDLE_FILE = "bundle.json"


def _created(value: JsonValue) -> datetime | None:
    """Return an ISO-8601 timestamp as an aware datetime, or None when it is not one.

    Args:
        value: The `created_at` value.

    Returns:
        The datetime, or None.

    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp: datetime = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return stamp if stamp.tzinfo else None


@dataclass(frozen=True)
class _BundleManifest:
    kind: Literal["page", "shell", "view"]
    slug: str
    build_spec: str
    created: datetime
    shell: JsonObject | None

    def __post_init__(self) -> None:
        if self.kind not in KINDS or not isinstance(self.slug, str) or not isinstance(self.build_spec, str):
            raise TypeError(_ARGUMENT_ERROR)
        if not isinstance(self.created, datetime):
            raise TypeError(_ARGUMENT_ERROR)
        check_type(self.shell, JsonObject | None, collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _manifest(body: JsonObject) -> _BundleManifest | None:
    kind: JsonValue = body.get("kind")
    slug: JsonValue = body.get("slug")
    spec: JsonValue = body.get("build_spec")
    created: datetime | None = _created(body.get("created_at"))
    if not isinstance(kind, str) or not isinstance(slug, str) or not isinstance(spec, str):
        return None
    if kind.strip() not in KINDS or not slug.strip() or not spec.strip() or created is None:
        return None
    shell: JsonObject | None = json_object(body["shell"]) if isinstance(body.get("shell"), dict) else None
    return _BundleManifest(
        check_type(kind.strip(), Literal["page", "shell", "view"]),
        slug.strip(),
        spec.strip(),
        created,
        shell,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_bundle(path: Path) -> Bundle | None:
    """Return a bundle's facts, or None when the directory holds no usable `bundle.json`.

    Args:
        path: The bundle directory.

    Returns:
        `path`, `kind`, `slug`, `shell`, `createdAt`, `buildSpec` (absolute), `design`
        (absolute `design/<kind>.html`) and `styles` (absolute `styles/`), or None.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(path, Path)):
        raise TypeError(_ARGUMENT_ERROR)
    marker: Path = path / BUNDLE_FILE
    if not marker.is_file():
        return None
    try:
        body: object = json.loads(marker.read_text(encoding="utf-8"))
    except OSError, UnicodeDecodeError, ValueError:
        return None
    if not isinstance(body, dict):
        return None
    manifest: _BundleManifest | None = _manifest(json_object(body))
    if manifest is None:
        return None
    root: Path = path.resolve()
    build_spec: Path = (root / manifest.build_spec).resolve()
    if not build_spec.is_relative_to(root):
        return None
    return {
        "path": str(root),
        "kind": manifest.kind,
        "slug": manifest.slug,
        "shell": manifest.shell,
        "createdAt": manifest.created.astimezone(UTC).isoformat(),
        "buildSpec": str(build_spec),
        "buildSpecExists": build_spec.is_file(),
        "design": str(root / "design" / f"{manifest.kind}.html"),
        "styles": str(root / "styles"),
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def list_bundles(packages_dir: str | Path | None) -> BundleListing:
    """Return the supplied bundles in a packages directory, newest per kind and slug.

    An absent, empty or unset directory supplies no bundle.

    Args:
        packages_dir: The packages directory, or None.

    Returns:
        `packagesDir`, `bundles` (the supplied ones, by kind then slug), `superseded`
        (older bundles of a kind and slug) and `ignored` (directories with no usable
        `bundle.json`).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    child: Path
    if not (isinstance(packages_dir, (str, Path)) or packages_dir is None):
        raise TypeError(_ARGUMENT_ERROR)
    text: str = str(packages_dir or "").strip()
    root: Path | None = Path(text).expanduser().resolve() if text else None
    out: BundleListing = {
        "packagesDir": str(root) if root else None,
        "bundles": [],
        "superseded": [],
        "ignored": [],
    }
    if root is None or not root.is_dir():
        return out
    newest: dict[tuple[str, str], Bundle] = {}
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        bundle: beadcontracts.Bundle | None = read_bundle(child)
        if bundle is None:
            out["ignored"].append(str(child))
            continue
        key: tuple[str, str] = (bundle["kind"], bundle["slug"])
        held: beadcontracts.Bundle | None = newest.get(key)
        if held is None or bundle["createdAt"] > held["createdAt"]:
            if held is not None:
                out["superseded"].append(held["path"])
            newest[key] = bundle
        else:
            out["superseded"].append(bundle["path"])
    out["bundles"] = [newest[k] for k in sorted(newest)]
    return out


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
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

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(bundle_dir, str)) or not (isinstance(build_spec, str) or build_spec is None):
        raise TypeError(_ARGUMENT_ERROR)
    if not bundle_dir or not Path(bundle_dir).is_absolute():
        return f"the bundle {bundle_dir or '(none)'} is not an absolute path"
    path: Path = Path(bundle_dir).resolve()
    bundle: beadcontracts.Bundle | None = read_bundle(path)
    if bundle is None:
        return f"{path} holds no usable {BUNDLE_FILE}"
    supplied: beadcontracts.Bundle | None = next(
        (b for b in list_bundles(path.parent)["bundles"] if (b["kind"], b["slug"]) == (bundle["kind"], bundle["slug"])),
        None,
    )
    if supplied and supplied["path"] != bundle["path"]:
        return f"{path} is superseded by the newer bundle of {bundle['kind']} {bundle['slug']}: {supplied['path']}"
    if build_spec is not None and Path(build_spec).resolve() != Path(bundle["buildSpec"]):
        return f"{build_spec} is not the build spec {path}/{BUNDLE_FILE} names ({bundle['buildSpec']})"
    if build_spec is not None and not bundle["buildSpecExists"]:
        return f"the build spec {bundle['buildSpec']} does not exist"
    return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def select_build(
    packages_dir: str | Path | None,
    design_source: str,
    artifact: DesignArtifact | None,
    recorded_bundle: str | None = None,
) -> BuildSelection:
    """Return the design source a web-ui Task builds with now, from the bundles supplied today.

    A mockup can arrive any time before its Task is built. A `cds` Task whose artifact now has
    a supplied bundle builds from that bundle; a `bundle` Task builds from the newest bundle of
    its artifact; a `none` Task is unchanged. A `bundle` Task whose artifact has no supplied
    bundle is blocked, naming the bundle it recorded.

    Args:
        packages_dir: The packages directory, or None.
        design_source: The design source the Task's contract records.
        artifact: The Task's artifact, `{kind, slug}`, or None.
        recorded_bundle: The bundle the contract records, or None.

    Returns:
        `designSource` (`bundle`, `cds` or `none`), `recordedSource`, `artifact`, `bundle`,
        `buildSpec`, `switched` (true when the source or the bundle differs from the
        recorded one), and `blocked` (why the build cannot proceed) or None.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    kind: str
    slug: str
    if (
        not (isinstance(packages_dir, (str, Path)) or packages_dir is None)
        or not (isinstance(design_source, str))
        or not (isinstance(artifact, dict) or artifact is None)
        or not (isinstance(recorded_bundle, str) or recorded_bundle is None)
    ):
        raise TypeError(_ARGUMENT_ERROR)
    recorded: str | None = str(recorded_bundle or "").strip() or None
    art: DesignArtifact = artifact if artifact is not None else {"kind": "", "slug": ""}
    kind = str(art.get("kind") or "").strip()
    slug = str(art.get("slug") or "").strip()
    if (not kind or not slug) and recorded:
        held: beadcontracts.Bundle | None = read_bundle(Path(recorded))
        if held:
            kind, slug = held["kind"], held["slug"]
    out: BuildSelection = {
        "designSource": design_source,
        "recordedSource": design_source,
        "artifact": {"kind": kind, "slug": slug} if kind and slug else None,
        "bundle": None,
        "buildSpec": None,
        "switched": False,
        "blocked": None,
    }
    if design_source not in {"bundle", "cds"}:
        return out
    found: beadcontracts.Bundle | None = _find_bundle(packages_dir, recorded, kind, slug)
    if found is None:
        if design_source == "bundle":
            out["blocked"] = (
                f"the supplied cds bundle {recorded or '(none recorded)'} for "
                f"{kind or '?'} {slug or '?'} is missing, and no bundle of that artifact "
                f"is in {packages_dir or '(no packages directory)'}"
            )
        return out
    if not found["buildSpecExists"]:
        out["blocked"] = f"the cds bundle {found['path']} has no build spec at {found['buildSpec']}"
        return out
    out |= {
        "designSource": "bundle",
        "bundle": found["path"],
        "buildSpec": found["buildSpec"],
        "switched": design_source != "bundle" or not recorded or Path(recorded).resolve() != Path(found["path"]),
    }
    return out


def _find_bundle(packages_dir: str | Path | None, recorded: str | None, kind: str, slug: str) -> Bundle | None:
    """Find the newest matching supplied bundle across recorded roots.

    Returns:
        The matching bundle, or None.

    """
    root: str | Path | None
    roots: list[str | Path | None] = [packages_dir] if str(packages_dir or "").strip() else []
    if recorded:
        roots.append(Path(recorded).parent)
    found: Bundle | None = None
    if kind and slug:
        for root in roots:
            found = next(
                (b for b in list_bundles(root)["bundles"] if (b["kind"], b["slug"]) == (kind, slug)),
                None,
            )
            if found:
                break
    return found
