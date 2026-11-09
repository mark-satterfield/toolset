"""Append missing producer Tasks through the existing decomposer, writer and Task scoring."""

from __future__ import annotations

import json
from pathlib import Path

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
import beadgraph
import beadwrite
import hierarchy
import scoring
from bead_metadata import KEY_ELAB_KEY, KEY_REPO_PATH
from step_journal_contract import BeadId, Journal
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, value_artifact
from orchestrator.core.models import StepError
from orchestrator.flows.build_sessions import OutputContract, latest, reasoned
from orchestrator.flows.build_state import ARTIFACT_CONTRACTS, artifact_document, artifact_file, new_step
from orchestrator.flows.elaboration_files import control_repository, project_root


def prepare(run: StepRun, diagnosis: dict[str, JsonValue]) -> Completion:
    """Locate real completed Story authoring inputs before assigning missing producer work.

    Returns:
        A completed source-context record followed by the existing decomposer.

    Raises:
        StepError: No actual open Story with complete accepted authoring artifacts exists.

    """
    graph: beadgraph.Graph = run.tools.portfolio_read(run.step["script"], beadgraph.load, control_repository())
    story: beadgraph.Bead | None = graph.beads.get(check_type(diagnosis.get("authoringStory") or "", str))
    if story is None or story.kind != "story" or story.closed:
        raise StepError(
            run.step["script"],
            OTHER_CAUSE,
            (
                "Producer work-authoring gap: no actual open Story with saved scope/spec context was established",
                check_type(diagnosis["evidence"], str),
            ),
        )
    epic: beadgraph.Bead | None = graph.epic_of(story.id)
    if epic is None:
        raise StepError(run.step["script"], OTHER_CAUSE, (f"Producer Story {story.id} has no actual Epic",))
    context: dict[str, JsonValue] = _source(run.journal_path.parent, story, epic)
    return Completion(
        artifacts=(
            value_artifact("prerequisiteAuthoring", context),
            value_artifact("prerequisiteFingerprint", check_type(run.params()["fingerprint"], str)),
        ),
        add=(
            StepGroup((
                new_step(
                    "build:prerequisite-author",
                    "Author the missing real producer work",
                    {
                        "again": check_type(run.params()["again"], str),
                    },
                ),
            )),
        ),
    )


def _done_files(journal: Journal) -> dict[str, str]:
    """Read accepted file pointers without changing their original journal.

    Returns:
        The latest completed file artifact for each exact artifact name.

    """
    return {
        artifact["name"]: artifact["path"]
        for step in step_journal.steps_in_order(journal)
        if step["status"] == "done"
        for artifact in step["artifacts"]
        if artifact["kind"] == "file"
    }


