"""Run a command for a workflow script, and check or write a saved JSON file, checkably.

A workflow script cannot run a command or read a file; a runner session types the command and
copies what it prints. This script is what the session types, for every command other than
`depscore.py` (which carries the same protocol itself). relay.py implements the protocol;
this script only builds each command's view and hands it to relay.py.

Everything it prints is one line, `RELAY64v1:` followed by the base64 of the canonical JSON
envelope. The envelope is flat: each leaf of the command's view under its dotted path (only
booleans, numbers and strings), plus `~exit` (the integer exit status), `~checksum` (the
SHA-256 hex of the canonical `{exit, view}`) and, when a relay file is involved, `~file`,
`~sha256` and `~bytes` (that file's path, SHA-256 hex and size). `run` also writes the relay
file: a JSON object `{command, argvSha256, exitCode, view, result}` holding the full result.

A command line may start with `--argv-sha256 HEX`, the SHA-256 of the canonical JSON array of
the remaining arguments; when it differs, nothing runs and the envelope says why.

Exit statuses: 0 the command ran (a run's own status is `exitCode` in its view); 2 refused or
failed; 3 the command line was typed wrong (`--argv-sha256` mismatch); 4 `read` found no saved
result for this command line.

Commands:

    run --relay FILE [--cwd DIR] [--keys K1,K2] [--tail N] [--timeout S] -- PROGRAM ARG...
        Run PROGRAM (no shell; pass `/bin/sh -c '...'` explicitly when one is needed). The full
        result goes to FILE; stdout parsed as one JSON object is reduced to the top-level KEYS
        when given, and `--tail N` keeps the last N lines of each stream in the view.
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
import subprocess  # ruff: ignore[suspicious-subprocess-import] - The run command executes the workflow's argv without a shell.
import sys
from pathlib import Path

import relay
from contracts import JsonObject, JsonValue, json_object


def _dump(envelope: relay.FlatView) -> None:
    """Print one envelope on one line.

    Args:
        envelope: The sealed envelope.

    """
    sys.stdout.write(relay.line(envelope) + "\n")


def _tail(text: str, n: int) -> str:
    """Return the last `n` lines of a text.

    Args:
        text: The text.
        n: The number of lines.

    Returns:
        Those lines, joined.

    """
    return "\n".join(text.splitlines()[-n:])


def _parsed(text: str) -> JsonObject | None:
    """Stdout parsed, when it is exactly one JSON object.

    Args:
        text: The stdout text.

    Returns:
        The object, or None.

    """
    try:
        value: object = json.loads(text)
    except ValueError:
        return None
    return json_object(value) if isinstance(value, dict) else None


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
        done = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - The workflow's checked argv; shell disabled.
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
    parsed: JsonObject | None = _parsed(out)
    keys: list[str] = [k for k in (args.keys or "").split(",") if k]
    if parsed is not None and keys:
        parsed = {k: parsed.get(k) for k in keys}
    shown: JsonObject = {
        "exitCode": code,
        "json": parsed,
        "stdoutBytes": len(out.encode("utf-8")),
        "stderrBytes": len(err.encode("utf-8")),
    }
    if args.tail:
        shown["stdoutTail"] = _tail(out, args.tail)
        shown["stderrTail"] = _tail(err, args.tail)
    full: JsonObject = {
        "argv": list[JsonValue](argv),
        "cwd": args.cwd,
        "exitCode": code,
        "stdout": out,
        "stderr": err,
        "json": _parsed(out),
    }
    _dump(relay.save("run", full, shown, 0, args.relay))
    return 0


def _canonical_sha(value: JsonValue) -> str:
    """Hash a value's canonical JSON with SHA-256.

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
    shown: JsonObject = {
        "exists": path.is_file(),
        "parsed": False,
        "match": False,
        "sha256": None,
    }
    if path.is_file():
        try:
            value: JsonValue = json.loads(path.read_text(encoding="utf-8"))
        except ValueError, OSError:
            value = None
        else:
            digest: str = _canonical_sha(value)
            shown["parsed"] = True
            shown["sha256"] = digest
            shown["match"] = digest == args.sha256
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
        value: JsonValue = json.loads(args.json)
    except ValueError as exc:
        _dump(
            relay.seal(
                {"written": False, "error": f"--json is not JSON: {exc}"},
                2,
                None,
            ),
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
    """Build the command-line parser.

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    read.add_argument("--for-argv", default="")
    check = sub.add_parser(
        "check-file",
        help="whether a saved JSON file equals a hashed value",
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

    Raises:
        RelayError: A saved relay file records an exit status that is not an integer.

    """
    rest, typed_wrong = relay.argv_mismatch(
        list(sys.argv[1:] if argv is None else argv),
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
        shown: relay.FlatView = relay.read(args.relay, args.sha256, args.bytes, args.for_argv)
    except (relay.RelayError, ValueError, OSError) as exc:
        _dump(relay.seal({"error": str(exc)}, 2, None))
        return 2
    _dump(shown)
    status: relay.FlatScalar = shown["~exit"]
    if isinstance(status, bool) or not isinstance(status, int):
        message: str = f"{args.relay}: the saved relay exit status is not an integer"
        raise relay.RelayError(message)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
