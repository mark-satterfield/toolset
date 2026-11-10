"""Diagnose real producer work and release a consumer while its prerequisites progress."""

from __future__ import annotations

import hashlib
import json
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Literal

from orchestrator.core import portfolio_bootstrap  # ruff: ignore[unused-import] - Install shared contract paths.

# isort: split
import beadgraph
import beads_contract
from bead_metadata import KEY_REPO_PATH
from matrixstore import Matrix, as_entry_id
from step_journal_contract import BeadId
from story_deploy_args import VERIFIED_STATUSES
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE, WaitingProducer
from orchestrator.core.io import JsonValue, write_json
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, value_artifact
from orchestrator.core.models import StepError
from orchestrator.core.tool_locks import control_repo
from orchestrator.flows import build_prerequisite_work
from orchestrator.flows.build_sessions import OutputContract, latest, reasoned
from orchestrator.flows.build_state import (
    CONTRACTS,
    artifact_document,
    artifact_file,
    build_rounds,
    new_step,
    workspace_of,
)
from orchestrator.flows.build_workspace import git_operation


def _completed_facts(path: Path) -> dict[str, JsonValue]:
    """Read facts only from a completed and closed producer Story journal.

    Args:
        path: Canonical producer journal.

    Returns:
        Recorded facts, or an empty mapping while completion is unproven.

    """
    if not path.is_file():
        return {}
    steps = list(step_journal.steps_in_order(step_journal.read_journal(path)))
    if not steps or any(step["status"] != "done" for step in steps):
        return {}
    facts: dict[str, JsonValue] = {
        artifact["name"]: artifact["value"]
        for step in steps
        for artifact in step["artifacts"]
        if artifact["kind"] == "value"
    }
    return facts if facts.get("closed") is True else {}


class StorySnapshot:
    """Completed producer Story facts, each journal read at most once within one query.

    A snapshot belongs to one diagnosis, readiness check or candidate listing and is dropped
    with it, so a later query always rereads the journals and sees new publication or
    deployment receipts.
    """

    def __init__(self, directory: Path) -> None:
        """Bind the canonical journal directory.

        Args:
            directory: Canonical journals directory.

        """
        self._directory: Path = directory
        self._facts: dict[str, dict[str, JsonValue]] = {}

    def facts(self, story: str) -> dict[str, JsonValue]:
        """Read one Story's completed facts, reusing an earlier read in this query.

        Args:
            story: The producer Story's bead id.

        Returns:
            Its completed and closed facts, or an empty mapping while completion is unproven.

        """
        if story not in self._facts:
            self._facts[story] = _completed_facts(_journal(self._directory, story))
        return self._facts[story]


def _deployment_in(facts: dict[str, JsonValue]) -> bool:
    """Require actual verified stacks in completed Story facts.

    Returns:
        Whether the facts record nonempty successfully verified stacks.

    """
    stacks: JsonValue = facts.get("stacks")
    return (
        isinstance(stacks, list)
        and bool(stacks)
        and all(isinstance(stack, dict) and stack.get("status") in VERIFIED_STATUSES for stack in stacks)
    )


def _publication_in(facts: dict[str, JsonValue]) -> bool:
    """Require a package availability receipt for the exact published commit.

    Returns:
        Whether the facts hold a complete CodeArtifact availability receipt for ``publishedHead``.

    """
    receipt: JsonValue = facts.get("packagePublication")
    if not isinstance(receipt, dict) or receipt.get("available") is not True:
        return False
    fields: tuple[str, ...] = ("checkedCommit", "package", "version", "domain", "domainOwner", "repository")
    if not all(isinstance(receipt.get(key), str) and bool(receipt.get(key)) for key in fields):
        return False
    return receipt.get("checkedCommit") == facts.get("publishedHead")


def _delivered_in(facts: dict[str, JsonValue], stage: Literal["built", "published", "deployed"]) -> bool:
    """Select the exact delivery evidence a stage requires from completed Story facts.

    Returns:
        Whether the requested delivery stage has evidence; built is checked by the Task reader.

    Raises:
        ValueError: If the stage is outside the shared contract.

    """
    if stage == "built":
        return True
    if stage == "published":
        return _publication_in(facts)
    if stage == "deployed":
        return _deployment_in(facts)
    message: str = f"Unknown prerequisite stage: {stage}"
    raise ValueError(message)


