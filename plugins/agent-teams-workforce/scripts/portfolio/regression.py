"""Validate cumulative requirement coverage, prepare a tree for its runs, and confirm fresh evidence for it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import] - The tool exists to run the mapped suite commands.
import sys
import time
import xml.etree.ElementTree as ET  # ruff: ignore[suspicious-xml-etree-import] - Bundled expat 2.7.4 mitigates entity expansion and external entities are never resolved.
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from contracts import JsonObject, JsonValue, json_object
from gitutils import GitError, cmd_hash_files, deadline_scope, separate_group, stop_process
from jsonartifact import read_artifact

KINDS: Final[frozenset[str]] = frozenset({"unit", "contract", "integration", "nonfunctional"})
ORIGINS: Final[frozenset[str]] = frozenset({"task", "existing"})
EXISTING: Final = "existing"
TASK: Final = "task"
CITATION_WORD_CHARACTERS: Final = "A-Za-z0-9_-"
"""A citation token is bounded by none of these characters, so TR-12 never matches TR-120 and E1 never E11."""
PATH_BEFORE: Final[re.Pattern[str]] = re.compile(r"[^\s(\[`'\"]*$")
"""The path text written directly before a cited name: everything back to whitespace, a bracket or a quote."""
SLUG: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
"""A PRD or Epic slug, such as myagent-identity-bot-mitigation or ssbd-sego."""
OPENERS: Final = " \t\n([`'\""
"""Whitespace and opening brackets or quotes that may stand between a qualifying slug and the name it qualifies."""
NAME_REST: Final[re.Pattern[str]] = re.compile(r"[\w.-]*")
"""The rest of a cited file name after its stem, such as .criteria.md."""
NEXT_SOURCE: Final[re.Pattern[str]] = re.compile(
    r"[\w./-]+\.(?:md|json|ya?ml)\b|(?<![\w/.#-])[a-z][a-z0-9]*(?:-[a-z0-9]+){2,}(?![\w/.-])",
)
"""The naming of the next source after a cited spec: another file, or a standalone PRD or Epic slug."""
CRITERION: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9])(AC|DOD)-(\d+)(?:\s*(?:\.\.\.?|\u2013|\u2014|\bto\b)\s*(?:(?:AC|DOD)-)?(\d+))?(?![0-9])",
)
"""An acceptance criterion or Definition of Done id, alone or as a range such as AC-1..AC-5."""
ARTIFACT_FOLDER: Final = "artifacts"
"""A spec path names its Epic's artifact folder in the segment after this one."""
EXECUTION_BUDGET_SECONDS: Final[int] = 500
OUTPUT_TAIL_BYTES: Final[int] = 16384
PASSED: Final = "passed"
FAILED: Final = "failed"
ERRORED: Final = "errored"
NOT_RUN: Final = "not run"

type Mode = Literal["prepare", "check", "validate", "verify", "setup"]
MODES: Final[dict[str, Mode]] = {
    "prepare": "prepare",
    "check": "check",
    "validate": "validate",
    "verify": "verify",
    "setup": "setup",
}


@dataclass(frozen=True, slots=True)
class CliArgs:
    """The validated command line."""

    mode: Mode
    plan: str
    ledger: str
    review: str | None
    source: list[str]
    approved_plan: str | None
    output: str
    tree: str | None
    repos: list[str]
    bindings: str | None = None
    citations: str | None = None


@dataclass(frozen=True, slots=True)
class JunitOutcome:
    """What one JUnit report shows: the test IDs that passed and failed, and its structural errors.

    A test ID reported more than once (one test run under several projects or configurations) passes only when
    every case of it passed, and fails when any case of it failed or errored.
    """

    passed: frozenset[str]
    failed: frozenset[str]
    errors: tuple[str, ...]


def _str(obj: JsonObject, key: str) -> str:
    """Read a required string field.

    Returns:
        The field's string value.

    Raises:
        TypeError: The field is not a string.

    """
    value: JsonValue = obj[key]
    if not isinstance(value, str):
        message: str = f"{key}: expected a string"
        raise TypeError(message)
    return value


def _obj(obj: JsonObject, key: str) -> JsonObject:
    """Read a required object field.

    Returns:
        The field's object value.

    Raises:
        TypeError: The field is not an object.

    """
    value: JsonValue = obj[key]
    if not isinstance(value, dict):
        message: str = f"{key}: expected an object"
        raise TypeError(message)
    return value


def _objs(obj: JsonObject, key: str) -> list[JsonObject]:
    """Read a required list-of-objects field.

    Returns:
        The field's objects.

    Raises:
        TypeError: The field is not a list of objects.

    """
    value: JsonValue = obj[key]
    if not isinstance(value, list):
        message: str = f"{key}: expected a list"
        raise TypeError(message)
    result: list[JsonObject] = []
    for item in value:
        if not isinstance(item, dict):
            message = f"{key}: expected a list of objects"
            raise TypeError(message)
        result.append(item)
    return result


def _strs(obj: JsonObject, key: str) -> list[str]:
    """Read a required list-of-strings field.

    Returns:
        The field's strings.

    Raises:
        TypeError: The field is not a list of strings.

    """
    value: JsonValue = obj[key]
    if not isinstance(value, list):
        message: str = f"{key}: expected a list"
        raise TypeError(message)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            message = f"{key}: expected a list of strings"
            raise TypeError(message)
        result.append(item)
    return result


def _optional_objs(obj: JsonObject | None, key: str) -> list[JsonObject]:
    """Read an optional list-of-objects field, absent meaning empty.

    Returns:
        The field's objects, or an empty list when the object or field is absent.

    """
    if obj is None or key not in obj:
        return []
    return _objs(obj, key)


def _optional_strs(obj: JsonObject | None, key: str) -> list[str]:
    """Read an optional list-of-strings field, absent meaning empty.

    Returns:
        The field's strings, or an empty list when the object or field is absent.

    """
    if obj is None or key not in obj:
        return []
    return _strs(obj, key)


def _flag(obj: JsonObject, key: str) -> bool:
    """Read a required field by its JSON truthiness.

    Returns:
        Whether the field's value is truthy.

    """
    return bool(obj[key])


def read(path: str | Path) -> JsonObject:
    """Read an authoritative artifact, including publication receipts when present.

    Returns:
        The artifact's JSON object.

    """
    return json_object(read_artifact(Path(path)))


def write(path: str | Path, value: JsonValue) -> None:
    """Publish deterministic state atomically."""
    target: Path = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)


def source_errors(paths: list[str]) -> list[str]:
    """Name each requirement source that is not the absolute path of an existing regular file.

    Returns:
        One error per such source; empty when every source is a readable file.

    """
    return [
        f"Requirement source is not an absolute readable file: {value}"
        for value in paths
        if not Path(value).is_absolute() or not Path(value).is_file()
    ]


