"""Quick checks of the step journal: its contract, its behaviour, its command and how it is loaded.

Pure checks against temporary files; no workflow, flow, tracker or vault is touched. They cover:
the generated contract is current with its schema; create, nested child steps, start and done
ordering, the next step after each change, inputs and artifacts, invalidation; the agent session
id of a step; a reviewer whose findings become child steps after its session ended; what validation
rejects; two processes writing at once, each loading the module by file path as the driver does;
and every sub-command of bin/atw-step-journal run as a subprocess from another directory.
"""

import copy
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs this interpreter and the plugin's own command with fixed argv, no shell.
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from jsonschema import Draft7Validator
from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.core import step_journal as sj
from step_journal_contract import (
    BEAD_TYPE_TASK,
    JOURNAL_SUFFIX,
    KIND_FILE,
    KIND_VALUE,
    PIPELINE_BUILD,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PLANNED,
    STATUS_RUNNING,
    BeadId,
    Journal,
    JsonValue,
    Step,
    StepId,
    StepJournalError,
    StepPlan,
    json_value,
    load_schema,
)

if TYPE_CHECKING:
    from collections.abc import Callable

PLUGIN: Path = Path(__file__).resolve().parents[2]
MODULE: Path = PLUGIN / "orchestrator" / "core" / "step_journal.py"
COMMAND: Path = PLUGIN / "bin" / "atw-step-journal"
GENERATOR: Path = PLUGIN / "skills" / "pipeline-contracts" / "scripts" / "generate_step_journal_contract.py"
BEAD: BeadId = BeadId("ssbd-check.1")
MOMENT: str = "2026-01-01T00:00:00Z"
WRITES_EACH: int = 8
ADDED_TOGETHER: int = 2
SURVEY_ARTIFACTS: int = 2
DESIGN_CHILDREN: int = 2
STEPS_UNDER_DRAFT: int = 2
RESET_FROM_DESIGN: int = 5
WRITER: str = """
import importlib.util
import sys
from pathlib import Path

name = "_atw_step_journal_by_path"
spec = importlib.util.spec_from_file_location(name, sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
for index in range(int(sys.argv[4])):
    plan = {"description": f"{sys.argv[3]} {index}", "purpose": "concurrent write"}
    module.update_journal(Path(sys.argv[2]), lambda journal: module.add_step(journal, plan, module.timestamp()))
"""
REVIEW_PLANS: list[StepPlan] = [
    {"description": "prepare the spec", "purpose": "something to review", "script": "prepare.py"},
    {"description": "review the spec", "purpose": "find its defects", "agent": "reviewer"},
    {"description": "publish the spec", "purpose": "later steps read it", "script": "publish.py"},
]
FINDING_PLANS: list[StepPlan] = [
    {"ref": "fix", "description": "fix finding one", "purpose": "the reviewer found it", "agent": "author"},
    {"description": "check the fix", "purpose": "confirm the finding is gone", "agent": "reviewer", "inputs": ["fix"]},
]
PLANS: list[StepPlan] = [
    {"ref": "survey", "description": "survey the repository", "purpose": "know what exists", "script": "survey.py"},
    {
        "description": "design the change",
        "purpose": "agree the design before building",
        "steps": [
            {
                "ref": "draft",
                "description": "draft the design",
                "purpose": "a design to review",
                "agent": "author",
                "inputs": ["survey"],
            },
            {
                "description": "review the design",
                "purpose": "an independent check",
                "agent": "reviewer",
                "inputs": ["draft"],
            },
        ],
    },
    {
        "description": "publish the design",
        "purpose": "later steps read it",
        "script": "publish.py",
        "inputs": ["survey"],
    },
]


def _next_id(journal: Journal) -> StepId | None:
    """Name the step a run does next.

    Returns:
        The id of the next step, or None when none is left.

    """
    step: Step | None = sj.next_step(journal)
    return None if step is None else step["id"]


def _run_through(journal: Journal, step_id: StepId) -> None:
    """Start a step and mark it done."""
    sj.start_step(journal, step_id, MOMENT)
    sj.finish_step(journal, step_id, MOMENT)


