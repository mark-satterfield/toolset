"""The skills an Epic's domains need, kept on the Epic's PRD row.

A skill declares what it is expertise for in its own front matter: resource types an Epic's
architecture records, and terms of a PRD. No table of skills exists anywhere else; this module
asks the skills (``orchestrator.core.skills``) and records the answer for an Epic:

- at the start of a run, the skills whose terms occur in the PRD, and the skills for the
  resource types of every element the PRD already reaches (:func:`refresh`);
- during a run, the skills for the resource type of each element the architect records
  (:func:`add_for_types`), so the knowledge is in front of the architect when the need appears.

:func:`skill_text` gives the text of skills in the form a session is handed, and
:func:`hook_output` wraps it as what a Claude Code hook prints to add context to a session.
"""

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import ELEMENT_KINDS, KIND_PRD, Matrix, MatrixError, Node, NodeId
from matrixquery import reached_from
from matrixstore import MatrixRefusedError, Stamp, make_id
from orchestrator.core.frontmatter import split_front_matter, string_list
from orchestrator.core.skills import SkillRoots, load_skills, matching_skills, skills_text

PLUGIN: Final[Path] = Path(__file__).resolve().parents[2]
AGENTS_DIRECTORY: Final = "agents"
AGENT_SUFFIX: Final = ".md"
AGENT_SKILLS_KEY: Final = "skills"
QUALIFIER: Final = ":"
"""What separates a plugin name from the agent or skill name it qualifies."""
CONFIG_ENV: Final = "CLAUDE_CONFIG_DIR"
DEFAULT_CONFIG: Final[tuple[str, ...]] = (".claude",)
SUBAGENT_START: Final = "SubagentStart"
"""The Claude Code hook event whose output adds context to a session an agent starts."""


class Expertise(TypedDict):
    """What ``expertise`` prints."""

    bead: str
    expertise: list[str]
    """The skills recorded for the Epic."""
    added: list[str]
    """The skills this call recorded for the first time."""
    skills: list[str]
    """The skills to hand the session asked about: the Epic's, less those the agent already lists."""
    text: NotRequired[str]


class HookSpecific(TypedDict):
    """The part of a hook's output that adds context."""

    hookEventName: str
    additionalContext: str


class HookOutput(TypedDict):
    """What a Claude Code hook prints to add context to a session."""

    hookSpecificOutput: HookSpecific


