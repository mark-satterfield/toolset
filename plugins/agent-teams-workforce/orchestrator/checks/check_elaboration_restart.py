"""Check that the steps after the TRD restart where they stopped, and rerun from an invalidated step only.

No agent, workflow or pipeline is started: sessions are stand-ins, and beads, the matrix read, the
repository inventory and the Epic's lifecycle are stood in. The span has two repositories, one of
them a frontend repository.

One run stops after every step and starts again with a new runner: every step's code and every
session runs once, and every Story and Task bead is created once. Then a step in the middle of
the spec steps, and one in the middle of the Task steps, is invalidated: that step and the later
ones run again, nothing earlier does, and no second bead is created. A second run fails every
step once before it runs: each step runs exactly twice, so a restart begins at the step that
failed. That run's review has a finding for each author, a disputed finding and a ruling, each
as its own step.
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
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.checks.elaboration_bench import SERVICE, WEB, ElabBench, Script, descriptions, require_done
from orchestrator.core import step_journal as sj
from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import driver_module
from orchestrator.core.journal_run import concurrent_group
from orchestrator.flows.elaboration_files import (
    AUTHOR_CONTRACTS,
    AUTHOR_CRITERIA,
    AUTHOR_DATA_MODEL,
    DECIDER,
    DECOMPOSER,
    EDGE_CLOSURE,
    EDGE_LISTING,
    EDGE_WRITE,
    EDGES_CONTAINER,
    MAPPER,
    REVIEWER,
    SPEC_CONTEXT,
    SPECS_CONTAINER,
    STORY_DOCUMENT_STEP,
    STORY_WRITE,
    TASK_CONTEXT,
    TASK_PLAN,
    TASK_RECORD,
    TASK_RETIRE,
    TASK_WRITE,
    TASKS_CONTAINER,
    UI_APPEND,
    UI_BUNDLES,
    UI_NORMALIZE,
)
from orchestrator.flows.spec_review import DROPPED, FINDINGS, UPHELD
from spec_review_contract import DOCUMENT_CRITERIA, DOCUMENT_DATA_MODEL, DOCUMENT_SPEC

if TYPE_CHECKING:
    from step_journal_contract import Journal, Step, StepId

TWICE: Final = 2
AUTHORED: Final[list[str]] = [AUTHOR_CONTRACTS, AUTHOR_DATA_MODEL, AUTHOR_CRITERIA]
ENDING: Final[list[str]] = [STORY_DOCUMENT_STEP, STORY_WRITE]
WRITTEN: Final[list[str]] = [TASK_WRITE, TASK_RETIRE, TASK_RECORD]


def later_steps(journal: Journal) -> list[Step]:
    """List the steps of the journal from the Specs and Stories container on that have no child steps.

    Returns:
        The steps in walk order.

    """
    names: list[str] = [step["description"] for step in journal["steps"]]
    return [
        step
        for outermost in journal["steps"][names.index(SPECS_CONTAINER) :]
        for step in sj.steps_in_order_from(outermost)
        if not step["steps"]
    ]


def runs(bench: ElabBench, step: Step) -> int:
    """Count how often a step ran.

    Returns:
        The runs of a script step's code, or the sessions launched for an agent step.

    """
    return bench.counts[step["id"]] if "script" in step else bench.launches(step["id"])


def under(bench: ElabBench, container: str, repository: str) -> list[Step]:
    """List the steps of one repository under one container.

    Returns:
        The steps in the order they run.

    """
    found: list[Step] = [step for step in bench.step(container)["steps"] if step["description"] == repository]
    require(len(found) == 1, f"{container} has {len(found)} containers named {repository}")
    return found[0]["steps"]


def require_beads(bench: ElabBench, tasks: int) -> None:
    """Require one Story per repository, the Tasks expected, and no bead created twice."""
    require(len(bench.beads.of_kind("story")) == len(bench.repositories), "one Story per repository")
    require(len(bench.beads.of_kind("task")) == tasks, f"{tasks} Tasks: {len(bench.beads.of_kind('task'))}")
    require(all(count == 1 for count in bench.beads.created.values()), f"a bead twice: {bench.beads.created}")


def check_invalidation(bench: ElabBench, target: Step) -> None:
    """Invalidate one step of a finished journal and run it: that step and the later ones run, nothing earlier."""
    journal: Journal = bench.journal()
    order: list[StepId] = [step["id"] for step in sj.steps_in_order(journal)]
    before: dict[StepId, int] = {step["id"]: runs(bench, step) for step in later_steps(journal)}
    earlier: set[StepId] = set(order[: order.index(target["id"])])
    held: set[str] = set(bench.beads.records)
    sj.update_journal(bench.path, lambda changed: sj.invalidate_from(changed, target["id"], sj.timestamp()))
    with bench.patched():
        bench.runner().run()
    require_done(bench)
    for step in later_steps(bench.journal()):
        ran: int = runs(bench, step)
        expected: int = before.get(step["id"], 0) + (0 if step["id"] in earlier else 1)
        require(ran == expected, f"{step['description']} ran {ran} times, not {expected}")
    require(set(bench.beads.records) == held, "the same beads after the invalidated steps ran again")
    require(all(count == 1 for count in bench.beads.created.values()), f"a bead twice: {bench.beads.created}")


def check_stops(root: Path) -> None:
    """Check a run that stops after every step, then two invalidations of the finished journal."""
    bench: ElabBench = ElabBench(root / "stops")
    with bench.patched():
        while bench.runner().run_next():
            pass
    require_done(bench)
    journal: Journal = bench.journal()
    for step in later_steps(journal):
        require(runs(bench, step) == 1, f"{step['description']} ran {runs(bench, step)} times, not once")
    require_beads(bench, tasks=len(bench.repositories))
    service: list[str] = descriptions(under(bench, SPECS_CONTAINER, SERVICE))
    require(service == [SPEC_CONTEXT, *AUTHORED, REVIEWER, *ENDING], f"the service repository's spec steps: {service}")
    web: list[str] = descriptions(under(bench, SPECS_CONTAINER, WEB))
    frontend: list[str] = [
        SPEC_CONTEXT,
        UI_BUNDLES,
        AUTHOR_CONTRACTS,
        UI_NORMALIZE,
        AUTHOR_CONTRACTS,
        AUTHOR_DATA_MODEL,
    ]
    require(web == [*frontend, UI_APPEND, AUTHOR_CRITERIA, REVIEWER, *ENDING], f"the frontend's spec steps: {web}")
    tasks: list[str] = descriptions(under(bench, TASKS_CONTAINER, SERVICE))
    require(tasks == [TASK_CONTEXT, DECOMPOSER, TASK_PLAN, *WRITTEN], f"the service repository's Task steps: {tasks}")
    edges: list[str] = descriptions(bench.step(EDGES_CONTAINER)["steps"])
    require(edges == [EDGE_CLOSURE, EDGE_LISTING, MAPPER, EDGE_WRITE], f"the Task edge steps: {edges}")
    blocked: list[object] = [task["dependencies"] for task in bench.beads.of_kind("task")]
    require(sum(1 for held in blocked if held) == 1, f"one Task is blocked by another Story's Task: {blocked}")
    report("PASS: a run that stops after every step runs each step and each session once, and writes each bead once")
    check_invalidation(bench, bench.step(f"Write the acceptance criteria of {SERVICE}"))
    check_invalidation(bench, bench.step(f"Decompose the Story of {SERVICE} into Tasks"))
    report("PASS: an invalidated step and the later ones run again, nothing earlier does, and no second bead is made")


def check_failures(root: Path) -> None:
    """Check a run in which every step after the TRD fails once: each runs exactly twice.

    The review of the service repository has a finding per author, a dispute and a ruling, and
    the frontend's first decomposition leaves its item uncited.
    """
    script: Script = Script(
        findings=[("F1", DOCUMENT_SPEC, "I1"), ("F2", DOCUMENT_DATA_MODEL, "I2"), ("F3", DOCUMENT_CRITERIA, "A5")],
        disputes={DOCUMENT_DATA_MODEL: ["F2"]},
        upheld=["F2"],
        gap=True,
    )
    bench: ElabBench = ElabBench(root / "failures", script=script)
    with bench.patched():
        bench.run_architecture()
        while (following := sj.next_step(bench.journal())) is not None:
            group: list[StepId] = concurrent_group(bench.journal(), following["id"])
            bench.fail_once.update(group)
            with expected_error(Exception):
                bench.runner().run_next()
            stopped: Step | None = sj.next_step(bench.journal())
            require(stopped is not None and stopped["id"] == following["id"], "the journal stands at the failed step")
            require(stopped is not None and stopped["status"] == "failed", "the failure is recorded on the step")
            require(bench.runner().run_next(), "the next dispatch runs the failed step")
    require_done(bench)
    for step in later_steps(bench.journal()):
        require(runs(bench, step) == TWICE, f"{step['description']} ran {runs(bench, step)} times, not twice")
    require_beads(bench, tasks=len(bench.repositories) + 1)
    report("PASS: every step that fails once runs exactly twice; a restart begins at the step that failed")
    steps: list[Step] = under(bench, SPECS_CONTAINER, SERVICE)
    corrections: list[str] = [AUTHOR_CONTRACTS, AUTHOR_DATA_MODEL, AUTHOR_CRITERIA]
    revisions: list[str] = [AUTHOR_DATA_MODEL, AUTHOR_CRITERIA]
    expected: list[str] = [SPEC_CONTEXT, *AUTHORED, REVIEWER, *corrections, DECIDER, *revisions, *ENDING]
    require(descriptions(steps) == expected, f"the review's steps: {descriptions(steps)}")
    reviewed: Step = steps[expected.index(REVIEWER)]
    values: dict[str, object] = {
        held["name"]: held["value"] for held in reviewed["artifacts"] if held["kind"] == "value"
    }
    kept: list[dict[str, str]] = [
        {"id": "F1", "document": DOCUMENT_SPEC},
        {"id": "F2", "document": DOCUMENT_DATA_MODEL},
    ]
    require(values[FINDINGS] == kept and values[DROPPED] == ["F3"], f"the findings the review holds: {values}")
    ruled: Step = steps[expected.index(DECIDER)]
    upheld: list[object] = [
        held["value"] for held in ruled["artifacts"] if held["kind"] == "value" and held["name"] == UPHELD
    ]
    require(upheld == [["F2"]], f"the ruling upholds the disputed finding: {upheld}")
    require(
        ruled.get("inputs", [])[-1] == steps[expected.index(DECIDER) - 1]["id"],
        "the last correction plans the ruling",
    )
    plans: list[str] = descriptions(under(bench, TASKS_CONTAINER, WEB))
    gap: list[str] = [TASK_CONTEXT, DECOMPOSER, TASK_PLAN, DECOMPOSER, TASK_PLAN, TASK_WRITE, *WRITTEN]
    require(plans == gap, f"the frontend's Task steps with a correction: {plans}")
    report("PASS: a finding, each author's correction, the ruling and each revision are steps the step before plans")


def main() -> None:
    """Run the restart checks in a temporary directory with stand-in sessions."""
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
                check_stops(root)
                check_failures(root)


if __name__ == "__main__":
    main()
