"""Stand-in sessions of the architecture team for the architecture flow checks; not a check itself.

Each stand-in acts as one agent would: it writes a result that satisfies the architecture work
contract and, where the scenario says so, edits the journal, the vault and the matrix as the agent
does with ``atw-step-journal`` and ``atw-matrix``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import matrixstore
import matrixsync
from architecture_work_contract import (
    CONCLUSION_COMPLETE_AND_APPROVED,
    CONCLUSION_READY_FOR_REVIEW,
    CONCLUSION_UNSETTLED,
    UNSETTLED_TECHNICAL_CHOICE,
)
from orchestrator.checks.architecture_bench import ARCH, BEAD, CONCEPT, result_document, review_document
from orchestrator.checks.check_support import require
from orchestrator.core import step_journal as sj
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_steps import file_artifact, value_artifact
from orchestrator.flows.architecture import ARCHITECT_REQUEST
from orchestrator.flows.architecture_files import (
    ARTIFACT_CONCLUSION,
    LABEL_CONTEXT,
    LABEL_RESULT,
    LABEL_STATE,
    PLUGIN,
    ROLE_ARCHITECT,
    ROLE_DECIDER,
    ROLE_LEAD,
    ROLE_MAINTAINER,
    ROLE_REVIEWER,
    ROLE_SPECIALIST,
    ROLE_TRD_AUTHOR,
    agents_with_role,
)
from review_criteria import load_criteria
from typeguard import check_type

if TYPE_CHECKING:
    from architecture_work_contract import ArchitectureResult, Conclusion, Position, ScopeFinding, UnsettledMatter
    from matrix_contract import Claim, Matrix
    from orchestrator.checks.architecture_bench import ArchBench
    from orchestrator.checks.journal_bench import Call
    from step_journal_contract import Journal, Step, StepId, StepPlan


ARCHITECT: Final[str] = agents_with_role(PLUGIN, ROLE_ARCHITECT)[0]


LEAD: Final[str] = agents_with_role(PLUGIN, ROLE_LEAD)[0]


DECIDER: Final[str] = agents_with_role(PLUGIN, ROLE_DECIDER)[0]


TRD_AUTHOR: Final[str] = agents_with_role(PLUGIN, ROLE_TRD_AUTHOR)[0]


MAINTAINER: Final[str] = agents_with_role(PLUGIN, ROLE_MAINTAINER)[0]


SPECIALISTS: Final[tuple[str, ...]] = agents_with_role(PLUGIN, ROLE_SPECIALIST)[:2]


REVIEWERS: Final[dict[str, str]] = {group.id: group.reviewer for group in load_criteria().groups}


GUARDIAN: Final[str] = REVIEWERS["ownership-boundary"]


CORRECT: Final = "Correct finding F1"


RECHECK: Final = "Re-check finding F1"


RULE: Final = "Rule on the disputed finding"


TRD_TEXT: Final = "---\ndecisionIds: [arc42/08-crosscutting-concepts/email-channel.md#Proof]\n---\n# TRD\n\nTR-1.\n"


def context_of(call: Call) -> dict[str, JsonValue]:
    """Read the context file a stand-in architect's brief names.

    Returns:
        The decoded context.

    """
    decoded: object = json.loads(call.inputs[LABEL_CONTEXT].read_text(encoding="utf-8"))
    require(isinstance(decoded, dict), "the context file is a JSON object")
    return decoded if isinstance(decoded, dict) else {}


def helper_step(journal: Journal, parent: StepId, agent: str, description: str, files: dict[str, Path]) -> StepId:
    """Record one helper an agent ran inside its own session: added, started, artifacts, done.

    Returns:
        The id of the helper's step.

    """
    moment: str = sj.timestamp()
    plan: StepPlan = {"description": description, "purpose": "A gap this PRD has", "agent": agent, "inputs": [parent]}
    last: list[Step] = [child for child in sj.find_step(journal, parent)["steps"] if child["description"] != "Finish"]
    added: Step = sj.add_step(journal, plan, moment, parent=parent, after=last[-1]["id"] if last else None)
    sj.start_step(journal, added["id"], moment)
    for name, path in files.items():
        sj.record_artifact(journal, added["id"], file_artifact(name, path))
    sj.finish_step(journal, added["id"], moment)
    return added["id"]


def finish_step(journal: Journal, parent: StepId, agent: str, call: Call, conclusion: Conclusion | None) -> None:
    """Add the "Finish" child of an agent's step; mark it done with the result when one is given."""
    moment: str = sj.timestamp()
    plan: StepPlan = {
        "description": "Finish: record the result and the check against the criteria",
        "purpose": "The architecture and the TRD are ready for review, with each criterion answered",
        "agent": agent,
        "inputs": [parent],
    }
    ending: Step = sj.add_step(journal, plan, moment, parent=parent)
    if conclusion is None:
        return
    sj.start_step(journal, ending["id"], moment, session=call.session)
    sj.record_artifact(journal, ending["id"], file_artifact(LABEL_RESULT, call.output))
    sj.record_artifact(journal, ending["id"], value_artifact(ARTIFACT_CONCLUSION, conclusion))
    sj.finish_step(journal, ending["id"], moment)


