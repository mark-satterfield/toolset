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
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator

from archevidence import digest, evidence_state, view_content

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills/artifact-handoff/schemas/architecture-baseline.schema.json"
)

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
TEXT_FIELDS = ("rationale", "current", "target")


def _document_warnings(document: dict) -> list[str]:
    """Name what a cited document's state says against the observation recorded for it.

    Args:
        document: One `documents` entry.

    Returns:
        The warnings; the observation is replaced by the state the file now carries.
    """
    path = Path(document["path"])
    if not path.is_absolute():
        return [f"document path is not absolute: {path}"]
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"document is unreadable: {path}: {exc}"]
    front = content.split("---", 2)
    match = (
        re.search(r"(?m)^lifecycle_state:\s*([^\n#]+)", front[1])
        if len(front) == 3 and not front[0].strip()
        else None
    )
    state = match[1].strip().strip("\"'") if match else None
    observed = document["lifecycle_state"]
    if state in {"effective", "in-review"} and state != observed:
        document["lifecycle_state"] = state
        return [f"document lifecycle is now {state} (observed {observed}): {path}"]
    return []


def _list(value: object) -> list:
    """A list value, or an empty list.

    Args:
        value: Any JSON value.

    Returns:
        The list.
    """
    return value if isinstance(value, list) else []


def _normalize(entry: dict, warnings: list[str]) -> bool:
    """Fill the fields an entry omits and derive those another field determines.

    Args:
        entry: One assessment entry; changed in place.
        warnings: Collects what was filled or derived.

    Returns:
        True when the entry's design or implementation state is unknown.
    """
    unknown = False
    for key in ("requirements", "subjects", "documents", "conflicts", *REF_LISTS):
        if not isinstance(entry.get(key), list):
            entry[key] = []
    entry["documents"] = [
        d
        for d in entry["documents"]
        if isinstance(d, dict) and isinstance(d.get("path"), str) and d["path"]
    ]
    for document in entry["documents"]:
        document.setdefault("version", "effective")
        document.setdefault("lifecycle_state", "in-review")
    for key in TEXT_FIELDS:
        if not isinstance(entry.get(key), str):
            entry[key] = ""
    code = entry.get("code") if isinstance(entry.get("code"), dict) else {}
    code.setdefault("state", "unknown")
    for key in CODE_REF_LISTS:
        if not isinstance(code.get(key), list):
            code[key] = []
    entry["code"] = code
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
    action = DISPOSITION_ACTION[entry["disposition"]]
    if code["state"] == "unknown":
        action = "unknown"
    elif code["state"] == "not-applicable":
        action = "none"
    elif action == "none" and code["state"] in CODE_STATE_ACTION:
        action = CODE_STATE_ACTION[code["state"]]
    if entry.get("implementationAction") != action:
        warnings.append(
            f"implementationAction {entry.get('implementationAction')!r} derived as "
            f"{action!r} from disposition {entry['disposition']} and code {code['state']}"
        )
        entry["implementationAction"] = action
    canonical = [
        d
        for d in entry["documents"]
        if d["version"] == "effective" and "arc42" in Path(d["path"]).parts
    ]
    if entry["documentationAction"] == "none" and entry["designAction"] in {
        "none",
        "reuse",
        "validate-existing",
    }:
        if not canonical:
            warnings.append(
                "existing design has no canonical arc42 document: documentation is created"
            )
            entry["documentationAction"] = "create"
        elif entry["designAction"] in {"none", "reuse"} and any(
            d["lifecycle_state"] != "effective" for d in canonical
        ):
            warnings.append(
                "canonical views are in review: the existing design is validated"
            )
            entry["designAction"] = "validate-existing"
    return unknown or code["state"] == "unknown" or action == "unknown"


