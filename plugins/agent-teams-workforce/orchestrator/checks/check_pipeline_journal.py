"""Quick checks of the build and deploy steps definition and of the journal changes a workflow reports.

Pure checks against temporary files; no workflow, session, tracker or repository is touched. They
cover: the definition loads and every kind it names exists; the up-front plans as step plans; a
journal opened for dispatch when it does not exist, when it holds only its creating step and when
it already holds its plan; and a change reader applying started, done (with artifacts, added steps
and their parameters), failed and child-steps changes, ignoring a change seen twice and a change of
another run, joining part lines, and refusing a change that skips a number.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.core import pipeline_steps
from orchestrator.core import step_journal as sj
from orchestrator.core.journal_lines import Applied, ChangeReader, JournalChangeError
from step_journal_contract import (
    BEAD_TYPE_STORY,
    BEAD_TYPE_TASK,
    CHANGE_CHUNK,
    CHANGE_OP_ADD,
    CHANGE_OP_DONE,
    CHANGE_OP_FAIL,
    CHANGE_OP_START,
    CHANGE_PART_PREFIX,
    CHANGE_PREFIX,
    KIND_VALUE,
    PIPELINE_BUILD,
    PIPELINE_DEPLOY,
    PIPELINE_ELABORATION,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PLANNED,
    STATUS_RUNNING,
    BeadId,
    Journal,
    JsonValue,
    Pipeline,
    Step,
    StepId,
    StepPlan,
)

TASK: BeadId = BeadId("ssbd-check.1.1")
STORY: BeadId = BeadId("ssbd-check.1")
RUN: str = "check-run"
CREATING: StepPlan = {"description": "Write the bead", "purpose": "the bead exists", "script": "bead-write"}
LONG_TAIL_FACTOR: int = 3


def kinds_of(journal: Journal) -> list[str]:
    """List the kind of every outermost step of a journal.

    Returns:
        Each step's script text, in order.

    """
    return [step.get("script", "") for step in journal["steps"]]


def line(number: int, op: str, step: str, **more: JsonValue) -> str:
    """Build the log line of one journal change, as a workflow script writes it.

    Returns:
        The change prefix followed by the change as JSON.

    """
    return CHANGE_PREFIX + json.dumps({"run": RUN, "n": number, "op": op, "step": step, **more})


def check_definition() -> None:
    """Check the definition's plans and that every kind a pipeline names is defined."""
    pipeline: Pipeline
    for pipeline in (PIPELINE_BUILD, PIPELINE_DEPLOY):
        definition: pipeline_steps.PipelineDefinition = pipeline_steps.definition(pipeline)
        plans: list[StepPlan] = pipeline_steps.plans(pipeline)
        require([plan.get("script") for plan in plans] == list(definition.plan), f"{pipeline}: one plan per kind")
        require(all(plan.get("ref") == plan.get("script") for plan in plans), f"{pipeline}: a plan's ref is its kind")
        require(all(kind.startswith(f"{pipeline}:") for kind in definition.kinds), f"{pipeline}: kinds carry its name")
        parent: str
        for parent in definition.inner:
            children: list[StepPlan] = pipeline_steps.inner_plans(pipeline, parent)
            require(all(definition.kinds[str(plan.get("script"))].within == parent for plan in children), parent)
    regression: StepPlan = pipeline_steps.plans(PIPELINE_BUILD)[1]
    require(regression.get("inputs") == ["build:workspace"], "a plan names the earlier plans whose artifacts it reads")
    filled: StepPlan = pipeline_steps.step_plan(PIPELINE_BUILD, "build:implement", {"implementer": "cdk-stack-author"})
    require(filled["description"] == "Write the code with cdk-stack-author", "a description takes its parameter")
    require(pipeline_steps.runner_of(PIPELINE_DEPLOY, "deploy:fix-author") == "story-deploy-fix", "who runs a kind")
    with expected_error(pipeline_steps.PipelineStepsError):
        pipeline_steps.step_plan(PIPELINE_BUILD, "build:implement")
    with expected_error(pipeline_steps.PipelineStepsError):
        pipeline_steps.step_plan(PIPELINE_BUILD, "build:nothing")
    with expected_error(pipeline_steps.PipelineStepsError):
        pipeline_steps.definition(PIPELINE_ELABORATION)
    report("PASS: the build and deploy steps definition loads; plans, child plans and descriptions come from it")


