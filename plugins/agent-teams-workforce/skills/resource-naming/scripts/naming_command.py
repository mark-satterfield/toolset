"""Run the project's naming command: the plugin's one way to build, convert or check a name.

The plugin holds no naming rule, pattern or token list. Every name it needs comes from the
command the project names in `$ATW_NAMING_COMMAND`: an executable (a name on `PATH`, or an
absolute path) that implements the `resource-naming` command line, whose contract is its
commands and options, its JSON documents and its exit codes:

- exit 0: the value was produced, or the name is valid;
- exit 1: refused or invalid; the JSON document lists the violations;
- exit 2: a usage error (unknown command, kind, role or option);
- exit 70: an internal error of the command.

Every call here adds `--json` and reads the one JSON document the command prints on stdout.
The module uses the standard library only, so every plugin script can import it.
"""

from __future__ import annotations

import json
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs the configured naming command with list argv and no shell
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

NAMING_COMMAND_ENV: Final = "ATW_NAMING_COMMAND"
"""The environment variable that names the project's naming command."""
NAMING_TIMEOUT: Final = 60
"""Seconds one call of the naming command may take."""
EXIT_DONE: Final = 0
EXIT_REFUSED: Final = 1
"""The naming command's exit codes for a produced value or valid name, and for a refusal."""
KIND_REPOSITORY: Final = "repository"
"""The kind of a repository name of the form project, domain, type: the one kind that holds a stack."""
ROLE_TYPE: Final = "type"
"""The token that says what kind of component a repository holds."""

type JsonObject = dict[str, object]


class NamingCommandError(Exception):
    """The naming command is not configured, could not run, or did not answer by its contract."""


@dataclass(frozen=True, slots=True)
class NamingAnswer:
    """What one call of the naming command answered: whether it produced or passed, and its document."""

    ok: bool
    document: JsonObject


@dataclass(frozen=True, slots=True)
class RepositoryNames:
    """The names a repository name determines, as the naming command gives them.

    `component_type` is the repository's type token (for example `service` or `lib`); the stack
    names are None when the command gives the repository no stack.
    """

    repository: str
    component_type: str
    cdk_stack: str | None
    cdk_stack_file: str | None
    python_source_package: str
    python_import_package: str
    python_distribution: str


def naming_command(environ: Mapping[str, str] | None = None) -> str:
    """Return the naming command the project configured.

    Args:
        environ: The environment to read; the process environment when None.

    Returns:
        The command `$ATW_NAMING_COMMAND` names.

    Raises:
        NamingCommandError: No naming command is configured.

    """
    command = (os.environ if environ is None else environ).get(NAMING_COMMAND_ENV, "").strip()
    if not command:
        msg = (
            f"no naming command is configured: ${NAMING_COMMAND_ENV} is not set; set it to the command "
            "that runs the project's resource-naming command line"
        )
        raise NamingCommandError(msg)
    return command


def run_naming(args: Sequence[str], environ: Mapping[str, str] | None = None) -> NamingAnswer:
    """Run the naming command once with `--json` and read its answer.

    Args:
        args: The command's arguments, for example `["name", "repository-names", "SkillSpoke-auth-service"]`.
        environ: The environment to read the command from; the process environment when None.

    Returns:
        Whether the command produced the value or found the name valid (exit 0) or refused it
        (exit 1), with the JSON document it printed.

    Raises:
        NamingCommandError: The command is not configured, cannot run, exits with any other
            status, or prints no JSON object.

    """
    command = naming_command(environ)
    argv = [command, *args, "--json"]
    shown = " ".join([NAMING_COMMAND_ENV, *args])
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=NAMING_TIMEOUT, check=False)  # ruff: ignore[subprocess-without-shell-equals-true] - list argv, no shell
    except (OSError, subprocess.TimeoutExpired) as exc:
        msg = f"the naming command {command!r} could not run: {exc}"
        raise NamingCommandError(msg) from exc
    if cp.returncode not in {EXIT_DONE, EXIT_REFUSED}:
        detail = (cp.stderr or cp.stdout).strip().splitlines()
        msg = f"{shown} failed with exit status {cp.returncode}: {detail[-1] if detail else 'no output'}"
        raise NamingCommandError(msg)
    try:
        document: object = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        msg = f"{shown} printed no JSON document: {exc}"
        raise NamingCommandError(msg) from exc
    if not isinstance(document, dict):
        msg = f"{shown} printed JSON that is not an object"
        raise NamingCommandError(msg)
    return NamingAnswer(cp.returncode == EXIT_DONE, {str(k): v for k, v in document.items()})


def violations_text(document: Mapping[str, object]) -> str:
    """Join the messages of a document's violations into one line.

    Returns:
        The messages, each with its rule id, separated by `; `; empty when there are none.

    """
    found = document.get("violations")
    if not isinstance(found, list):
        return ""
    return "; ".join(f"[{v.get('rule')}] {v.get('message')}" for v in found if isinstance(v, dict))


def _text(document: Mapping[str, object], key: str) -> str | None:
    """Read a non-empty string field of a document.

    Returns:
        The string, or None.

    """
    value = document.get(key)
    return value if isinstance(value, str) and value else None


def produced(answer: NamingAnswer, key: str = "name") -> str | None:
    """Read the value a producing command gave.

    Args:
        answer: The answer of a `name build`, `name convert` or `name swap` call.
        key: The field that holds the value.

    Returns:
        The value, or None when the command refused.

    """
    return _text(answer.document, key) if answer.ok else None


def repository_type(name: str, environ: Mapping[str, str] | None = None) -> str | None:
    """Read the type token of a repository name that holds a stack.

    Args:
        name: The repository name.
        environ: The environment to read the command from.

    Returns:
        The type token when the name is a valid repository name of kind `repository`
        (project, domain, type); None for any other name.

    """
    answer = run_naming(["name", "check-repository", name], environ)
    matched = answer.document.get("matched")
    if not answer.ok or not isinstance(matched, dict) or matched.get("kind") != KIND_REPOSITORY:
        return None
    tokens = matched.get("tokens")
    for token in tokens if isinstance(tokens, list) else []:
        if isinstance(token, dict) and token.get("role") == ROLE_TYPE:
            value = token.get("value")
            return value if isinstance(value, str) and value else None
    return None


def repository_names(name: str, environ: Mapping[str, str] | None = None) -> RepositoryNames | None:
    """Read the names a repository name determines.

    Args:
        name: The repository name.
        environ: The environment to read the command from.

    Returns:
        The names, or None when the name is not a valid repository name of kind `repository`.

    Raises:
        NamingCommandError: The command answered a valid repository name without the Python names.

    """
    component_type = repository_type(name, environ)
    if component_type is None:
        return None
    answer = run_naming(["name", "repository-names", name], environ)
    if not answer.ok:
        return None
    doc = answer.document
    source, package, distribution = (
        _text(doc, "pythonSourcePackage"),
        _text(doc, "pythonImportPackage"),
        _text(doc, "pythonDistribution"),
    )
    if source is None or package is None or distribution is None:
        msg = f"the naming command gave {name} no Python names"
        raise NamingCommandError(msg)
    return RepositoryNames(
        name,
        component_type,
        _text(doc, "cdkStack"),
        _text(doc, "cdkStackFile"),
        source,
        package,
        distribution,
    )
