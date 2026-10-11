"""Small pure checks for placement boundaries, interrupted creation and citations."""

from __future__ import annotations

import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import override

from typeguard import CollectionCheckStrategy, check_type, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from orchestrator.checks.check_support import report, require
from orchestrator.core.io import JsonValue
from orchestrator.core.tools import CommandResult, Tools
from orchestrator.flows.repo_placement import PlacementInputs, accept_placement, app_space
from orchestrator.flows.repo_scoping import create_repositories
from orchestrator.flows.trd_authoring import document
from placement_contract import (
    KEY_FRONTEND,
    KEY_ITEM_IDS,
    KEY_MISSING_REPOS,
    KEY_NAME,
    KEY_NO_CODE,
    KEY_PLACEMENTS,
    KEY_PURPOSE,
    KEY_RATIONALE,
    KEY_REPO_NAME,
    KEY_REPO_PATH,
    KEY_SPAN_RATIONALE,
    KEY_TEMPLATE,
    MissingRepo,
    Placement,
    PlacementRuling,
)


def _first(value: object) -> dict[str, JsonValue]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)[0]


class CreationFacts(Tools):
    """Provide typed inventory and authentication facts without external commands."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(self, path: Path) -> None:
        """Bind the repository returned by the fixture inventory."""
        super().__init__(path / "evidence")
        self.path = path

    @override
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def polyrepo(self, args: Sequence[str], *, stage: str, timeout: float = 300) -> CommandResult:
        """Return the existing repository; reject any creation command.

        Returns:
            The fixture inventory command result.

        """
        require(list(args) == ["inventory"], "this check never creates a repository")
        result = {"repos": [{"name": "Product-existing", "path": str(self.path)}]}
        return CommandResult(tuple(args), 0, json.dumps(result), "")

    @override
    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def command(
        self,
        argv: Sequence[str],
        *,
        stage: str,
        cwd: Path | None = None,
        timeout: float = 120,
        check: bool = True,
    ) -> CommandResult:
        """Return a failed authentication result without invoking GitHub.

        Returns:
            The fixture authentication result.

        """
        require(list(argv) == ["gh", "auth", "status"], "unexpected command")
        return CommandResult(tuple(argv), 1, "", "not parsed for classification")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Evaluate the existing isolated check contract.

    Raises:
        AssertionError: Invalid coverage or a prohibited path was accepted.

    """
    config: dict[str, JsonValue] = {
        "repositories": {
            "patterns": [
                {"regex": "^Product-", "kind": "application", "space": "product"},
                {"regex": "^marketing-", "kind": "application", "space": "marketing"},
            ],
        },
        "github_owner": "example-org",
    }
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        arch, control, marketing = (
            root / "vault/architecture",
            root / "control",
            root / "apps/marketing",
        )
        arch.mkdir(parents=True)
        repo = root / "apps/product/Product-existing"
        repo.mkdir(parents=True)
        path = root / "placement.json"
        placement: Placement = {
            KEY_REPO_NAME: "Product-existing",
            KEY_REPO_PATH: str(repo),
            KEY_ITEM_IDS: ["a"],
            KEY_FRONTEND: False,
            KEY_RATIONALE: "element owner",
        }
        value: PlacementRuling = {
            KEY_PLACEMENTS: [placement],
            KEY_MISSING_REPOS: [],
            KEY_NO_CODE: [],
            KEY_SPAN_RATIONALE: "one element",
        }
        items: list[dict[str, JsonValue]] = [{"id": "a", "element": "Queue"}]
        live: dict[str, JsonValue] = {"repos": [{"name": "Product-existing", "path": str(repo)}]}

        def check() -> tuple[PlacementRuling, list[str]]:
            path.write_text(json.dumps(value))
            return accept_placement(
                path,
                PlacementInputs(items, live, {}, config, control, arch, marketing),
            )

        require(check()[0][KEY_PLACEMENTS][0][KEY_ITEM_IDS] == ["a"], "the one placement keeps item a")
        for ids in (["a", "a"], [], ["unknown"]):
            placement[KEY_ITEM_IDS] = list(ids)
            try:
                check()
            except ValueError:
                pass
            else:
                message = f"accepted invalid coverage: {ids}"
                raise AssertionError(message)
        placement[KEY_ITEM_IDS] = ["a"]
        for bad in (control, arch.parent, marketing / "marketing-ui"):
            placement[KEY_REPO_PATH] = str(bad)
            _first(live["repos"])["path"] = str(bad)
            try:
                check()
            except ValueError:
                pass
            else:
                message = f"accepted forbidden path: {bad}"
                raise AssertionError(message)
        require(app_space("Product-new", config) == "product", "app_space('Product-new', config) == 'product'")
        report("PASS: exact coverage, empty span and prohibited repository rejection")

        missing: MissingRepo = {
            KEY_NAME: "Product-existing",
            KEY_TEMPLATE: "service",
            KEY_PURPOSE: "queue",
            KEY_ITEM_IDS: ["a"],
        }
        creation: PlacementRuling = {
            KEY_PLACEMENTS: [],
            KEY_MISSING_REPOS: [missing],
            KEY_NO_CODE: [],
            KEY_SPAN_RATIONALE: "one missing repository",
        }
        result = create_repositories(
            creation,
            CreationFacts(repo),
            config,
            root,
        )
        require(_first(result["created"])["existed"], "result['created'][0]['existed']")
        require(not result["failures"], "not result['failures']")
        missing[KEY_NAME] = "Product-new"
        result = create_repositories(
            creation,
            CreationFacts(repo),
            config,
            root,
        )
        require(_first(result["failures"])["ownerFact"] is True, "result['failures'][0]['ownerFact'] is True")
        report("PASS: interrupted creation reuses inventory; failed auth produces owner fact")

        _check_citations(arch, root)


def _check_citations(arch: Path, root: Path) -> None:
    view = arch / "arc42/view.md"
    view.parent.mkdir()
    view.write_text("view")
    trd = root / "trd.md"
    trd.write_text("---\ndecisionIds: [view.md#one]\n---\nTechnical requirement")
    require(document(trd, arch)[0] == ["view.md#one"], "document(trd, arch)[0] == ['view.md#one']")
    view.unlink()
    try:
        document(trd, arch)
    except ValueError as exc:
        require("view.md#one" in str(exc), "'view.md#one' in str(exc)")
    else:
        message = "missing citation accepted on reread"
        raise AssertionError(message)
    report("PASS: TRD citations resolve within architecture and are checked again on reuse")


if __name__ == "__main__":
    main()