def check_open(root: Path) -> None:
    """Check that a journal opened for dispatch holds its plan once, however it came to exist."""
    directory: Path = root / "step-journals"
    build_plan: list[str] = list(pipeline_steps.definition(PIPELINE_BUILD).plan)
    absent: Path = pipeline_steps.open_journal(directory, TASK, BEAD_TYPE_TASK)
    require(kinds_of(sj.read_journal(absent)) == build_plan, "a bead with no journal gets the plan")
    older: Journal = sj.new_journal(STORY, BEAD_TYPE_STORY, PIPELINE_DEPLOY, [CREATING])
    opening: StepId = older["steps"][0]["id"]
    sj.start_step(older, opening, sj.timestamp())
    sj.finish_step(older, opening, sj.timestamp())
    path: Path = sj.journal_path(directory, STORY)
    sj.create_journal(path, older)
    require(not pipeline_steps.is_planned(sj.read_journal(path)), "a journal with only its creating step has no plan")
    pipeline_steps.open_journal(directory, STORY, BEAD_TYPE_STORY)
    opened: Journal = sj.read_journal(path)
    deploy_plan: list[str] = list(pipeline_steps.definition(PIPELINE_DEPLOY).plan)
    require(kinds_of(opened) == ["bead-write", *deploy_plan], "the plan follows the creating step")
    require(opened["steps"][0]["status"] == STATUS_DONE, "the creating step stays done")
    first: Step | None = sj.next_step(opened)
    require(first is not None and first.get("script") == deploy_plan[0], "the run begins at the first planned step")
    before: str = path.read_text(encoding="utf-8")
    pipeline_steps.open_journal(directory, STORY, BEAD_TYPE_STORY)
    require(path.read_text(encoding="utf-8") == before, "opening again changes nothing")
    with expected_error(pipeline_steps.PipelineStepsError):
        pipeline_steps.open_journal(directory, STORY, BEAD_TYPE_TASK)
    report("PASS: a journal opened for dispatch holds its plan once: absent, creating step only, already planned")


def check_changes(root: Path) -> tuple[Path, ChangeReader]:
    """Check started and done changes: artifacts, added steps, their parameters, and a change seen twice.

    Returns:
        The journal file and the reader, with the two added steps planned under the refs a.1 and a.2.

    """
    path: Path = pipeline_steps.open_journal(root / "changes", TASK, BEAD_TYPE_TASK)
    first: StepId = sj.read_journal(path)["steps"][0]["id"]
    reader: ChangeReader = ChangeReader(path, RUN)
    require(reader.feed("Workspace: reused worktree") is None, "a line with no change is not applied")
    started: Applied | None = reader.feed("[agent-teams-workforce:workspace] " + line(1, CHANGE_OP_START, first))
    require(started is not None and started.op == CHANGE_OP_START, "a change behind a called script's name is read")
    require(sj.find_step(sj.read_journal(path), first)["status"] == STATUS_RUNNING, "the step is running")
    implement: JsonValue = {"ref": "a.1", "description": "Write the code", "purpose": "p", "script": "build:implement"}
    judge: dict[str, JsonValue] = {"ref": "a.2", "description": "Judge", "purpose": "p", "script": "build:green-check"}
    added: list[JsonValue] = [
        {"plan": implement, "params": {"implementer": "x"}},
        {"plan": {**judge, "inputs": ["a.1"]}},
    ]
    artifacts: list[JsonValue] = [{"name": "worktree", "kind": "directory", "path": str(root / "tree")}]
    done: Applied | None = reader.feed(line(2, CHANGE_OP_DONE, first, artifacts=artifacts, add=added))
    require(done is not None and len(done.added) == len(added), "the steps a result adds are added")
    journal: Journal = sj.read_journal(path)
    require(kinds_of(journal)[:3] == ["build:workspace", "build:implement", "build:green-check"], "right after it")
    holder: Step = sj.find_step(journal, first)
    require(holder["status"] == STATUS_DONE, "the step is done")
    new: Step = journal["steps"][1]
    handed: list[JsonValue] = [
        held["value"]
        for held in holder["artifacts"]
        if held["kind"] == KIND_VALUE and held["name"] == sj.planned_for_name(new["id"])
    ]
    require(handed == [{"implementer": "x"}], "the parameters are recorded on the step that added the step")
    require(first in new.get("inputs", []), "the adding step joins the new step's inputs")
    require(journal["steps"][2].get("inputs") == [new["id"]], "an input that is a ref of the change is resolved")
    require(reader.feed(line(2, CHANGE_OP_DONE, first, artifacts=artifacts)) is None, "a change seen twice is ignored")
    other: str = CHANGE_PREFIX + json.dumps({"run": "another", "n": 3, "op": CHANGE_OP_START, "step": "a.1"})
    require(reader.feed(other) is None, "a change of another run is ignored")
    report("PASS: a change reader applies started and done changes once, with the steps and parameters a result adds")
    return path, reader


