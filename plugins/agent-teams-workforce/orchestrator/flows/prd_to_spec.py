"""Elaborate one ready Epic: one dispatch is one pass of the loop over the Epic's step journal.

A dispatch claims the Epic, creates the Epic's journal when its file does not exist, with every
outermost step planned, and runs the journal's steps from the first that is not done until none is
left or one fails. Nothing but the journal decides where it begins. The claim and its release are
the dispatch's own lifecycle and not journal steps. The dispatch result is assembled from the
journal's artifacts, so it is the same whichever dispatch ran a step.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, NotRequired, TypedDict

# The driver-surface and matrix contracts are generated into their skills, their one definitions.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import elaboration
import elaborationcontracts
from driver_surface_types import ARCH_PATH_ENV, CONTROL_REPO_ENV, PRD_DIR_ENV
from elaborationcontracts import Finished, Refused, Released, Started
from matrix_contract import LOCK_DIRECTORY, MatrixError
from matrixstore import Matrix, matrix_path, update_matrix
from matrixsync import EpicBead, program_output, read_epics, sync_documents, sync_epics, vault_root
from matrixtraverse import epic_id
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core import step_journal
from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.events import EventWriter
from orchestrator.core.handback_contract import (
    EVENT_KEY,
    FATAL_CLASSES,
    NOTE_EVENT,
    OTHER_CAUSE,
    VERDICT_EVENT,
    EventName,
)
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import children_together, fills, script_step
from orchestrator.core.journal_run import JournalRunner, open_journal
from orchestrator.core.journal_steps import Completion, StepRun, file_artifact, value_artifact
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows import (
    architecture_earlier,
    architecture_promotion,
    architecture_ruling,
    elaboration_steps,
    spec_review,
    task_decomposition,
    task_edges,
    trd_authoring,
)
from orchestrator.flows.architecture import first_steps
from orchestrator.flows.architecture_files import (
    ARCHITECT,
    ARCHITECTURE,
    CONFIRM_TRD,
    HUMAN_ACTION_STAGE,
    LABEL_CONTEXT,
    LABEL_PRD,
    OPEN_RUN,
    context_path,
    new_context,
)
from orchestrator.flows.elaboration_files import (
    DONE_RULE_STEP,
    EDGE_CLOSURE,
    EDGES_CONTAINER,
    MARK_DONE,
    SCORE,
    SPECS_CONTAINER,
    STORY_EDGES,
    STORY_WRITE,
    TASKS_CONTAINER,
)
from orchestrator.flows.elaboration_result import journal_result
from orchestrator.flows.elaboration_support import (
    ARCHITECTURE_PHASE,
    enter_phase,
    failed,
    lifecycle,
    record,
)
from orchestrator.flows.repo_scoping import (
    SPAN,
    SPAN_DESCRIPTION,
    SPAN_PURPOSE,
)

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import (
    BEAD_TYPE_EPIC,
    PIPELINE_ELABORATION,
    BeadId,
    StepPlan,
)

_ARGUMENT_ERROR: str = "Arguments violate the prd_to_spec input contract"
MATRIX_EPIC: Final = "matrix epic entry"
LIFECYCLE_STAGE: Final = "epic-lifecycle"
REGISTERED: Final = (
    architecture_earlier,
    architecture_promotion,
    architecture_ruling,
    trd_authoring,
    spec_review,
    task_decomposition,
    task_edges,
    elaboration_steps,
)
"""The flow modules imported for the steps they register and nothing else."""
LOGGER = logging.getLogger(__name__)
SYNC_RECORD: Final = "documents-synced.json"
"""The record, beside the matrix's lock, of the vault commit the document entries were last synced at."""

type JsonObject = dict[str, JsonValue]


class _Lifecycle(TypedDict):
    owner: str
    done: bool
    claimAttempted: bool
    start: NotRequired[Started | Refused]
    release: NotRequired[Released | JsonObject]
    finish: NotRequired[Finished]


