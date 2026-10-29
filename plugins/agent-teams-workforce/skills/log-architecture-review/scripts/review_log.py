"""Write and check the architecture review log of one Epic.

The log is the proof that the architecture of an Epic was not designed by instinct: which AWS
tools, MCP servers, skills and specialists reviewed each AWS resource the design defines, the
best practices and security best practices each follows, the Well-Architected review of the
design, and every decision between two or more options with the options and the reason. Its
contract is ``schemas/review-log.schema.json`` beside this skill's ``SKILL.md``.

The solutions architect writes the log with the commands below, so that every entry is checked
against the schema as it is written; the check step of the architecture part runs ``problems``
on the finished log. Each command prints one JSON document on stdout.

- ``init --log PATH --bead ID``: start the log; an existing log for the same Epic is kept.
- ``resource --log PATH --entry JSON|@FILE``: add the review of one resource, or replace the
  entry for the same ``element``.
- ``decision --log PATH --entry JSON|@FILE``: add one decision, or replace the one with its ``id``.
- ``well-architected --log PATH --entry JSON|@FILE``: set the Well-Architected review.
- ``check --log PATH --bead ID [--resource ID=TYPE ...]``: report every problem the check step
  would report, given the AWS resources the design adds or changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, TypedDict, TypeIs

from jsonschema import Draft202012Validator

sys.path.append(str(Path(__file__).resolve().parents[3] / "scripts" / "portfolio"))

import strictschema

if TYPE_CHECKING:
    from collections.abc import Mapping

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
type ToolKind = Literal["mcp-tool", "skill", "agent"]
type Pillar = Literal[
    "operational-excellence",
    "security",
    "reliability",
    "performance-efficiency",
    "cost-optimization",
    "sustainability",
]

SKILL_DIR: Final[Path] = Path(__file__).resolve().parents[1]
SCHEMA_PATH: Final[Path] = SKILL_DIR / "schemas" / "review-log.schema.json"
PILLARS: Final[tuple[Pillar, ...]] = (
    "operational-excellence",
    "security",
    "reliability",
    "performance-efficiency",
    "cost-optimization",
    "sustainability",
)
DEF_RESOURCE: Final = "ResourceReview"
DEF_DECISION: Final = "Decision"
DEF_WELL_ARCHITECTED: Final = "WellArchitectedReview"
FILE_MARK: Final = "@"
PAIR_MARK: Final = "="
MIN_OPTIONS: Final = 2
"""A decision is a choice between two or more options."""


class ToolUse(TypedDict):
    """One use of a tool, a skill or a specialist."""

    kind: ToolKind
    name: str
    asked: str
    outcome: str
    sources: list[str]


class Practice(TypedDict):
    """One best practice a resource's design follows."""

    practice: str
    source: str
    applied: str


class ResourceReview(TypedDict):
    """The review of one AWS resource."""

    element: str
    resourceType: str
    reviewedWith: list[ToolUse]
    bestPractices: list[Practice]
    securityPractices: list[Practice]


class PillarReview(TypedDict):
    """The review of the design against one Well-Architected pillar."""

    pillar: Pillar
    assessment: str
    risks: list[str]
    actions: list[str]


class WellArchitectedReview(TypedDict):
    """The Well-Architected review of the design."""

    reviewedWith: list[ToolUse]
    pillars: list[PillarReview]
    summary: str


class Option(TypedDict):
    """One option a decision considered."""

    option: str
    tradeoffs: str


class Decision(TypedDict):
    """One decision between two or more options."""

    id: str
    question: str
    elements: list[str]
    options: list[Option]
    chosen: str
    reason: str
    sources: list[str]


class ReviewLog(TypedDict):
    """The review log of one Epic."""

    bead: str
    resources: list[ResourceReview]
    wellArchitected: WellArchitectedReview | None
    decisions: list[Decision]


class ReviewLogError(ValueError):
    """A log or an entry does not satisfy the review log's schema, or cannot be read."""


def load_schema() -> dict[str, JsonValue]:
    """Read the review log's schema.

    Returns:
        The decoded schema.

    Raises:
        ReviewLogError: The schema file is not a JSON object.

    """
    decoded: JsonValue = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        message: str = f"{SCHEMA_PATH} is not a JSON object"
        raise ReviewLogError(message)
    return decoded


def schema_problems(value: object, definition: str | None = None) -> list[str]:
    """Describe every way a value fails the schema, or one of its definitions.

    Args:
        value: The decoded document or entry.
        definition: The ``$defs`` entry to validate against; None for the whole log.

    Returns:
        One line per failure, in path order, as ``strictschema.explain_all`` states it: the path,
        the field names it is about, the fields allowed there, the schema rule quoted and the
        schema file with the pointer and definition of the rule; empty when the value conforms.

    Raises:
        ReviewLogError: The schema defines no such entry.

    """
    schema: dict[str, JsonValue] = load_schema()
    target: dict[str, JsonValue] = schema
    if definition is not None:
        definitions: JsonValue = schema.get("$defs")
        if not isinstance(definitions, dict) or definition not in definitions:
            message: str = f"the review log schema defines no {definition!r}"
            raise ReviewLogError(message)
        target = {"$ref": "#/$defs/" + definition, "$defs": definitions}
    return strictschema.explain_all(
        Draft202012Validator(target).iter_errors(value),
        root=target,
        location=SCHEMA_PATH,
        definition=definition,
    )


