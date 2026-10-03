"""Run a command for a workflow script, and check or write a saved JSON file, checkably.

A workflow script cannot run a command or read a file; a runner session types the command and
copies what it prints. This script is what the session types, for every command other than
`depscore.py` (which carries the same protocol itself). It takes, first, `--argv-sha256 HEX`: the
SHA-256 of the canonical JSON of the argument list after it, so a command line typed differently
from the one the workflow built is refused (exit 3) before anything runs. Everything it prints is
one sealed, flat envelope line (see relay.py): the facts, plus `~exit`, `~checksum` and the
relay file's `~file`, `~sha256`, `~bytes`, which the workflow checks the session's copy against.

Commands:

    run --relay FILE [--cwd DIR] [--keys K1,K2] [--tail N] [--timeout S] -- PROGRAM ARG...
        Run PROGRAM (no shell; pass `/bin/sh -c '...'` explicitly when one is needed). The full
        stdout, stderr and exit status go to FILE; the view carries `exitCode`, `json` (stdout
        parsed when it is one JSON object, reduced to the top-level KEYS when given; else null),
        `stdoutBytes`, `stderrBytes`, and with `--tail N` the last N lines of each.
    read --relay FILE [--sha256 HEX] [--bytes N]
        Print the envelope saved in FILE again, re-running nothing. Optional receipt checks
        refuse a stale or changed file instead of substituting it for the original result.
    check-file --file F --sha256 HEX
        Whether F holds JSON whose canonical form hashes to HEX (`match`), as a workflow checks a
        file a session saved against the schema-validated result the session returned.
    write-file --file F --sha256 HEX --json TEXT
        Write TEXT (pretty-printed) to F, only when its canonical form hashes to HEX.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import relay


def _dump(envelope: dict) -> None:
    """Print one envelope on one line.

    Args:
        envelope: The sealed envelope.
    """
    print(relay.line(envelope))


def _tail(text: str, n: int) -> str:
    """The last `n` lines of a text.

    Args:
        text: The text.
        n: The number of lines.

    Returns:
        Those lines, joined.
    """
    return "\n".join(text.splitlines()[-n:])


def _parsed(text: str) -> dict | None:
    """Stdout parsed, when it is exactly one JSON object.

    Args:
        text: The stdout text.

    Returns:
        The object, or None.
    """
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _run(args: argparse.Namespace) -> int:
    """Run the child command and print its sealed view.

    Args:
        args: The parsed arguments.

    Returns:
        0 when the child ran (its status is in the view), 2 when it could not be started.
    """
    argv = list(args.argv)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        _dump(relay.seal({"error": "run names no program"}, 2, None))
        return 2
    try:
        done = subprocess.run(
            argv,
            cwd=args.cwd,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
        code, out, err = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = f"timed out after {args.timeout} s"
    except OSError as exc:
        _dump(relay.seal({"error": f"cannot run {argv[0]}: {exc}"}, 2, None))
        return 2
    parsed = _parsed(out)
    keys = [k for k in (args.keys or "").split(",") if k]
    if parsed is not None and keys:
        parsed = {k: parsed.get(k) for k in keys}
    shown: dict = {
        "exitCode": code,
        "json": parsed,
        "stdoutBytes": len(out.encode("utf-8")),
        "stderrBytes": len(err.encode("utf-8")),
    }
    if args.tail:
        shown["stdoutTail"] = _tail(out, args.tail)
        shown["stderrTail"] = _tail(err, args.tail)
    full = {
        "argv": argv,
        "cwd": args.cwd,
        "exitCode": code,
        "stdout": out,
        "stderr": err,
        "json": _parsed(out),
    }
    _dump(relay.save("run", full, shown, 0, args.relay))
    return 0


def _canonical_sha(value: object) -> str:
    """The SHA-256 of a value's canonical JSON.

    Args:
        value: A JSON value.

    Returns:
        The hex digest.
    """
    return hashlib.sha256(relay.canonical(value).encode("ascii")).hexdigest()


def _check_file(args: argparse.Namespace) -> int:
    """Print whether a saved JSON file equals the value its hash names.

    Args:
        args: The parsed arguments.

    Returns:
        0.
    """
    path: Path = args.file
    shown: dict = {
        "exists": path.is_file(),
        "parsed": False,
        "match": False,
        "sha256": None,
    }
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            value = None
        else:
            shown["parsed"] = True
            shown["sha256"] = _canonical_sha(value)
            shown["match"] = shown["sha256"] == args.sha256
    _dump(relay.seal(shown, 0, None))
    return 0


def _write_file(args: argparse.Namespace) -> int:
    """Write a JSON value to a file, only when it hashes to the value the workflow holds.

    Args:
        args: The parsed arguments.

    Returns:
        0 when written, 2 when refused.
    """
    try:
        value = json.loads(args.json)
    except ValueError as exc:
        _dump(
            relay.seal(
                {"written": False, "error": f"--json is not JSON: {exc}"}, 2, None
            )
        )
        return 2
    got = _canonical_sha(value)
    if got != args.sha256:
        why = f"--json hashes to {got}, not {args.sha256}: it was not typed as built"
        _dump(relay.seal({"written": False, "error": why}, 2, None))
        return 2
    args.file.parent.mkdir(parents=True, exist_ok=True)
    args.file.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    _dump(relay.seal({"written": True, "sha256": got}, 0, None))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The command-line parser.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a command and relay its result")
    run.add_argument("--relay", type=Path, required=True)
    run.add_argument("--cwd", default=None)
    run.add_argument("--keys", default="")
    run.add_argument("--tail", type=int, default=0)
    run.add_argument("--timeout", type=float, default=None)
    run.add_argument("argv", nargs=argparse.REMAINDER)
    read = sub.add_parser("read", help="print a saved envelope again")
    read.add_argument("--relay", type=Path, required=True)
    read.add_argument("--sha256", default="")
    read.add_argument("--bytes", type=int, default=None)
    check = sub.add_parser(
        "check-file", help="whether a saved JSON file equals a hashed value"
    )
    check.add_argument("--file", type=Path, required=True)
    check.add_argument("--sha256", required=True)
    write = sub.add_parser("write-file", help="write a JSON value that hashes as given")
    write.add_argument("--file", type=Path, required=True)
    write.add_argument("--sha256", required=True)
    write.add_argument("--json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point: prints one sealed envelope.

    Args:
        argv: The command line, or None for `sys.argv`.

    Returns:
        The exit status: 0, 2 (refused or failed), 3 (command line typed wrong), 4 (no saved
        result to read).
    """
    rest, typed_wrong = relay.argv_mismatch(
        list(sys.argv[1:] if argv is None else argv)
    )
    if typed_wrong:
        _dump(relay.mismatch_envelope(typed_wrong))
        return 3
    args = build_parser().parse_args(rest)
    if args.command == "run":
        return _run(args)
    if args.command == "check-file":
        return _check_file(args)
    if args.command == "write-file":
        return _write_file(args)
    try:
        shown = relay.read(args.relay, args.sha256, args.bytes)
    except (relay.RelayError, ValueError, OSError) as exc:
        _dump(relay.seal({"error": str(exc)}, 2, None))
        return 2
    _dump(shown)
    return shown["~exit"]


if __name__ == "__main__":
    raise SystemExit(main())
