"""The skills an Epic's domains need, kept on the Epic's entry.

A skill declares what it is expertise for in its own front matter: resource types an Epic's
architecture records, and terms of a PRD. No table of skills exists anywhere else; this module
asks the skills (``orchestrator.core.skills``) and records the answer in the ``expertise``
attribute of the Epic's entry:

- :func:`expertise_of` reads the skills recorded for an Epic and changes nothing;
- at the start of a run, :func:`refresh` adds the skills whose terms occur in the PRD and the
  skills for the resource types of every entry the Epic already reaches;
- during a run, :func:`add_for_types` adds the skills for the resource type of each entry the
  architect records, so the knowledge is in front of the architect when the need appears.

:func:`skill_text` gives the text of skills in the form a session is handed, and
:func:`hook_output` wraps it as what a Claude Code hook prints to add context to a session.
"""

import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import KIND_EPIC, Entry, EntryId, JsonValue, MatrixError
from matrixstore import Matrix, MatrixRefusedError
from matrixtraverse import epic_id, epic_reach
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
ATTR_EXPERTISE: Final = "expertise"
ATTR_RESOURCE_TYPE: Final = "resourceType"
ATTR_PRD: Final = "prd"
ATTR_PRD_PATH: Final = "path"


class Expertise(TypedDict):
    """What ``expertise`` prints."""

    epic: EntryId
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


def _epic(matrix: Matrix, bead: str) -> Entry:
    """Read the entry of an Epic.

    An empty beads id raises ``ValueError`` from ``epic_id``.

    Returns:
        The entry.

    Raises:
        MatrixRefusedError: The matrix has no entry for the Epic, or the entry is not an Epic.

    """
    entry: Entry | None = matrix.find(epic_id(bead))
    if entry is None or entry.kind != KIND_EPIC:
        message: str = f"the matrix has no epic entry for {bead!r}; sync-epics writes it"
        raise MatrixRefusedError(message)
    return entry


def _recorded(entry: Entry) -> list[str]:
    """Read the skills an Epic's entry records.

    Returns:
        The skill names of the entry's ``expertise`` attribute, in the order held.

    """
    held: JsonValue = entry.attributes.get(ATTR_EXPERTISE)
    return [name for name in held if isinstance(name, str)] if isinstance(held, list) else []


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def expertise_of(matrix: Matrix, bead: str) -> Expertise:
    """Read the skills recorded for an Epic, and change nothing.

    An Epic the matrix holds no entry for raises ``MatrixRefusedError``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id, or the id of its entry.

    Returns:
        The Epic's skills, with nothing added.

    Raises:
        TypeError: ``bead`` is not a string.

    """
    if not isinstance(bead, str):
        message: str = "an Epic is named by its beads id, a string"
        raise TypeError(message)
    entry: Entry = _epic(matrix, bead)
    recorded: list[str] = _recorded(entry)
    return {"epic": entry.id, "expertise": recorded, "added": [], "skills": list(recorded)}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def epic_resource_types(matrix: Matrix, bead: str) -> list[str]:
    """List the resource types of every entry an Epic reaches.

    An Epic the matrix holds no entry for raises ``MatrixRefusedError``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id, or the id of its entry.

    Returns:
        The resource types stated by the entries the Epic's features reach, on either side, and
        by what those depend on (``matrixtraverse.epic_reach``), sorted.

    Raises:
        TypeError: ``bead`` is not a string.

    """
    if not isinstance(bead, str):
        message: str = "an Epic is named by its beads id, a string"
        raise TypeError(message)
    types: set[str] = set()
    entry_id: EntryId
    for entry_id in epic_reach(matrix, _epic(matrix, bead).id).entries():
        resource_type: JsonValue = matrix.entry(entry_id).attributes.get(ATTR_RESOURCE_TYPE)
        if isinstance(resource_type, str) and resource_type:
            types.add(resource_type)
    return sorted(types)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def prd_text(matrix: Matrix, bead: str, vault: Path) -> str:
    """Read the text of the PRD an Epic's entry names.

    An Epic the matrix holds no entry for raises ``MatrixRefusedError``.

    Args:
        matrix: The matrix.
        bead: The Epic's beads id, or the id of its entry.
        vault: The vault root the entry's PRD path is relative to.

    Returns:
        The PRD file's text; empty when the entry names no PRD.

    Raises:
        TypeError: ``vault`` is not a path.
        MatrixError: The PRD file cannot be read.

    """
    message: str
    if not isinstance(vault, Path):
        message = "the vault root must be a path"
        raise TypeError(message)
    prd: JsonValue = _epic(matrix, bead).attributes.get(ATTR_PRD)
    relative: JsonValue = prd.get(ATTR_PRD_PATH) if isinstance(prd, dict) else None
    if not isinstance(relative, str) or not relative:
        return ""
    file: Path = vault / relative
    try:
        return file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        message = f"cannot read the PRD {file}: {error}"
        raise MatrixError(message) from error


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
def add_skills(matrix: Matrix, bead: str, names: Sequence[str]) -> list[str]:
    """Record skills an Epic's domains need on its entry.

    An Epic the matrix holds no entry for raises ``MatrixRefusedError``. The entry keeps its
    side and everything else it holds.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic's beads id, or the id of its entry.
        names: The skills.

    Returns:
        The skills the entry did not hold before, sorted.

    Raises:
        ValueError: A skill name is empty.

    """
    if not all(name.strip() for name in names):
        message: str = "a skill is recorded by its name, and a name given is empty"
        raise ValueError(message)
    entry: Entry = _epic(matrix, bead)
    held: list[str] = _recorded(entry)
    added: list[str] = sorted(set(names) - set(held))
    if added:
        listed: list[JsonValue] = [*sorted({*held, *added})]
        matrix.put(replace(entry, attributes={**entry.attributes, ATTR_EXPERTISE: listed}))
    return added


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def add_for_types(matrix: Matrix, bead: str, resource_types: Sequence[str]) -> list[str]:
    """Record the skills for resource types an Epic's architect has just recorded.

    An Epic the matrix holds no entry for raises ``MatrixRefusedError``.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic's beads id, or the id of its entry.
        resource_types: The resource types of the entries recorded.

    Returns:
        The skills the Epic did not have before, sorted.

    """
    return add_skills(matrix, bead, skills_for(resource_types))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def refresh(matrix: Matrix, bead: str, text: str = "") -> Expertise:
    """Bring an Epic's expertise list up to date and return it.

    An Epic the matrix holds no entry for raises ``MatrixRefusedError``.

    Args:
        matrix: The matrix, changed in place.
        bead: The Epic's beads id, or the id of its entry.
        text: The text of the PRD to search for the skills' terms (:func:`prd_text`); empty
            searches no text.

    Returns:
        The Epic's skills after adding those for the PRD's terms and for the resource types of
        every entry the Epic reaches. Skills recorded earlier are kept.

    """
    added: list[str] = add_skills(matrix, bead, skills_for(epic_resource_types(matrix, bead), text))
    entry: Entry = _epic(matrix, bead)
    recorded: list[str] = _recorded(entry)
    return {"epic": entry.id, "expertise": recorded, "added": added, "skills": list(recorded)}


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