def source_hashes(paths: list[str]) -> dict[str, str]:
    """Bind the actual source bytes, independent of model-authored evidence prose.

    Returns:
        The SHA-256 of each source file, keyed by its path.

    Raises:
        ValueError: A source is not an absolute readable file.

    """
    errors: list[str] = source_errors(paths)
    if errors:
        raise ValueError(errors[0])
    return {str(Path(value)): hashlib.sha256(Path(value).read_bytes()).hexdigest() for value in paths}


def without_origin(plan: JsonObject) -> JsonObject:
    """Drop each requirement's origin, which the gate derives from the Task's contract rather than keeps.

    Returns:
        The plan with every requirement as it is, less its ``origin``.

    """
    requirements: list[JsonValue] = [
        {key: value for key, value in requirement.items() if key != "origin"}
        for requirement in _objs(plan, "requirements")
    ]
    return {**plan, "requirements": requirements}


def scope(plan: JsonObject) -> JsonObject:
    """Only mapping and execution configuration may change after scope approval.

    A requirement's origin is no part of the scope: the gate derives it (:func:`origins`), so a plan written
    before origins existed and its mapping written after compare equal.

    Returns:
        The plan fields that fix the approved scope.

    """
    stripped: JsonObject = without_origin(plan)
    return {k: stripped[k] for k in ("components", "discovery", "requirements", "sourceFiles")}


def _token_found(text: str, token: str) -> list[int]:
    """Find a citation token as a whole token.

    Returns:
        The start offset of each occurrence.

    """
    pattern: str = rf"(?<![{CITATION_WORD_CHARACTERS}]){re.escape(token)}(?![{CITATION_WORD_CHARACTERS}])"
    return [match.start() for match in re.finditer(pattern, text)]


def _epic_folder(spec: PurePosixPath) -> str | None:
    """Name the Epic artifact folder a spec path runs through.

    Returns:
        The segment after ``artifacts``, or None when the path has none.

    """
    parts: tuple[str, ...] = spec.parts
    if ARTIFACT_FOLDER not in parts[:-1]:
        return None
    return parts[parts.index(ARTIFACT_FOLDER) + 1]


def _names_this_spec(before: str, spec: PurePosixPath) -> bool:
    """Report whether the path written before a spec's name points at this spec.

    A bare name, a path through the spec's Epic artifact folder, or a path ending in the spec's own folders
    names it; a path through any other folder names another Epic's spec of the same name. A bare name
    written directly after a PRD or Epic slug, or a path ending in one, other than this spec's Epic folder
    (whitespace or an opening bracket between them) names that PRD's or Epic's spec of the same name.

    Returns:
        True when the text names this spec.

    """
    found: re.Match[str] | None = PATH_BEFORE.search(before)
    written: tuple[str, ...] = tuple(
        part for part in PurePosixPath(found.group(0) if found else "").parts if part != "/"
    )
    epic: str | None = _epic_folder(spec)
    if written:
        folders: tuple[str, ...] = spec.parent.parts
        return (epic is not None and epic in written) or folders[len(folders) - len(written) :] == written
    words: list[str] = before.rstrip(OPENERS).split()
    qualifier: str = words[-1].rsplit("/", 1)[-1] if words else ""
    return SLUG.fullmatch(qualifier) is None or qualifier == epic


def criteria_ids(text: str) -> set[str]:
    """List the acceptance criterion and Definition of Done ids a text cites, ranges expanded.

    Returns:
        Each id, such as ``AC-3`` or ``DOD-1``; ``AC-1..AC-3`` gives AC-1, AC-2 and AC-3.

    """
    ids: set[str] = set()
    for match in CRITERION.finditer(text):
        kind: str = match.group(1)
        first: int = int(match.group(2))
        last: int = int(match.group(3)) if match.group(3) else first
        ids.update(f"{kind}-{number}" for number in range(first, max(first, last) + 1))
    return ids


def _cited_criteria(text: str, spec_path: str) -> set[str]:
    """Collect the criteria ids a text cites of one spec.

    Each naming of the spec governs the ids written after it, up to the naming of the next source (another
    file, or a standalone PRD or Epic slug) or the next naming of a spec of the same name, so ids written
    for another source are not this spec's.

    Returns:
        The ids cited of this spec; empty when the text never names it.

    """
    spec: PurePosixPath = PurePosixPath(spec_path.split("#", 1)[0])
    stem: str = spec.name.split(".", 1)[0]
    starts: list[int] = _token_found(text, stem) if stem else []
    ends: list[int] = [*starts[1:], len(text)][: len(starts)]
    return {
        criterion
        for start, end in zip(starts, ends, strict=True)
        if _names_this_spec(text[:start], spec)
        for criterion in criteria_ids(_governed(text[:end], start + len(stem)))
    }


def _governed(text: str, name_end: int) -> str:
    """Cut the text a cited spec name governs: from the end of its stem to the naming of the next source.

    Returns:
        The governed text, the rest of the name (such as ``.criteria.md#AC-3``) included.

    """
    rest: re.Match[str] | None = NAME_REST.match(text, name_end)
    after: int = rest.end() if rest else name_end
    following: re.Match[str] | None = NEXT_SOURCE.search(text, after)
    return text[name_end : following.start() if following else len(text)]


def cited(requirement: JsonObject, citations: JsonObject) -> bool:
    """Report whether the Task's contract cites a requirement as its own.

    A requirement is cited when its id or sourceRef holds one of the contract's requirement ids as a whole
    token, or when it names one of the Task's specs (:func:`_names_this_spec`) with an acceptance criterion or
    Definition of Done id the Task's bead lists as its own. The Tasks of a Story share their spec, so naming
    the spec alone, or citing a criterion another Task owns, is no citation.

    Args:
        requirement: One requirement of the plan.
        citations: The Task's contract citations: ``requirementIds``, ``specPaths``, ``acceptanceCriteria`` and
            ``definitionOfDone``.

    Returns:
        True when the contract cites it.

    """
    texts: tuple[str, str] = (_str(requirement, "id"), _str(requirement, "sourceRef"))
    if any(_token_found(text, token) for text in texts for token in _strs(citations, "requirementIds")):
        return True
    own: set[str] = {*_strs(citations, "acceptanceCriteria"), *_strs(citations, "definitionOfDone")}
    return any(_cited_criteria(text, spec) & own for text in texts for spec in _strs(citations, "specPaths"))


