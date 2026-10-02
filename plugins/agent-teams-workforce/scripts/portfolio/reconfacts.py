"""Read one repository's saved detailing on disk and report only what the workflows branch on.

`depscore.py recon-facts` runs `recon_facts`. The detailing of a repository, saved as
`recon-<slug>.json` in the Epic's working directory, gives each delta item placed in that
repository a status (`add`, `modify`, `remove`, `done`, `planned-elsewhere`), the file:line
evidence for it, its surface, the design source each `ui` item takes (`bundle`, `cds` or
`none`, with the supplied bundle and build spec of a `bundle` item), and the upstream
dependency changes. This command checks it against the items placed in the repository and
prints the small facts: whether it is usable and, when not, what is wrong with which item;
the ids of the items that make work and of those that do not; each `ui` work item's design
source; the mocks directory; whether the dependencies are current.

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
WORK_STATUSES = ("add", "modify", "remove")
SURFACES = ("ui", "service", "infra", "data", "unknown")
FILE_LINE = re.compile(r"[^\s:]+:\d+")
#: At most this many item problems are printed; the count of all of them is always printed.
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


def _item_problems(items: list[dict], placed: list[str]) -> list[dict]:
    """Name every item of the detailing that makes it unusable.

    Args:
        items: The normalized items.
        placed: The ids of the delta items placed in the repository.

    Returns:
        One `{id, problem}` per defect.
    """
    placed_set = set(placed)
    counted: dict[str, int] = {}
    for r in items:
        counted[r["id"]] = counted.get(r["id"], 0) + 1
    problems = [
        {"id": i, "problem": "has no entry"} for i in placed if i not in counted
    ]
    problems += [
        {"id": i, "problem": "listed more than once"}
        for i, n in counted.items()
        if i in placed_set and n > 1
    ]
    for r in items:
        rid = r["id"] or "(no id)"
        if r["id"] not in placed_set:
            problems.append(
                {"id": rid, "problem": "not an item placed in this repository"}
            )
            continue
        if r["status"] not in STATUSES:
            problems.append(
                {
                    "id": rid,
                    "problem": f"status {json.dumps(r['status'])} is not one of "
                    + ", ".join(STATUSES),
                }
            )
            continue
        if not any(FILE_LINE.search(e) for e in r["evidence"]):
            problems.append({"id": rid, "problem": f"{r['status']} cites no file:line"})
        if r["status"] == "planned-elsewhere" and not r["plannedBy"]:
            problems.append(
                {"id": rid, "problem": "planned-elsewhere names no bead in plannedBy"}
            )
        if r["surface"] not in SURFACES:
            problems.append(
                {
                    "id": rid,
                    "problem": f"surface {json.dumps(r['surface'])} is not one of "
                    + ", ".join(SURFACES),
                }
            )
    return problems


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


def _ui_problems(ui_work: list[dict]) -> list[dict]:
    """Name every `ui` work item whose design source cannot be built from.

    A `bundle` item cites a supplied bundle (the newest of its kind and slug) and the build
    spec its `bundle.json` names; a `cds` or `none` item cites nothing.

    Args:
        ui_work: The `uiWork` entries.

    Returns:
        One `{id, problem}` per defect.
    """
    problems = []
    for item in ui_work:
        source = item["designSource"]
        if source not in DESIGN_SOURCES:
            problems.append(
                {
                    "id": item["id"],
                    "problem": f"design source {json.dumps(source)} is not one of "
                    + ", ".join(DESIGN_SOURCES)
                    + " (uiAuthority.uiItems gives every ui item one)",
                }
            )
            continue
        if source == "none":
            continue
        art = item["artifact"] or {}
        if source == "bundle" and not (art.get("kind") and art.get("slug")):
            held = read_bundle(Path(item["bundle"])) if item["bundle"] else None
            if held:
                art = item["artifact"] = {"kind": held["kind"], "slug": held["slug"]}
        if art.get("kind") not in KINDS or not art.get("slug"):
            problems.append(
                {
                    "id": item["id"],
                    "problem": "names no artifact: a bundle or cds item records "
                    "`artifact` {kind: page | shell | view, slug}",
                }
            )
            continue
        if source != "bundle":
            continue
        problem = bundle_problem(item["bundle"] or "", item["buildSpec"] or "")
        if problem:
            problems.append({"id": item["id"], "problem": f"bundle: {problem}"})
            continue
        held = read_bundle(Path(item["bundle"]))
        if held and (held["kind"], held["slug"]) != (art["kind"], art["slug"]):
            problems.append(
                {
                    "id": item["id"],
                    "problem": f"artifact {art['kind']} {art['slug']} is not the one "
                    f"{item['bundle']} packages ({held['kind']} {held['slug']})",
                }
            )
    return problems


def recon_facts(path: Path, placed: list[str]) -> dict:
    """Check a saved detailing against the items placed in its repository; report the facts.

    Args:
        path: The saved detailing, `recon-<slug>.json`.
        placed: The ids of the delta items placed in the repository.

    Returns:
        `file`, `bytes`, `ok`; when not ok, `problem` (the file as a whole) or
        `failedItems` with `problemCount`. When ok: `itemCount`, `counts` per status,
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
    dc = body.get("dependencyChanges")
    if not isinstance(dc, dict) or not isinstance(dc.get("current"), bool):
        return head | {
            "ok": False,
            "problem": "`dependencyChanges.current` is not true or false",
        }
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
    problems = _item_problems(items, placed)
    if problems:
        return head | {
            "ok": False,
            "itemCount": len(items),
            "problemCount": len(problems),
            "failedItems": problems[:MAX_PROBLEMS],
        }
    work = [r["id"] for r in items if r["status"] in WORK_STATUSES]
    ui = _ui_authority(
        body.get("uiAuthority"),
        [
            r["id"]
            for r in items
            if r["status"] in WORK_STATUSES and r["surface"] == "ui"
        ],
    )
    ui_problems = _ui_problems(ui["uiWork"])
    if ui_problems:
        return head | {
            "ok": False,
            "itemCount": len(items),
            "problemCount": len(ui_problems),
            "failedItems": ui_problems[:MAX_PROBLEMS],
        }
    findings = dc.get("changeFindings")
    return (
        head
        | {
            "ok": True,
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
