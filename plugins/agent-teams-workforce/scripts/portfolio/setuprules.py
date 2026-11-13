"""Decide which regression-run setup commands a build may run, without a model.

A setup prepares a tree for a run and nothing more. It is one of: a task the repository's
Taskfile declares whose commands deploy nothing, call no AWS service other than CodeArtifact and
install no ad-hoc package; a locked install (``npm ci``, ``uv sync --locked`` or ``--frozen``,
``npx playwright install <browser>``); or a read-only presence check (``command -v X``,
``X --version``, ``test -n "$VAR"``). A deploy, an AWS call or an ad-hoc package install is
refused with its own reason, and the packages an ad-hoc install names are reported as undeclared:
the repository declares them in its manifest instead.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import yaml

if TYPE_CHECKING:
    from pathlib import Path

TASKFILES: Final = ("Taskfile.yml", "Taskfile.yaml")
DEPLOY: Final[re.Pattern[str]] = re.compile(r"\bcdk\s+(?:deploy|destroy)\b|\bcdk:(?:deploy|destroy)\b")
AWS_CALL: Final[re.Pattern[str]] = re.compile(r"(?<![\w./=-])aws\s+(?P<service>[a-z0-9-]+)")
REGISTRY_SERVICE: Final = "codeartifact"
"""The one AWS service a repository's own install task may call: its package registry's token."""
AD_HOC_INSTALL: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w./-])(?:npm\s+(?:install|i|add)|yarn\s+add|pnpm\s+(?:add|install)|uv\s+tool\s+install"
    r"|uv\s+pip\s+install|(?:python3?\s+-m\s+)?pip3?\s+install)\b(?P<rest>[^;&|\n]*)",
)
NOT_PACKAGE: Final = frozenset("/{\\")
"""Characters of an install argument that is a path, a Taskfile template or a line continuation, not a package."""
SHELL_OPERATORS: Final[re.Pattern[str]] = re.compile(r"[;&|<>`\n]|\$\(")
LOCKED_UV: Final = frozenset({"--locked", "--frozen"})
BROWSERS: Final = frozenset({"chromium", "chromium-headless-shell", "firefox", "webkit", "chrome", "msedge"})
TASK_DIR_FLAGS: Final = frozenset({"-d", "--dir"})
PRESENCE_TEST: Final[re.Pattern[str]] = re.compile(r'test -n "\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"')


def _form_refusal() -> str:
    """State why a command in none of the allowed forms may not be a setup.

    Returns:
        The reason, naming the allowed forms.

    """
    return (
        "is not an allowed setup: a setup is a task the repository's Taskfile declares, a locked install "
        "(npm ci, uv sync --locked or --frozen, npx playwright install <browser>) or a presence check "
        '(command -v X, X --version, test -n "$VAR")'
    )


@dataclass(frozen=True, slots=True)
class SetupCommand:
    """One setup command of one run, with the repository it runs in."""

    run_id: str
    repo_path: Path
    command: str


@dataclass(frozen=True, slots=True)
class SetupFindings:
    """What the setup rules refuse: one error per refused command, and the packages ad-hoc installs name."""

    errors: tuple[str, ...]
    undeclared: tuple[str, ...]


def _packages(install_rest: str) -> list[str]:
    """Name the packages an ad-hoc install command lists after its verb.

    Returns:
        Each argument that is neither a flag nor a path, a template or a line continuation, in order.

    """
    return [word for word in install_rest.split() if not word.startswith("-") and not set(word) & NOT_PACKAGE]


def _refusal(command: str) -> tuple[str | None, list[str]]:
    """Name why a command may never be a setup, and the packages it would install ad hoc.

    Returns:
        The reason, or None when the command neither deploys, calls AWS nor installs ad hoc; and the
        ad-hoc packages.

    """
    if DEPLOY.search(command):
        return "deploys to AWS: a run that needs deployed resources is phase deployed, run after the deploy", []
    if AWS_CALL.search(command):
        return "calls AWS: a run that needs deployed resources is phase deployed, run after the deploy", []
    installs: list[str] = [name for match in AD_HOC_INSTALL.finditer(command) for name in _packages(match["rest"])]
    if installs:
        return "installs packages ad hoc: the repository declares them in its manifest", installs
    return None, []


def _locked_install(words: list[str]) -> bool:
    """Tell whether a command is a locked install of what the repository declares.

    Returns:
        True for ``npm ci``, ``uv sync`` with ``--locked`` or ``--frozen``, or ``npx playwright install`` of browsers.

    """
    flags: set[str] = {word for word in words[2:] if word.startswith("-")}
    if words[:2] == ["npm", "ci"]:
        return True
    if words[:2] == ["uv", "sync"]:
        return bool(flags & LOCKED_UV) and len(flags) == len(words) - 2
    browsers: list[str] = words[3:]
    return words[:3] == ["npx", "playwright", "install"] and bool(browsers) and set(browsers) <= BROWSERS


def _presence_check(command: str, words: list[str]) -> bool:
    """Tell whether a command only checks that a tool or an environment variable is present.

    Returns:
        True for ``command -v X``, ``X --version`` and ``test -n "$VAR"``.

    """
    match words:
        case ["command", "-v", _] | [_, "--version"]:
            return True
        case _:
            return PRESENCE_TEST.fullmatch(command) is not None


def _task_call(words: list[str], repo: Path) -> tuple[Path, str] | None:
    """Read a ``task <name>`` or ``task -d <path> <name>`` command.

    Returns:
        The directory whose Taskfile declares the task and the task's name, or None when the command is neither.

    """
    match words:
        case ["task", name] if not name.startswith("-"):
            return repo, name
        case ["task", flag, directory, name] if flag in TASK_DIR_FLAGS and not name.startswith("-"):
            return repo / directory, name
        case _:
            return None


def _taskfile_tasks(directory: Path) -> dict[str, object] | None:
    """Read the tasks a directory's Taskfile declares.

    Returns:
        The ``tasks`` mapping, or None when no Taskfile there declares one.

    Raises:
        ValueError: The Taskfile is not valid YAML.

    """
    found: Path | None = next((directory / name for name in TASKFILES if (directory / name).is_file()), None)
    if found is None:
        return None
    try:
        document: object = yaml.safe_load(found.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        message: str = f"Taskfile {found} is not valid YAML"
        raise ValueError(message) from error
    tasks: object = document.get("tasks") if isinstance(document, dict) else None
    return {str(name): body for name, body in tasks.items()} if isinstance(tasks, dict) else None


def _entries(body: object) -> list[object]:
    """List a task's commands and dependencies.

    Returns:
        Its ``cmds``, ``cmd`` and ``deps`` entries; a task written as one list or one string is its commands.

    """
    if isinstance(body, str):
        return [body]
    if isinstance(body, list):
        return list(body)
    if not isinstance(body, dict):
        return []
    return [*_listed(body.get("cmds")), *_listed(body.get("cmd")), *_listed(body.get("deps"))]


def _listed(value: object) -> list[object]:
    """Read one Taskfile field that holds an entry or a list of entries.

    Returns:
        The entries; none when the field is absent.

    """
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _split(entry: object) -> tuple[str, str | None]:
    """Split one command or dependency entry into its shell text and the task it calls.

    Returns:
        The shell text (empty when none) and the called task's name, or None when it calls none.

    """
    if isinstance(entry, str):
        return entry, None
    if not isinstance(entry, dict):
        return "", None
    called: object = entry.get("task")
    shell: object = entry.get("cmd")
    return (shell if isinstance(shell, str) else ""), (called if isinstance(called, str) else None)


def _task_texts(tasks: dict[str, object], name: str) -> list[str]:
    """Collect the shell text a task runs, through every task it calls.

    Returns:
        Each command text, the called tasks' included.

    """
    texts: list[str] = []
    pending: list[str] = [name]
    seen: set[str] = set()
    while pending:
        current: str = pending.pop()
        seen.add(current)
        pairs: list[tuple[str, str | None]] = [_split(entry) for entry in _entries(tasks.get(current))]
        texts.extend(text for text, _ in pairs)
        pending.extend(called for _, called in pairs if called is not None and called not in seen)
    return texts


def _task_refusal(text: str) -> tuple[str | None, list[str]]:
    """Name why a command inside a repository task may not run as a setup.

    The repository's install task may fetch its package registry's token from CodeArtifact.

    Returns:
        The reason, or None when the command is allowed; and the packages it installs ad hoc.

    """
    calls: set[str] = {match["service"] for match in AWS_CALL.finditer(text)}
    reason, packages = _refusal(AWS_CALL.sub("", text) if calls <= {REGISTRY_SERVICE} else text)
    return reason, packages


def _declared_task(words: list[str], repo: Path) -> tuple[str | None, list[str]] | None:
    """Judge a ``task`` setup by what the task it names runs.

    Returns:
        None when the command is no task call; otherwise the refusal reason (None when the task may run)
        and the packages its commands install ad hoc.

    """
    call: tuple[Path, str] | None = _task_call(words, repo)
    if call is None:
        return None
    directory, name = call
    tasks: dict[str, object] | None = _taskfile_tasks(directory)
    if tasks is None or name not in tasks:
        return f"names a task the Taskfile in {directory} does not declare", []
    judged: list[tuple[str | None, list[str]]] = [_task_refusal(text) for text in _task_texts(tasks, name)]
    reason: str | None = next((found for found, _ in judged if found is not None), None)
    return (f"runs a task whose commands {reason}" if reason else None), [name for _, names in judged for name in names]


def _judged(setup: SetupCommand) -> tuple[str | None, list[str]]:
    """Judge one setup command against the rules.

    Returns:
        The refusal reason, or None when the command may run; and the packages it installs ad hoc.

    """
    command: str = setup.command.strip()
    refused, packages = _refusal(command)
    if refused is not None:
        return refused, packages
    if SHELL_OPERATORS.search(command):
        return _form_refusal(), []
    try:
        words: list[str] = shlex.split(command)
    except ValueError:
        return _form_refusal(), []
    task: tuple[str | None, list[str]] | None = _declared_task(words, setup.repo_path)
    if task is not None:
        return task
    allowed: bool = _locked_install(words) or _presence_check(command, words)
    return (None if allowed else _form_refusal()), []


def setup_findings(setups: list[SetupCommand]) -> SetupFindings:
    """Judge every setup command of a plan.

    Args:
        setups: Each run's setup commands, with the repository each runs in.

    Returns:
        One error per refused command, naming its run and the command, and every package an ad-hoc install
        names, each once.

    """
    judged: list[tuple[SetupCommand, str | None, list[str]]] = [(setup, *_judged(setup)) for setup in setups]
    errors: tuple[str, ...] = tuple(
        f"{setup.run_id}: setup `{setup.command}` {reason}" for setup, reason, _ in judged if reason is not None
    )
    undeclared: tuple[str, ...] = tuple(dict.fromkeys(name for _, _, names in judged for name in names))
    return SetupFindings(errors=errors, undeclared=undeclared)