def check_change_order(path: Path, reader: ChangeReader) -> None:
    """Check child steps, part lines, a skipped number, an unknown step, a failure and a later run."""
    parent_id: StepId = reader.refs["a.1"]
    reader.feed(line(3, CHANGE_OP_START, "a.1"))
    child_plan: JsonValue = {"ref": "a.1.1", "description": "Child", "purpose": "p", "script": "build:docs-write"}
    reader.feed(line(4, CHANGE_OP_ADD, "a.1", add=[{"plan": child_plan}]))
    parent: Step = sj.find_step(sj.read_journal(path), parent_id)
    require(parent["status"] == STATUS_RUNNING and len(parent["steps"]) == 1, "child steps go under a running step")
    reader.feed(line(5, CHANGE_OP_START, "a.1.1"))
    tail: str = "x" * (CHANGE_CHUNK * LONG_TAIL_FACTOR)
    held: JsonValue = {"name": "tail", "kind": "value", "value": tail}
    body: str = json.dumps({"run": RUN, "n": 6, "op": CHANGE_OP_DONE, "step": "a.1.1", "artifacts": [held]})
    parts: list[str] = [body[at : at + CHANGE_CHUNK] for at in range(0, len(body), CHANGE_CHUNK)]
    results: list[Applied | None] = [
        reader.feed(f"{CHANGE_PART_PREFIX}6 {index}/{len(parts)} {part}") for index, part in enumerate(parts, start=1)
    ]
    require(results[-1] is not None and all(result is None for result in results[:-1]), "part lines join")
    child: Step = sj.find_step(sj.read_journal(path), parent["steps"][0]["id"])
    require(child["status"] == STATUS_DONE and child["artifacts"] == [held], "the joined change is applied whole")
    with expected_error(JournalChangeError):
        reader.feed(line(8, CHANGE_OP_START, "a.2"))
    with expected_error(JournalChangeError):
        reader.feed(line(7, CHANGE_OP_START, "no-such-ref"))
    reader.feed(line(7, CHANGE_OP_START, "a.2"))
    reader.feed(line(8, CHANGE_OP_FAIL, "a.2", failure='{"stage": "green", "message": "the suite is not green"}'))
    failed: Step = sj.read_journal(path)["steps"][2]
    require(failed["status"] == STATUS_FAILED and "not green" in failed.get("failure", ""), "a failure holds its cause")
    again: Step | None = sj.next_step(sj.read_journal(path))
    require(again is not None and again["id"] == failed["id"], "the next run begins at the failed step")
    later: ChangeReader = ChangeReader(path, "later-run")
    later.feed(CHANGE_PREFIX + json.dumps({"run": "later-run", "n": 1, "op": CHANGE_OP_START, "step": failed["id"]}))
    require(sj.read_journal(path)["steps"][2]["status"] == STATUS_RUNNING, "a later run names the step by its id")
    after: list[Step] = [step for step in sj.read_journal(path)["steps"][3:] if step["status"] != STATUS_PLANNED]
    require(not after, "every step after it is still planned")
    report(
        "PASS: child steps, part lines and a failure are applied in order; a skipped number and an unknown step refuse",
    )


