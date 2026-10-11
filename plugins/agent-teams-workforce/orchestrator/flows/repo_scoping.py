"""Place approved elements, then create only the repositories the steward names."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# The driver surface and target report contracts are defined once, in their skills.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from driver_surface_types import CONTROL_REPO_ENV
from placement_contract import (
    KEY_ITEM_IDS,
    KEY_MISSING_REPOS,
    KEY_NAME,
    KEY_NO_CODE,
    KEY_PLACEMENTS,
    KEY_PURPOSE,
    KEY_REPO_NAME,
    KEY_REPO_PATH,
    KEY_SPAN_RATIONALE,
    KEY_TEMPLATE,
    MissingRepo,
    Placement,
    PlacementRuling,
)
from target_contract import (
    DELTA_ITEMS_FILE,
    KEY_ARCHITECTURE_CHANGE,
    KEY_DELTA_DIR,
    KEY_ELEMENT,
    KEY_ITEMS,
    KEY_NOTE,
    KEY_TARGET_DIR,
    TARGET_REPORT_PARTS,
    TargetContractError,
    load_delta_report,
)
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.agent_context import yaml_safe_load
from orchestrator.core.agents import AgentRunner
from orchestrator.core.artifacts import ArtifactStore
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback import failure_for
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.matrix import read_snapshot, row_for, snapshot
from orchestrator.core.models import AgentStep, RunContext, StepError
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.architecture_support import REPO_SCOPING_PHASE
from orchestrator.flows.repo_placement import PlacementInputs, accept_placement, app_space

if TYPE_CHECKING:
    from target_contract import DeltaItem, DeltaResult


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def inventory(tools: Tools) -> dict[str, JsonValue]:
    """Read the repository inventory and validate its row collection.

    Returns:
        The inventory object returned by the repository steward.

    """
    result = tools.polyrepo(["inventory"], stage=REPO_SCOPING_PHASE)
    value = json_object(json.loads(result.stdout))
    _objects(value["repos"])
    return value


def _preflight(tools: Tools, config: dict[str, JsonValue]) -> str | None:
    signed_in = tools.command(["gh", "auth", "status"], stage="repo-creation", check=False)
    if signed_in.exit:
        return "The GitHub CLI is not signed in on this machine; run gh auth login."
    owner = check_type(config["github_owner"], str)
    membership = tools.command(
        ["gh", "api", f"user/memberships/orgs/{owner}", "--jq", ".state"],
        stage="repo-creation",
        check=False,
    )
    if membership.exit or membership.stdout.strip() != "active":
        return (
            f"The signed-in GitHub account is not an active member of {owner}; "
            "sign in with an active member account or arrange organisation membership."
        )
    return None


def _create(missing: MissingRepo, tools: Tools, config: dict[str, JsonValue]) -> str:
    stage = "repo-creation"
    name: str = missing[KEY_NAME]
    result = tools.polyrepo(
        [
            "create",
            name,
            "--space",
            app_space(name, config),
            "--template",
            missing[KEY_TEMPLATE],
            "--purpose",
            missing[KEY_PURPOSE],
        ],
        stage=stage,
    )
    value = json_object(json.loads(result.stdout))
    path = check_type(value.get("path"), str | None)
    if not path or not Path(path).is_absolute():
        raise tools.failure(stage, OTHER_CAUSE, {"result": value})
    return path


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def create_repositories(
    ruling: PlacementRuling,
    tools: Tools,
    config: dict[str, JsonValue],
    work: Path,
) -> dict[str, JsonValue]:
    """Create the steward's missing repositories after verifying GitHub access.

    Returns:
        Measured creation results or an explicit owner authentication requirement.

    Raises:
        StepError: A deterministic repository operation fails.
        ValueError: Repository output is invalid.
        OSError: A repository operation cannot access a required resource.
        KeyError: A required repository field is absent.

    """
    created: list[dict[str, JsonValue]] = []
    failures: list[dict[str, JsonValue]] = []
    preflight_done = False
    for missing in ruling[KEY_MISSING_REPOS]:
        facts: dict[str, JsonValue] = {
            KEY_NAME: missing[KEY_NAME],
            KEY_TEMPLATE: missing[KEY_TEMPLATE],
            KEY_ITEM_IDS: list(missing[KEY_ITEM_IDS]),
        }
        try:
            outcome, preflight_done = _ensure_repository(missing, tools, config, preflight_done=preflight_done)
        except (StepError, ValueError, OSError, KeyError) as exc:
            failures.append(
                json_object({
                    **facts,
                    "error": list(exc.evidence) if isinstance(exc, StepError) else str(exc),
                    "ownerFact": False,
                    "failure": failure_for("repo-creation", exc, agent_started=False),
                }),
            )
            write_json(work / "repo-creation.json", {"created": created, "failures": failures})
            raise
        if outcome.get("ownerFact"):
            failures.append({**facts, **outcome})
            break
        created.append({**facts, **outcome})
    result = json_object({"created": created, "failures": failures})
    write_json(work / "repo-creation.json", result)
    return result


class _RepositoryScoping:
    """Bind one placement ruling's immutable evidence and output paths."""

    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        runner: AgentRunner,
        tools: Tools,
        matrix_path: Path | None,
    ) -> None:
        self.context, self.store, self.runner, self.tools = context, store, runner, tools
        self.args, self.work = context.args, context.work
        stage = "input"
        target = self.args.get(KEY_TARGET_DIR)
        if not target:
            raise StepError(stage, OTHER_CAUSE, (f"{KEY_TARGET_DIR} is required",))
        self.target = check_type(target, str)
        self.items_path = self.work / DELTA_ITEMS_FILE
        try:
            delta: DeltaResult = load_delta_report(self.items_path)
        except (TargetContractError, OSError, json.JSONDecodeError) as exc:
            raise StepError(stage, OTHER_CAUSE, (f"{DELTA_ITEMS_FILE} is not a delta report: {exc}",)) from exc
        delta_items: list[DeltaItem] = delta.get(KEY_ITEMS, [])
        if not delta_items:
            raise StepError(stage, OTHER_CAUSE, (f"{DELTA_ITEMS_FILE} has no build items",))
        items: list[dict[str, JsonValue]] = _objects(delta_items)
        dispatch: DispatchArguments = dispatch_arguments()
        arch = Path(check_type(self.args[dispatch.KEY_ARCH_PATH], str)).resolve()
        self.prd = Path(check_type(json_object(self.args[dispatch.KEY_PRD])[dispatch.PRD_PATH], str)).resolve()
        control = env_path(CONTROL_REPO_ENV)
        config = json_object(yaml_safe_load((control / ".polyrepo/config.yaml").read_text(encoding="utf-8")))
        matrix = matrix_path or snapshot(context, tools)
        matrix_data = read_snapshot(matrix)
        self.elements = sorted({" ".join(item[KEY_ELEMENT].split()).casefold() for item in delta_items})
        self.placement = PlacementInputs(
            items=items,
            inventory=inventory(tools),
            rows={name: row_for(matrix_data, name) for name in self.elements},
            config=config,
            control=control,
            arch=arch,
            marketing=env_path("SKILLSPOKE_ROOT") / "apps/marketing",
            avoid=_objects(self.args.get("avoidRepos", [])),
        )
        binding = "matrix-rows:" + json.dumps({"matrix": str(matrix), "elements": self.elements}, sort_keys=True)
        self.inputs: tuple[str, ...] = (
            *map(
                str,
                (
                    self.prd,
                    self.work / "architecture/decision.md",
                    self.work.joinpath(*TARGET_REPORT_PARTS),
                    self.items_path,
                    self.target,
                ),
            ),
            binding,
        )
        if self.args.get(KEY_DELTA_DIR):
            self.inputs += (check_type(self.args[KEY_DELTA_DIR], str),)
        self.final = self.work / "repo-scoping.json"
        self.warnings: list[str] = []

    def _validate(self, path: Path, *, reused: bool = False) -> PlacementRuling:
        value, self.warnings = accept_placement(path, self.placement, reused=reused)
        return value

    def _check_candidate(self, path: Path) -> dict[str, JsonValue]:
        return json_object(self._validate(path))

    def _author(self, feedback_data: dict[str, JsonValue]) -> PlacementRuling:
        self.store.invalidate((self.final,))
        inventory_path = self.work / "repo-scoping.inventory.json"
        rows_path = self.work / "repo-scoping.matrix.json"
        facts_path = self.work / "repo-scoping.context.json"
        feedback = self.work / "repo-scoping.feedback.json"
        write_json(inventory_path, self.placement.inventory)
        write_json(rows_path, {"elements": self.placement.rows})
        write_json(feedback, feedback_data)
        write_json(
            facts_path,
            {
                KEY_ARCHITECTURE_CHANGE: self.args.get(KEY_ARCHITECTURE_CHANGE),
                KEY_NOTE: self.args.get(KEY_NOTE),
                KEY_TARGET_DIR: self.target,
                KEY_DELTA_DIR: self.args.get(KEY_DELTA_DIR),
            },
        )
        candidate = self.work / "candidates/repo-scoping.json"
        self.store.invalidate((candidate,))
        self.runner.run(
            AgentStep(
                stage=REPO_SCOPING_PHASE,
                agent="polyrepo-steward",
                inputs=(*self.inputs, *map(str, (inventory_path, rows_path, feedback, facts_path))),
                output=candidate,
                final=None,
                validate=self._check_candidate,
                outcome="Repository placement ruling for the approved architecture elements.",
                model="sonnet",
                effort="high",
                add_dirs=(self.work, self.placement.arch, self.prd.parent),
                corrective=not bool(feedback_data.get("errors")),
            ),
        )
        ruling = self._validate(candidate)
        write_json(self.final, ruling)
        self.store.accept(REPO_SCOPING_PHASE, self.inputs, (self.final,))
        return ruling

    def _ruling(self) -> PlacementRuling:
        feedback = json_object({"avoid": self.placement.avoid})
        if self.store.reusable(self.inputs, (self.final,)) and not self.placement.avoid:
            try:
                return self._validate(self.final, reused=True)
            except (ValueError, OSError) as exc:
                feedback["errors"] = [str(exc)]
        return self._author(feedback)

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self) -> dict[str, JsonValue]:
        """Complete placement and publish measured repository creation results.

        Returns:
            The repository span or explicit owner authentication action.

        """
        ruling = self._ruling()
        creation = create_repositories(ruling, self.tools, self.placement.config, self.work)
        creation_path = self.work / "repo-creation.json"
        self.store.accept("repo-creation", (str(self.final),), (creation_path,))
        failures = _objects(creation["failures"])
        if failures:
            return json_object({
                "ok": False,
                "stage": "requires-human-action",
                "requiredHumanActions": [item["error"] for item in failures],
                "creationPath": str(creation_path),
            })
        paths: dict[str, str] = {
            check_type(repo[KEY_NAME], str).casefold(): check_type(repo[KEY_REPO_PATH], str)
            for repo in _objects(creation["created"])
        }
        placements: list[Placement] = []
        for placement in ruling[KEY_PLACEMENTS]:
            placed: Placement = placement.copy()
            placed[KEY_REPO_PATH] = placement[KEY_REPO_PATH] or paths[placement[KEY_REPO_NAME].casefold()]
            placements.append(placed)
        ruling[KEY_PLACEMENTS] = placements
        write_json(self.final, ruling)
        self.store.accept(REPO_SCOPING_PHASE, self.inputs, (self.final,))
        self.store.accept("repo-creation", (str(self.final),), (creation_path,))
        repos: list[str] = list(dict.fromkeys(check_type(p[KEY_REPO_PATH], str) for p in placements))
        return json_object({
            "ok": True,
            "repos": repos,
            KEY_PLACEMENTS: placements,
            KEY_NO_CODE: ruling[KEY_NO_CODE],
            "createdRepos": creation["created"],
            "warnings": self.warnings,
            "artifactPath": str(self.final),
            "creationPath": str(creation_path),
            KEY_SPAN_RATIONALE: ruling[KEY_SPAN_RATIONALE],
            "ledger": {
                "phase": REPO_SCOPING_PHASE,
                "beadId": self.context.bead,
                "subject": self.args.get("architectureSubject", ""),
                "chosen": ["polyrepo-steward"],
                "mode": "fixed",
                "repoCount": len(repos),
                "itemCount": len(self.placement.items),
                "createdRepoCount": len(_objects(creation["created"])),
                "ok": True,
            },
        })


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run(
    context: RunContext,
    store: ArtifactStore,
    runner: AgentRunner,
    tools: Tools,
    *,
    matrix_path: Path | None = None,
) -> dict[str, JsonValue]:
    """Place approved elements and create the declared repository span.

    Returns:
        The accepted placement and measured repository creation outcome.

    """
    context.stage = REPO_SCOPING_PHASE
    return _RepositoryScoping(context, store, runner, tools, matrix_path).run()


def _ensure_repository(
    missing: MissingRepo,
    tools: Tools,
    config: dict[str, JsonValue],
    *,
    preflight_done: bool,
) -> tuple[dict[str, JsonValue], bool]:
    live = inventory(tools)
    name: str = missing[KEY_NAME].casefold()
    existing = next(
        (r for r in _objects(live["repos"]) if check_type(r["name"], str).casefold() == name and r.get("path")),
        None,
    )
    if existing:
        return {KEY_REPO_PATH: existing["path"], "existed": True}, preflight_done
    if not preflight_done:
        need = _preflight(tools, config)
        if need:
            return {"error": need, "ownerFact": True}, False
    return {KEY_REPO_PATH: _create(missing, tools, config), "existed": False}, True