def write_trd(call: Call) -> Path:
    """Write the TRD at the path the context file names.

    Returns:
        The TRD file.

    """
    trd: Path = Path(str(context_of(call)["trdPath"]))
    trd.parent.mkdir(parents=True, exist_ok=True)
    trd.write_text(TRD_TEXT, encoding="utf-8")
    return trd


def write_state(call: Call) -> None:
    """Write the architect's first output, and record it on its step as the architect does."""
    state: Path = call.inputs[LABEL_STATE]
    write_json(state, {"bead": BEAD, "needs": [], "conclusion": "work-remains", "summary": "The check."})
    sj.update_journal(
        call.journal,
        lambda journal: sj.record_artifact(journal, call.step, file_artifact("state of the architecture", state)),
    )


def change_document(bench: ArchBench, heading: str) -> None:
    """Change the vault as the maintainer does, and bring the matrix up to date for the Epic."""
    concept: Path = bench.vault / CONCEPT
    concept.write_text(concept.read_text(encoding="utf-8") + f"\n## {heading}\n\nThe design fact.\n", encoding="utf-8")

    def synced(matrix: Matrix) -> None:
        stamp: matrixstore.Stamp = matrixstore.Stamp(matrixstore.timestamp(), BEAD)
        done: matrixsync.DocumentsSynced = matrixsync.sync_documents(matrix, bench.vault / ARCH, stamp)
        claim: Claim = {"bead": str(BEAD), "step": "sync-documents", "at": stamp.at}
        matrixsync.hold_for_review(matrix, bench.vault / ARCH, [*done["added"], *done["changed"]], claim)

    matrixstore.update_matrix(bench.matrix, synced)


@dataclass(frozen=True)
class Scenario:
    """What the stand-in sessions of one run do."""

    work: bool = True
    finding: bool = False
    disputed: bool = False
    unsettled: bool = False
    mechanical: bool = False


def _establish(bench: ArchBench, scenario: Scenario, call: Call) -> None:
    """Act as the architect's first session: its state, its helpers, the documents and its result."""
    write_state(call)
    trd: Path = write_trd(call)
    asked: Path = bench.work / "architecture" / "request.json"
    write_json(asked, {})
    helpers: list[tuple[str, str, dict[str, Path]]] = [
        (TRD_AUTHOR, "Draft the TRD from the PRD and the approved arc42 material", {"request": asked, "TRD": trd}),
    ]
    if scenario.work:
        helpers += [(name, f"Question for {name}", {"question": asked, "answer": asked}) for name in SPECIALISTS]
        helpers.append((MAINTAINER, "Write the decisions into the arc42 documents", {"write request": asked}))
        helpers.append((TRD_AUTHOR, "Update the TRD with the technical requirements the design added", {"TRD": trd}))
        change_document(bench, "Unproven sign-up")
    conclusion: Conclusion = (
        CONCLUSION_UNSETTLED
        if scenario.unsettled
        else CONCLUSION_READY_FOR_REVIEW
        if scenario.work
        else CONCLUSION_COMPLETE_AND_APPROVED
    )
    result: ArchitectureResult = result_document(
        conclusion,
        failure_behaviours=["retry of the proof send"] if scenario.work else [],
    )
    if scenario.mechanical:
        result["criteria"] = result["criteria"][:-1]
    if scenario.unsettled:
        result["unsettled"] = [_matter()]
    write_json(call.output, result)

    def record(journal: Journal) -> None:
        for agent, description, files in helpers:
            helper_step(journal, call.step, agent, description, files)
        finish_step(journal, call.step, ARCHITECT, call, conclusion)

    sj.update_journal(call.journal, record)


def _matter() -> UnsettledMatter:
    """Build one matter the architect could not settle, to the question schema.

    Returns:
        The matter, with two positions.

    """
    positions: list[Position] = [
        {"id": name, "statement": f"Position {name}.", "evidence": [], "cost": "A cost."} for name in ("a", "b")
    ]
    return {
        "id": "U1",
        "kind": UNSETTLED_TECHNICAL_CHOICE,
        "matter": "Which store holds the proof.",
        "positions": positions,
    }


