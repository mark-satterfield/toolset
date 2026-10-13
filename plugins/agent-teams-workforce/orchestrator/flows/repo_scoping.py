"""Read the repository span of an Epic from the matrix, and create a repository it names and lacks.

The solutions architect records each element with its repository and stack, what it depends on
and which feature it realizes. This step reads that: the elements the PRD's features are realized
by, with everything they depend on, that no pipeline has built yet. Each is an item some
repository's Story builds. No session is started. A repository the matrix names and the
inventory lacks is created from the template the project's naming rules give its name.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

# The driver surface and the placement contract are defined once, in their skills.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
import hierarchy
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import (
    CODE_BUILT,
    CODE_DEPLOYED,
    ELEMENT_KINDS,
    KIND_REPOSITORY,
    LINK_DEPENDS_ON,
    LINK_DESCRIBED_BY,
    LINK_REALIZED_BY,
    Matrix,
    Node,
    NodeId,
)
from matrixquery import PrdView, prd_view
from matrixstore import make_id, matrix_path, read_matrix
from placement_contract import (
    KEY_ITEM_IDS,
    KEY_MISSING_REPOS,
    KEY_NAME,
    KEY_PLACEMENTS,
    KEY_PURPOSE,
    KEY_REPO_PATH,
    KEY_TEMPLATE,
    MissingRepo,
    Placement,
    PlacementRuling,
)
from target_contract import KIND_IMPLEMENTATION_GAP, KIND_PREREQUISITE, STATE_UNKNOWN, DeltaItem, DeltaResult
from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.frontmatter import yaml_safe_load
from orchestrator.core.handback import failure_for
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import script_step
from orchestrator.core.journal_steps import Completion, NewStep, StepGroup, StepRun, file_artifact, value_artifact
from orchestrator.core.models import StepError
from orchestrator.core.tools import Tools, env_path
from orchestrator.flows.architecture_files import HUMAN_ACTION_STAGE
from orchestrator.flows.elaboration_files import (
    ARTIFACT_CREATION,
    ARTIFACT_ELEMENTS,
    ARTIFACT_REPOSITORIES,
    ARTIFACT_SPAN,
    SPEC_CONTEXT,
)
from orchestrator.flows.elaboration_support import REPO_SCOPING_PHASE, enter_phase
from orchestrator.flows.repo_placement import app_space, forbidden

if TYPE_CHECKING:
    from step_journal_contract import StepPlan

SPAN: Final = "atw-matrix prd --closure"
"""The script key of the span step."""
SPAN_DESCRIPTION: Final = "Read the repositories this PRD involves from the matrix"
SPAN_PURPOSE: Final = "The repository span and the elements each repository builds come from the matrix"
SPECS_PURPOSE: Final = "The repository has one reviewed spec set and one Story"
SPAN_FILE: Final = "repo-scoping.json"
ELEMENTS_FILE: Final = "span-elements.json"
"""The files the span step writes in the Epic's work directory: the placements and the elements."""
CONTEXT_PURPOSE: Final = "The items this repository builds and the steps that specify them are known"
CREATION_STAGE: Final = "repo-creation"
FRONTEND_KIND: Final = "frontend"


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def inventory(tools: Tools) -> dict[str, JsonValue]:
    """Read the repository inventory and validate its row collection.

    Returns:
        The inventory object the ``polyrepo`` tool printed.

    """
    result = tools.polyrepo(["inventory"], stage=REPO_SCOPING_PHASE)
    value = json_object(json.loads(result.stdout))
    _objects(value["repos"])
    return value


def _preflight(tools: Tools, config: dict[str, JsonValue]) -> str | None:
    signed_in = tools.command(["gh", "auth", "status"], stage=CREATION_STAGE, check=False)
    if signed_in.exit:
        return "The GitHub CLI is not signed in on this machine; run gh auth login."
    owner = check_type(config["github_owner"], str)
    membership = tools.command(
        ["gh", "api", f"user/memberships/orgs/{owner}", "--jq", ".state"],
        stage=CREATION_STAGE,
        check=False,
    )
    if membership.exit or membership.stdout.strip() != "active":
        return (
            f"The signed-in GitHub account is not an active member of {owner}; "
            "sign in with an active member account or arrange organisation membership."
        )
    return None


