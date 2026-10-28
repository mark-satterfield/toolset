"""The report of one elaboration dispatch, assembled from the Epic's step journal alone.

Nothing here reads what a step returned in memory: every field comes from an artifact a step
recorded, so the report is the same whichever dispatch ran the step.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypeIs

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import (
    PASSED_PHASE,
    SPEC_PHASE_PREFIX,
    TRD_PHASE,
    ArtifactReport,
    ToolingRecommendation,
)
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import stage_of
from orchestrator.core.models import RunContext
from orchestrator.flows.architecture_files import ARTIFACT_SPECIALIST_RECOMMENDATIONS, ARTIFACT_TRD, CONFIRM_TRD
from orchestrator.flows.elaboration_files import (
    ARTIFACT_CREATION,
    ARTIFACT_REPOSITORIES,
    EDGES_RESULT,
    LIFECYCLE_DONE,
    STORY,
    STORY_EDGES_RESULT,
    TASK,
)
from orchestrator.flows.elaboration_support import FINISH_PHASE

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import STATUS_DONE, Artifact, Journal, Step

if TYPE_CHECKING:
    from collections.abc import Iterator

type JsonObject = dict[str, JsonValue]


def _artifacts(journal: Journal, name: str) -> Iterator[Artifact]:
    """Yield every artifact of a journal that has one name, in walk order.

    Yields:
        Each artifact named ``name``.

    """
    step: Step
    for step in step_journal.steps_in_order(journal):
        yield from (held for held in step["artifacts"] if held["name"] == name)


def _values(journal: Journal, name: str) -> list[JsonValue]:
    """Read every value artifact of a journal that has one name.

    Returns:
        The values, in walk order.

    """
    return [held["value"] for held in _artifacts(journal, name) if held["kind"] == "value"]


def _is_tooling_recommendation(value: object) -> TypeIs[ToolingRecommendation]:
    """Tell whether a recorded value is a tooling recommendation.

    Returns:
        True when it is an object whose ``agent``, ``description`` and ``reason`` are text and
        that holds nothing else.

    """
    return (
        isinstance(value, dict)
        and set(value) == set(ToolingRecommendation.__required_keys__)
        and all(isinstance(value[key], str) and value[key] for key in value)
    )


def _recommendations(journal: Journal) -> list[ToolingRecommendation]:
    """Read the solutions architect's latest recommendations to create or update a specialist agent.

    Every architect step rewrites one result in place, so the last step's recommendations are all
    of them. A recorded value that is not a tooling recommendation is not one.

    Returns:
        The recommendations; empty when there are none.

    """
    recorded: list[JsonValue] = _values(journal, ARTIFACT_SPECIALIST_RECOMMENDATIONS)
    latest: JsonValue = recorded[-1] if recorded else []
    return [entry for entry in latest if _is_tooling_recommendation(entry)] if isinstance(latest, list) else []


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def journal_result(journal: Journal, context: RunContext) -> JsonObject:
    """Assemble what a dispatch reports from the Epic's journal alone.

    Args:
        journal: The Epic's journal as it stands.
        context: The run context, for the Epic, the work directory and the dispatch arguments.

    Returns:
        The repository span, the Stories and the Tasks written so far, the artifact report, the edges, whether the
        Epic's lifecycle is done, and the stage the journal stands at; under
        ``toolingRecommendations``, the solutions architect's latest recommendations to create or
        update a specialist agent, which ask nothing of a person.

    """
    dispatch: DispatchArguments = dispatch_arguments()
    stories: list[JsonValue] = _values(journal, STORY)
    tasks: list[JsonValue] = _values(journal, TASK)
    report: ArtifactReport = {"dir": str(context.work), "epicId": context.bead, "phases": {}, "filing": {}}
    if any(True for _ in _artifacts(journal, ARTIFACT_TRD) if _.get("kind") == "file"):
        confirmed: list[Step] = [
            step
            for step in step_journal.steps_in_order(journal)
            if step.get("script") == CONFIRM_TRD and step["status"] == STATUS_DONE
        ]
        if confirmed:
            report["phases"][TRD_PHASE] = PASSED_PHASE
            filing: JsonValue = context.args.get(dispatch.KEY_TRD_PATH)
            if isinstance(filing, str) and filing:
                report["filing"]["trd.md"] = filing
    for story in stories:
        slug: str = check_type(json_object(story).get("elabKey", ""), str).removeprefix("story:")
        if slug:
            report["phases"][SPEC_PHASE_PREFIX + slug] = PASSED_PHASE
    following: Step | None = step_journal.next_step(journal)
    result: JsonObject = json_object({
        "ok": following is None,
        "stage": FINISH_PHASE if following is None else stage_of(following),
        "repoSpan": next(iter(_values(journal, ARTIFACT_REPOSITORIES)), []),
        "createdRepos": [
            created
            for held in _artifacts(journal, ARTIFACT_CREATION)
            if held["kind"] == "file" and Path(held["path"]).is_file()
            for created in check_type(strict_json(Path(held["path"])).get("created", []), list[JsonValue])
        ],
        "hierarchy": {"epic": context.args.get(dispatch.KEY_EPIC, {}), "stories": stories, "tasks": tasks},
        "beadsEmitted": len(stories) + len(tasks),
        "lifecycleDone": any(value is True for value in _values(journal, LIFECYCLE_DONE)),
        "artifacts": report,
    })
    for edges in map(json_object, _values(journal, EDGES_RESULT)):
        result.update({key: edges[key] for key in ("closureEdges", "crossStoryDependencies") if key in edges})
    for written in _values(journal, STORY_EDGES_RESULT):
        result["storyEdges"] = written
    recommendations: list[ToolingRecommendation] = _recommendations(journal)
    if recommendations:
        result["toolingRecommendations"] = [json_object(dict(entry)) for entry in recommendations]
    return result
