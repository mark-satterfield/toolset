"""Evidence binding consumed by architecture claims, coverage and saved-target reuse."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Bounded Git reads with fixed executable and no shell.
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict

# Evidence references and review verdicts are generated into the artifact-handoff skill, their one place.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff"))

# isort: split
import contracts
import survey_contract
from architecture_artifacts import RESOLUTION_ACCEPTED, VERDICT_VERIFIED, EvidenceRef
from contracts import JsonInput, JsonObject, json_object, json_value
from survey_contract import BASELINE_REF_LISTS, CODE_REF_LISTS, Survey, SurveyContractError, parse_survey
from typeguard import CollectionCheckStrategy, TypeCheckError, check_type, typechecked

CONTRACT_VERSION = 2


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def digest(value: JsonInput) -> str:
    """Hash a deterministic JSON encoding.

    Returns:
        The SHA-256 digest.

    Raises:
        TypeError: The input is outside the JSON scalar/tree domain.

    """
    if value is not None and not isinstance(value, (str, bool, int, float, Sequence, Mapping)):
        message: str = "Digest input must contain only JSON scalar or collection values"
        raise TypeError(message)
    return hashlib.sha256(json.dumps(json_value(value), sort_keys=True).encode()).hexdigest()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def view_content(path: str, heading: str = "") -> str:
    """Bind a unique section and catalog, falling back to the entire view.

    Returns:
        The content digest or an explicit unreadable marker.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    start: int
    level: int
    if not (isinstance(path, str)) or not (isinstance(heading, str)):
        argument_error: str = "view_content: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    p: Path = Path(path)
    if not p.is_absolute():
        return "invalid: expected absolute path"
    try:
        text: str = p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return f"unreadable: {exc}"
    front: str = ""
    if text.startswith("---\n"):
        end: int = text.find("\n---", 4)
        if end >= 0:
            front = re.sub(
                r"(?m)^lifecycle_state:.*$",
                "lifecycle_state: <review-state>",
                text[:end],
            )
            text = front + text[end:]
    if heading:
        lines: list[str] = text.splitlines(keepends=True)
        hits: list[tuple[int, int]] = [
            (i, len(m.group(1)))
            for i, line in enumerate(lines)
            if (m := re.match(r"^(#{1,6})\s+(.+?)\s*$", line)) and m.group(2) == heading
        ]
        if len(hits) == 1:
            start, level = hits[0]
            end = next(
                (
                    i
                    for i in range(start + 1, len(lines))
                    if (m := re.match(r"^(#{1,6})\s", lines[i])) and len(m.group(1)) <= level
                ),
                len(lines),
            )
            text = front + "\n" + "".join(lines[start:end])
    return digest(text)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def load_repository_paths(work: Path) -> dict[str, str]:
    """Read the exact repository menu supplied to this architecture's agents.

    Returns:
        Repository identifiers mapped to absolute checkouts; uncloned entries are omitted.

    Raises:
        ValueError: The menu contains invalid or ambiguous names or checkout paths.
        TypeError: The menu is not an array of JSON objects.

    """
    menu = work / "repositories.json"
    if not menu.exists():
        return {}
    raw: object = json.loads(menu.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        message = "repository menu must be an array"
        raise TypeError(message)
    result: dict[str, str] = {}
    seen: dict[str, str | None] = {}
    for item in raw:
        row = json_object(item)
        if "path" not in row:
            message = "repository menu requires an explicit nullable path"
            raise ValueError(message)
        name, path = row.get("name"), row.get("path")
        if not isinstance(name, str) or not name.strip():
            message = "repository menu requires a nonempty name"
            raise ValueError(message)
        if path is not None and (not isinstance(path, str) or not Path(path).is_absolute()):
            message = f"repository menu path must be absolute or null: {name}"
            raise ValueError(message)
        if name in seen and seen[name] != path:
            message = f"ambiguous repository menu name: {name}"
            raise ValueError(message)
        seen[name] = path
        if path is not None:
            result[name] = path
    return result


def _git_bytes(repo: str, *arguments: str) -> bytes:
    executable: str | None = shutil.which("git")
    if executable is None:
        message: str = "Git executable is unavailable"
        raise FileNotFoundError(message)
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved Git executable, separate arguments, no shell.
        [executable, "-C", repo, *arguments],
        capture_output=True,
        timeout=10,
        check=True,
    ).stdout