def _route(bench: ArchBench, scenario: Scenario, call: Call) -> None:
    """Act as the lead: write the routing and add the steps it calls for under its own step."""
    finishing: bool = call.request.startswith("Finish")
    journal: Journal = sj.read_journal(call.journal)
    ruled: bool = any(step.get("agent") == DECIDER for step in sj.steps_in_order(journal))
    to_decider: bool = (scenario.unsettled and not finishing) or (scenario.disputed and finishing and not ruled)
    routing: str = "decider" if to_decider or scenario.unsettled else "correct"
    item: dict[str, JsonValue] = {"item": "F1", "raisedBy": GUARDIAN, "routing": routing, "reason": "A defect."}
    write_json(call.output, {"items": [{**item, "steps": []}], "summary": "The check."})
    ending: StepPlan = {"description": "Finish", "purpose": "Every item is resolved", "agent": LEAD}
    plans: list[StepPlan]
    if to_decider:
        question: Path = bench.work / "architecture" / "question.json"
        write_json(question, _matter())
        plans = [{"description": RULE, "purpose": "Last resort", "agent": DECIDER, "inputs": [call.step]}, ending]
    elif finishing:
        sj.update_journal(
            call.journal,
            lambda held: sj.record_artifact(held, call.step, value_artifact("resolved", True)),
        )
        return
    else:
        reviewed: list[str] = [step["id"] for step in sj.steps_in_order(journal) if step.get("agent") == GUARDIAN]
        plans = [
            {"ref": "fix", "description": CORRECT, "purpose": "One correction", "agent": ARCHITECT, "inputs": reviewed},
            {"description": RECHECK, "purpose": "Only the corrected item", "agent": GUARDIAN, "inputs": ["fix"]},
            ending,
        ]

    def add(held: Journal) -> None:
        if to_decider:
            sj.record_artifact(
                held,
                call.step,
                file_artifact("question", bench.work / "architecture" / "question.json"),
            )
        sj.add_steps(held, plans, sj.timestamp(), parent=call.step)

    sj.update_journal(call.journal, add)


def install(bench: ArchBench, scenario: Scenario) -> None:
    """Register the stand-in session of every agent the architecture flow can launch."""

    def architect(call: Call) -> None:
        bench.enter(ARCHITECT)
        if call.request == ARCHITECT_REQUEST:
            _establish(bench, scenario, call)
            return
        require(call.resume, f"{call.request}: a later step of the architect continues its session")
        if call.request == CORRECT:
            require("findings" in call.inputs, "a correction is handed the findings")
        signals: list[str] = ["retry of the proof send"]
        write_json(call.output, result_document(CONCLUSION_READY_FOR_REVIEW, failure_behaviours=signals))

    def reviewer(call: Call) -> None:
        bench.enter(call.agent)
        scope: dict[str, JsonValue] = json_object(json.loads(call.inputs["review scope"].read_text(encoding="utf-8")))
        raises: bool = call.agent == GUARDIAN and (
            (scenario.finding and call.request != RECHECK) or (scenario.disputed and call.request == RECHECK)
        )
        findings: list[ScopeFinding] = []
        if raises:
            heading: dict[str, JsonValue] = check_type(scope["headings"], list[dict[str, JsonValue]])[0]
            findings = [
                {
                    "id": "F1",
                    "criterion": "A1",
                    "item": f"{heading['document']}#{heading['heading']}",
                    "observation": "The heading names no owner.",
                    "location": {"source": str(heading["document"]), "heading": str(heading["heading"])},
                    "correction": "Name the owner.",
                    "doneWhen": "The heading names one owner.",
                },
                {
                    "id": "F2",
                    "criterion": "A1",
                    "item": "something else#Elsewhere",
                    "observation": "Outside the scope.",
                    "location": {"source": "elsewhere.md", "heading": "Elsewhere"},
                    "correction": "None.",
                    "doneWhen": "Never.",
                },
            ]
        write_json(call.output, review_document(findings))

    def lead(call: Call) -> None:
        bench.enter(LEAD)
        _route(bench, scenario, call)

    def decider(call: Call) -> None:
        bench.enter(DECIDER)
        require(call.inputs["question"].is_file(), "the decider is handed the question file")
        ruling: dict[str, JsonValue] = {
            "matter": "U1",
            "stands": "a",
            "reason": "The evidence of position a.",
            "losingPositionChanges": "Nothing.",
            "ownerConcerns": [],
            "summary": "The check.",
        }
        write_json(call.output, ruling)

    bench.sessions.behaviours.update({ARCHITECT: architect, LEAD: lead, DECIDER: decider})
    bench.sessions.behaviours.update(dict.fromkeys(agents_with_role(PLUGIN, ROLE_REVIEWER), reviewer))
