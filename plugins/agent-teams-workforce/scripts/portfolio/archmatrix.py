"""Pure architecture projections of the dispatch's element matrix snapshot."""

from __future__ import annotations

from pathlib import Path


def element_id(name: str) -> str:
    """Match catalog names using the matrix's canonical identifier rule."""
    return " ".join(name.split()).casefold()


def row_of(snapshot: dict | None, name: str) -> dict:
    """Return a recorded element, without treating a missing row as built."""
    return (snapshot or {}).get("elements", {}).get(element_id(name), {})


def satisfied(snapshot: dict, row: dict) -> bool:
    """Require deployment for repositories with stacks; libraries need built code."""
    if row.get("state") == "deployed":
        return True
    if row.get("state") != "built" or not row.get("repository"):
        return False
    repository = element_id(row["repository"])
    rows = snapshot.get("elements", {})
    owner = rows.get(f"repository:{repository}", {})
    if not owner or owner.get("stacksError"):
        return False
    return not any(
        str(key).startswith("stack:") for key in owner.get("contains", [])
    ) and not any(key.startswith(f"stack:{repository}/") for key in rows)


def catalog_elements(documents: list[dict]) -> dict[str, list[str]]:
    """Map element names to cited views, using the architecture catalog reader."""
    from archstate import _catalog

    elements: dict[str, list[str]] = {}
    for document in documents:
        path = Path(document["path"])
        catalog = _catalog(path)
        names = catalog["shows"] or ([catalog["subject"]] if catalog["subject"] else [])
        for name in names:
            elements.setdefault(name, []).append(str(path))
    return elements