def origins(plan: JsonObject, citations: JsonObject) -> dict[str, str]:
    """Derive each requirement's effective origin.

    A requirement the Task's contract cites, or the plan marks task, is task; every other is existing. The
    derivation only raises: a plan cannot mark the Task's own criterion existing, and a missing origin is
    derived, never an error.

    Returns:
        The effective origin of each requirement id.

    """
    return {
        _str(r, "id"): TASK if r.get("origin") == TASK or cited(r, citations) else EXISTING
        for r in _objs(plan, "requirements")
    }


def origin_corrections(plan: JsonObject, effective: dict[str, str]) -> list[JsonValue]:
    """Name each requirement whose effective origin is not the one the plan states.

    Returns:
        One ``{requirementId, planned, effective}`` record per derived or raised origin.

    """
    return [
        {"requirementId": _str(r, "id"), "planned": r.get("origin"), "effective": effective[_str(r, "id")]}
        for r in _objs(plan, "requirements")
        if r.get("origin") != effective[_str(r, "id")]
    ]


def read_citations(path: str) -> JsonObject:
    """Read the Task's contract citations.

    Returns:
        ``requirementIds``, ``specPaths``, ``acceptanceCriteria`` and ``definitionOfDone``, each a list of
        strings, absent meaning empty; a field that is not a list of strings raises TypeError.

    """
    document: JsonObject = json_object(json.loads(Path(path).read_text(encoding="utf-8")))
    fields: tuple[str, ...] = ("requirementIds", "specPaths", "acceptanceCriteria", "definitionOfDone")
    return {field: [*_optional_strs(document, field)] for field in fields}


def _discovery_errors(plan: JsonObject, requirements: list[JsonObject]) -> list[str]:
    """Check that discovery is evidenced and some impacted requirement needs tests.

    Returns:
        The discovery errors.

    """
    errors: list[str] = []
    discovery: JsonObject = _obj(plan, "discovery")
    if (
        not _flag(discovery, "priorRequirementsSearched")
        or not _flag(discovery, "sourceRefs")
        or not _str(discovery, "evidence").strip()
    ):
        errors.append("Prior product requirements and affected dependencies were not evidenced")
    if not _flag(plan, "sourceFiles"):
        errors.append("Requirement discovery has no physical source files")
    if not any(
        _flag(r, "impacted") and any(_flag(a, "required") for a in _objs(r, "applicability")) for r in requirements
    ):
        errors.append("Build has no impacted requirement with required test coverage")
    return errors


def _requirement_errors(plan: JsonObject, requirements: list[JsonObject], ids: list[str]) -> list[str]:
    """Check requirement identity, bindings and layer dispositions.

    Returns:
        The requirement errors.

    """
    errors: list[str] = []
    if not ids or len(ids) != len(set(ids)):
        errors.append("Requirement IDs must be nonempty, source-qualified and unique")
    component_ids: set[str] = {_str(c, "id") for c in _objs(plan, "components")}
    for r in requirements:
        rid: str = _str(r, "id")
        if (
            not _str(r, "sourceRef").strip()
            or not _flag(r, "componentIds")
            or not set(_strs(r, "componentIds")) <= component_ids
        ):
            errors.append(f"{rid}: missing source or component binding")
        if "origin" in r and r["origin"] not in ORIGINS:
            errors.append(f"{rid}: origin must be task or existing")
        layers: list[JsonObject] = _objs(r, "applicability")
        if {_str(a, "kind") for a in layers} != KINDS or len(layers) != len(KINDS):
            errors.append(f"{rid}: every test layer needs an applicability disposition")
        if any(not _str(a, "reason").strip() or not _flag(a, "sourceRefs") for a in layers):
            errors.append(f"{rid}: applicability lacks source evidence")
    return errors


def _run_errors(plan: JsonObject, ids: list[str]) -> list[str]:
    """Check run identity and what each mapping may claim of the run it names.

    Returns:
        The run errors.

    """
    errors: list[str] = []
    plan_runs: list[JsonObject] = _objs(plan, "runs")
    runs: dict[str, JsonObject] = {_str(r, "id"): r for r in plan_runs}
    if len(runs) != len(plan_runs):
        errors.append("Duplicate run IDs")
    for m in _objs(plan, "mappings"):
        req_id: str = _str(m, "requirementId")
        run: JsonObject | None = runs.get(_str(m, "runId"))
        if req_id not in ids or run is None:
            errors.append(f"{req_id}: mapping references unknown requirement or run {_str(m, 'runId')}")
        elif _str(run, "format") == "exitStatus" and (_str(m, "kind") != "nonfunctional" or _flag(m, "testIds")):
            errors.append(
                f"{req_id}/{_str(m, 'kind')}: exitStatus run {_str(run, 'id')} proves only the nonfunctional layer "
                "and names no tests",
            )
    return errors


def _coverage_errors(plan: JsonObject, requirements: list[JsonObject], owned: frozenset[str]) -> list[str]:
    """Check that every required layer of an impacted requirement maps to a run in its repository.

    A requirement the Task owns (``owned``, its effective task origins) is checked as impacted whatever the
    plan's ``impacted`` says, so the Task cannot pass without its own criterion. A junit run needs concrete
    tests.

    Returns:
        The coverage errors.

    """
    errors: list[str] = []
    runs: dict[str, JsonObject] = {_str(r, "id"): r for r in _objs(plan, "runs")}
    mappings: list[JsonObject] = _objs(plan, "mappings")
    for req in requirements:
        if not _flag(req, "impacted") and _str(req, "id") not in owned:
            continue
        req_id: str = _str(req, "id")
        for layer in _objs(req, "applicability"):
            if not _flag(layer, "required"):
                continue
            kind: str = _str(layer, "kind")
            matched: list[JsonObject] = [
                m for m in mappings if _str(m, "requirementId") == req_id and _str(m, "kind") == kind
            ]
            if not matched:
                errors.append(f"{req_id}/{kind}: no mapping to a run")
            for m in matched:
                run: JsonObject | None = runs.get(_str(m, "runId"))
                if run is None or run["repoPath"] != req["repoPath"]:
                    errors.append(f"{req_id}/{kind}: mapping has no matching repository execution")
                elif _str(run, "format") == "junit" and not _flag(m, "testIds"):
                    errors.append(f"{req_id}/{kind}: no concrete tests")
    return errors


