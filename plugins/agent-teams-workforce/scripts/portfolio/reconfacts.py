"""Read one repository's saved detailing on disk and report only what the workflows branch on.

`depscore.py recon-facts` runs `recon_facts`. The detailing of a repository is saved as
`recon-<slug>.json` in the Epic's working directory; its shape, statuses, surfaces, design
sources and artifact kinds are the artifact-handoff skill's recon contract
(`skills/artifact-handoff/schemas/recon.schema.json`, generated into `recon_contract.py`), and
this module defines none of them. The file is validated against that contract: a file that
does not conform is not usable (`ok` false, the violations named in `problem`).

A conforming detailing is then read against the items placed in the repository, and the small
facts are printed: the ids of the items that make work and of those that do not; each `ui`
work item's design source; the mocks directory; whether the dependencies are current. What
the contract cannot express and had to be settled (an item not placed here, a repeated or
missing entry, a `ui` work item with no design source, an unusable bundle, absent dependency
changes) is named in `warnings`.

No item text travels back: the sessions that specify and decompose the repository read the
file by its path.

A file that cannot be read or is not JSON is an error naming the file, never an empty
result, so the step stops instead of detailing the repository again.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from cdsbundles import artifact_kind, bundle_problem, read_bundle

# The detailing contract is generated from the artifact-handoff recon schema, its one definition.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))

# isort: split
from recon_contract import (
    DEFAULT_ARTIFACT_KIND,
    DEFAULT_DESIGN_SOURCE,
    DESIGN_SOURCE_BUNDLE,
    DESIGN_SOURCE_CDS,
    DESIGN_SOURCE_NONE,
    KEY_ARTIFACT,
    KEY_BUILD_SPEC,
    KEY_BUNDLE,
    KEY_CHANGE_FINDINGS,
    KEY_CURRENT,
    KEY_DEPENDENCY_CHANGES,
    KEY_DESIGN_SOURCE,
    KEY_ID,
    KEY_ITEM,
    KEY_ITEMS,
    KEY_KIND,
    KEY_MOCKS_DIR,
    KEY_PLANNED_BY,
    KEY_SECTIONS,
    KEY_SLUG,
    KEY_STATUS,
    KEY_SURFACE,
    KEY_UI_AUTHORITY,
    KEY_UI_ITEMS,
    STATUS_ADD,
    STATUSES,
    SURFACE_UI,
    WORK_STATUSES,
    ArtifactKind,
    DependencyChanges,
    DesignSource,
    ReconContractError,
    ReconDetailing,
    ReconItem,
    ReconStatus,
    UiArtifact,
    UiAuthority,
    UiItem,
    parse_detailing,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beadcontracts import Bundle
    from contracts import JsonObject, JsonValue

#: At most this many warnings are printed; the count of all of them is always printed.
MAX_PROBLEMS: Final = 40
_SLUG_SEPARATORS: Final = re.compile(r"[^a-z0-9]+")


class ReconError(Exception):
    """The saved detailing cannot be read or is not JSON."""


@dataclass(frozen=True)
class _Settled:
    """One placed item's settled status: the detailing's entry, or `add` when it has none."""

    id: str
    status: ReconStatus
    planned_by: str | None
    ui: bool


@dataclass(frozen=True)
class _UiWork:
    """One `ui` work item's settled design source."""

    id: str
    design_source: DesignSource
    artifact: UiArtifact | None
    bundle: str | None
    build_spec: str | None
    sections: tuple[str, ...]

    def as_json(self) -> JsonObject:
        """Return the entry as the `uiWork` member printed for the workflows.

        Returns:
            `id` and the design source fields, named as the recon contract names them.

        """
        artifact: JsonValue = (
            {KEY_KIND: self.artifact[KEY_KIND], KEY_SLUG: self.artifact[KEY_SLUG]} if self.artifact else None
        )
        return {
            KEY_ID: self.id,
            KEY_DESIGN_SOURCE: self.design_source,
            KEY_ARTIFACT: artifact,
            KEY_BUNDLE: self.bundle,
            KEY_BUILD_SPEC: self.build_spec,
            KEY_SECTIONS: list(self.sections),
        }


