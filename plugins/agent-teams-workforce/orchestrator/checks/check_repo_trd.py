"""Small pure checks for placement boundaries, interrupted creation and citations."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.core.tools import CommandResult
from orchestrator.flows.repo_placement import accept_placement, app_space
from orchestrator.flows.repo_scoping import create_repositories
from orchestrator.flows.trd_authoring import document


class CreationFacts:
    def __init__(self, path: Path, *, signed_in: bool = True) -> None:
        self.path, self.signed_in = path, signed_in
        self.created = []

    def polyrepo(self, args: list, **kwargs: object) -> CommandResult:
        assert args == ["inventory"]  # This check never creates a repository.
        result = {"repos": [{"name": "Product-existing", "path": str(self.path)}]}
        return CommandResult(tuple(args), 0, json.dumps(result), "")

    def command(self, args: list, **kwargs: object) -> CommandResult:
        assert args == ["gh", "auth", "status"]
        return CommandResult(tuple(args), 1, "", "not parsed for classification")


def main() -> None:
    plugin = Path(__file__).resolve().parents[2]
    schema = plugin / "skills/artifact-handoff/schemas/placement.schema.json"
    config = {
        "repositories": {
            "patterns": [
                {"regex": "^Product-", "kind": "application", "space": "product"},
                {"regex": "^marketing-", "kind": "application", "space": "marketing"},
            ]
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
        value = {
            "placements": [
                {
                    "repoName": "Product-existing",
                    "repoPath": str(repo),
                    "itemIds": ["a"],
                    "frontend": False,
                    "rationale": "element owner",
                }
            ],
            "missingRepos": [],
            "noCode": [],
            "spanRationale": "one element",
        }
        items = [{"id": "a", "element": "Queue"}]
        live = {"repos": [{"name": "Product-existing", "path": str(repo)}]}

        def check() -> tuple[dict, list]:
            path.write_text(json.dumps(value))
            return accept_placement(
                path, schema, items, live, {}, config, control, arch, marketing
            )

        assert check()[0]["placements"][0]["itemIds"] == ["a"]
        for ids in (["a", "a"], [], ["unknown"]):
            value["placements"][0]["itemIds"] = ids
            try:
                check()
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted invalid coverage: {ids}")
        value["placements"][0]["itemIds"] = ["a"]
        for bad in (control, arch.parent, marketing / "marketing-ui"):
            value["placements"][0]["repoPath"] = str(bad)
            live["repos"][0]["path"] = str(bad)
            try:
                check()
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted forbidden path: {bad}")
        assert app_space("Product-new", config) == "product"
        print("PASS: exact coverage, empty span and prohibited repository rejection")

        missing = {
            "name": "Product-existing",
            "template": "service",
            "purpose": "queue",
            "itemIds": ["a"],
        }
        result = create_repositories(
            {"missingRepos": [missing]}, CreationFacts(repo), config, root
        )
        assert result["created"][0]["existed"] and not result["failures"]
        missing["name"] = "Product-new"
        result = create_repositories(
            {"missingRepos": [missing]}, CreationFacts(repo), config, root
        )
        assert result["failures"][0]["ownerFact"] is True
        print(
            "PASS: interrupted creation reuses inventory; failed auth produces owner fact"
        )

        view = arch / "arc42/view.md"
        view.parent.mkdir()
        view.write_text("view")
        trd = root / "trd.md"
        trd.write_text("---\ndecisionIds: [view.md#one]\n---\nTechnical requirement")
        assert document(trd, arch)[0] == ["view.md#one"]
        view.unlink()
        try:
            document(trd, arch)
        except ValueError as exc:
            assert "view.md#one" in str(exc)
        else:
            raise AssertionError("missing citation accepted on reread")
        print(
            "PASS: TRD citations resolve within architecture and are checked again on reuse"
        )


if __name__ == "__main__":
    main()
