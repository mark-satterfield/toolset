"""Check one elaboration dispatch from the open-run step to the Epic's mark, and the result it assembles.

No agent, workflow or pipeline is started: sessions are stand-ins, and beads, the matrix read, the
repository inventory, the push and the Epic's lifecycle are stood in. One dispatch of a small Epic
creates the Epic's journal, runs every step and reports the Story and the Tasks from the journal;
the Story and each Task have a journal of their own whose first step is done and holds the files
their later steps are handed. A second dispatch on the finished journal launches no session and
makes no bead call, and reports the same. The check also covers the items the span step reads
from the matrix.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))

from driver_surface_types import ARCH_PATH_ENV, CONTROL_REPO_ENV, HEADLESSENV_MODULE, STOP_FILE_ENV, HeadlessEnvironment
from orchestrator.checks.architecture_bench import BEAD, STAMP
from orchestrator.checks.check_architecture_flow import OUTERMOST
from orchestrator.checks.check_support import report, require
from orchestrator.checks.elaboration_bench import SERVICE, ElabBench, matrix_node, require_done
from orchestrator.core import step_journal as sj
from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import driver_module
from orchestrator.core.handback_contract import PASSED_PHASE, TRD_PHASE, wire_result
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.manifest import manifest_path
from orchestrator.flows import prd_to_spec
from orchestrator.flows.architecture_files import ARTIFACT_TRD
from orchestrator.flows.elaboration_files import (
    CRITERIA,
    DATA_MODEL,
    SPEC,
    STORY_DOCUMENT,
    TASK_KEY,
    TASKS_FILE,
    objects,
)
from orchestrator.flows.elaboration_support import FINISH_PHASE
from orchestrator.flows.repo_scoping import span_items
from step_journal_contract import BEAD_TYPE_STORY, BEAD_TYPE_TASK, PIPELINE_BUILD, PIPELINE_DEPLOY, BeadId

if TYPE_CHECKING:
    from matrix_contract import Matrix, Node, NodeId
    from step_journal_contract import Journal
    from target_contract import DeltaItem

HANDED: list[str] = [SPEC, DATA_MODEL, CRITERIA, ARTIFACT_TRD, STORY_DOCUMENT]
"""The files a Story's later steps are handed, by artifact name."""


def require_child_journal(bench: ElabBench, bead: str, bead_type: str, pipeline: str, names: list[str]) -> None:
    """Require the journal of a Story or a Task: its kind, its pipeline, and a done first step with its files."""
    journal: Journal = sj.read_journal(sj.journal_path(bench.path.parent, BeadId(bead)))
    require((journal["beadType"], journal["pipeline"]) == (bead_type, pipeline), f"the journal of {bead}: {journal}")
    first = journal["steps"][0]
    require(first["status"] == "done", f"the first step of {bead}'s journal is done")
    held: list[str] = [artifact["name"] for artifact in first["artifacts"]]
    require(held == names, f"the first step of {bead}'s journal holds {held}, not {names}")
    for artifact in first["artifacts"]:
        if artifact["kind"] != "value":
            require(Path(artifact["path"]).is_file(), f"{artifact['name']} of {bead} is a file that exists")


def check_dispatch(root: Path) -> None:
    """Check two dispatches of one small Epic: every step, the report, the journals, and nothing run twice."""
    bench: ElabBench = ElabBench(root / "dispatch", repositories=(SERVICE,))
    with bench.patched():
        first: dict[str, JsonValue] = prd_to_spec.elaborate(bench.context, bench.agents, bench.tools, [])
        done: tuple[int, int, int] = (len(bench.sessions.calls), len(bench.beads.calls), len(bench.tools.calls))
        second: dict[str, JsonValue] = prd_to_spec.elaborate(bench.context, bench.agents, bench.tools, [])
        again: tuple[int, int, int] = (len(bench.sessions.calls), len(bench.beads.calls), len(bench.tools.calls))
    journal: Journal = bench.journal()
    require([step["description"] for step in journal["steps"]] == OUTERMOST, "the journal has every outermost step")
    require(journal["pipeline"] == "elaboration" and journal["beadType"] == "epic", "an Epic's elaboration journal")
    require_done(bench)
    require(first["ok"] is True and first["stage"] == FINISH_PHASE and first["lifecycleDone"] is True, f"done: {first}")
    hierarchy: dict[str, JsonValue] = json_object(first["hierarchy"])
    stories: list[dict[str, JsonValue]] = objects(hierarchy["stories"])
    tasks: list[dict[str, JsonValue]] = objects(hierarchy["tasks"])
    beads: list[str] = [str(record["id"]) for record in bench.beads.of_kind("story")]
    require([story["id"] for story in stories] == beads, f"the Story comes from the journal: {stories}")
    written: list[str] = [str(record["id"]) for record in bench.beads.of_kind("task")]
    require(
        [task["id"] for task in tasks] == written and len(written) == 1,
        f"the Task comes from the journal: {tasks}",
    )
    require(first["beadsEmitted"] == len(beads) + len(written), "the beads emitted are the Story and its Task")
    require(first["repoSpan"] == [str(bench.paths[SERVICE])], f"the repository span: {first['repoSpan']}")
    slug: str = str(stories[0]["elabKey"]).removeprefix("story:")
    phases: JsonValue = json_object(first["artifacts"])["phases"]
    require(phases == {TRD_PHASE: PASSED_PHASE, f"spec:{slug}": PASSED_PHASE}, f"the phases reported: {phases}")
    require("closureEdges" in first and "crossStoryDependencies" in first and "storyEdges" in first, "the edges")
    wire_result(first)
    require(manifest_path(bench.work).is_file(), "the run record is written")
    require_child_journal(bench, beads[0], BEAD_TYPE_STORY, PIPELINE_DEPLOY, HANDED)
    require_child_journal(bench, written[0], BEAD_TYPE_TASK, PIPELINE_BUILD, [*HANDED, TASKS_FILE, TASK_KEY])
    report("PASS: one dispatch runs every step, reports the Story and the Task, and creates their journals")
    require(again == done, f"the second dispatch launched a session or called beads or a tool: {done} then {again}")
    same: tuple[str, ...] = ("ok", "stage", "hierarchy", "beadsEmitted", "artifacts", "repoSpan", "lifecycleDone")
    require(all(second[name] == first[name] for name in same), "the second dispatch reports the same")
    report("PASS: a dispatch on a finished journal launches no session, makes no bead call and reports the same")


