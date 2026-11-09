"""The Task's accepted execution policy and the identity of reusable verification evidence.

The regression-impact-assessor writes the policy (``build-execution-policy.schema.json``) once the
regression scope is accepted. :func:`checked` validates it and records the identity of the scope
it was written for; :func:`decide` follows it for each optional stage while that scope is
unchanged and runs the stage when no accepted policy applies. Every decision is recorded on the
step as a ``stageDecision`` artifact, so the journal and the step events show which stages ran,
which were omitted and why.

A passing suite result may stand for a later run only when the accepted policy marks the suite
reusable and the later run's :func:`evidence_key` equals the earlier one: the work tree's content
(untracked files included, so the dependency lock and tool configuration in the tree too), the
requirements, the declared command, the setup, the runtime and tool configuration, the contract
version and the evidence scope. A live check is never reused.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shlex
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from driver_surface_types import SUITE_TIMEOUT_ENV
from typeguard import check_type

from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import Completion, StepGroup, StepRun, value_artifact
from orchestrator.flows.build_sessions import REQUIREMENT_NAMES, OutputContract, reasoned, view_of
from orchestrator.flows.build_state import (
    CONTRACTS,
    PLUGIN,
    artifact_document,
    build_rounds,
    count_in_dispatch,
    new_step,
    workspace_of,
)

if TYPE_CHECKING:
    from step_journal_contract import Artifact, Step, ValueArtifact

    from orchestrator.core.journal_views import AcceptedArtifact, AcceptedView

POLICY: Final = "executionPolicy"
IDENTITY: Final = "policyIdentity"
PROBLEMS: Final = "policyProblems"
DECISION: Final = "stageDecision"
SCHEMA: Final = CONTRACTS / "build-execution-policy.schema.json"
AUTHOR: Final = "regression-impact-assessor"
OPTIONAL_STAGES: Final = ("tests", "reuse-audit", "refactor", "docs")
"""Stages the policy may omit with an applicability reason."""
REQUIRED_STAGES: Final = ("code-review", "final-review", "final-suite", "regression-map")
"""Stages that always run: the independent judgment, the final suite and the regression gate."""
SUITE_NAMES: Final = ("baseline", "redRun", "greenRun", "refactorRun", "finalRun")
"""The artifacts that hold a whole-suite result."""
SCOPE_NAMES: Final = ("regressionPlan", "regressionScope")
"""The accepted regression artifacts the policy was written from."""
BEAD_SCOPE: Final = ("acceptanceCriteria", "definitionOfDone", "requirementIds", "surfaces", "testStrategy")
"""The Task's own fields the policy was written from."""
SUITE_SCOPE: Final = "whole-suite"
RUNNER: Final = Path(__file__).resolve().with_name("build_suite.py")

type Action = Literal["run", "omit", "reuse"]


@dataclass(frozen=True, slots=True)
class Decision:
    """What the build does with one stage, and why."""

    stage: str
    action: Action
    reason: str
    policy_step: str | None = None
    reused_from: str | None = None

    def artifact(self) -> ValueArtifact:
        """Record the decision on the step.

        Returns:
            The ``stageDecision`` value artifact.

        """
        value: dict[str, JsonValue] = {"stage": self.stage, "action": self.action, "reason": self.reason}
        if self.policy_step is not None:
            value["policyStep"] = self.policy_step
        if self.reused_from is not None:
            value["reusedFrom"] = self.reused_from
        return value_artifact(DECISION, value)


def _digest(value: JsonValue) -> str:
    """Hash a JSON value canonically.

    Returns:
        Its SHA-256 hex digest.

    """
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _file_digest(path: str) -> str:
    """Hash a file's bytes, or name it missing.

    Returns:
        The SHA-256 hex digest of its content, or ``missing`` when it is not a file.

    """
    target: Path = Path(path)
    return hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else "missing"


def _artifact_digest(held: AcceptedArtifact | None) -> str | None:
    """Hash what an accepted artifact holds: a file's content or a value.

    Returns:
        The digest, or None when the artifact is absent.

    """
    if held is None:
        return None
    if held.path is not None:
        return _file_digest(held.path) if held.kind == "file" else held.path
    return _digest(held.value)