def deployment_verified(path: Path) -> bool:
    """Require actual verified stacks, independently of package publication.

    Args:
        path: Canonical producer journal.

    Returns:
        Whether completed delivery records nonempty successfully verified stacks.

    """
    return _deployment_in(_completed_facts(path))


def publication_verified(path: Path) -> bool:
    """Require an explicit observation that the committed package version is available.

    Args:
        path: Canonical producer journal.

    Returns:
        Whether the completed Story recorded a matching CodeArtifact availability receipt.

    """
    return _publication_in(_completed_facts(path))


def delivery_verified(path: Path, stage: Literal["built", "published", "deployed"]) -> bool:
    """Select the exact producer evidence required by a consumer.

    Args:
        path: Canonical producer journal.
        stage: Declared dependency stage; built is checked by the Task reader.

    Returns:
        Whether the requested delivery stage has evidence.

    """
    if stage == "built":
        return True
    return _delivered_in(_completed_facts(path), stage)


def _delivered(producer: dict[str, JsonValue], snapshot: StorySnapshot) -> bool:
    """Select delivery evidence for one validated producer row.

    Args:
        producer: Declared producer.
        snapshot: This query's Story facts.

    Returns:
        Whether its delivery stage is evidenced.

    """
    stage = check_type(producer["requiredStage"], Literal["built", "published", "deployed"])
    if stage == "built":
        return True
    return _delivered_in(snapshot.facts(check_type(producer["story"], str)), stage)


def prerequisites_for_record(record: object) -> list[dict[str, JsonValue]]:
    """Read structured stages through the canonical metadata projection.

    Args:
        record: A current real Task record.

    Returns:
        Valid producer rows, or none for older Tasks without stage metadata.

    """
    row: dict[str, JsonValue] = check_type(record, dict[str, JsonValue])
    declared = beads_contract.read_contract(row).get("buildPrerequisites")
    if not declared:
        return []
    producers: list[dict[str, JsonValue]] = check_type(declared.get("producers", []), list[dict[str, JsonValue]])
    _producer_rows(producers)
    return producers


def _producer_rows(producers: list[dict[str, JsonValue]]) -> None:
    """Validate producer stage fields and durable evidence references.

    Raises:
        ValueError: A producer lacks a valid absolute existing evidence artifact.

    """
    check_type(producers, list[WaitingProducer])
    for producer in producers:
        evidence: Path = Path(check_type(producer["evidence"], str))
        if not evidence.is_absolute() or not evidence.is_file():
            message: str = f"Producer {producer['task']} has no absolute existing evidence artifact: {evidence}"
            raise ValueError(message)


class WaitCycleError(ValueError):
    """Pending waits and actual Task blockers form a completion cycle no scheduling can satisfy."""

    def __init__(self, cycle: tuple[str, ...]) -> None:
        """Keep the cycle's bead ids, first id repeated last, as the error's evidence."""
        super().__init__(f"Unschedulable prerequisite Task/Story completion cycle: {' -> '.join(cycle)}")
        self.cycle = cycle


def validate_wait_graph(records: object, waits: object, scheduling: object = None) -> None:
    """Reject Task/Story completion cycles from a current snapshot and pending waits.

    Args:
        records: Current normalized tracker records.
        waits: Canonically validated pending waits, including the proposed wait.
        scheduling: Optional actual host Task-to-blocking-Story scheduling edges.

    Raises:
        WaitCycleError: Actual Task blockers and required Story deployment stages form a cycle.
        ValueError: A wait names no existing evidence or a scheduling edge is not Task to Story.

    """
    rows: list[dict[str, JsonValue]] = check_type(records, list[dict[str, JsonValue]])
    pending_waits: list[dict[str, JsonValue]] = check_type(waits, list[dict[str, JsonValue]])
    beads: dict[str, beadgraph.Bead] = {str(row["id"]): beadgraph.bead_of(row) for row in rows}
    graph: beadgraph.Graph = beadgraph.Graph(beads, "prerequisite-snapshot", rows)
    edges: dict[str, set[str]] = {}
    for task in graph.of_kind("task"):
        if task.closed:
            continue
        edges[task.id] = {blocker for blocker in task.blockers if blocker in beads and not beads[blocker].closed}
        if task.parent is not None:
            edges.setdefault(task.parent, set()).add(task.id)
    for wait in pending_waits:
        _add_wait_edges(graph, edges, wait)
    for task_id, story_id in check_type(scheduling or {}, dict[str, str]).items():
        if (
            task_id not in beads
            or story_id not in beads
            or beads[task_id].kind != "task"
            or beads[story_id].kind != "story"
        ):
            message: str = f"Invalid actual scheduling relationship: {task_id} -> {story_id}"
            raise ValueError(message)
        edges.setdefault(task_id, set()).add(story_id)
    try:
        TopologicalSorter(edges).prepare()
    except CycleError as error:
        raise WaitCycleError(tuple(str(node) for node in error.args[1])) from error