fills(ARCHITECTURE, OPEN_RUN)
fills(TASKS_CONTAINER, SPAN, STORY_WRITE)
"""The steps that fill the containers :func:`outermost_steps` plans empty: the open-run step plans
the architecture steps; the span plans the repositories' containers whose Story bead write plans
each repository's Tasks container."""
children_together(SPECS_CONTAINER, TASKS_CONTAINER)
"""The repositories' containers under Specs and Stories, and under Tasks, run at the same time."""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def outermost_steps() -> list[StepPlan]:
    """Plan every outermost step of an Epic's elaboration journal.

    Returns:
        The steps in the order they run. The Architecture and Tasks containers get their steps
        from the steps before them; the Specs and Stories container is created with the step
        that reads the repository span, and the Task edges container with the step that derives
        the edges the elements' requirements make.

    """
    span: StepPlan = {"description": SPAN_DESCRIPTION, "purpose": SPAN_PURPOSE, "script": SPAN, "inputs": ["trd"]}
    closure: StepPlan = {
        "description": "Derive the Task edges the elements' requirements make",
        "purpose": "A Task that builds an element is blocked by the Tasks that build what it requires",
        "script": EDGE_CLOSURE,
        "inputs": ["specs", "tasks"],
    }
    return [
        {
            "ref": "open",
            "description": "Open the run",
            "purpose": (
                "Bring the Epic's entry, its requirements and the document entries in the matrix up to date, "
                "and plan the architecture steps"
            ),
            "script": OPEN_RUN,
        },
        {
            "ref": "architecture",
            "description": ARCHITECTURE,
            "purpose": "The architecture this PRD needs exists, is documented in arc42 and is approved",
            "inputs": ["open"],
        },
        {
            "ref": "trd",
            "description": "TRD",
            "purpose": "The Epic carries one reviewed TRD whose every source resolves",
            "script": CONFIRM_TRD,
            "inputs": ["architecture"],
        },
        {
            "ref": "specs",
            "description": SPECS_CONTAINER,
            "purpose": "One reviewed spec set and one Story per repository the matrix names for this PRD",
            "inputs": ["trd"],
            "steps": [span],
        },
        {
            "ref": "tasks",
            "description": TASKS_CONTAINER,
            "purpose": "Every Story has Tasks that name what to build and which shared capabilities to use",
            "inputs": ["specs"],
        },
        {
            "ref": "edges",
            "description": EDGES_CONTAINER,
            "purpose": "A Task that needs another Story's Task built first is blocked by it",
            "inputs": ["specs", "tasks"],
            "steps": [closure],
        },
        {
            "ref": "score",
            "description": "Score the Tasks",
            "purpose": "Every Task has a WSJF score",
            "script": SCORE,
            "inputs": ["edges"],
        },
        {
            "ref": "done-rule",
            "description": "Apply the done rule",
            "purpose": "Every repository has its Story and its Tasks, and every Task is scored",
            "script": DONE_RULE_STEP,
            "inputs": ["specs", "tasks", "score"],
        },
        {
            "ref": "story-edges",
            "description": "Story edges",
            "purpose": "A Story that needs another Story first is blocked by it",
            "script": STORY_EDGES,
            "inputs": ["done-rule"],
        },
        {
            "description": "Mark the Epic elaborated",
            "purpose": "The Epic is done with elaboration and its Tasks can be built",
            "script": MARK_DONE,
            "inputs": ["story-edges"],
        },
    ]


def _sync_record(matrix: Path) -> Path:
    """Name the record of the vault commit the matrix's document entries were last synced at.

    Returns:
        The record file, in the matrix's state folder.

    """
    return matrix.parent / LOCK_DIRECTORY / SYNC_RECORD


def _git_names(vault: Path, arguments: list[str]) -> set[str]:
    """Run one git command in the vault that prints one path per line.

    Returns:
        The paths it printed, relative to the vault root.

    """
    return {line for line in program_output("git", arguments, vault).splitlines() if line.strip()}


def _uncommitted(vault: Path, scope: str) -> set[str]:
    """List the files under the architecture root whose working copy differs from the vault's last commit.

    Returns:
        The changed, deleted and untracked files, relative to the vault root.

    """
    return _git_names(vault, ["diff", "--name-only", "--no-renames", "HEAD", "--", scope]) | _git_names(
        vault,
        ["ls-files", "--others", "--exclude-standard", "--", scope],
    )


