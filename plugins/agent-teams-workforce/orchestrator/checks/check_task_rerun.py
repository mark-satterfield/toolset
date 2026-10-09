"""Bounded pure checks for Task reruns; no pipeline, tracker or agent is run."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "scripts/portfolio"))
sys.path.insert(0, str(PLUGIN))

import beadwrite  # noqa: E402 - plugin-local imports
from beadgraph import Bead  # noqa: E402 - plugin-local imports
from orchestrator.flows.task_decomposition import task_inputs  # noqa: E402 - plugin-local imports
from orchestrator.flows import task_state  # noqa: E402 - plugin-local imports


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def check() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        repo = str(work / "repo")
        save(
            work / "repo-scoping.json",
            {"placements": [{"repoPath": repo, "itemIds": ["D1", "D2"]}], "noCode": []},
        )
        save(
            work / "delta-items.json",
            {
                "items": [
                    {"id": "D1", "element": "service", "requires": ["D2"]},
                    {"id": "D2", "element": "layer", "requires": []},
                ]
            },
        )
        save(
            work / "story-repo.json",
            {"title": "Story", "description": "Build", "decisionIds": []},
        )
        for name in [
            "spec-repo.md",
            "spec-repo.data-model.md",
            "spec-repo.criteria.md",
        ]:
            (work / name).write_text("Specification", encoding="utf-8")
        task = {
            "key": "T1",
            "title": "Build service",
            "description": "Implement service",
            "requirementIds": ["D1"],
        }
        score = {
            "key": "T1",
            "jobSize": 2,
            "sizeLow": 1,
            "sizeHigh": 3,
            "sizeConfidence": 80,
        }
        save(
            work / "tasks-repo.json", {"tasks": [task], "scores": [score], "edges": []}
        )
        inputs = task_inputs(work, "repo", ui=False)
        save(
            work / "tasks-repo.json.meta.json",
            {
                "inputs": [
                    {
                        "path": path,
                        "kind": "file",
                        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    }
                    for path in inputs
                ]
            },
        )
        assert beadwrite.tasks_inputs(work, slug="repo", root=work)["unchanged"]
        (work / "spec-repo.md").write_text("Changed specification", encoding="utf-8")
        assert not beadwrite.tasks_inputs(work, slug="repo", root=work)["unchanged"]
        planned = beadwrite.plan_story_tasks(work, slug="repo", repo=repo, root=work)
        assert planned["uncited"] == ["D2"]
        correction = work / "correction.json"
        save(
            correction,
            {
                "tasks": [
                    {
                        **task,
                        "key": "N1",
                        "title": "Build layer",
                        "requirementIds": ["D2"],
                    }
                ],
                "edges": [],
                "scores": [{**score, "key": "N1"}],
            },
        )
        beadwrite.add_corrective_tasks(work, slug="repo", correction=correction)
        planned = beadwrite.plan_story_tasks(work, slug="repo", repo=repo, root=work)
        assert not planned["uncited"] and not planned["unsized"]
        assert planned["tasks"][0]["key"] == "T2"  # prerequisite precedes service
        print("PASS: input fingerprints and placed prerequisite coverage/correction")

        story = {
            "id": "story",
            "title": "Story",
            "issue_type": "story",
            "status": "open",
            "metadata": {"elab_key": "story:repo"},
        }
        records = []
        for key, status, metadata in [
            ("unstarted", "open", {}),
            ("blocked", "blocked", {}),
            ("started", "in_progress", {}),
            ("closed", "closed", {}),
            ("deferred", "deferred", {}),
            ("stopped", "open", {"build_stop_stage": "red"}),
            ("audited", "open", {"cds_audit_result": "passed"}),
        ]:
            records.append(
                {
                    "id": key,
                    "title": key,
                    "issue_type": "task",
                    "status": status,
                    "metadata": {"elab_key": f"task:repo:{key}", **metadata},
                }
            )

        class Writer:
            repo = work
            dry_run = False
            planned = []

            def bd(self, args: list[str], stdin: str | None = None) -> str:
                self.planned.append(args)
                return ""

        writer = Writer()
        with patch.object(
            beadwrite,
            "children",
            side_effect=lambda _, parent, kind: [story] if kind == "story" else records,
        ):
            result = beadwrite.replace_tasks(
                writer, "epic", slug="repo", reason="changed"
            )
        assert {x["id"] for x in result["deleted"]} == {"unstarted", "blocked"}
        assert {x["id"] for x in result["kept"]} == {
            "started",
            "closed",
            "deferred",
            "stopped",
            "audited",
        }
        print(
            "PASS: changed inputs delete only unstarted; started/closed/deferred/build facts survive"
        )

        saved = beadwrite.plan_tasks(work, None, "repo", repo)
        existing = Bead(
            "task-existing",
            saved[0].title,
            "task",
            "open",
            "story",
            {"elab_key": saved[0].elab_key},
            (),
        )
        writer.planned = []
        task_record = {
            "id": existing.id,
            "title": existing.title,
            "issue_type": "task",
            "status": "open",
            "metadata": existing.metadata,
        }
        with (
            patch.object(
                beadwrite,
                "children",
                side_effect=lambda _, parent, kind: (
                    [story] if kind == "story" else [task_record]
                ),
            ),
            patch.object(
                beadwrite,
                "_refresh",
                side_effect=AssertionError("existing Task changed"),
            ),
        ):
            result = beadwrite.write_task(
                writer,
                "epic",
                work,
                slug="repo",
                repo=repo,
                key=saved[0].key,
                root=work,
                missing_only=True,
            )
        assert result["task"]["action"] == "unchanged" and not writer.planned

        class CreatingWriter(Writer):
            def create(self, args: list[str], key: str) -> str:
                self.planned.append(args)
                return "task-missing"

        writer = CreatingWriter()
        writer.planned = []
        with patch.object(
            beadwrite,
            "children",
            side_effect=lambda _, parent, kind: (
                [story] if kind == "story" else [task_record]
            ),
        ):
            result = beadwrite.write_task(
                writer,
                "epic",
                work,
                slug="repo",
                repo=repo,
                key=saved[1].key,
                root=work,
                missing_only=True,
            )
        assert result["task"]["action"] == "created" and len(writer.planned) == 1
        print(
            "PASS: unchanged inputs preserve existing Tasks and create only missing Tasks"
        )

        outgoing = Bead(
            "outside", "outside", "task", "open", "other-story", {}, ("old",)
        )
        old = Bead(
            "old",
            "old",
            "task",
            "open",
            "story",
            {"elab_key": "task:repo:old", "requirement_ids": '["D1"]'},
            (),
        )
        new = Bead(
            "new",
            "new",
            "task",
            "open",
            "story",
            {"elab_key": "task:repo:new", "requirement_ids": '["D1"]'},
            (),
        )
        graph = SimpleNamespace(beads={"outside": outgoing, "old": old})

        class FakeTools:
            def operation(self, stage, action):
                return action()

            def portfolio(self, module, function, *args, **kwargs):
                if function == "task_started":
                    return beadwrite.task_started(args[0])
                if function == "replace_tasks":
                    graph.beads.pop("old", None)
                return None

            def bd(self, args, **kwargs):
                assert args == ["dep", "add", "outside", "new", "--type", "blocks"]
                self.added = True

        tools = FakeTools()
        with (
            patch.object(task_state, "env_path", return_value=work),
            patch.object(
                task_state,
                "snapshot",
                side_effect=lambda *_: (
                    graph,
                    SimpleNamespace(id="story"),
                    [b for b in graph.beads.values() if b.parent == "story"],
                ),
            ),
        ):
            first = task_state.replace(tools, "epic", "repo", work, "changed")
            resumed = task_state.replace(tools, "epic", "repo", work, "changed")
            assert first["incoming"] == resumed["incoming"] and resumed["deleted"]
            graph.beads["new"] = new
            assert not task_state.repoint(tools, "epic", "repo", work)
            assert tools.added
        print(
            "PASS: replacement journal survives interruption and re-points external blockers"
        )


if __name__ == "__main__":
    check()
