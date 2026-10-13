"""Check the review criteria: one level and one home each, the standard written from them, and who reads them."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Final

import yaml
from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))
from orchestrator.checks.check_support import expected_error, report, require
from review_criteria import (
    CRITERIA_PATH,
    HOMES,
    LEVEL_ALL,
    LEVEL_ARCHITECTURE,
    LEVEL_IMPLEMENTATION,
    LEVEL_TECHNICAL_REQUIREMENT,
    LEVELS,
    SKILL_DIR,
    STANDARD_PATH,
    Criteria,
    ReviewCriteriaError,
    criterion_ids,
    load_criteria,
    parse_criteria,
    render_standard,
)

PLUGIN: Final[Path] = Path(__file__).resolve().parents[2]
SKILL: Final[str] = "agent-teams-workforce:" + SKILL_DIR.name
SKILL_FILE: Final[re.Pattern[str]] = re.compile(re.escape(SKILL_DIR.name) + r"/([A-Za-z0-9._-]+\.(?:md|json))")
CRITERIA_FILES: Final[frozenset[str]] = frozenset({CRITERIA_PATH.name, STANDARD_PATH.name})


def _objects(value: object, where: str) -> list[dict[str, object]]:
    """Narrow a decoded value to a list of objects; ``require`` fails the check for anything else.

    Returns:
        The objects.

    """
    require(isinstance(value, list), f"{where} is not a list")
    result: list[dict[str, object]] = []
    item: object
    for item in value if isinstance(value, list) else []:
        require(isinstance(item, dict), f"{where} holds a value that is not an object")
        if isinstance(item, dict):
            result.append({str(key): entry for key, entry in item.items()})
    return result


def _one_level_one_home(raw: dict[str, object], criteria: Criteria) -> None:
    """Require every criterion to carry exactly one level and, below ``all``, exactly one home."""
    entry: dict[str, object]
    for entry in _objects(raw["criteria"], "criteria"):
        level: object = entry.get("level")
        home: object = entry.get("home")
        require(isinstance(level, str) and level in LEVELS, f"{entry.get('id')}: level is not one level")
        if level == LEVEL_ALL:
            require("home" not in entry, f"{entry.get('id')}: a rule on how to work names no home document")
        else:
            require(isinstance(home, str) and home in HOMES, f"{entry.get('id')}: home is not one home document")
    require(len({item.id for item in criteria.criteria}) == len(criteria.criteria), "a criterion id is repeated")
    homes: dict[str, set[str]] = {}
    for item in criteria.criteria:
        if item.home is not None:
            homes.setdefault(item.level, set()).add(item.home)
    require(all(len(found) == 1 for found in homes.values()), f"a level has more than one home document: {homes}")
    require(
        len({next(iter(found)) for found in homes.values()}) == len(homes),
        f"two levels share a home document: {homes}",
    )


def _refusals(raw: dict[str, object]) -> None:
    """Require the reader to refuse a criterion with two homes, no home, a second copy or no reviewer."""
    two_homes: dict[str, object] = copy.deepcopy(raw)
    no_home: dict[str, object] = copy.deepcopy(raw)
    repeated: dict[str, object] = copy.deepcopy(raw)
    unreviewed: dict[str, object] = copy.deepcopy(raw)
    last: dict[str, object] = _objects(two_homes["criteria"], "criteria")[-1]
    last["home"] = list(HOMES)
    two_homes["criteria"] = [*_objects(two_homes["criteria"], "criteria")[:-1], last]
    dropped: dict[str, object] = _objects(no_home["criteria"], "criteria")[-1]
    del dropped["home"]
    no_home["criteria"] = [*_objects(no_home["criteria"], "criteria")[:-1], dropped]
    entries: list[dict[str, object]] = _objects(repeated["criteria"], "criteria")
    repeated["criteria"] = [*entries, entries[-1]]
    unreviewed["reviewerGroups"] = _objects(unreviewed["reviewerGroups"], "reviewerGroups")[:1]
    probe: dict[str, object]
    for probe in (two_homes, no_home, repeated, unreviewed):
        with expected_error(ReviewCriteriaError):
            parse_criteria(probe)


def _frontmatter_and_body(path: Path) -> tuple[list[str], str]:
    """Read an agent definition's skills and its text after the front matter.

    ``require`` fails the check for a definition with no front matter object.

    Returns:
        The skills the front matter lists, and the body.

    """
    text: str = path.read_text(encoding="utf-8")
    require(text.startswith("---\n") and "\n---" in text[4:], f"{path.name} has no front matter")
    front: str
    body: str
    front, body = text[4:].split("\n---", 1)
    metadata: object = yaml.safe_load(front)
    require(isinstance(metadata, dict), f"{path.name}: front matter is not an object")
    skills: object = metadata.get("skills") if isinstance(metadata, dict) else None
    listed: list[str] = []
    if isinstance(skills, str):
        listed = [item.strip() for item in skills.split(",")]
    elif isinstance(skills, list):
        listed = [str(item).strip() for item in skills]
    return [skill for skill in listed if skill], body


def _readers(criteria: Criteria) -> int:
    """Require every agent that is given the criteria to name a criteria file that exists.

    The skill's own links to the two files are required to resolve as well.

    Returns:
        The number of agent definitions that load the criteria skill.

    """
    skill_text: str = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    link: str
    for link in re.findall(r"\]\(([^)]+)\)", skill_text):
        require((SKILL_DIR / link).is_file(), f"{SKILL_DIR.name}/SKILL.md links to a missing file: {link}")
    require(CRITERIA_PATH.name in skill_text and STANDARD_PATH.name in skill_text, "SKILL.md must name both files")
    named: str
    for named in sorted(criteria.agents()):
        require((PLUGIN / "agents" / f"{named}.md").is_file(), f"the criteria file names no real agent: {named}")
    loaders: int = 0
    path: Path
    for path in sorted((PLUGIN / "agents").glob("*.md")):
        skills: list[str]
        body: str
        skills, body = _frontmatter_and_body(path)
        files: set[str] = set(SKILL_FILE.findall(body))
        missing: list[str] = sorted(name for name in files if not (SKILL_DIR / name).is_file())
        require(not missing, f"{path.name} names a file the {SKILL_DIR.name} skill does not have: {missing}")
        if path.stem in criteria.agents():
            require(SKILL in skills, f"{path.name} is given the criteria and does not load {SKILL}")
        if SKILL in skills:
            loaders += 1
            require(files & CRITERIA_FILES, f"{path.name} loads {SKILL} and names neither criteria file")
    return loaders


def _restated(criteria: Criteria) -> list[str]:
    """Find a criterion whose full text is written in an agent definition or a skill besides the standard.

    Returns:
        ``<file>: <criterion id>`` for each second copy.

    """
    found: list[str] = []
    files: list[Path] = [
        *sorted((PLUGIN / "agents").glob("*.md")),
        *sorted(path for path in (PLUGIN / "skills").rglob("*.md") if path != STANDARD_PATH),
    ]
    path: Path
    for path in files:
        flat: str = " ".join(path.read_text(encoding="utf-8").split())
        found.extend(f"{path.relative_to(PLUGIN)}: {entry.id}" for entry in criteria.criteria if entry.text in flat)
    return found


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Check the criteria file, the standard written from it and the agent definitions that read them."""
    decoded: object = json.loads(CRITERIA_PATH.read_text(encoding="utf-8"))
    require(isinstance(decoded, dict), f"{CRITERIA_PATH} is not a JSON object")
    raw: dict[str, object] = {str(key): value for key, value in decoded.items()} if isinstance(decoded, dict) else {}
    criteria: Criteria = load_criteria()
    _one_level_one_home(raw, criteria)
    _refusals(raw)
    standard: str = STANDARD_PATH.read_text(encoding="utf-8")
    require(standard == render_standard(criteria), f"{STANDARD_PATH.name} differs from what its criteria file produces")
    require(
        criterion_ids(standard) == [entry.id for entry in criteria.criteria],
        f"{STANDARD_PATH.name} does not state each criterion once, in order",
    )
    loaders: int = _readers(criteria)
    restated: list[str] = _restated(criteria)
    require(not restated, f"a criterion is written a second time: {restated}")
    counts: str = ", ".join(
        f"{len(criteria.at_level(level))} {level}"
        for level in (LEVEL_ARCHITECTURE, LEVEL_TECHNICAL_REQUIREMENT, LEVEL_IMPLEMENTATION, LEVEL_ALL)
    )
    report(
        f"PASS: {len(criteria.criteria)} criteria ({counts}), each with one level and one home; "
        f"{STANDARD_PATH.name} matches; {loaders} agent definitions name a criteria file that exists",
    )


if __name__ == "__main__":
    main()
