"""A temporary Epic with repositories, beads and stand-in sessions for the steps after the TRD; not a check itself.

It builds on the architecture bench: the vault, the plugin and the sessions of the architecture
part are the ones that bench makes. Added here are an in-memory bead tracker that answers the
``bd`` calls the portfolio makes, the matrix rows an Epic's span is read from, the repository
inventory, and a stand-in session for every agent of the spec, Task and Task edge steps. Each
script step's code and each stand-in session is counted under its step id, and can be made to
fail once.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, override
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts"))

from itertools import starmap

import beadgraph
import storyedges
from bead_metadata import KEY_ELAB_KEY
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import Matrix, Node, NodeId
from orchestrator.checks.architecture_bench import BEAD, STAMP, ArchBench
from orchestrator.checks.architecture_standins import Scenario, install
from orchestrator.checks.check_support import require
from orchestrator.core.agents import strict_json
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import REGISTRY, Registry
from orchestrator.core.journal_run import JournalRunner, open_journal
from orchestrator.flows import elaboration_steps, prd_to_spec, repo_scoping
from orchestrator.flows.elaboration_files import (
    AUTHOR_CONTRACTS,
    AUTHOR_CRITERIA,
    AUTHOR_DATA_MODEL,
    CONTEXT,
    CRITERIA,
    DATA_MODEL,
    DECIDER,
    DECOMPOSER,
    MAPPER,
    PLACED_ITEMS,
    REVIEWER,
    SPEC,
    TASK_CONTEXT_FILE,
    objects,
)
from orchestrator.flows.prd_to_spec import outermost_steps
from spec_review_contract import DOCUMENT_CRITERIA, DOCUMENT_DATA_MODEL, DOCUMENT_SPEC, RULING_FINDING_STANDS
from step_journal_contract import BEAD_TYPE_EPIC, PIPELINE_ELABORATION, Step
from task_deps_contract import empty_task_deps
from typeguard import check_type

if TYPE_CHECKING:
    from collections.abc import Callable

    from orchestrator.checks.journal_bench import Call
    from orchestrator.core.journal_steps import AgentBuilder, Completion, ScriptHandler, StepRun
    from orchestrator.core.models import RunContext
    from orchestrator.core.tools import Tools

SERVICE: Final = "Product-auth-service"
WEB: Final = "Product-web"
"""The repositories of the check's span: a service repository and a frontend repository."""
DOCUMENT_TEXT: Final = "---\ndecisionIds: []\n---\n# Specification\n"
CORRECTED: Final = "\nCorrected.\n"
DOCUMENT_ARTIFACT: Final[dict[str, str]] = {
    DOCUMENT_SPEC: SPEC,
    DOCUMENT_DATA_MODEL: DATA_MODEL,
    DOCUMENT_CRITERIA: CRITERIA,
}
SPEC_AGENTS: Final[tuple[str, ...]] = (
    AUTHOR_CONTRACTS,
    AUTHOR_DATA_MODEL,
    AUTHOR_CRITERIA,
    REVIEWER,
    DECIDER,
    DECOMPOSER,
    MAPPER,
)
CONFIG: Final = (
    "templates:\n  kinds:\n    frontend:\n      name_regex: '-web$'\n    service:\n      name_regex: '-service$'\n"
)
SCORE: Final[dict[str, JsonValue]] = {"jobSize": 2, "sizeLow": 1, "sizeHigh": 3, "sizeConfidence": 80}


def matrix_node(key: str, kind: str, name: str, **fields: object) -> tuple[NodeId, Node]:
    """Build one matrix row.

    Returns:
        The row's id and the row.

    """
    node: dict[str, object] = {"id": key, "kind": kind, "name": name, "links": [], "changed": STAMP.change(), **fields}
    return NodeId(key), check_type(node, Node)


