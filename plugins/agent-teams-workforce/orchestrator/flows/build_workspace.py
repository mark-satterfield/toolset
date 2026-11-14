"""Mechanical workspace and checkpoint operations, without a command-runner session."""

from __future__ import annotations

import configparser
import fnmatch
import hashlib
import json
import re
import sys
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import yaml
from typeguard import TypeCheckError, check_type

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import PipelineDefectError, StepError
from orchestrator.core.tool_locks import control_repo
from orchestrator.core.tools import Tools

if TYPE_CHECKING:
    from collections.abc import Sequence

GITUTILS: Final = Path(__file__).resolve().parents[2] / "scripts" / "portfolio" / "gitutils.py"
WORKTREE_PREFIX: Final = "story"
PATH_COMPONENT: Final = re.compile(r"[^A-Za-z0-9._-]+")
GIT_OPERATION_SECONDS: Final = 120.0
GIT_OPERATION_MARGIN_SECONDS: Final = 20.0
RUN_OUTPUT: Final = Path(".agent-workforce") / "reports"
"""Transient test reports; the regression runner archives and deletes its own, and none is committed."""


@dataclass(frozen=True, slots=True)
class Workspace:
    """The independently verified Story worktree and its actual branch."""

    tree: Path
    branch: str
    default_branch: str


def git_operation(tools: Tools, stage: str, arguments: list[str]) -> dict[str, JsonValue]:
    """Call the existing git utilities directly and validate their object result.

    The utilities run under a deadline GIT_OPERATION_MARGIN_SECONDS short of the command's own time
    limit, so a git command that runs out of time ends the run with an error that is not retried
    (it may have changed something) instead of the retried command timeout.

    Args:
        tools: The dispatch's command boundary.
        stage: The journal step for attribution.
        arguments: Exact gitutils subcommand arguments.

    Returns:
        The checked utility result.

    Raises:
        TypeError: Arguments violate the operation contract.
        StepError: The utility cannot execute successfully.

    """
    if not isinstance(tools, Tools) or not isinstance(stage, str):
        message: str = "git operation requires Tools and a stage string"
        raise TypeError(message)
    if not arguments or any(not isinstance(argument, str) for argument in arguments):
        message = "git operation requires nonempty string arguments"
        raise TypeError(message)
    deadline: str = str(GIT_OPERATION_SECONDS - GIT_OPERATION_MARGIN_SECONDS)
    result = tools.command(
        [sys.executable, str(GITUTILS), "--deadline-seconds", deadline, *arguments],
        stage=stage,
        timeout=GIT_OPERATION_SECONDS,
    )
    document: dict[str, JsonValue] = json_object(json.loads(result.stdout))
    if document.get("error"):
        message = f"{stage}: {document['error']}"
        raise StepError(stage, OTHER_CAUSE, (message,))
    return document


def provision(tools: Tools, repository: Path, story_id: str) -> Workspace:
    """Create or reuse the Story's own worktree and independently verify its git identity.

    Args:
        tools: The dispatch's command boundary.
        repository: The canonical repository path named by the Story.
        story_id: The parent Story's bead id.

    Returns:
        A verified workspace on the Story's branch.

    Raises:
        TypeError: Inputs or utility fields have invalid types.
        StepError: A git operation fails.

    """
    if not isinstance(repository, Path) or not isinstance(story_id, str):
        message: str = "workspace provision requires a repository Path and Story id"
        raise TypeError(message)
    if not repository.is_absolute() or not repository.is_dir() or not story_id.startswith("ssbd-"):
        message = "workspace provision requires an absolute repository and parent Story id"
        msg = "build:workspace"
        raise StepError(msg, OTHER_CAUSE, (message,))
    tools.git(repository, ["fetch", "origin"], stage="build:workspace")
    tools.git(repository, ["remote", "set-head", "origin", "--auto"], stage="build:workspace")
    integration = tools.git(
        repository,
        ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        stage="build:workspace",
    )
    if integration.stdout.strip() != "origin/develop":
        message = "Story work requires the migrated develop integration branch"
        stage: str = "build:workspace"
        raise StepError(stage, OTHER_CAUSE, (message,))
    name: str = PATH_COMPONENT.sub("-", f"{story_id}-{repository.name}")
    branch: str = f"{WORKTREE_PREFIX}/{story_id}"
    planned: dict[str, JsonValue] = git_operation(
        tools,
        "build:workspace",
        ["provision", "--repo", str(repository), "--branch", branch, "--name", name],
    )
    if planned.get("ok") is not True:
        message = f"Story worktree provision failed: {planned.get('blocked', [])}"
        msg = "build:workspace"
        raise StepError(msg, OTHER_CAUSE, (message,))
    tree: Path = Path(check_type(planned["worktree"], str))
    facts: dict[str, JsonValue] = git_operation(
        tools,
        "build:workspace",
        ["facts", "--path", str(tree), "--repo", str(repository)],
    )
    actual_branch: str = check_type(facts["branch"], str)
    default: str = check_type(facts["defaultBranch"], str)
    if facts.get("sameRepository") is not True or actual_branch != branch or actual_branch == default:
        message = f"Story worktree identity mismatch: {facts}"
        msg = "build:workspace"
        raise StepError(msg, OTHER_CAUSE, (message,))
    return Workspace(tree, actual_branch, default)