def correction_steps(kinds: tuple[str, ...]) -> list[JsonValue]:
    """Build the steps a reuse audit adds when it finds a violation, as a workflow script reports them.

    Returns:
        One added step per kind, each with the plan the definition gives it and the audit's finding as purpose.

    """
    params: dict[str, JsonValue] = {"implementer": "python-lambda-implementer"}
    purpose: str = "The reuse audit found 1 violation"
    added: list[JsonValue] = []
    position: int
    kind: str
    for position, kind in enumerate(kinds, start=1):
        handed: dict[str, JsonValue] = params if kind == "build:implement" else {}
        built: StepPlan = pipeline_steps.step_plan(PIPELINE_BUILD, kind, handed, purpose=purpose)
        wire: dict[str, JsonValue] = {
            "ref": f"r.{position}",
            "description": built["description"],
            "purpose": built["purpose"],
            "script": kind,
        }
        added.append({"plan": wire, "params": handed} if handed else {"plan": wire})
    return added


def check_reuse_violation(root: Path) -> None:
    """Check that a reuse audit that finds violations adds the steps that correct them, right after it."""
    audit_kind: str = "build:reuse-audit"
    definition: pipeline_steps.PipelineDefinition = pipeline_steps.definition(PIPELINE_BUILD)
    plan: list[str] = list(definition.plan)
    require(plan.index(audit_kind) == plan.index("build:select-implementers") + 1, "the audit follows the green steps")
    correction: tuple[str, ...] = definition.kinds[audit_kind].adds[0].kinds
    require(correction == ("build:implement", "build:green-check", audit_kind), "a violation adds its correction")
    path: Path = pipeline_steps.open_journal(root / "reuse", TASK, BEAD_TYPE_TASK)
    audit: StepId = next(step["id"] for step in sj.read_journal(path)["steps"] if step.get("script") == audit_kind)
    reader: ChangeReader = ChangeReader(path, RUN)
    reader.feed(line(1, CHANGE_OP_START, audit))
    added: list[JsonValue] = correction_steps(correction)
    finding: str = "src/handler.py:12 duplicate feature:event-publishing publish: a direct EventBridge PutEvents call"
    held: JsonValue = {"clean": False, "violations": [finding], "judgment": [], "unchecked": []}
    artifacts: list[JsonValue] = [{"name": "reuseAudit", "kind": "value", "value": held}]
    done: Applied | None = reader.feed(line(2, CHANGE_OP_DONE, audit, artifacts=artifacts, add=added))
    require(done is not None and len(done.added) == len(correction), "the audit's result adds the correction steps")
    journal: Journal = sj.read_journal(path)
    at: int = kinds_of(journal).index(audit_kind)
    require(tuple(kinds_of(journal)[at + 1 : at + 1 + len(correction)]) == correction, "they follow the audit")
    require(kinds_of(journal)[at + 1 + len(correction)] == plan[plan.index(audit_kind) + 1], "then the plan goes on")
    following: Step | None = sj.next_step(journal)
    require(following is not None and following.get("script") == plan[0], "an earlier planned step still runs first")
    require(artifacts[0] in sj.find_step(journal, audit)["artifacts"], "the audit holds the violations it found")
    report("PASS: a reuse violation adds the steps that correct it after the audit: implement, green-check, the audit")


def main() -> None:
    """Run the checks in a temporary directory."""
    check_definition()
    directory: str
    with tempfile.TemporaryDirectory() as directory:
        root: Path = Path(directory).resolve() / ".claude" / "workflow-runs"
        check_open(root)
        check_reuse_violation(root)
        check_change_order(*check_changes(root))


if __name__ == "__main__":
    main()
