"""Survey adoption proves the old seal before migrating its binding format."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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

    """
    survey = flow.work / "survey.json"
    seal = read(flow.work / "survey.json.baseline-inputs.json")
    form = seal.get("form")
    schema = read(flow.schemas / "survey.schema.json")
    schema_sha = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()
    context_sha = schema_sha if form in {"v2", "adopted"} else seal.get("contextSha")
    freshness = json_object(
        flow.call(
            "archbaseline",
            "survey_freshness",
            survey,
            context_sha=context_sha,
            form=form,
            stage="survey",
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
                    "archbaseline",
                    "survey_freshness",
                    survey,
                    seal=True,
                    form="adopted",
                    context_sha=schema_sha,
                    stage="survey",
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
    """Prepare a current survey and validate its target subject."""
    context_facts = read(flow.context_path)
    current = current_survey(flow, adopt=False)
    revision = flow.checked(
        json_object(
            flow.call(
                "archrevision",
                "check",
                str(flow.arch),
                str(flow.work),
                stage="survey",
            ),
        ),
        "survey",
    )
    if revision.get("status") == "stale" and current:
        moved = Path(check_type(revision["movedTo"], str))
        for name in SURVEY_FILES:
            source = moved / name
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
    result = flow.target(dry_run=True)
    stage = "survey"
    if result.get("subjectRefusals"):
        raise flow.tools.failure(stage, "other", result)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def produce_survey(flow: Architecture, *, recheck: bool = False) -> None:
    """Produce and seal the survey against repository and architecture inputs."""
    stage = "survey"
    inventory = flow.tools.polyrepo(["inventory", "--no-fetch"], stage="survey")
    value: object = json.loads(inventory.stdout)
    rows = (
        value
        if isinstance(value, list)
        else json_object(value).get("repositories", json_object(value).get("repos", []))
    )
    repositories = [
        {key: row.get(key) for key in ("name", "path", "role", "lifecycle")}
        for row in check_type(
            rows,
            list[dict[str, JsonValue]],
            collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
        )
        if row.get("lifecycle") != "archived" and "/apps/marketing/" not in str(row.get("path", ""))
    ]
    repo_file = flow.work / "repositories.json"
    write_json(repo_file, repositories)
    refs = (
        flow.prd,
        flow.arch / "reference/architecture-documentation-model.md",
        flow.arch / "reference/diagram-and-model-types.md",
        flow.arch / "arc42/02-architecture-constraints",
    )
    inputs = (*map(str, refs), str(repo_file))
    if recheck:
        inputs += (str(flow.ledger_input("recheck")),)
    survey = flow.work / "survey.json"
    schema = read(flow.schemas / "survey.schema.json")
    context_sha = hashlib.sha256(
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
        sealed = json_object(
            flow.call(
                "archbaseline",
                "survey_freshness",
                survey,
                inputs=list(refs),
                seal=True,
                form="v2",
                context_sha=context_sha,
                stage="survey",
            ),
        )
        if sealed["current"]:
            break
        error_path = flow.work / "survey.errors.json"
        write_json(error_path, sealed)
        inputs += (str(error_path),)
    else:
        raise flow.tools.failure(stage, "other", sealed)
    markdown = flow.work / "survey.md"
    result = read(survey)
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
    """Adopt a valid prior artifact only when its recorded inputs still match."""
    if not flow.adopted or not path.is_file():
        return
    meta = read(path.with_name(path.name + ".meta.json"))
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
    schema = "coordinator-plan" if producer == "architecture-decision-workflow-coordinator" else "architecture-writer"
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
