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
import strictschema
from archevidence import digest, evidence_state, load_repository_paths, view_content
from archmatrix import catalog_elements, row_of, satisfied
from contracts import (
    SEAL_FORMS,
    BaselineDocument,
    BaselineEntry,
    BaselineFacts,
    FreshnessResult,
    JsonObject,
    JsonValue,
    SealForm,
    SurveySeal,
    json_object,
    read_survey_seal,
    survey_seal_path,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

# isort: split
import survey_contract as sc

FRONTMATTER_PARTS = 3
#: The work actions a design action names: new or changed design, and existing design to validate.
DESIGN_WORK: frozenset[sc.DesignAction] = frozenset((sc.DESIGN_MODIFY, sc.DESIGN_NEW))
#: Design actions that keep the existing design.
DESIGN_KEPT: frozenset[sc.DesignAction] = frozenset((sc.DESIGN_NONE, sc.DESIGN_REUSE, sc.DESIGN_VALIDATE_EXISTING))
#: Design actions that keep the existing design without validating it.
DESIGN_UNVALIDATED: frozenset[sc.DesignAction] = frozenset((sc.DESIGN_NONE, sc.DESIGN_REUSE))
#: Code states whose assessment claims inspected code.
CODE_ASSESSED: frozenset[sc.CodeState] = frozenset((sc.CODE_COMPLETE, sc.CODE_PARTIAL, sc.CODE_ABSENT))


def _array_keys(definition: str) -> tuple[str, ...]:
    """Name the array-valued properties of one survey schema definition.

    Args:
        definition: A `$defs` name in the survey schema.

    Returns:
        The property names whose schema type is an array, in schema order.

    Raises:
        SurveyContractError: The schema carries no such definition.

    """
    defs: JsonValue = sc.load_schema().get("$defs")
    node: JsonValue = defs.get(definition) if isinstance(defs, dict) else None
    properties: JsonValue = node.get("properties") if isinstance(node, dict) else None
    if not isinstance(properties, dict):
        message: str = f"survey schema has no $defs/{definition} properties"
        raise sc.SurveyContractError(message)
    return tuple(key for key, value in properties.items() if isinstance(value, dict) and value.get("type") == "array")


#: The list-valued fields of a baseline entry, every one defaulted to an empty list.
ENTRY_LISTS: tuple[str, ...] = _array_keys("BaselineEntry")


def _evidence_lists(entry: BaselineEntry) -> list[list[sc.EvidenceRef]]:
    """Gather every evidence list one baseline entry carries, by the keys the survey contract names.

    Args:
        entry: A validated baseline entry.

    Returns:
        The code evidence lists, then the entry's own evidence lists, in contract order.

    """
    code: contracts.BaselineCode = entry["code"]
    code_lists: list[list[sc.EvidenceRef]] = [code[key] for key in sc.CODE_REF_LISTS]
    entry_lists: list[list[sc.EvidenceRef]] = [entry[key] for key in sc.BASELINE_REF_LISTS]
    return code_lists + entry_lists


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
    observed: sc.DocumentLifecycleState = document["lifecycle_state"]
    if sc.is_document_lifecycle_state(state) and state != observed:
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
    for key in ENTRY_LISTS:
        if not isinstance(entry.get(key), list):
            entry[key] = []
    documents: list[
        dict[str, bool | int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None]
    ] = [d for d in _list(entry["documents"]) if isinstance(d, dict) and isinstance(d.get("path"), str) and d["path"]]
    for document in documents:
        document.setdefault("version", sc.DEFAULT_DOCUMENT_VERSION)
        document.setdefault("lifecycle_state", sc.DEFAULT_DOCUMENT_LIFECYCLE_STATE)
    entry["documents"] = list(documents)
    for key in sc.BASELINE_TEXT_FIELDS:
        if not isinstance(entry.get(key), str):
            entry[key] = ""
    raw_code: int | float | str | list[contracts.JsonValue] | dict[str, contracts.JsonValue] | None = entry.get("code")
    code: JsonObject = raw_code if isinstance(raw_code, dict) else {}
    if not sc.is_code_state(code.get("state")):
        code["state"] = sc.DEFAULT_CODE_STATE
    for key in sc.CODE_REF_LISTS:
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
        if d["version"] == sc.VERSION_EFFECTIVE and "arc42" in Path(d["path"]).parts
    ]
    design: JsonValue = entry["designAction"]
    if entry["documentationAction"] == sc.DOC_NONE and design in DESIGN_KEPT:
        if not canonical:
            warnings.append(
                "existing design has no canonical arc42 document: documentation is created",
            )
            entry["documentationAction"] = sc.DOC_CREATE
        elif design in DESIGN_UNVALIDATED and any(d["lifecycle_state"] != sc.LIFECYCLE_EFFECTIVE for d in canonical):
            warnings.append(
                "canonical views are in review: the existing design is validated",
            )
            entry["designAction"] = sc.DESIGN_VALIDATE_EXISTING


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
    if not sc.is_baseline_kind(entry.get("kind")):
        entry["kind"] = sc.DEFAULT_BASELINE_KIND
    if not sc.is_design_action(entry.get("designAction")):
        warnings.append(f"designAction {entry.get('designAction')!r} is not stated")
        entry["designAction"] = sc.DEFAULT_DESIGN_ACTION
        unknown = True
    if not sc.is_documentation_action(entry.get("documentationAction")):
        entry["documentationAction"] = sc.DEFAULT_DOCUMENTATION_ACTION
    stated: JsonValue = entry.get("disposition")
    disposition: sc.BaselineDisposition = (
        stated if sc.is_baseline_disposition(stated) else sc.DEFAULT_BASELINE_DISPOSITION
    )
    entry["disposition"] = disposition
    state: JsonValue = code["state"]
    action: sc.ImplementationAction = sc.DISPOSITION_ACTION[disposition]
    if state == sc.CODE_UNKNOWN:
        action = sc.IMPL_UNKNOWN
    elif state == sc.CODE_NOT_APPLICABLE:
        action = sc.IMPL_NONE
    elif action == sc.IMPL_NONE and sc.is_code_state(state) and state in sc.CODE_STATE_ACTION:
        action = sc.CODE_STATE_ACTION[state]
    if entry.get("implementationAction") != action:
        warnings.append(
            f"implementationAction {entry.get('implementationAction')!r} derived as "
            f"{action!r} from disposition {disposition} and code {state}",
        )
        entry["implementationAction"] = action
    _normalize_documentation(entry, warnings)
    return unknown or state == sc.CODE_UNKNOWN or action == sc.IMPL_UNKNOWN


