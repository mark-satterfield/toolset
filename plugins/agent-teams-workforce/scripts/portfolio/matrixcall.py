"""One invocation of ``atw-matrix``: its parsed arguments, the environment it runs in, and what it prints.

``matrix.py`` and ``matrixcli.py`` hold the sub-commands; both read their options through
:class:`Call` and answer with an :class:`Outcome`, so an option is read one way everywhere.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import JsonValue, MatrixError, json_value
from matrixstore import DEFAULT_LOCK_WAIT, MatrixRefusedError, matrix_path

if TYPE_CHECKING:
    import argparse
    from collections.abc import Mapping, Sequence

PROGRAM: Final = "atw-matrix"
EXIT_OK: Final = 0
EXIT_REFUSED: Final = 1
FILE_MARK: Final = "@"
"""What starts an option value that names a file holding the value."""


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one sub-command prints on stdout and the status the process exits with."""

    result: Mapping[str, object]
    status: int = EXIT_OK


@dataclass(frozen=True, slots=True)
class Call:
    """One invocation of the command: its parsed arguments and the environment it runs in."""

    args: argparse.Namespace
    environ: Mapping[str, str]

    def text(self, name: str) -> str | None:
        """Read a string option.

        Returns:
            The option's value, or None when it was not given.

        """
        value: object = getattr(self.args, name, None)
        return value if isinstance(value, str) and value else None

    def required(self, name: str) -> str:
        """Read a string option the sub-command cannot do without.

        Returns:
            The option's value.

        Raises:
            MatrixRefusedError: The option was not given.

        """
        value: str | None = self.text(name)
        if value is None:
            message: str = f"--{name.replace('_', '-')} is required"
            raise MatrixRefusedError(message)
        return value

    def flag(self, name: str) -> bool:
        """Read a flag.

        Returns:
            True when the flag was given.

        """
        return getattr(self.args, name, False) is True

    def texts(self, name: str) -> list[str]:
        """Read an option that takes several strings.

        Returns:
            The strings given; none when the option was not given.

        """
        value: object = getattr(self.args, name, None)
        return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []

    def number(self, name: str) -> int | None:
        """Read an option that takes a whole number.

        Returns:
            The number, or None when the option was not given.

        """
        value: object = getattr(self.args, name, None)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def json(self, name: str) -> JsonValue:
        """Read an option that holds JSON, or names a file that holds it with a leading ``@``.

        Returns:
            The decoded value; None when the option was not given.

        Raises:
            MatrixRefusedError: The value, or the file it names, is not JSON.

        """
        stated: str | None = self.text(name)
        if stated is None:
            return None
        shown: str = f"--{name.replace('_', '-')}"
        try:
            text: str = (
                Path(stated[len(FILE_MARK) :]).expanduser().read_text(encoding="utf-8")
                if stated.startswith(FILE_MARK)
                else stated
            )
            return json_value(json.loads(text))
        except (OSError, json.JSONDecodeError, TypeError) as error:
            message: str = f"{shown} does not hold JSON: {error}"
            raise MatrixRefusedError(message) from error

    def matrix(self) -> Path:
        """Decide which matrix file the sub-command works on.

        Returns:
            The file ``--matrix`` or the environment names.

        """
        return matrix_path(self.text("matrix"), self.environ)

    def lock_wait(self) -> float:
        """Read how long a change waits for the matrix's lock.

        Returns:
            The seconds given with ``--lock-wait``, or the default.

        """
        value: object = getattr(self.args, "lock_wait", None)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else DEFAULT_LOCK_WAIT

    def folder(self, option: str, variables: Sequence[str]) -> Path | None:
        """Find a folder from an option or, when it was not given, from the environment.

        Returns:
            The folder the option names, else the folder the first set variable names, else None.

        """
        stated: str = self.text(option) or next(
            (self.environ[name].strip() for name in variables if self.environ.get(name, "").strip()),
            "",
        )
        return Path(stated).expanduser() if stated else None

    def required_folder(self, option: str, variables: Sequence[str]) -> Path:
        """Find a folder the sub-command cannot do without.

        Returns:
            The folder.

        Raises:
            MatrixRefusedError: Neither the option nor a variable names it.

        """
        folder: Path | None = self.folder(option, variables)
        if folder is None:
            message: str = f"give --{option.replace('_', '-')}, or set {' or '.join(variables)}"
            raise MatrixRefusedError(message)
        return folder


def decoded_file(path: Path, what: str) -> JsonValue:
    """Read a JSON file the caller named.

    Returns:
        The decoded file.

    Raises:
        MatrixError: The file is missing, unreadable or not JSON.

    """
    try:
        return json_value(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError) as error:
        message: str = f"cannot read {what} {path}: {error}"
        raise MatrixError(message) from error