def _prior_mapping_errors(plan: JsonObject, previous: JsonObject | None, superseded: set[str]) -> list[str]:
    """Check that prior test mappings survive unless explicitly replaced or superseded.

    Returns:
        The prior-mapping errors.

    """
    errors: list[str] = []
    mappings: list[JsonObject] = _objs(plan, "mappings")
    for mapping in _optional_objs(previous, "mappings"):
        requirement_id: str = _str(mapping, "requirementId")
        if requirement_id in superseded:
            continue
        kind: str = _str(mapping, "kind")
        retained: set[str] = {
            test
            for m in mappings
            if _str(m, "requirementId") == requirement_id and _str(m, "kind") == kind
            for test in _strs(m, "testIds")
        }
        replaced: set[str] = {
            _str(replacement, "oldTestId")
            for replacement in _optional_objs(plan, "replacements")
            if _str(replacement, "requirementId") == requirement_id
            and _str(replacement, "kind") == kind
            and _str(replacement, "reason").strip()
            and _flag(replacement, "newTestIds")
            and set(_strs(replacement, "newTestIds")) <= retained
        }
        if not set(_strs(mapping, "testIds")) <= retained | replaced:
            errors.append(f"{requirement_id}: prior test mapping removed without explicit supersession")
    return errors


def _prior_layer_errors(
    requirements: list[JsonObject],
    old: dict[str, JsonObject],
    ids: list[str],
    superseded: set[str],
) -> list[str]:
    """Check that a previously required layer stays required unless superseded.

    Returns:
        The prior-layer errors.

    """
    errors: list[str] = []
    for req_id in old.keys() & set(ids):
        now: JsonObject = next(r for r in requirements if _str(r, "id") == req_id)
        authorized: bool = req_id in superseded
        now_layers: list[JsonObject] = _objs(now, "applicability")
        errors.extend(
            f"{req_id}: previously required layer removed without supersession"
            for layer in _objs(old[req_id], "applicability")
            if _flag(layer, "required")
            and not any(_str(a, "kind") == _str(layer, "kind") and _flag(a, "required") for a in now_layers)
            and not authorized
        )
    return errors


def _superseded(requirements: list[JsonObject]) -> set[str]:
    """List the prior requirement IDs the plan's requirements supersede with a source and a reason.

    Returns:
        The superseded requirement IDs.

    """
    return {
        _str(s, "id")
        for r in requirements
        for s in _objs(r, "supersedes")
        if _str(s, "sourceRef").strip() and _str(s, "reason").strip()
    }


def _passed_pairs(mappings: list[JsonObject], execution: list[JsonObject]) -> set[tuple[str, str]]:
    """Pair each mapped test with its requirement where the execution records it passing in the mapping's run.

    Returns:
        The ``(requirementId, testId)`` pairs whose test passed.

    """
    passed: set[tuple[str, str]] = {
        (_str(record, "runId"), test) for record in execution for test in _optional_strs(record, "passedTestIds")
    }
    return {
        (_str(mapping, "requirementId"), test)
        for mapping in mappings
        for test in _strs(mapping, "testIds")
        if (_str(mapping, "runId"), test) in passed
    }


def proven(previous: JsonObject | None, plan: JsonObject) -> frozenset[tuple[str, str]]:
    """List the tests a completed build proved for each requirement: the pairs that bind every later Task.

    The ledger is written only by a verification that passed. Its ``proven`` list carries every pair proven so
    far, and a test its mappings name for a requirement and its execution records as passed in that mapping's
    run is proven too, which also reads a ledger written before the list existed. A test the plan's
    ``replacements`` name as replacing a proven test of the same requirement is proven in its place. A
    requirement the plan supersedes binds no longer.

    Args:
        previous: The previous ledger, when there is one.
        plan: The final regression mapping.

    Returns:
        Each proven ``(requirementId, testId)`` pair.

    """
    held: set[tuple[str, str]] = {
        (_str(pair, "requirementId"), _str(pair, "testId")) for pair in _optional_objs(previous, "proven")
    }
    held |= _passed_pairs(_optional_objs(previous, "mappings"), _optional_objs(previous, "execution"))
    renamed: set[tuple[str, str]] = {
        (_str(replacement, "requirementId"), new)
        for replacement in _optional_objs(plan, "replacements")
        if (_str(replacement, "requirementId"), _str(replacement, "oldTestId")) in held
        for new in _strs(replacement, "newTestIds")
    }
    dropped: set[str] = _superseded(_objs(plan, "requirements"))
    return frozenset(pair for pair in held | renamed if pair[0] not in dropped)


def proven_record(held: frozenset[tuple[str, str]], plan: JsonObject, evidence: list[JsonValue]) -> list[JsonValue]:
    """Write the ledger's ``proven`` list after a verification that passed.

    The pairs proven before (:func:`proven`) and the pairs whose test passed in this verification, each kept while
    the plan still maps its test to its requirement.

    Returns:
        Each ``{requirementId, testId}`` pair, sorted.

    """
    mappings: list[JsonObject] = _objs(plan, "mappings")
    mapped: set[tuple[str, str]] = {(_str(m, "requirementId"), test) for m in mappings for test in _strs(m, "testIds")}
    records: list[JsonObject] = [record for record in evidence if isinstance(record, dict)]
    kept: frozenset[tuple[str, str]] = (held | _passed_pairs(mappings, records)) & mapped
    return [{"requirementId": requirement, "testId": test} for requirement, test in sorted(kept)]


def validate(
    plan: JsonObject,
    previous: JsonObject | None = None,
    *,
    complete: bool = False,
    owned: frozenset[str] = frozenset(),
) -> list[str]:
    """Reject incomplete discovery, missing old obligations, and unmapped layers.

    Args:
        plan: The regression plan or final mapping.
        previous: The previous ledger, when there is one.
        complete: Whether the mapping must cover every required layer (the final mapping).
        owned: The requirements whose effective origin is task; each is covered as impacted.

    Returns:
        Every validation error; empty when the plan is acceptable.

    """
    requirements: list[JsonObject] = _objs(plan, "requirements")
    errors: list[str] = _discovery_errors(plan, requirements)
    ids: list[str] = [_str(r, "id") for r in requirements]
    errors.extend(_requirement_errors(plan, requirements, ids))
    errors.extend(_run_errors(plan, ids))
    old: dict[str, JsonObject] = {_str(r, "id"): r for r in _optional_objs(previous, "requirements")}
    superseded: set[str] = _superseded(requirements)
    errors.extend(
        f"{missing}: prior requirement dropped without explicit supersession"
        for missing in old.keys() - set(ids) - superseded
    )
    if old and _flag(_obj(plan, "discovery"), "greenfield"):
        errors.append("Existing cumulative requirements contradict greenfield declaration")
    if complete:
        errors.extend(_coverage_errors(plan, requirements, owned))
        errors.extend(_prior_mapping_errors(plan, previous, superseded))
        errors.extend(_prior_layer_errors(requirements, old, ids, superseded))
    return errors


