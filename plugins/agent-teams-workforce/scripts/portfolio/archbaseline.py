"""Read baseline observations and derive bounded architecture work from them.

The canonical schema belongs to artifact-handoff. These are assessment actions,
not new document lifecycle states. Fields one another determines are derived here
rather than refused; shape problems, evidence bindings and contradictions are
returned as warnings, and reviewers and the decider judge whether the evidence
proves the assessment. Only a survey with no assessment at all is invalid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Bounded read-only Git argv without shell.
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import contracts
from archevidence import digest, evidence_state, view_content
from archmatrix import catalog_elements, row_of, satisfied
from contracts import (
    BaselineDocument,
    BaselineEntry,
    BaselineFacts,
    FreshnessResult,
    JsonObject,
    JsonValue,
    json_object,
)
from jsonschema import Draft202012Validator
from typeguard import CollectionCheckStrategy, check_type, typechecked

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "skills/artifact-handoff/schemas/architecture-baseline.schema.json"

#: The implementation action each target disposition implies.
DISPOSITION_ACTION = {
    "retain": "none",
    "change": "modify",
    "replace": "replace",
    "add": "new",
    "retire": "retire",
    "undetermined": "unknown",
}
#: The implementation action code in each state needs when the disposition implies none.
CODE_STATE_ACTION = {"partial": "modify", "absent": "new"}
REF_LISTS = ("awsGuidance", "suitabilityEvidenceRefs")
CODE_REF_LISTS = ("behaviorEvidenceRefs", "infrastructureEvidenceRefs")
FRONTMATTER_PARTS = 3
TEXT_FIELDS = ("rationale", "current", "target")


def _document_warnings(document: BaselineDocument) -> list[str]:
    """Name what a cited document's state says against the observation recorded for it.

    Args:
        document: One `documents` entry.

    Returns:
        The warnings; the observation is replaced by the state the file now carries.

    """
    path: Path = Path(document["path"])
    if not path.is_absolute():
        return [f"document path is not absolute: {path}"]
    try:
        content: str = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"document is unreadable: {path}: {exc}"]
    front: list[str] = content.split("---", 2)
    match: re.Match[str] | None = (
        re.search(r"(?m)^lifecycle_state:\s*([^\n#]+)", front[1])
        if len(front) == FRONTMATTER_PARTS and not front[0].strip()
        else None
    )
    state: str | None = match.group(1).strip().strip("\"'") if match else None
    observed: str = document["lifecycle_state"]
    if state in {"effective", "in-review"} and state != observed:
        document["lifecycle_state"] = state
        return [f"document lifecycle is now {state} (observed {observed}): {path}"]
    return []


def _list(value: JsonValue) -> list[JsonValue]:
    """Return a list value, or an empty list.

    Args:
        value: Any JSON value.

    Returns:
        The list.

    """
    return (
        check_type(value, list[JsonValue], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
        if isinstance(value, list)
        else []
    )


def _normalize_inputs(entry: JsonObject) -> JsonObject:
    key: str
    document: dict[str, bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None]
    for key in ("requirements", "subjects", "documents", "conflicts", *REF_LISTS):
        if not isinstance(entry.get(key), list):
            entry[key] = []
    documents: list[
        dict[str, bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None]
    ] = [d for d in _list(entry["documents"]) if isinstance(d, dict) and isinstance(d.get("path"), str) and d["path"]]
    for document in documents:
        document.setdefault("version", "effective")
        document.setdefault("lifecycle_state", "in-review")
    entry["documents"] = list(documents)
    for key in TEXT_FIELDS:
        if not isinstance(entry.get(key), str):
            entry[key] = ""
    raw_code: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = entry.get("code")
    code: JsonObject = raw_code if isinstance(raw_code, dict) else {}
    code.setdefault("state", "unknown")
    for key in CODE_REF_LISTS:
        if not isinstance(code.get(key), list):
            code[key] = []
    entry["code"] = code
    return code


def _normalize_documentation(entry: JsonObject, warnings: list[str]) -> None:
    canonical: list[contracts.BaselineDocument] = [
        d
        for d in check_type(
            entry["documents"],
            list[BaselineDocument],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        if d["version"] == "effective" and "arc42" in Path(d["path"]).parts
    ]
    if entry["documentationAction"] == "none" and entry["designAction"] in {
        "none",
        "reuse",
        "validate-existing",
    }:
        if not canonical:
            warnings.append(
                "existing design has no canonical arc42 document: documentation is created",
            )
            entry["documentationAction"] = "create"
        elif entry["designAction"] in {"none", "reuse"} and any(d["lifecycle_state"] != "effective" for d in canonical):
            warnings.append(
                "canonical views are in review: the existing design is validated",
            )
            entry["designAction"] = "validate-existing"


def _normalize(entry: JsonObject, warnings: list[str]) -> bool:
    """Fill the fields an entry omits and derive those another field determines.

    Args:
        entry: One assessment entry; changed in place.
        warnings: Collects what was filled or derived.

    Returns:
        True when the entry's design or implementation state is unknown.

    """
    unknown: bool = False
    code: dict[str, contracts.JsonValue] = _normalize_inputs(entry)
    if entry.get("kind") not in {"behavior", "infrastructure", "documentation"}:
        entry["kind"] = "behavior"
    if entry.get("designAction") not in {
        "none",
        "reuse",
        "validate-existing",
        "modify",
        "new",
    }:
        warnings.append(f"designAction {entry.get('designAction')!r} is not stated")
        entry["designAction"] = "validate-existing"
        unknown = True
    if entry.get("documentationAction") not in {"none", "update", "create"}:
        entry["documentationAction"] = "none"
    if entry.get("disposition") not in DISPOSITION_ACTION:
        entry["disposition"] = "undetermined"
    action: str = DISPOSITION_ACTION[check_type(entry["disposition"], str)]
    if code["state"] == "unknown":
        action = "unknown"
    elif code["state"] == "not-applicable":
        action = "none"
    elif action == "none" and code["state"] in CODE_STATE_ACTION:
        action = CODE_STATE_ACTION[check_type(code["state"], str)]
    if entry.get("implementationAction") != action:
        warnings.append(
            f"implementationAction {entry.get('implementationAction')!r} derived as "
            f"{action!r} from disposition {entry['disposition']} and code {code['state']}",
        )
        entry["implementationAction"] = action
    _normalize_documentation(entry, warnings)
    return unknown or code["state"] == "unknown" or action == "unknown"


def _entry_warnings(entry: BaselineEntry) -> list[str]:
    """Name what the evidence of an entry does not show.

    Args:
        entry: One normalized assessment entry.

    Returns:
        The warnings.

    """
    document: BaselineDocument
    refs: list[JsonObject]
    _: list[JsonObject]
    failures: list[str]
    warnings: list[str] = []
    code: contracts.BaselineCode = entry["code"]
    relevant: list[contracts.JsonObject] = (
        code["behaviorEvidenceRefs"] if entry["kind"] == "behavior" else code["infrastructureEvidenceRefs"]
    )
    if code["state"] in {"complete", "partial", "absent"} and not relevant:
        warnings.append(
            "code assessment lacks inspected evidence for its obligation kind",
        )
    if entry["kind"] == "behavior" and code["state"] == "not-applicable":
        warnings.append("behavioral obligation states no implementation evidence")
    for document in entry["documents"]:
        warnings.extend(_document_warnings(document))
    for refs in (
        code["behaviorEvidenceRefs"],
        code["infrastructureEvidenceRefs"],
        entry["awsGuidance"],
        entry["suitabilityEvidenceRefs"],
    ):
        _, failures = evidence_state(refs)
        warnings.extend(failures)
    return warnings


def _assess_entry(
    key: str,
    raw_entry: JsonObject,
    named: dict[str, JsonObject],
    result: BaselineFacts,
    matrix_snapshot: JsonObject | None,
) -> None:
    notes: list[str] = []
    _normalize(raw_entry, notes)
    entry: contracts.BaselineEntry = check_type(
        raw_entry,
        BaselineEntry,
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    # Historical code judgments remain context, never the scope decision.
    unknown: bool = entry["disposition"] == "undetermined"
    if key in named:
        stated: list[str] = [str(r) for r in _list(named[key].get("requirements")) if isinstance(r, str) and r.strip()]
        if stated and set(stated) != set(entry["requirements"]):
            notes.append("requirements taken from the surveyed capability")
            entry["requirements"] = stated
    notes.extend(_entry_warnings(entry))
    result["warnings"].extend(f"{key}: {note}" for note in notes)
    if entry["designAction"] in {"modify", "new"}:
        result["designWork"].append(key)
    if entry["designAction"] == "validate-existing":
        result["designReview"].append(key)
    if entry["documentationAction"] != "none":
        result["docWork"].append(key)
    if unknown or entry["conflicts"]:
        result["unknowns"].append(key)
    try:
        elements: dict[str, list[str]] = catalog_elements([json_object(document) for document in entry["documents"]])
    except (OSError, UnicodeError) as exc:
        elements = {}
        result["warnings"].append(f"{key}: cited catalog unreadable: {exc}")
    if (
        not elements
        or any(not satisfied(matrix_snapshot or {}, row_of(matrix_snapshot, name)) for name in elements)
        or key in result["unknowns"]
    ):
        result["implementationWork"].append(key)
    result["entries"].append(entry)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def baseline_facts(survey: JsonObject, matrix_snapshot: JsonObject | None = None) -> BaselineFacts:
    """Return explicit actions; missing/invalid observations never imply no work.

    The assessment is invalid only when the survey carries none. Each entry is normalized
    (`_normalize`); a duplicate id keeps the last entry; requirements are taken from the
    surveyed capability of the same name; a capability with no entry, and an entry whose state
    is unknown or in conflict, is reported as implementation work and in `unknowns`. Shape
    errors and evidence problems are `warnings`.

    Returns:
        The normalized actions and assessment diagnostics.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    raw: bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
    name: str
    raw_entry: JsonObject
    if not (isinstance(survey, dict)) or not (isinstance(matrix_snapshot, dict) or matrix_snapshot is None):
        argument_error: str = "baseline_facts: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    result: BaselineFacts = {
        "valid": False,
        "revision": digest(survey.get("baseline")),
        "errors": [],
        "warnings": [],
        "designWork": [],
        "designReview": [],
        "docWork": [],
        "implementationWork": [],
        "unknowns": [],
        "entries": [],
    }
    baseline: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = survey.get(
        "baseline",
    )
    if not isinstance(baseline, list) or not any(
        isinstance(e, dict) and isinstance(identifier := e.get("id"), str) and identifier.strip() for e in baseline
    ):
        result["errors"].append(
            "the survey carries no assessment (its `baseline` list is missing or empty)",
        )
        return result
    raw_schema: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema: JsonObject = json_object(raw_schema)
    result["warnings"].extend(
        f"baseline {list(error.absolute_path)}: {error.message}"
        for error in sorted(
            Draft202012Validator(schema).iter_errors(baseline),
            key=lambda error: str(list(error.absolute_path)),
        )
    )
    by_id: dict[str, JsonObject] = {}
    for raw in baseline:
        if not isinstance(raw, dict) or not isinstance(raw_id := raw.get("id"), str):
            continue
        key: str = raw_id.strip()
        if not key:
            continue
        if key in by_id:
            result["warnings"].append(f"duplicate baseline id {key}: the last is kept")
        by_id[key] = deepcopy(raw) | {"id": key}
    capabilities: list[
        dict[str, bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None]
    ] = [c for c in _list(survey.get("capabilities", [])) if isinstance(c, dict)]
    named: dict[
        str,
        dict[str, bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None],
    ] = {
        str(c.get("name")).strip(): c
        for c in capabilities
        if isinstance(cap_name := c.get("name"), str) and cap_name.strip()
    }
    for name in sorted(set(named) - set(by_id)):
        result["warnings"].append(f"capability {name} has no assessment entry")
        result["unknowns"].append(name)
        result["implementationWork"].append(name)
    for key in sorted(set(by_id) - set(named)):
        result["warnings"].append(f"{key}: no surveyed capability has this name")
    for key, raw_entry in by_id.items():
        _assess_entry(key, raw_entry, named, result, matrix_snapshot)
    result["valid"] = True
    return result