def _add_wait_edges(graph: beadgraph.Graph, edges: dict[str, set[str]], wait: dict[str, JsonValue]) -> None:
    """Validate one pending real consumer before adding its delivery-stage edges.

    Raises:
        StepError: A closed producer cannot complete missing historical delivery evidence.

    """
    consumer: str = check_type(wait["task"], str)
    if consumer in graph.beads and graph.beads[consumer].closed:
        return
    producers: list[dict[str, JsonValue]] = check_type(wait["producers"], list[dict[str, JsonValue]])
    _producer_rows(producers)
    _validate_producers(graph, consumer, producers)
    for producer in producers:
        story: beadgraph.Bead = graph.beads[check_type(producer["story"], str)]
        if producer["requiredStage"] != "built" and story.closed:
            stage: str = "build:prerequisites-diagnosed"
            message: str = (
                f"Closed producer Story {story.id} has no verified delivery evidence; "
                "history cannot be republished or redeployed as pending work"
            )
            raise StepError(stage, OTHER_CAUSE, (message,))
        _validate_repository_ownership(graph, graph.beads[consumer], story)
    edges.setdefault(consumer, set()).update(
        check_type(producer["story"] if producer["requiredStage"] != "built" else producer["task"], str)
        for producer in producers
    )


def _active_waits(graph: beadgraph.Graph, directory: Path, snapshot: StorySnapshot) -> list[JsonValue]:
    """Read pending journal waits, excluding completed producer stages and historical waits.

    Args:
        graph: A current tracker snapshot.
        directory: Canonical journals directory.
        snapshot: This diagnosis's producer Story facts.

    Returns:
        The currently unresolved structured waits from real open consumer Tasks.

    """
    waits: list[JsonValue] = []
    for task in graph.of_kind("task"):
        path: Path = _journal(directory, task.id)
        if task.closed or not path.is_file():
            continue
        journal = step_journal.read_journal(path)
        next_step = step_journal.next_step(journal)
        if next_step is None or next_step.get("script") != "build:prerequisites-ready":
            continue
        saved: list[JsonValue] = [
            artifact["value"]
            for step in step_journal.steps_in_order(journal)
            if step["status"] == "done"
            for artifact in step["artifacts"]
            if artifact["kind"] == "value" and artifact["name"] == "prerequisiteWait"
        ]
        if saved:
            wait: dict[str, JsonValue] = check_type(saved[-1], dict[str, JsonValue])
            waits.append(_unresolved_wait(graph, snapshot, wait))
    return [wait for wait in waits if isinstance(wait, dict) and wait["producers"]]


