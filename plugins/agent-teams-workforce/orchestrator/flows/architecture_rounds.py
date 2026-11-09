"""The work the script does between the solutions architect's sessions.

The architect never starts an agent. Each of its steps is a fresh session that writes a file, and
the step that accepts that file plans what follows it, among its siblings:

- a round of requests (the Analyze step's ``questions.json``, or a result's ``requests``): one
  step per request whose answer cannot be reused (:func:`reuse_refusal`), each started as the agent
  the request names, then a fresh Decide step of the architect, handed every answer. An answer is
  reused only when it is valid and was asked of the same agent, with the same request, under the
  same answer contract and with the same contents of the documents the request concerns
  (:func:`answer_basis`); a change to any of them asks again only the requests it affects;
- a result with no open request: at most three ``architecture-maintainer`` steps, one per group of
  arc42 sections (:data:`SECTION_GROUPS`) whose write request was not already written, each
  write request built here from the result's ``facts``, ``restatements``, ``settlements`` and
  ``diagrams``, so one session reads each neighbouring document of its group once. Each request
  and its result are files of their own, named for the request's content, so a later write of a
  group never replaces the files of an earlier one.

A Decide step is handed a digest of its answers (:func:`write_digest`), so it reads a few KB
instead of every answer file. The digest names each answer's writer from one walk of one read of
the journal (:func:`_answer_writers`).
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
    ARCHITECTURE_RESULT_SCHEMA_PATH,
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
    from collections.abc import Iterable, Mapping, Sequence

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
BASIS_SUFFIX: Final = ".basis.json"
"""What the basis file of a request adds to its answer file's stem: what the answer was asked under
(:func:`answer_basis`)."""
PARAM_ASKED_BECAUSE: Final = "askedBecause"
"""The parameter that hands a specialist step why its answer could not be reused (:func:`reuse_refusal`)."""
REFUSED_NO_ANSWER: Final = "answer"
"""Why an answer is not reused when its file is missing or is not a valid answer."""
REFUSED_REQUEST: Final = "request"
"""Why an answer is not reused when it was asked with another request, or nothing records what it was asked."""
ANSWER_DEFINITION: Final = "SpecialistAnswer"
"""The definition in the architecture result schema that every answer satisfies."""
_DEFINITION_REF: Final[re.Pattern[str]] = re.compile(r'"#/\$defs/(?P<name>[^"]+)"')
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


def _sibling(answer: Path, suffix: str) -> Path:
    """Name a file kept beside an answer file.

    Returns:
        The path with the answer file's stem and ``suffix``.

    """
    return answer.with_name(answer.stem + suffix)


def _held_json(path: Path) -> object:
    """Read a file the script wrote beside an answer, when it can be read.

    Returns:
        The decoded file; None when it is missing or is not strict JSON.

    """
    if not path.is_file():
        return None
    try:
        return strict_json(path)
    except OSError, ValueError:
        return None


def _valid_answer(path: Path) -> bool:
    """Tell whether a file holds a valid specialist answer.

    Returns:
        True when the file is a valid specialist answer (:func:`read_answer`).

    """
    if not path.is_file():
        return False
    try:
        read_answer(strict_json(path), str(path))
    except OSError, ValueError:
        return False
    return True


def _digest(content: bytes) -> str:
    """Fingerprint some bytes.

    Returns:
        The SHA-256 of the bytes, in hex.

    """
    return hashlib.sha256(content).hexdigest()


def _json_digest(value: object) -> str:
    """Fingerprint a JSON value by its content, whatever the order of its keys.

    Returns:
        The SHA-256 of its canonical text.

    """
    return _digest(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def _file_digest(path: Path) -> str | None:
    """Fingerprint a file's bytes, read in chunks.

    Returns:
        The SHA-256 of the file; None when there is no file at the path.

    """
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _definitions(schema: Path) -> dict[str, object]:
    """Read the definitions of a JSON schema.

    Returns:
        Each definition under ``$defs``, by name.

    Raises:
        TypeError: The schema holds no ``$defs`` object.

    """
    loaded: object = json.loads(schema.read_text(encoding="utf-8"))
    held: object = loaded.get("$defs") if isinstance(loaded, dict) else None
    if not isinstance(held, dict):
        message: str = f"{schema} holds no $defs object"
        raise TypeError(message)
    return {str(name): definition for name, definition in held.items()}


def _contract_closure(definitions: Mapping[str, object], root: str) -> dict[str, object]:
    """Collect a definition with every definition it refers to, directly or through another.

    Returns:
        Each such definition, by name.

    """
    closure: dict[str, object] = {}
    pending: list[str] = [root]
    while pending:
        name: str = pending.pop()
        if name in closure or name not in definitions:
            continue
        closure[name] = definitions[name]
        pending.extend(found["name"] for found in _DEFINITION_REF.finditer(json.dumps(definitions[name])))
    return closure


def answer_contract() -> str:
    """Fingerprint the contract every specialist answer satisfies.

    Returns:
        The SHA-256 of the SpecialistAnswer definition with every definition it refers to, so a
        change to any other definition of the schema leaves it as it was.

    """
    return _json_digest(_contract_closure(_definitions(ARCHITECTURE_RESULT_SCHEMA_PATH), ANSWER_DEFINITION))


def _source_file(arch: Path, source: str) -> Path | None:
    """Name the file a concern's source is, when it is one.

    Returns:
        The document under the architecture root a citation names (:func:`cited_document`), else
        the absolute path the source states; None for a source that names no file path, which the
        request's own fingerprint covers.

    """
    document: str | None = cited_document(arch, source)
    if document is not None:
        return arch / document_path(document)
    stated: Path = Path(source.strip())
    return stated if stated.is_absolute() else None


def _source_digests(arch: Path, concerns: Iterable[SourceHeading]) -> dict[str, JsonValue]:
    """Fingerprint the files a request's concerns are in.

    Returns:
        Each file's path, in path order, with the SHA-256 of its bytes; None for a file that does
        not exist, so its later creation changes the fingerprint too.

    """
    files: set[Path] = {found for concern in concerns if (found := _source_file(arch, concern["source"])) is not None}
    return {str(path): _file_digest(path) for path in sorted(files)}


def answer_basis(arch: Path, agent: str, request: SpecialistRequest) -> dict[str, JsonValue]:
    """State what an answer is asked under, the evidence its reuse is checked against.

    Args:
        arch: The architecture root, which a concern's document is named under.
        agent: The agent asked.
        request: The request.

    Returns:
        The agent, the fingerprint of the whole request (its question, bounds, concerns, trusted
        code and answer path), of the answer contract (:func:`answer_contract`) and of each file
        the request's concerns are in (:func:`_source_digests`).

    """
    return {
        "agent": agent,
        REFUSED_REQUEST: _json_digest(request),
        "contract": answer_contract(),
        "sources": _source_digests(arch, request["concerns"]),
    }


def reuse_refusal(entry: AgentRequest, arch: Path) -> str | None:
    """Tell why a request's existing answer cannot stand for a new session, if it cannot.

    An answer is reused only when its file is a valid answer and the basis file beside it
    (:data:`BASIS_SUFFIX`), written when its request was planned, states the basis the request has
    now (:func:`answer_basis`). Planning a request removes the answer at its path before it writes
    the basis (:func:`round_steps`), so an answer beside a basis was written under that basis. An
    answer written before basis files existed has none: it is reused only when the request file
    beside it holds exactly this request.

    Args:
        entry: The request, with the agent it names.
        arch: The architecture root.

    Returns:
        None when the answer can be reused; otherwise :data:`REFUSED_NO_ANSWER`, or the first
        member of the basis that differs (``agent``, ``request``, ``contract`` or ``sources``).

    """
    request: SpecialistRequest = entry["request"]
    answer: Path = Path(request["answerPath"])
    if not _valid_answer(answer):
        return REFUSED_NO_ANSWER
    held: object = _held_json(_sibling(answer, BASIS_SUFFIX))
    if held is None:
        return None if _held_json(_sibling(answer, REQUEST_SUFFIX)) == request else REFUSED_REQUEST
    now: dict[str, JsonValue] = answer_basis(arch, step_journal.agent_name(entry["agent"]), request)
    stated: dict[object, object] = held if isinstance(held, dict) else {}
    return next((member for member, value in now.items() if stated.get(member) != value), None)


def answered(entry: AgentRequest, arch: Path) -> bool:
    """Tell whether a request's existing answer can be reused.

    Returns:
        True when :func:`reuse_refusal` finds no reason to ask again.

    """
    return reuse_refusal(entry, arch) is None


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
    return _handed(run, _answer_writers(step_journal.steps_in_order(run.journal())))


def _handed(run: StepRun, writers: Mapping[str, Step]) -> list[Path]:
    """Name every specialist answer an architect step is handed, from the writers of one journal read.

    Returns:
        What :func:`handed_answers` returns.

    """
    held: list[Path] = [
        path for path in run.inputs.files(LABEL_ANSWER) if _writer_agent(writers, path) not in SCRIPT_STARTED
    ]
    return list(dict.fromkeys([*held, *map(Path, _answered_before(run))]))


def round_steps(run: StepRun, requests: Sequence[AgentRequest], number: int, arch: Path) -> StepGroup:
    """Plan one round of requests after an architect step, then the Decide step that uses the answers.

    Each request whose answer cannot be reused (:func:`reuse_refusal`) has the answer at its
    answer path removed, so the basis written next never stands beside an answer asked under
    another one, is written beside that path, with its basis (:func:`answer_basis`), and gets one
    step, performed by the agent
    the request names and handed the request file as the parameter ``request`` and why it is
    asked as the parameter ``askedBecause``. The Decide step's inputs are those steps and the completing step's own
    inputs, so it is handed every answer of the chain, the findings and rulings the completing
    step was handed, and the round's number. A request whose answer can be reused gets no step:
    its answer file goes to the Decide step as the parameter ``answered``, with those the
    completing step was handed the same way.

    Args:
        run: The architect step whose output holds the requests.
        requests: The requests, one per agent.
        number: The round these requests make.
        arch: The architecture root, which a concern's document is named under.

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
        refusal: str | None = reuse_refusal(entry, arch)
        if refusal is None:
            kept[entry["request"]["answerPath"]] = agent
            continue
        answer: Path = Path(entry["request"]["answerPath"])
        answer.unlink(missing_ok=True)
        asked: Path = _sibling(answer, REQUEST_SUFFIX)
        write_json(asked, json_object(entry["request"]))
        write_json(_sibling(answer, BASIS_SUFFIX), answer_basis(arch, agent, entry["request"]))
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
                params={PARAM_REQUEST: str(asked), PARAM_ASKED_BECAUSE: refusal},
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