def _prd(matrix: Matrix, bead: str) -> Node:
    """Read the PRD row of an Epic.

    Returns:
        The row.

    Raises:
        MatrixRefusedError: The matrix has no PRD row for the Epic.

    """
    key: NodeId = make_id(KIND_PRD, bead) if bead.strip() else NodeId("")
    if key not in matrix["nodes"]:
        message: str = f"the matrix has no PRD row for {bead!r}; sync-prds writes it"
        raise MatrixRefusedError(message)
    return matrix["nodes"][key]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_resource_types(matrix: Matrix, bead: str) -> list[str]:
    """List the resource types of every element an Epic's PRD reaches.

    Args:
        matrix: The matrix.
        bead: The Epic.

    Returns:
        The resource types of the elements that realize the PRD's features and provide the
        shared capabilities those features use, sorted.

    """
    types: set[str] = set()
    key: NodeId
    for key in reached_from(matrix, _prd(matrix, bead)["id"]):
        node: Node = matrix["nodes"][key]
        resource_type: str | None = node.get("resourceType")
        if node["kind"] in ELEMENT_KINDS and resource_type:
            types.add(resource_type)
    return sorted(types)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def skills_for(resource_types: Sequence[str], text: str = "") -> list[str]:
    """Name the skills that declare themselves expertise for some resource types or a text.

    Args:
        resource_types: Resource types an Epic's architecture records.
        text: A text to search for the skills' terms, such as a PRD.

    Returns:
        The matching skills' names, sorted; none when neither a type nor a text is given.

    Raises:
        MatrixError: A skill declares its expertise wrongly.

    """
    if not resource_types and not text.strip():
        return []
    try:
        return list(matching_skills(PLUGIN, list(resource_types), text))
    except (ValueError, TypeError, OSError) as error:
        message: str = f"cannot read what the skills are expertise for: {error}"
        raise MatrixError(message) from error


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def add_skills(matrix: Matrix, bead: str, names: Sequence[str], stamp: Stamp) -> list[str]:
    """Record skills an Epic's domains need on its PRD row.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic.
        names: The skills.
        stamp: The moment and the maker to record when the row changes.

    Returns:
        The skills the row did not hold before, sorted.

    """
    node: Node = _prd(matrix, bead)
    held: list[str] = node.get("expertise", [])
    added: list[str] = sorted(set(names) - set(held))
    if added:
        node["expertise"] = sorted({*held, *added})
        node["changed"] = stamp.change()
    return added


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def add_for_types(matrix: Matrix, bead: str, resource_types: Sequence[str], stamp: Stamp) -> list[str]:
    """Record the skills for resource types an Epic's architect has just recorded.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic.
        resource_types: The resource types of the elements recorded.
        stamp: The moment and the maker to record when the row changes.

    Returns:
        The skills the Epic did not have before, sorted.

    """
    return add_skills(matrix, bead, skills_for(resource_types), stamp)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def refresh(matrix: Matrix, bead: str, prd_text: str, stamp: Stamp) -> Expertise:
    """Bring an Epic's expertise list up to date and return it.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic.
        prd_text: The text of the PRD to search for the skills' terms; empty searches no text.
        stamp: The moment and the maker to record when the row changes.

    Returns:
        The Epic's skills after adding those for the PRD's terms and for the resource types of
        every element the PRD reaches. Skills recorded earlier are kept.

    """
    added: list[str] = add_skills(matrix, bead, skills_for(epic_resource_types(matrix, bead), prd_text), stamp)
    recorded: list[str] = list(_prd(matrix, bead).get("expertise", []))
    return {"bead": bead, "expertise": recorded, "added": added, "skills": recorded}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def agent_skills(agent: str) -> list[str]:
    """List the skills an agent's own definition already gives it.

    Args:
        agent: The agent type, with or without the plugin name in front.

    Returns:
        The names of the skills in the definition's front matter, without a plugin name in front;
        none when this plugin has no definition of that agent.

    Raises:
        MatrixError: The definition cannot be read.

    """
    definition: Path = PLUGIN / AGENTS_DIRECTORY / f"{agent.rpartition(QUALIFIER)[2]}{AGENT_SUFFIX}"
    if not definition.is_file():
        return []
    try:
        front: dict[str, object] = split_front_matter(definition.read_text(encoding="utf-8"), f"agent {agent}")[0]
        return [name.rpartition(QUALIFIER)[2] for name in string_list(front.get(AGENT_SKILLS_KEY))]
    except (ValueError, TypeError, OSError) as error:
        message: str = f"cannot read the skills of the agent {agent}: {error}"
        raise MatrixError(message) from error


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def skill_text(names: Sequence[str], environ: Mapping[str, str]) -> str:
    """Give the text of skills in the form a session is handed.

    Args:
        names: The skills.
        environ: The environment, which names the Claude configuration directory and the
            control repository when they are not the defaults.

    Returns:
        The section of skill text; empty for no skills.

    Raises:
        MatrixError: A skill cannot be found or read.

    """
    if not names:
        return ""
    config: str = environ.get(CONFIG_ENV, "").strip()
    control: str = environ.get(CONTROL_REPO_ENV, "").strip()
    roots: SkillRoots = SkillRoots(
        PLUGIN,
        Path(config).expanduser() if config else Path.home().joinpath(*DEFAULT_CONFIG),
        Path(control).expanduser() if control else None,
    )
    try:
        return skills_text(load_skills(roots, list(names)))
    except (ValueError, TypeError, OSError) as error:
        message: str = f"cannot read the text of the skills {', '.join(names)}: {error}"
        raise MatrixError(message) from error


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def hook_output(text: str, event: str = SUBAGENT_START) -> HookOutput:
    """Wrap text as what a Claude Code hook prints to add it to a session's context.

    Args:
        text: The context to add.
        event: The hook event the output answers.

    Returns:
        The hook output.

    Raises:
        ValueError: ``event`` is empty.

    """
    if not event.strip():
        message: str = "a hook output names the event it answers"
        raise ValueError(message)
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