def _since_record(record: Path, vault: Path, arch: Path, scope: str) -> set[str] | None:
    """List the files changed since the recorded sync: committed since its commit, or uncommitted then.

    Returns:
        The files, relative to the vault root; None when there is no usable record (none, another
        architecture root, or a commit the vault cannot compare with), so every document is read.

    """
    try:
        recorded: object = json.loads(record.read_text(encoding="utf-8"))
    except FileNotFoundError, ValueError:
        return None
    if not isinstance(recorded, dict) or recorded.get("architectureRoot") != str(arch):
        return None
    commit: object = recorded.get("vaultCommit")
    dirty: object = recorded.get("dirty")
    if not isinstance(commit, str) or not isinstance(dirty, list):
        return None
    try:
        committed: set[str] = _git_names(vault, ["diff", "--name-only", "--no-renames", commit, "HEAD", "--", scope])
    except MatrixError:
        return None
    return committed | {str(name) for name in dirty}


def _sync_matrix(epics: list[EpicBead], prd: Path, arch: Path) -> str:
    """Bring the Epic's entry, its requirements and the changed document entries up to date.

    One matrix change does what ``atw-matrix sync-epics --bead`` and ``sync-documents`` do: the
    Epic with its PRD path and hash and one requirement per heading; and each arc42 document
    changed since the vault commit the last sync recorded, with its lifecycle and headings. A
    changed document is one committed since that commit, or one uncommitted then or now. With no
    usable record every document is read. The record is written under the matrix's lock with the
    change, and removed when the matrix could not be written, so it never names a commit the
    matrix does not reflect.

    Returns:
        The vault commit the documents were read at.

    """
    vault: Path = vault_root(arch)
    scope: str = arch.relative_to(vault).as_posix() or "."
    matrix: Path = matrix_path(None, os.environ)
    record: Path = _sync_record(matrix)

    def change(held: Matrix) -> str:
        commit: str = program_output("git", ["rev-parse", "HEAD"], vault).strip()
        dirty: set[str] = _uncommitted(vault, scope)
        since: set[str] | None = _since_record(record, vault, arch, scope)
        sync_epics(held, epics, env_path(PRD_DIR_ENV), prd=str(prd))
        if since is None:
            sync_documents(held, arch)
        else:
            sync_documents(held, arch, paths=sorted(str(vault / name) for name in since | dirty))
        write_json(record, {"architectureRoot": str(arch), "vaultCommit": commit, "dirty": sorted(dirty)})
        return commit

    try:
        return update_matrix(matrix, change)
    except BaseException:
        record.unlink(missing_ok=True)
        raise


@script_step(OPEN_RUN)
def open_run(run: StepRun) -> Completion:
    """Open the run: the matrix work, the context file, and the first architecture steps.

    Beads that does not hold the bead as an Epic fails the step.

    Returns:
        The PRD, the id of the Epic's matrix entry and the context file as artifacts, with the
        TRD initial write, the architect's step and the check after it planned under the
        Architecture container (``architecture.first_steps``).

    """
    enter_phase(run.context, run.agents.emit, ARCHITECTURE_PHASE, OPEN_RUN)
    dispatch: DispatchArguments = dispatch_arguments()
    args: JsonObject = run.context.args
    prd: Path = Path(check_type(json_object(args[dispatch.KEY_PRD])[dispatch.PRD_PATH], str)).resolve()
    arch: Path = Path(check_type(args[dispatch.KEY_ARCH_PATH], str)).resolve()
    control: Path = env_path(CONTROL_REPO_ENV)

    def read() -> list[EpicBead]:
        return run.tools.portfolio(OPEN_RUN, read_epics, control, run.bead)

    epics: list[EpicBead] = run.tools.operation(OPEN_RUN, read)
    commit: str = run.tools.portfolio(OPEN_RUN, _sync_matrix, epics, prd, arch)
    path: Path = context_path(run.context.work)
    write_json(path, new_context(run.bead, prd, arch, run.context.work, commit))
    architect: str = ARCHITECT
    return Completion(
        artifacts=(
            file_artifact(LABEL_PRD, prd),
            value_artifact(MATRIX_EPIC, epic_id(run.bead)),
            file_artifact(LABEL_CONTEXT, path),
        ),
        add=(first_steps(run.step["id"], run.step_named(ARCHITECTURE)["id"], architect),),
    )