def integrate(tools: Tools, workspace: Workspace, stage: str) -> None:
    """Merge the fetched integration branch into the Story branch, so work it waited on is present.

    A Task that waited on a producer Task of another Story in its repository resumes on its own
    Story branch; the producer's commits reach that branch only through ``origin/<default branch>``
    after the producer Story's pull request merged. Uncommitted changes are stashed for the merge and
    restored after it.

    Args:
        tools: The dispatch's command boundary.
        workspace: The verified Story worktree.
        stage: The journal step for attribution.

    Raises:
        StepError: The merge conflicts; it is aborted and the Story branch is left as it was.

    """
    tools.git(workspace.tree, ["fetch", "origin"], stage=stage)
    integration: str = f"origin/{workspace.default_branch}"
    merged = tools.command(
        ["git", "merge", "--no-edit", "--autostash", integration],
        stage=stage,
        cwd=workspace.tree,
        check=False,
    )
    if not merged.exit:
        return
    tools.command(["git", "merge", "--abort"], stage=stage, cwd=workspace.tree, check=False)
    message: str = (
        f"merging {integration} into {workspace.branch} conflicts; the merge was aborted: "
        f"{(merged.stdout + merged.stderr).strip()[-2000:]}"
    )
    raise StepError(stage, OTHER_CAUSE, (message,))


@dataclass(frozen=True, slots=True)
class ToolingOwnership:
    """Canonical paths and mixed-file sections owned by the tooling flow."""

    names: frozenset[str]
    tables: tuple[str, ...]
    sections: tuple[str, ...]
    tsconfig_bases: frozenset[str]