def check_span_items() -> None:
    """Check the items the span step reads: realized elements and what they depend on, unless built."""
    handler: str = "component:auth/auth/handler"
    table: str = "infrastructure:infra/infra/table"
    done: str = "library:lib/@repository/lib"
    rows: list[tuple[NodeId, Node]] = [
        matrix_node(f"prd:{BEAD}", "prd", "PRD", links=[{"type": "needs", "to": "feature:proof"}]),
        matrix_node(
            "feature:proof",
            "feature",
            "Proof",
            featureType="prd",
            links=[{"type": "realizedBy", "to": handler}],
        ),
        matrix_node(
            handler,
            "component",
            "Handler",
            repository="Product-auth-service",
            code={"state": "none"},
            links=[{"type": "dependsOn", "to": table}, {"type": "dependsOn", "to": done}],
        ),
        matrix_node(table, "infrastructure", "Table", repository="Product-identity-infra", code={"state": "legacy"}),
        matrix_node(done, "library", "Library", repository="shared-lib", code={"state": "built"}),
    ]
    matrix: Matrix = {
        "version": 3,
        "documentsSyncedAt": {"vaultCommit": "", "at": STAMP.at, "dirtyPaths": []},
        "resourceTypes": [],
        "nodes": dict(rows),
    }
    items: list[DeltaItem] = span_items(matrix, BEAD)
    require([item["element"] for item in items] == ["Handler", "Table"], f"built code is not built again: {items}")
    require(items[0].get("requires") == [items[1]["id"]] and items[1].get("requiredBy") == [items[0]["id"]], "requires")
    require([item.get("repository") for item in items] == ["Product-auth-service", "Product-identity-infra"], "placed")
    report("PASS: the span's items are the realized elements and what they depend on, each in its repository")


def main() -> None:
    """Run the dispatch checks in a temporary directory with stand-in sessions."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-repo", required=True, type=Path)
    options: argparse.Namespace = parser.parse_args()
    control: Path = options.control_repo
    # The driver's modules read the installed plugin, so they are loaded before the check's own
    # configuration directory takes the place of the real one.
    with patch.dict(os.environ, {CONTROL_REPO_ENV: str(control.resolve())}):
        driver_module(HEADLESSENV_MODULE)
    directory: str
    with tempfile.TemporaryDirectory() as directory:
        root: Path = Path(directory).resolve()
        (root / "config").mkdir()
        values: dict[str, str] = {
            "CLAUDE_CONFIG_DIR": str(root / "config"),
            CONTROL_REPO_ENV: str(control.resolve()),
            "ATW_ORCH_SESSIONS": "4",
        }
        with (
            patch.dict(os.environ, values),
            patch.object(AgentRunner, "_version", lambda _runner: None),
            patch("beadgraph.write_metadata", lambda _bead, _pairs, _control: None),
        ):
            for name in (ARCH_PATH_ENV, STOP_FILE_ENV):
                os.environ.pop(name, None)
            headless: object = driver_module(HEADLESSENV_MODULE)
            with patch.object(
                headless,
                HeadlessEnvironment.child_env.__name__,
                side_effect=lambda _scratch: dict(os.environ),
            ):
                check_dispatch(root)
                check_span_items()


if __name__ == "__main__":
    main()