def _evidence_ref(ref: JsonObject) -> EvidenceRef | None:
    """Narrow one JSON object to the generated EvidenceRef.

    Returns:
        The reference typed by architecture-common.schema.json, or None when it does not conform.

    """
    try:
        return check_type(ref, EvidenceRef)
    except TypeCheckError:
        return None


def _evidence_refs(value: contracts.JsonValue) -> list[EvidenceRef]:
    """Narrow a saved evidenceRefs list to the generated EvidenceRef.

    Returns:
        The references typed by architecture-common.schema.json.

    Raises:
        TypeError: The value is not a list of conforming evidence references.

    """
    try:
        return check_type(value, list[EvidenceRef], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    except TypeCheckError as exc:
        message: str = f"evidenceRefs do not conform to architecture-common EvidenceRef: {exc}"
        raise TypeError(message) from exc


def _repository_evidence(ref: EvidenceRef, repo: str, path: str) -> tuple[JsonObject, list[str]]:
    stored: JsonObject = json_object(ref)
    revision: str = ref["revision"]
    try:
        content: bytes = _git_bytes(repo, "show", f"main:{path}")
        if not re.fullmatch(r"[0-9a-fA-F]{7,40}", revision):
            return {"ref": stored, "content": hashlib.sha256(content).hexdigest()}, []
        commit: str = _git_bytes(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()
        cited: bytes = _git_bytes(repo, "show", f"{commit}:{path}")
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ref": stored, "error": str(exc)}, [f"source unreadable: {repo}:{path}"]
    state: JsonObject = {"ref": stored, "commit": commit, "content": hashlib.sha256(content).hexdigest()}
    if cited != content:
        state["moved"] = True
        return state, [f"cited source content moved on main since {commit[:12]}: {repo}:{path}"]
    return state, []


def _reference_evidence(ref: EvidenceRef, repository_paths: Mapping[str, str]) -> tuple[JsonObject, list[str]]:
    stored: JsonObject = json_object(ref)
    path: str = ref["path"]
    repo: str = ref["repo"]
    if path and (not repo or Path(path).is_absolute()):
        content: str = view_content(path, ref["heading"])
        errors: list[str] = [content] if content.startswith(("invalid:", "unreadable:")) else []
        return {"ref": stored, "content": content}, errors
    if repo:
        resolved: str | None = repo if Path(repo).is_absolute() else repository_paths.get(repo)
        if resolved is None:
            message: str = f"repository evidence has no resolved checkout: {repo}"
            return {"ref": stored, "error": message}, [message]
        state, warnings = _repository_evidence(ref, resolved, path)
        state["repository"] = resolved
        return state, warnings
    if ref["url"] and ref["revision"]:
        return {"ref": stored}, []
    return {"ref": stored, "error": "missing path or external version"}, [
        "evidence reference lacks path or external version",
    ]


def _bind_references(
    refs: Sequence[EvidenceRef],
    repository_paths: Mapping[str, str],
) -> tuple[list[JsonObject], list[str]]:
    """Bind typed evidence references to their current source content.

    Returns:
        Bound reference states and warnings.

    """
    states: list[JsonObject] = []
    errors: list[str] = []
    ref: EvidenceRef
    for ref in refs:
        state, warnings = _reference_evidence(ref, repository_paths)
        states.append(state)
        errors.extend(warnings)
    return states, errors


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def evidence_state(
    refs: JsonInput,
    *,
    repository_paths: dict[str, str] | None = None,
) -> tuple[list[JsonObject], list[str]]:
    """Bind cited source bytes; unrelated main commits do not invalidate evidence.

    The second list holds warnings about the references, never reasons to refuse them: a
    repository reference with no commit is bound to the file's content on `main`, a reference
    with an absolute path is bound as a file whatever `repo` says, and a cited file whose
    content moved on `main` is bound to the new content.

    Returns:
        Bound reference states and warnings.

    Raises:
        ValueError: A repository mapping names a relative checkout path.

    """
    ref: JsonInput
    states: list[JsonObject] = []
    errors: list[str] = []
    if not isinstance(refs, Sequence) or isinstance(refs, str):
        return [], ["evidenceRefs must be a list"]
    if repository_paths is not None and any(not Path(path).is_absolute() for path in repository_paths.values()):
        message = "repository evidence mappings require absolute checkout paths"
        raise ValueError(message)
    for ref in refs:
        if not isinstance(ref, Mapping):
            errors.append("invalid evidence reference")
            continue
        raw: JsonObject = {key: json_value(value) for key, value in ref.items()}
        typed: EvidenceRef | None = _evidence_ref(raw)
        if typed is None:
            states.append({"ref": raw, "error": "invalid evidence reference"})
            errors.append("invalid evidence reference")
            continue
        bound, warnings = _bind_references([typed], repository_paths or {})
        states.extend(bound)
        errors.extend(warnings)
    return states, errors


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def view_bindings(paths: list[str], refs: list[JsonObject]) -> dict[str, str]:
    """Scope only explicitly referenced views; unknown legacy scope remains whole-file.

    A reference that does not conform to architecture-common EvidenceRef is reported, as
    `evidence_state` reports it: every view is bound to the `invalid:` marker instead of content,
    so no binding is computed from a partial reference list.

    Returns:
        Content bindings indexed by view path.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(paths, list)) or not (isinstance(refs, list)):
        argument_error: str = "view_bindings: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    typed: list[EvidenceRef] = [ref for raw in refs if (ref := _evidence_ref(raw)) is not None]
    if len(typed) != len(refs):
        return dict.fromkeys(paths, "invalid: invalid evidence reference")
    return _view_bindings(paths, typed)


def _view_bindings(paths: Sequence[str], refs: Sequence[EvidenceRef]) -> dict[str, str]:
    """Bind each view path to the sections its file-local evidence references cite.

    Returns:
        Content bindings indexed by view path.

    """
    path: str
    result: dict[str, str] = {}
    for path in paths:
        sections: list[EvidenceRef] = [r for r in refs if not r["repo"] and r["path"] == path and r["heading"]]
        values: list[str] = [view_content(path, r["heading"]) for r in sections] if sections else [view_content(path)]
        invalid: str | None = next(
            (v for v in values if v.startswith(("invalid:", "unreadable:"))),
            None,
        )
        result[path] = invalid or (digest(values) if sections else values[0])
    return result


def _ledger_evidence_current(ledger: JsonObject, repository_paths: dict[str, str]) -> bool:
    plans: list[contracts.JsonObject] = check_type(
        ledger.get("roundPlans", []),
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    findings: list[contracts.JsonObject] = check_type(
        ledger.get("findings", []),
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    claims: list[contracts.JsonObject] = check_type(
        ledger.get("claims", []),
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    coverage: list[contracts.JsonObject] = check_type(
        ledger.get("coverage", []),
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    if ledger.get("contractVersion") != CONTRACT_VERSION or any(not plan.get("complete") for plan in plans):
        return False
    if any(
        finding.get("verdict") != VERDICT_VERIFIED
        and json_object(finding.get("resolution") or {}).get("verdict") != RESOLUTION_ACCEPTED
        for finding in findings
    ):
        return False
    if any(claim.get("active", True) and not claim.get("verdicts") for claim in claims):
        return False
    return all(_row_evidence_current(row, repository_paths) for row in claims + coverage)


def _row_evidence_current(row: JsonObject, repository_paths: dict[str, str]) -> bool:
    states: list[JsonObject]
    errors: list[str]
    if row.get("active") is False:
        return True
    try:
        refs: list[EvidenceRef] = _evidence_refs(row.get("evidenceRefs", []))
    except TypeError:
        return False
    states, errors = _bind_references(refs, repository_paths)
    if errors or ("evidenceState" in row and states != row["evidenceState"]):
        return False
    views: list[str] = check_type(
        row.get("views", []),
        list[str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    return "viewState" not in row or _view_bindings(views, refs) == row["viewState"]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def saved_evidence_current(work: str) -> bool:
    """Check evidence before reusing a saved composite target.

    Returns:
        Whether all saved evidence remains current.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(work, str)):
        argument_error: str = "saved_evidence_current: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    try:
        raw_survey: object = json.loads((Path(work) / survey_contract.SURVEY_FILE).read_text(encoding="utf-8"))
        raw_ledger: object = json.loads((Path(work) / "ledger.json").read_text(encoding="utf-8"))
        survey: Survey = parse_survey(raw_survey)
    except OSError, ValueError:
        return False
    if not isinstance(raw_ledger, dict):
        return False
    ledger: JsonObject = json_object(raw_ledger)
    if not survey["subject"] or not survey["coverage"]:
        return False
    return _ledger_evidence_current(ledger, load_repository_paths(Path(work)))


class SourceBinding(TypedDict):
    """Cited source content used by approval and completion receipt consumers."""

    states: list[JsonObject]
    errors: list[str]


def _reference_rows(value: contracts.JsonValue) -> list[JsonObject]:
    return check_type(value, list[JsonObject], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _survey_references(survey: Survey) -> list[EvidenceRef]:
    references: list[EvidenceRef] = [ref for row in survey["coverage"] for ref in row["evidenceRefs"]]
    for entry in survey["baseline"]:
        for code_key in CODE_REF_LISTS:
            references.extend(entry["code"][code_key])
        for entry_key in BASELINE_REF_LISTS:
            references.extend(entry[entry_key])
    return references


def _ledger_references(ledger: JsonObject) -> list[EvidenceRef]:
    references: list[EvidenceRef] = []
    rows: list[JsonObject] = _reference_rows(ledger.get("coverage", [])) + _reference_rows(ledger.get("claims", []))
    for row in rows:
        if row.get("active") is not False:
            references.extend(_evidence_refs(row.get("evidenceRefs", [])))
    return references


def _cited_location(ref: EvidenceRef, repository_paths: Mapping[str, str]) -> Path | None:
    path: str = ref["path"]
    repo: str = ref["repo"]
    if not path:
        return None
    if Path(path).is_absolute():
        return Path(path).resolve()
    if not repo:
        return None
    checkout: str | None = repo if Path(repo).is_absolute() else repository_paths.get(repo)
    return (Path(checkout) / path).resolve() if checkout is not None else None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def source_binding(work: Path, *, governed: Path | None = None) -> SourceBinding:
    """Resolve the saved survey and active claim citations against current source bytes.

    Args:
        work: The architecture work directory holding survey.json, ledger.json and repositories.json.
        governed: A canonical tree whose cited files another receipt binds; citations inside it are
            left out, so writes that receipt permits do not revoke this binding.

    A survey.json that is not JSON or breaks survey.schema.json, and a ledger.json that is not a
    JSON object or whose active evidenceRefs do not conform to architecture-common EvidenceRef,
    are reported in `errors` (as `evidence_state` reports an invalid reference) instead of raised,
    so every consumer sees an unresolved binding rather than a crash.

    Returns:
        Actual evidence states and explicit unresolved-source diagnostics.

    Raises:
        TypeError: An argument is not a path.

    """
    if not isinstance(work, Path) or (governed is not None and not isinstance(governed, Path)):
        message = "source_binding requires a work path and an optional governed path"
        raise TypeError(message)
    repository_paths: dict[str, str] = load_repository_paths(work)
    root: Path | None = governed.resolve() if governed is not None else None
    cited: list[EvidenceRef] = []
    unreadable: list[str] = []
    survey_path: Path = work / survey_contract.SURVEY_FILE
    if survey_path.is_file():
        try:
            cited.extend(_survey_references(parse_survey(json.loads(survey_path.read_text(encoding="utf-8")))))
        except (OSError, SurveyContractError, ValueError) as exc:
            unreadable.append(f"invalid survey: {survey_path}: {exc}")
    ledger_path: Path = work / "ledger.json"
    if ledger_path.is_file():
        try:
            cited.extend(_ledger_references(json_object(json.loads(ledger_path.read_text(encoding="utf-8")))))
        except (OSError, TypeError, ValueError) as exc:
            unreadable.append(f"invalid evidence reference: {ledger_path}: {exc}")
    references: list[EvidenceRef] = []
    for ref in cited:
        location: Path | None = _cited_location(ref, repository_paths)
        if root is None or location is None or not location.is_relative_to(root):
            references.append(ref)
    states, errors = _bind_references(references, repository_paths)
    return {"states": states, "errors": unreadable + errors}
