"""Survey adoption proves the old seal before migrating its binding format."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from orchestrator.core.tools import CommandResult

import json
import sys
from pathlib import Path

# The survey and target report contracts are generated into the artifact-handoff skill.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import archbaseline
import archrevision
import jsonartifact
import jsonschema
import strictschema
from contracts import (
    SEAL_FORM_ADOPTED,
    SEAL_FORM_V2,
    FreshnessResult,
    SealForm,
    survey_seal_path,
)
from survey_contract import (
    SURVEY_FILE,
    Survey,
    SurveyContractError,
    parse_survey,
    schema_sha256,
)
from target_contract import KEY_SUBJECT_REFUSALS, TargetResult, validate_target_report
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.handback_contract import OTHER_CAUSE, reused_note
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.flows.architecture_resume import retire_generation
from orchestrator.flows.architecture_support import Architecture, ArchitectureStep, read
from orchestrator.flows.elaboration_support import emit_event


class RepositorySummary(TypedDict):
    """The four repository facts consumed by survey authoring."""

    name: str
    path: str | None
    role: str | None
    lifecycle: str


SURVEY_MARKDOWN: str = "survey.md"
SURVEY_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    SURVEY_MARKDOWN,
    f"{SURVEY_FILE}.meta.json",
    f"{SURVEY_MARKDOWN}.meta.json",
    survey_seal_path(Path(SURVEY_FILE)).name,
    jsonartifact.receipt_path(Path(SURVEY_FILE)).name,
)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def saved_survey(path: Path) -> Survey | None:
    """Read and validate a saved survey against its contract.

    Returns:
        The typed survey, or None when the file is absent or breaks the survey contract.

    Raises:
        TypeError: The path is not a Path.

    """
    if not isinstance(path, Path):
        argument_error: str = "saved_survey: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    if not path.is_file():
        return None
    try:
        return parse_survey(read(path))
    except SurveyContractError:
        return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def current_survey(flow: Architecture, *, adopt: bool = True) -> bool:
    """Check whether the survey still matches its accepted inputs.

    Returns:
        The validated architecture result.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)) or not (isinstance(adopt, bool)):
        argument_error: str = "current_survey: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    form: SealForm | None
    context_sha: str
    survey: Path = flow.work / SURVEY_FILE
    binding: tuple[SealForm | None, str] | None = archbaseline.survey_binding(survey_seal_path(survey))
    if binding is None:
        return False
    form, context_sha = binding
    schema_sha: str = schema_sha256()
    if form is not None:
        context_sha = schema_sha
    freshness: FreshnessResult = flow.call(
        "survey",
        archbaseline.survey_freshness,
        survey,
        archbaseline.FreshnessOptions(context_sha=context_sha, form=form),
    )
    if not freshness["current"]:
        return False
    saved: Survey | None = saved_survey(survey)
    if saved is None or not saved["subject"]:
        return False
    if form is None and adopt:
        adopted: FreshnessResult = flow.call(
            "survey",
            archbaseline.survey_freshness,
            survey,
            archbaseline.FreshnessOptions(seal=True, form=SEAL_FORM_ADOPTED, context_sha=schema_sha),
        )
        flow.checked(adopted, "survey")
        flow.adopted = True
    emit_event(flow.runner.emit, reused_note(step="architecture:survey"))
    return True


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def prepare_survey(flow: Architecture) -> None:
    # The survey's exact binding can remain current when a different cited round view changed.
    """Prepare a current survey and validate its target subject.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    name: str
    if not (isinstance(flow, Architecture)):
        argument_error: str = "prepare_survey: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    context_facts: dict[str, JsonValue] = read(flow.context_path)
    current: bool = current_survey(flow, adopt=False)
    revision: dict[str, JsonValue] = flow.checked(
        json_object(
            flow.call("survey", archrevision.check, str(flow.arch), str(flow.work)),
        ),
        "survey",
    )
    if revision.get("status") == "stale" and current:
        moved: Path = Path(check_type(revision["movedTo"], str))
        for name in SURVEY_FILES:
            source: Path = moved / name
            if source.exists():
                source.rename(flow.work / name)
    if not current:
        retire_generation(flow)
    flow.draft.mkdir(parents=True, exist_ok=True)
    write_json(flow.context_path, context_facts)
    if not current_survey(flow):
        produce_survey(flow)
    produced: Survey | None = saved_survey(flow.work / SURVEY_FILE)
    flow.subject = flow.subject or (produced["subject"] if produced is not None else "") or flow.prd.stem
    if flow.subject == flow.prd.stem:
        flow.forbid.remove(flow.prd.stem)
    report: dict[str, JsonValue] = flow.target(dry_run=True)
    result: TargetResult = validate_target_report(report, "architecture target dry run")
    stage: str = "survey"
    if result.get(KEY_SUBJECT_REFUSALS):
        raise flow.tools.failure(stage, OTHER_CAUSE, report)


def _survey_repositories(flow: Architecture) -> list[RepositorySummary]:
    """Project the inventory response into the saved survey repository fields.

    Returns:
        The active repository summaries consumed by survey authoring.

    """
    inventory: CommandResult = flow.tools.polyrepo(["inventory", "--no-fetch"], stage="survey")
    return survey_repositories(inventory.stdout)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def survey_repositories(output: str) -> list[RepositorySummary]:
    """Project the polyrepo inventory's sole wire shape into survey repository facts.

    Returns:
        Active repository summaries from the required ``repos`` collection.

    Raises:
        TypeError: Output is not a JSON object text, or a repository row or field has the wrong type.
        ValueError: The output is not JSON, or lacks its required repository collection.

    """
    if not isinstance(output, str):
        message: str = "Repository inventory output must be JSON text"
        raise TypeError(message)
    decoded: object = json.loads(output)
    if not isinstance(decoded, dict):
        message = "Repository inventory output must be a JSON object"
        raise TypeError(message)
    value: dict[str, JsonValue] = json_object(decoded)
    if "repos" not in value:
        message = "Repository inventory requires the producer's repos collection"
        raise ValueError(message)
    raw_rows: JsonValue = value["repos"]
    if not isinstance(raw_rows, list) or any(not isinstance(row, dict) for row in raw_rows):
        message = "Repository inventory repos must be an array of objects"
        raise TypeError(message)
    rows: list[dict[str, JsonValue]] = check_type(
        raw_rows,
        list[dict[str, JsonValue]],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    repositories: list[RepositorySummary] = []
    row: dict[str, JsonValue]
    for row in rows:
        fields: dict[str, JsonValue] = {}
        key: str
        for key in ("name", "path", "role", "lifecycle"):
            field: JsonValue = row.get(key)
            if key not in row or (not isinstance(field, str) and not (field is None and key in {"path", "role"})):
                message = f"Repository inventory repos[].{key} must match its string/null producer contract"
                raise TypeError(message)
            fields[key] = field
        if fields["lifecycle"] != "archived" and "/apps/marketing/" not in str(fields["path"]):
            repositories.append({
                "name": check_type(fields["name"], str),
                "path": check_type(fields["path"], str | None),
                "role": check_type(fields["role"], str | None),
                "lifecycle": check_type(fields["lifecycle"], str),
            })
    return repositories


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def produce_survey(flow: Architecture, *, recheck: bool = False) -> None:
    """Produce and seal the survey against repository and architecture inputs.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if not (isinstance(flow, Architecture)) or not (isinstance(recheck, bool)):
        argument_error: str = "produce_survey: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    stage: str = "survey"
    repositories: list[RepositorySummary] = _survey_repositories(flow)
    repo_file: Path = flow.work / "repositories.json"
    write_json(repo_file, repositories)
    refs: tuple[Path, Path, Path, Path] = (
        flow.prd,
        flow.arch / "reference/architecture-documentation-model.md",
        flow.arch / "reference/diagram-and-model-types.md",
        flow.arch / "arc42/02-architecture-constraints",
    )
    inputs: tuple[str, ...] = (*map(str, refs), str(repo_file))
    if recheck:
        inputs += (str(flow.ledger_input("recheck")),)
    survey: Path = flow.work / SURVEY_FILE
    context_sha: str = schema_sha256()
    for _ in range(2):
        flow.agent(
            ArchitectureStep(
                "prd-reality-reconciler",
                survey,
                "survey",
                inputs,
                "Reassess the capabilities the open findings in the ledger concern."
                if recheck
                else "Write the survey of this PRD's capabilities.",
            ),
        )
        sealed: FreshnessResult = flow.call(
            "survey",
            archbaseline.survey_freshness,
            survey,
            archbaseline.FreshnessOptions(inputs=list(refs), seal=True, form=SEAL_FORM_V2, context_sha=context_sha),
        )
        if sealed["current"]:
            break
        error_path: Path = flow.work / "survey.errors.json"
        write_json(error_path, sealed)
        inputs += (str(error_path),)
    else:
        raise flow.tools.failure(stage, OTHER_CAUSE, json_object(sealed))
    markdown: Path = flow.work / SURVEY_MARKDOWN
    try:
        result: Survey = parse_survey(read(survey))
    except SurveyContractError as exc:
        raise flow.tools.failure(stage, OTHER_CAUSE, {"error": str(exc)}) from exc
    markdown.write_text(
        f"# {result['subject']}\n\n{result['summary']}\n\n"
        + "\n".join(f"- {capability['name']}" for capability in result["capabilities"])
        + "\n",
        encoding="utf-8",
    )
    flow.store.accept("architecture:survey", inputs, (markdown,), producer="python")
    flow.facts()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def adopt_result(
    flow: Architecture,
    path: Path,
    inputs: tuple[str, ...],
    producer: str,
) -> None:
    """Adopt a valid prior artifact only when its recorded inputs still match.

    Raises:
        TypeError: An argument violates the declared input contract.

    """
    if (
        not (isinstance(flow, Architecture))
        or not (isinstance(path, Path))
        or not (isinstance(inputs, tuple))
        or not (isinstance(producer, str))
    ):
        argument_error: str = "adopt_result: arguments do not satisfy the declared input contract"
        raise TypeError(argument_error)
    if not flow.adopted or not path.is_file():
        return
    meta: dict[str, JsonValue] = read(path.with_name(path.name + ".meta.json"))
    if meta.get("sha256") != flow.store.module.sha256_file(path) or not meta.get(
        "inputs",
    ):
        return
    if any(
        flow.store.module.input_problem(row, flow.store.root, path)
        for row in check_type(
            meta["inputs"],
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
    ):
        return
    schema: str = (
        "coordinator-plan" if producer == "architecture-decision-workflow-coordinator" else "architecture-writer"
    )
    try:
        strictschema.validate(read(path), read(flow.schemas / f"{schema}.schema.json"))
    except jsonschema.ValidationError:
        return
    flow.store.accept(
        f"architecture:{path.stem}",
        (*inputs, str(flow.context_path)),
        (path,),
        producer=producer,
    )