def _answer_writers(steps: Iterable[Step]) -> dict[str, Step]:
    """Index the agent step that wrote each answer file, from one walk of one journal read.

    Args:
        steps: The journal's steps in walk order (``step_journal.steps_in_order``).

    Returns:
        Each answer file's path, with the last agent step in walk order that holds it as its answer.

    """
    return {
        held["path"]: step
        for step in steps
        if step.get("agent") is not None
        for held in step["artifacts"]
        if held["name"] == LABEL_ANSWER and held["kind"] != "value"
    }


def _writer_agent(writers: Mapping[str, Step], path: Path) -> str | None:
    """Name the agent of the step that wrote an answer file.

    Returns:
        The agent; None when no agent step of the journal holds the file.

    """
    writer: Step | None = writers.get(str(path))
    return None if writer is None else writer.get("agent")


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
    ordered: list[Step] = step_journal.steps_in_order(run.journal())
    writers: dict[str, Step] = _answer_writers(ordered)
    answers: list[Path] = _handed(run, writers)
    if not answers:
        return None
    before: dict[str, str] = _answered_before(run)
    digested: list[DigestedAnswer] = []
    stale: list[StaleInputError] = []
    path: Path
    for path in answers:
        try:
            answer: SpecialistAnswer = checked_output(run, path, read_answer, writers.get(str(path)))
        except StaleInputError as found:
            stale.append(found)
            continue
        agent: str = _writer_agent(writers, path) or before.get(str(path), "unknown")
        digested.append(_digested(agent, path, answer))
    if stale:
        position: dict[str, int] = {step["id"]: index for index, step in enumerate(ordered)}
        first: StaleInputError = min(stale, key=lambda found: position[found.writer])
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
