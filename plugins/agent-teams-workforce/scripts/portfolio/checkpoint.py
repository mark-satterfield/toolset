"""Read a workflow's phase checkpoint file and print it as one JSON object.

A workflow script cannot read a file. This is the command its runner session types (through
`relayrun.py run`, which seals the printed object so the workflow checks the session's copy) to
load the checkpoint a composite saved earlier. The checkpoint itself is written with
`relayrun.py write-file`, which writes only the value whose hash the workflow holds.

Commands:

    load --file F
        Print {found, retired, content, error}. `found` is whether F exists; `content` is the
        JSON value F holds (null when F is missing or not JSON, `error` then saying why);
        `retired` is whether F holds `{}`, the value a completed run leaves behind. An empty
        F is found with null content and no error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict

from contracts import JsonValue


class CheckpointLoad(TypedDict):
    """What `load` prints for one checkpoint file."""

    found: bool
    retired: bool
    content: JsonValue
    error: str | None


def _json(value: object) -> JsonValue:
    """Narrow a value `json.loads` returned to a JSON value.

    Args:
        value: The decoded value.

    Returns:
        The same value, typed as JSON.

    Raises:
        TypeError: The value holds something JSON cannot.

    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_json(member) for member in value]
    if isinstance(value, dict):
        result: dict[str, JsonValue] = {}
        for key, member in value.items():
            if not isinstance(key, str):
                msg: str = f"JSON object key {key!r} is not a string"
                raise TypeError(msg)
            result[key] = _json(member)
        return result
    msg = f"{type(value).__name__} is not a JSON value"
    raise TypeError(msg)


def load(path: Path) -> CheckpointLoad:
    """Read the checkpoint at `path`, as the workflow reads it.

    Args:
        path: The checkpoint file.

    Returns:
        {found, retired, content, error}.

    """
    if not path.is_file():
        return {"found": False, "retired": False, "content": None, "error": None}
    try:
        text: str = path.read_text(encoding="utf-8")
        if not text.strip():
            return {"found": True, "retired": False, "content": None, "error": None}
        decoded: object = json.loads(text)
        value: JsonValue = _json(decoded)
    except (OSError, ValueError, TypeError) as exc:
        return {
            "found": True,
            "retired": False,
            "content": None,
            "error": f"{path} is unreadable or not JSON: {exc}",
        }
    return {
        "found": True,
        "retired": value == {},
        "content": value,
        "error": None,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("load", help="print a checkpoint file as JSON")
    read.add_argument("--file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: prints one JSON object on stdout.

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        0.

    Raises:
        TypeError: argparse produced something other than a path for `--file`.

    """
    args: argparse.Namespace = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    file: object = args.file
    if not isinstance(file, Path):
        msg: str = f"--file must be a path, got {type(file).__name__}"
        raise TypeError(msg)
    sys.stdout.write(json.dumps(load(file), separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