def _created() -> Journal:
    """Create the journal and run its first step.

    Returns:
        The journal with the survey step done and holding two artifacts.

    """
    journal: Journal = sj.new_journal(BEAD, BEAD_TYPE_TASK, PIPELINE_BUILD, PLANS)
    survey: Step = journal["steps"][0]
    draft: Step = journal["steps"][1]["steps"][0]
    require(all(step["status"] == STATUS_PLANNED for step in journal["steps"]), "a new journal is all planned")
    require(draft.get("inputs") == [survey["id"]], "a ref in a plan becomes the id of the step it names")
    require(_next_id(journal) == survey["id"], "the first step is next in a new journal")
    with expected_error(sj.StepRefusedError):
        sj.finish_step(journal, survey["id"], MOMENT)
    sj.start_step(journal, survey["id"], MOMENT)
    require(survey["status"] == STATUS_RUNNING and "started" in survey, "start sets running and started")
    require(_next_id(journal) == survey["id"], "a running step is returned as next")
    sj.record_artifact(journal, survey["id"], {"name": "report", "kind": KIND_FILE, "path": "work/survey.json"})
    sj.record_artifact(journal, survey["id"], {"name": "count", "kind": KIND_VALUE, "value": {"files": 3}})
    sj.finish_step(journal, survey["id"], MOMENT)
    require(survey["status"] == STATUS_DONE and "finished" in survey, "done sets done and finished")
    require(_next_id(journal) == draft["id"], "a step with child steps is passed over for its first child")
    return journal


def _built() -> tuple[Journal, Step, Step, Step, Step, Step, Step]:
    """Create the journal and run it up to the point where only the publish step is left.

    Returns:
        The journal, then its steps: survey, design (a container), draft, review, publish, and
        the child step the draft added under itself.

    """
    journal: Journal = _created()
    survey: Step = journal["steps"][0]
    design: Step = journal["steps"][1]
    publish: Step = journal["steps"][2]
    draft: Step = design["steps"][0]
    review: Step = design["steps"][1]
    sj.start_step(journal, draft["id"], MOMENT)
    require(design["status"] == STATUS_RUNNING, "a container becomes running when a child step starts")
    section: Step = sj.add_step(
        journal,
        {"description": "write one section", "purpose": "the draft found two sections", "agent": "author"},
        MOMENT,
        parent=draft["id"],
    )
    with expected_error(sj.StepRefusedError):
        sj.add_step(journal, {"description": "too early", "purpose": "x"}, MOMENT, parent=section["id"])
    sj.start_step(journal, section["id"], MOMENT)
    figure: Step = sj.add_step(
        journal,
        {"description": "draw the figure", "purpose": "the section needs one", "script": "draw.py"},
        MOMENT,
        parent=section["id"],
    )
    require(design["steps"][0]["steps"][0]["steps"][0]["id"] == figure["id"], "child steps nest three deep")
    require(_next_id(journal) == figure["id"], "the walk goes down to the deepest step that is not done")
    with expected_error(sj.StepRefusedError):
        sj.start_step(journal, draft["id"], MOMENT)
    with expected_error(sj.StepRefusedError):
        sj.finish_step(journal, section["id"], MOMENT)
    sj.start_step(journal, figure["id"], MOMENT)
    sj.fail_step(journal, figure["id"], "the renderer crashed", MOMENT)
    require(figure["status"] == STATUS_FAILED and figure.get("failure") == "the renderer crashed", "fail sets failure")
    require(_next_id(journal) == figure["id"], "a failed step is returned as next")
    _run_through(journal, figure["id"])
    require("failure" not in figure, "starting a failed step again drops its failure")
    sj.finish_step(journal, section["id"], MOMENT)
    require(draft["status"] == STATUS_RUNNING, "the last child done does not complete a parent that has an agent")
    require([step["id"] for step in sj.unclosed_steps(journal)] == [draft["id"]], "that parent is reported unclosed")
    require(_next_id(journal) == review["id"], "next moves on past a parent whose child steps are done")
    sj.record_artifact(journal, draft["id"], {"name": "design", "kind": KIND_FILE, "path": "work/design.md"})
    sj.finish_step(journal, draft["id"], MOMENT)
    handed: list[sj.InputArtifacts] = sj.resolve_inputs(journal, review["id"])
    require(len(handed) == 1 and handed[0]["step"] == draft["id"], "inputs resolve to the step they name")
    require([item["name"] for item in handed[0]["artifacts"]] == ["design"], "inputs hand over that step's artifacts")
    _run_through(journal, review["id"])
    require(design["status"] == STATUS_DONE and "finished" in design, "a container is done when its last child is")
    require(_next_id(journal) == publish["id"], "next moves on past a finished container")
    require(
        len(sj.resolve_inputs(journal, publish["id"])[0]["artifacts"]) == SURVEY_ARTIFACTS,
        "both survey artifacts are handed on",
    )
    require(not sj.is_complete(journal), "the journal is not complete while a step is left")
    return journal, survey, design, draft, review, publish, section


