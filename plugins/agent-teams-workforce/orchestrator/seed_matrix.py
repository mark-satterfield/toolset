"""Seed reviewed architecture intent; never execute CDK or infer intent from code."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts/portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.matrix import write_seed
from orchestrator.core.tools import Tools, retry_call

archmatrix = importlib.import_module("archmatrix")


def _element_id(value: object) -> str:
    return check_type(archmatrix.element_id(check_type(value, str)), str)


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _strings(value: object) -> list[str]:
    return check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


BUILD_FIELDS = (
    "state",
    "task",
    "story",
    "pr",
    "commit",
    "deployedCommit",
    "changedAt",
    "changedBy",
)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def row(name: str, kind: str, repository: str, stack: str | None = None) -> dict[str, JsonValue]:
    """IDs identify inventory records, not physical AWS resource names.

    Returns:
        The validated inventory record or compiled matrix.

    """
    prefix = {
        "repository": "repository:",
        "stack": f"stack:{repository}/",
        "element": f"element:{repository}/{stack or '@repository'}/",
    }[kind]
    return {
        "id": _element_id(prefix + name),
        "name": name,
        "kind": kind,
        "repository": repository,
        "repositorySource": "seed",
        "stack": stack,
        "purpose": "",
        "expected": "",
        "evidence": [],
        "views": [],
        "contains": [],
        **dict.fromkeys(BUILD_FIELDS),
        "state": "unknown",
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def add_row(rows: dict[str, dict[str, JsonValue]], item: dict[str, JsonValue], spec: dict[str, JsonValue]) -> None:
    """Reject duplicate identities and undocumented intended contents.

    Raises:
        ValueError: Required inventory identity or evidence is missing.

    """
    key = check_type(item["id"], str)
    if key in rows:
        message = f"duplicate intended identity: {key}"
        raise ValueError(message)
    purpose = spec.get("purpose") or spec.get("expected")
    if not isinstance(purpose, str) or not purpose.strip():
        message = f"missing purpose: {key}"
        raise ValueError(message)
    evidence = _objects(spec.get("evidence", []))
    if not evidence or any(not e.get("path") or not e.get("quote") for e in evidence):
        message = f"missing source evidence: {key}"
        raise ValueError(message)
    item.update(
        json_object({
            "purpose": purpose,
            "expected": spec.get("expected", purpose),
            "evidence": evidence,
            "views": sorted({check_type(e["path"], str) for e in evidence}),
            "aliases": spec.get("aliases", []),
        }),
    )
    for field in (
        "status",
        "notes",
        "declaredNames",
        "declaredStacks",
        "resourceType",
        "physicalName",
        "conflicts",
        "nameStatus",
    ):
        if field in spec:
            item[field] = spec[field]
    rows[key] = item


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def preserve_build_facts(rows: dict[str, dict[str, JsonValue]], previous: dict[str, JsonValue]) -> None:
    """Migrate only unique legacy identities; retain all unmatched build evidence."""
    for key, old in check_type(
        previous.get("elements", {}),
        dict[str, dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    ).items():
        target = rows.get(key)
        if target is None and old.get("kind") == "element":
            candidates = [
                r
                for r in rows.values()
                if r["kind"] == "element"
                and _element_id(old.get("name", key)) in {_element_id(n) for n in [r["name"], *_strings(r["aliases"])]}
                and (not old.get("repository") or old["repository"] == r["repository"])
                and (not old.get("stack") or old["stack"] == r["stack"])
            ]
            if len(candidates) == 1:
                target = candidates[0]
        meaningful = (
            old.get("state", "unknown") != "unknown"
            or any(old.get(f) is not None for f in BUILD_FIELDS if f != "state")
            or old.get("repositorySource") == "build"
        )
        if target is None:
            if meaningful:
                rows[key] = {**old, "inventoryStatus": "retained-build-evidence"}
            continue
        if meaningful or key in rows:
            target.update({field: old.get(field) for field in BUILD_FIELDS})
            target["state"] = old.get("state") or "unknown"
        if old.get("repositorySource") == "build":
            target.update(
                repository=old.get("repository"),
                stack=old.get("stack"),
                repositorySource="build",
            )


def _inventory_rows(sources: dict[str, JsonValue]) -> dict[str, dict[str, JsonValue]]:
    rows: dict[str, dict[str, JsonValue]] = {}
    for repo in _objects(sources["repositories"]):
        name = check_type(repo["repository"], str)
        add_row(rows, row(name, "repository", name), repo)
        for stack in _objects(repo.get("stacks", [])):
            stack_name = check_type(stack["name"], str)
            add_row(rows, row(stack_name, "stack", name, stack_name), stack)
            for component in _objects(stack.get("elements", [])):
                add_row(
                    rows,
                    row(check_type(component["name"], str), "element", name, stack_name),
                    component,
                )
        for component in _objects(repo.get("elements", [])):
            add_row(rows, row(check_type(component["name"], str), "element", name), component)
    return rows


def _index_rows(rows: dict[str, dict[str, JsonValue]]) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for key, item in rows.items():
        if item["kind"] in {"repository", "stack"}:
            item["contains"] = []
        if item.get("inventoryStatus") != "retained-build-evidence":
            for name in [item["name"], *_strings(item.get("aliases", []))]:
                aliases.setdefault(_element_id(name), []).append(key)
    for key, item in rows.items():
        owner = rows.get(_element_id(f"repository:{item.get('repository')}"))
        if owner and item["kind"] != "repository":
            _strings(owner["contains"]).append(key)
        if item["kind"] == "element" and item.get("stack"):
            stack = rows.get(_element_id(f"stack:{item['repository']}/{item['stack']}"))
            if stack:
                _strings(stack["contains"]).append(key)
    for item in rows.values():
        item["contains"] = json_object({"contains": sorted(set(_strings(item.get("contains", []))))})["contains"]
    return aliases


def _prefer_aliases(rows: dict[str, dict[str, JsonValue]], aliases: dict[str, list[str]]) -> None:
    # Catalog names denote a stack/component, not its repository container.
    # Prefer the stack aggregate only within its own repository; equally named
    # resources in different stacks or repositories remain ambiguous.
    for name, candidates in aliases.items():
        preferred = []
        for key in candidates:
            item = rows[key]
            peers = [rows[c] for c in candidates if c != key]
            if item["kind"] == "repository" and any(
                p["repository"] == item["repository"] and p["kind"] != "repository" for p in peers
            ):
                continue
            if item["kind"] == "element" and any(
                p["kind"] == "stack" and p["repository"] == item["repository"] and p["stack"] == item["stack"]
                for p in peers
            ):
                continue
            preferred.append(key)
        aliases[name] = preferred


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def seed(sources: dict[str, JsonValue], previous: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Compile explicit, cited repository → stack → expected-component records.

    Returns:
        The validated inventory record or compiled matrix.

    Raises:
        ValueError: Required inventory identity or evidence is missing.

    """
    if sources.get("version") != 1 or not isinstance(sources.get("repositories"), list):
        message = "expected a version 1 expected-inventory source manifest"
        raise ValueError(message)
    rows = _inventory_rows(sources)
    preserve_build_facts(rows, previous)
    aliases = _index_rows(rows)
    _prefer_aliases(rows, aliases)
    return json_object({
        "version": 2,
        "seededAt": previous.get("seededAt") or sources["acquiredAt"],
        "intentUpdatedAt": sources["acquiredAt"],
        "elements": rows,
        "aliases": {k: sorted(set(v)) for k, v in sorted(aliases.items())},
        "unresolved": sources.get("unresolved", []),
        "excludedReferences": sources.get("excludedReferences", []),
        "source": sources.get("source", "reviewed expected inventory"),
        "ownerOverrides": sources.get("ownerOverrides", []),
        "resolutions": sources.get("resolutions", []),
        "namingStandard": sources.get("namingStandard", {}),
        "architectureCommit": sources.get("architectureCommit"),
    })


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def publish(path: Path, root: Path) -> None:
    """Publish only the matrix while its write lock is held."""
    relative = str(path.relative_to(root))
    tools = Tools(root / "ops/sdlc-automation/state/matrix-evidence")
    tools.git(root, ["add", "--", relative], stage="matrix")
    changed = tools.command(
        ["git", "diff", "--cached", "--quiet", "--", relative],
        cwd=root,
        stage="matrix",
        check=False,
    )
    if changed.exit == 1:
        tools.git(
            root,
            [
                "commit",
                "--only",
                relative,
                "-m",
                "feat(matrix): update architecture expected inventory",
                "-m",
                "Pipeline-Run: seed-matrix",
            ],
            stage="matrix",
        )
    elif changed.exit:
        stage = "matrix"
        raise tools.failure(stage, "other", vars(changed))
    tools.git(root, ["push", "origin", "main"], stage="matrix")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Compile and publish the explicitly reviewed inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--control",
        type=Path,
        default=os.environ.get("ATW_CONTROL_REPO"),
        required=not os.environ.get("ATW_CONTROL_REPO"),
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Reviewed expected-inventory.json; architecture changes require review",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=os.environ.get("ATW_ELEMENT_MATRIX"),
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Leave the seed for independent review before publishing",
    )
    args = parser.parse_args()
    source = args.source or args.control / "ops/sdlc-automation/expected-inventory.json"
    sources = json_object(json.loads(source.read_text(encoding="utf-8")))
    output = args.output or args.control / "ops/sdlc-automation/element-matrix.json"
    result = retry_call(
        lambda: write_seed(
            output,
            args.control,
            lambda old: seed(sources, old),
            None if args.no_publish else lambda: publish(output, args.control),
        ),
    )
    sys.stdout.write(json.dumps({"rows": len(json_object(result["elements"])), "output": str(output)}) + "\n")


if __name__ == "__main__":
    main()
