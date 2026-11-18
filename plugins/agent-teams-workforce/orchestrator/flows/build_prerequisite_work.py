"""Append missing producer Tasks through the existing decomposer, writer and Task scoring.

Producer work that cannot be authored (no open producer Story, a Story whose specs or Tasks are not
found, or an authoring result that would change existing Tasks) is recorded as a
``producer-missing`` finding (``core.findings``) and the consumer's build continues against its
specified contract (:func:`continuation`); it never fails the Task.
"""

from __future__ import annotations

import json
from pathlib import Path

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
import beadgraph
import beadwrite
import hierarchy
import scoring
from bead_metadata import ELABORATION_DONE, KEY_ELAB_KEY, KEY_ELABORATION_STATE, KEY_REPO_PATH
from step_journal_contract import BeadId, Journal
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.findings import record_for_run
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, value_artifact
from orchestrator.flows.build_sessions import OutputContract, latest, reasoned
from orchestrator.flows.build_state import ARTIFACT_CONTRACTS, artifact_document, artifact_file, new_step
from orchestrator.flows.elaboration_files import CRITERIA, DATA_MODEL, SPEC, control_repository, project_root
from orchestrator.flows.repo_scoping import ELEMENTS_FILE, SPAN_FILE
from orchestrator.flows.spec_authoring import spec_context_path, spec_document_path, story_document_path
from orchestrator.flows.task_decomposition import task_context_path, tasks_path