def _unresolved_wait(
    graph: beadgraph.Graph,
    snapshot: StorySnapshot,
    wait: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Retain only producer stages that current facts have not established.

    Returns:
        A copy of the accepted wait with currently unresolved producer rows.

    """
    producers: list[dict[str, JsonValue]] = check_type(wait["producers"], list[dict[str, JsonValue]])
    _validate_producers(graph, check_type(wait["task"], str), producers)
    return {
        **wait,
        "producers": [
            producer
            for producer in producers
            if (
                not graph.beads[check_type(producer["task"], str)].closed
                or (producer["requiredStage"] != "built" and not _delivered(producer, snapshot))
            )
        ],
    }


def producer_candidates(
    graph: beadgraph.Graph,
    matrix: Matrix,
    stacks: set[str],
    journals: Path,
    exclude: str,
) -> list[JsonValue]:
    """Keep real Tasks, including closed Tasks whose producer Story has not delivered its output.

    Args:
        graph: A current tracker snapshot.
        matrix: Current matrix relationships.
        stacks: The supplied own and upstream stack ids.
        journals: Canonical journal directory.
        exclude: The consumer Task to leave out, or an empty string.

    Returns:
        Matching Tasks with their actual parent Story and distinct delivery evidence.

    """
    candidates: list[JsonValue] = []
    snapshot: StorySnapshot = StorySnapshot(journals)
    for record in graph.records:
        bead: beadgraph.Bead = beadgraph.bead_of(record)
        if bead.kind != "task" or bead.id == exclude:
            continue
        elements: list[str] = list(beads_contract.read_contract(record).get("matrix_elements", []))
        if not any(_in_stacks(matrix, element, stacks) for element in elements):
            continue
        story: beadgraph.Bead | None = next((held for held in graph.ancestors(bead.id) if held.kind == "story"), None)
        facts: dict[str, JsonValue] = {} if story is None else snapshot.facts(story.id)
        candidates.append({
            "task": bead.id,
            "title": bead.title,
            "status": bead.status,
            "elements": list(elements),
            "story": None if story is None else story.id,
            "storyStatus": None if story is None else story.status,
            "publicationVerified": story is not None and _publication_in(facts),
            "deploymentVerified": story is not None and _deployment_in(facts),
        })
    return candidates


def _in_stacks(matrix: Matrix, element: str, stacks: set[str]) -> bool:
    """Tell whether a stated entry is in one of the supplied stacks.

    Returns:
        Whether this entry or its containing stack was supplied.

    """
    entry = matrix.find(as_entry_id(element))
    return entry is not None and (element in stacks or matrix.home(entry.id, side=None) in stacks)


def _journal(directory: Path, bead: str) -> Path:
    """Use the canonical journal naming contract for a producer.

    Returns:
        The producer's canonical journal path.

    """
    return step_journal.journal_path(directory, BeadId(bead))


def _failure_observation(run: StepRun, again: str) -> dict[str, JsonValue]:
    """Read the accepted failure belonging to the continuation's actual phase.

    Returns:
        A setup failure payload or an accepted independent suite judgment.

    """
    if again == "build:baseline":
        return check_type(latest(run, "setupFailure"), dict[str, JsonValue])
    return artifact_document(run, "suiteReview")


def diagnose(run: StepRun, again: str, observation: dict[str, JsonValue] | None = None) -> Completion:
    """Append one evidence-based diagnosis for a distinct observed failure and tree.

    Args:
        run: Current environment judgment consumer.
        again: The baseline or suite-review consumer to resume after fresh verification.
        observation: Actual setup failure evidence when no suite review exists yet.

    Returns:
        A genuine mapper session with fresh tracker and repository facts.

    Raises:
        StepError: This failure was already diagnosed or the correction allowance is spent.

    """
    tree: dict[str, JsonValue] = git_operation(
        run.tools,
        run.step["script"],
        ["hash-files", "--tree", str(workspace_of(run).tree)],
    )
    review: dict[str, JsonValue] = observation if observation is not None else _failure_observation(run, again)
    graph: beadgraph.Graph = run.tools.portfolio_read(
        run.step["script"],
        beadgraph.load,
        control_repo(),
        with_description=True,
    )
    state: list[JsonValue] = [
        {"id": bead.id, "status": bead.status, "parent": bead.parent, "blockers": list(bead.blockers)}
        for bead in graph.of_kind("task", "story")
    ]
    fingerprint: str = hashlib.sha256(
        json.dumps([review, tree["treeDigest"], state], sort_keys=True).encode(),
    ).hexdigest()
    accepted = [
        artifact["value"]
        for step in step_journal.steps_in_order(run.journal())
        if step["status"] == "done"
        for artifact in step["artifacts"]
        if artifact["kind"] == "value" and artifact["name"] == "prerequisiteFingerprint"
    ]
    if fingerprint in accepted or len(accepted) >= build_rounds():
        raise StepError(run.step["script"], OTHER_CAUSE, ("Prerequisite recovery exhausted its evidence-based bound",))
    path: Path = run.context.work / "build" / str(run.step["id"]) / "prerequisite-context.json"
    write_json(path, {"consumer": str(run.bead), "records": graph.records, "tree": tree, "review": review})
    planned: Completion = reasoned(
        run,
        "task-dependency-mapper",
        OutputContract(CONTRACTS / "build-prerequisites.schema.json", "prerequisiteDiagnosis"),
        f"Diagnose this current Task's failure read-only from fresh context {path}. Verify actual producer Task ids, "
        "their parent Stories, the consumed outputs and whether built code, a Published package or a recorded deployed "
        "resource is required. "
        "For regression-setup evidence, read setupPath and each failed command's output JSON, including stderrTail; "
        "retain the recorded successful setup commands as facts, not proof that the whole setup succeeded. "
        "Check current readiness rather than inferring missing SSM from an old synth or cached test. "
        "Never create parameters, invent issues, change edges or modify any source. "
        "Each producer evidence value must be an absolute existing captured evidence artifact path. "
        "When an actual Task builds the consumed output, route prerequisites and name it, even when waiting for it "
        "would close a cycle with standing edges: the caller checks cycles and fails only this Task with the cycle. "
        "Use missing-work only when no actual Task builds a consumed output; name authoringStory only if an actual "
        "open Story with completed saved scope/spec authorizes the missing work; "
        "distinguish an environment-only defect.",
        followups=(
            new_step(
                "build:prerequisites-diagnosed",
                "Apply the verified producer prerequisites",
                {
                    "again": again,
                    "fingerprint": fingerprint,
                },
            ),
        ),
    )
    return Completion(
        artifacts=planned.artifacts,
        add=planned.add,
    )


def diagnosed(run: StepRun) -> Completion:
    """Add only validated real prerequisite edges for the active consumer.

    Returns:
        A slot-releasing readiness gate, or a scoped environment observation.

    Raises:
        StepError: The diagnosis names a producer without existing evidence, contradicts the
            tracker, or its wait closes a completion cycle; only this Task fails, as an item.

    """
    diagnosis: dict[str, JsonValue] = artifact_document(run, "prerequisiteDiagnosis")
    again: str = check_type(run.params()["again"], str)
    if diagnosis["route"] == "environment":
        return Completion(
            artifacts=(value_artifact("prerequisiteFingerprint", check_type(run.params()["fingerprint"], str)),),
            add=(
                StepGroup((
                    new_step("build:environment-observe", "Observe the current environment", {"again": again}),
                )),
            ),
        )
    if diagnosis["route"] == "missing-work":
        return build_prerequisite_work.prepare(run, diagnosis)
    graph: beadgraph.Graph = run.tools.portfolio_read(run.step["script"], beadgraph.load, control_repo())
    producers: list[dict[str, JsonValue]] = check_type(diagnosis["producers"], list[dict[str, JsonValue]])
    try:
        _producer_rows(producers)
    except ValueError as error:
        # from None: a chained ValueError would classify this item's diagnosis as a pipeline defect.
        raise StepError(run.step["script"], OTHER_CAUSE, (str(error),)) from None
    _validate_producers(graph, str(run.bead), producers)
    writer: beadgraph.Writer = beadgraph.Writer(control_repo())
    standing: tuple[str, ...] = graph.beads[str(run.bead)].blockers
    blockers: list[str] = sorted({
        check_type(producer["task"], str) for producer in producers if producer["task"] not in standing
    })
    wait: dict[str, JsonValue] = {
        "task": str(run.bead),
        "evidencePath": str(artifact_file(run, "prerequisiteDiagnosis")),
        "fingerprint": check_type(run.params()["fingerprint"], str),
        "producers": list(producers),
    }
    snapshot: StorySnapshot = StorySnapshot(run.journal_path.parent)
    unresolved: dict[str, JsonValue] = _unresolved_wait(graph, snapshot, wait)
    waits: list[JsonValue] = _active_waits(graph, run.journal_path.parent, snapshot)
    if unresolved["producers"]:
        waits.append(unresolved)
    try:
        validate_wait_graph(graph.records, waits)
    except WaitCycleError as error:
        # from None: a chained ValueError would classify this Task's cyclic wait as a pipeline defect.
        evidence: tuple[str, ...] = (str(error), f"Proposed wait: {wait['evidencePath']}")
        raise StepError(run.step["script"], OTHER_CAUSE, evidence) from None
    run.tools.portfolio(run.step["script"], writer.write_blocks, {str(run.bead): blockers})
    return Completion(
        artifacts=(
            value_artifact("prerequisiteWait", wait),
            value_artifact("prerequisiteFingerprint", wait["fingerprint"]),
        ),
        add=(
            StepGroup((new_step("build:prerequisites-ready", "Wait for the actual producer work", {"again": again}),)),
        ),
    )


def _validate_producers(graph: beadgraph.Graph, consumer: str, producers: list[dict[str, JsonValue]]) -> None:
    """Refuse invented, self-referential or wrongly parented prerequisite Tasks.

    Raises:
        StepError: An identity, parent or requested stage contradicts the actual graph.

    """
    stage: str = "build:prerequisites-diagnosed"
    _producer_rows(producers)
    held: beadgraph.Bead | None = graph.beads.get(consumer)
    if held is None or held.kind != "task" or held.closed or not producers:
        raise StepError(stage, OTHER_CAUSE, ("No active consumer and real producers",))
    for producer in producers:
        task: beadgraph.Bead | None = graph.beads.get(check_type(producer["task"], str))
        story: beadgraph.Bead | None = graph.beads.get(check_type(producer["story"], str))
        identities: bool = task is not None and task.kind == "task" and task.id != consumer
        parent: bool = story is not None and story.kind == "story" and task is not None and task.parent == story.id
        if not identities or not parent:
            raise StepError(
                stage,
                OTHER_CAUSE,
                ("Producer Task/Story evidence disagrees with the tracker",),
            )
        if producer["requiredStage"] != "built" and story is not None and held.parent == story.id:
            raise StepError(
                stage,
                OTHER_CAUSE,
                ("A consumer cannot wait for delivery of its own unfinished Story",),
            )


def _validate_repository_ownership(
    graph: beadgraph.Graph,
    consumer: beadgraph.Bead,
    story: beadgraph.Bead,
) -> None:
    """Require actual repository ownership before evaluating prerequisite cycles.

    Raises:
        StepError: The consumer or producer Story lacks absolute repository ownership.

    """
    own: beadgraph.Bead | None = graph.beads.get(consumer.parent or "")
    left: str = "" if own is None else own.metadata.get(KEY_REPO_PATH, "")
    right: str = story.metadata.get(KEY_REPO_PATH, "")
    if not left or not right or not Path(left).is_absolute() or not Path(right).is_absolute():
        stage: str = "build:prerequisites-diagnosed"
        message: str = f"Consumer {consumer.id} or producer Story {story.id} lacks actual repository ownership"
        raise StepError(stage, OTHER_CAUSE, (message,))


def pending(wait: dict[str, JsonValue], directory: Path, control: Path) -> bool:
    """Check prerequisite progression without starting a session or retaining a slot.

    Args:
        wait: Accepted structured prerequisite wait.
        directory: Canonical journal directory.
        control: Central tracker repository.

    Returns:
        Whether any real producer still lacks the stage the consumer requires.

    """
    graph: beadgraph.Graph = beadgraph.load(control)
    producers: list[dict[str, JsonValue]] = check_type(wait["producers"], list[dict[str, JsonValue]])
    _validate_producers(graph, check_type(wait["task"], str), producers)
    snapshot: StorySnapshot = StorySnapshot(directory)
    return any(
        not graph.beads[check_type(producer["task"], str)].closed
        or (producer["requiredStage"] != "built" and not _delivered(producer, snapshot))
        for producer in producers
    )


def observe(run: StepRun, again: str) -> Completion:
    """Assign a fresh, read-only readiness observation before resuming the original suite.

    Returns:
        A bounded observation session and its result consumer.

    """
    return reasoned(
        run,
        "test-environment-provisioner",
        OutputContract(CONTRACTS / "build-readiness.schema.json", "prerequisiteReadiness"),
        "Observe the current readiness of the explicitly named consumed outputs and suite environment. "
        "Read-only prerequisite-readiness mode: record fresh resource states and commands in evidence; "
        "do not deploy, provision, reset, create SSM parameters, modify files or execute the suite. "
        "A closed Task or old synth is not readiness evidence.",
        followups=(
            new_step(
                "build:prerequisites-observed",
                "Resume the suite from fresh readiness evidence",
                {"again": again},
            ),
        ),
    )


def observed(run: StepRun) -> Completion:
    """Resume factual verification only after independently recorded current readiness.

    Returns:
        The original suite's fresh execution and assessment step.

    Raises:
        StepError: Fresh evidence shows the environment remains unready.

    """
    readiness: dict[str, JsonValue] = artifact_document(run, "prerequisiteReadiness")
    if readiness["ready"] is not True:
        raise StepError(run.step["script"], OTHER_CAUSE, (check_type(readiness["evidence"], str),))
    again: str = check_type(run.params()["again"], str)
    continuation: str = "build:baseline" if again == "build:baseline" else "build:prerequisites-suite"
    return Completion(
        add=(
            StepGroup((
                new_step(
                    continuation,
                    "Resume the baseline setup" if again == "build:baseline" else "Run and reassess the original suite",
                    {"again": again},
                ),
            )),
        ),
    )