def _create(missing: MissingRepo, tools: Tools, config: dict[str, JsonValue]) -> str:
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
        stage=CREATION_STAGE,
    )
    value = json_object(json.loads(result.stdout))
    path = check_type(value.get("path"), str | None)
    if not path or not Path(path).is_absolute():
        raise tools.failure(CREATION_STAGE, OTHER_CAUSE, {"result": value})
    return path


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


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def create_repositories(
    ruling: PlacementRuling,
    tools: Tools,
    config: dict[str, JsonValue],
    work: Path,
) -> dict[str, JsonValue]:
    """Create the repositories the span names and the inventory lacks, after verifying GitHub access.

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
                    "failure": failure_for(CREATION_STAGE, exc, agent_started=False),
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


def _work_elements(matrix: Matrix, view: PrdView) -> tuple[list[Node], set[NodeId]]:
    """Find the elements an Epic's Stories build, from the links the architect recorded.

    Returns:
        The elements the PRD's features are realized by and everything those depend on, that no
        pipeline has built yet, in id order; and the ids of those a feature is realized by.

    """
    features: list[NodeId] = [row["id"] for row in view.get("closure", {}).get("features", [])]
    roots: set[NodeId] = {
        link["to"]
        for key in features
        for link in matrix["nodes"][key]["links"]
        if link["type"] == LINK_REALIZED_BY and link["to"] in matrix["nodes"]
    }
    reached: dict[NodeId, None] = dict.fromkeys(sorted(roots))
    queue: list[NodeId] = list(reached)
    while queue:
        for link in matrix["nodes"][queue.pop(0)]["links"]:
            if link["type"] == LINK_DEPENDS_ON and link["to"] in matrix["nodes"] and link["to"] not in reached:
                reached[link["to"]] = None
                queue.append(link["to"])
    work: list[Node] = [
        matrix["nodes"][key]
        for key in sorted(reached)
        if matrix["nodes"][key]["kind"] in ELEMENT_KINDS
        and matrix["nodes"][key].get("code", {}).get("state") not in {CODE_BUILT, CODE_DEPLOYED}
    ]
    return work, roots


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def span_items(matrix: Matrix, bead: str) -> list[DeltaItem]:
    """List the items an Epic's Stories build, in the shape the spec and Task steps read.

    A matrix with no PRD row for the Epic raises ``MatrixRefusedError``.

    Args:
        matrix: The matrix.
        bead: The Epic.

    Returns:
        One item per element to build: its id, the element's name, the documents that describe
        it, its repository, and the items it requires and is required by, from the
        ``dependsOn`` links between the elements.

    """
    work, roots = _work_elements(matrix, prd_view(matrix, bead, closure=True))
    ids: dict[NodeId, str] = {node["id"]: f"E{index}" for index, node in enumerate(work, 1)}
    items: list[DeltaItem] = []
    node: Node
    for node in work:
        requires: list[str] = [
            ids[link["to"]] for link in node["links"] if link["type"] == LINK_DEPENDS_ON and link["to"] in ids
        ]
        item: DeltaItem = {
            "id": ids[node["id"]],
            "element": node["name"],
            "views": [link["to"] for link in node["links"] if link["type"] == LINK_DESCRIBED_BY],
            "kind": KIND_IMPLEMENTATION_GAP if node["id"] in roots else KIND_PREREQUISITE,
            "state": STATE_UNKNOWN,
            "repository": node.get("repository"),
            "requires": requires,
            "requiredBy": [],
            "evidence": [node["id"]],
        }
        items.append(item)
    by_id: dict[str, DeltaItem] = {item["id"]: item for item in items}
    for item in items:
        for needed in item.get("requires", []):
            by_id[needed].setdefault("requiredBy", []).append(item["id"])
    return items


def _repository_kind(name: str, config: dict[str, JsonValue]) -> str | None:
    """Find the template the project's naming rules give a repository name.

    Returns:
        The template whose name pattern matches, or None when none does.

    """
    kinds: dict[str, JsonValue] = json_object(json_object(config.get("templates", {})).get("kinds", {}))
    for kind, rule in kinds.items():
        pattern: JsonValue = json_object(rule).get("name_regex")
        if isinstance(pattern, str) and re.search(pattern, name):
            return kind
    return None


def _ruling(
    run: StepRun,
    matrix: Matrix,
    items: list[DeltaItem],
    config: dict[str, JsonValue],
) -> PlacementRuling:
    """Group the items by the repository the matrix places each in.

    Returns:
        The span in the placement contract's shape: one placement per repository, with its path
        when the inventory has it, and one missing repository per name it lacks.

    Raises:
        StepError: An item has no repository, a repository may hold no product element, or a
            missing repository's name matches no template.

    """
    live: dict[str, dict[str, JsonValue]] = {
        check_type(repo["name"], str).casefold(): repo for repo in _objects(inventory(run.tools)["repos"])
    }
    control: Path = env_path(CONTROL_REPO_ENV)
    arch: Path = Path(check_type(run.context.args[dispatch_arguments().KEY_ARCH_PATH], str)).resolve()
    grouped: dict[str, list[str]] = {}
    unplaced: list[str] = [item["element"] for item in items if not item.get("repository")]
    if unplaced:
        raise StepError(SPAN, OTHER_CAUSE, tuple(f"the matrix places {name} in no repository" for name in unplaced))
    for item in items:
        grouped.setdefault(check_type(item.get("repository"), str), []).append(item["id"])
    ruling: PlacementRuling = {
        KEY_PLACEMENTS: [],
        KEY_MISSING_REPOS: [],
        "noCode": [],
        "spanRationale": "The repository of each element, as the matrix records it.",
    }
    for name, placed in grouped.items():
        known: JsonValue = live.get(name.casefold(), {}).get("path")
        path: str | None = str(Path(known).resolve()) if isinstance(known, str) and known else None
        if path is not None and forbidden(Path(path), control, arch, env_path("SKILLSPOKE_ROOT") / "apps/marketing"):
            raise StepError(SPAN, OTHER_CAUSE, (f"{name} at {path} may hold no product element",))
        kind: str | None = _repository_kind(name, config)
        placement: Placement = {
            KEY_REPO_PATH: path,
            "repoName": name,
            KEY_ITEM_IDS: placed,
            "frontend": kind == FRONTEND_KIND,
            "rationale": "The matrix places these elements in this repository.",
        }
        ruling[KEY_PLACEMENTS].append(placement)
        if path is None:
            if kind is None:
                raise StepError(SPAN, OTHER_CAUSE, (f"{name} does not exist and its name matches no template",))
            row: Node | None = matrix["nodes"].get(make_id(KIND_REPOSITORY, name))
            stated: str = "" if row is None else row.get("purpose", "")
            purpose: str = stated or f"Holds elements the matrix places in it for {run.bead}."
            ruling[KEY_MISSING_REPOS].append({
                KEY_NAME: name,
                KEY_TEMPLATE: kind,
                KEY_PURPOSE: purpose,
                KEY_ITEM_IDS: placed,
            })
    return ruling


def _spec_steps(run: StepRun, ruling: PlacementRuling, repos: list[str]) -> tuple[StepGroup, ...]:
    """Plan one container per repository of the span, each with its first step, after the span step.

    Returns:
        The group, or nothing for an empty span. A container is named for its repository; its
        first step gathers what the repository builds and plans the repository's other steps.

    """
    slugs: dict[str, str] = check_type(
        run.tools.portfolio(SPAN, hierarchy.repo_slugs, repos),
        dict[str, str],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )
    frontend: set[str] = {
        check_type(placement[KEY_REPO_PATH], str) for placement in ruling[KEY_PLACEMENTS] if placement["frontend"]
    }
    steps: list[NewStep] = []
    for index, (repo, slug) in enumerate(slugs.items(), 1):
        name: str = Path(repo).name
        first: StepPlan = {
            "description": f"Gather what {name} builds",
            "purpose": CONTEXT_PURPOSE,
            "script": SPEC_CONTEXT,
            "inputs": [run.step["id"], *run.step.get("inputs", [])],
        }
        params: dict[str, JsonValue] = {
            "repoPath": repo,
            "slug": slug,
            "storyKey": f"S{index}",
            "frontend": repo in frontend,
        }
        container: StepPlan = {"description": name, "purpose": SPECS_PURPOSE}
        steps.append(NewStep(container, children=(NewStep(first, params),)))
    return (StepGroup(tuple(steps)),) if steps else ()


@script_step(SPAN)
def span(run: StepRun) -> Completion:
    """Read the repository span from the matrix and plan one spec step per repository.

    Returns:
        The span file, the elements file, the repository paths, and the creation record when a
        repository had to be created; with the spec steps planned after this step.

    Raises:
        StepError: The PRD reaches no element to build, or a repository can be created only
            after the owner acts.

    """
    enter_phase(run.context, run.agents.emit, REPO_SCOPING_PHASE, SPAN)
    matrix: Matrix = run.tools.portfolio(SPAN, read_matrix, matrix_path(None, os.environ))
    items: list[DeltaItem] = run.tools.portfolio(SPAN, span_items, matrix, run.bead)
    if not items:
        raise StepError(SPAN, OTHER_CAUSE, (f"the matrix records no element to build for {run.bead}",))
    work: Path = run.context.work
    control: Path = env_path(CONTROL_REPO_ENV)
    config: dict[str, JsonValue] = json_object(
        yaml_safe_load((control / ".polyrepo/config.yaml").read_text(encoding="utf-8")),
    )
    ruling: PlacementRuling = _ruling(run, matrix, items, config)
    elements: DeltaResult = {
        "ok": True,
        "refusals": [],
        "summary": {"ok": True, "refusals": [], "items": len(items)},
        "items": items,
    }
    elements_path: Path = work / ELEMENTS_FILE
    write_json(elements_path, elements)
    artifacts = [file_artifact(ARTIFACT_ELEMENTS, elements_path)]
    if ruling[KEY_MISSING_REPOS]:
        creation: dict[str, JsonValue] = create_repositories(ruling, run.tools, config, work)
        artifacts.append(file_artifact(ARTIFACT_CREATION, work / "repo-creation.json"))
        failures: list[dict[str, JsonValue]] = _objects(creation["failures"])
        if failures:
            raise StepError(HUMAN_ACTION_STAGE, OTHER_CAUSE, tuple(str(item["error"]) for item in failures))
        made: dict[str, str] = {
            check_type(repo[KEY_NAME], str).casefold(): check_type(repo[KEY_REPO_PATH], str)
            for repo in _objects(creation["created"])
        }
        for placement in ruling[KEY_PLACEMENTS]:
            placement[KEY_REPO_PATH] = placement[KEY_REPO_PATH] or made[placement["repoName"].casefold()]
    span_path: Path = work / SPAN_FILE
    write_json(span_path, ruling)
    repos: list[str] = list(dict.fromkeys(check_type(p[KEY_REPO_PATH], str) for p in ruling[KEY_PLACEMENTS]))
    held: list[JsonValue] = list(repos)
    return Completion(
        artifacts=(file_artifact(ARTIFACT_SPAN, span_path), *artifacts, value_artifact(ARTIFACT_REPOSITORIES, held)),
        add=_spec_steps(run, ruling, repos),
    )