ELABORATION_STAGE = "build:prerequisite-elaboration"
"""The gate that holds a consumer while its producer Story's Epic finishes elaboration."""
ELABORATION_WAIT = "prerequisiteElaborationWait"
"""The journal value naming the consumer, its diagnosis and the Epic and Story it waits for."""
BASELINE = "build:baseline"
"""The continuation that resumes the baseline setup."""
REQUIRED: tuple[str, ...] = (
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
"""The producer Story's files the decomposer and the writer are handed."""


def continuation(again: str) -> Completion:
    """Resume the consumer's verification where the prerequisite recovery began.

    Returns:
        The baseline setup again, or the original suite run and its assessment.

    """
    return Completion(
        add=(
            StepGroup((
                new_step(
                    BASELINE if again == BASELINE else "build:prerequisites-suite",
                    "Resume the baseline setup" if again == BASELINE else "Run and reassess the original suite",
                    {"again": again},
                ),
            )),
        ),
    )


def _missing(run: StepRun, owner: str, detail: str, *evidence: str) -> Completion:
    """Record producer work that cannot be authored as a finding, and continue the consumer's build.

    Returns:
        The continuation (:func:`continuation`).

    """
    record_for_run(run, owner, kind="producer-missing", detail=detail, evidence=evidence)
    return continuation(check_type(run.params()["again"], str))


def prepare(run: StepRun, diagnosis: dict[str, JsonValue]) -> Completion:
    """Locate real completed Story authoring inputs before assigning missing producer work.

    A producer Story whose Epic has not finished elaboration has no specs or Tasks yet; the
    consumer waits for that elaboration instead of failing. No open producer Story, a Story with
    no Epic, and a Story whose files are not found are recorded as ``producer-missing`` and the
    consumer's build continues (:func:`_missing`).

    Returns:
        A completed source-context record followed by the existing decomposer, the wait for the
        producer Story's Epic to finish elaboration, or the continuation of the consumer's build.

    """
    graph: beadgraph.Graph = run.tools.portfolio_read(run.step["script"], beadgraph.load, control_repository())
    consumer: beadgraph.Bead | None = graph.beads.get(str(run.bead))
    own_story: str = str(run.bead) if consumer is None or consumer.parent is None else consumer.parent
    evidence: str = check_type(diagnosis["evidence"], str)
    story: beadgraph.Bead | None = graph.beads.get(check_type(diagnosis.get("authoringStory") or "", str))
    if story is None or story.kind != "story" or story.closed:
        return _missing(run, own_story, "no open producer Story authorizes the missing producer work", evidence)
    epic: beadgraph.Bead | None = graph.epic_of(story.id)
    if epic is None:
        return _missing(run, story.id, f"producer Story {story.id} has no Epic", evidence)
    if epic.metadata.get(KEY_ELABORATION_STATE) != ELABORATION_DONE:
        return _await_elaboration(run, story, epic)
    found: dict[str, JsonValue] | str = _source(run.journal_path.parent, run.context.work.parent, story, epic)
    if isinstance(found, str):
        return _missing(run, story.id, found, evidence)
    context: dict[str, JsonValue] = found
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


def _await_elaboration(run: StepRun, story: beadgraph.Bead, epic: beadgraph.Bead) -> Completion:
    """Hold the consumer until the producer Story's Epic has written its specs and Tasks.

    Returns:
        The accepted wait and the gate that releases the build slot while the Epic elaborates.

    """
    fingerprint: str = check_type(run.params()["fingerprint"], str)
    wait: dict[str, JsonValue] = {
        "task": str(run.bead),
        "evidencePath": str(artifact_file(run, "prerequisiteDiagnosis")),
        "fingerprint": fingerprint,
        "producers": [],
        "elaboration": {"epic": epic.id, "story": story.id},
    }
    return Completion(
        artifacts=(value_artifact(ELABORATION_WAIT, wait), value_artifact("prerequisiteFingerprint", fingerprint)),
        add=(
            StepGroup((
                new_step(
                    ELABORATION_STAGE,
                    f"Wait for Epic {epic.id} to finish elaboration",
                    {"again": check_type(run.params()["again"], str)},
                ),
            )),
        ),
    )


def elaboration_pending(wait: dict[str, JsonValue], control: Path) -> bool:
    """Check, without a session, whether the awaited Epic has not finished its elaboration.

    Args:
        wait: The accepted elaboration wait.
        control: Central tracker repository.

    Returns:
        Whether the Epic is still not marked elaborated.

    """
    epic: str = check_type(json_object(wait["elaboration"])["epic"], str)
    graph: beadgraph.Graph = beadgraph.load(control)
    found: beadgraph.Bead | None = graph.beads.get(epic)
    return found is None or found.metadata.get(KEY_ELABORATION_STATE) != ELABORATION_DONE


def elaborated(run: StepRun) -> Completion:
    """Diagnose again against the Tasks the producer Story's finished elaboration wrote.

    Returns:
        A fresh diagnosis of the now-decomposed producer work within the correction allowance.

    """
    return Completion(
        add=(
            StepGroup((
                new_step(
                    "build:prerequisites-rediagnose",
                    "Diagnose the producer work the finished elaboration wrote",
                    {"again": check_type(run.params()["again"], str)},
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


def _on_disk(work: Path, slug: str) -> dict[str, str]:
    """Name the producer Story's files where its Epic's elaboration writes them.

    Returns:
        Each required file (:data:`REQUIRED`) by its artifact name.

    """
    paths: dict[str, Path] = {
        "span": work / SPAN_FILE,
        "elements": work / ELEMENTS_FILE,
        "spec": spec_document_path(work, slug, SPEC),
        "data model": spec_document_path(work, slug, DATA_MODEL),
        "criteria": spec_document_path(work, slug, CRITERIA),
        "story document": story_document_path(work, slug),
        "task context": task_context_path(work, slug),
        "repository context": spec_context_path(work, slug),
        "tasks": tasks_path(work, slug),
    }
    return {name: str(path) for name, path in paths.items()}


def _journal_files(directory: Path, story: beadgraph.Bead, epic: beadgraph.Bead) -> dict[str, str]:
    """Read the producer Story's file pointers from the done steps of its Story and Epic journals.

    Returns:
        Each file artifact the journals' done steps recorded; empty when a journal does not exist.

    """
    story_path: Path = step_journal.journal_path(directory, BeadId(story.id))
    epic_path: Path = step_journal.journal_path(directory, BeadId(epic.id))
    files: dict[str, str] = {}
    if epic_path.is_file():
        journal: Journal = step_journal.read_journal(epic_path)
        files.update(_done_files(journal))
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
    if story_path.is_file():
        files.update(_done_files(step_journal.read_journal(story_path)))
    return files


def _usable(path: str | None) -> bool:
    """Tell whether a recorded file pointer names a file that exists.

    Returns:
        True for an absolute path to an existing file.

    """
    return path is not None and Path(path).is_absolute() and Path(path).is_file()


def _source(
    directory: Path,
    artifacts: Path,
    story: beadgraph.Bead,
    epic: beadgraph.Bead,
) -> dict[str, JsonValue] | str:
    """Resolve the producer Story's authoring files: from done journal records, else from its Epic's work folder.

    A file the Story's and Epic's journals record in a done step is taken from there; a file they
    do not record is taken from the Epic's work directory, where the elaboration writes it.

    Returns:
        The source identity and its file pointers; or one line saying what is missing, when a
        file is found nowhere or the contexts name another Story.

    """
    slug: str = story.metadata.get(KEY_ELAB_KEY, "").removeprefix("story:")
    if not slug:
        return f"producer Story {story.id} has no elaboration key"
    recorded: dict[str, str] = _journal_files(directory, story, epic)
    disk: dict[str, str] = _on_disk(artifacts / epic.id, slug)
    files: dict[str, str] = {name: recorded[name] if _usable(recorded.get(name)) else disk[name] for name in REQUIRED}
    absent: list[str] = [name for name in REQUIRED if not _usable(files[name])]
    if absent:
        return f"producer Story {story.id} lacks its {', '.join(absent)} files"
    task_context: dict[str, JsonValue] = json_object(
        json.loads(Path(files["task context"]).read_text(encoding="utf-8")),
    )
    spec_context: dict[str, JsonValue] = json_object(
        json.loads(Path(files["repository context"]).read_text(encoding="utf-8")),
    )
    expected: dict[str, JsonValue] = {"slug": slug, "epic": epic.id, "repoPath": story.metadata.get(KEY_REPO_PATH)}
    if any(context.get(key) != value for context in (task_context, spec_context) for key, value in expected.items()):
        return f"producer Story {story.id} context identity does not match its files"
    return {
        "story": story.id,
        "epic": epic.id,
        "slug": slug,
        "repoPath": story.metadata[KEY_REPO_PATH],
        "files": {name: files[name] for name in REQUIRED},
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


def _new_keys(original: dict[str, JsonValue], candidate: dict[str, JsonValue]) -> set[str] | str:
    """Require exact retention before any append-only Task write.

    Returns:
        The newly authored local Task keys; or one line saying why nothing is written, when
        existing authored content changed or no new work was authorized.

    """
    old: dict[str, dict[str, JsonValue]] = {
        check_type(row["key"], str): row for row in check_type(original["tasks"], list[dict[str, JsonValue]])
    }
    new: dict[str, dict[str, JsonValue]] = {
        check_type(row["key"], str): row for row in check_type(candidate["tasks"], list[dict[str, JsonValue]])
    }
    keys: set[str] = set(new) - set(old)
    if not keys:
        return "producer authoring found no new work the Story's specs authorize"
    if any(new.get(key) != row for key, row in old.items()):
        return "producer authoring changed existing Tasks; nothing was written"
    prior_scores: list[JsonValue] = check_type(original.get("scores", []), list[JsonValue])
    scores: list[JsonValue] = check_type(candidate.get("scores", []), list[JsonValue])
    if any(score not in scores for score in prior_scores):
        return "producer authoring changed an existing Task's score; nothing was written"
    return keys


def authored(run: StepRun) -> Completion:
    """Persist new durable Task keys through normal idempotent writes and scoped scoring.

    An authoring result that adds nothing or changes existing Tasks is not written: it is recorded
    as ``producer-missing`` and the consumer's build continues. New Tasks that normal scoring
    cannot score are recorded the same way, and the diagnosis runs again.

    Returns:
        The real authored ids and a bounded new diagnosis of the changed tracker facts, or the
        continuation of the consumer's build.

    """
    context: dict[str, JsonValue] = json_object(latest(run, "prerequisiteAuthoring"))
    files: dict[str, JsonValue] = json_object(context["files"])
    original: dict[str, JsonValue] = json_object(
        json.loads(Path(check_type(files["tasks"], str)).read_text(encoding="utf-8")),
    )
    checked: set[str] | str = _new_keys(original, artifact_document(run, "prerequisiteTasks"))
    if isinstance(checked, str):
        return _missing(run, check_type(context["story"], str), checked, str(artifact_file(run, "prerequisiteTasks")))
    keys: set[str] = checked
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
        record_for_run(
            run,
            check_type(context["story"], str),
            kind="producer-missing",
            detail=f"new producer Tasks could not be normally scored: {json.dumps(scored)}",
            evidence=tuple(identities.values()),
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