def _started(context: RunContext) -> bool:
    return any(row.get("startedAt") is not None for row in context.sessions)


@dataclass
class _Elaboration:
    context: RunContext
    runner: AgentRunner
    tools: Tools
    state: _Lifecycle = field(init=False)
    result: JsonObject = field(init=False)
    dispatch: DispatchArguments = field(init=False)

    def __post_init__(self) -> None:
        self.dispatch = dispatch_arguments()
        self.state = {
            "owner": str(self.context.args.get(self.dispatch.KEY_OWNER) or self.context.run_id),
            "done": False,
            "claimAttempted": False,
        }
        self.result = json_object({
            "ok": False,
            "stage": "input",
            "lifecycle": self.state,
            "repoSpan": [],
            "hierarchy": {"epic": self.context.args.get(self.dispatch.KEY_EPIC, {}), "stories": [], "tasks": []},
            "beadsEmitted": 0,
            "lifecycleDone": False,
            "artifacts": {"dir": str(self.context.work), "epicId": self.context.bead, "phases": {}, "filing": {}},
        })

    def _release(self) -> None:
        if not self.state["claimAttempted"] or self.state["done"] or "release" in self.state:
            return
        try:
            self.state["release"] = lifecycle(
                self.context,
                self.tools,
                "release",
                elaboration.release,
                owner=self.state["owner"],
            )
        except Exception as exc:
            LOGGER.exception("Elaboration operation failed")
            release: dict[str, JsonValue] = failed("release", exc, agent_started=_started(self.context))
            self.state["release"] = release
            cleanup_failure: dict[str, JsonValue] = json_object(release["failure"])
            prior: dict[str, JsonValue] = json_object(self.result.get("failure") or {})
            prior_class: JsonValue = prior.get("classification")
            cleanup_class: JsonValue = cleanup_failure.get("classification")
            prior_fatal: bool = isinstance(prior_class, str) and prior_class in FATAL_CLASSES
            cleanup_fatal: bool = isinstance(cleanup_class, str) and cleanup_class in FATAL_CLASSES
            if prior_fatal and not cleanup_fatal:
                prior["originalFailure"] = {
                    "priorEvidence": prior.get("originalFailure"),
                    "releaseFailure": cleanup_failure,
                }
                self.result.update(ok=False, failure=prior)
            elif not self.result.get("ok"):
                cleanup_failure["originalFailure"] = json_object({
                    "stage": self.result.get("stage"),
                    "headline": self.result.get("headline"),
                    "failure": prior,
                })
                self.result.update(ok=False, failure=cleanup_failure)
            else:
                self.result.update(release)

    def _journal(self) -> JournalRunner:
        """Open the Epic's journal: created with its outermost steps when its file does not exist.

        Returns:
            The runner of the journal.

        """
        return open_journal(
            step_journal.journals_directory(self.context.work),
            BeadId(self.context.bead),
            BEAD_TYPE_EPIC,
            PIPELINE_ELABORATION,
            outermost_steps(),
            self.runner,
            self.tools,
        )

    def _elaborate(self) -> None:
        """Run the journal's steps and report from the journal, whether the loop ended or a step failed."""
        loop: JournalRunner = self._journal()
        failure: JsonObject = {}
        try:
            loop.run()
        except Exception as exc:
            LOGGER.exception("Elaboration step failed")
            failure = failed(self.context.stage, exc, agent_started=_started(self.context))
        reported: JsonObject = journal_result(step_journal.read_journal(loop.path), self.context)
        self.state["done"] = reported["lifecycleDone"] is True
        owner_stop: bool = reported.get("stage") == HUMAN_ACTION_STAGE
        self.result.update({**failure, **reported} if owner_stop else {**reported, **failure})

    def _claim_and_elaborate(self) -> None:
        self.context.stage = LIFECYCLE_STAGE
        self.state["claimAttempted"] = True
        start: elaborationcontracts.Started | elaborationcontracts.Refused = lifecycle(
            self.context,
            self.tools,
            "start",
            elaboration.start,
            owner=self.state["owner"],
            reclaim=bool(self.context.args.get(self.dispatch.KEY_RECLAIM)),
        )
        self.state["start"] = start
        if not start["ok"]:
            self.state["claimAttempted"] = False
            self.result.update(
                stage=LIFECYCLE_STAGE,
                refusal=json_object(start["refusal"]),
                headline="Epic lifecycle refused elaboration",
            )
            return
        self.state["owner"] = start["owner"]
        self.context.args[self.dispatch.KEY_OWNER] = start["owner"]
        self._elaborate()

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def execute(self, notes: list[JsonValue]) -> JsonObject:
        """Run one dispatch while retaining lifecycle and diagnostic records.

        Returns:
            The recorded flow report.

        Raises:
            TypeError: An argument violates the declared input contract.

        """
        if not (isinstance(notes, list)):
            raise TypeError(_ARGUMENT_ERROR)
        self.context.cleanup.insert(0, self._release)
        try:
            self._claim_and_elaborate()
        except Exception as exc:
            LOGGER.exception("Elaboration operation failed")
            self.result.update(failed(self.context.stage, exc, agent_started=_started(self.context)))
        finally:
            self._release()
        self.result.setdefault(
            "headline",
            "Architecture, Specs, Stories and scored Tasks are ready"
            if self.result["ok"]
            else "Epic elaboration incomplete",
        )
        self.result["lifecycleDone"] = self.state["done"]
        return record(self.context, json_object(self.result), {}, notes)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def elaborate(context: RunContext, runner: AgentRunner, tools: Tools, notes: list[JsonValue]) -> JsonObject:
    """Run one dispatch of an Epic's elaboration with the services given.

    Args:
        context: The run context of the dispatch.
        runner: The session runner of the dispatch.
        tools: The deterministic tools of the dispatch.
        notes: The list the dispatch's note and verdict events are collected in.

    Returns:
        The detailed internal report, assembled from the Epic's journal.

    """
    return _Elaboration(context, runner, tools).execute(notes)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run(context: RunContext) -> JsonObject:
    """Own the Epic's claim for one dispatch and run the Epic's journal from where it stands.

    Returns:
        The detailed internal report, projected to the wire contract by run.py.

    Raises:
        TypeError: An argument violates the declared input contract.
        StepError: Required Epic, tracker or PRD configuration is absent.

    """
    if not (isinstance(context, RunContext)):
        raise TypeError(_ARGUMENT_ERROR)
    dispatch: DispatchArguments = dispatch_arguments()
    args: dict[str, JsonValue] = context.args
    prd: dict[str, JsonValue] = json_object(args.get(dispatch.KEY_PRD, {}))
    if (
        not context.bead
        or not args.get(dispatch.KEY_BEADS_REPO_PATH)
        or not Path(check_type(prd.get(dispatch.PRD_PATH, ""), str)).is_file()
    ):
        stage: str = "input"
        raise StepError(stage, OTHER_CAUSE, ("Epic, beadsRepoPath and readable PRD path are required",))
    context.work.mkdir(parents=True, exist_ok=True)
    args[dispatch.KEY_ARCH_PATH] = args.get(dispatch.KEY_ARCH_PATH) or os.environ.get(ARCH_PATH_ENV, "")
    tools: Tools = Tools(context.work / "evidence")
    notes: list[JsonValue] = []
    output: EventWriter = EventWriter()

    def emit(event: EventName, **facts: JsonValue) -> None:
        if event in {NOTE_EVENT, VERDICT_EVENT}:
            notes.append({EVENT_KEY: event, **facts})
        output(event, **facts)

    runner: AgentRunner = AgentRunner(context, emit=emit)
    return elaborate(context, runner, tools, notes)