def _check_invalidation() -> None:
    """Invalidate from an agent step and from a container, and finish a journal."""
    journal: Journal
    survey: Step
    design: Step
    draft: Step
    review: Step
    publish: Step
    section: Step
    journal, survey, design, draft, review, publish, section = _built()
    follow: Step = sj.add_step(
        journal,
        {"description": "reuse the section", "purpose": "it reads the section", "inputs": [section["id"]]},
        MOMENT,
    )
    branch: Journal = copy.deepcopy(journal)

    result: sj.Invalidation = sj.invalidate_from(journal, draft["id"], MOMENT)
    require(result["reset"] == [draft["id"], review["id"], publish["id"], follow["id"]], "the step and all after reset")
    require(
        len(result["removed"]) == STEPS_UNDER_DRAFT and not draft["steps"],
        "an agent step loses the child steps it added",
    )
    require(result["pruned"] == [follow["id"]] and "inputs" not in follow, "an input naming a removed step is dropped")
    require(draft["status"] == STATUS_PLANNED and not draft["artifacts"], "a reset step is planned with no artifacts")
    require("started" not in draft and "finished" not in draft, "a reset step loses its times")
    require(
        survey["status"] == STATUS_DONE and len(survey["artifacts"]) == SURVEY_ARTIFACTS,
        "steps before it are untouched",
    )
    require(design["status"] == STATUS_PLANNED and "finished" not in journal, "the container follows its children")
    require(_next_id(journal) == draft["id"], "a restart begins at the invalidated step")
    sj.checked_journal(journal)

    kept: Step = branch["steps"][1]
    result = sj.invalidate_from(branch, kept["id"], MOMENT)
    require(
        result["reset"][0] == kept["id"] and len(result["reset"]) == RESET_FROM_DESIGN,
        "a container and all after it reset",
    )
    require(len(kept["steps"]) == DESIGN_CHILDREN, "a container keeps its child steps")
    require(all(child["status"] == STATUS_PLANNED for child in kept["steps"]), "and they are reset the same way")
    require(not kept["steps"][0]["steps"], "an agent child of the container loses its own child steps")
    sj.checked_journal(branch)

    for step_id in (draft["id"], review["id"], publish["id"], follow["id"]):
        _run_through(journal, step_id)
    require(sj.is_complete(journal) and _next_id(journal) is None, "nothing is next when every step is done")
    require("finished" in journal, "a complete journal carries finished")
    middle: Step = sj.add_step(journal, {"description": "late", "purpose": "placed"}, MOMENT, after=survey["id"])
    require(journal["steps"][1]["id"] == middle["id"], "a step is added immediately after the named sibling")
    require("finished" not in journal and not sj.is_complete(journal), "a new step reopens the journal")