def _entry_warnings(entry: BaselineEntry, repository_paths: dict[str, str]) -> list[str]:
    """Name what the evidence of an entry does not show.

    Args:
        entry: One normalized assessment entry.
        repository_paths: Named checkout paths from the saved repository menu.

    Returns:
        The warnings.

    """
    document: BaselineDocument
    refs: list[sc.EvidenceRef]
    _: list[JsonObject]
    failures: list[str]
    warnings: list[str] = []
    code: contracts.BaselineCode = entry["code"]
    relevant: list[sc.EvidenceRef] = (
        code["behaviorEvidenceRefs"] if entry["kind"] == sc.KIND_BEHAVIOR else code["infrastructureEvidenceRefs"]
    )
    if code["state"] in CODE_ASSESSED and not relevant:
        warnings.append(
            "code assessment lacks inspected evidence for its obligation kind",
        )
    if entry["kind"] == sc.KIND_BEHAVIOR and code["state"] == sc.CODE_NOT_APPLICABLE:
        warnings.append("behavioral obligation states no implementation evidence")
    for document in entry["documents"]:
        warnings.extend(_document_warnings(document))
    for refs in _evidence_lists(entry):
        _, failures = evidence_state([json_object(ref) for ref in refs], repository_paths=repository_paths)
        warnings.extend(failures)
    return warnings