def _entry_warnings(entry: dict) -> list[str]:
    """Name what the evidence of an entry does not show.

    Args:
        entry: One normalized assessment entry.

    Returns:
        The warnings.
    """
    warnings = []
    code = entry["code"]
    relevant = (
        code["behaviorEvidenceRefs"]
        if entry["kind"] == "behavior"
        else code["infrastructureEvidenceRefs"]
    )
    if code["state"] in {"complete", "partial", "absent"} and not relevant:
        warnings.append(
            "code assessment lacks inspected evidence for its obligation kind"
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


def baseline_facts(survey: dict) -> dict:
    """Return explicit actions; missing/invalid observations never imply no work.

    The assessment is invalid only when the survey carries none. Each entry is normalized
    (`_normalize`); a duplicate id keeps the last entry; requirements are taken from the
    surveyed capability of the same name; a capability with no entry, and an entry whose state
    is unknown or in conflict, is reported as implementation work and in `unknowns`. Shape
    errors and evidence problems are `warnings`.
    """
    result = {
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
    baseline = survey.get("baseline")
    if not isinstance(baseline, list) or not any(
        isinstance(e, dict) and isinstance(e.get("id"), str) and e["id"].strip()
        for e in baseline
    ):
        result["errors"].append(
            "the survey carries no assessment (its `baseline` list is missing or empty)"
        )
        return result
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    result["warnings"].extend(
        f"baseline {list(error.absolute_path)}: {error.message}"
        for error in sorted(
            Draft202012Validator(schema).iter_errors(baseline),
            key=lambda error: str(list(error.absolute_path)),
        )
    )
    by_id: dict[str, dict] = {}
    for raw in baseline:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            continue
        key = raw["id"].strip()
        if not key:
            continue
        if key in by_id:
            result["warnings"].append(f"duplicate baseline id {key}: the last is kept")
        by_id[key] = json.loads(json.dumps(raw)) | {"id": key}
    capabilities = [c for c in survey.get("capabilities", []) if isinstance(c, dict)]
    named = {
        str(c.get("name")).strip(): c
        for c in capabilities
        if isinstance(c.get("name"), str) and c["name"].strip()
    }
    for name in sorted(set(named) - set(by_id)):
        result["warnings"].append(f"capability {name} has no assessment entry")
        result["unknowns"].append(name)
        result["implementationWork"].append(name)
    for key in sorted(set(by_id) - set(named)):
        result["warnings"].append(f"{key}: no surveyed capability has this name")
    for key, entry in by_id.items():
        notes: list[str] = []
        unknown = _normalize(entry, notes)
        if key in named:
            stated = [
                str(r)
                for r in _list(named[key].get("requirements"))
                if isinstance(r, str) and r.strip()
            ]
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
        if (
            entry["implementationAction"] in {"modify", "new", "replace", "retire"}
            or key in result["unknowns"]
        ):
            result["implementationWork"].append(key)
        result["entries"].append(entry)
    result["valid"] = True
    return result


def survey_freshness(
    survey_path: Path,
    inputs: list[Path] | None = None,
    *,
    repos: list[str] | None = None,
    seal: bool = False,
    context_sha: str | None = None,
) -> dict:
    """Bind survey reuse to its inputs, cited evidence and repository main trees.

    Repository trees are survey-discovery inputs, not reviewer invalidation keys.
    A newly accepted survey is sealed explicitly; checking never updates its seal. Whatever
    cannot be read (the receipt, an input, a repository's main tree, a cited source) is a
    warning and is bound as it is; the seal is written whenever the survey parses, and the
    survey is current only while it carries an assessment.
    """
    errors: list[str] = []
    warnings: list[str] = []
    seal_path = survey_path.with_name(survey_path.name + ".baseline-inputs.json")
    saved = {}
    try:
        saved = json.loads(seal_path.read_text())
        if not isinstance(saved, dict) or any(
            not isinstance(saved.get(field), list)
            or any(
                not isinstance(value, str) or not Path(value).is_absolute()
                for value in saved[field]
            )
            for field in ("inputs", "repos")
        ):
            raise ValueError("freshness receipt lacks absolute input/repository paths")
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        warnings.append(f"survey freshness receipt unreadable: {exc}")
        saved = {}
    if context_sha is None:
        context_sha = saved.get("contextSha", "")
    if context_sha and not re.fullmatch(r"[0-9a-f]{64}", context_sha):
        warnings.append("survey context is not a SHA-256 digest")
    if not inputs:
        inputs = [Path(value) for value in saved.get("inputs", [])]
    if not repos:
        repos = saved.get("repos", [])
    if not inputs:
        warnings.append("survey freshness names no PRD/model/constraint inputs")
    parsed = False
    try:
        survey = json.loads(survey_path.read_text(encoding="utf-8"))
        if not isinstance(survey, dict):
            raise ValueError("survey is not an object")
        parsed = True
    except FileNotFoundError:
        survey = {}
    except (OSError, ValueError) as exc:
        survey = {}
        errors.append(f"survey unreadable: {exc}")
    facts = baseline_facts(survey)
    entries = facts["entries"]
    references = [
        ref
        for entry in entries
        for ref in entry["code"]["behaviorEvidenceRefs"]
        + entry["code"]["infrastructureEvidenceRefs"]
        + entry["awsGuidance"]
        + entry["suitabilityEvidenceRefs"]
    ]
    states, reference_warnings = evidence_state(references)
    warnings.extend(reference_warnings)
    paths = set(inputs) | {
        Path(document["path"]) for entry in entries for document in entry["documents"]
    }
    paths |= {
        Path(ref["path"])
        for ref in references
        if isinstance(ref, dict)
        and ref.get("path")
        and (not ref.get("repo") or Path(ref["path"]).is_absolute())
    }
    files = {}
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
                content = path.read_bytes()
                files[str(path)] = (
                    view_content(str(path))
                    if path.suffix == ".md"
                    else hashlib.sha256(content).hexdigest()
                )
        except FileNotFoundError:
            files[str(path)] = "absent"
            warnings.append(f"survey input absent: {path}")
        except OSError as exc:
            files[str(path)] = f"unreadable: {exc}"
            warnings.append(f"survey input unreadable: {path}")
    repositories = set(repos or []) | {
        ref["repo"]
        for ref in references
        if isinstance(ref, dict)
        and ref.get("repo")
        and not Path(str(ref.get("path") or "")).is_absolute()
    }
    trees = {}
    for repo in sorted(repositories):
        try:
            result = subprocess.run(
                ["git", "-C", repo, "rev-parse", "--verify", "main^{tree}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            trees[repo] = result.stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            trees[repo] = "unreadable"
            warnings.append(f"cannot fingerprint repository main tree: {repo}: {exc}")
    binding = {
        "files": files,
        "contextSha": context_sha,
        "repositories": trees,
        "evidence": states,
        "schema": json.loads(SCHEMA_PATH.read_text()),
    }
    revision = digest(binding)
    receipt = {
        "revision": revision,
        "surveySha256": digest(survey),
        "contextSha": context_sha,
        "inputs": sorted(str(path) for path in inputs),
        "repos": sorted(repositories),
    }
    valid = facts["valid"] and not errors
    current = False
    if seal and parsed:
        temporary = seal_path.with_suffix(seal_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(seal_path)
        current = valid
    elif not seal:
        try:
            current = valid and json.loads(seal_path.read_text()) == receipt
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            warnings.append(f"survey freshness receipt unreadable: {exc}")
    return {
        "valid": valid,
        "current": current,
        "revision": revision,
        "errors": facts["errors"] + errors,
        "warnings": facts["warnings"] + warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, required=True)
    parser.add_argument("--input", type=Path, action="append", default=[])
    parser.add_argument("--repo", action="append", default=[])
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--context-sha")
    args = parser.parse_args()
    result = survey_freshness(
        args.survey,
        args.input,
        repos=args.repo,
        seal=args.seal,
        context_sha=args.context_sha,
    )
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 2 if args.seal and not result["current"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