def _source(directory: Path, story: beadgraph.Bead, epic: beadgraph.Bead) -> dict[str, JsonValue]:
    """Resolve authoring pointers only from completed actual Story and Epic journal records.

    Returns:
        The source identity and immutable accepted artifact pointers.

    Raises:
        StepError: A required actual context artifact is absent or incomplete.

    """
    story_path: Path = step_journal.journal_path(directory, BeadId(story.id))
    epic_path: Path = step_journal.journal_path(directory, BeadId(epic.id))
    stage: str = "build:prerequisite-author"
    if not story_path.is_file() or not epic_path.is_file():
        raise StepError(stage, OTHER_CAUSE, (f"Producer Story {story.id} has no saved authoring journals",))
    journal: Journal = step_journal.read_journal(epic_path)
    files: dict[str, str] = _done_files(journal)
    for step in step_journal.steps_in_order(journal):
        matches: bool = any(
            artifact["name"] == "repository"
            and artifact["kind"] == "value"
            and isinstance(artifact["value"], dict)
            and artifact["value"].get("repoPath") == story.metadata.get(KEY_REPO_PATH)
            for artifact in step["artifacts"]
        )
        if step["status"] == "done" and matches:
            for descendant in step_journal.steps_in_order({**journal, "steps": [step]}):
                if descendant["status"] == "done":
                    files.update({
                        artifact["name"]: artifact["path"]
                        for artifact in descendant["artifacts"]
                        if artifact["kind"] == "file"
                        and artifact["name"] in {"task context", "repository context", "tasks"}
                    })
    files.update(_done_files(step_journal.read_journal(story_path)))
    required: tuple[str, ...] = (
        "span",
        "elements",
        "spec",
        "data model",
        "criteria",
        "story document",
        "task context",
        "repository context",
        "tasks",
    )
    if any(
        name not in files or not Path(files[name]).is_absolute() or not Path(files[name]).is_file() for name in required
    ):
        raise StepError(
            stage,
            OTHER_CAUSE,
            (f"Producer Story {story.id} lacks complete accepted scope/spec/Task artifacts",),
        )
    slug: str = story.metadata.get(KEY_ELAB_KEY, "").removeprefix("story:")
    task_context: dict[str, JsonValue] = json_object(
        json.loads(Path(files["task context"]).read_text(encoding="utf-8")),
    )
    spec_context: dict[str, JsonValue] = json_object(
        json.loads(Path(files["repository context"]).read_text(encoding="utf-8")),
    )
    expected: dict[str, JsonValue] = {"slug": slug, "epic": epic.id, "repoPath": story.metadata.get(KEY_REPO_PATH)}
    if not slug or any(
        context.get(key) != value for context in (task_context, spec_context) for key, value in expected.items()
    ):
        raise StepError(stage, OTHER_CAUSE, (f"Producer Story {story.id} context identity does not match",))
    return {
        "story": story.id,
        "epic": epic.id,
        "slug": slug,
        "repoPath": story.metadata[KEY_REPO_PATH],
        "files": {name: files[name] for name in required},
    }


def author(run: StepRun) -> Completion:
    """Use the existing task decomposer with validated real Story/spec context.

    Returns:
        A bounded append-only authoring session and deterministic writer step.

    """
    context: JsonValue = latest(run, "prerequisiteAuthoring")
    return reasoned(
        run,
        "task-decomposer",
        OutputContract(ARTIFACT_CONTRACTS / "tasks.schema.json", "prerequisiteTasks"),
        f"Append only missing producer Tasks within this verified Story/spec scope: {json.dumps(context)}. "
        "Retain every original Task and score object exactly; add only missing work the existing spec authorizes. "
        "Never change a requirement, author a spec, choose a parent, edit existing Tasks, write beads or deploy. "
        "Use the supplied original task context, repository context, scope, specs and original Tasks file. "
        "If no new work is authorized, return the original document unchanged and explain the gap in notes.",
        followups=(
            new_step(
                "build:prerequisite-authored",
                "Write and score only the new producer Tasks",
                {
                    "again": check_type(run.params()["again"], str),
                },
            ),
        ),
    )


def _story_files(context: dict[str, JsonValue], tasks: Path) -> hierarchy.StoryFiles:
    """Build the existing writer's exact source-file contract.

    Returns:
        The real Story's accepted scope and specs with the new append-only Tasks document.

    """
    files: dict[str, JsonValue] = json_object(context["files"])
    return hierarchy.StoryFiles(
        slug=check_type(context["slug"], str),
        repo=check_type(context["repoPath"], str),
        scope=hierarchy.SpanFiles(Path(check_type(files["span"], str)), Path(check_type(files["elements"], str))),
        story=Path(check_type(files["story document"], str)),
        specs=tuple(Path(check_type(files[name], str)) for name in ("spec", "data model", "criteria")),
        tasks=tasks,
    )