def _case_state(case: ET.Element) -> str:
    """Classify one JUnit test case.

    Returns:
        ERRORED when it holds an error, FAILED when it holds a failure, PASSED when it executed and was not
        skipped, else NOT_RUN.

    """
    if case.find("error") is not None:
        return ERRORED
    if case.find("failure") is not None:
        return FAILED
    executed: bool = case.get("status", "run").lower() in {"run", "passed", "success"} and case.get(
        "result",
        "completed",
    ).lower() in {"completed", "passed", "success"}
    if executed and case.find("skipped") is None:
        return PASSED
    return NOT_RUN


def junit_results(report: Path, run_id: str) -> JunitOutcome:
    """Parse the executed cases of a JUnit report; an error outside any test case fails closed.

    Returns:
        The passing and failing test IDs and the report's structural errors.

    """
    tree: ET.ElementTree[ET.Element] = ET.parse(report)  # ruff: ignore[suspicious-xml-element-tree-usage] - Bundled expat 2.7.4 mitigates entity expansion and external entities are never resolved.
    errors: list[str] = []
    if tree.getroot().tag not in {"testsuites", "testsuite"}:
        errors.append(f"{run_id}: unsupported JUnit root")
    errors.extend(
        f"{run_id}: suite reports an error outside its test cases"
        for suite in (node for node in tree.iter() if node.tag in {"testsuite", "testsuites"})
        if suite.find("error") is not None
    )
    states: dict[str, set[str]] = {}
    for case in tree.iter("testcase"):
        states.setdefault(f"{case.get('classname', '')}::{case.get('name', '')}", set()).add(_case_state(case))
    return JunitOutcome(
        passed=frozenset(test for test, seen in states.items() if seen == {PASSED}),
        failed=frozenset(test for test, seen in states.items() if seen & {FAILED, ERRORED}),
        errors=tuple(errors),
    )


def _report_path(run: JsonObject, root: Path) -> Path:
    """Resolve and check a junit run's report path.

    Returns:
        The resolved report path under the repository's report folder.

    Raises:
        ValueError: The report is not a regular XML file under the report folder.

    """
    report: Path = Path(_str(run, "reportPath"))
    if not report.is_absolute():
        report = root / report
    report = report.resolve()
    if (
        not report.is_relative_to(root / ".agent-workforce" / "reports")
        or report.suffix != ".xml"
        or (report.exists() and not report.is_file())
    ):
        message: str = "JUnit report must be a regular XML file under .agent-workforce/reports"
        raise ValueError(message)
    return report


def _tree_digest(root: Path, state: Execution) -> str:
    """Hash the repository tree as tested, within what is left of the execution budget.

    Returns:
        The tree digest gitutils reports.

    """
    with deadline_scope(state.remaining()):
        return cmd_hash_files(argparse.Namespace(tree=str(root), files=[]))["treeDigest"]


def _output_tail(log: Path) -> tuple[int, str]:
    """Read the size of a command's output log and its last OUTPUT_TAIL_BYTES.

    Returns:
        The log's size in bytes and its tail, decoded as UTF-8 with undecodable bytes replaced.

    """
    size: int = log.stat().st_size
    with log.open("rb") as handle:
        handle.seek(max(0, size - OUTPUT_TAIL_BYTES))
        return size, handle.read().decode("utf-8", errors="replace")


def _wait(process: subprocess.Popen[str], limit: int, *, own_group: bool) -> int | None:
    """Wait for a command, then make sure it and every process it started have stopped.

    An interruption stops the command the same way before it propagates.

    Returns:
        The exit status, or None when the command ran out of time and was stopped.

    """
    try:
        return process.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        return None
    finally:
        stop_process(process, own_group=own_group)


@dataclass(slots=True)
class Execution:
    """The state one verification shares across its runs."""

    folder: Path
    deadline: float
    setups: dict[tuple[str, str], int]

    def remaining(self) -> int:
        """Seconds left of the execution budget.

        Returns:
            The remaining seconds.

        Raises:
            ValueError: The budget is exhausted.

        """
        left: int = int(self.deadline - time.monotonic())
        if left <= 0:
            message: str = "Regression execution time budget exhausted; evidence retained"
            raise ValueError(message)
        return left

    def shell(self, command: str, root: Path, record: str, context: JsonObject) -> int:
        """Run one command with /bin/sh in the repository, streaming its output to durable logs.

        The complete stdout and stderr go to `<record stem>.stdout.log` and `.stderr.log` beside the
        record as the command writes them, so memory stays bounded and a timed-out command leaves its
        partial output. The record names both logs and holds their sizes and last OUTPUT_TAIL_BYTES.

        Returns:
            The command's exit status.

        Raises:
            ValueError: The command ran out of the execution budget; it was stopped and its record and
                partial output are kept.

        """
        limit: int = self.remaining()
        self.folder.mkdir(parents=True, exist_ok=True)
        stem: str = Path(record).stem
        stdout_log: Path = self.folder / f"{stem}.stdout.log"
        stderr_log: Path = self.folder / f"{stem}.stderr.log"
        own_group: bool = separate_group()
        with (
            stdout_log.open("w", encoding="utf-8") as stdout_file,
            stderr_log.open("w", encoding="utf-8") as stderr_file,
        ):
            process: subprocess.Popen[str] = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - The reviewed plan's commands run by design.
                ["/bin/sh", "-c", command],
                cwd=root,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                process_group=0 if own_group else None,
            )
            exit_code: int | None = _wait(process, limit, own_group=own_group)
        stdout_bytes, stdout_tail = _output_tail(stdout_log)
        stderr_bytes, stderr_tail = _output_tail(stderr_log)
        write(
            self.folder / record,
            {
                **context,
                "command": command,
                "exitCode": exit_code,
                "timedOut": exit_code is None,
                "stdoutLog": str(stdout_log),
                "stderrLog": str(stderr_log),
                "stdoutBytes": stdout_bytes,
                "stderrBytes": stderr_bytes,
                "stdoutTail": stdout_tail,
                "stderrTail": stderr_tail,
            },
        )
        if exit_code is None:
            message: str = (
                f"`{command}` did not finish within {limit}s of the regression execution budget and was stopped;"
                f" its partial output is kept in {self.folder / record}"
            )
            raise ValueError(message)
        return exit_code


@dataclass(frozen=True, slots=True)
class Verification:
    """What one verification needs besides its runs: the plan's mappings and what binds the Task.

    ``origins`` is :func:`origins`; ``proven`` is :func:`proven`.
    """

    state: Execution
    mappings: list[JsonObject]
    origins: dict[str, str]
    proven: frozenset[tuple[str, str]]


