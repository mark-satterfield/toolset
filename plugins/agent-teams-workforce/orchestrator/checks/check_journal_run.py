"""Run step journals end to end with stand-in sessions; never start an agent, a workflow or a pipeline.

A stand-in takes the place of the session process: it reads the brief the runner sent, writes the
output and, where the scenario says so, edits the journal as an agent session would with
``atw-step-journal``. Everything else is the code the pipeline runs: the journal runner, the
registries, the session entry of the agent runner and the step journal. The checks cover a whole
run and its final journal; a restart at every step boundary after a failure and after a kill;
invalidation from a step that planned other steps and from a step in the middle; an agent that
starts helpers in its own session, complete and interrupted; steps that run together; a failed
step and a stopped one; a resumed session and one whose conversation is gone; where journals are
held; and the journal of a Story or a Task.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Final
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))

from driver_surface_types import ARCH_PATH_ENV, CONTROL_REPO_ENV, HEADLESSENV_MODULE, STOP_FILE_ENV, HeadlessEnvironment
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.checks.journal_bench import (
    AUTHOR,
    BEAD,
    FINISH,
    OPEN,
    ORDER,
    PLANS,
    TOGETHER,
    Bench,
    Call,
    finish_own,
    start_helpers,
    write_run,
)
from orchestrator.core import pipeline_steps
from orchestrator.core import step_journal as sj
from orchestrator.core.agent_context import PipelineStoppedError
from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import driver_module
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_changes import create_child_journal
from orchestrator.core.journal_run import JournalRunner, concurrent_group
from orchestrator.core.journal_steps import (
    UNDER_CONTAINER,
    UNDER_THIS,
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import StepError
from orchestrator.core.skills import MATRIX_ENV
from step_journal_contract import (
    BEAD_TYPE_STORY,
    BEAD_TYPE_TASK,
    PIPELINE_BUILD,
    PIPELINE_DEPLOY,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PLANNED,
    STATUS_RUNNING,
    BeadId,
    Journal,
    Step,
    StepId,
    StepJournalError,
    StepPlan,
)

HELPED: Final[list[StepPlan]] = [
    {
        "description": "Architecture",
        "purpose": "the architecture is established",
        "steps": [{"description": "Establish the architecture", "purpose": "one agent owns it", "agent": "architect"}],
    },
]
PLACED: Final[list[StepPlan]] = [
    {"description": "Plan the repositories", "purpose": "one container each", "script": "check.plan"},
    {
        "description": "Later",
        "purpose": "work planned while the run goes",
        "steps": [{"description": "Begin", "purpose": "a first child", "script": "check.begin"}],
    },
]
REVIEWED: Final[list[StepPlan]] = [
    {"ref": "scope", "description": "List what is unapproved", "purpose": "reviewers see only that", "script": OPEN},
    {"ref": "r1", "description": "Review one", "purpose": "a check", "agent": "reviewer", "inputs": ["scope"]},
    {"ref": "r2", "description": "Review two", "purpose": "a check", "agent": "reviewer", "inputs": ["scope"]},
    {"ref": "r3", "description": "Review three", "purpose": "a check", "agent": "reviewer", "inputs": ["scope"]},
    {"description": "Review one again", "purpose": "a re-check", "agent": "reviewer", "inputs": ["scope", "r1"]},
    {"description": "Approve", "purpose": "the reviews agree", "script": FINISH, "inputs": ["r1", "r2", "r3"]},
]


def check_whole_run(bench: Bench) -> None:
    """Check a run from an absent journal to a complete one, and what the journal then holds."""
    write_run(bench)
    bench.runner(PLANS).run()
    journal: Journal = bench.journal()
    require(sj.is_complete(journal) and "finished" in journal, "every step is done and the journal is finished")
    require(dict(bench.counts) == dict.fromkeys((*ORDER, "author.accept"), 1), f"each step ran once: {bench.counts}")
    opened: Step = bench.step("Open the run")
    discovered: Step = bench.step("Discover the work")
    written: Step = bench.step("Write the document")
    confirmed: Step = bench.step("Confirm the document")
    require([held["name"] for held in opened["artifacts"]] == ["prd", "matrix row"], "the first step's artifacts")
    require(
        discovered["artifacts"]
        == [
            value_artifact(sj.planned_for_name(written["id"]), {"topic": "journals"}),
            value_artifact(sj.planned_for_name(confirmed["id"]), {}),
        ],
        "the planning step records each step it planned, with that step's parameters",
    )
    require(written.get("inputs") == [opened["id"], discovered["id"]], "a step with parameters names its planner")
    require(confirmed.get("inputs") == [written["id"]], "a ref names the step planned beside it")
    require(
        [step["description"] for step in bench.step("Work")["steps"]]
        == ["Discover the work", "Write the document", "Confirm the document"],
        "planned steps follow the step that planned them, in its container",
    )
    require([held["name"] for held in written["artifacts"]] == ["document", "topic"], "the accepted output")
    call: Call = bench.sessions.calls[0]
    require(not call.resume and written.get("session") == call.session, "the step holds the session it ran in")
    require(list(call.inputs) == ["prd", "step journal"], f"the brief names artifacts by name: {list(call.inputs)}")
    require(call.journal == bench.path, "the brief names the journal file")
    require(call.step == written["id"] and call.request == "Write the document", "the brief's step and request")
    report("PASS: a whole run from an absent journal; artifacts, inputs and the record of each planned step")


def check_restart(root: Path) -> None:
    """Check that a restart begins at exactly the step where the run stopped, at every boundary."""
    index: int
    key: str
    for index, key in enumerate(ORDER):
        failed: Bench = Bench(root / f"failed-{index}")
        write_run(failed)
        failed.fail_once.add(key)
        with expected_error(RuntimeError if key != AUTHOR else StepError):
            failed.runner(PLANS).run()
        stopped: Step | None = sj.next_step(failed.journal())
        require(stopped is not None and stopped["status"] == STATUS_FAILED, f"{key}: the next step is the failed one")
        cause: dict[str, JsonValue] = json_object(json.loads(stopped.get("failure", "") if stopped else ""))
        require(
            {"stage", "cause", "classification", "message"} <= set(cause) and "\n" not in str(stopped),
            f"{key}: the failure is one structured line: {cause}",
        )
        failed.counts.clear()
        failed.runner(PLANS).run()
        expected: dict[str, int] = dict.fromkeys(ORDER[index:], 1)
        ran: dict[str, int] = {name: failed.counts[name] for name in ORDER if failed.counts[name]}
        require(ran == expected and sj.is_complete(failed.journal()), f"{key}: after a failure ran {ran}")
        if key == AUTHOR:
            first, second = failed.sessions.calls
            require(second.resume and second.session == first.session, "an unfinished step's session is resumed")
        killed: Bench = Bench(root / f"killed-{index}")
        write_run(killed)
        dispatch: JournalRunner = killed.runner(PLANS)
        for _ in range(index):
            require(dispatch.run_next(), f"{key}: a step ran before the kill")
        killed.counts.clear()
        killed.runner(PLANS).run()
        ran = {name: killed.counts[name] for name in ORDER if killed.counts[name]}
        require(ran == expected and sj.is_complete(killed.journal()), f"{key}: after a kill ran {ran}")
    report(f"PASS: a restart after a failure and after a kill at each of {len(ORDER)} steps runs that step onward")


def check_invalidation(bench: Bench) -> None:
    """Check that an invalidated step and the later ones run again, and nothing else."""
    planner: Step = bench.step("Discover the work")
    planned: list[StepId] = [bench.step("Write the document")["id"], bench.step("Confirm the document")["id"]]
    result: sj.Invalidation = sj.update_journal(
        bench.path,
        lambda journal: sj.invalidate_from(journal, planner["id"], sj.timestamp()),
    )
    require(result["removed"] == planned, "the steps a reset step planned are removed with it")
    require(result["reset"] == [planner["id"], bench.step("Finish the run")["id"]], f"reset: {result['reset']}")
    bench.counts.clear()
    bench.runner(PLANS).run()
    ran: dict[str, int] = {name: bench.counts[name] for name in ORDER if bench.counts[name]}
    require(ran == dict.fromkeys(ORDER[1:], 1), f"invalidating the planning step ran {ran}")
    middle: Step = bench.step("Write the document")
    require(middle["id"] not in planned, "the planning step planned its steps again, once")
    sj.update_journal(bench.path, lambda journal: sj.invalidate_from(journal, middle["id"], sj.timestamp()))
    bench.counts.clear()
    bench.runner(PLANS).run()
    ran = {name: bench.counts[name] for name in ORDER if bench.counts[name]}
    require(ran == dict.fromkeys(ORDER[2:], 1), f"invalidating a middle step ran {ran}")
    require(not bench.sessions.calls[-1].resume, "an invalidated step starts a new session")
    require(sj.is_complete(bench.journal()), "the run is complete again")
    report("PASS: invalidation from a planning step and from a middle step runs exactly that step onward")


def helped_run(bench: Bench, *, interrupted: bool) -> None:
    """Register an architect that starts helpers in its own session, and the helper's own launch."""

    def nothing(_run: StepRun, _output: Path) -> Completion:
        bench.enter("architect.accept")
        return Completion()

    @bench.registry.agent_step("architect")
    def architect(run: StepRun) -> AgentLaunch:
        finishing: bool = run.step["description"] == "Finish"
        holder: Step | None = run.session_holder()
        asked: Step | None = run.earlier_sibling("helper")
        if finishing:
            require(holder is not None and holder["description"] == "Establish the architecture", "session holder")
            require(asked is not None and asked["description"] == "Question two", "the helper step before Finish")
        output: Path = bench.work / ("result.json" if finishing else "state.json")
        return AgentLaunch(output, bench.root / "schema.json", "Establish it.", nothing, fresh_output=not finishing)

    @bench.registry.agent_step("helper")
    def helper(run: StepRun) -> AgentLaunch:
        asked: Path = run.saved.file("request")

        def accept(_accepted: StepRun, output: Path) -> Completion:
            return Completion(artifacts=(file_artifact("request", asked), file_artifact("answer", output)))

        schema: Path = bench.root / "schema.json"
        return AgentLaunch(bench.work / "answer.json", schema, "Answer.", accept, files=(("request", asked),))

    def establish(call: Call) -> None:
        call.output.write_text('{"accepted": true}', encoding="utf-8")
        if call.resume:
            sj.update_journal(call.journal, lambda journal: finish_own(journal, call))
            return
        asked: Path = bench.work / "request.json"
        asked.write_text("{}", encoding="utf-8")
        sj.update_journal(call.journal, lambda journal: start_helpers(journal, call, asked, interrupted=interrupted))
        if interrupted:
            message: str = "the session ended before its work"
            raise RuntimeError(message)

    def answer(call: Call) -> None:
        bench.enter("helper.session")
        require(call.inputs["request"].is_file(), "a helper left running is launched from its saved request")
        call.output.write_text('{"accepted": true}', encoding="utf-8")

    bench.sessions.behaviours.update({"architect": establish, "helper": answer})


