"""Carry depscore.py results to a workflow script, and its commands from it, checkably.

A workflow script cannot read a file or run a command: a command reaches the shell only as
text a runner session types, and its result reaches the script only as the structured return
of that session. A model copying text does not reliably copy it unaltered, so neither copy is
trusted; both are checked deterministically:

- `--argv-sha256 HEX` (first on the command line): the SHA-256 of the canonical JSON of the
  argument list after it. A command line typed differently from the one the script built is
  refused with exit 3 before anything runs.
- `--relay FILE`: the full result is written to FILE as `{"command": ..., "result": ...}`, and
  stdout carries only the result's relay VIEW, the few facts the script branches on (for
  `arch-resume` see `view`), flattened to one object of scalars (`flatten`), plus `~file`,
  `~sha256`, `~bytes` (FILE's path, SHA-256 and size), `~exit` and `~checksum`, the SHA-256 of
  the canonical JSON of `{exit, view}`; its canonical ASCII JSON is base64-encoded after `RELAY64v1:` on one line (`line`). The
  runner returns that line verbatim; the script parses it, recomputes the checksum, accepts
  only an exact copy and never retries a mismatch.
  Sessions that need the details are given FILE's path.

The canonical form is ASCII only (every other character a `\\uXXXX` escape of its UTF-16
units), keys sorted, no whitespace, numbers spelled as JavaScript spells them, so this module
and the workflow script produce the same bytes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path

_SHORT = {
    '"': '\\"',
    "\\": "\\\\",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}


class RelayError(ValueError):
    """A relay file that cannot be read back, or a value with no canonical spelling."""


def _string(s: str) -> str:
    """Spell a string as canonical JSON: ASCII only, as JavaScript would escape it.

    Args:
        s: The string.

    Returns:
        The quoted, escaped string.
    """
    out = ['"']
    data = s.encode("utf-16-be", "surrogatepass")
    for i in range(0, len(data), 2):
        unit = (data[i] << 8) | data[i + 1]
        ch = chr(unit) if unit < 0x80 else ""
        if ch and ch in _SHORT:
            out.append(_SHORT[ch])
        elif 0x20 <= unit <= 0x7E:
            out.append(ch)
        else:
            out.append(f"\\u{unit:04x}")
    out.append('"')
    return "".join(out)


def _number(x: float) -> str:
    """Spell a float as JavaScript's `String(x)` does.

    Args:
        x: A finite float.

    Returns:
        Its JavaScript spelling.

    Raises:
        RelayError: For NaN or an infinity, which JSON cannot carry.
    """
    if math.isnan(x) or math.isinf(x):
        raise RelayError(f"{x} has no JSON spelling")
    if x == int(x) and abs(x) < 1e21:
        return str(int(x))
    sign = "-" if x < 0 else ""
    mantissa, _, exp = repr(abs(x)).partition("e")
    whole, _, frac = mantissa.partition(".")
    raw = whole + frac
    point = len(whole) + int(exp or 0)
    lead = len(raw) - len(raw.lstrip("0"))
    digits = raw.strip("0")
    n, k = point - lead, len(digits)
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = f"{digits[:n]}.{digits[n:]}"
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        body = (
            digits[0]
            + (f".{digits[1:]}" if k > 1 else "")
            + f"e{'+' if e >= 0 else '-'}{abs(e)}"
        )
    return sign + body


def canonical(value: object) -> str:
    """Spell a JSON value canonically: sorted keys, no whitespace, ASCII only.

    Args:
        value: A JSON value (dict, list, str, int, float, bool or None).

    Returns:
        Its canonical JSON text.

    Raises:
        RelayError: For a value JSON cannot carry.
    """
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _number(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical(v) for v in value) + "]"
    if isinstance(value, dict):
        items = sorted((str(k), v) for k, v in value.items())
        return "{" + ",".join(f"{_string(k)}:{canonical(v)}" for k, v in items) + "}"
    raise RelayError(f"a {type(value).__name__} has no JSON spelling")


def _integration_view(integration: object) -> object:
    """arch-resume's integration facts with the report's file lists and the last review's
    checks as counts; arch-integration-files and arch-review-check read them from disk.

    Args:
        integration: The `integration` facts.

    Returns:
        The reduced facts.
    """
    if not isinstance(integration, dict):
        return integration
    out = dict(integration)
    if isinstance(out.get("update"), dict):
        out["update"] = _counted(
            out["update"], ("changedFiles", "createdFiles", "deletedFiles")
        )
    if isinstance(out.get("lastReview"), dict):
        out["lastReview"] = _counted(
            out["lastReview"], ("coverageChecks", "reviewedFiles")
        )
    return out


def _arch_resume_view(result: dict) -> dict:
    """The facts of `arch-resume` the architecture workflow branches on, and nothing else.

    Prose (coverage gap texts, overlap warnings), finding verdicts and files, the dispatch
    files, answers and claim assignments of a pending plan, and the hash rows of the coverage
    checks stay in the relay file and in `ledger.json`, which the sessions read. The checks
    are reduced to their count; `arch-review-check --coverage-from` reads the rows from the
    relay file.

    Args:
        result: The full `arch-resume` result.

    Returns:
        The view.
    """
    rounds = result.get("rounds") or {}
    cov = result.get("coverage") or {}
    team = result.get("proposalTeam") or {}
    survey = result.get("survey") or {}
    open_by_owner: dict[str, dict[str, list[str]]] = {}
    for f in rounds.get("openFindings") or []:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        slot = open_by_owner.setdefault(
            str(f.get("owner") or ""), {"answered": [], "open": []}
        )
        slot["answered" if f.get("answered") else "open"].append(str(f["id"]))
    plan = rounds.get("pendingPlan")
    if isinstance(plan, dict):
        plan = {
            "round": plan.get("round"),
            "readyForDecision": plan.get("readyForDecision"),
            "dispatches": [
                {k: d.get(k) for k in ("seq", "role", "agentType", "complete")}
                for d in plan.get("dispatches") or []
                if isinstance(d, dict)
            ],
        }
    rows = sorted(
        (
            {"id": r.get("id"), "revision": r.get("revision")}
            for r in cov.get("checksNeeded") or []
            if isinstance(r, dict)
        ),
        key=lambda r: str(r["id"]),
    )
    gaps = cov.get("gaps")
    return {
        "contractVersion": result.get("contractVersion"),
        "survey": {
            k: survey.get(k)
            for k in ("saved", "coverageSaved", "subject", "capabilities")
        },
        "proposalTeam": {
            "lead": team.get("lead") or "",
            "second": team.get("second") or "",
        },
        "decision": result.get("decision"),
        "integration": _integration_view(result.get("integration")),
        "coverage": {
            "revision": cov.get("revision"),
            "gapCount": len(gaps) if isinstance(gaps, list) else 0,
            "rows": len(rows),
        },
        "rounds": {
            "last": rounds.get("last"),
            "pendingRound": rounds.get("pendingRound"),
            "pendingDispatches": rounds.get("pendingDispatches"),
            "pendingPlan": plan,
            "planKept": bool(rounds.get("planKept")),
            "readyForDecision": rounds.get("readyForDecision"),
            "saved": rounds.get("saved") or [],
            "writers": rounds.get("writers") or [],
            "reviewers": rounds.get("reviewers") or [],
            "legacyProposersWithoutClaims": rounds.get("legacyProposersWithoutClaims")
            or [],
            "proposersWithoutClaims": rounds.get("proposersWithoutClaims") or [],
            "claims": rounds.get("claims"),
            "findings": rounds.get("findings"),
            "openFindings": open_by_owner,
            "unreviewedClaims": rounds.get("unreviewedClaims") or {},
            "overlapWarnings": len(rounds.get("overlapWarnings") or []),
        },
    }


def _counted(result: dict, keys: tuple[str, ...]) -> dict:
    """A result with the named lists replaced by their lengths.

    Args:
        result: The result.
        keys: The keys whose list values become counts.

    Returns:
        The reduced copy.
    """
    return {
        k: (len(v) if k in keys and isinstance(v, list) else v)
        for k, v in result.items()
    }


#: Per command, the lists its relay view carries as counts; the names stay in the relay file.
COUNTED = {
    "arch-integration-files": (
        "touched",
        "deleted",
        "all",
        "unreported",
        "section2",
        "outside",
        "changedSinceLast",
        "reportedTouched",
        "reportedDeleted",
    ),
    "arch-review-check": ("missed", "coverageUnverified"),
    "arch-approve": ("promoted", "unchanged", "noFrontmatter", "wouldApprove"),
    "arch-commit": ("files",),
}


#: Keys no workflow reads that depscore.py echoes back (the data source, warnings, the
#: dry-run plan, the command's own name): left out of every view, kept in the relay file.
ECHOED = ("source", "warnings", "planned", "command", "dryRun")
#: Per command, the only top-level keys its view carries, when a workflow reads few of many.
WHITELIST = {
    "elaboration-start": ("ok", "refusal", "owner", "previousState"),
    "elaboration-finish": ("ok", "lifecycle", "missing", "summary", "storyEdges"),
}


def view(command: str, result: dict) -> dict:
    """The part of a command's result the workflow script receives.

    Args:
        command: The depscore.py command that produced the result.
        result: Its full result.

    Returns:
        For `arch-resume`, `_arch_resume_view`; for a command in COUNTED, its lists as counts;
        for `arch-snapshot --counts`, each diff's lists as counts; otherwise the result.
    """
    if result.get("error"):
        return {"error": result["error"]}
    if command == "arch-resume":
        return _arch_resume_view(result)
    if command in WHITELIST:
        return {k: result[k] for k in WHITELIST[command] if k in result}
    out = {k: v for k, v in result.items() if k not in ECHOED}
    if command in COUNTED:
        return _counted(out, COUNTED[command])
    if command == "arch-snapshot" and result.get("countsOnly"):
        diffs = [
            _counted(d, ("created", "changed", "deleted"))
            for d in result.get("diffs") or []
            if isinstance(d, dict)
        ]
        return out | {"diffs": diffs}
    return out


def _segment(key: object) -> str:
    """One path segment of a flat key: `~` written `~0` and `/` written `~1`.

    Args:
        key: An object key.

    Returns:
        The escaped segment.
    """
    return str(key).replace("~", "~0").replace("/", "~1")


def flatten(shown: dict) -> dict:
    """A view as one flat object of scalars, so a runner copies one line of plain values.

    Each scalar leaf is keyed by its path, segments joined by `/` (see `_segment`). A nested
    object, list or null is marked by a key ending in `/~{}` (its key count), `/~#` (its length)
    or `/~null` (1), and a non-empty list of non-empty strings without commas is one key ending
    in `/~,` holding them comma-joined, so the workflow rebuilds the view exactly, empty ones
    included. Keys
    starting with `~` at the top level are the relay's own.

    Args:
        shown: The view.

    Returns:
        The flat view.
    """
    out: dict = {}

    def walk(value: object, path: str) -> None:
        join = (lambda seg: f"{path}/{seg}") if path else (lambda seg: seg)
        if isinstance(value, dict):
            if path:
                out[join("~{}")] = len(value)
            for k, v in value.items():
                walk(v, join(_segment(k)))
        elif (
            isinstance(value, (list, tuple))
            and value
            and all(isinstance(v, str) and v and "," not in v for v in value)
        ):
            out[join("~,")] = ",".join(value)
        elif isinstance(value, (list, tuple)):
            out[join("~#")] = len(value)
            for i, v in enumerate(value):
                walk(v, join(str(i)))
        elif value is None:
            out[join("~null")] = 1
        else:
            out[path] = value

    walk(shown, "")
    return out


def checksum(flat: dict, exit_code: int) -> str:
    """The SHA-256 a relayed flat view is checked against: of the canonical `{exit, view}`.

    Args:
        flat: The flat view.
        exit_code: The exit status reported with it.

    Returns:
        The lower-case hex digest.
    """
    text = canonical({"exit": exit_code, "view": flat})
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def seal(shown: dict, exit_code: int, path: Path | None) -> dict:
    """The object printed on stdout: the flat view with the relay's own keys.

    Args:
        shown: The view.
        exit_code: The exit status the printing process ends with.
        path: The relay file holding the full result, or None when nothing was saved.

    Returns:
        The flat envelope: the view's leaves plus `~exit`, `~checksum` and, with a relay
        file, `~file`, `~sha256` and `~bytes`. No value in it is null, a list or an object.
    """
    flat = flatten(shown)
    env = flat | {"~exit": exit_code, "~checksum": checksum(flat, exit_code)}
    if path is not None:
        env["~file"] = str(path)
        if path.is_file():
            data = path.read_bytes()
            env["~sha256"] = hashlib.sha256(data).hexdigest()
            env["~bytes"] = len(data)
    return env


def line(envelope: dict) -> str:
    """The versioned base64 transport line for an envelope.

    Args:
        envelope: The flat envelope.

    Returns:
        The line.
    """
    encoded = base64.b64encode(canonical(envelope).encode("ascii")).decode("ascii")
    return f"RELAY64v1:{encoded}"


def save(command: str, result: dict, shown: dict, exit_code: int, path: Path) -> dict:
    """Write a full result and the view printed for it to the relay file; return the envelope.

    Args:
        command: The command that produced the result.
        result: Its full result.
        shown: The view printed for it.
        exit_code: The exit status printed with it.
        path: The relay file.

    Returns:
        The envelope.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = {"command": command, "exitCode": exit_code, "view": shown, "result": result}
    path.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    return seal(shown, exit_code, path)


