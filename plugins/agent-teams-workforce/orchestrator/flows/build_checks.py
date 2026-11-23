"""The deterministic checks a passing suite must also pass before a Task commits.

After the whole suite passes (``build:green-check``, ``build:refactor-check``,
``build:refactor-restore`` and the final suite), the build runs the repository's declared lint task
(``task lint``: its lint, format and type checks, cdk-nag included) and, for an infrastructure
Task, a real ``cdk synth --profile $ATW_DEPLOY_ENV --context env=$ATW_DEPLOY_ENV`` of every CDK app
the repository declares: the environment's name is also the AWS profile the CDK CLI resolves the
app's account and region from.
A non-zero exit stands in for the suite as the failing result, so it goes through the failing-suite
correction loop to the specialist that owns it, and when that loop's rounds are spent the Task is
held, never committed. A failing check is never carried as a review finding. With
``ATW_DEPLOY_ENV`` unset an infrastructure Task's synth check fails with that cause: the build
never guesses an environment.
"""

from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from driver_surface_types import DEPLOY_ENV_ENV
from typeguard import check_type

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import value_artifact
from orchestrator.core.models import StepError
from orchestrator.flows import build_policy
from orchestrator.flows.build_sessions import latest
from orchestrator.flows.build_state import argument_object, workspace_of
from orchestrator.flows.build_suite import SuiteResult, declared_task, run_suite

if TYPE_CHECKING:
    from step_journal_contract import ValueArtifact

    from orchestrator.core.journal_steps import StepRun

CHECKS: Final = "deterministicChecks"
"""The value artifact recording the checks that passed on a content tree, and the identity they ran for."""
LINT_TASK: Final = "lint"
"""The repository task that runs its lint, format and type checks (polyrepo ``checks-sync`` writes it)."""
LINT_CHECK: Final = "lint"
SYNTH_CHECK: Final = "cdk-synth"
CDK_JSON: Final = "cdk.json"
CHECKS_JSON: Final = Path(".code-checks") / "checks.json"
CDK_APPS_KEY: Final = "cdk_apps"


@dataclass(frozen=True, slots=True)
class Check:
    """One deterministic check: its kind, command and the folder it runs in."""

    kind: str
    command: str
    folder: Path


@dataclass(frozen=True, slots=True)
class Checks:
    """The outcome of the deterministic checks on one content tree."""

    identity: dict[str, JsonValue]
    commands: tuple[str, ...]
    lint_declared: bool
    failure: dict[str, JsonValue] | None

    def artifacts(self) -> tuple[ValueArtifact, ...]:
        """Record the checks that passed, so a later step on the same identity reuses them.

        Returns:
            The ``deterministicChecks`` artifact when every check passed, otherwise nothing.

        """
        if self.failure is not None:
            return ()
        record: dict[str, JsonValue] = {
            "identity": self.identity,
            "commands": list(self.commands),
            "lintDeclared": self.lint_declared,
        }
        return (value_artifact(CHECKS, record),)


def infrastructure(run: StepRun) -> bool:
    """Tell whether the Task is infrastructure work: its type or a label is in the infrastructure vocabulary.

    Returns:
        True for an infrastructure Task.

    """
    bead: dict[str, JsonValue] = argument_object(run, "bead")
    vocabulary: dict[str, JsonValue] = argument_object(run, "infraVocabulary")
    labels: list[str] = check_type(bead.get("labels", []), list[str])
    types: list[str] = check_type(vocabulary["types"], list[str])
    infrastructure_labels: list[str] = check_type(vocabulary["labels"], list[str])
    return bead.get("type") in types or bool(set(labels) & set(infrastructure_labels))


def cdk_apps(tree: Path, stage: str) -> list[Path]:
    """Name the ``cdk.json`` of every CDK app the repository declares.

    Args:
        tree: The repository worktree.
        stage: The journal step, for attribution of a malformed declaration.

    Returns:
        The apps ``.code-checks/checks.json`` lists under ``cdk_apps``, otherwise the root
        ``cdk.json`` when it exists, otherwise none.

    Raises:
        StepError: ``checks.json`` is not JSON or its ``cdk_apps`` is not a list of paths.

    """
    declaration: Path = tree / CHECKS_JSON
    if not declaration.is_file():
        return [tree / CDK_JSON] if (tree / CDK_JSON).is_file() else []
    try:
        declared: object = json_object(json.loads(declaration.read_text(encoding="utf-8"))).get(CDK_APPS_KEY)
    except (json.JSONDecodeError, TypeError) as error:
        raise StepError(stage, OTHER_CAUSE, (f"{declaration} is not a JSON object: {error}",)) from error
    if declared is None:
        return [tree / CDK_JSON] if (tree / CDK_JSON).is_file() else []
    if not isinstance(declared, list) or not all(isinstance(app, str) for app in declared):
        raise StepError(stage, OTHER_CAUSE, (f"{declaration}: {CDK_APPS_KEY} is not a list of cdk.json paths",))
    return [tree / app for app in declared if isinstance(app, str)]