def check_helpers(root: Path) -> None:
    """Check an agent that adds helper steps and "Finish" under its own step, whole and interrupted."""
    whole: Bench = Bench(root / "helpers")
    helped_run(whole, interrupted=False)
    whole.runner(HELPED).run()
    owner: Step = whole.step("Establish the architecture")
    require(owner["status"] == STATUS_DONE and sj.is_complete(whole.journal()), "the runner closes the parent")
    require(len(owner["steps"]) == TOGETHER and not whole.counts, "no helper is launched and nothing is accepted")
    require(len(whole.sessions.calls) == 1, "the agent's one session did all of it")
    broken: Bench = Bench(root / "interrupted")
    helped_run(broken, interrupted=True)
    with expected_error(StepError):
        broken.runner(HELPED).run()
    left: Step = broken.step("Question two")
    require(left["status"] == STATUS_FAILED, "the failure is recorded on the first step under it that is not done")
    require(broken.step("Establish the architecture")["status"] == STATUS_RUNNING, "the parent stays running")
    broken.runner(HELPED).run()
    first, helper, ending = broken.sessions.calls
    require(helper.agent == "helper" and not helper.resume and helper.step == left["id"], "the helper is launched")
    require(ending.agent == "architect" and ending.resume and ending.session == first.session, "Finish resumes")
    require(ending.step == broken.step("Finish")["id"], "Finish is launched as its own step")
    require(broken.step("Finish").get("session") == first.session, "Finish holds the session it continued")
    require(
        [held["name"] for held in broken.step("Question two")["artifacts"]] == ["request", "answer"],
        "the helper's request and answer are recorded",
    )
    require(sj.is_complete(broken.journal()) and not broken.counts["architect.accept"], "the parent is closed")
    report("PASS: an agent's helper steps and Finish close its step; an interrupted one resumes at the helper")


