"""Check one elaboration dispatch: the journal it creates and the result it assembles from it.

No agent, workflow or pipeline is started: sessions are stand-ins, and the Epic's claim, beads and
the push are stood in. A dispatch creates the Epic's journal with every outermost step, runs it,
and reports from the journal; a second dispatch runs no earlier step again and reports the same.
The check also covers the result a finished journal gives, and the items the span step reads
from the matrix.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))

from driver_surface_types import ARCH_PATH_ENV, CONTROL_REPO_ENV, HEADLESSENV_MODULE, STOP_FILE_ENV, HeadlessEnvironment
from matrix_contract import Matrix, Node, NodeId
from orchestrator.checks.architecture_bench import BEAD, STAMP, ArchBench
from orchestrator.checks.architecture_standins import Scenario, install
from orchestrator.checks.check_architecture_flow import OUTERMOST
from orchestrator.checks.check_support import report, require
from orchestrator.core import step_journal as sj
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import load_artifactio
from orchestrator.core.driver_contracts import driver_module
from orchestrator.core.handback_contract import PASSED_PHASE, TRD_PHASE, wire_result
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import value_artifact
from orchestrator.core.manifest import manifest_path
from orchestrator.flows import prd_to_spec
from orchestrator.flows.elaboration_result import journal_result
from orchestrator.flows.elaboration_steps import LIFECYCLE_DONE, SPEC_RESULT, TASKS_RESULT
from orchestrator.flows.elaboration_support import FINISH_PHASE
from orchestrator.flows.repo_scoping import ARTIFACT_REPOSITORIES, SPAN, span_items
from typeguard import check_type

if TYPE_CHECKING:
    from orchestrator.core.artifact_contract import ArtifactProducer
    from orchestrator.core.models import RunContext
    from orchestrator.core.tools import Tools
    from step_journal_contract import Journal, Step, StepPlan
    from target_contract import DeltaItem

REPOSITORY: Final = "/repositories/Product-auth-service"
EMITTED: Final = 3


def _lifecycle(_context: RunContext, _tools: Tools, _stage: str, operation: object, /, **facts: object) -> object:
    """Stand in for the Epic's claim and its release: no bead is read or written.

    Returns:
        A granted claim for the start, and an empty record for any other lifecycle operation.

    """
    return (
        {"ok": True, "owner": facts.get("owner", "check")}
        if getattr(operation, "__name__", "") == "start"
        else {"ok": True}
    )


def check_dispatch(root: Path, module: ArtifactProducer) -> None:
    """Check two dispatches of one Epic: the journal, the report, and nothing run twice."""
    bench: ArchBench = ArchBench(root / "dispatch", module)
    install(bench, Scenario(work=False))
    with patch.dict(os.environ, bench.environment()), patch.object(prd_to_spec, "lifecycle", _lifecycle):
        first, second = (
            prd_to_spec.elaborate(bench.context, bench.agents.store, bench.agents, bench.tools, []) for _ in range(2)
        )
    journal: Journal = bench.journal()
    require([step["description"] for step in journal["steps"]] == OUTERMOST, "the journal has every outermost step")
    require(journal["pipeline"] == "elaboration" and journal["beadType"] == "epic", "an Epic's elaboration journal")
    require(first["ok"] is False and json_object(first["failure"])["stage"] == SPAN, f"the span step failed: {first}")
    require(json_object(first["artifacts"])["phases"] == {TRD_PHASE: PASSED_PHASE}, "the TRD phase is reported")
    require(first["repoSpan"] == [] and first["beadsEmitted"] == 0 and first["lifecycleDone"] is False, "no bead yet")
    require(all(count == 1 for count in bench.counts.values()), f"the second dispatch ran no session: {bench.counts}")
    require(second["artifacts"] == first["artifacts"] and second["stage"] == first["stage"], "the same report again")
    following: Step | None = sj.next_step(journal)
    require(following is not None and following.get("script") == SPAN, "the journal stands at the span step")
    wire_result(first)
    require(manifest_path(bench.work).is_file(), "the run record is written")
    report("PASS: a dispatch creates the journal, reports from it, and a second dispatch repeats no step")


def check_finished_report(bench_root: Path, module: ArtifactProducer) -> None:
    """Check the report a finished journal gives: Stories, Tasks, the span and the lifecycle mark."""
    bench: ArchBench = ArchBench(bench_root / "finished", module)
    plans: list[StepPlan] = [{"description": "Everything", "purpose": "A finished run", "script": "check.everything"}]
    journal: Journal = sj.new_journal(BEAD, "epic", "elaboration", plans)
    step = journal["steps"][0]["id"]
    story: dict[str, JsonValue] = {"id": "ssbd-arch.1.1", "elabKey": "story:auth", "repoPath": REPOSITORY}
    sj.start_step(journal, step, STAMP.at)
    for artifact in (
        value_artifact(ARTIFACT_REPOSITORIES, [REPOSITORY]),
        value_artifact(SPEC_RESULT, {"ok": True, "story": story, "specPaths": []}),
        value_artifact(TASKS_RESULT, {"ok": True, "repoPath": REPOSITORY, "tasks": [{"id": "t1"}, {"id": "t2"}]}),
        value_artifact(LIFECYCLE_DONE, True),
    ):
        sj.record_artifact(journal, step, artifact)
    sj.finish_step(journal, step, STAMP.at)
    result: dict[str, JsonValue] = journal_result(journal, bench.context)
    require(result["ok"] is True and result["stage"] == FINISH_PHASE and result["lifecycleDone"] is True, "finished")
    require(result["repoSpan"] == [REPOSITORY] and result["beadsEmitted"] == EMITTED, f"the span and beads: {result}")
    require(json_object(result["artifacts"])["phases"] == {"spec:auth": PASSED_PHASE}, "the spec phase by its slug")
    require(json_object(result["hierarchy"])["stories"] == [story], "the Stories come from the journal")
    report("PASS: a finished journal gives the span, the Stories, the Tasks and the lifecycle mark")


def _node(key: str, kind: str, name: str, **fields: object) -> tuple[NodeId, Node]:
    """Build one matrix row for the span check.

    Returns:
        The row's id and the row.

    """
    node: dict[str, object] = {"id": key, "kind": kind, "name": name, "links": [], "changed": STAMP.change(), **fields}
    return NodeId(key), check_type(node, Node)


def check_span_items() -> None:
    """Check the items the span step reads: realized elements and what they depend on, unless built."""
    handler: str = "component:auth/auth/handler"
    table: str = "infrastructure:infra/infra/table"
    done: str = "library:lib/@repository/lib"
    rows: list[tuple[NodeId, Node]] = [
        _node(f"prd:{BEAD}", "prd", "PRD", links=[{"type": "needs", "to": "feature:proof"}]),
        _node("feature:proof", "feature", "Proof", featureType="prd", links=[{"type": "realizedBy", "to": handler}]),
        _node(
            handler,
            "component",
            "Handler",
            repository="Product-auth-service",
            code={"state": "none"},
            links=[{"type": "dependsOn", "to": table}, {"type": "dependsOn", "to": done}],
        ),
        _node(table, "infrastructure", "Table", repository="Product-identity-infra", code={"state": "legacy"}),
        _node(done, "library", "Library", repository="shared-lib", code={"state": "built"}),
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
    parser.add_argument("--artifact-script", required=True, type=Path)
    options: argparse.Namespace = parser.parse_args()
    script: Path = options.artifact_script
    module: ArtifactProducer = load_artifactio(script)
    directory: str
    with tempfile.TemporaryDirectory() as directory:
        root: Path = Path(directory).resolve()
        (root / "config").mkdir()
        values: dict[str, str] = {
            "CLAUDE_CONFIG_DIR": str(root / "config"),
            CONTROL_REPO_ENV: str(script.resolve().parents[2]),
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
                check_dispatch(root, module)
                check_finished_report(root, module)
                check_span_items()


if __name__ == "__main__":
    main()