def _listed(problems: list[str]) -> str:
    """Render schema problems for an error message.

    Returns:
        How many there are, then each one on its own line.

    """
    return f"{len(problems)} problem(s), one per line below\n" + "\n".join(problems)


def is_review_log(value: object) -> TypeIs[ReviewLog]:
    """Tell whether a value satisfies the review log's schema.

    Returns:
        True when the schema accepts the value.

    """
    return not schema_problems(value)


def read_log(path: Path) -> object:
    """Read a log file as decoded JSON, without validating it.

    Returns:
        The decoded document.

    Raises:
        ReviewLogError: The file is missing or is not JSON.

    """
    if not path.is_file():
        message: str = f"the review log {path} does not exist"
        raise ReviewLogError(message)
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        message = f"the review log {path} is not JSON: {error}"
        raise ReviewLogError(message) from error
    return decoded


def load_log(path: Path) -> ReviewLog:
    """Read and validate a log file.

    Returns:
        The log.

    Raises:
        ReviewLogError: The file is missing, is not JSON, or does not satisfy the schema.

    """
    decoded: object = read_log(path)
    if is_review_log(decoded):
        return decoded
    message: str = f"the review log {path} does not satisfy its schema ({SCHEMA_PATH.name}): " + _listed(
        schema_problems(decoded),
    )
    raise ReviewLogError(message)


def _is_decision(value: object) -> TypeIs[Decision]:
    return not schema_problems(value, DEF_DECISION)


def _decision_problems(decision: Decision) -> list[str]:
    """Check what the schema cannot: the chosen option is one of the options, each named once.

    Returns:
        One sentence per problem.

    """
    named: list[str] = [option["option"] for option in decision["options"]]
    found: list[str] = []
    if len(set(named)) != len(named):
        found.append(f"decision {decision['id']} names an option twice")
    if len(set(named)) < MIN_OPTIONS:
        found.append(f"decision {decision['id']} does not state two or more distinct options")
    if decision["chosen"] not in named:
        found.append(f"decision {decision['id']} chose {decision['chosen']!r}, which is not one of its options")
    if not decision["reason"].strip():
        found.append(f"decision {decision['id']} states no reason for its choice")
    return found


def problems(value: object, bead: str, aws_resources: Mapping[str, str]) -> list[str]:
    """Report every problem of a review log, as the check step reports them.

    Args:
        value: The decoded log.
        bead: The Epic the log must be for.
        aws_resources: The AWS resources the design adds or changes: matrix id to ``resourceType``.

    Returns:
        One sentence per problem: each schema failure; a log for another Epic; a decision whose
        options or reason are missing or whose choice is not one of its options; two decisions
        with one id or two entries for one resource; an AWS resource with no entry; and a design
        with an AWS resource and no Well-Architected review, or a review that does not cover
        each pillar once. Empty when the log is complete.

    """
    failures: list[str] = schema_problems(value)
    if failures or not is_review_log(value):
        return [f"the review log does not satisfy its schema: {failure}" for failure in failures]
    found: list[str] = []
    if value["bead"] != bead:
        found.append(f"the review log is for {value['bead']}, not {bead}")
    identifiers: list[str] = [decision["id"] for decision in value["decisions"]]
    found.extend(
        f"two decisions have the id {name}" for name in sorted({i for i in identifiers if identifiers.count(i) > 1})
    )
    for decision in value["decisions"]:
        found.extend(_decision_problems(decision))
    elements: list[str] = [entry["element"] for entry in value["resources"]]
    found.extend(
        f"two resource entries review {name}" for name in sorted({e for e in elements if elements.count(e) > 1})
    )
    found.extend(
        f"the AWS resource {element} ({kind}) has no review entry in the review log"
        for element, kind in sorted(aws_resources.items())
        if element not in elements
    )
    review: WellArchitectedReview | None = value["wellArchitected"]
    if review is None:
        if aws_resources:
            found.append("the design defines AWS resources and the review log has no Well-Architected review")
    elif sorted(pillar["pillar"] for pillar in review["pillars"]) != sorted(PILLARS):
        found.append(f"the Well-Architected review does not cover each of {list(PILLARS)} once")
    return found


