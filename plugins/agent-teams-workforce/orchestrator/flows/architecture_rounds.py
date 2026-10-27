"""The work the script does between the solutions architect's sessions.

The architect never starts an agent. Each of its steps is a fresh session that writes a file, and
the step that accepts that file plans what follows it, among its siblings:

- a round of requests (the Analyze step's ``questions.json``, or a result's ``requests``): one
  step per request whose answer is not yet a valid answer, each started as the agent the request
  names, then a fresh Decide step of the architect, handed every answer;
- a result with no open request: one ``architecture-maintainer`` step per home document whose
  write request differs from the one already written, each write request built here from the
  result's ``facts``, ``restatements``, ``settlements`` and ``diagrams``.

A Decide step is handed a digest of its answers (:func:`write_digest`), so it reads a few KB
instead of every answer file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import (
    validate_answers_digest,
    validate_specialist_answer,
    validate_write_request,
    validate_write_result,
)
from matrixstore import slug

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.io import json_object, write_json
from orchestrator.core.journal_steps import NewStep, StepGroup
from orchestrator.flows.architecture_files import (
    ARCHITECT,
    LABEL_ANSWER,
    MAINTAINER,
    PARAM_REQUEST,
    ArchitectureStepError,
    checked_file,
    cited_document,
    document_path,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from architecture_work_contract import (
        AgentRequest,
        AnswersDigest,
        AppliedSettlement,
        ArchitectureResult,
        DigestedAnswer,
        SourceHeading,
        SpecialistAnswer,
        SpecialistRequest,
        WriteRequest,
    )
    from step_journal_contract import Step, StepPlan

    from orchestrator.core.io import JsonValue
    from orchestrator.core.journal_steps import StepRun

DECIDE_DESCRIPTION: Final = "Decide the architecture with the specialists' answers"
PARAM_ROUND: Final = "round"
"""The parameter that hands a Decide step the number of the round of answers it decides with."""
MAX_ROUNDS: Final = 2
"""How many rounds of requests one chain of architect steps may put to the specialists."""
REQUEST_SUFFIX: Final = ".request.json"
"""What the request file of a request adds to its answer file's stem."""
WRITE_PREFIX: Final = "write-"
DIGEST_PREFIX: Final = "digest-"
ID_LENGTH: Final = 8
"""How much of a step id names a file the script writes for that step."""


def answered(request: SpecialistRequest) -> bool:
    """Tell whether a request's answer file already holds a valid answer.

    Returns:
        True when the file at the request's answer path is a valid specialist answer.

    """
    path: Path = Path(request["answerPath"])
    if not path.is_file():
        return False
    try:
        validate_specialist_answer(strict_json(path), str(path))
    except OSError, ValueError:
        return False
    return True


def round_of(run: StepRun) -> int:
    """Read which round of answers an architect step decides with.

    Returns:
        The ``round`` parameter its planning step handed it; 0 for a step planned without one
        (the Analyze step, a correction, a competing design).

    """
    held: JsonValue = run.params().get(PARAM_ROUND, 0)
    return held if isinstance(held, int) else 0


def round_steps(run: StepRun, requests: Sequence[AgentRequest], number: int) -> StepGroup:
    """Plan one round of requests after an architect step, then the Decide step that uses the answers.

    Each request whose answer is not yet a valid answer is written beside its answer path and gets
    one step, performed by the agent the request names and handed the request file as the
    parameter ``request``. The Decide step's inputs are those steps and the completing step's own
    inputs, so it is handed every answer of the chain, the findings and rulings the completing
    step was handed, and the round's number.

    Args:
        run: The architect step whose output holds the requests.
        requests: The requests, one per agent.
        number: The round these requests make.

    Returns:
        The group, placed after the completing step.

    """
    steps: list[NewStep] = []
    refs: list[str] = []
    index: int
    entry: AgentRequest
    for index, entry in enumerate(requests):
        if answered(entry["request"]):
            continue
        answer: Path = Path(entry["request"]["answerPath"])
        asked: Path = answer.with_name(answer.stem + REQUEST_SUFFIX)
        write_json(asked, json_object(entry["request"]))
        agent: str = step_journal.agent_name(entry["agent"])
        ref: str = f"round-{number}-{index}"
        refs.append(ref)
        steps.append(
            NewStep(
                {
                    "ref": ref,
                    "description": f"Answer the solutions architect's request to {agent}",
                    "purpose": "The solutions architect named this agent for this work",
                    "agent": agent,
                },
                params={PARAM_REQUEST: str(asked)},
            ),
        )
    carried: list[str] = [held for held in run.step.get("inputs", []) if held != run.step["id"]]
    decide: StepPlan = {
        "description": DECIDE_DESCRIPTION,
        "purpose": "The architect decides, in a fresh session, with every answer its requests returned",
        "agent": ARCHITECT,
        "inputs": list(dict.fromkeys([*refs, *carried])),
    }
    return StepGroup((*steps, NewStep(decide, params={PARAM_ROUND: number})))


def _answer_agents(run: StepRun) -> dict[str, str]:
    """Name the agent that wrote each answer file the journal records.

    Returns:
        Each answer file's path, with the agent of the step that holds it.

    """
    agents: dict[str, str] = {}
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        agent: str | None = step.get("agent")
        if agent is None:
            continue
        for held in step["artifacts"]:
            if held["name"] == LABEL_ANSWER and held["kind"] != "value":
                agents[held["path"]] = agent
    return agents