def _ownership() -> ToolingOwnership:
    """Read checker ownership from the configured canonical spec.

    Returns:
        Tooling ownership without importing the checks-sync execution environment.

    """
    config_path: Path = control_repo() / ".polyrepo" / "config.yaml"
    config: dict[str, JsonValue] = json_object(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    settings: dict[str, JsonValue] = json_object(config["checks_sync"])
    spec_path: Path = config_path.parent / check_type(settings["spec_file"], str)
    spec: dict[str, JsonValue] = json_object(yaml.safe_load(spec_path.read_text(encoding="utf-8")))
    technologies: list[dict[str, JsonValue]] = [
        json_object(value) for value in json_object(spec["technologies"]).values()
    ]
    removals: list[dict[str, JsonValue]] = [json_object(entry.get("remove", {})) for entry in technologies]
    canonical: set[str] = {name for entry in technologies for name in json_object(entry.get("files", {}))}
    removed: set[str] = {name for entry in removals for name in check_type(entry.get("files", []), list[str])}
    return ToolingOwnership(
        frozenset({"AGENTS.md", "CLAUDE.md", ".pre-commit-config.yaml", *canonical, *removed}),
        tuple(name for entry in removals for name in check_type(entry.get("pyproject_tables", []), list[str])),
        tuple(name for entry in removals for name in check_type(entry.get("setup_cfg_sections", []), list[str])),
        frozenset(check_type(entry["tsconfig_base"], str) for entry in technologies if entry.get("tsconfig_base")),
    )


def _status_entries(tools: Tools, tree: Path) -> list[str]:
    """Read every porcelain status entry without rename pairing or quoted filename ambiguity.

    Returns:
        Each entry as its two status letters, a space and its path; renames appear as a
        deletion and an addition.

    Raises:
        ValueError: Git reports an unresolved merge.

    """
    raw: str = tools.git(
        tree,
        ["status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all"],
        stage="build:commit",
    ).stdout
    entries: list[str] = [entry for entry in raw.split("\0") if entry]
    conflicts: set[str] = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
    if any(entry[:2] in conflicts for entry in entries):
        problem: str = "Resolve the Story worktree's merge conflicts before checkpointing"
        raise ValueError(problem)
    return entries


def _changed_paths(tools: Tools, tree: Path) -> tuple[str, ...]:
    """Read all changed paths.

    Returns:
        Index, worktree and untracked paths, including both sides of renames.

    """
    return tuple(sorted(entry[3:] for entry in _status_entries(tools, tree)))


def _staged_deletions(tools: Tools, tree: Path) -> frozenset[str]:
    """Read the paths whose deletion is already staged, which ``git add`` no longer matches.

    Returns:
        The paths whose index status is a deletion.

    """
    return frozenset(entry[3:] for entry in _status_entries(tools, tree) if entry[0] == "D")


def _tooling_path(path: str, ownership: ToolingOwnership) -> bool:
    """Identify complete tooling files, including nested instruction and checker files.

    Returns:
        Whether the whole path belongs to Tier 2.

    """
    parts: tuple[str, ...] = Path(path).parts
    names: frozenset[str] = frozenset(Path(name).name for name in ownership.names)
    return bool(set(parts) & {".claude", ".agents", ".beads", ".code-checks"}) or Path(path).name in names


def _pop_table(document: dict[str, JsonValue], dotted: str) -> JsonValue:
    """Remove a named checker table from a parsed mixed configuration.

    Returns:
        The removed table, or None if absent.

    """
    parts: list[str] = dotted.split(".")
    if len(parts) == 1:
        return document.pop(parts[0], None)
    child: JsonValue = document.get(parts[0])
    if not isinstance(child, dict):
        return None
    removed: JsonValue = _pop_table(child, ".".join(parts[1:]))
    if not child:
        document.pop(parts[0], None)
    return removed


def _typescript_parts(text: str, ownership: ToolingOwnership) -> tuple[JsonValue, JsonValue]:
    """Separate canonical checker inheritance from product TypeScript configuration.

    Returns:
        Product settings and the ordered canonical checker bases.

    """
    document: dict[str, JsonValue] = json_object(json.loads(text or "{}"))
    inherited: JsonValue = document.pop("extends", [])
    names: list[str] = [inherited] if isinstance(inherited, str) else check_type(inherited, list[str])
    canonical: frozenset[str] = ownership.tsconfig_bases | frozenset(f"./{name}" for name in ownership.tsconfig_bases)
    checker: list[JsonValue] = [name for name in names if name in canonical]
    product: list[JsonValue] = [name for name in names if name not in canonical]
    if product:
        document["extends"] = product
    return document, checker


def _configuration_parts(path: str, text: str, ownership: ToolingOwnership) -> tuple[JsonValue, JsonValue]:
    """Separate product settings from checker-owned settings without rewriting either.

    Returns:
        Product and tooling values for semantic ownership comparison.

    """
    name: str = Path(path).name
    if name == "tsconfig.json":
        return _typescript_parts(text, ownership)
    if name == "setup.cfg":
        parser: configparser.ConfigParser = configparser.ConfigParser(interpolation=None)
        parser.read_string(text)
        parsed: dict[str, JsonValue] = {section: dict(parser.items(section)) for section in parser.sections()}
        tooling: dict[str, JsonValue] = {
            section: parsed.pop(section)
            for section in tuple(parsed)
            if any(fnmatch.fnmatchcase(section, pattern) for pattern in ownership.sections)
        }
        return parsed, tooling
    if name == "pyproject.toml":
        document: dict[str, JsonValue] = json_object(tomllib.loads(text))
        return document, {table: _pop_table(document, table) for table in ownership.tables}
    document = json_object(yaml.safe_load(text) or {})
    return document, _pop_table(document, "tasks.lint")


def _revision_text(tools: Tools, tree: Path, revision: str, path: str) -> str:
    """Read an existing revision blob; an absent path has empty configuration content.

    Returns:
        Exact revision text, or empty text for a missing path.

    """
    arguments: list[str] = ["ls-tree", "-z", revision, "--", f":(literal){path}"]
    if not revision:
        arguments = ["ls-files", "--stage", "-z", "--", f":(literal){path}"]
    listed: str = tools.git(tree, arguments, stage="build:commit").stdout
    if not listed:
        return ""
    return tools.git(tree, ["show", f"{revision}:{path}"], stage="build:commit").stdout


def _checker_present(path: str, value: JsonValue) -> bool:
    """Distinguish absent checker fields from fields with empty or false settings.

    Returns:
        Whether textual-only changes need ownership resolution.

    """
    if Path(path).name == "pyproject.toml":
        return any(setting is not None for setting in json_object(value).values())
    if Path(path).name in {"Taskfile.yml", "Taskfile.yaml"}:
        return value is not None
    return bool(value)


class OwnershipRefusedError(ValueError):
    """The checkpoint refuses to assign a changed path to the product or to the tooling.

    It is a ``ValueError``, so a checkpoint that does not classify paths one by one still stops on it.
    A configuration file that cannot be read or decoded raises its own error instead.
    """


def _product_path(tools: Tools, tree: Path, path: str, ownership: ToolingOwnership) -> bool:
    """Classify a changed file, refusing to hide product edits inside a mixed file.

    Returns:
        True for product changes; False for preservable tooling-only changes and transient test reports.

    Raises:
        OwnershipRefusedError: Product and tooling changes share a configuration file.

    """
    if _tooling_path(path, ownership) or Path(path).is_relative_to(RUN_OUTPUT):
        return False
    if Path(path).name not in {"pyproject.toml", "setup.cfg", "Taskfile.yml", "Taskfile.yaml", "tsconfig.json"}:
        return True
    if (tree / path).is_symlink():
        problem: str = f"Cannot assign mixed configuration ownership through symlink {path}; resolve its owning flow"
        raise OwnershipRefusedError(problem)
    previous_text: str = _revision_text(tools, tree, "HEAD", path)
    before: tuple[JsonValue, JsonValue] = _configuration_parts(path, previous_text, ownership)
    current: Path = tree / path
    text: str = current.read_text(encoding="utf-8") if current.exists() else ""
    after: tuple[JsonValue, JsonValue] = _configuration_parts(path, text, ownership)
    indexed_text: str = _revision_text(tools, tree, "", path)
    indexed: tuple[JsonValue, JsonValue] = _configuration_parts(path, indexed_text, ownership)
    tooling_changed: bool = before[1] != after[1] or before[1] != indexed[1]
    product_changed: bool = before[0] != after[0] or before[0] != indexed[0]
    if before == after == indexed and _checker_present(path, before[1]):
        problem = f"Text-only edits in mixed configuration {path} need explicit tooling/product ownership before commit"
        raise OwnershipRefusedError(problem)
    if not tooling_changed:
        return True
    if product_changed:
        problem = (
            f"Mixed product and tooling edits in {path}; preserve this work and deliver the tooling "
            "through a separate main worktree, then integrate it into the Story before checkpointing"
        )
        raise OwnershipRefusedError(problem)
    return False


@dataclass(frozen=True, slots=True)
class ToolingPaths:
    """How the build checkpoint treats each changed path of a Story worktree."""

    product: tuple[str, ...]
    """The paths the checkpoint commits on the Story branch."""
    preserved: tuple[str, ...]
    """The tier 2 tooling paths and transient test reports it leaves uncommitted, for delivery through ``main``."""
    refused: tuple[str, ...]
    """Each path whose ownership it refuses to assign, as ``<path>: <reason>``; a checkpoint with one stops."""


def _verdict(tools: Tools, tree: Path, path: str, ownership: ToolingOwnership) -> bool | str:
    """Classify one changed path, turning a refused ownership into its reason.

    A configuration file that cannot be read or decoded is not a refusal: its error propagates.

    Returns:
        True for a product path, False for a preserved one, or the reason its ownership is refused.

    """
    try:
        return _product_path(tools, tree, path, ownership)
    except OwnershipRefusedError as error:
        return str(error)


def classify_tooling_paths(tools: Tools, tree: Path, paths: Sequence[str] | None = None) -> ToolingPaths:
    """Classify the changed paths of a Story worktree by the rule the build checkpoint commits by.

    This is the plugin's one public statement of which changes a build commits and which tooling it
    leaves uncommitted (``AGENTS.md``, ``CLAUDE.md``, ``.claude/``, ``.agents/``, ``.beads/``,
    ``.code-checks/``, the checker files the control repository's checks-sync spec names, checker-only
    edits of a mixed configuration file, and transient test reports). The control repository is read
    from ``ATW_CONTROL_REPO``; a missing variable, unresolved merge conflicts in the worktree, an
    unreadable checks-sync configuration, or a changed configuration file that cannot be read or
    decoded raises the error the step that reads it raises.

    Args:
        tools: The command boundary git runs through.
        tree: The Story worktree.
        paths: Its changed paths, relative to the worktree; None reads them from ``git status``.

    Returns:
        The product, preserved and refused paths.

    """
    ownership: ToolingOwnership = _ownership()
    listed: tuple[str, ...] = _changed_paths(tools, tree) if paths is None else tuple(paths)
    verdicts: list[tuple[str, bool | str]] = [(path, _verdict(tools, tree, path, ownership)) for path in listed]
    return ToolingPaths(
        product=tuple(path for path, verdict in verdicts if verdict is True),
        preserved=tuple(path for path, verdict in verdicts if verdict is False),
        refused=tuple(f"{path}: {verdict}" for path, verdict in verdicts if isinstance(verdict, str)),
    )


def _preserved_state(tools: Tools, tree: Path, paths: tuple[str, ...]) -> str:
    """Fingerprint preserved files and their exact index changes, including symlinks and modes.

    Returns:
        A digest suitable for equality checks across normal commit hooks.

    """
    if not paths:
        return ""
    digest = hashlib.sha256()
    for path in paths:
        full: Path = tree / path
        digest.update(path.encode())
        if not full.exists() and not full.is_symlink():
            digest.update(b"missing")
            continue
        digest.update(str(full.lstat().st_mode).encode())
        digest.update(str(full.readlink()).encode() if full.is_symlink() else full.read_bytes())
    indexed: str = tools.git(
        tree,
        ["diff", "--cached", "--binary", "--no-ext-diff", "--", *[f":(literal){path}" for path in paths]],
        stage="build:commit",
    ).stdout
    digest.update(indexed.encode())
    return digest.hexdigest()


def checkpoint(tools: Tools, workspace: Workspace, message: str) -> str:
    """Commit product paths through normal hooks while preserving unrelated tooling edits.

    Args:
        tools: The dispatch's command boundary.
        workspace: Verified Story worktree.
        message: Task-specific commit message.

    Returns:
        Actual HEAD after the commit, or unchanged HEAD for a clean tree.

    Raises:
        TypeError: Arguments have invalid types.
        StepError: Git or the repository's hooks reject the commit.
        PipelineDefectError: Mixed ownership needs a separate tooling delivery operation.

    """
    if not isinstance(workspace, Workspace) or not isinstance(message, str):
        problem: str = "checkpoint requires a Workspace and commit message"
        raise TypeError(problem)
    facts: dict[str, JsonValue] = git_operation(tools, "build:commit", ["facts", "--path", str(workspace.tree)])
    if facts.get("branch") != workspace.branch or workspace.branch in {workspace.default_branch, "HEAD"}:
        problem = "checkpoint worktree is no longer on its Story branch"
        msg = "build:commit"
        raise StepError(msg, OTHER_CAUSE, (problem,))
    if facts.get("dirty") is not True:
        return check_type(facts["head"], str)
    stage: str = "build:commit"
    try:
        classified: ToolingPaths = classify_tooling_paths(tools, workspace.tree)
        fingerprint: str = _preserved_state(tools, workspace.tree, classified.preserved)
        deleted: frozenset[str] = _staged_deletions(tools, workspace.tree)
    except (OSError, ValueError, KeyError, TypeCheckError, configparser.Error, yaml.YAMLError) as error:
        raise PipelineDefectError(stage, error) from error
    if classified.refused:
        raise PipelineDefectError(stage, ValueError("; ".join(classified.refused)))
    product: tuple[str, ...] = classified.product
    preserved: tuple[str, ...] = classified.preserved
    additions: list[str] = [f":(literal){path}" for path in product if path not in deleted]
    if additions:
        tools.git(workspace.tree, ["add", "--", *additions], stage="build:commit")
    if product:
        pathspecs: list[str] = [f":(literal){path}" for path in product]
        tools.git(workspace.tree, ["commit", "--only", "-m", message, "--", *pathspecs], stage="build:commit")
    after: dict[str, JsonValue] = git_operation(tools, "build:commit", ["facts", "--path", str(workspace.tree)])
    remaining: tuple[str, ...] = _changed_paths(tools, workspace.tree)
    unchanged: bool = _preserved_state(tools, workspace.tree, preserved) == fingerprint
    if after.get("branch") != workspace.branch or remaining != preserved or not unchanged:
        problem = "checkpoint changed preserved tooling or left product changes on the Story worktree"
        msg = "build:commit"
        raise StepError(msg, OTHER_CAUSE, (problem,))
    head: str = check_type(after["head"], str)
    write_json(
        tools.evidence / f"checkpoint-{uuid.uuid4().hex}.json",
        {
            "head": head,
            "productPaths": list(product),
            "preservedToolingPaths": list(preserved),
            "toolingDelivery": "Preserved only; deliver through Tier 2 main and integrate before relying on it",
        },
    )
    return head