def execute(
    plan: JsonObject,
    folder: Path,
    effective: dict[str, str],
    held: frozenset[tuple[str, str]],
) -> tuple[list[str], list[JsonValue]]:
    """Run each run mapped to an impacted or Task-owned requirement, or holding a proven test, after its setup.

    Exit zero alone never establishes per-test coverage of a junit run.

    Args:
        plan: The final regression mapping.
        folder: Where the evidence is written.
        effective: The origins (:func:`origins`).
        held: The proven pairs (:func:`proven`).

    Returns:
        The execution errors and the per-run evidence records.

    """
    state: Execution = Execution(folder=folder, deadline=time.monotonic() + EXECUTION_BUDGET_SECONDS, setups={})
    requirements: list[JsonObject] = _objs(plan, "requirements")
    verification: Verification = Verification(
        state=state,
        mappings=_objs(plan, "mappings"),
        origins=effective,
        proven=held,
    )
    evidence: list[JsonValue] = []
    errors: list[str] = []
    impacted: set[str] = {
        _str(r, "id") for r in requirements if _flag(r, "impacted") or effective.get(_str(r, "id")) == TASK
    }
    needed: set[str] = {
        _str(m, "runId")
        for m in verification.mappings
        if _str(m, "requirementId") in impacted or {(_str(m, "requirementId"), t) for t in _strs(m, "testIds")} & held
    }
    for index, run in enumerate(_objs(plan, "runs")):
        if _str(run, "id") not in needed:
            continue
        run_errors, record = _execute_run(run, index, verification)
        errors.extend(run_errors)
        evidence.append(record)
    return errors, evidence


def collected(evidence: list[JsonValue], name: str) -> list[JsonValue]:
    """Collect one list field of every run record, in run order.

    Returns:
        The entries of each record's ``name`` list.

    """
    values: list[JsonValue] = [record.get(name) for record in evidence if isinstance(record, dict)]
    return [entry for value in values if isinstance(value, list) for entry in value]


def prepare_tree(plan: JsonObject, tree: Path, repos: list[str], folder: Path) -> tuple[list[str], list[JsonValue]]:
    """Run, in ``tree``, the setup of every run of the plan that runs in that tree or in one of ``repos``.

    Each command runs once, in plan order, as verify runs it (:func:`_setup_errors`), so a suite
    run in the tree finds the preconditions the reviewed plan declares.

    Returns:
        The setup errors and the setup records.

    """
    state: Execution = Execution(folder=folder, deadline=time.monotonic() + EXECUTION_BUDGET_SECONDS, setups={})
    root: Path = tree.resolve()
    held: set[Path] = {root, *(Path(repo).resolve() for repo in repos)}
    errors: list[str] = []
    records: list[JsonValue] = []
    for index, run in enumerate(_objs(plan, "runs")):
        if Path(_str(run, "repoPath")).resolve() not in held:
            continue
        run_errors, run_records = _setup_errors(run, f"run-{index}", root, state)
        records.extend(run_records)
        if run_errors:
            errors.extend(run_errors)
            break
    return errors, records


def _setup_errors(run: JsonObject, label: str, root: Path, state: Execution) -> tuple[list[str], list[JsonValue]]:
    """Run the run's setup commands in order, each once per repository per verification.

    Args:
        run: The run whose setup is run.
        label: The stem of each setup record's name, unique to the run and the tree it runs in.
        root: The tree the setup runs in.
        state: The verification's shared execution state.

    Returns:
        The setup errors (the first failing command stops the setup) and the setup records.

    """
    run_id: str = _str(run, "id")
    records: list[JsonValue] = []
    for position, setup in enumerate(_objs(run, "setup")):
        command: str = _str(setup, "command")
        key: tuple[str, str] = (str(root), command)
        if key not in state.setups:
            record: str = f"{label}-setup-{position}.json"
            state.setups[key] = state.shell(command, root, record, {"runId": run_id, "setup": setup})
            records.append({"command": command, "exitCode": state.setups[key], "output": str(state.folder / record)})
        if state.setups[key] != 0:
            return [f"{run_id}: setup `{command}` exited {state.setups[key]}; the run did not execute"], records
    return [], records


def _fresh_report(run: JsonObject, root: Path) -> Path | None:
    """Resolve a junit run's report path and remove any stale report there.

    Returns:
        The report path, or None for an exitStatus run.

    """
    if _str(run, "format") != "junit":
        return None
    report: Path = _report_path(run, root)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    return report


def _archive(report: Path, archived: Path, run_id: str) -> JunitOutcome | None:
    """Move a fresh report into the evidence folder.

    Returns:
        None when the command wrote no report; otherwise what the report shows, parsed before it is moved.

    """
    if not report.is_file():
        return None
    outcome: JunitOutcome = junit_results(report, run_id)
    archived.write_bytes(report.read_bytes())
    report.unlink()
    return outcome


def _execute_run(run: JsonObject, index: int, verification: Verification) -> tuple[list[str], JsonObject]:
    """Run one mapped run after its setup and archive its output and, for a junit run, its report.

    Returns:
        The run's errors and its evidence record.

    """
    state: Execution = verification.state
    run_id: str = _str(run, "id")
    root: Path = Path(_str(run, "repoPath")).resolve()
    report: Path | None = _fresh_report(run, root)
    errors, setups = _setup_errors(run, f"run-{index}", root, state)
    record: JsonObject = {"runId": run_id, "format": _str(run, "format"), "setup": setups}
    if errors:
        return errors, record
    revision: str = _tree_digest(root, state)
    output: str = f"run-{index}.json"
    exit_code: int = state.shell(_str(run, "command"), root, output, {"run": run})
    record |= {"output": str(state.folder / output), "testedTreeDigest": revision, "exitCode": exit_code}
    if report is None:
        return ([f"{run_id}: check exited {exit_code}"] if exit_code else []), record
    archived: Path = state.folder / f"run-{index}.xml"
    outcome: JunitOutcome | None = _archive(report, archived, run_id)
    if outcome is None:
        return [f"{run_id}: missing fresh JUnit report"], record
    record |= {
        "report": str(archived),
        "reportSha256": hashlib.sha256(archived.read_bytes()).hexdigest(),
        "passedTestIds": [*sorted(outcome.passed)],
        "failedTestIds": [*sorted(outcome.failed)],
    }
    judged_errors, judged = _judge(run_id, exit_code, outcome, verification)
    return [*outcome.errors, *judged_errors], record | judged


def _tests_of(mappings: list[JsonObject], run_id: str) -> dict[str, set[str]]:
    """Map each test ID a run's mappings name to the requirements mapped to it.

    Returns:
        The requirement IDs of each mapped test of the run.

    """
    linked: dict[str, set[str]] = {}
    pairs: list[tuple[str, str]] = [
        (test, _str(m, "requirementId")) for m in mappings if _str(m, "runId") == run_id for test in _strs(m, "testIds")
    ]
    for test, requirement in pairs:
        linked.setdefault(test, set()).add(requirement)
    return linked