def reviewed_run(bench: Bench, failing: str | None = None) -> list[tuple[str, str]]:
    """Register reviewers whose sessions record when each started and ended.

    Returns:
        The list the sessions append their events to: ``start`` or ``end``, and the step's request.

    """
    write_run(bench)
    events: list[tuple[str, str]] = []
    barrier: threading.Barrier = threading.Barrier(TOGETHER, timeout=30)

    @bench.registry.agent_step("reviewer")
    def reviewer(run: StepRun) -> AgentLaunch:
        def accept(_accepted: StepRun, output: Path) -> Completion:
            return Completion(artifacts=(file_artifact("review", output), value_artifact("findings", [])))

        named: list[StepId] = run.step.get("inputs", [])
        earlier: StepId | None = named[-1] if run.step["description"] == "Review one again" else None
        output: Path = bench.work / f"{run.step['id']}.md"
        return AgentLaunch(output, lambda _path: None, "Review.", accept, resume_from=earlier)

    def review(call: Call) -> None:
        events.append(("start", call.request))
        if call.request != "Review one again":
            barrier.wait()
        call.output.write_text("No finding.\n", encoding="utf-8")
        events.append(("end", call.request))
        if call.request == failing:
            message: str = f"{failing} failed"
            raise RuntimeError(message)

    bench.sessions.behaviours["reviewer"] = review
    return events