def _check_review_findings() -> None:
    """Follow a reviewer step whose findings become child steps after its session has ended.

    The reviewer stays running until the child steps are added and done, and is then closed. At
    every point the next step is where a restart resumes, and the session id is kept for it.
    """
    journal: Journal = sj.new_journal(BEAD, BEAD_TYPE_TASK, PIPELINE_BUILD, REVIEW_PLANS)
    prepare: Step = journal["steps"][0]
    reviewer: Step = journal["steps"][1]
    publish: Step = journal["steps"][2]
    with expected_error(sj.StepRefusedError):
        sj.start_step(journal, prepare["id"], MOMENT, session="s-0")
    sj.start_step(journal, prepare["id"], MOMENT)
    with expected_error(sj.StepRefusedError):
        sj.set_session(journal, prepare["id"], "s-0")
    sj.finish_step(journal, prepare["id"], MOMENT)
    with expected_error(sj.StepRefusedError):
        sj.set_session(journal, reviewer["id"], "s-0")
    sj.start_step(journal, reviewer["id"], MOMENT, session="s-1")
    require(sj.step_session(journal, reviewer["id"]) == "s-1", "start records the agent session id")
    sj.start_step(journal, reviewer["id"], MOMENT)
    require(sj.step_session(journal, reviewer["id"]) == "s-1", "starting again keeps the session id to resume")
    sj.set_session(journal, reviewer["id"], "s-2")
    require(reviewer.get("session") == "s-2", "the session id can be recorded after the step started")

    require(_next_id(journal) == reviewer["id"], "before its findings are filed, a restart runs the reviewer again")
    fixes: list[Step] = sj.add_steps(journal, FINDING_PLANS, MOMENT, parent=reviewer["id"])
    require(
        [step["id"] for step in reviewer["steps"]] == [step["id"] for step in fixes],
        "both are added in one change",
    )
    require(fixes[1].get("inputs") == [fixes[0]["id"]], "a ref resolves between steps added together")
    require(reviewer["status"] == STATUS_RUNNING, "the reviewer stays running while its child steps are open")
    require(_next_id(journal) == fixes[0]["id"], "next is the first child, never the reviewer again")
    require(not sj.unclosed_steps(journal), "the reviewer is not awaiting close while a child is open")
    with expected_error(sj.StepRefusedError):
        sj.start_step(journal, reviewer["id"], MOMENT)
    with expected_error(sj.StepRefusedError):
        sj.finish_step(journal, reviewer["id"], MOMENT)
    sj.start_step(journal, fixes[0]["id"], MOMENT, session="s-3")
    require(_next_id(journal) == fixes[0]["id"], "a restart resumes the child that was running")
    sj.finish_step(journal, fixes[0]["id"], MOMENT)
    require(_next_id(journal) == fixes[1]["id"], "then the next child")
    _run_through(journal, fixes[1]["id"])
    require(_next_id(journal) == publish["id"], "with its children done, next moves past the reviewer")
    require([step["id"] for step in sj.unclosed_steps(journal)] == [reviewer["id"]], "which awaits its own close")
    require(not sj.is_complete(journal), "the journal is not complete while the reviewer is open")
    sj.finish_step(journal, reviewer["id"], MOMENT)
    require(reviewer["status"] == STATUS_DONE and not sj.unclosed_steps(journal), "the reviewer is then closed")
    require(reviewer.get("session") == "s-2", "a done step keeps its session id for a later correction")
    with expected_error(sj.StepRefusedError):
        sj.add_steps(journal, FINDING_PLANS, MOMENT, parent=reviewer["id"])
    sj.checked_journal(journal)
    sj.invalidate_from(journal, reviewer["id"], MOMENT)
    require("session" not in reviewer and not reviewer["steps"], "invalidate removes the session id and the children")
    sj.checked_journal(journal)


def _document(journal: Journal) -> dict[str, JsonValue]:
    """Copy a journal as a plain JSON object a check can break.

    Returns:
        The journal as decoded JSON.

    Raises:
        TypeError: The journal did not decode to an object.

    """
    decoded: JsonValue = json_value(json.loads(json.dumps(journal)))
    if not isinstance(decoded, dict):
        message: str = "a journal is a JSON object"
        raise TypeError(message)
    return decoded