@dataclass(frozen=True)
class _AssessmentInputs:
    named: dict[str, JsonObject]
    matrix: JsonObject | None
    repository_paths: dict[str, str]


def _assess_entry(
    key: str,
    raw_entry: JsonObject,
    result: BaselineFacts,
    inputs: _AssessmentInputs,
) -> None:
    named, matrix_snapshot, repository_paths = inputs.named, inputs.matrix, inputs.repository_paths
    notes: list[str] = []
    _normalize(raw_entry, notes)
    entry: contracts.BaselineEntry = check_type(
        raw_entry,
        BaselineEntry,
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    # Historical code judgments remain context, never the scope decision.
    unknown: bool = entry["disposition"] == sc.DISPOSITION_UNDETERMINED
    if key in named:
        stated: list[str] = [str(r) for r in _list(named[key].get("requirements")) if isinstance(r, str) and r.strip()]
        if stated and set(stated) != set(entry["requirements"]):
            notes.append("requirements taken from the surveyed capability")
            entry["requirements"] = stated
    notes.extend(_entry_warnings(entry, repository_paths))
    result["warnings"].extend(f"{key}: {note}" for note in notes)
    if entry["designAction"] in DESIGN_WORK:
        result["designWork"].append(key)
    if entry["designAction"] == sc.DESIGN_VALIDATE_EXISTING:
        result["designReview"].append(key)
    if entry["documentationAction"] != sc.DOC_NONE:
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
def baseline_facts(
    survey: JsonObject,
    matrix_snapshot: JsonObject | None = None,
    *,
    repository_paths: dict[str, str] | None = None,
) -> BaselineFacts:
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
    schema: JsonObject = sc.baseline_schema()
    result["warnings"].extend(
        f"baseline {list(error.absolute_path)}: {error.message}"
        for error in sorted(
            strictschema.validator(schema).iter_errors(baseline),
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
        _assess_entry(key, raw_entry, result, _AssessmentInputs(named, matrix_snapshot, repository_paths or {}))
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


def _fingerprint_repositories(repositories: set[str], form: SealForm | None, warnings: list[str]) -> dict[str, str]:
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


def survey_binding(path: Path) -> tuple[SealForm | None, str] | None:
    """Read a validated survey seal's form and context binding.

    An OSError reading the seal, other than its absence, propagates from
    contracts.read_survey_seal.

    Args:
        path: The survey freshness seal file (see contracts.survey_seal_path).

    Returns:
        The seal's form and contextSha, or None when the seal is missing or fails validation.

    Raises:
        TypeError: path is not a Path.

    """
    if not isinstance(path, Path):
        message: str = "survey_binding requires a Path"
        raise TypeError(message)
    warnings: list[str] = []
    saved: SurveySeal | None = read_survey_seal(path, warnings)
    if saved is None or warnings:
        return None
    return saved.get("form"), saved["contextSha"]


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
    form: SealForm | None = None

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __post_init__(self) -> None:
        """Validate each field and collection member.

        Raises:
            TypeError: The freshness configuration contains a value of the wrong type.
            ValueError: form is not one of contracts.SEAL_FORMS.

        """
        message: str = "Invalid survey freshness configuration"
        if not isinstance(self.seal, bool):
            raise TypeError(message)
        if self.context_sha is not None and not isinstance(self.context_sha, str):
            raise TypeError(message)
        if self.form is not None and self.form not in SEAL_FORMS:
            form_error: str = f"{message}: form {self.form!r} is not one of {sorted(SEAL_FORMS)}"
            raise ValueError(form_error)
        if self.inputs is not None and (
            not isinstance(self.inputs, list) or any(not isinstance(path, Path) for path in self.inputs)
        ):
            raise TypeError(message)
        if self.repos is not None and (
            not isinstance(self.repos, list) or any(not isinstance(repo, str) for repo in self.repos)
        ):
            raise TypeError(message)


@dataclass(frozen=True)
class _FreshnessInputs:
    saved: SurveySeal | None
    warnings: list[str]
    repository_paths: dict[str, str]


def _freshness_receipt(
    survey: JsonObject,
    facts: BaselineFacts,
    options: FreshnessOptions,
    binding_inputs: _FreshnessInputs,
) -> tuple[SurveySeal, bool]:
    states: list[JsonObject]
    reference_warnings: list[str]
    saved: SurveySeal | None = binding_inputs.saved
    inputs: list[Path] | None = options.inputs
    repos: list[str] | None = options.repos
    context_sha: str | None = options.context_sha
    form: SealForm | None = options.form
    if form is None and saved is not None:
        form = saved.get("form")
    if context_sha is None:
        context_sha = saved["contextSha"] if saved is not None else ""
    if context_sha and not re.fullmatch(r"[0-9a-f]{64}", context_sha):
        binding_inputs.warnings.append("survey context is not a SHA-256 digest")
    if not inputs:
        inputs = [Path(value) for value in saved["inputs"]] if saved is not None else []
    if not repos:
        repos = list(saved["repos"]) if saved is not None else []
    if not inputs:
        binding_inputs.warnings.append("survey freshness names no PRD/model/constraint inputs")
    references: list[dict[str, contracts.JsonValue]] = [
        json_object(ref) for entry in facts["entries"] for refs in _evidence_lists(entry) for ref in refs
    ]
    states, reference_warnings = evidence_state(references, repository_paths=binding_inputs.repository_paths)
    binding_inputs.warnings.extend(reference_warnings)
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
    schema: JsonObject = sc.baseline_schema()
    binding: contracts.JsonInput = {
        "files": _fingerprint_paths(paths, binding_inputs.warnings),
        "contextSha": context_sha,
        "repositories": _fingerprint_repositories(repositories, form, binding_inputs.warnings),
        "evidence": states,
        "schema": schema,
    }
    receipt: SurveySeal = {
        "revision": digest(binding),
        "surveySha256": digest(survey),
        "contextSha": context_sha,
        "inputs": sorted(str(path) for path in inputs),
        "repos": sorted(repositories),
    }
    if form is not None:
        receipt["form"] = form
    return receipt, not reference_warnings


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def survey_freshness(survey_path: Path, options: FreshnessOptions) -> FreshnessResult:
    """Bind survey reuse to its inputs, cited evidence and repository main trees.

    Repository trees are survey-discovery inputs, not reviewer invalidation keys.
    A newly accepted survey is sealed explicitly; checking never updates its seal. Whatever
    cannot be read (an input, a repository's main tree, a cited source) is a warning and is
    bound as it is; the seal is written whenever the survey parses, and the survey is current
    only while it carries an assessment. An OSError reading the seal, other than its absence,
    propagates from contracts.read_survey_seal, and an OSError writing the seal propagates.

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
    seal_path: Path = survey_seal_path(survey_path)
    saved: SurveySeal | None = read_survey_seal(seal_path, warnings)
    survey, parsed = _read_survey(survey_path, errors)
    repository_paths = load_repository_paths(survey_path.parent)
    facts: contracts.BaselineFacts = baseline_facts(survey, repository_paths=repository_paths)
    receipt: SurveySeal
    evidence_readable: bool
    receipt, evidence_readable = _freshness_receipt(
        survey,
        facts,
        options,
        _FreshnessInputs(saved, warnings, repository_paths),
    )
    valid: bool = facts["valid"] and not errors
    current: bool = False
    if options.seal and parsed:
        temporary: Path = seal_path.with_suffix(seal_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(receipt, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(seal_path)
        current = valid and evidence_readable
    elif not options.seal:
        current = valid and evidence_readable and saved is not None and saved == receipt
    return {
        "valid": valid,
        "current": current,
        "revision": receipt["revision"],
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