def check_together(root: Path) -> None:
    """Check which sibling agent steps run as concurrent sessions, and how a failure among them ends."""
    bench: Bench = Bench(root / "together")
    events: list[tuple[str, str]] = reviewed_run(bench)
    dispatch: JournalRunner = bench.runner(REVIEWED)
    require(dispatch.run_next(), "the scope step ran")
    three: list[StepId] = [bench.step(f"Review {name}")["id"] for name in ("one", "two", "three")]
    require(concurrent_group(bench.journal(), three[0]) == three, "three reviewers with one done input run together")
    dispatch.run()
    again: int = events.index(("start", "Review one again"))
    require(again == 2 * TOGETHER, f"a step that names one of them in its inputs runs after them: {events}")
    require({kind for kind, _ in events[:TOGETHER]} == {"start"}, "the three sessions were running at once")
    require(bench.step("Approve")["artifacts"] == [value_artifact("reviews", TOGETHER)], "every review is handed on")
    rechecked: Call = next(call for call in bench.sessions.calls if call.request == "Review one again")
    require(
        rechecked.resume and rechecked.session == bench.step("Review one").get("session"),
        "a step continues the session of the step its launch names",
    )
    failing: Bench = Bench(root / "one-fails")
    reviewed_run(failing, "Review two")
    with expected_error(StepError):
        failing.runner(REVIEWED).run()
    statuses: list[str] = [failing.step(f"Review {name}")["status"] for name in ("one", "two", "three", "one again")]
    require(statuses == ["done", "failed", "done", "planned"], f"each step of the group is recorded: {statuses}")
    report("PASS: sibling agent steps with done inputs run together; one failure ends the dispatch after the group")


