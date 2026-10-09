"""Survey adoption proves the old seal before migrating its binding format."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema

from ..core.io import write_json
from .architecture_support import Architecture, read

SURVEY_FILES = (
    "survey.json",
    "survey.md",
    "survey.json.meta.json",
    "survey.md.meta.json",
    "survey.json.baseline-inputs.json",
    "survey.json.receipt",
)


def current_survey(flow: Architecture, *, adopt: bool = True) -> bool:
    survey = flow.work / "survey.json"
    seal = read(flow.work / "survey.json.baseline-inputs.json")
    form = seal.get("form")
    schema = read(flow.schemas / "survey.schema.json")
    context_sha = (
        hashlib.sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if form == "v2"
        else seal.get("contextSha")
    )
    freshness = flow.call(
        "archbaseline",
        "survey_freshness",
        survey,
        context_sha=context_sha,
        form=form,
        stage="survey",
    )
    if not freshness["current"] or not read(survey).get("subject"):
        return False
    try:
        jsonschema.validate(read(survey), schema)
    except jsonschema.ValidationError:
        return False
    if not form and adopt:
        flow.checked(
            flow.call(
                "archbaseline",
                "survey_freshness",
                survey,
                seal=True,
                form="adopted",
                context_sha=context_sha,
                stage="survey",
            ),
            "survey",
        )
        flow.adopted = True
    flow.runner.emit("note", kind="reused", step="architecture:survey")
    return True


def prepare_survey(flow: Architecture) -> None:
    # The survey's exact binding can remain current when a different cited round view changed.
    context_facts = read(flow.context_path)
    current = current_survey(flow, adopt=False)
    revision = flow.checked(
        flow.call(
            "archrevision", "check", str(flow.arch), str(flow.work), stage="survey"
        ),
        "survey",
    )
    if revision.get("status") == "stale" and current:
        moved = Path(revision["movedTo"])
        for name in SURVEY_FILES:
            source = moved / name
            if source.exists():
                source.rename(flow.work / name)
    flow.draft.mkdir(parents=True, exist_ok=True)
    write_json(flow.context_path, context_facts)
    if not current_survey(flow):
        produce_survey(flow)
    flow.subject = flow.subject or str(
        read(flow.work / "survey.json").get("subject") or flow.prd.stem
    )
    if flow.subject == flow.prd.stem:
        flow.forbid.remove(flow.prd.stem)
    result = flow.target(dry_run=True)
    if result.get("subjectRefusals"):
        raise flow.tools.failure("survey", "other", result)


def produce_survey(flow: Architecture, *, recheck: bool = False) -> None:
    inventory = flow.tools.polyrepo(["inventory", "--no-fetch"], stage="survey")
    value = json.loads(inventory.stdout)
    rows = (
        value
        if isinstance(value, list)
        else value.get("repositories", value.get("repos", []))
    )
    repositories = [
        {key: row.get(key) for key in ("name", "path", "role", "lifecycle")}
        for row in rows
        if row.get("lifecycle") != "archived"
        and "/apps/marketing/" not in str(row.get("path", ""))
    ]
    repo_file = flow.work / "repositories.json"
    write_json(repo_file, repositories)
    refs = (
        flow.prd,
        flow.arch / "reference/architecture-documentation-model.md",
        flow.arch / "reference/diagram-and-model-types.md",
        flow.arch / "arc42/02-architecture-constraints",
    )
    inputs = tuple(map(str, refs)) + (str(repo_file),)
    if recheck:
        inputs += (str(flow.ledger_input("recheck")),)
    survey = flow.work / "survey.json"
    schema = read(flow.schemas / "survey.schema.json")
    context_sha = hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    for attempt in range(2):
        flow.agent(
            "prd-reality-reconciler",
            survey,
            "survey",
            inputs,
            "Reassess the capabilities the open findings in the ledger concern."
            if recheck
            else "Write the survey of this PRD's capabilities.",
        )
        sealed = flow.call(
            "archbaseline",
            "survey_freshness",
            survey,
            inputs=list(refs),
            seal=True,
            form="v2",
            context_sha=context_sha,
            stage="survey",
        )
        if sealed["current"]:
            break
        error_path = flow.work / "survey.errors.json"
        write_json(error_path, sealed)
        inputs += (str(error_path),)
    else:
        raise flow.tools.failure("survey", "other", sealed)
    markdown = flow.work / "survey.md"
    result = read(survey)
    markdown.write_text(
        f"# {result['subject']}\n\n{result.get('summary', '')}\n\n"
        + "\n".join(f"- {row['name']}" for row in result.get("capabilities", []))
        + "\n",
        encoding="utf-8",
    )
    flow.store.accept("architecture:survey", inputs, (markdown,), producer="python")
    flow.facts()


def adopt_result(
    flow: Architecture, path: Path, inputs: tuple[str, ...], producer: str
) -> None:
    if not flow.adopted or not path.is_file():
        return
    meta = read(path.with_name(path.name + ".meta.json"))
    if meta.get("sha256") != flow.store.module.sha256_file(path) or not meta.get(
        "inputs"
    ):
        return
    if any(
        flow.store.module.input_problem(row, flow.store.root, path)
        for row in meta["inputs"]
    ):
        return
    schema = (
        "coordinator-plan"
        if producer == "architecture-decision-workflow-coordinator"
        else "architecture-writer"
    )
    try:
        jsonschema.validate(read(path), read(flow.schemas / f"{schema}.schema.json"))
    except jsonschema.ValidationError:
        return
    flow.store.accept(
        f"architecture:{path.stem}",
        inputs + (str(flow.context_path),),
        (path,),
        producer=producer,
    )
