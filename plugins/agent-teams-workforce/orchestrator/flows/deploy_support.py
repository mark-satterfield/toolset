"""Validated Story leaf inputs, scoped journals and direct deterministic commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

import strictschema
from step_journal_contract import StepId
from typeguard import check_type

from orchestrator.core import pipeline_steps, step_journal
from orchestrator.core.agents import AgentRunner
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_run import JournalRunner
from orchestrator.core.journal_steps import NewStep
from orchestrator.core.models import RunContext, StepError
from orchestrator.core.tools import Tools
from orchestrator.flows.build_sessions import attach

if TYPE_CHECKING:
    from orchestrator.core.journal_registry import Registry

PLUGIN: Final = Path(__file__).resolve().parents[2]
SCHEMAS: Final = PLUGIN / "skills" / "artifact-handoff" / "schemas"


def arguments(context: RunContext, definition: str) -> dict[str, JsonValue]:
    """Validate declared leaf arguments, excluding host execution metadata.

    Returns:
        The arguments admitted by the shared Story deploy contract.

    """
    schema_path = SCHEMAS / "story-deploy-args.schema.json"
    schema = json_object(json.loads(schema_path.read_text(encoding="utf-8")))
    definitions = json_object(schema["$defs"])
    properties = json_object(json_object(definitions[definition])["properties"])
    selected = {key: value for key, value in context.args.items() if key in properties}
    strictschema.validate(selected, {"$defs": definitions, "$ref": f"#/$defs/{definition}"}, location=schema_path)
    return selected


def command(tools: Tools, stage: str, argv: list[str]) -> dict[str, JsonValue]:
    """Run a deterministic command once through the shared retry and evidence boundary.

    Returns:
        Its validated object result.

    Raises:
        StepError: The process fails.

    """
    done = tools.command(argv, stage=stage)
    document = json_object(json.loads(done.stdout))
    if document.get("error"):
        raise StepError(stage, OTHER_CAUSE, (str(document["error"]),))
    return document


def depscore(tools: Tools, stage: str, args: dict[str, JsonValue], tail: list[str]) -> dict[str, JsonValue]:
    """Call the declared portfolio CLI directly without a model relay.

    Returns:
        The checked command result.

    """
    reference = json_object(args["depscore"])
    return command(
        tools,
        stage,
        [sys.executable, check_type(reference["script"], str), "-C", check_type(reference["repo"], str), *tail],
    )


def addition(kind: str, params: dict[str, JsonValue] | None = None) -> NewStep:
    """Build one deploy step from its canonical definition.

    Returns:
        The step with its runtime parameters.

    """
    return NewStep(pipeline_steps.step_plan("deploy", kind, params), params or {})


def execute(context: RunContext, args: dict[str, JsonValue], kind: str, registry: Registry) -> JournalRunner:
    """Run only the children of the Story step the driver dispatched.

    Returns:
        Its runner after all child steps succeed.

    Raises:
        ValueError: The driver references another bead or step kind.

    """
    reference = json_object(args["journal"])
    path = Path(check_type(reference["path"], str))
    identifier = StepId(check_type(reference["step"], str))
    journal = step_journal.read_journal(path)
    parent = step_journal.find_step(journal, identifier)
    if journal["bead"] != context.bead or parent.get("script") != kind:
        msg = "deploy leaf journal does not match its Story and parent step"
        raise ValueError(msg)
    if not parent["steps"]:
        step_journal.update_journal(
            path,
            lambda held: step_journal.add_steps(
                held,
                pipeline_steps.inner_plans("deploy", kind),
                step_journal.timestamp(),
                parent=identifier,
            ),
        )
    attach(registry, PLUGIN)
    runner = JournalRunner(path, AgentRunner(context), Tools(context.work / "evidence"), registry)
    runner.run_within(identifier)
    return runner


def recorded(runner: JournalRunner, names: tuple[str, ...]) -> dict[str, JsonValue]:
    """Read the latest accepted artifacts from this leaf's container.

    Returns:
        Named values and file paths, omitted when no accepted step recorded them.

    """
    journal = step_journal.read_journal(runner.path)
    reference = json_object(runner.context.args["journal"])
    parent = step_journal.find_step(journal, StepId(check_type(reference["step"], str)))
    result: dict[str, JsonValue] = {}
    for step in step_journal.steps_in_order_from(parent):
        if step["status"] == "done":
            result.update({
                artifact["name"]: artifact.get("value") if artifact["kind"] == "value" else artifact["path"]
                for artifact in step["artifacts"]
                if artifact["name"] in names
            })
    return result


def handback(context: RunContext, stage: str, headline: str, **fields: JsonValue) -> dict[str, JsonValue]:
    """Build a successful leaf handback in the driver's existing shape.

    Returns:
        The Story result and any leaf-specific fields.

    """
    return {"ok": True, "stage": stage, "beadId": context.bead, "headline": headline, "detailPath": None, **fields}