def synth_command(environment: str, output: Path) -> str:
    """Build the synth check's command for one app.

    Returns:
        ``cdk synth --profile <environment> --context env=<environment> --quiet --output <output>``,
        quoted for the shell.

    """
    named: str = shlex.quote(environment)
    return f"cdk synth --profile {named} --context env={named} --quiet --output {shlex.quote(str(output))}"


def _planned(run: StepRun, stage: str, *, infra: bool, environment: str) -> list[Check]:
    """Plan the deterministic checks of the current worktree.

    Returns:
        The lint check when the repository declares it, then one synth check per CDK app of an
        infrastructure Task.

    Raises:
        StepError: An infrastructure Task has CDK apps to synthesize and ``ATW_DEPLOY_ENV`` is unset.

    """
    tree: Path = workspace_of(run).tree
    lint: str | None = declared_task(tree, LINT_TASK)
    planned: list[Check] = [Check(LINT_CHECK, lint, tree)] if lint is not None else []
    apps: list[Path] = cdk_apps(tree, str(run.step["script"])) if infra else []
    if apps and not environment:
        detail: str = (
            f"{DEPLOY_ENV_ENV} is unset, so the CDK synth check cannot name the environment it targets "
            f"(cdk synth --profile <name> --context env=<name>); the build never guesses one"
        )
        raise StepError(str(run.step["script"]), OTHER_CAUSE, (detail,))
    scratch: Path = run.context.work / "build" / str(run.step["id"]) / f"{stage}-cdk-out"
    planned.extend(
        Check(SYNTH_CHECK, synth_command(environment, scratch / str(index)), app.parent)
        for index, app in enumerate(apps)
    )
    return planned


def _executed(run: StepRun, stage: str, index: int, check: Check) -> SuiteResult:
    """Run one deterministic check through the suite runner, keeping its full output as evidence.

    Returns:
        The check's factual result.

    """
    evidence: Path = run.context.work / "build" / str(run.step["id"]) / f"{stage}-{check.kind}-{index}.json"
    return run_suite(run.tools, check.folder, check.command, evidence, str(run.step["script"]))


def run_checks(run: StepRun, stage: str) -> Checks:
    """Run the deterministic checks on the current content tree, or reuse the ones that passed on it.

    Args:
        run: The step that verifies a passing suite.
        stage: The verifying stage, for the evidence file names.

    Returns:
        The checks, with the first failing check's suite-shaped result as ``failure``.

    """
    infra: bool = infrastructure(run)
    environment: str = os.environ.get(DEPLOY_ENV_ENV, "").strip()
    identity: dict[str, JsonValue] = {
        "tree": build_policy.content_tree(run),
        "environment": environment,
        "infrastructure": infra,
    }
    prior: JsonValue = latest(run, CHECKS)
    if isinstance(prior, dict) and prior.get("identity") == identity:
        commands: list[str] = check_type(prior["commands"], list[str])
        return Checks(identity, tuple(commands), prior.get("lintDeclared") is True, None)
    planned: list[Check] = _planned(run, stage, infra=infra, environment=environment)
    outcomes = ((check, _executed(run, stage, index, check)) for index, check in enumerate(planned))
    failed: tuple[Check, SuiteResult] | None = next(
        ((check, result) for check, result in outcomes if result.exit_code != 0),
        None,
    )
    lint_declared: bool = any(check.kind == LINT_CHECK for check in planned)
    passed: tuple[str, ...] = tuple(check.command for check in planned)
    if failed is None:
        return Checks(identity, passed, lint_declared, None)
    failure: dict[str, JsonValue] = {**failed[1].document(), "check": failed[0].kind, "tree": identity["tree"]}
    return Checks(identity, passed, lint_declared, failure)
