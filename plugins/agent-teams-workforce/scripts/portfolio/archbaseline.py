"""Validate baseline observations and derive bounded architecture work from them.

The canonical schema belongs to artifact-handoff. These are assessment actions,
not new document lifecycle states. This helper verifies evidence bindings and
contradictions; reviewers still judge whether the evidence proves the assessment.
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


def _document_errors(document: dict) -> list[str]:
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
    if state != observed and not (observed == "in-review" and state == "effective"):
        return [f"document lifecycle changed or was not observed: {path}"]
    return []


def _entry_errors(entry: dict) -> list[str]:
    errors = []
    code = entry["code"]
    required_action = {
        "retain": "none",
        "change": "modify",
        "replace": "replace",
        "add": "new",
        "retire": "retire",
        "undetermined": "unknown",
    }[entry["disposition"]]
    if entry["implementationAction"] != required_action:
        errors.append("target disposition and implementation action disagree")
    relevant = (
        code["behaviorEvidenceRefs"]
        if entry["kind"] == "behavior"
        else code["infrastructureEvidenceRefs"]
    )
    if code["state"] in {"complete", "partial", "absent"} and not relevant:
        errors.append(
            "code assessment lacks inspected evidence for its obligation kind"
        )
    if entry["kind"] == "behavior" and code["state"] == "not-applicable":
        errors.append("behavioral obligation cannot omit implementation evidence")
    if entry["implementationAction"] == "none" and code["state"] not in {
        "complete",
        "not-applicable",
    }:
        errors.append("no implementation work requires complete or non-applicable code")
    if code["state"] == "unknown" and entry["implementationAction"] != "unknown":
        errors.append("unknown code must not be treated as absent or complete")
    if code["state"] == "not-applicable" and entry["implementationAction"] != "none":
        errors.append("non-executable obligation cannot request implementation")
    if (
        entry["designAction"] in {"none", "reuse"}
        and entry["documentationAction"] == "none"
        and not any(
            d["lifecycle_state"] == "effective"
            and d["version"] == "effective"
            and "arc42" in Path(d["path"]).parts
            for d in entry["documents"]
        )
    ):
        errors.append(
            "unchanged design requires a reviewed canonical effective document"
        )
    if (
        entry["designAction"] in {"none", "reuse", "validate-existing"}
        and entry["documentationAction"] == "none"
    ):
        canonical = [
            d
            for d in entry["documents"]
            if d["version"] == "effective" and "arc42" in Path(d["path"]).parts
        ]
        if not canonical:
            errors.append(
                "existing design needs canonical arc42 documentation or documentation integration work"
            )
        elif entry["designAction"] in {"none", "reuse"} and any(
            document["lifecycle_state"] != "effective" for document in canonical
        ):
            errors.append(
                "unreviewed canonical views require explicit existing-design validation"
            )
    for document in entry["documents"]:
        errors.extend(_document_errors(document))
    for refs in (
        code["behaviorEvidenceRefs"],
        code["infrastructureEvidenceRefs"],
        entry["awsGuidance"],
        entry["suitabilityEvidenceRefs"],
    ):
        _, failures = evidence_state(refs)
        errors.extend(failures)
    return errors


def baseline_facts(survey: dict) -> dict:
    """Return explicit actions; missing/invalid observations never imply no work."""
    result = {
        "valid": False,
        "revision": digest(survey.get("baseline")),
        "errors": [],
        "designWork": [],
        "designReview": [],
        "docWork": [],
        "implementationWork": [],
        "unknowns": [],
        "entries": [],
    }
    baseline = survey.get("baseline")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(baseline),
        key=lambda error: str(list(error.absolute_path)),
    )
    if errors:
        result["errors"] = [
            f"baseline {list(error.absolute_path)}: {error.message}" for error in errors
        ]
        return result
    capabilities = survey.get("capabilities", [])
    expected = {item.get("name") for item in capabilities if isinstance(item, dict)}
    actual = {entry["id"] for entry in baseline}
    if not expected or None in expected or expected != actual:
        result["errors"].append(
            "baseline ids must cover exactly the survey capability names"
        )
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        entry = next(
            (row for row in baseline if row["id"] == capability.get("name")), None
        )
        if entry and set(entry["requirements"]) != set(
            capability.get("requirements", [])
        ):
            result["errors"].append(
                f"{entry['id']}: baseline requirements differ from surveyed capability"
            )
    seen = set()
    for entry in baseline:
        key = entry["id"]
        if key in seen:
            result["errors"].append(f"duplicate baseline id: {key}")
        seen.add(key)
        result["errors"].extend(f"{key}: {error}" for error in _entry_errors(entry))
        if entry["designAction"] in {"modify", "new"}:
            result["designWork"].append(key)
        if entry["designAction"] == "validate-existing":
            result["designReview"].append(key)
        if entry["documentationAction"] != "none":
            result["docWork"].append(key)
        if entry["implementationAction"] in {"modify", "new", "replace", "retire"}:
            result["implementationWork"].append(key)
        if (
            entry["code"]["state"] == "unknown"
            or entry["implementationAction"] == "unknown"
            or entry["conflicts"]
        ):
            result["unknowns"].append(key)
        result["entries"].append(entry)
    result["valid"] = not result["errors"]
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
    A newly accepted survey is sealed explicitly; checking never updates its seal.
    """
    errors = []
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
        errors.append(f"survey freshness receipt unreadable: {exc}")
        saved = {}
    if context_sha is None:
        context_sha = saved.get("contextSha", "")
    if context_sha and not re.fullmatch(r"[0-9a-f]{64}", context_sha):
        errors.append("survey context must be a SHA-256 digest")
    if not inputs:
        inputs = [Path(value) for value in saved.get("inputs", [])]
    if not repos:
        repos = saved.get("repos", [])
    if not inputs:
        errors.append("survey freshness needs explicit PRD/model/constraint inputs")
    try:
        survey = json.loads(survey_path.read_text(encoding="utf-8"))
        if not isinstance(survey, dict):
            raise ValueError("survey is not an object")
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
    states, reference_errors = evidence_state(references)
    errors.extend(reference_errors)
    paths = set(inputs) | {
        Path(document["path"]) for entry in entries for document in entry["documents"]
    }
    paths |= {
        Path(ref["path"])
        for ref in references
        if ref.get("path") and not ref.get("repo")
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
            errors.append(f"required survey input absent: {path}")
        except OSError as exc:
            files[str(path)] = f"unreadable: {exc}"
            errors.append(f"required survey input unreadable: {path}")
    repositories = set(repos or []) | {
        ref["repo"] for ref in references if ref.get("repo")
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
            errors.append(f"cannot fingerprint repository main tree: {repo}: {exc}")
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
    if seal and valid:
        temporary = seal_path.with_suffix(seal_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(seal_path)
        current = True
    elif not seal:
        try:
            current = valid and json.loads(seal_path.read_text()) == receipt
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            errors.append(f"survey freshness receipt unreadable: {exc}")
    return {
        "valid": valid,
        "current": current,
        "revision": revision,
        "errors": facts["errors"] + errors,
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