def span_matrix(repositories: tuple[str, ...]) -> Matrix:
    """Build the matrix an Epic's span is read from: one element per repository, each needing the one before.

    Returns:
        A matrix with the Epic's PRD row, one feature and the elements that realize it.

    """
    keys: list[str] = [f"component:{name}/{name}/element" for name in repositories]
    rows: list[tuple[NodeId, Node]] = [
        matrix_node(f"prd:{BEAD}", "prd", "PRD", links=[{"type": "needs", "to": "feature:proof"}]),
        matrix_node(
            "feature:proof",
            "feature",
            "Proof",
            featureType="prd",
            links=[{"type": "realizedBy", "to": key} for key in keys],
        ),
    ]
    for index, (name, key) in enumerate(zip(repositories, keys, strict=True)):
        needs: list[dict[str, str]] = [{"type": "dependsOn", "to": keys[index - 1]}] if index else []
        rows.append(
            matrix_node(key, "component", f"Element of {name}", repository=name, code={"state": "none"}, links=needs),
        )
    return {
        "version": 3,
        "documentsSyncedAt": {"vaultCommit": "", "at": STAMP.at, "dirtyPaths": []},
        "resourceTypes": [],
        "nodes": dict(rows),
    }


@dataclass
class Beads:
    """An in-memory bead tracker: it answers the ``bd`` calls the portfolio makes, and counts them."""

    records: dict[str, dict[str, JsonValue]] = field(default_factory=dict)
    created: Counter[str] = field(default_factory=Counter)
    calls: list[list[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Hold the Epic, the one bead that exists before the run."""
        self.records[BEAD] = self._record(BEAD, "epic", "Address proof", None)

    @staticmethod
    def _record(identifier: str, kind: str, title: str, parent: str | None) -> dict[str, JsonValue]:
        return {
            "id": identifier,
            "title": title,
            "issue_type": kind,
            "status": "open",
            "parent": parent,
            "metadata": {},
            "dependencies": [],
            "description": "",
            "priority": 2,
        }

    def of_kind(self, kind: str) -> list[dict[str, JsonValue]]:
        """List the beads of one issue type.

        Returns:
            The records, in the order they were created.

        """
        return [record for record in self.records.values() if record["issue_type"] == kind]

    def _block(self, bead: str, blocker: str) -> None:
        held: list[JsonValue] = check_type(self.records[bead]["dependencies"], list[JsonValue])
        edge: dict[str, JsonValue] = {"depends_on_id": blocker, "type": "blocks"}
        if edge not in held:
            held.append(edge)

    def _create(self, args: list[str]) -> str:
        def option(name: str) -> str | None:
            return args[args.index(name) + 1] if name in args else None

        parent: str = option("--parent") or ""
        metadata: dict[str, JsonValue] = json_object(json.loads(option("--metadata") or "{}"))
        identifier: str = f"{parent}.{sum(1 for record in self.records.values() if record['parent'] == parent) + 1}"
        record: dict[str, JsonValue] = self._record(identifier, option("--type") or "", option("--title") or "", parent)
        record["description"] = option("--description") or ""
        record["metadata"] = metadata
        self.records[identifier] = record
        self.created[str(metadata.get(KEY_ELAB_KEY, identifier))] += 1
        for entry in (option("--deps") or "").split(","):
            if entry:
                self._block(identifier, entry.removeprefix("blocked-by:"))
        return identifier + "\n"

    def _update(self, args: list[str]) -> None:
        record: dict[str, JsonValue] = self.records[args[1]]
        metadata: dict[str, JsonValue] = json_object(record["metadata"])
        for index, word in enumerate(args):
            if word == "--title":
                record["title"] = args[index + 1]
            elif word == "--description":
                record["description"] = args[index + 1]
            elif word == "--set-metadata":
                key, _, value = args[index + 1].partition("=")
                metadata[key] = value
        record["metadata"] = metadata

    def run(self, args: list[str], _repo: Path | None, stdin: str | None = None) -> str:
        """Answer one ``bd`` call from memory.

        Returns:
            What ``bd`` would print: a JSON array for a listing, the new id for a creation,
            otherwise nothing.

        Raises:
            ValueError: The check's tracker does not know the command.

        """
        self.calls.append(list(args))
        if args[0] == "list":
            parent: str | None = args[args.index("--parent") + 1] if "--parent" in args else None
            kind: str | None = args[args.index("--type") + 1] if "--type" in args else None
            return json.dumps([
                record
                for record in self.records.values()
                if (parent is None or record["parent"] == parent) and (kind is None or record["issue_type"] == kind)
            ])
        if args[0] == "create":
            return self._create(args)
        if args[0] == "update":
            self._update(args)
        elif args[:3] == ["dep", "add", "--file"]:
            for line in (stdin or "").splitlines():
                edge: dict[str, JsonValue] = json_object(json.loads(line))
                self._block(str(edge["issue_id"]), str(edge["depends_on_id"]))
        elif args[:2] == ["dep", "add"]:
            self._block(args[2], args[3])
        elif args[:2] == ["dep", "remove"]:
            held: list[JsonValue] = check_type(self.records[args[2]]["dependencies"], list[JsonValue])
            held[:] = [edge for edge in held if json_object(edge)["depends_on_id"] != args[3]]
        elif args[0] == "delete":
            for identifier in args[1:]:
                self.records.pop(identifier, None)
        else:
            message: str = f"the check's bead tracker does not know bd {args}"
            raise ValueError(message)
        return ""


@dataclass
class Script:
    """What the stand-in sessions of the spec and Task steps write.

    ``findings`` are the review's findings on the service repository: each a finding id, the
    document it names and the criterion it is held against. ``disputes`` are the finding ids each
    document's author disputes, and ``upheld`` those of them the decider rules for. With
    ``gap`` the first decomposition of the frontend repository cites no item.
    """

    findings: list[tuple[str, str, str]] = field(default_factory=list)
    disputes: dict[str, list[str]] = field(default_factory=dict)
    upheld: list[str] = field(default_factory=list)
    gap: bool = False


class Counting(Registry):
    """The flows' registry, with each script step's code counted under its step id."""

    def __init__(self, enter: Callable[[str], None]) -> None:
        """Bind the counter a step's code is entered through."""
        super().__init__()
        self.enter: Callable[[str], None] = enter

    @override
    def script(self, step: Step) -> ScriptHandler:
        """Find the handler of a script step and count each run of it.

        Returns:
            The handler the flows registered, entered through the counter first.

        """
        handler: ScriptHandler = REGISTRY.script(step)
        identifier: str = step["id"]

        def counted(run: StepRun) -> Completion:
            self.enter(identifier)
            return handler(run)

        return counted

    @override
    def agent(self, step: Step) -> AgentBuilder:
        """Find the launch builder of an agent step.

        Returns:
            The builder the flows registered.

        """
        return REGISTRY.agent(step)


def _lifecycle(_context: RunContext, _tools: Tools, _stage: str, operation: object, /, **facts: object) -> object:
    """Stand in for the Epic's claim, its scoring, its mark and its release: no bead is read or written.

    Returns:
        A granted claim for the start; a finish with every Task scored and the Epic marked done;
        an empty record for the release.

    """
    name: str = getattr(operation, "__name__", "")
    if name == "start":
        return {"ok": True, "owner": facts.get("owner", "check")}
    if name == "finish":
        return {"score": {"unscored": []}, "summary": {"done": True}}
    return {"ok": True}


@dataclass
class ElabBench(ArchBench):
    """One scenario's Epic with its repositories, its beads and every stand-in session."""

    repositories: tuple[str, ...] = (SERVICE, WEB)
    script: Script = field(default_factory=Script)
    beads: Beads = field(default_factory=Beads)

    def __post_init__(self) -> None:
        """Make the architecture bench, then the repositories, the agents and the stand-in sessions."""
        super().__post_init__()
        self.control: Path = self.matrix.parent
        (self.control / ".polyrepo").mkdir()
        (self.control / ".polyrepo" / "config.yaml").write_text(CONFIG, encoding="utf-8")
        self.paths: dict[str, Path] = {name: self.root / "repositories" / name for name in self.repositories}
        for path in self.paths.values():
            path.mkdir(parents=True)
        for name in SPEC_AGENTS:
            (self.agents.plugin / "agents" / f"{name}.md").write_text(
                f"---\ndescription: {name}\ntools: Read, Write\nmodel: sonnet\neffort: low\n---\nDo the step.\n",
                encoding="utf-8",
            )
        self.registry: Counting = Counting(self.enter)
        install(self, Scenario(work=False))
        _install(self)

    def patched(self) -> ExitStack:
        """Stand in for beads, the matrix read, the repository inventory and the Epic's lifecycle.

        Returns:
            The stack of stand-ins, entered; closing it removes them.

        """

        def env_path(name: str) -> Path:
            return self.control if name == CONTROL_REPO_ENV else Path(os.environ[name])

        def inventory(_tools: Tools) -> dict[str, JsonValue]:
            return {"repos": [{"name": name, "path": str(path)} for name, path in self.paths.items()]}

        def read_matrix(_path: Path) -> Matrix:
            return span_matrix(self.repositories)

        def story_edges(_graph: object, _writer: object) -> dict[str, JsonValue]:
            return {"ok": True}

        stack: ExitStack = ExitStack()
        stack.enter_context(patch.dict(os.environ, self.environment()))
        stack.enter_context(patch.object(beadgraph, "run_bd", self.beads.run))
        stack.enter_context(patch.object(repo_scoping, "env_path", env_path))
        stack.enter_context(patch.object(repo_scoping, "inventory", inventory))
        stack.enter_context(patch.object(repo_scoping, "read_matrix", read_matrix))
        stack.enter_context(patch.object(storyedges, "story_edges", story_edges))
        stack.enter_context(patch.object(prd_to_spec, "lifecycle", _lifecycle))
        stack.enter_context(patch.object(elaboration_steps, "lifecycle", _lifecycle))
        return stack

    @override
    def runner(self) -> JournalRunner:
        """Open the Epic's journal as one dispatch does, with every script step's code counted.

        Returns:
            The runner of the journal.

        """
        return open_journal(
            self.path.parent,
            BEAD,
            BEAD_TYPE_EPIC,
            PIPELINE_ELABORATION,
            outermost_steps(),
            self.agents,
            self.tools,
            self.registry,
        )

    def launches(self, step: str) -> int:
        """Count the stand-in sessions launched for one step.

        Returns:
            How many sessions the runner launched for the step id.

        """
        return sum(1 for call in self.sessions.calls if call.step == step)


def _frontend(call: Call) -> bool:
    """Tell whether a session works on the frontend repository.

    Returns:
        True when the repository context or the task context it is handed names that repository.

    """
    handed: Path | None = call.inputs.get(CONTEXT) or call.inputs.get(TASK_CONTEXT_FILE)
    return handed is not None and Path(str(strict_json(handed)["repoPath"])).name == WEB


def _item_ids(path: Path) -> list[str]:
    """Read the ids of the items a context file or a placed items file lists.

    Returns:
        The ids, in the file's order.

    """
    return [str(item["id"]) for item in objects(strict_json(path)["items"])]


def _dispute(identifier: str) -> dict[str, JsonValue]:
    return {"findingId": identifier, "reason": "The route is internal.", "evidence": "trd.md#T3"}


def _ui_item(key: str) -> dict[str, JsonValue]:
    return {"item": key, "designSource": "none"}


def _finding(identifier: str, document: str, criterion: str) -> dict[str, JsonValue]:
    return {
        "id": identifier,
        "document": document,
        "criterion": criterion,
        "location": "API",
        "observation": "The route states no status codes.",
        "correction": "State the status codes of the route.",
        "doneWhen": "The route lists each status code it returns.",
    }


def _ruling(identifier: str) -> dict[str, JsonValue]:
    return {"findingId": identifier, "ruling": RULING_FINDING_STANDS, "reason": "Measured.", "directive": "Apply it."}


def _task(key: str, cited: list[str]) -> dict[str, JsonValue]:
    ids: list[JsonValue] = list(cited)
    return {"key": key, "title": f"Build {key}", "description": "Build it.", "requirementIds": ids}


def _score(key: str) -> dict[str, JsonValue]:
    return {"key": key, **SCORE}


def _install(bench: ElabBench) -> None:
    """Register the stand-in session of every agent of the spec, Task and Task edge steps."""
    _install_spec(bench)
    _install_tasks(bench)


def _install_spec(bench: ElabBench) -> None:
    """Register the stand-in sessions of the authors, the reviewer and the decider."""
    script: Script = bench.script

    def correct(call: Call) -> None:
        kind, phase = call.output.name.removesuffix(".json").rsplit(".", 2)[-2:]
        own: list[str] = [identifier for identifier, document, _ in script.findings if document == kind]
        disputed: list[str] = [] if phase == "revision" else script.disputes.get(kind, [])
        if not own or set(own) - set(disputed):
            with call.inputs[DOCUMENT_ARTIFACT[kind]].open("a", encoding="utf-8") as handle:
                handle.write(CORRECTED)
        disputes: list[JsonValue] = [_dispute(identifier) for identifier in disputed]
        write_json(call.output, {"disputes": disputes, "summary": "Corrected."})

    def author(call: Call) -> None:
        bench.enter(call.step)
        if call.output.name.endswith(".ui.json"):
            items: list[JsonValue] = [_ui_item(key) for key in _item_ids(call.inputs[CONTEXT])]
            write_json(call.output, {"uiItems": items})
        elif call.output.suffix == ".md":
            call.output.write_text(DOCUMENT_TEXT, encoding="utf-8")
        else:
            correct(call)

    def reviewer(call: Call) -> None:
        bench.enter(call.step)
        findings: list[JsonValue] = list(starmap(_finding, [] if _frontend(call) else script.findings))
        write_json(call.output, {"findings": findings, "summary": "Reviewed."})

    def decider(call: Call) -> None:
        bench.enter(call.step)
        rulings: list[JsonValue] = [_ruling(identifier) for identifier in script.upheld]
        write_json(call.output, {"rulings": rulings, "summary": "Ruled."})

    for name in (AUTHOR_CONTRACTS, AUTHOR_DATA_MODEL, AUTHOR_CRITERIA):
        bench.sessions.behaviours[name] = author
    bench.sessions.behaviours.update({REVIEWER: reviewer, DECIDER: decider})


def _install_tasks(bench: ElabBench) -> None:
    """Register the stand-in sessions of the decomposer and the dependency mapper."""
    script: Script = bench.script

    def decomposer(call: Call) -> None:
        bench.enter(call.step)
        cited: list[str] = _item_ids(call.inputs[PLACED_ITEMS])
        correcting: bool = call.output.name.endswith(".correction.json")
        if script.gap and _frontend(call) and not correcting:
            cited = []
        series: str = "N" if correcting else "T"
        keys: list[str] = [f"{series}{index}" for index in range(1, len(cited) + 1)] or [f"{series}1"]
        tasks: list[JsonValue] = [_task(key, cited[index : index + 1]) for index, key in enumerate(keys)]
        scores: list[JsonValue] = [_score(key) for key in keys]
        write_json(call.output, {"tasks": tasks, "edges": [], "scores": scores})

    def mapper(call: Call) -> None:
        bench.enter(call.step)
        write_json(call.output, json_object(empty_task_deps()))

    bench.sessions.behaviours.update({DECOMPOSER: decomposer, MAPPER: mapper})


def descriptions(steps: list[Step]) -> list[str]:
    """Name each step by what performs it.

    Returns:
        The agent of each agent step and the script key of each script step, in order.

    """
    return [step.get("agent") or step.get("script") or step["description"] for step in steps]


def require_done(bench: ElabBench) -> None:
    """Require that every outermost step of the Epic's journal is done."""
    left: list[str] = [step["description"] for step in bench.journal()["steps"] if step["status"] != "done"]
    require(not left, f"outermost steps are not done: {left}")
