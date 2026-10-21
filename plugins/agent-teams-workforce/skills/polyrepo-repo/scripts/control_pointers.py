"""Find what in a repository's tracked files points back to the control repo.

Every repository is self-contained: the control repo may reach out to it, but nothing in it may name,
call into or climb to the control repo. A pointer is one of:

- an environment variable that names the control repo (the config's `control_pointers.variables`);
- the control repo's absolute path, written out, from the home folder (`~/...`, `$HOME/...`), or after
  any environment variable whose value is a folder above the control repo (`$ROOT/apps/...`);
- a relative path that climbs out of the repository into the control repo (`../<control repo>/...`).

A path counts only when it ends at the control repo's folder name (followed by `/`, a quote, a space or
the end), so a sibling repository whose name begins with the same word is no match. The records the
config's `rename.sweep_exclude` lists (history kept by another tool) are not searched.
"""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed argument list runs git grep
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

GREP_TIMEOUT: Final = 120
GREP_NO_MATCH: Final = 1
BOUNDARY: Final = r"(?=[/\"'`\s):;,]|$)"
VARIABLE_NAME: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ControlPointerError(RuntimeError):
    """`git grep` could not search a repository."""


@dataclasses.dataclass(frozen=True)
class Pointer:
    """One line of a tracked file that points back to the control repo."""

    path: str
    line: int
    text: str


def _variable_forms(name: str) -> list[str]:
    """Return the two ways a shell or a Taskfile writes a variable: `$NAME` and `${NAME`.

    Returns:
        The two prefixes, escaped for a regular expression.

    """
    return [re.escape(f"${name}"), re.escape("${" + name) + r"(?::?[-?=+][^}]*)?\}"]


def patterns(control: Path, variables: Iterable[str], environ: Mapping[str, str]) -> list[re.Pattern[str]]:
    """Build the patterns of every way a file can point at the control repo.

    Args:
        control: The control repo's root.
        variables: The environment variables that name the control repo itself.
        environ: The environment, for the variables whose value is a folder above the control repo.

    Returns:
        The compiled patterns.

    """
    root = control.resolve()
    found: list[str] = [rf"(?<![A-Za-z0-9_]){re.escape(v)}(?![A-Za-z0-9_])" for v in variables]
    found.append(re.escape(root.as_posix()) + BOUNDARY)
    home = Path.home().resolve()
    if root.is_relative_to(home):
        rel = re.escape(root.relative_to(home).as_posix())
        found.extend(f"{prefix}/{rel}{BOUNDARY}" for prefix in (r"~", *_variable_forms("HOME")))
    for name, value in environ.items():
        if not VARIABLE_NAME.match(name) or not value.startswith("/") or name in variables:
            continue
        parent = Path(value).resolve()
        if parent in {root, Path("/"), home} or not root.is_relative_to(parent):
            continue
        rel = re.escape(root.relative_to(parent).as_posix())
        found.extend(f"(?<![A-Za-z0-9_]){prefix}/{rel}{BOUNDARY}" for prefix in _variable_forms(name))
    found.append(r"(?:\.\./)+" + re.escape(root.name) + BOUNDARY)
    return [re.compile(p) for p in found]


def _fixed_strings(control: Path, variables: Iterable[str]) -> list[str]:
    """Return the plain strings every pointer contains, for a fast `git grep -F` pre-filter.

    Returns:
        The control repo's folder name and each variable name.

    """
    return [control.resolve().name, *variables]


def scan(
    repo: Path,
    control: Path,
    pats: list[re.Pattern[str]],
    variables: Iterable[str],
    exclude: Iterable[str],
) -> list[Pointer]:
    """List every tracked line of a repository that points back to the control repo.

    Returns:
        The pointers, in `git grep` order.

    Raises:
        ControlPointerError: when git is missing or `git grep` fails.

    """
    git = shutil.which("git")
    if git is None:
        msg = "git is not on PATH"
        raise ControlPointerError(msg)
    argv = [git, "-C", str(repo), "grep", "-nIF"]
    for s in _fixed_strings(control, variables):
        argv.extend(["-e", s])
    argv.append("--")
    argv.extend(f":(exclude,glob){g}" for g in exclude)
    cp = subprocess.run(argv, capture_output=True, text=True, timeout=GREP_TIMEOUT, check=False)  # ruff: ignore[subprocess-without-shell-equals-true] - fixed argv, no shell
    if cp.returncode not in {0, GREP_NO_MATCH}:
        msg = f"git grep in {repo} exited {cp.returncode}: {cp.stderr.strip()}"
        raise ControlPointerError(msg)
    out: list[Pointer] = []
    for row in cp.stdout.splitlines():
        path, _, rest = row.partition(":")
        number, _, text = rest.partition(":")
        if number.isdigit() and any(p.search(text) for p in pats):
            out.append(Pointer(path, int(number), text.strip()))
    return out


def environment() -> dict[str, str]:
    """Return the process environment, for `patterns`.

    Returns:
        A copy of the environment.

    """
    return dict(os.environ)
