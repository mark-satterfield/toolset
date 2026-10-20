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
KIND_REPOSITORY_DEPRECATED: Final = "repository-deprecated"
"""The kind of the name a deprecated repository is renamed to."""
ROLE_TYPE: Final = "type"
"""The token that says what kind of component a repository holds."""
ROLE_PROJECT: Final = "project"
"""The token that names the project a repository belongs to."""
ROLE_ORIGINAL_NAME: Final = "originalName"
"""The token of a deprecated repository name that holds the name it was made from."""

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


@dataclass(frozen=True, slots=True)
class RepositoryCheck:
    """What `name check-repository` answered for one repository name.

    `kind` is the repository kind the name matched (for example `repository` or
    `repository-deprecated`), None when it matched none; `tokens` maps each token role of the
    match to its value; `problem` joins the violations of a refused name.
    """

    name: str
    valid: bool
    kind: str | None
    tokens: dict[str, str]
    problem: str


def _tokens(matched: Mapping[str, object]) -> dict[str, str]:
    """Map the token roles of a matched kind to their values.

    Returns:
        Each role with its non-empty string value.

    """
    found = matched.get("tokens")
    out: dict[str, str] = {}
    for token in found if isinstance(found, list) else []:
        if isinstance(token, dict):
            role, value = token.get("role"), token.get("value")
            if isinstance(role, str) and isinstance(value, str) and value:
                out[role] = value
    return out


def check_repository(name: str, environ: Mapping[str, str] | None = None) -> RepositoryCheck:
    """Check a repository name and read the kind and tokens it matched.

    Args:
        name: The repository name.
        environ: The environment to read the command from.

    Returns:
        Whether the name is valid, the kind it matched with its tokens, and the violations of a
        refused name.

    """
    answer = run_naming(["name", "check-repository", name], environ)
    matched = answer.document.get("matched")
    if not answer.ok or not isinstance(matched, dict):
        return RepositoryCheck(name, valid=False, kind=None, tokens={}, problem=violations_text(answer.document))
    kind = matched.get("kind")
    return RepositoryCheck(
        name,
        valid=True,
        kind=kind if isinstance(kind, str) else None,
        tokens=_tokens({str(k): v for k, v in matched.items()}),
        problem="",
    )


def deprecated_repository_name(name: str, environ: Mapping[str, str] | None = None) -> str:
    """Return the name a repository takes when it is deprecated.

    Args:
        name: The repository name.
        environ: The environment to read the command from.

    Returns:
        The deprecated repository name the naming command builds from it.

    Raises:
        NamingCommandError: The command refused to build it.

    """
    answer = run_naming(["name", "convert", name, "--to", KIND_REPOSITORY_DEPRECATED], environ)
    value = produced(answer)
    if value is None:
        msg = f"the naming command gives {name} no deprecated name: {violations_text(answer.document)}"
        raise NamingCommandError(msg)
    return value


def type_problem(value: str, environ: Mapping[str, str] | None = None) -> str | None:
    """Check one value as the type token of a repository name.

    Args:
        value: The type, for example `service`.
        environ: The environment to read the command from.

    Returns:
        None when the value is a type the naming command accepts; else its violations.

    """
    answer = run_naming(["token", "check", value, "--role", ROLE_TYPE, "--in", KIND_REPOSITORY], environ)
    return None if answer.ok else violations_text(answer.document) or f"{value!r} is not a repository type"


def repository_type(name: str, environ: Mapping[str, str] | None = None) -> str | None:
    """Read the type token of a repository name that holds a stack.

    Args:
        name: The repository name.
        environ: The environment to read the command from.

    Returns:
        The type token when the name is a valid repository name of kind `repository`
        (project, domain, type); None for any other name.

    """
    check = check_repository(name, environ)
    return check.tokens.get(ROLE_TYPE) if check.kind == KIND_REPOSITORY else None


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
