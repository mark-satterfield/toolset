"""Survey adoption proves the old seal before migrating its binding format."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator.core.tools import CommandResult

import hashlib
import json
from pathlib import Path

import archbaseline
import archrevision
import jsonschema
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.flows.architecture_resume import retire_generation
from orchestrator.flows.architecture_support import Architecture, ArchitectureStep, read

SURVEY_FILES = (
    "survey.json",
    "survey.md",
    "survey.json.meta.json",
    "survey.md.meta.json",
    "survey.json.baseline-inputs.json",
    "survey.json.receipt",
)


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
    form: str | None
    context_sha: str | None
    survey: Path = flow.work / "survey.json"
    seal: dict[str, JsonValue] = read(flow.work / "survey.json.baseline-inputs.json")
    form = check_type(seal.get("form"), str | None)
    schema: dict[str, JsonValue] = read(flow.schemas / "survey.schema.json")
    schema_sha: str = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()
    context_sha = schema_sha if form in {"v2", "adopted"} else check_type(seal.get("contextSha"), str | None)
    freshness: dict[str, JsonValue] = json_object(
        flow.call(
            "survey",
            archbaseline.survey_freshness,
            survey,
            archbaseline.FreshnessOptions(context_sha=context_sha, form=form),
        ),
    )
    if not freshness["current"] or not read(survey).get("subject"):
        return False
    try:
        jsonschema.validate(read(survey), schema)
    except jsonschema.ValidationError:
        return False
    if not form and adopt:
        flow.checked(
            json_object(
                flow.call(
                    "survey",
                    archbaseline.survey_freshness,
                    survey,
                    archbaseline.FreshnessOptions(seal=True, form="adopted", context_sha=schema_sha),
                ),
            ),
            "survey",
        )
        flow.adopted = True
    flow.runner.emit("note", kind="reused", step="architecture:survey")
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
    flow.subject = flow.subject or str(
        read(flow.work / "survey.json").get("subject") or flow.prd.stem,
    )
    if flow.subject == flow.prd.stem:
        flow.forbid.remove(flow.prd.stem)
    result: dict[str, JsonValue] = flow.target(dry_run=True)
    stage: str = "survey"
    if result.get("subjectRefusals"):
        raise flow.tools.failure(stage, "other", result)


def _survey_repositories(flow: Architecture) -> list[dict[str, JsonValue]]:
    """Project the inventory response into the saved survey repository fields.

    Returns:
        The active repository summaries consumed by survey authoring.

    """
    rows: JsonValue
    inventory: CommandResult = flow.tools.polyrepo(["inventory", "--no-fetch"], stage="survey")
    value: object = json.loads(inventory.stdout)
    rows = (
        value
        if isinstance(value, list)
        else json_object(value).get("repositories", json_object(value).get("repos", []))
    )
    repositories: list[dict[str, int | float | str | list[JsonValue] | dict[str, JsonValue] | None]] = [
        {key: row.get(key) for key in ("name", "path", "role", "lifecycle")}
        for row in check_type(
            rows,
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        if row.get("lifecycle") != "archived" and "/apps/marketing/" not in str(row.get("path", ""))
    ]
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
    repositories: list[dict[str, JsonValue]] = _survey_repositories(flow)
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
    survey: Path = flow.work / "survey.json"
    schema: dict[str, JsonValue] = read(flow.schemas / "survey.schema.json")
    context_sha: str = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()
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
        sealed: dict[str, JsonValue] = json_object(
            flow.call(
                "survey",
                archbaseline.survey_freshness,
                survey,
                archbaseline.FreshnessOptions(inputs=list(refs), seal=True, form="v2", context_sha=context_sha),
            ),
        )
        if sealed["current"]:
            break
        error_path: Path = flow.work / "survey.errors.json"
        write_json(error_path, sealed)
        inputs += (str(error_path),)
    else:
        raise flow.tools.failure(stage, "other", sealed)
    markdown: Path = flow.work / "survey.md"
    result: dict[str, JsonValue] = read(survey)
    markdown.write_text(
        f"# {result['subject']}\n\n{result.get('summary', '')}\n\n"
        + "\n".join(
            f"- {row['name']}"
            for row in check_type(
                result.get("capabilities", []),
                list[dict[str, JsonValue]],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            )
        )
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
        jsonschema.validate(read(path), read(flow.schemas / f"{schema}.schema.json"))
    except jsonschema.ValidationError:
        return
    flow.store.accept(
        f"architecture:{path.stem}",
        (*inputs, str(flow.context_path)),
        (path,),
        producer=producer,
    )
