"""Read one repository's saved detailing on disk and report only what the workflows branch on.

`depscore.py recon-facts` runs `recon_facts`. The detailing of a repository, saved as
`recon-<slug>.json` in the Epic's working directory, gives each delta item placed in that
repository a status (`add`, `modify`, `remove`, `done`, `planned-elsewhere`), the file:line
evidence for it, its surface, the design source each `ui` item takes (`bundle`, `cds` or
`none`, with the supplied bundle and build spec of a `bundle` item), and the upstream
dependency changes. This command reads it against the items placed in the repository and
prints the small facts: the ids of the items that make work and of those that do not; each
`ui` work item's design source; the mocks directory; whether the dependencies are current.
What it had to normalize (a missing or repeated entry, an unknown status, surface or design
source, a missing artifact, an unusable bundle) is named in `warnings`; only a file that is
not a detailing at all is not usable.

No item text travels back: the sessions that specify and decompose the repository read the
file by its path.

A file that cannot be read or is not JSON is an error naming the file, never an empty
result, so the step stops instead of detailing the repository again.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from cdsbundles import DESIGN_SOURCES, KINDS, bundle_problem, read_bundle

STATUSES = ("add", "modify", "remove", "done", "planned-elsewhere")
#: Close synonyms of a status, as a detailing may write them.
STATUS_SYNONYMS = {
    "new": "add",
    "create": "add",
    "added": "add",
    "change": "modify",
    "changed": "modify",
    "update": "modify",
    "modified": "modify",
    "delete": "remove",
    "removed": "remove",
    "retire": "remove",
    "exists": "done",
    "built": "done",
    "complete": "done",
    "planned": "planned-elsewhere",
}
WORK_STATUSES = ("add", "modify", "remove")
SURFACES = ("ui", "service", "infra", "data", "unknown")
FILE_LINE = re.compile(r"[^\s:]+:\d+")
#: At most this many warnings are printed; the count of all of them is always printed.
MAX_PROBLEMS = 40


class ReconError(Exception):
    """The saved detailing cannot be read or is not JSON."""


def _text(value: object) -> str:
    """Return a value as stripped text, or empty when it is not a string.

    Args:
        value: Any JSON value.

    Returns:
        The stripped string, or "".
    """
    return value.strip() if isinstance(value, str) else ""


def _texts(value: object) -> list[str]:
    """Return the non-empty strings of a list value.

    Args:
        value: Any JSON value.

    Returns:
        The stripped strings, in order.
    """
    return [_text(x) for x in value if _text(x)] if isinstance(value, list) else []


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
        msg = f"{path}: no saved detailing at this path"
        raise ReconError(msg)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        msg = f"{path}: {exc}"
        raise ReconError(msg) from exc


def _normalize_items(
    items: list[dict], placed: list[str]
) -> tuple[list[dict], list[str]]:
    """Settle the detailing's items on one usable entry per placed item.

    A placed item with no entry is `add`; a repeated entry keeps the first; an entry for an
    item not placed here is ignored; a status is mapped from a close synonym, else taken as
    `modify`; `planned-elsewhere` with no `plannedBy` is `done`; an unknown surface is
    `unknown`. A work or done status that cites no file:line is only noted.

    Args:
        items: The items as read.
        placed: The ids of the delta items placed in the repository.

    Returns:
        The items, one per placed id in placement order, and the warnings.
    """
    placed_set = set(placed)
    warnings: list[str] = []
    first: dict[str, dict] = {}
    for r in items:
        if r["id"] not in placed_set:
            warnings.append(
                f"{r['id'] or '(no id)'}: not an item placed in this repository; ignored"
            )
            continue
        if r["id"] in first:
            warnings.append(
                f"{r['id']}: listed more than once; the first entry is used"
            )
            continue
        first[r["id"]] = r
    out = []
    for i in placed:
        r = first.get(i)
        if r is None:
            warnings.append(f"{i}: has no entry; taken as add")
            r = {
                "id": i,
                "status": "add",
                "evidence": [],
                "plannedBy": None,
                "surface": "unknown",
            }
        status = r["status"]
        if status not in STATUSES:
            mapped = STATUS_SYNONYMS.get(status.lower(), "modify")
            warnings.append(f"{i}: status {json.dumps(status)} taken as {mapped}")
            r = r | {"status": mapped}
        if r["status"] == "planned-elsewhere" and not r["plannedBy"]:
            warnings.append(
                f"{i}: planned-elsewhere names no bead in plannedBy; taken as done"
            )
            r = r | {"status": "done"}
        if r["surface"] not in SURFACES:
            warnings.append(f"{i}: surface {json.dumps(r['surface'])} taken as unknown")
            r = r | {"surface": "unknown"}
        if r["status"] != "planned-elsewhere" and not any(
            FILE_LINE.search(e) for e in r["evidence"]
        ):
            warnings.append(f"{i}: {r['status']} cites no file:line")
        out.append(r)
    return out, warnings


def _ui_authority(raw: object, work_ui: list[str]) -> dict:
    """Return the mocks directory and each `ui` work item's design source.

    Args:
        raw: The detailing's `uiAuthority` value.
        work_ui: The ids of the `ui` items that make work.

    Returns:
        `mocksDir` and `uiWork`: one `{id, designSource, artifact, bundle, buildSpec,
        sections}` per `ui` work item. `designSource` is `bundle`, `cds` or `none` (None when
        the detailing gives the item none); `artifact` (`{kind, slug}`, as a cds bundle's
        `bundle.json` names it) is set for a `bundle` or `cds` item; `bundle` and
        `buildSpec` for a `bundle` item only.
    """
    ua = raw if isinstance(raw, dict) else {}
    entries: dict[str, dict] = {}
    for b in ua.get("uiItems") if isinstance(ua.get("uiItems"), list) else []:
        if not isinstance(b, dict):
            continue
        item = _text(b.get("item"))
        if item and item not in entries:
            source = _text(b.get("designSource"))
            bundled = source == "bundle"
            raw_art = b.get("artifact") if isinstance(b.get("artifact"), dict) else {}
            art = {
                "kind": _text(raw_art.get("kind")),
                "slug": _text(raw_art.get("slug")),
            }
            entries[item] = {
                "designSource": source or None,
                "artifact": art if source in ("bundle", "cds") else None,
                "bundle": _text(b.get("bundle")) or None if bundled else None,
                "buildSpec": _text(b.get("buildSpec")) or None if bundled else None,
                "sections": _texts(b.get("sections")) if bundled else [],
            }
    blank = {
        "designSource": None,
        "artifact": None,
        "bundle": None,
        "buildSpec": None,
        "sections": [],
    }
    return {
        "mocksDir": _text(ua.get("mocksDir")) or None,
        "uiWork": [{"id": i} | entries.get(i, blank) for i in work_ui],
    }


def _normalize_ui(ui_work: list[dict]) -> list[str]:
    """Settle each `ui` work item on a design source it can be built from.

    A design source outside `bundle`, `cds` and `none` is `cds`. A `bundle` item whose
    bundle or build spec cannot be built from is `cds`; its artifact is the one its bundle
    packages. A `bundle` or `cds` item with no artifact gets a `page` named for the item.

    Args:
        ui_work: The `uiWork` entries; changed in place.

    Returns:
        The warnings.
    """
    warnings = []
    for item in ui_work:
        source = item["designSource"]
        if source not in DESIGN_SOURCES:
            warnings.append(
                f"{item['id']}: design source {json.dumps(source)} taken as cds"
            )
            source = item["designSource"] = "cds"
        if source == "none":
            continue
        if source == "bundle":
            problem = bundle_problem(item["bundle"] or "", item["buildSpec"] or "")
            held = None if problem else read_bundle(Path(item["bundle"]))
            if problem or held is None:
                warnings.append(
                    f"{item['id']}: bundle {problem or 'unreadable'}; taken as cds"
                )
                source = item["designSource"] = "cds"
                item["bundle"] = item["buildSpec"] = None
                item["sections"] = []
            else:
                art = {"kind": held["kind"], "slug": held["slug"]}
                if (item["artifact"] or {}) != art:
                    item["artifact"] = art
        art = item["artifact"] or {}
        if art.get("kind") not in KINDS or not art.get("slug"):
            slug = re.sub(r"[^a-z0-9]+", "-", item["id"].lower()).strip("-") or "page"
            item["artifact"] = {"kind": "page", "slug": slug}
            warnings.append(f"{item['id']}: names no artifact; taken as page {slug}")
    return warnings


def recon_facts(path: Path, placed: list[str]) -> dict:
    """Check a saved detailing against the items placed in its repository; report the facts.

    Args:
        path: The saved detailing, `recon-<slug>.json`.
        placed: The ids of the delta items placed in the repository.

    Returns:
        `file`, `bytes`, `ok`; when not ok, `problem` (the file as a whole is not a
        detailing). When ok: `warnings`, `itemCount`, `counts` per status,
        `work` (ids that make work), `idle` (`{id, status, plannedBy}` of the others),
        `mocksDir`, `uiWork` (each `ui` work item's design source, and for a `bundle`
        item its bundle and build spec), `dependenciesCurrent` and
        `dependencyFindings` (the number of invalidating upstream changes).

    Raises:
        ReconError: The file is absent, cannot be read, or is not JSON.
    """
    body = _load(path)
    head = {"file": str(path), "bytes": path.stat().st_size}
    if not isinstance(body, dict):
        return head | {"ok": False, "problem": "the file is not one JSON object"}
    raw = body.get("items")
    if not isinstance(raw, list):
        return head | {
            "ok": False,
            "problem": "the file holds no `items` list (a detailing saved in an earlier "
            "format, or not a detailing)",
        }
    warnings: list[str] = []
    dc = body.get("dependencyChanges")
    if not isinstance(dc, dict) or not isinstance(dc.get("current"), bool):
        warnings.append(
            "`dependencyChanges.current` is not true or false; taken as true"
        )
        dc = {"current": True, "changeFindings": []}
    items = [
        {
            "id": _text(r.get("id")),
            "status": _text(r.get("status")),
            "evidence": _texts(r.get("evidence")),
            "plannedBy": _text(r.get("plannedBy")) or None,
            "surface": _text(r.get("surface")) or "unknown",
        }
        for r in raw
        if isinstance(r, dict)
    ]
    items, item_warnings = _normalize_items(items, placed)
    warnings += item_warnings
    work = [r["id"] for r in items if r["status"] in WORK_STATUSES]
    ui = _ui_authority(
        body.get("uiAuthority"),
        [
            r["id"]
            for r in items
            if r["status"] in WORK_STATUSES and r["surface"] == "ui"
        ],
    )
    warnings += _normalize_ui(ui["uiWork"])
    findings = dc.get("changeFindings")
    return (
        head
        | {
            "ok": True,
            "warnings": warnings[:MAX_PROBLEMS],
            "warningCount": len(warnings),
            "itemCount": len(items),
            "counts": {s: sum(1 for r in items if r["status"] == s) for s in STATUSES},
            "work": work,
            "idle": [
                {"id": r["id"], "status": r["status"], "plannedBy": r["plannedBy"]}
                for r in items
                if r["status"] not in WORK_STATUSES
            ],
        }
        | ui
        | {
            "dependenciesCurrent": dc["current"],
            "dependencyFindings": len(findings) if isinstance(findings, list) else 0,
        }
    )