def check_failures(root: Path) -> None:
    """Check a step with no registered code, a stopped step, and a session whose conversation is gone."""
    bare: Bench = Bench(root / "unregistered")
    with expected_error(StepError) as unregistered:
        bare.runner(PLANS).run()
    require("no handler is registered" in unregistered[0].evidence[0], "a step with no handler says so")
    require(bare.step("Open the run")["status"] == STATUS_FAILED, "and is marked failed")
    halted: Bench = Bench(root / "stopped")

    @halted.registry.script_step(OPEN)
    def stop(_run: StepRun) -> Completion:
        message: str = "supervisor stopped new agent steps"
        raise PipelineStoppedError(message)

    with expected_error(PipelineStoppedError):
        halted.runner(PLANS).run()
    stopped: Step = halted.step("Open the run")
    require(stopped["status"] == STATUS_RUNNING and "failure" not in stopped, "a stop leaves the step running")
    gone: Bench = Bench(root / "lost")
    write_run(gone)
    gone.fail_once.add(AUTHOR)
    with expected_error(StepError):
        gone.runner(PLANS).run()
    held: str = gone.step("Write the document").get("session", "")
    gone.sessions.lost.add(held)
    gone.runner(PLANS).run()
    resumed, fresh = gone.sessions.calls[1:]
    require(resumed.resume and resumed.session == held, "the held session is resumed first")
    require(not fresh.resume and fresh.session != held, "a conversation that is gone is started again, new")
    require(gone.step("Write the document").get("session") == fresh.session, "and the step holds the new session")
    report("PASS: an unregistered step fails; a stop leaves its step running; a lost conversation starts again")


def check_placements(root: Path) -> None:
    """Check steps planned under the planning step itself and under a container planned earlier."""
    bench: Bench = Bench(root / "placed")
    seen: list[str] = []

    @bench.registry.script_step("check.plan")
    def plan(run: StepRun) -> Completion:
        scope: StepPlan = {"description": "Scope the repository", "purpose": "its work", "script": "check.scope"}
        repository: StepPlan = {"description": "Repository one", "purpose": "one repository's steps"}
        count: StepPlan = {"description": "Count the repositories", "purpose": "a total", "script": "check.count"}
        inside: NewStep = NewStep(repository, children=(NewStep(scope, {"repository": "one"}),))
        later: StepId = run.step_named("Later")["id"]
        return Completion(add=(StepGroup((inside,), UNDER_CONTAINER, later), StepGroup((NewStep(count),), UNDER_THIS)))

    @bench.registry.script_step("check.scope")
    def scope(run: StepRun) -> Completion:
        seen.append(f"scope {run.params()['repository']}")
        return Completion()

    @bench.registry.script_step("check.count")
    def count(run: StepRun) -> Completion:
        seen.append(f"count {len(run.params())}")
        return Completion()

    @bench.registry.script_step("check.begin")
    def begin(_run: StepRun) -> Completion:
        seen.append("begin")
        return Completion()

    bench.runner(PLACED).run()
    require(seen == ["count 0", "begin", "scope one"], f"the planned steps ran in walk order: {seen}")
    planner: Step = bench.step("Plan the repositories")
    scoped: Step = bench.step("Scope the repository")
    require(planner["status"] == STATUS_DONE and len(planner["steps"]) == 1, "the runner closes a step that waited")
    require(
        [step["description"] for step in bench.step("Later")["steps"]] == ["Begin", "Repository one"],
        "steps go last under a container planned earlier",
    )
    require(scoped.get("inputs") == [planner["id"]], "a step below a planned container is handed its parameters")
    require(
        [held["name"] for held in planner["artifacts"]]
        == [
            sj.planned_for_name(bench.step(name)["id"])
            for name in ("Repository one", scoped["description"], "Count the repositories")
        ],
        "the planning step records the steps it planned at each place",
    )
    require(sj.is_complete(bench.journal()), "the run is complete")
    report("PASS: steps planned under the planning step and under an earlier container, with a first child")