def _write(path: Path, log: ReviewLog) -> None:
    """Write a log atomically, so that a reader never sees a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int
    temporary: str
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(log, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    Path(temporary).replace(path)


def _entry(text: str, definition: str) -> dict[str, JsonValue]:
    """Decode an entry given inline or as ``@<file>`` and check it against one definition.

    Returns:
        The entry.

    Raises:
        ReviewLogError: The entry is not JSON or does not satisfy the definition.

    """
    raw: str = Path(text[1:]).read_text(encoding="utf-8") if text.startswith(FILE_MARK) else text
    try:
        decoded: JsonValue = json.loads(raw)
    except json.JSONDecodeError as error:
        message: str = f"the entry is not JSON: {error}"
        raise ReviewLogError(message) from error
    failures: list[str] = schema_problems(decoded, definition)
    if failures or not isinstance(decoded, dict):
        message = f"the entry does not satisfy {definition} ({SCHEMA_PATH.name}#/$defs/{definition}): " + _listed(
            failures,
        )
        raise ReviewLogError(message)
    return decoded


def _replaced(entries: list[dict[str, JsonValue]], entry: dict[str, JsonValue], key: str) -> list[dict[str, JsonValue]]:
    """Put an entry in a list, replacing the one with the same key.

    Returns:
        The list with the entry at the place of the one it replaces, or at the end.

    """
    if any(held.get(key) == entry[key] for held in entries):
        return [entry if held.get(key) == entry[key] else held for held in entries]
    return [*entries, entry]


def _change(path: Path, member: str, entry: dict[str, JsonValue], key: str | None) -> ReviewLog:
    """Apply one entry to the log on disk and write it back, refusing a result the schema refuses.

    Returns:
        The log as written.

    Raises:
        ReviewLogError: The log does not satisfy its schema before or after the change.

    """
    load_log(path)
    decoded: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    log: dict[str, JsonValue] = dict(decoded) if isinstance(decoded, dict) else {}
    if key is None:
        log[member] = entry
    else:
        held: JsonValue = log[member]
        entries: list[dict[str, JsonValue]] = (
            [item for item in held if isinstance(item, dict)] if isinstance(held, list) else []
        )
        log[member] = list(_replaced(entries, entry, key))
    if not is_review_log(log):
        message: str = f"the change leaves the review log unsatisfied ({SCHEMA_PATH.name}): " + _listed(
            schema_problems(log),
        )
        raise ReviewLogError(message)
    _write(path, log)
    return log


def _resources(pairs: list[str]) -> dict[str, str]:
    """Read ``ID=TYPE`` pairs.

    Returns:
        Matrix id to resource type.

    Raises:
        ReviewLogError: A pair has no ``=``.

    """
    resources: dict[str, str] = {}
    pair: str
    for pair in pairs:
        element, mark, kind = pair.partition(PAIR_MARK)
        if not mark or not element or not kind:
            message: str = f"--resource takes ID=TYPE, got {pair!r}"
            raise ReviewLogError(message)
        resources[element] = kind
    return resources


def _run(args: argparse.Namespace) -> JsonValue:
    """Run one command.

    Returns:
        The JSON document the command prints.

    Raises:
        ReviewLogError: An argument has the wrong type.

    """
    command: object = args.command
    log_path: object = args.log
    if not isinstance(command, str) or not isinstance(log_path, str):
        message: str = "the command and --log are strings"
        raise ReviewLogError(message)
    path: Path = Path(log_path)
    if command in {"init", "check"}:
        bead: object = args.bead
        if not isinstance(bead, str):
            message = "--bead is a string"
            raise ReviewLogError(message)
        if command == "init":
            if path.is_file() and load_log(path)["bead"] == bead:
                return {"log": str(path), "created": False}
            _write(path, {"bead": bead, "resources": [], "wellArchitected": None, "decisions": []})
            return {"log": str(path), "created": True}
        pairs: object = args.resource
        listed: list[str] = [str(pair) for pair in pairs] if isinstance(pairs, list) else []
        found: list[str] = problems(read_log(path), bead, _resources(listed))
        return {"valid": not found, "problems": list(found)}
    text: object = args.entry
    if not isinstance(text, str):
        message = "--entry is a string"
        raise ReviewLogError(message)
    written: ReviewLog
    if command == "resource":
        written = _change(path, "resources", _entry(text, DEF_RESOURCE), "element")
    elif command == "decision":
        entry: dict[str, JsonValue] = _entry(text, DEF_DECISION)
        refused: list[str] = _decision_problems(entry) if _is_decision(entry) else []
        if refused:
            message = "; ".join(refused)
            raise ReviewLogError(message)
        written = _change(path, "decisions", entry, "id")
    else:
        written = _change(path, "wellArchitected", _entry(text, DEF_WELL_ARCHITECTED), None)
    return {
        "log": str(path),
        "resources": len(written["resources"]),
        "decisions": len(written["decisions"]),
        "wellArchitected": written["wellArchitected"] is not None,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the command line.

    Returns:
        0 on success and for a complete log; 1 for a log ``check`` finds problems in, or an error.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "check"):
        sub: argparse.ArgumentParser = commands.add_parser(name)
        sub.add_argument("--log", required=True)
        sub.add_argument("--bead", required=True)
        if name == "check":
            sub.add_argument("--resource", action="append", default=[], help="ID=TYPE of an AWS resource")
    for name in ("resource", "decision", "well-architected"):
        sub = commands.add_parser(name)
        sub.add_argument("--log", required=True)
        sub.add_argument("--entry", required=True, help="the entry as JSON, or @<file>")
    args: argparse.Namespace = parser.parse_args(argv)
    try:
        result: JsonValue = _run(args)
    except (ReviewLogError, OSError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}) + "\n")
        return 1
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 1 if isinstance(result, dict) and result.get("valid") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
