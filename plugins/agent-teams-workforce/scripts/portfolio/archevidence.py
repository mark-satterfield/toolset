"""Evidence binding consumed by architecture claims, coverage and saved-target reuse."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Bounded Git reads with fixed executable and no shell.
from collections.abc import Mapping, Sequence
from pathlib import Path

import contracts
from contracts import JsonInput, JsonObject, json_object, json_value
from typeguard import CollectionCheckStrategy, check_type, typechecked

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


def _repository_evidence(ref: JsonObject, repo: str, path: str) -> tuple[JsonObject, list[str]]:
    try:
        revision: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = ref.get(
            "revision",
        )
        content: bytes = _git_bytes(repo, "show", f"main:{path}")
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", revision):
            return {"ref": ref, "content": hashlib.sha256(content).hexdigest()}, []
        commit: str = _git_bytes(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()
        cited: bytes = _git_bytes(repo, "show", f"{commit}:{path}")
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ref": ref, "error": str(exc)}, [f"source unreadable: {repo}:{path}"]
    state: JsonObject = {"ref": ref, "commit": commit, "content": hashlib.sha256(content).hexdigest()}
    if cited != content:
        state["moved"] = True
        return state, [f"cited source content moved on main since {commit[:12]}: {repo}:{path}"]
    return state, []


def _reference_evidence(ref: JsonObject) -> tuple[JsonObject, list[str]]:
    path: str = check_type(ref.get("path", ""), str)
    repo: str = check_type(ref.get("repo", ""), str)
    if path and (not repo or Path(path).is_absolute()):
        content: str = view_content(path, check_type(ref.get("heading", ""), str))
        errors: list[str] = [content] if content.startswith(("invalid:", "unreadable:")) else []
        return {"ref": ref, "content": content}, errors
    if repo:
        return _repository_evidence(ref, repo, path)
    if ref.get("url") and ref.get("revision"):
        return {"ref": ref}, []
    return {"ref": ref, "error": "missing path or external version"}, [
        "evidence reference lacks path or external version",
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def evidence_state(refs: JsonInput) -> tuple[list[JsonObject], list[str]]:
    """Bind cited source bytes; unrelated main commits do not invalidate evidence.

    The second list holds warnings about the references, never reasons to refuse them: a
    repository reference with no commit is bound to the file's content on `main`, a reference
    with an absolute path is bound as a file whatever `repo` says, and a cited file whose
    content moved on `main` is bound to the new content.

    Returns:
        Bound reference states and warnings.

    """
    ref: JsonInput
    state: JsonObject
    warnings: list[str]
    states: list[JsonObject] = []
    errors: list[str] = []
    if not isinstance(refs, Sequence) or isinstance(refs, str):
        return [], ["evidenceRefs must be a list"]
    for ref in refs:
        if not isinstance(ref, Mapping):
            errors.append("invalid evidence reference")
            continue
        state, warnings = _reference_evidence({key: json_value(value) for key, value in ref.items()})
        states.append(state)
        errors.extend(warnings)
    return states, errors


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def view_bindings(paths: list[str], refs: list[JsonObject]) -> dict[str, str]:
    """Scope only explicitly referenced views; unknown legacy scope remains whole-file.

    Returns:
        Content bindings indexed by view path.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    path: str
    if not (isinstance(paths, list)) or not (isinstance(refs, list)):
        argument_error: str = "view_bindings: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    result: dict[str, str] = {}
    for path in paths:
        sections: list[
            dict[str, bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None]
        ] = [
            r for r in refs if isinstance(r, dict) and not r.get("repo") and r.get("path") == path and r.get("heading")
        ]
        values: list[str] = (
            [view_content(path, check_type(r["heading"], str)) for r in sections] if sections else [view_content(path)]
        )
        invalid: str | None = next(
            (v for v in values if v.startswith(("invalid:", "unreadable:"))),
            None,
        )
        result[path] = invalid or (digest(values) if sections else values[0])
    return result


def _ledger_evidence_current(ledger: JsonObject) -> bool:
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
        finding.get("verdict") != "verified"
        and json_object(finding.get("resolution") or {}).get("verdict") != "accepted"
        for finding in findings
    ):
        return False
    if any(claim.get("active", True) and not claim.get("verdicts") for claim in claims):
        return False
    return all(_row_evidence_current(row) for row in claims + coverage)


def _row_evidence_current(row: JsonObject) -> bool:
    states: list[JsonObject]
    errors: list[str]
    if row.get("active") is False:
        return True
    refs: list[contracts.JsonObject] = check_type(
        row.get("evidenceRefs", []),
        list[JsonObject],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    states, errors = evidence_state(refs)
    if errors or ("evidenceState" in row and states != row["evidenceState"]):
        return False
    views: list[str] = check_type(
        row.get("views", []),
        list[str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    return "viewState" not in row or view_bindings(views, refs) == row["viewState"]


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
        raw_survey: object = json.loads((Path(work) / "survey.json").read_text(encoding="utf-8"))
        raw_ledger: object = json.loads((Path(work) / "ledger.json").read_text(encoding="utf-8"))
    except OSError, ValueError:
        return False
    if not isinstance(raw_survey, dict) or not isinstance(raw_ledger, dict):
        return False
    survey: JsonObject = json_object(raw_survey)
    ledger: JsonObject = json_object(raw_ledger)
    if not survey.get("subject") or not isinstance(survey.get("coverage"), list) or not survey["coverage"]:
        return False
    return _ledger_evidence_current(ledger)
