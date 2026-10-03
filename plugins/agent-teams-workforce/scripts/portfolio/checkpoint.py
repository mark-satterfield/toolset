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


def load(path: Path) -> dict:
    """The checkpoint at `path`, as the workflow reads it.

    Args:
        path: The checkpoint file.

    Returns:
        {found, retired, content, error}.
    """
    if not path.is_file():
        return {"found": False, "retired": False, "content": None, "error": None}
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {"found": True, "retired": False, "content": None, "error": None}
        value = json.loads(text)
    except (OSError, ValueError) as exc:
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
    """The command-line parser.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
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
    """
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    print(json.dumps(load(args.file), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