def _fingerprint_paths(paths: set[Path], warnings: list[str]) -> dict[str, str | dict[str, str]]:
    path: Path
    files: dict[str, str | dict[str, str]] = {}
    for path in sorted(paths, key=str):
        try:
            if path.is_dir():
                files[str(path)] = {
                    str(child.relative_to(path)): view_content(str(child))
                    if child.suffix == ".md"
                    else hashlib.sha256(child.read_bytes()).hexdigest()
                    for child in sorted(path.rglob("*"))
                    if child.is_file()
                }
            else:
                content: bytes = path.read_bytes()
                files[str(path)] = (
                    view_content(str(path)) if path.suffix == ".md" else hashlib.sha256(content).hexdigest()
                )
        except FileNotFoundError:
            files[str(path)] = "absent"
            warnings.append(f"survey input absent: {path}")
        except OSError as exc:
            files[str(path)] = f"unreadable: {exc}"
            warnings.append(f"survey input unreadable: {path}")
    return files


def _fingerprint_repositories(repositories: set[str], form: str | None, warnings: list[str]) -> dict[str, str]:
    repo: str
    trees: dict[str, str] = {}
    for repo in sorted(repositories) if form is None else []:
        try:
            executable: str | None = shutil.which("git")
            if executable is None:
                raise FileNotFoundError
            result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved Git executable and fixed argv.
                [executable, "-C", repo, "rev-parse", "--verify", "main^{tree}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            trees[repo] = result.stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            trees[repo] = "unreadable"
            warnings.append(f"cannot fingerprint repository main tree: {repo}: {exc}")
    return trees


def _read_freshness_receipt(path: Path, warnings: list[str]) -> JsonObject:
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
        saved: dict[str, contracts.JsonValue] = _validate_freshness_receipt(loaded)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        warnings.append(f"survey freshness receipt unreadable: {exc}")
        return {}
    return saved


def _validate_freshness_receipt(value: object) -> JsonObject:
    field: str | str
    saved: dict[str, contracts.JsonValue] = json_object(value)
    for field in ("inputs", "repos"):
        paths: list[str] = check_type(
            saved.get(field),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        if any(not Path(path).is_absolute() for path in paths):
            message: str = "freshness receipt lacks absolute input/repository paths"
            raise ValueError(message)
    return saved


def _read_survey(path: Path, errors: list[str]) -> tuple[JsonObject, bool]:
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, False
    except (OSError, ValueError) as exc:
        errors.append(f"survey unreadable: {exc}")
        return {}, False
    return json_object(loaded), True


@dataclass(frozen=True)
class FreshnessOptions:
    """Explicit configuration for survey freshness."""

    inputs: list[Path] | None = None
    repos: list[str] | None = None
    seal: bool = False
    context_sha: str | None = None
    form: str | None = None

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate each field and collection member.

        Raises:
            TypeError: The freshness configuration contains an invalid value.

        """
        message: str = "Invalid survey freshness configuration"
        if not isinstance(self.seal, bool):
            raise TypeError(message)
        if any(value is not None and not isinstance(value, str) for value in (self.context_sha, self.form)):
            raise TypeError(message)
        if self.inputs is not None and (
            not isinstance(self.inputs, list) or any(not isinstance(path, Path) for path in self.inputs)
        ):
            raise TypeError(message)
        if self.repos is not None and (
            not isinstance(self.repos, list) or any(not isinstance(repo, str) for repo in self.repos)
        ):
            raise TypeError(message)


def _freshness_receipt(
    survey: JsonObject,
    facts: BaselineFacts,
    options: FreshnessOptions,
    saved: JsonObject,
    warnings: list[str],
) -> JsonObject:
    states: list[JsonObject]
    reference_warnings: list[str]
    inputs: list[Path] | None = options.inputs
    repos: list[str] | None = options.repos
    context_sha: str | None = options.context_sha
    form: str | None = options.form
    if context_sha is None:
        context_sha = check_type(saved.get("contextSha", ""), str)
    if context_sha and not re.fullmatch(r"[0-9a-f]{64}", context_sha):
        warnings.append("survey context is not a SHA-256 digest")
    if not inputs:
        inputs = [
            Path(value)
            for value in check_type(
                saved.get("inputs", []),
                list[str],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        ]
    if not repos:
        repos = check_type(
            saved.get("repos", []),
            list[str],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    if not inputs:
        warnings.append("survey freshness names no PRD/model/constraint inputs")
    references: list[dict[str, contracts.JsonValue]] = [
        ref
        for entry in facts["entries"]
        for ref in entry["code"]["behaviorEvidenceRefs"]
        + entry["code"]["infrastructureEvidenceRefs"]
        + entry["awsGuidance"]
        + entry["suitabilityEvidenceRefs"]
    ]
    states, reference_warnings = evidence_state(references)
    warnings.extend(reference_warnings)
    paths: set[Path] = set(inputs) | {
        Path(document["path"]) for entry in facts["entries"] for document in entry["documents"]
    }
    paths |= {
        Path(check_type(ref["path"], str))
        for ref in references
        if isinstance(ref, dict)
        and ref.get("path")
        and (not ref.get("repo") or Path(check_type(ref["path"], str)).is_absolute())
    }
    repositories: set[str] = set(repos or []) | {
        check_type(ref["repo"], str)
        for ref in references
        if isinstance(ref, dict) and ref.get("repo") and not Path(str(ref.get("path") or "")).is_absolute()
    }
    if form not in {None, "adopted", "v2"}:
        message: str = f"unknown survey seal form: {form}"
        raise ValueError(message)
    raw_schema: object = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema: JsonObject = json_object(raw_schema)
    binding: contracts.JsonInput = {
        "files": _fingerprint_paths(paths, warnings),
        "contextSha": context_sha,
        "repositories": _fingerprint_repositories(repositories, form, warnings),
        "evidence": states,
        "schema": schema,
    }
    receipt: JsonObject = {
        "revision": digest(binding),
        "surveySha256": digest(survey),
        "contextSha": context_sha,
        "inputs": contracts.json_value(sorted(str(path) for path in inputs)),
        "repos": contracts.json_value(sorted(repositories)),
    }
    if form is not None:
        receipt["form"] = form
    return receipt


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def survey_freshness(survey_path: Path, options: FreshnessOptions) -> FreshnessResult:
    """Bind survey reuse to its inputs, cited evidence and repository main trees.

    Repository trees are survey-discovery inputs, not reviewer invalidation keys.
    A newly accepted survey is sealed explicitly; checking never updates its seal. Whatever
    cannot be read (the receipt, an input, a repository's main tree, a cited source) is a
    warning and is bound as it is; the seal is written whenever the survey parses, and the
    survey is current only while it carries an assessment.

    Returns:
        The exact validity, freshness, fingerprint and diagnostics.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    survey: JsonObject
    parsed: bool
    if not (isinstance(survey_path, Path)) or not (isinstance(options, FreshnessOptions)):
        argument_error: str = "survey_freshness: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    errors: list[str] = []
    warnings: list[str] = []
    seal_path: Path = survey_path.with_name(survey_path.name + ".baseline-inputs.json")
    saved: dict[str, contracts.JsonValue] = _read_freshness_receipt(seal_path, warnings)
    survey, parsed = _read_survey(survey_path, errors)
    facts: contracts.BaselineFacts = baseline_facts(survey)
    receipt: dict[str, contracts.JsonValue] = _freshness_receipt(survey, facts, options, saved, warnings)
    valid: bool = facts["valid"] and not errors
    current: bool = False
    if options.seal and parsed:
        temporary: Path = seal_path.with_suffix(seal_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(receipt, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(seal_path)
        current = valid
    elif not options.seal:
        try:
            saved_receipt: object = json.loads(seal_path.read_text(encoding="utf-8"))
            current = valid and saved_receipt == receipt
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            warnings.append(f"survey freshness receipt unreadable: {exc}")
    return {
        "valid": valid,
        "current": current,
        "revision": check_type(receipt["revision"], str),
        "errors": facts["errors"] + errors,
        "warnings": facts["warnings"] + warnings,
    }


class _Options(argparse.Namespace):
    survey: Path
    input: list[Path]
    repo: list[str]
    seal: bool
    context_sha: str | None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> int:
    """Report the survey freshness CLI result.

    Returns:
        Zero on success or two when sealing cannot establish freshness.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, required=True)
    input_default: list[Path] = []
    parser.add_argument("--input", type=Path, action="append", default=input_default)
    repo_default: list[str] = []
    parser.add_argument("--repo", action="append", default=repo_default)
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--context-sha")
    args: _Options = parser.parse_args(namespace=_Options())
    result: contracts.FreshnessResult = survey_freshness(
        args.survey,
        FreshnessOptions(inputs=args.input, repos=args.repo, seal=args.seal, context_sha=args.context_sha),
    )
    sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n")
    return 2 if args.seal and not result["current"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