def _binding(linked: dict[str, set[str]], verification: Verification) -> tuple[frozenset[str], frozenset[str]]:
    """Split a run's mapped tests into the Task's own and the proven ones, the two kinds that bind the Task.

    Returns:
        The tests mapped to a requirement of effective origin task, and the other tests a completed build proved
        for a requirement they are mapped to.

    """
    owned: frozenset[str] = frozenset(
        test for test, requirements in linked.items() if any(verification.origins.get(r) == TASK for r in requirements)
    )
    held: frozenset[str] = frozenset(
        test for test, requirements in linked.items() if any((r, test) in verification.proven for r in requirements)
    )
    return owned, held - owned


def _judge(
    run_id: str,
    exit_code: int,
    outcome: JunitOutcome,
    verification: Verification,
) -> tuple[list[str], JsonObject]:
    """Hold the Task to its own requirements in full and to existing ones only as far as the pipeline proved them.

    A mapped test binds the Task when a requirement it is mapped to is the Task's own, or when a completed build
    proved it for such a requirement (:func:`proven`); it must pass. Every other mapped test belongs to an existing
    requirement the pipeline never proved: one that does not pass is recorded as unmet for the requirement, and a
    failing test no requirement maps is recorded as unmapped, neither as this Task's failure.

    Returns:
        The errors, and the record fields of the unmet requirements and the unmapped failing tests.

    """
    linked: dict[str, set[str]] = _tests_of(verification.mappings, run_id)
    owned, held = _binding(linked, verification)
    errors: list[str] = [
        f"{run_id}: test of the Task's own requirement failed: {test}" for test in sorted(outcome.failed & owned)
    ]
    errors.extend(
        f"{run_id}: test of an existing requirement a completed build proved failed: {test}"
        for test in sorted(outcome.failed & held)
    )
    errors.extend(
        f"{run_id}: mapped test not executed successfully: {test}"
        for test in sorted((owned | held) - outcome.passed - outcome.failed)
    )
    if exit_code and not outcome.failed:
        errors.append(f"{run_id}: exited {exit_code} with no failing test in its report")
    unmet: list[JsonValue] = [
        {"requirementId": requirement, "testId": test, "outcome": FAILED if test in outcome.failed else NOT_RUN}
        for test in sorted(linked.keys() - owned - held - outcome.passed)
        for requirement in sorted(linked[test])
    ]
    unmapped: list[JsonValue] = [*sorted(outcome.failed - linked.keys())]
    return errors, {"unmet": unmet, "unmappedFailing": unmapped}


def _optional_arg(value: object, name: str) -> str | None:
    """Narrow an optional string command-line value.

    Returns:
        The value, or None when it was not given.

    Raises:
        TypeError: The value is neither a string nor None.

    """
    if value is None or isinstance(value, str):
        return value
    message: str = f"--{name}: expected a string"
    raise TypeError(message)


def _strings_arg(value: object, name: str) -> tuple[str, ...]:
    """Narrow a repeatable string command-line value.

    Returns:
        The strings, in the order given.

    Raises:
        TypeError: The value is not a list of strings.

    """
    if not isinstance(value, list):
        message: str = f"--{name}: expected strings"
        raise TypeError(message)
    strings: tuple[str, ...] = tuple(item for item in value if isinstance(item, str))
    if len(strings) != len(value):
        message = f"--{name}: expected strings"
        raise TypeError(message)
    return strings


