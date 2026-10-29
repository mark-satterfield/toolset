"""The work the script does between the solutions architect's sessions.

The architect never starts an agent. Each of its steps is a fresh session that writes a file, and
the step that accepts that file plans what follows it, among its siblings:

- a round of requests (the Analyze step's ``questions.json``, or a result's ``requests``): one
  step per request whose answer is not yet a valid answer, each started as the agent the request
  names, then a fresh Decide step of the architect, handed every answer;
- a result with no open request: at most three ``architecture-maintainer`` steps, one per group of
  arc42 sections (:data:`SECTION_GROUPS`) whose write request was not already written, each
  write request built here from the result's ``facts``, ``restatements``, ``settlements`` and
  ``diagrams``, so one session reads each neighbouring document of its group once. Each request
  and its result are files of their own, named for the request's content, so a later write of a
  group never replaces the files of an earlier one.

A Decide step is handed a digest of its answers (:func:`write_digest`), so it reads a few KB
instead of every answer file.
"""

from __future__ import annotations

import hashlib
import json
import re
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

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.io import json_object, write_json
from orchestrator.core.journal_steps import NewStep, StepGroup
from orchestrator.core.models import StaleInputError
from orchestrator.flows.architecture_files import (
    ARCHITECT,
    LABEL_ANSWER,
    MAINTAINER,
    PARAM_REQUEST,
    SCRIPT_STARTED,
    checked_output,
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
PARAM_ANSWERED: Final = "answered"
"""The parameter that hands a Decide step each answer of its chain that no step of it wrote, because
the answer file already held a valid answer when its request was planned, with the agent asked."""
MAX_ROUNDS: Final = 2
"""How many rounds of requests one chain of architect steps may put to the specialists."""
REQUEST_SUFFIX: Final = ".request.json"
"""What the request file of a request adds to its answer file's stem."""
WRITE_PREFIX: Final = "write-"
DIGEST_PREFIX: Final = "digest-"
ID_LENGTH: Final = 8
"""How much of a step id names a file the script writes for that step."""
SECTION_GROUPS: Final[tuple[tuple[str, str, frozenset[int]], ...]] = (
    ("structure", "the building blocks, the detailed design and the sections before them", frozenset(range(1, 6))),
    ("runtime", "the runtime and deployment views", frozenset({6, 7})),
    ("concepts", "the crosscutting concepts and the sections after them", frozenset(range(8, 13))),
)
"""The groups one ``architecture-maintainer`` session writes, each with what it covers and its arc42
section numbers; ``detailed/`` and any other document go to the first."""
_SECTION: Final[re.Pattern[str]] = re.compile(r"^arc42/(?P<number>\d{2})-")


RETIRED_REASON_SOURCE: Final = "source"
"""The key a reason of a specialist answer may hold for its one source, which the answer contract
no longer defines: a reason lists its sources under ``sources`` (:func:`read_answer`)."""
REASON_SOURCES: Final = "sources"


def _reason_with_sources(reason: object) -> object:
    """Move a reason's retired one source (:data:`RETIRED_REASON_SOURCE`) into ``sources``.

    Returns:
        The reason with ``sources`` holding that one source, when it is an object that holds the
        retired key and no ``sources``; otherwise the reason as it was.

    """
    if not isinstance(reason, dict) or RETIRED_REASON_SOURCE not in reason or REASON_SOURCES in reason:
        return reason
    moved: dict[str, object] = {key: held for key, held in reason.items() if key != RETIRED_REASON_SOURCE}
    moved[REASON_SOURCES] = [reason[RETIRED_REASON_SOURCE]]
    return moved


def read_answer(value: object, where: str = "SpecialistAnswer") -> SpecialistAnswer:
    """Validate a decoded specialist answer, its reasons first brought to the current shape.

    Each reason that holds the retired one source is read as one that lists it under ``sources``
    (:func:`_reason_with_sources`); every other key and value is checked as it is.

    Returns:
        The answer, typed; ``validate_specialist_answer`` raises ``ArchitectureWorkError`` for an
        answer that does not satisfy the SpecialistAnswer definition.

    """
    if isinstance(value, dict) and isinstance(value.get("reasons"), list):
        value = {**value, "reasons": [_reason_with_sources(reason) for reason in value["reasons"]]}
    return validate_specialist_answer(value, where)


def answered(request: SpecialistRequest) -> bool:
    """Tell whether a request's answer file already holds a valid answer.

    Returns:
        True when the file at the request's answer path is a valid specialist answer (:func:`read_answer`).

    """
    path: Path = Path(request["answerPath"])
    if not path.is_file():
        return False
    try:
        read_answer(strict_json(path), str(path))
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


def _answered_before(run: StepRun) -> dict[str, str]:
    """Read the answers a step is handed that no step of its chain wrote.

    Returns:
        Each such answer file's path, with the agent its request named; none for a step planned
        without them.

    """
    held: JsonValue = run.params().get(PARAM_ANSWERED, {})
    if not isinstance(held, dict):
        return {}
    return {path: agent for path, agent in held.items() if isinstance(agent, str)}


def handed_answers(run: StepRun) -> list[Path]:
    """Name every specialist answer an architect step is handed.

    An ``answer`` is a specialist's when the step that holds it is performed by an agent the
    architect's requests may name; a step of an agent the script starts from the result itself
    (:data:`SCRIPT_STARTED`) holds a file of that agent's own contract.

    Returns:
        The specialists' answers its inputs hold, then each answer its chain did not start again
        (:data:`PARAM_ANSWERED`), each once.

    """
    agents: dict[str, str] = _answer_agents(run)
    held: list[Path] = [path for path in run.inputs.files(LABEL_ANSWER) if agents.get(str(path)) not in SCRIPT_STARTED]
    return list(dict.fromkeys([*held, *map(Path, _answered_before(run))]))


def round_steps(run: StepRun, requests: Sequence[AgentRequest], number: int) -> StepGroup:
    """Plan one round of requests after an architect step, then the Decide step that uses the answers.

    Each request whose answer is not yet a valid answer is written beside its answer path and gets
    one step, performed by the agent the request names and handed the request file as the
    parameter ``request``. The Decide step's inputs are those steps and the completing step's own
    inputs, so it is handed every answer of the chain, the findings and rulings the completing
    step was handed, and the round's number. A request whose answer is already valid gets no step:
    its answer file goes to the Decide step as the parameter ``answered``, with those the
    completing step was handed the same way.

    Args:
        run: The architect step whose output holds the requests.
        requests: The requests, one per agent.
        number: The round these requests make.

    Returns:
        The group, placed after the completing step.

    """
    steps: list[NewStep] = []
    refs: list[str] = []
    kept: dict[str, str] = _answered_before(run)
    index: int
    entry: AgentRequest
    for index, entry in enumerate(requests):
        agent: str = step_journal.agent_name(entry["agent"])
        if answered(entry["request"]):
            kept[entry["request"]["answerPath"]] = agent
            continue
        answer: Path = Path(entry["request"]["answerPath"])
        asked: Path = answer.with_name(answer.stem + REQUEST_SUFFIX)
        write_json(asked, json_object(entry["request"]))
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
    params: dict[str, JsonValue] = {PARAM_ROUND: number}
    if kept:
        params[PARAM_ANSWERED] = dict(kept)
    return StepGroup((*steps, NewStep(decide, params=params)))


def _answer_writer(run: StepRun, path: Path) -> Step | None:
    """Find the agent step that wrote an answer file.

    Returns:
        The last agent step in walk order that holds the file as its answer; None when no step
        of the journal holds it.

    """
    writer: Step | None = None
    step: Step
    for step in step_journal.steps_in_order(run.journal()):
        if "agent" not in step:
            continue
        if any(
            held["name"] == LABEL_ANSWER and held["kind"] != "value" and held["path"] == str(path)
            for held in step["artifacts"]
        ):
            writer = step
    return writer


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

    Each answer is read with :func:`checked_output`: an answer the current contract refuses,
    written by a session made under another agent definition or contracts, sends its writer's
    step to run again (``StaleInputError``) instead of failing the architect's step. Every answer
    is read before that is raised, and the error names the first writer in walk order with the
    evidence of every stale answer: the journal runner sets that step and every step after it
    back to planned, so every stale answer's writer runs again in the one replan.

    Returns:
        The digest file, in the helpers folder and named for the step; None when the step is
        handed no answer.

    Raises:
        StaleInputError: At least one answer was written to an earlier contract.

    """
    answers: list[Path] = handed_answers(run)
    if not answers:
        return None
    agents: dict[str, str] = {**_answered_before(run), **_answer_agents(run)}
    digested: list[DigestedAnswer] = []
    stale: list[StaleInputError] = []
    path: Path
    for path in answers:
        try:
            answer: SpecialistAnswer = checked_output(run, path, read_answer, _answer_writer(run, path))
        except StaleInputError as found:
            stale.append(found)
            continue
        digested.append(_digested(agents.get(str(path), "unknown"), path, answer))
    if stale:
        order: list[str] = [step["id"] for step in step_journal.steps_in_order(run.journal())]
        first: StaleInputError = min(stale, key=lambda found: order.index(found.writer))
        raise StaleInputError(first.stage, first.writer, tuple(text for found in stale for text in found.evidence))
    digest: AnswersDigest = {"answers": digested}
    validate_answers_digest(digest)
    path = helpers / f"{DIGEST_PREFIX}{run.step['id'][:ID_LENGTH]}.json"
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
    """Start the write request of one group of documents.

    Returns:
        A request with nothing to write and no result path yet.

    """
    return {"bead": bead, "facts": [], "restatements": [], "settlements": [], "diagrams": [], "resultPath": ""}


def section_group(document: str) -> str:
    """Name the group of arc42 sections a document is written with.

    Args:
        document: The document's path under the architecture root.

    Returns:
        The name of the group in :data:`SECTION_GROUPS` that holds its arc42 section; the first
        group for a document under ``detailed/`` or outside the numbered sections.

    """
    found: re.Match[str] | None = _SECTION.match(document)
    number: int = 0 if found is None else int(found["number"])
    return next((name for name, _covers, numbers in SECTION_GROUPS if number in numbers), SECTION_GROUPS[0][0])


def write_requests(arch: Path, result: ArchitectureResult) -> dict[str, WriteRequest]:
    """Group what an architecture result has written into one write request per group of sections.

    A fact and a diagram go to the request of their home's group, a restatement to the request of
    the group of the document it is in, and a settlement to the request of each group holding a
    statement that lost, with only that group's places.

    Returns:
        Each group's name with its request, whose ``resultPath`` is still empty; in the order of
        :data:`SECTION_GROUPS`, holding only groups with something to write.

    """
    requests: dict[str, WriteRequest] = {}

    def of(citation: SourceHeading) -> WriteRequest:
        return requests.setdefault(section_group(_document(arch, citation)), _empty(result["bead"]))

    for fact in result["facts"]:
        of(fact["home"])["facts"].append(fact)
    for restatement in result["restatements"]:
        of(restatement["at"])["restatements"].append(restatement)
    for drawn in result["diagrams"]:
        of(drawn["home"])["diagrams"].append(drawn)
    settlement: AppliedSettlement
    for settlement in result["settlements"]:
        placed: dict[str, list[SourceHeading]] = {}
        for place in settlement["corrections"]:
            placed.setdefault(section_group(_document(arch, place)), []).append(place)
        for group, places in placed.items():
            requests.setdefault(group, _empty(result["bead"]))["settlements"].append(
                {**settlement, "corrections": places},
            )
    return {name: requests[name] for name, _covers, _numbers in SECTION_GROUPS if name in requests}


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


def write_name(group: str, request: WriteRequest) -> str:
    """Name the files of one group's write request, for the group and the request's content.

    Returns:
        ``write-<group>-<hash>``: the hash is the start of the SHA-256 of the request, so the same
        request is always named the same and two different requests never share a file.

    """
    content: bytes = json.dumps(request, sort_keys=True, ensure_ascii=False).encode()
    return f"{WRITE_PREFIX}{group}-{hashlib.sha256(content).hexdigest()[:ID_LENGTH]}"


def write_steps(arch: Path, helpers: Path, result: ArchitectureResult) -> tuple[StepGroup, ...]:
    """Plan the document writes an accepted architecture result needs, after the step that accepts it.

    Each group's request (:func:`write_requests`) is written to the helpers folder under its own
    name (:func:`write_name`), with its result path beside it; a group whose request was already
    written with a valid result is not written again. The steps are consecutive agent steps with
    done inputs, so their sessions run together.

    Returns:
        One group of at most three ``architecture-maintainer`` steps, one per group of sections to
        write, each handed its request as the parameter ``request``; none when every group is
        written as decided.

    """
    covering: dict[str, str] = {name: covers for name, covers, _numbers in SECTION_GROUPS}
    steps: list[NewStep] = []
    group: str
    request: WriteRequest
    for group, request in write_requests(arch, result).items():
        name: str = write_name(group, request)
        asked: Path = helpers / f"{name}{REQUEST_SUFFIX}"
        stated: WriteRequest = {**request, "resultPath": str(helpers / f"{name}.result.json")}
        validate_write_request(stated)
        if _written(asked, stated):
            continue
        write_json(asked, json_object(stated))
        steps.append(
            NewStep(
                {
                    "description": f"Write {covering[group]} as the solutions architect decided",
                    "purpose": "Each design fact is stated in its one home, and every other document links to it",
                    "agent": MAINTAINER,
                },
                params={PARAM_REQUEST: str(asked)},
            ),
        )
    return (StepGroup(tuple(steps)),) if steps else ()