def _new_keys(original: dict[str, JsonValue], candidate: dict[str, JsonValue], stage: str) -> set[str]:
    """Require exact retention before any append-only Task write.

    Returns:
        The newly authored local Task keys.

    Raises:
        StepError: Existing authored content changed, or no real new work was authorized.

    """
    old: dict[str, dict[str, JsonValue]] = {
        check_type(row["key"], str): row for row in check_type(original["tasks"], list[dict[str, JsonValue]])
    }
    new: dict[str, dict[str, JsonValue]] = {
        check_type(row["key"], str): row for row in check_type(candidate["tasks"], list[dict[str, JsonValue]])
    }
    keys: set[str] = set(new) - set(old)
    if not keys or any(new.get(key) != row for key, row in old.items()):
        raise StepError(
            stage,
            OTHER_CAUSE,
            ("Producer authoring must preserve existing Tasks and add real authorized work",),
        )
    prior_scores: list[JsonValue] = check_type(original.get("scores", []), list[JsonValue])
    scores: list[JsonValue] = check_type(candidate.get("scores", []), list[JsonValue])
    if any(score not in scores for score in prior_scores):
        raise StepError(stage, OTHER_CAUSE, ("Producer authoring changed an existing Task's score",))
    return keys


def authored(run: StepRun) -> Completion:
    """Persist new durable Task keys through normal idempotent writes and scoped scoring.

    Returns:
        The real authored ids and a bounded new diagnosis of the changed tracker facts.

    Raises:
        StepError: Normal scoring cannot make the new Tasks eligible.

    """
    context: dict[str, JsonValue] = json_object(latest(run, "prerequisiteAuthoring"))
    files: dict[str, JsonValue] = json_object(context["files"])
    original: dict[str, JsonValue] = json_object(
        json.loads(Path(check_type(files["tasks"], str)).read_text(encoding="utf-8")),
    )
    keys: set[str] = _new_keys(original, artifact_document(run, "prerequisiteTasks"), run.step["script"])
    story_files: hierarchy.StoryFiles = _story_files(context, artifact_file(run, "prerequisiteTasks"))
    planned: list[hierarchy.Task] = run.tools.portfolio(
        run.step["script"],
        beadwrite.plan_tasks,
        story_files,
        project_root(),
    )
    writer: beadgraph.Writer = beadgraph.Writer(control_repository())
    identities: dict[str, str] = {}
    for task in planned:
        if task.key in keys:
            written = run.tools.portfolio(
                run.step["script"],
                beadwrite.write_task,
                writer,
                check_type(context["epic"], str),
                story_files,
                key=task.key,
                root=project_root(),
                append_only=True,
            )
            identities[task.key] = check_type(written["task"]["id"], str)
    graph: beadgraph.Graph = run.tools.portfolio_read(run.step["script"], beadgraph.load, control_repository())
    by_key: dict[str, str] = {
        task.key: bead.id
        for task in planned
        for bead in graph.of_kind("task")
        if bead.parent == context["story"] and bead.metadata.get(KEY_ELAB_KEY) == task.elab_key
    }
    additions: dict[str, list[str]] = {
        identities[task.key]: [by_key[key] for key in task.depends_on] + task.blocked_by_external
        for task in planned
        if task.key in identities
    }
    run.tools.portfolio(run.step["script"], writer.write_blocks, additions)
    refreshed: beadgraph.Graph = run.tools.portfolio_read(run.step["script"], beadgraph.load, control_repository())
    scored = run.tools.portfolio(run.step["script"], scoring.score_tasks, refreshed, writer, set(identities.values()))
    if scored["unscored"] or scored["sizeFaults"]:
        raise StepError(
            run.step["script"],
            OTHER_CAUSE,
            (f"New producer Tasks could not be normally scored: {scored}",),
        )
    return Completion(
        artifacts=(
            value_artifact("prerequisiteWork", json_object({"tasks": list(identities.values()), "scoring": scored})),
        ),
        add=(
            StepGroup((
                new_step(
                    "build:prerequisites-rediagnose",
                    "Diagnose the actual newly authored producer work",
                    {
                        "again": check_type(run.params()["again"], str),
                    },
                ),
            )),
        ),
    )