def _parse_args() -> CliArgs:
    """Parse and narrow the command line.

    Returns:
        The validated command line.

    Raises:
        TypeError: argparse produced a value outside the declared types.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(__doc__)
    parser.add_argument("mode", choices=list(MODES))
    parser.add_argument("--plan", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--review")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--approved-plan")
    parser.add_argument("--bindings", help="Source seal written by scope validation, preserved across journal steps")
    parser.add_argument("--output", required=True)
    parser.add_argument("--tree")
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument(
        "--citations",
        help="verify: a JSON file of the Task's contract citations, "
        "{requirementIds, specPaths, acceptanceCriteria, definitionOfDone}",
    )
    args: argparse.Namespace = parser.parse_args()
    mode: object = args.mode
    plan: str | None = _optional_arg(args.plan, "plan")
    ledger: str | None = _optional_arg(args.ledger, "ledger")
    output: str | None = _optional_arg(args.output, "output")
    if plan is None or ledger is None or output is None:
        message: str = "--plan, --ledger and --output are required"
        raise TypeError(message)
    resolved: Mode | None = MODES.get(mode) if isinstance(mode, str) else None
    if resolved is not None:
        return CliArgs(
            mode=resolved,
            plan=plan,
            ledger=ledger,
            review=_optional_arg(args.review, "review"),
            source=[*_strings_arg(args.source, "source")],
            approved_plan=_optional_arg(args.approved_plan, "approved-plan"),
            output=output,
            tree=_optional_arg(args.tree, "tree"),
            repos=[*_strings_arg(args.repo, "repo")],
            bindings=_optional_arg(args.bindings, "bindings"),
            citations=_optional_arg(args.citations, "citations"),
        )
    message = f"unsupported mode: {mode}"
    raise TypeError(message)


def _emit(value: JsonValue) -> None:
    """Write one JSON line to standard output."""
    sys.stdout.write(json.dumps(value) + "\n")


def _check(plan: JsonObject, previous: JsonObject | None, args: CliArgs) -> None:
    """Check a newly written plan for everything validate later requires that holds without a review.

    The scope is checked as validate checks it; a final mapping (``--approved-plan`` given) also
    as verify checks it before it runs the mapped tests.
    """
    errors: list[str] = source_errors(_strs(plan, "sourceFiles"))
    errors.extend(validate(plan, previous, complete=args.approved_plan is not None))
    if args.approved_plan and scope(plan) != scope(read(args.approved_plan)):
        errors.append("Final mapping changed the approved impact scope")
    error_values: list[JsonValue] = [*errors]
    write(args.output, {"ok": not errors, "errors": error_values})
    _emit({"ok": not errors, "errors": error_values, "path": args.output})


def _setup(plan: JsonObject, args: CliArgs) -> None:
    """Run the setup the plan declares for one tree (:func:`prepare_tree`) and report it.

    Raises:
        ValueError: No ``--tree`` was given.

    """
    if args.tree is None:
        message: str = "setup requires --tree"
        raise ValueError(message)
    errors, records = prepare_tree(plan, Path(args.tree), args.repos, Path(args.output).parent)
    error_values: list[JsonValue] = [*errors]
    write(args.output, {"ok": not errors, "errors": error_values, "setup": records})
    _emit({"ok": not errors, "errors": error_values, "path": args.output, "setup": records})


def _effective_origins(plan: JsonObject, args: CliArgs) -> tuple[dict[str, str], list[JsonValue]]:
    """Derive the origins verify holds the Task to, from the reviewed scope and the Task's contract.

    The approved plan is the reviewed scope, so its origins, raised by the contract's citations, are the ones
    that count; a mapping cannot weaken them.

    Returns:
        The effective origin of each requirement, and each origin the gate derived or raised.

    Raises:
        ValueError: No ``--citations`` was given.

    """
    if args.citations is None:
        message: str = "verify requires --citations, the Task's contract citations"
        raise ValueError(message)
    reviewed: JsonObject = read(args.approved_plan) if args.approved_plan else plan
    effective: dict[str, str] = origins(reviewed, read_citations(args.citations))
    return effective, origin_corrections(reviewed, effective)


def blocking_findings(review: JsonObject) -> list[JsonValue]:
    """Return the findings of a review that withhold approval.

    A finding the review marks non-blocking is a note; every other finding blocks, a finding
    written as plain text by a review that carried no severity included.

    Args:
        review: The review, as regression-review.schema.json defines it.

    Returns:
        The blocking findings.

    """
    findings: JsonValue = review.get("findings")
    if not isinstance(findings, list):
        return []
    return [
        finding for finding in findings if not (isinstance(finding, dict) and finding.get("severity") == "non-blocking")
    ]


def required_kinds(plan: JsonObject) -> list[JsonValue]:
    """List the test layers a required layer of an impacted requirement names.

    Returns:
        The layer kinds, sorted.

    """
    return [
        *sorted(
            {
                _str(a, "kind")
                for r in _objs(plan, "requirements")
                if _flag(r, "impacted")
                for a in _objs(r, "applicability")
                if _flag(a, "required")
            },
        ),
    ]


def _prepare(previous: JsonObject | None, args: CliArgs) -> None:
    """Write the previous ledger for the assessor, without origins, and report the sources' revision.

    A requirement an earlier Task built is existing for this one unless this Task's contract cites it, so the
    previous origins are not carried forward.
    """
    approved: JsonObject | None = read(args.approved_plan) if args.approved_plan else None
    hashes: dict[str, str] = source_hashes(
        sorted(
            set(args.source + _optional_strs(approved, "sourceFiles") + _optional_strs(previous, "sourceFiles")),
        ),
    )
    write(args.output, without_origin(previous) if previous else {"requirements": [], "mappings": [], "runs": []})
    _emit(
        {
            "ok": True,
            "path": args.output,
            "sourceRevision": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        },
    )


def _review_approved(args: CliArgs) -> bool:
    """Report whether the independent review given with ``--review`` approves, with evidence and no blocking finding.

    Returns:
        True when the review approves.

    """
    review: JsonObject = read(args.review) if args.review else {}
    return review.get("approved") is True and not blocking_findings(review) and bool(review.get("evidence"))


def _found(evidence: list[JsonValue]) -> JsonObject:
    """Collect what verification recorded outside the Task's obligations, for the Epics that own it.

    Returns:
        ``unmet``: each ``{requirementId, testId, outcome}`` of an existing requirement no completed build proved
        whose test did not pass; ``unmappedFailing``: each failing test no requirement maps.

    """
    return {"unmet": collected(evidence, "unmet"), "unmappedFailing": collected(evidence, "unmappedFailing")}


def _verify(
    plan: JsonObject,
    previous: JsonObject | None,
    args: CliArgs,
    effective: dict[str, str],
) -> tuple[list[str], list[JsonValue]]:
    """Run the mapped runs, and on success write the ledger with the pairs now proven.

    Returns:
        The execution errors and the per-run evidence records.

    """
    held: frozenset[tuple[str, str]] = proven(previous, plan)
    errors, evidence = execute(plan, Path(args.output).parent, effective, held)
    if not errors:
        ledger: JsonObject = {
            **without_origin(plan),
            "execution": evidence,
            "proven": proven_record(held, plan, evidence),
            **_found(evidence),
        }
        write(args.ledger, ledger)
    return errors, evidence


def main() -> None:
    """Prepare, validate or verify a cumulative regression plan and report the result as JSON."""
    args: CliArgs = _parse_args()
    previous: JsonObject | None = read(args.ledger) if Path(args.ledger).is_file() else None
    if args.mode == "prepare":
        _prepare(previous, args)
        return
    plan: JsonObject = read(args.plan)
    if args.mode == "setup":
        _setup(plan, args)
        return
    if args.mode == "check":
        _check(plan, previous, args)
        return
    effective, corrections = _effective_origins(plan, args) if args.mode == "verify" else ({}, [])
    owned: frozenset[str] = frozenset(requirement for requirement, origin in effective.items() if origin == TASK)
    errors: list[str] = validate(plan, previous, complete=args.mode == "verify", owned=owned)
    review_approved: bool = _review_approved(args)
    if not review_approved:
        errors.append("Independent source/coverage/supersession review is not approved")
    if args.approved_plan and scope(plan) != scope(read(args.approved_plan)):
        errors.append("Final mapping changed the approved impact scope")
    bindings: Path = Path(args.bindings) if args.bindings else Path(args.output).parent / "source-bindings.json"
    source_bytes: dict[str, str] = source_hashes(_strs(plan, "sourceFiles"))
    bound: JsonObject = {**source_bytes}
    sources_changed: bool = args.mode == "verify" and (not bindings.is_file() or read(bindings) != bound)
    if sources_changed:
        errors.append("Requirement source bytes changed since scope approval; reassess scope before building")
    if args.mode == "validate" and not errors:
        write(bindings, bound)
    evidence: list[JsonValue] = []
    if not errors and args.mode == "verify":
        errors, evidence = _verify(plan, previous, args, effective)
    error_values: list[JsonValue] = [*errors]
    found: JsonObject = _found(evidence)
    write(
        args.output,
        {
            "ok": not errors,
            "errors": error_values,
            "evidence": evidence,
            "sourcesChanged": sources_changed,
            **found,
            "originCorrections": corrections,
        },
    )
    _emit(
        {
            "ok": not errors,
            "errors": error_values,
            "path": args.output,
            "ledger": args.ledger,
            "requiredKinds": required_kinds(plan),
            "reviewApproved": review_approved,
            "sourcesChanged": sources_changed,
            **found,
            "originCorrections": corrections,
        },
    )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        TypeError,
        OSError,
        KeyError,
        ET.ParseError,
        GitError,
    ) as error:
        _emit({"ok": False, "errors": [str(error)]})
        raise SystemExit(1) from error