def _first_step(document: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Find the first outermost step of a journal document.

    Returns:
        The step object itself.

    Raises:
        TypeError: The document has no first step object.

    """
    steps: JsonValue = document.get("steps")
    if not isinstance(steps, list) or not steps or not isinstance(steps[0], dict):
        message: str = "the document has no first step"
        raise TypeError(message)
    return steps[0]


def _check_rejections(work: Path) -> None:
    """Require validation to reject four broken journals, and reading them to fail."""

    def both(step: dict[str, JsonValue]) -> None:
        step["agent"] = "author"

    def stray_input(step: dict[str, JsonValue]) -> None:
        step["inputs"] = ["00000000-0000-4000-8000-000000000000"]

    def path_and_value(step: dict[str, JsonValue]) -> None:
        step["artifacts"] = [{"name": "both", "kind": KIND_FILE, "path": "a", "value": 1}]

    def duplicate(step: dict[str, JsonValue]) -> None:
        step["steps"] = [copy.deepcopy(step)]

    def session_without_agent(step: dict[str, JsonValue]) -> None:
        step["session"] = "s-1"

    breaks: dict[str, Callable[[dict[str, JsonValue]], None]] = {
        "a step with both agent and script": both,
        "an input that names no step": stray_input,
        "an artifact with both path and value": path_and_value,
        "a repeated step id": duplicate,
        "a session id on a step no agent performs": session_without_agent,
    }
    journal: Journal = sj.new_journal(BEAD, BEAD_TYPE_TASK, PIPELINE_BUILD, PLANS)
    path: Path = work / "broken.json"
    path.write_text(json.dumps(journal), encoding="utf-8")
    require(not sj.file_problems(path), "a new journal has no problems")
    label: str
    for label, change in breaks.items():
        document: dict[str, JsonValue] = _document(journal)
        change(_first_step(document))
        path.write_text(json.dumps(document), encoding="utf-8")
        require(bool(sj.file_problems(path)), f"validation rejects {label}")
        with expected_error(StepJournalError):
            sj.read_journal(path)


def _check_contract() -> None:
    """Require the schema to be a valid draft-07 schema and the generated contract to be current."""
    Draft7Validator.check_schema(load_schema())
    result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv: this interpreter and the plugin's generator.
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    require(result.returncode == 0, f"step_journal_contract.py is stale: {result.stderr.strip()}")


def _check_two_writers(work: Path) -> None:
    """Run two processes that load the module by file path and write the same journal at once."""
    path: Path = sj.journal_path(work, BEAD)
    sj.create_journal(path, sj.new_journal(BEAD, BEAD_TYPE_TASK, PIPELINE_BUILD, PLANS))
    writers: list[subprocess.Popen[str]] = [
        subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv: this interpreter and the probe above.
            [sys.executable, "-P", "-c", WRITER, str(MODULE), str(path), label, str(WRITES_EACH)],
            cwd=work,
            stderr=subprocess.PIPE,
            text=True,
        )
        for label in ("first", "second")
    ]
    writer: subprocess.Popen[str]
    for writer in writers:
        errors: str = writer.communicate(timeout=120)[1]
        require(writer.returncode == 0, f"a writer that loads the module by path failed: {errors.strip()}")
    journal: Journal = sj.read_journal(path)
    described: list[str] = [step["description"] for step in journal["steps"]]
    require(len(described) == len(PLANS) + 2 * WRITES_EACH, "two processes writing at once lose no step")
    for label in ("first", "second"):
        own: list[str] = [text for text in described if text.startswith(label)]
        require(own == [f"{label} {index}" for index in range(WRITES_EACH)], f"the {label} writer's steps are in order")
    require(not list(work.glob("*.tmp")), "no temporary file is left behind")


def _command(work: Path, *arguments: str, status: int = 0) -> dict[str, JsonValue]:
    """Run bin/atw-step-journal from another directory and decode what it prints.

    Returns:
        The JSON object on stdout, or an empty object when the command printed none.

    Raises:
        TypeError: The command printed JSON that is not an object.

    """
    result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv: the plugin's own command.
        [str(COMMAND), *arguments],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    shown: str = f"atw-step-journal {' '.join(arguments)}"
    require(result.returncode == status, f"{shown} exited {result.returncode}, not {status}: {result.stderr.strip()}")
    if not result.stdout.strip():
        return {}
    decoded: JsonValue = json_value(json.loads(result.stdout))
    if not isinstance(decoded, dict):
        message: str = f"{shown} printed JSON that is not an object"
        raise TypeError(message)
    return decoded


def _printed_step(result: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Read the step a sub-command printed.

    Returns:
        The step object.

    Raises:
        TypeError: The result holds no step object.

    """
    step: JsonValue = result.get("step")
    if not isinstance(step, dict):
        message: str = "the command printed no step"
        raise TypeError(message)
    return step


def _printed_id(result: dict[str, JsonValue]) -> str:
    """Read the id of the step a sub-command printed.

    Returns:
        The step id.

    Raises:
        TypeError: The step has no string id.

    """
    step_id: JsonValue = _printed_step(result).get("id")
    if not isinstance(step_id, str):
        message: str = "the printed step has no id"
        raise TypeError(message)
    return step_id


def _check_command(work: Path) -> None:
    """Run every sub-command of bin/atw-step-journal as a subprocess, from another directory."""
    bead: str = "ssbd-check.2"
    where: tuple[str, ...] = ("--dir", "journals", "--bead", bead)
    plans: str = json.dumps([{"description": "first", "purpose": "start", "script": "one.py"}])
    created: dict[str, JsonValue] = _command(
        work,
        "create",
        *where,
        "--bead-type",
        "task",
        "--pipeline",
        "build",
        "--steps-json",
        plans,
    )
    file: Path = work / "journals" / f"{bead}{JOURNAL_SUFFIX}"
    require(created.get("path") == str(Path("journals") / file.name) and file.is_file(), "create writes the file")
    _command(work, "create", *where, "--bead-type", "task", "--pipeline", "build", "--steps-json", plans, status=1)
    require(_command(work, "validate", "--journal", str(file)).get("valid") is True, "validate accepts it")
    first: str = _printed_id(_command(work, "next", *where))
    _command(work, "done", *where, "--step", first, status=1)
    require(_printed_step(_command(work, "start", *where, "--step", first)).get("status") == STATUS_RUNNING, "start")
    _command(work, "artifact", *where, "--step", first, "--name", "out", "--kind", "file", "--path", "out.json")
    _command(work, "artifact", *where, "--step", first, "--name", "n", "--kind", "value", "--value", '{"a": [1]}')
    _command(work, "artifact", *where, "--step", first, "--name", "x", "--kind", "file", "--value", "1", status=1)
    require(_printed_step(_command(work, "done", *where, "--step", first)).get("status") == STATUS_DONE, "done")
    held: JsonValue = _command(work, "artifacts", *where, "--step", first).get("artifacts")
    require(isinstance(held, list) and len(held) == SURVEY_ARTIFACTS, "artifacts prints both artifacts")
    second: str = _printed_id(
        _command(work, "add", *where, "--description", "second", "--purpose", "next", "--agent", "a", "--input", first),
    )
    _command(work, "add", *where, "--description", "x", "--purpose", "y", "--agent", "a", "--script", "s", status=1)
    inputs: JsonValue = _command(work, "inputs", *where, "--step", second).get("inputs")
    require(isinstance(inputs, list) and len(inputs) == 1, "inputs prints the input step's artifacts")
    _command(work, "start", *where, "--step", first, "--session", "s-0", status=1)
    started: dict[str, JsonValue] = _printed_step(_command(work, "start", *where, "--step", second, "--session", "s-1"))
    require(started.get("session") == "s-1", "start --session records the agent session id")
    require(_command(work, "session", *where, "--step", second).get("session") == "s-1", "session prints it")
    _command(work, "session", *where, "--step", second, "--session", "s-2")
    require(_command(work, "session", *where, "--step", second).get("session") == "s-2", "session records it")
    require(_command(work, "session", *where, "--step", first).get("session") is None, "a script step holds none")
    failed: dict[str, JsonValue] = _printed_step(_command(work, "fail", *where, "--step", second, "--failure", "no"))
    require(failed.get("status") == STATUS_FAILED and failed.get("failure") == "no", "fail")
    require(_printed_id(_command(work, "next", *where)) == second, "next prints the failed step")
    reset: JsonValue = _command(work, "invalidate", *where, "--step", first).get("reset")
    require(reset == [first, second], "invalidate prints the steps it reset")
    following: dict[str, JsonValue] = _command(work, "next", *where)
    require(_printed_id(following) == first and following.get("complete") is False, "next after invalidate")
    several: str = json.dumps([{"description": "third", "purpose": "a"}, {"description": "fourth", "purpose": "b"}])
    added: JsonValue = _command(work, "add", *where, "--steps-json", several).get("steps")
    require(isinstance(added, list) and len(added) == ADDED_TOGETHER, "add --steps-json adds several in one change")
    file.write_text(json.dumps({"bead": bead}), encoding="utf-8")
    require(_command(work, "validate", *where, status=1).get("valid") is False, "validate rejects a broken file")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Run every step journal check against a temporary directory."""
    _check_contract()
    _check_invalidation()
    _check_review_findings()
    temporary: str
    with tempfile.TemporaryDirectory(prefix="atw-step-journal-check-") as temporary:
        work: Path = Path(temporary).resolve()
        _check_rejections(work)
        _check_two_writers(work)
        _check_command(work)
    report(
        "PASS: step journal contract, behaviour, sessions, reviewer findings, validation, "
        "concurrent by-path writers and bin/atw-step-journal",
    )


if __name__ == "__main__":
    main()