def _load(path: Path) -> object:
    """Parse the saved detailing.

    Args:
        path: The file.

    Returns:
        The parsed value.

    Raises:
        ReconError: The file is absent, cannot be read, or is not JSON.

    """
    if not path.is_file():
        message: str = f"{path}: no saved detailing at this path"
        raise ReconError(message)
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        message = f"{path}: {exc}"
        raise ReconError(message) from exc
    return raw


def _settle_items(items: Sequence[ReconItem], placed: Sequence[str]) -> tuple[list[_Settled], list[str]]:
    """Settle the detailing's items on one entry per placed item.

    A placed item with no entry is `add`; a repeated entry keeps the first; an entry for an
    item not placed here is ignored.

    Args:
        items: The detailing's items, validated against the recon contract.
        placed: The ids of the delta items placed in the repository.

    Returns:
        The settled items, one per placed id in placement order, and the warnings.

    """
    placed_set: set[str] = set(placed)
    warnings: list[str] = []
    first: dict[str, ReconItem] = {}
    for item in items:
        item_id: str = item[KEY_ID]
        if item_id not in placed_set:
            warnings.append(f"{item_id}: not an item placed in this repository; ignored")
        elif item_id in first:
            warnings.append(f"{item_id}: listed more than once; the first entry is used")
        else:
            first[item_id] = item
    settled: list[_Settled] = []
    for placed_id in placed:
        entry: ReconItem | None = first.get(placed_id)
        if entry is None:
            warnings.append(f"{placed_id}: has no entry; taken as {STATUS_ADD}")
            settled.append(_Settled(placed_id, STATUS_ADD, None, ui=False))
            continue
        settled.append(
            _Settled(placed_id, entry[KEY_STATUS], entry.get(KEY_PLANNED_BY), ui=entry[KEY_SURFACE] == SURFACE_UI),
        )
    return settled, warnings


def _default_artifact(item_id: str) -> UiArtifact:
    """Return the artifact a `ui` item with none builds: a page named for the item.

    Args:
        item_id: The delta item id.

    Returns:
        The default artifact kind, with a slug made from the item id.

    """
    slug: str = _SLUG_SEPARATORS.sub("-", item_id.lower()).strip("-") or DEFAULT_ARTIFACT_KIND
    return {KEY_KIND: DEFAULT_ARTIFACT_KIND, KEY_SLUG: slug}


def _bundle_artifact(held: Bundle, fallback: UiArtifact) -> UiArtifact:
    """Return the artifact a supplied bundle packages.

    Args:
        held: The bundle, as `cdsbundles.read_bundle` read it.
        fallback: The artifact the detailing named, used when the bundle names no known kind.

    Returns:
        The bundle's kind and slug.

    """
    kind: ArtifactKind | None = artifact_kind(held["kind"])
    return {KEY_KIND: kind, KEY_SLUG: held["slug"]} if kind is not None else fallback


def _settle_ui(item_id: str, entry: UiItem | None) -> tuple[_UiWork, list[str]]:
    """Settle one `ui` work item on a design source it can be built from.

    An item the detailing gives no design source takes the contract's default. A `bundle`
    item whose bundle or build spec cannot be built from takes `cds`; a `bundle` item's
    artifact is the one its bundle packages. A `bundle` or `cds` item with no artifact gets a
    page named for the item.

    Args:
        item_id: The delta item id.
        entry: The detailing's `uiItems` entry for the item, or None.

    Returns:
        The settled item and the warnings.

    """
    warnings: list[str] = []
    if entry is None:
        warnings.append(f"{item_id}: has no design source; taken as {DEFAULT_DESIGN_SOURCE}")
        source: DesignSource = DEFAULT_DESIGN_SOURCE
        named: UiArtifact | None = None
    else:
        source = entry[KEY_DESIGN_SOURCE]
        named = entry.get(KEY_ARTIFACT)
    if source == DESIGN_SOURCE_NONE:
        return _UiWork(item_id, source, None, None, None, ()), warnings
    artifact: UiArtifact = named if named is not None else _default_artifact(item_id)
    if named is None:
        warnings.append(f"{item_id}: names no artifact; taken as {artifact[KEY_KIND]} {artifact[KEY_SLUG]}")
    if source == DESIGN_SOURCE_BUNDLE and entry is not None:
        bundle: str = entry.get(KEY_BUNDLE) or ""
        build_spec: str | None = entry.get(KEY_BUILD_SPEC)
        problem: str | None = bundle_problem(bundle, build_spec or "")
        held: Bundle | None = None if problem else read_bundle(Path(bundle))
        if held is not None:
            sections: tuple[str, ...] = tuple(entry.get(KEY_SECTIONS, []))
            return _UiWork(item_id, source, _bundle_artifact(held, artifact), bundle, build_spec, sections), warnings
        warnings.append(f"{item_id}: bundle {problem or 'unreadable'}; taken as {DESIGN_SOURCE_CDS}")
    return _UiWork(item_id, DESIGN_SOURCE_CDS, artifact, None, None, ()), warnings


