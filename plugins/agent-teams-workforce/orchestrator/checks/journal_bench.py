"""Stand-in sessions and one scenario's step code for the journal runner checks; not a check itself.

A stand-in takes the place of the session process: it reads the brief the runner sent, writes the
output and, where a scenario says so, edits the journal as an agent session would with
``atw-step-journal``. No executable is started.
"""

from __future__ import annotations

import io
import json
import os
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from orchestrator.checks.check_support import expected_error, require
from orchestrator.core import step_journal as sj
from orchestrator.core.agent_context import AGENT_PREFIX
from orchestrator.core.agent_process import SessionProcesses, SessionRequest
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.events import EventWriter
from orchestrator.core.handback_contract import PRD_TO_SPEC_PHASES
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_registry import Registry
from orchestrator.core.journal_run import JournalRunner, open_journal
from orchestrator.core.journal_steps import (
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import RunContext, SessionFacts, StepError
from orchestrator.core.tools import Tools
from step_journal_contract import BEAD_TYPE_EPIC, PIPELINE_ELABORATION, BeadId, Journal, Step, StepId, StepPlan

if TYPE_CHECKING:
    from collections.abc import Callable

    from orchestrator.core.artifact_contract import ArtifactProducer

BEAD: Final[BeadId] = BeadId("ssbd-check.1")
TOGETHER: Final = 3
OPEN: Final = "check.open"
DISCOVER: Final = "check.discover"
AUTHOR: Final = "author.session"
CONFIRM: Final = "check.confirm"
FINISH: Final = "check.finish"
ORDER: Final[tuple[str, ...]] = (OPEN, DISCOVER, AUTHOR, CONFIRM, FINISH)
"""The steps of the first scenario in the order they run; each is counted under its key."""
SCHEMA: Final[dict[str, JsonValue]] = {
    "type": "object",
    "required": ["accepted"],
    "properties": {"accepted": {"const": True}},
}
PLANS: Final[list[StepPlan]] = [
    {"ref": "open", "description": "Open the run", "purpose": "the PRD is on record", "script": OPEN},
    {
        "description": "Work",
        "purpose": "the document exists and is confirmed",
        "steps": [
            {"description": "Discover the work", "purpose": "plan the rest", "script": DISCOVER, "inputs": ["open"]},
        ],
    },
    {"description": "Finish the run", "purpose": "the run is closed", "script": FINISH, "inputs": ["open"]},
]


@dataclass(frozen=True)
class Call:
    """One stand-in session: what the runner launched and what it sent."""

    agent: str
    resume: bool
    session: str
    step: StepId
    request: str
    output: Path
    inputs: dict[str, Path]

    @property
    def journal(self) -> Path:
        """The journal file the brief names under the label ``step journal``."""
        return self.inputs["step journal"]


@dataclass
class StandIns(SessionProcesses):
    """Takes the place of every session process: no executable is started."""

    behaviours: dict[str, Callable[[Call], None]] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    lost: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Set up the process registry the session runner expects."""
        super().__init__()

    def run(self, request: SessionRequest) -> SessionFacts:
        """Act as the session of the agent the command line names.

        Returns:
            The facts of a session that succeeded, or of one that ended without a turn when the
            conversation it was to resume is lost.

        """
        argv: list[str] = request.argv
        resume: bool = "--resume" in argv
        session: str = argv[argv.index("--resume" if resume else "--session-id") + 1]
        brief: dict[str, JsonValue] = json_object(json.loads(request.prompt))
        files: dict[str, Path] = {}
        entry: JsonValue
        for entry in brief["inputs"] if isinstance(brief["inputs"], list) else []:
            item: dict[str, JsonValue] = json_object(entry)
            files[str(item["label"])] = Path(str(item["path"]))
        call: Call = Call(
            agent=argv[argv.index("--agent") + 1].removeprefix(AGENT_PREFIX),
            resume=resume,
            session=session,
            step=StepId(str(brief["step"])),
            request=str(brief["request"]),
            output=Path(str(brief["output"])),
            inputs=files,
        )
        request.started(os.getpid())
        self.calls.append(call)
        if resume and session in self.lost:
            return {"result": None, "rate": None, "timeout": False, "exit": 1, "pid": os.getpid()}
        self.behaviours[call.agent](call)
        result: dict[str, JsonValue] = {"type": "result", "subtype": "success", "is_error": False}
        return {"result": result, "rate": None, "timeout": False, "exit": 0, "pid": os.getpid()}


@dataclass
class Bench:
    """One scenario's services, counters and injected failures, in its own directory."""

    root: Path
    module: ArtifactProducer
    registry: Registry = field(default_factory=Registry)
    sessions: StandIns = field(default_factory=StandIns)
    counts: Counter[str] = field(default_factory=Counter)
    fail_once: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        """Write a made-up plugin and bind a session runner whose sessions are stand-ins."""
        name: str
        for name in ("author", "architect", "helper", "reviewer"):
            (self.root / "plugin" / "agents").mkdir(parents=True, exist_ok=True)
            (self.root / "plugin" / "agents" / f"{name}.md").write_text(
                f"---\ndescription: {name}\ntools: Read, Write\nmodel: sonnet\neffort: low\n---\nDo the step.\n",
                encoding="utf-8",
            )
        self.work: Path = self.root / ".claude" / "workflow-runs" / "artifacts" / BEAD
        self.work.mkdir(parents=True)
        self.directory: Path = sj.journals_directory(self.work)
        self.path: Path = sj.journal_path(self.directory, BEAD)
        (self.root / "schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
        context: RunContext = RunContext(
            BEAD,
            dispatch_arguments().FLOW_PRD_TO_SPEC,
            {},
            self.work,
            "check-run",
            stage=PRD_TO_SPEC_PHASES[0],
        )
        store: ArtifactStore = ArtifactStore(self.module, self.root, self.work, BEAD, "check-run")
        self.agents: AgentRunner = AgentRunner(
            context,
            store,
            plugin=self.root / "plugin",
            emit=EventWriter(io.StringIO()),
        )
        self.agents.processes = self.sessions
        self.tools: Tools = Tools(self.work / "evidence")

    def enter(self, key: str) -> None:
        """Count one run of a step's code, and fail it when a failure is injected for it.

        Raises:
            RuntimeError: A failure was injected for ``key``; it is injected once.

        """
        with self.lock:
            self.counts[key] += 1
            injected: bool = key in self.fail_once
            self.fail_once.discard(key)
        if injected:
            message: str = f"injected failure in {key}"
            raise RuntimeError(message)

    def runner(self, plans: list[StepPlan]) -> JournalRunner:
        """Open the journal as one dispatch does: created when absent, otherwise left as it is.

        Returns:
            The runner of the bead's journal.

        """
        return open_journal(
            self.directory,
            BEAD,
            BEAD_TYPE_EPIC,
            PIPELINE_ELABORATION,
            plans,
            self.agents,
            self.tools,
            self.registry,
        )

    def journal(self) -> Journal:
        """Read the journal as it stands.

        Returns:
            The journal.

        """
        return sj.read_journal(self.path)

    def step(self, description: str) -> Step:
        """Find the one step with this description.

        Returns:
            The step.

        """
        found: list[Step] = [step for step in sj.steps_in_order(self.journal()) if step["description"] == description]
        require(len(found) == 1, f"{len(found)} steps are described {description!r}")
        return found[0]


def write_run(bench: Bench) -> None:
    """Register the code of the first scenario: two script steps plan an agent step and a script step."""

    @bench.registry.script_step(OPEN)
    def opened(run: StepRun) -> Completion:
        bench.enter(OPEN)
        prd: Path = bench.root / "prd.md"
        prd.write_text("The requirement.\n", encoding="utf-8")
        return Completion(artifacts=(file_artifact("prd", prd), value_artifact("matrix row", f"prd:{run.bead}")))

    @bench.registry.script_step(DISCOVER)
    def discovered(run: StepRun) -> Completion:
        bench.enter(DISCOVER)
        require(run.inputs.file("prd").is_file(), "the PRD is handed over from the journal")
        write: StepPlan = {
            "ref": "write",
            "description": "Write the document",
            "purpose": "the document exists",
            "agent": "author",
            "inputs": list(run.step.get("inputs", [])),
        }
        confirm: StepPlan = {
            "description": "Confirm the document",
            "purpose": "the document is the one asked for",
            "script": CONFIRM,
            "inputs": ["write"],
        }
        return Completion(add=(StepGroup((NewStep(write, {"topic": "journals"}), NewStep(confirm))),))

    @bench.registry.agent_step("author")
    def author(run: StepRun) -> AgentLaunch:
        require(run.params() == {"topic": "journals"}, "the planning step hands the new step its parameters")

        def accept(accepted: StepRun, output: Path) -> Completion:
            bench.enter("author.accept")
            return Completion(
                artifacts=(file_artifact("document", output), value_artifact("topic", accepted.params()["topic"])),
            )

        return AgentLaunch(bench.work / "document.json", bench.root / "schema.json", "Write the document.", accept)

    @bench.registry.script_step(CONFIRM)
    def confirmed(run: StepRun) -> Completion:
        bench.enter(CONFIRM)
        require(run.inputs.file("document").is_file(), "the document is handed over from the journal")
        require(run.inputs.value("topic") == "journals", "a value artifact is handed over from the journal")
        with expected_error(StepError) as missing:
            run.inputs.file("absent")
        require("'absent'" in missing[0].evidence[0], "a missing artifact is named in the failure")
        require(run.step["id"] in missing[0].evidence[0], "the step is named in the failure")
        return Completion()

    @bench.registry.script_step(FINISH)
    def finished(run: StepRun) -> Completion:
        bench.enter(FINISH)
        return Completion(artifacts=(value_artifact("reviews", len(run.inputs.files("review"))),))

    def write(call: Call) -> None:
        bench.enter(AUTHOR)
        call.output.write_text('{"accepted": true}', encoding="utf-8")

    bench.sessions.behaviours["author"] = write


def start_helpers(journal: Journal, call: Call, asked: Path, *, interrupted: bool) -> None:
    """Edit the journal as an architect's session does: its own output, two helpers and "Finish".

    Both helpers are started with their request recorded. Whole, every child step is marked done.
    Interrupted, the second helper is left running and "Finish" is left planned.
    """
    moment: str = sj.timestamp()
    sj.record_artifact(journal, call.step, file_artifact("state", call.output))
    plans: list[StepPlan] = [
        {"description": "Question one", "purpose": "a gap", "agent": "helper", "inputs": [call.step]},
        {"description": "Question two", "purpose": "a gap", "agent": "helper", "inputs": [call.step]},
        {"description": "Finish", "purpose": "the result", "agent": "architect", "inputs": [call.step]},
    ]
    one, two, ending = sj.add_steps(journal, plans, moment, parent=call.step)
    child: Step
    for child in (one, two):
        sj.start_step(journal, child["id"], moment)
        sj.record_artifact(journal, child["id"], file_artifact("request", asked))
    sj.finish_step(journal, one["id"], moment)
    if interrupted:
        return
    sj.finish_step(journal, two["id"], moment)
    sj.start_step(journal, ending["id"], moment)
    sj.record_artifact(journal, ending["id"], file_artifact("architecture result", call.output))
    sj.finish_step(journal, ending["id"], moment)


def finish_own(journal: Journal, call: Call) -> None:
    """Edit the journal as an architect's resumed session does: record the result and mark "Finish" done."""
    sj.record_artifact(journal, call.step, file_artifact("architecture result", call.output))
    sj.finish_step(journal, call.step, sj.timestamp())