def write(command: str, result: dict, path: Path, exit_code: int = 0) -> dict:
    """Write a depscore.py result to the relay file and return the envelope to print.

    Args:
        command: The depscore.py command.
        result: Its full result.
        path: The relay file.
        exit_code: The exit status depscore.py ends with.

    Returns:
        The envelope.
    """
    return save(command, result, view(command, result), exit_code, path)


def read(path: Path) -> dict:
    """The envelope of a relay file written earlier, re-running nothing.

    A missing file yields a sealed `{missing: true}` view with exit 4: the command never saved a
    result, so the caller knows it may run it again.

    Args:
        path: The relay file.

    Returns:
        The same envelope as when the file was written, or the missing-file envelope.

    Raises:
        RelayError: When the file does not hold a relayed result.
    """
    if not path.is_file():
        return seal({"missing": True, "error": f"{path} does not exist"}, 4, path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(saved, dict)
        or not isinstance(saved.get("view"), dict)
        or not isinstance(saved.get("exitCode"), int)
    ):
        raise RelayError(f"{path}: not a relay file")
    return seal(saved["view"], saved["exitCode"], path)


ARGV_FLAG = "--argv-sha256"


def argv_mismatch(argv: list[str]) -> tuple[list[str], str]:
    """Check and strip a leading `--argv-sha256 HEX` from a command line.

    Args:
        argv: The arguments after the script name.

    Returns:
        The arguments without the flag, and why they differ from what the script built ('' when
        they match or no checksum was given).
    """
    if not argv or argv[0] != ARGV_FLAG:
        return argv, ""
    if len(argv) < 2:
        return argv[1:], f"{ARGV_FLAG} has no value"
    want, rest = argv[1], argv[2:]
    got = hashlib.sha256(canonical(rest).encode("ascii")).hexdigest()
    if got != want:
        return (
            rest,
            f"the command line differs from the one the workflow script built ({ARGV_FLAG} {want}, typed arguments hash to {got})",
        )
    return rest, ""


def mismatch_envelope(why: str) -> dict:
    """The sealed envelope printed, with exit 3, for a command line typed wrong: nothing ran.

    Args:
        why: The mismatch.

    Returns:
        The envelope, with no relay file.
    """
    return seal({"argvMismatch": True, "error": why}, 3, None)