def _ui_work(authority: UiAuthority | None, work_ui: Sequence[str]) -> tuple[list[_UiWork], list[str]]:
    """Return each `ui` work item's settled design source.

    Args:
        authority: The detailing's `uiAuthority`, or None when it has none.
        work_ui: The ids of the `ui` items that make work.

    Returns:
        One settled entry per `ui` work item, in order, and the warnings.

    """
    entries: dict[str, UiItem] = {}
    for entry in authority[KEY_UI_ITEMS] if authority is not None else []:
        entries.setdefault(entry[KEY_ITEM], entry)
    out: list[_UiWork] = []
    warnings: list[str] = []
    for item_id in work_ui:
        settled, problems = _settle_ui(item_id, entries.get(item_id))
        out.append(settled)
        warnings.extend(problems)
    return out, warnings


def recon_facts(path: Path, placed: list[str]) -> JsonObject:
    """Check a saved detailing against the items placed in its repository; report the facts.

    A file that is absent, cannot be read, or is not JSON raises `ReconError` (from `_load`).

    Args:
        path: The saved detailing, `recon-<slug>.json`.
        placed: The ids of the delta items placed in the repository.

    Returns:
        `file`, `bytes`, `ok`; when not ok, `problem` (the file does not conform to the
        recon contract, each violation named). When ok: `warnings`, `warningCount`,
        `itemCount`, `counts` per status, `work` (ids that make work), `idle`
        (`{id, status, plannedBy}` of the others), `mocksDir`, `uiWork` (each `ui` work
        item's design source, and for a `bundle` item its bundle and build spec),
        `dependenciesCurrent` and `dependencyFindings` (the number of invalidating upstream
        changes).

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not isinstance(path, Path) or not isinstance(placed, list) or not all(isinstance(i, str) for i in placed):
        message: str = "recon_facts takes a Path and a list of placed item ids"
        raise TypeError(message)
    raw: object = _load(path)
    head: JsonObject = {"file": str(path), "bytes": path.stat().st_size}
    try:
        detailing: ReconDetailing = parse_detailing(raw, source=str(path))
    except ReconContractError as exc:
        return head | {"ok": False, "problem": str(exc)}
    items, warnings = _settle_items(detailing[KEY_ITEMS], placed)
    changes: DependencyChanges | None = detailing.get(KEY_DEPENDENCY_CHANGES)
    if changes is None:
        warnings.append(f"`{KEY_DEPENDENCY_CHANGES}` is absent; taken as {KEY_CURRENT}")
    authority: UiAuthority | None = detailing.get(KEY_UI_AUTHORITY)
    ui_work, ui_warnings = _ui_work(authority, [i.id for i in items if i.status in WORK_STATUSES and i.ui])
    warnings += ui_warnings
    counts: JsonObject = {status: sum(1 for i in items if i.status == status) for status in STATUSES}
    idle: list[JsonValue] = [
        {KEY_ID: i.id, KEY_STATUS: i.status, KEY_PLANNED_BY: i.planned_by}
        for i in items
        if i.status not in WORK_STATUSES
    ]
    return head | {
        "ok": True,
        "warnings": list(warnings[:MAX_PROBLEMS]),
        "warningCount": len(warnings),
        "itemCount": len(items),
        "counts": counts,
        "work": [i.id for i in items if i.status in WORK_STATUSES],
        "idle": idle,
        KEY_MOCKS_DIR: authority.get(KEY_MOCKS_DIR) if authority is not None else None,
        "uiWork": [w.as_json() for w in ui_work],
        "dependenciesCurrent": changes[KEY_CURRENT] if changes is not None else True,
        "dependencyFindings": len(changes.get(KEY_CHANGE_FINDINGS, [])) if changes is not None else 0,
    }
