"""The GitHub repository rulesets every product repository carries, read from the project's ruleset files.

Each file the polyrepo config's `rulesets.files` names is one ruleset as the GitHub REST API takes it
(`name`, `target`, `enforcement`, `conditions`, `rules`, `bypass_actors`). A product repository carries
a ruleset when its workflows define every status check the ruleset requires, so a repository with no
workflow that reports those checks is never given a rule its pull requests could not pass.

The plan is pure: it reads files and compares JSON. Calling GitHub is the caller's.
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Final

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

if TYPE_CHECKING:
    from pathlib import Path

FIELDS: Final[tuple[str, ...]] = ("name", "target", "enforcement", "conditions", "rules", "bypass_actors")
"""The fields of a ruleset the files state and the comparison reads."""

WORKFLOW_GLOBS: Final[tuple[str, ...]] = ("*.yml", "*.yaml")


class RulesetSpecError(Exception):
    """A ruleset file is missing or malformed."""


@dataclasses.dataclass(frozen=True, slots=True)
class RulesetSpec:
    """One ruleset as its file states it."""

    path: Path
    body: dict[str, object]

    @property
    def name(self) -> str:
        """The ruleset's name, its `name` field."""
        return str(self.body["name"])

    def required_checks(self) -> frozenset[str]:
        """Name the status checks the ruleset requires.

        Returns:
            The contexts of its `required_status_checks` rules, empty when it has none.

        """
        found: set[str] = set()
        for rule in _list(self.body.get("rules"), f"{self.path} rules"):
            entry = _dict(rule, f"{self.path} rule")
            if entry.get("type") != "required_status_checks":
                continue
            params = _dict(entry.get("parameters") or {}, f"{self.path} rule parameters")
            checks = _list(params.get("required_status_checks") or [], f"{self.path} required_status_checks")
            found.update(str(_dict(c, f"{self.path} required status check").get("context")) for c in checks)
        return frozenset(found)

    def differs(self, live: dict[str, object]) -> list[str]:
        """Name the fields in which a ruleset on GitHub differs from this one.

        Returns:
            The differing field names, empty when the live ruleset matches.

        """
        return [field for field in FIELDS if _canonical(live.get(field)) != _canonical(self.body.get(field))]


def _dict(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        msg = f"{what}: expected an object"
        raise RulesetSpecError(msg)
    return {str(k): v for k, v in value.items()}


def _list(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        msg = f"{what}: expected a list"
        raise RulesetSpecError(msg)
    return list(value)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def load_rulesets(paths: list[Path]) -> list[RulesetSpec]:
    """Read the ruleset files.

    Returns:
        One spec per file, in the order given.

    Raises:
        RulesetSpecError: when a file is missing, is not JSON, or lacks a field.

    """
    specs: list[RulesetSpec] = []
    for path in paths:
        try:
            raw: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            msg = f"ruleset file {path}: {exc}"
            raise RulesetSpecError(msg) from exc
        body = _dict(raw, f"ruleset file {path}")
        missing = [field for field in FIELDS if field not in body]
        if missing:
            msg = f"ruleset file {path} lacks {', '.join(missing)}"
            raise RulesetSpecError(msg)
        specs.append(RulesetSpec(path, {field: body[field] for field in FIELDS}))
    return specs


def workflow_checks(repo: Path) -> frozenset[str]:
    """Name the status checks a repository's GitHub Actions workflows report: each job's `name`, else its id.

    Returns:
        The check names; empty when the repository has no workflow.

    """
    folder = repo / ".github" / "workflows"
    names: set[str] = set()
    yaml = YAML(typ="safe")
    for pattern in WORKFLOW_GLOBS:
        for path in sorted(folder.glob(pattern)):
            try:
                doc: object = yaml.load(path.read_text(encoding="utf-8"))
            except OSError, YAMLError:
                continue
            jobs = doc.get("jobs") if isinstance(doc, dict) else None
            if not isinstance(jobs, dict):
                continue
            for job_id, job in jobs.items():
                name = job.get("name") if isinstance(job, dict) else None
                names.add(str(name) if isinstance(name, str) else str(job_id))
    return frozenset(names)


def applies(spec: RulesetSpec, checks: frozenset[str]) -> bool:
    """Say whether a repository whose workflows report these checks carries the ruleset.

    Returns:
        True when the workflows report every check the ruleset requires.

    """
    return spec.required_checks() <= checks