def _digested(agent: str, path: Path, answer: SpecialistAnswer) -> DigestedAnswer:
    """Cut one answer to what a decision needs.

    Returns:
        The answer, its assumptions and needs, a task's decisions, and what each of its diagrams shows.

    """
    return {
        "agent": agent,
        "kind": answer["kind"],
        "answerPath": str(path),
        "answer": answer["answer"],
        "assumptions": answer["assumptions"],
        "needs": answer["needs"],
        "decisions": answer.get("decisions", []),
        "diagrams": [
            {"home": drawn["home"], "viewType": drawn["viewType"], "shows": drawn["shows"]}
            for drawn in answer.get("diagrams", [])
        ],
    }


def write_digest(run: StepRun, helpers: Path) -> Path | None:
    """Write the digest of the answers an architect step is handed.

    Returns:
        The digest file, in the helpers folder and named for the step; None when the step is
        handed no answer.

    """
    answers: list[Path] = list(dict.fromkeys(run.inputs.files(LABEL_ANSWER)))
    if not answers:
        return None
    agents: dict[str, str] = _answer_agents(run)
    digest: AnswersDigest = {
        "answers": [
            _digested(agents.get(str(path), "unknown"), path, checked_file(run, path, validate_specialist_answer))
            for path in answers
        ],
    }
    validate_answers_digest(digest)
    path: Path = helpers / f"{DIGEST_PREFIX}{run.step['id'][:ID_LENGTH]}.json"
    write_json(path, json_object(digest))
    return path


def _document(arch: Path, citation: SourceHeading) -> str:
    """Name the document a citation is in.

    Returns:
        Its path under the architecture root; the citation's source as given when it names no
        document under the root.

    """
    held: str | None = cited_document(arch, citation["source"])
    return citation["source"].strip() if held is None else document_path(held)


def _empty(bead: str) -> WriteRequest:
    """Start the write request of one document.

    Returns:
        A request with nothing to write and no result path yet.

    """
    return {"bead": bead, "facts": [], "restatements": [], "settlements": [], "diagrams": [], "resultPath": ""}


def write_requests(arch: Path, result: ArchitectureResult) -> dict[str, WriteRequest]:
    """Group what an architecture result has written into one write request per document.

    A fact and a diagram go to the request of their home, a restatement to the request of the
    document it is in, and a settlement to the request of each document holding a statement that
    lost, with only that document's places.

    Returns:
        Each document's path under the architecture root with its request, whose ``resultPath``
        is still empty; in path order.

    """
    requests: dict[str, WriteRequest] = {}

    def of(document: str) -> WriteRequest:
        return requests.setdefault(document, _empty(result["bead"]))

    for fact in result["facts"]:
        of(_document(arch, fact["home"]))["facts"].append(fact)
    for restatement in result["restatements"]:
        of(_document(arch, restatement["at"]))["restatements"].append(restatement)
    for drawn in result["diagrams"]:
        of(_document(arch, drawn["home"]))["diagrams"].append(drawn)
    settlement: AppliedSettlement
    for settlement in result["settlements"]:
        documents: list[str] = list(dict.fromkeys(_document(arch, place) for place in settlement["corrections"]))
        for document in documents:
            places: list[SourceHeading] = [
                place for place in settlement["corrections"] if _document(arch, place) == document
            ]
            of(document)["settlements"].append({**settlement, "corrections": places})
    return dict(sorted(requests.items()))


def _written(asked: Path, request: WriteRequest) -> bool:
    """Tell whether a write request was already written as it stands.

    Returns:
        True when the request file holds exactly this request and its result file is a valid write result.

    """
    if not asked.is_file():
        return False
    result: Path = Path(request["resultPath"])
    try:
        if strict_json(asked) != request or not result.is_file():
            return False
        validate_write_result(strict_json(result), str(result))
    except OSError, ValueError:
        return False
    return True


def write_steps(run: StepRun, arch: Path, helpers: Path, result: ArchitectureResult) -> tuple[StepGroup, ...]:
    """Plan the document writes an accepted architecture result needs, after the step that accepts it.

    Each document's request (:func:`write_requests`) is written to the helpers folder; a document
    whose request file already holds the same request with a valid result is not written again.

    Returns:
        One group of ``architecture-maintainer`` steps, one per document to write, each handed
        its request as the parameter ``request``; none when every document is written as decided.

    Raises:
        ArchitectureStepError: A document's path gives no name to file its request under.

    """
    steps: list[NewStep] = []
    document: str
    request: WriteRequest
    for document, request in write_requests(arch, result).items():
        try:
            name: str = f"{WRITE_PREFIX}{slug(document)}"
        except ValueError as error:
            raise ArchitectureStepError(
                run,
                f"the document {document!r} has no name to file its request under: {error}",
            ) from None
        asked: Path = helpers / f"{name}{REQUEST_SUFFIX}"
        stated: WriteRequest = {**request, "resultPath": str(helpers / f"{name}.result.json")}
        validate_write_request(stated)
        if _written(asked, stated):
            continue
        write_json(asked, json_object(stated))
        steps.append(
            NewStep(
                {
                    "description": f"Write {document} as the solutions architect decided",
                    "purpose": "Each design fact is stated in its one home, and every other document links to it",
                    "agent": MAINTAINER,
                },
                params={PARAM_REQUEST: str(asked)},
            ),
        )
    return (StepGroup(tuple(steps)),) if steps else ()