def _requirements(run: StepRun, view: AcceptedView) -> dict[str, JsonValue]:
    """Identify the requirements the Task is built against.

    Returns:
        The digest of each accepted requirement artifact and of the Task's own requirement fields.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    return {
        "artifacts": {name: _artifact_digest(view.artifact(name)) for name in REQUIREMENT_NAMES},
        "task": _digest({key: bead.get(key) for key in BEAD_SCOPE}),
    }


def scope_identity(run: StepRun) -> str:
    """Identify the accepted scope an execution policy is written for.

    Args:
        run: The current step.

    Returns:
        The digest of the accepted regression scope and the requirements.

    """
    view: AcceptedView = view_of(run)
    scope: dict[str, JsonValue] = {name: _artifact_digest(view.artifact(name)) for name in SCOPE_NAMES}
    return _digest({"scope": scope, "requirements": _requirements(run, view)})


def author(run: StepRun) -> Completion:
    """Have the build scope assessor write the Task's execution policy.

    Returns:
        The assessor session and the deterministic check of its policy.

    """
    request: str = (
        "Write this Task's execution policy from its accepted regression scope, its requirements and "
        "acceptance criteria, its recorded surfaces and test strategy, the repository's capabilities and the "
        "existing evidence: run or omit each build stage with the requirement or evidence reason, the "
        "verification methods its actual changed surfaces need, and whether whole-suite evidence may be reused"
    )
    problems: JsonValue = run.params().get("problems")
    if isinstance(problems, list) and problems:
        request += ". Correct these problems of the previous policy: " + "; ".join(str(item) for item in problems)
    return reasoned(
        run,
        AUTHOR,
        OutputContract(SCHEMA, POLICY),
        request,
        followups=(new_step("build:execution-policy-checked", "Validate the execution policy against its contract"),),
    )


def problems_of(document: dict[str, JsonValue]) -> list[str]:
    """List what the schema cannot state about a policy: every stage once, every required stage run.

    Args:
        document: A policy that satisfied its schema.

    Returns:
        Each problem; empty for a valid policy.

    """
    stages: list[dict[str, JsonValue]] = [
        json_object(entry) for entry in check_type(document["stages"], list[JsonValue])
    ]
    named: list[str] = [check_type(entry["stage"], str) for entry in stages]
    found: list[str] = [
        f"stage {stage} is named {named.count(stage)} times" for stage in sorted(set(named)) if named.count(stage) > 1
    ]
    found.extend(f"stage {stage} is missing" for stage in (*OPTIONAL_STAGES, *REQUIRED_STAGES) if stage not in named)
    found.extend(
        f"stage {entry['stage']} always runs and cannot be omitted"
        for entry in stages
        if entry["stage"] in REQUIRED_STAGES and entry["decision"] != "run"
    )
    return found


def checked(run: StepRun) -> Completion:
    """Accept a valid policy for the scope it was written for, or correct it a bounded number of times.

    A policy still invalid when its correction allowance is spent is recorded as refused, and every
    stage then runs.

    Returns:
        The scope identity of an accepted policy, or its problems and a correction step.

    """
    found: list[str] = problems_of(artifact_document(run, POLICY))
    if not found:
        return Completion(artifacts=(value_artifact(IDENTITY, scope_identity(run)),))
    listed: list[JsonValue] = [*found]
    refused: tuple[ValueArtifact, ...] = (value_artifact(PROBLEMS, listed),)
    if count_in_dispatch(run, "build:execution-policy-checked") >= build_rounds() - 1:
        return Completion(artifacts=refused)
    correction = new_step(
        "build:execution-policy",
        "Correct the execution policy's contract problems",
        {"problems": listed},
    )
    return Completion(artifacts=refused, add=(StepGroup((correction,)),))


def _rank(view: AcceptedView, held: AcceptedArtifact) -> int:
    """Place an accepted artifact's producing step in walk order.

    Returns:
        Its position among the accepted steps.

    """
    return view.boundary.index(held.step)


def accepted_policy(run: StepRun) -> tuple[dict[str, JsonValue] | None, str, str | None]:
    """Read the policy the build follows now.

    Args:
        run: The current step.

    Returns:
        The policy, or None with the reason no policy applies; and the step that wrote it.

    """
    view: AcceptedView = view_of(run)
    policy: AcceptedArtifact | None = view.artifact(POLICY)
    if policy is None:
        return None, "no execution policy was accepted for this Task", None
    identity: AcceptedArtifact | None = view.artifact(IDENTITY)
    if identity is None or _rank(view, identity) < _rank(view, policy):
        return None, "the latest execution policy was not accepted", None
    if identity.value != scope_identity(run):
        return (
            None,
            "the execution policy is out of date: the Task's accepted scope changed after it was accepted",
            None,
        )
    return artifact_document(run, POLICY), "", policy.step


def decide(run: StepRun, stage: str) -> Decision:
    """Decide whether an optional stage runs.

    Args:
        run: The current step.
        stage: One of the optional stages.

    Returns:
        The policy's decision and reason, or a run decision naming why no policy applies.

    Raises:
        ValueError: The stage is not one the policy may omit.

    """
    if stage not in OPTIONAL_STAGES:
        message: str = f"the execution policy does not decide the stage {stage!r}"
        raise ValueError(message)
    policy, why, step = accepted_policy(run)
    if policy is None:
        return Decision(stage, "run", why)
    entry: dict[str, JsonValue] = next(
        json_object(item)
        for item in check_type(policy["stages"], list[JsonValue])
        if json_object(item)["stage"] == stage
    )
    action: Action = "omit" if entry["decision"] == "omit" else "run"
    return Decision(stage, action, check_type(entry["reason"], str), step)


def content_tree(run: StepRun) -> str:
    """Identify the work tree's content, untracked files included, without touching its index.

    A copy of the worktree's index takes every change with ``git add -A``; ``git write-tree`` then
    names the content. A commit of the same content keeps the same tree id.

    Returns:
        The git tree id.

    """
    tree: Path = workspace_of(run).tree
    stage: str = run.step.get("script", "build:evidence")
    located = run.tools.command(
        ["git", "rev-parse", "--path-format=absolute", "--git-path", "index"],
        stage=stage,
        cwd=tree,
    )
    index: Path = Path(located.stdout.strip())
    scratch: Path = run.context.work / "build" / str(run.step["id"]) / "content-index"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    if index.is_file():
        shutil.copyfile(index, scratch)
    else:
        scratch.unlink(missing_ok=True)
    environment: list[str] = ["env", f"GIT_INDEX_FILE={scratch}", "git"]
    run.tools.command([*environment, "add", "-A"], stage=stage, cwd=tree)
    written = run.tools.command([*environment, "write-tree"], stage=stage, cwd=tree)
    scratch.unlink(missing_ok=True)
    return written.stdout.strip()


def _tool(command: str) -> dict[str, JsonValue]:
    """Identify the executable a suite command starts.

    Returns:
        Its resolved path, size and modification time; nulls when it does not resolve.

    """
    words: list[str] = shlex.split(command)
    found: str | None = shutil.which(words[0]) if words else None
    if found is None:
        return {"path": None, "size": None, "modified": None}
    status = Path(found).stat()
    return {"path": found, "size": status.st_size, "modified": status.st_mtime_ns}


def _contract() -> dict[str, JsonValue]:
    """Identify the contract that produces suite evidence.

    Returns:
        The plugin version and the digests of the suite runner and the policy contract.

    """
    manifest: dict[str, JsonValue] = json_object(
        json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")),
    )
    return {"plugin": manifest.get("version"), "runner": _file_digest(str(RUNNER)), "policy": _file_digest(str(SCHEMA))}


def evidence_key(run: StepRun, command: str) -> dict[str, JsonValue]:
    """Identify a whole-suite result by everything that can change it.

    Args:
        run: The current step.
        command: The declared suite command.

    Returns:
        The key's digest and the content tree it covers.

    """
    view: AcceptedView = view_of(run)
    tree: str = content_tree(run)
    components: dict[str, JsonValue] = {
        "tree": tree,
        "command": command,
        "setup": _artifact_digest(view.artifact("regressionPlan")),
        "requirements": _requirements(run, view),
        "runtime": {
            "platform": platform.platform(),
            "python": sys.version,
            "path": os.environ.get("PATH", ""),
            "tool": _tool(command),
        },
        "configuration": {SUITE_TIMEOUT_ENV: os.environ.get(SUITE_TIMEOUT_ENV)},
        "contract": _contract(),
        "scope": SUITE_SCOPE,
    }
    return {"digest": _digest(components), "tree": tree}


def reusable_suite(
    run: StepRun,
    key: dict[str, JsonValue],
    *,
    fresh: bool,
) -> tuple[dict[str, JsonValue] | None, str]:
    """Find an accepted passing suite result that stands for a run with this evidence key.

    Args:
        run: The current step.
        key: The key :func:`evidence_key` gives the run.
        fresh: True when this check needs fresh evidence whatever the policy says.

    Returns:
        A copy of the result marked with what it was reused from, or None with the reason it must run.

    """
    if fresh:
        return None, "this check observes live readiness and needs fresh evidence"
    policy, why, _ = accepted_policy(run)
    if policy is None:
        return None, why
    freshness: dict[str, JsonValue] = json_object(policy["suiteFreshness"])
    if freshness["value"] != "reusable":
        return None, f"the execution policy requires fresh suite evidence: {freshness['reason']}"
    step: Step
    for step in reversed(view_of(run).steps()):
        found: dict[str, JsonValue] | None = _passing(step, key)
        if found is not None:
            return {**found, "evidenceKey": key, "reusedFrom": step["id"]}, ""
    return None, "no accepted passing suite result has this evidence identity"


def _passing(step: Step, key: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    """Find a step's last passing suite result recorded under an evidence key.

    Returns:
        A copy of the result, or None when the step recorded none.

    """
    artifact: Artifact
    for artifact in reversed(step["artifacts"]):
        if artifact["kind"] != "value" or artifact["name"] not in SUITE_NAMES:
            continue
        value: JsonValue = artifact["value"]
        if not isinstance(value, dict):
            continue
        recorded: JsonValue = value.get("evidenceKey")
        if value.get("exitCode") == 0 and isinstance(recorded, dict) and recorded.get("digest") == key["digest"]:
            return dict(value)
    return None


def suite_decision(document: dict[str, JsonValue], stage: str) -> ValueArtifact:
    """Record whether a suite check ran or reused accepted evidence.

    Args:
        document: The suite result a check recorded.
        stage: The check's stage name.

    Returns:
        The ``stageDecision`` artifact.

    """
    origin: JsonValue = document.get("reusedFrom")
    if isinstance(origin, str):
        reason: str = "an accepted passing suite result has the same evidence identity"
        return Decision(stage, "reuse", reason, reused_from=origin).artifact()
    refused: JsonValue = document.get("reuseRefused")
    return Decision(stage, "run", refused if isinstance(refused, str) and refused else "the suite ran").artifact()


def summary(run: StepRun) -> dict[str, JsonValue]:
    """Summarize the Task's model sessions, corrective rounds and stage decisions.

    Args:
        run: The current step.

    Returns:
        Counts from the accepted journal: sessions by agent, correction steps by kind, and every
        recorded stage decision.

    """
    sessions: dict[str, JsonValue] = {}
    corrections: dict[str, JsonValue] = {}
    decisions: list[JsonValue] = []
    correcting: frozenset[str] = frozenset({
        "build:suite-reviewed",
        "build:green-reviewed",
        "build:correct-findings",
        "build:implementation-recheck",
        "build:regression-reassess",
        "build:regression-remap",
        "build:final-review",
        "build:prerequisites-rediagnose",
    })
    for step in view_of(run).steps():
        agent: str | None = step.get("agent")
        if agent is not None:
            sessions[agent] = check_type(sessions.get(agent, 0), int) + 1
        script: str | None = step.get("script")
        if script in correcting:
            corrections[script] = check_type(corrections.get(script, 0), int) + 1
        decisions.extend(
            artifact["value"]
            for artifact in step["artifacts"]
            if artifact["name"] == DECISION and artifact["kind"] == "value"
        )
    return {
        "sessions": sessions,
        "sessionCount": sum(check_type(count, int) for count in sessions.values()),
        "corrections": corrections,
        "correctionCount": sum(check_type(count, int) for count in corrections.values()),
        "decisions": decisions,
    }