def check_journal_files(root: Path) -> None:
    """Check where journals are held and the journal a Story or a Task is created with."""
    runs: Path = root / ".claude" / "workflow-runs"
    require(sj.journals_directory(runs / "artifacts" / BEAD) == runs / sj.JOURNALS_DIRECTORY, "from a work directory")
    require(sj.journals_directory(runs) == runs / sj.JOURNALS_DIRECTORY, "from the workflow runs directory")
    with expected_error(StepJournalError):
        sj.journals_directory(root)
    directory: Path = sj.journals_directory(runs)
    story: BeadId = BeadId("ssbd-check.2")
    created: StepPlan = {"description": "Create the Story", "purpose": "the Story exists", "script": "story.create"}
    spec: Path = root / "spec.md"
    path: Path = create_child_journal(directory, story, BEAD_TYPE_STORY, [created], [file_artifact("spec", spec)])
    journal: Journal = sj.read_journal(path)
    require(path == sj.journal_path(directory, story) and journal["pipeline"] == PIPELINE_DEPLOY, "a Story's journal")
    first: Step = journal["steps"][0]
    require(first["status"] == STATUS_DONE and first["artifacts"] == [file_artifact("spec", spec)], "done")
    planned: list[str] = [step.get("script", "") for step in journal["steps"][1:]]
    require(planned == list(pipeline_steps.definition(PIPELINE_DEPLOY).plan), "the deploy plan follows")
    require(all(step["status"] == STATUS_PLANNED for step in journal["steps"][1:]), "every planned step is planned")
    create_child_journal(directory, story, BEAD_TYPE_STORY, [created], [file_artifact("trd", spec)])
    require(sj.read_journal(path)["steps"][0]["artifacts"] == [file_artifact("trd", spec)], "created again: replaced")
    task: Path = create_child_journal(directory, BeadId("ssbd-check.3"), BEAD_TYPE_TASK, [created], [])
    built: Journal = sj.read_journal(task)
    require(built["pipeline"] == PIPELINE_BUILD, "a Task's journal is for the build pipeline")
    require(
        [step.get("script", "") for step in built["steps"][1:]] == list(pipeline_steps.definition(PIPELINE_BUILD).plan),
        "the build plan follows",
    )
    report("PASS: one journals directory; a Story's and a Task's journal hold their first step done and their plan")


def main() -> None:
    """Run the journal runner checks in a temporary directory with stand-in sessions."""
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
        with patch.dict(os.environ, values), patch.object(AgentRunner, "_version", lambda _runner: None):
            name: str
            for name in (ARCH_PATH_ENV, MATRIX_ENV, STOP_FILE_ENV):
                os.environ.pop(name, None)
            child_env: str = HeadlessEnvironment.child_env.__name__
            headless: object = driver_module(HEADLESSENV_MODULE)
            with patch.object(headless, child_env, side_effect=lambda _scratch: dict(os.environ)):
                whole: Bench = Bench(root / "whole")
                check_whole_run(whole)
                check_invalidation(whole)
                check_restart(root)
                check_helpers(root)
                check_together(root)
                check_placements(root)
                check_failures(root)
                check_journal_files(root / "files")


if __name__ == "__main__":
    main()
