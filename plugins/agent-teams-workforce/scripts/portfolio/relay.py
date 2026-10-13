r"""Carry depscore.py results to a workflow script, and its commands from it, checkably.

A workflow script cannot read a file or run a command: a command reaches the shell only as
text a runner session types, and its result reaches the script only as the structured return
of that session. A model copying text does not reliably copy it unaltered, so neither copy is
trusted; both are checked deterministically:

- `--argv-sha256 HEX` (first on the command line): the SHA-256 of the canonical JSON of the
  argument list after it. A command line typed differently from the one the script built is
  refused with exit 3 before anything runs.
- `--relay FILE`: the full result is written to FILE as `{"command": ..., "result": ...}`, and
  stdout carries only the result's relay VIEW, the few facts the script branches on (see
  `view`), flattened to one object of scalars (`flatten`), plus `~file`,
  `~sha256`, `~bytes` (FILE's path, SHA-256 and size), `~exit` and `~checksum`, the SHA-256 of
  the canonical JSON of `{exit, view}`; its canonical ASCII JSON is base64-encoded after
  `RELAY64v1:` on one line (`line`). The runner returns that line verbatim; the script parses
  it, recomputes the checksum, accepts only an exact copy and never retries a mismatch.
  Sessions that need the details are given FILE's path.

The canonical form is ASCII only (every other character a `\uXXXX` escape of its UTF-16
units), keys sorted, no whitespace, numbers spelled as JavaScript spells them, so this module
and the workflow script produce the same bytes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import operator
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from contracts import JsonInput, JsonObject, JsonValue, json_object
from typeguard import TypeCheckError

type FlatScalar = bool | int | float | str
type FlatView = dict[str, FlatScalar]

_SHORT: Final[dict[str, str]] = {
    '"': '\\"',
    "\\": "\\\\",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}
_ASCII_LIMIT: Final[int] = 0x80
_PRINTABLE_FIRST: Final[int] = 0x20
_PRINTABLE_LAST: Final[int] = 0x7E
_PLAIN_INTEGER_LIMIT: Final[float] = 1e21
_PLAIN_DIGITS: Final[int] = 21
_SMALL_EXPONENT: Final[int] = -6
_MISSING_EXIT: Final[int] = 4
_MISMATCH_EXIT: Final[int] = 3


class RelayError(ValueError):
    """A relay file that cannot be read back, or a value with no canonical spelling."""


def _string(text: str) -> str:
    """Spell a string as canonical JSON: ASCII only, as JavaScript would escape it.

    Returns:
        The quoted, escaped string.

    """
    out: list[str] = ['"']
    data: bytes = text.encode("utf-16-be", "surrogatepass")
    for i in range(0, len(data), 2):
        unit: int = (data[i] << 8) | data[i + 1]
        ch: str = chr(unit) if unit < _ASCII_LIMIT else ""
        if ch and ch in _SHORT:
            out.append(_SHORT[ch])
        elif _PRINTABLE_FIRST <= unit <= _PRINTABLE_LAST:
            out.append(ch)
        else:
            out.append(f"\\u{unit:04x}")
    out.append('"')
    return "".join(out)


def _number(x: float) -> str:
    """Spell a float as JavaScript's `String(x)` does.

    Returns:
        Its JavaScript spelling.

    Raises:
        RelayError: For NaN or an infinity, which JSON cannot carry.

    """
    if math.isnan(x) or math.isinf(x):
        message: str = f"{x} has no JSON spelling"
        raise RelayError(message)
    if x == int(x) and abs(x) < _PLAIN_INTEGER_LIMIT:
        return str(int(x))
    sign: str = "-" if x < 0 else ""
    mantissa, _, exp = repr(abs(x)).partition("e")
    whole, _, frac = mantissa.partition(".")
    raw: str = whole + frac
    point: int = len(whole) + int(exp or 0)
    lead: int = len(raw) - len(raw.lstrip("0"))
    digits: str = raw.strip("0")
    n: int = point - lead
    k: int = len(digits)
    body: str
    if k <= n <= _PLAIN_DIGITS:
        body = digits + "0" * (n - k)
    elif 0 < n <= _PLAIN_DIGITS:
        body = f"{digits[:n]}.{digits[n:]}"
    elif _SMALL_EXPONENT < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e: int = n - 1
        body = digits[0] + (f".{digits[1:]}" if k > 1 else "") + f"e{'+' if e >= 0 else '-'}{abs(e)}"
    return sign + body


def canonical(value: JsonInput) -> str:
    """Spell a JSON value canonically: sorted keys, no whitespace, ASCII only.

    Returns:
        Its canonical JSON text.

    Raises:
        RelayError: For a value JSON cannot carry, including an object key that is not text.

    """
    if value is None or isinstance(value, bool):
        return {None: "null", True: "true", False: "false"}[value]
    if isinstance(value, int):
        return str(int(value))
    if isinstance(value, float):
        return _number(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, Mapping):
        members: list[tuple[str, JsonInput]] = []
        for key, member in value.items():
            if not isinstance(key, str):
                message: str = f"a {type(key).__name__} object key has no JSON spelling"
                raise RelayError(message)
            members.append((key, member))
        members.sort(key=operator.itemgetter(0))
        return "{" + ",".join(f"{_string(key)}:{canonical(member)}" for key, member in members) + "}"
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return "[" + ",".join(canonical(member) for member in value) + "]"
    message = f"a {type(value).__name__} has no JSON spelling"
    raise RelayError(message)


def _counted(result: JsonObject, keys: tuple[str, ...]) -> JsonObject:
    """Return a result with the named lists replaced by their lengths.

    Returns:
        The reduced copy.

    """
    return {k: (len(v) if k in keys and isinstance(v, list) else v) for k, v in result.items()}


#: Per command, the lists its relay view carries as counts; the names stay in the relay file.
COUNTED: Final[dict[str, tuple[str, ...]]] = {
    "arch-approve": ("promoted", "unchanged", "noFrontmatter", "wouldApprove"),
}


#: Keys no workflow reads that depscore.py echoes back (the data source, warnings, the
#: dry-run plan, the command's own name): left out of every view, kept in the relay file.
ECHOED: Final[tuple[str, ...]] = ("source", "warnings", "planned", "command", "dryRun")
#: Per command, the only top-level keys its view carries, when a workflow reads few of many.
WHITELIST: Final[dict[str, tuple[str, ...]]] = {
    "elaboration-start": ("ok", "refusal", "owner", "previousState"),
    "elaboration-finish": ("ok", "lifecycle", "summary", "storyEdges"),
}


def _require_object(value: object, name: str) -> None:
    """Refuse a relay argument that is not a JSON object with text keys.

    Raises:
        TypeError: The value is not a dict keyed by text.

    """
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        message: str = f"{name} must be a JSON object keyed by text"
        raise TypeError(message)


def view(command: str, result: JsonObject) -> JsonObject:
    """Select the part of a command's result the workflow script receives.

    Returns:
        For an error, only the error; for a command in
        WHITELIST, those keys; for a command in COUNTED, its lists as counts; for
        `arch-snapshot --counts`, each diff's lists as counts; otherwise the result without
        the ECHOED keys.

    Raises:
        TypeError: The command is not text or the result is not a JSON object.

    """
    if not isinstance(command, str):
        message: str = "relay view command must be text"
        raise TypeError(message)
    _require_object(result, "relay result")
    error: JsonValue = result.get("error")
    if error:
        return {"error": error}
    if command in WHITELIST:
        return {k: result[k] for k in WHITELIST[command] if k in result}
    out: JsonObject = {k: v for k, v in result.items() if k not in ECHOED}
    if command in COUNTED:
        return _counted(out, COUNTED[command])
    if command == "arch-snapshot" and result.get("countsOnly"):
        listed: JsonValue = result.get("diffs") or []
        diffs: list[JsonValue] = [
            _counted(d, ("created", "changed", "deleted"))
            for d in (listed if isinstance(listed, list) else [])
            if isinstance(d, dict)
        ]
        return out | {"diffs": diffs}
    return out


def _segment(key: str) -> str:
    """Escape one path segment of a flat key: `~` written `~0` and `/` written `~1`.

    Returns:
        The escaped segment.

    """
    return key.replace("~", "~0").replace("/", "~1")


def _words(value: list[JsonValue]) -> list[str] | None:
    """Return a non-empty list of non-empty comma-free strings as text, else None.

    Returns:
        The strings, or None when the list does not qualify.

    """
    words: list[str] = [member for member in value if isinstance(member, str) and member and "," not in member]
    return words if value and len(words) == len(value) else None


def flatten(shown: JsonObject) -> FlatView:
    """Flatten a view to one object of scalars, so a runner copies one line of plain values.

    Each scalar leaf is keyed by its path, segments joined by `/` (see `_segment`). A nested
    object, list or null is marked by a key ending in `/~{}` (its key count), `/~#` (its length)
    or `/~null` (1), and a non-empty list of non-empty strings without commas is one key ending
    in `/~,` holding them comma-joined, so the workflow rebuilds the view exactly, empty ones
    included. Keys starting with `~` at the top level are the relay's own.

    Returns:
        The flat view.

    Raises:
        TypeError: The view is not a JSON object keyed by text.

    """
    if not isinstance(shown, dict) or any(not isinstance(key, str) for key in shown):
        message: str = "relay view must be a JSON object keyed by text"
        raise TypeError(message)
    out: FlatView = {}
    _walk(shown, "", out)
    return out


def _walk(value: JsonValue, path: str, out: FlatView) -> None:
    """Add the flat keys of one value at one path to `out` (see `flatten`).

    Raises:
        TypeError: The value holds something JSON cannot carry.

    """

    def join(seg: str) -> str:
        return f"{path}/{seg}" if path else seg

    if isinstance(value, dict):
        if path:
            out[join("~{}")] = len(value)
        for k, v in value.items():
            _walk(v, join(_segment(k)), out)
    elif isinstance(value, list):
        words: list[str] | None = _words(value)
        if words is not None:
            out[join("~,")] = ",".join(words)
            return
        out[join("~#")] = len(value)
        for i, v in enumerate(value):
            _walk(v, join(str(i)), out)
    elif value is None:
        out[join("~null")] = 1
    elif isinstance(value, (bool, int, float, str)):
        out[path] = value
    else:
        message: str = f"a {type(value).__name__} has no flat relay spelling"
        raise TypeError(message)


def checksum(flat: Mapping[str, FlatScalar], exit_code: int) -> str:
    """Hash a relayed flat view as the workflow checks it: the canonical `{exit, view}`.

    Returns:
        The lower-case hex digest.

    Raises:
        TypeError: The exit status is not an exact integer.

    """
    if type(exit_code) is not int:
        message: str = "relay exit status must be an exact integer"
        raise TypeError(message)
    text: str = canonical({"exit": exit_code, "view": flat})
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def seal(shown: JsonObject, exit_code: int, path: Path | None) -> FlatView:
    """Build the object printed on stdout: the flat view with the relay's own keys.

    Returns:
        The flat envelope: the view's leaves plus `~exit`, `~checksum` and, with a relay
        file, `~file`, `~sha256` and `~bytes`. No value in it is null, a list or an object.

    Raises:
        TypeError: The relay file is neither a Path nor None.

    """
    if path is not None and not isinstance(path, Path):
        message: str = "relay file must be a Path or None"
        raise TypeError(message)
    flat: FlatView = flatten(shown)
    env: FlatView = flat | {"~exit": exit_code, "~checksum": checksum(flat, exit_code)}
    if path is not None:
        env["~file"] = str(path)
        if path.is_file():
            data: bytes = path.read_bytes()
            env["~sha256"] = hashlib.sha256(data).hexdigest()
            env["~bytes"] = len(data)
    return env


def line(envelope: Mapping[str, JsonValue]) -> str:
    """Encode an envelope as the versioned base64 transport line.

    Returns:
        The line.

    """
    encoded: str = base64.b64encode(canonical(envelope).encode("ascii")).decode("ascii")
    return f"RELAY64v1:{encoded}"


def save(command: str, result: JsonObject, shown: JsonObject, exit_code: int, path: Path) -> FlatView:
    """Write a full result and the view printed for it to the relay file; return the envelope.

    Returns:
        The envelope.

    Raises:
        TypeError: The relay file is not a Path.

    """
    if not isinstance(path, Path):
        message: str = "relay file must be a Path"
        raise TypeError(message)
    _require_object(result, "relay result")
    path.parent.mkdir(parents=True, exist_ok=True)
    saved: JsonObject = {
        "command": command,
        "argvSha256": TYPED_ARGV[0],
        "exitCode": exit_code,
        "view": shown,
        "result": result,
    }
    path.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    return seal(shown, exit_code, path)


def write(command: str, result: JsonObject, path: Path, exit_code: int = 0) -> FlatView:
    """Write a depscore.py result to the relay file and return the envelope to print.

    Returns:
        The envelope.

    """
    return save(command, result, view(command, result), exit_code, path)


def _saved_relay(path: Path, data: bytes) -> tuple[JsonObject, int, JsonValue]:
    """Parse a relay file's bytes into its view, exit status and recorded argv digest.

    Returns:
        The saved view, its exact integer exit status and its `argvSha256` value.

    Raises:
        RelayError: The bytes are not a relay file with an object view and integer exit.

    """
    try:
        raw: object = json.loads(data.decode("utf-8"))
    except ValueError as exc:
        message: str = f"{path}: not a relay file: {exc}"
        raise RelayError(message) from exc
    if not isinstance(raw, dict):
        message = f"{path}: not a relay file"
        raise RelayError(message)
    shown: object = raw.get("view")
    exit_code: object = raw.get("exitCode")
    if not isinstance(shown, dict) or type(exit_code) is not int:
        message = f"{path}: not a relay file"
        raise RelayError(message)
    try:
        checked: JsonObject = json_object(shown)
    except TypeCheckError as exc:
        message = f"{path}: relay view is not JSON: {exc}"
        raise RelayError(message) from exc
    recorded: object = raw.get("argvSha256")
    return checked, exit_code, recorded if isinstance(recorded, str) else None


def read(
    path: Path,
    expected_sha256: str = "",
    expected_bytes: int | None = None,
    for_argv: str = "",
) -> FlatView:
    """Rebuild the envelope of a relay file written earlier, re-running nothing.

    A missing file, or with `for_argv` a file another command line wrote, yields a sealed
    `{missing: true}` view with exit 4: the command never saved a result there.

    Returns:
        The same envelope as when the file was written, or the missing-file envelope.

    Raises:
        TypeError: An argument has the wrong type, or `expected_bytes` is not an exact integer.
        RelayError: When the file does not hold a relayed result or differs from its receipt.

    """
    if (
        not isinstance(path, Path)
        or not isinstance(expected_sha256, str)
        or not isinstance(for_argv, str)
        or (expected_bytes is not None and type(expected_bytes) is not int)
    ):
        message: str = "relay read arguments violate their declared types"
        raise TypeError(message)
    if not path.is_file():
        return seal({"missing": True, "error": f"{path} does not exist"}, _MISSING_EXIT, path)
    data: bytes = path.read_bytes()
    digest: str = hashlib.sha256(data).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        message = f"{path}: saved relay bytes differ from the original command receipt"
        raise RelayError(message)
    if expected_bytes is not None and len(data) != expected_bytes:
        message = f"{path}: saved relay size differs from the original command receipt"
        raise RelayError(message)
    shown, exit_code, recorded = _saved_relay(path, data)
    if for_argv and recorded != for_argv:
        why: str = f"{path} holds the result of another command line"
        return seal({"missing": True, "error": why}, _MISSING_EXIT, path)
    return seal(shown, exit_code, None) | {"~file": str(path), "~sha256": digest, "~bytes": len(data)}


ARGV_FLAG: Final[str] = "--argv-sha256"
#: The `--argv-sha256` of the command line this process checked; `save` records it in the relay file.
TYPED_ARGV: Final[list[str]] = [""]


def argv_mismatch(argv: Sequence[str]) -> tuple[list[str], str]:
    """Check and strip a leading `--argv-sha256 HEX` from a command line.

    Returns:
        The arguments without the flag, and why they differ from what the script built ('' when
        they match or no checksum was given).

    Raises:
        TypeError: The command line is not a sequence of text arguments.

    """
    if isinstance(argv, str) or not isinstance(argv, Sequence) or any(not isinstance(a, str) for a in argv):
        message: str = "the command line must be a sequence of text arguments"
        raise TypeError(message)
    words: list[str] = list(argv)
    if not words or words[0] != ARGV_FLAG:
        return words, ""
    if len(words) < len((ARGV_FLAG, "HEX")):
        return words[1:], f"{ARGV_FLAG} has no value"
    want: str = words[1]
    rest: list[str] = words[2:]
    TYPED_ARGV[0] = want
    got: str = hashlib.sha256(canonical(rest).encode("ascii")).hexdigest()
    if got != want:
        return (
            rest,
            (
                f"the command line differs from the one the workflow script built ({ARGV_FLAG} {want}, "
                f"typed arguments hash to {got})"
            ),
        )
    return rest, ""


def mismatch_envelope(why: str) -> FlatView:
    """Seal the envelope printed, with exit 3, for a command line typed wrong: nothing ran.

    Returns:
        The envelope, with no relay file.

    """
    return seal({"argvMismatch": True, "error": why}, _MISMATCH_EXIT, None)
