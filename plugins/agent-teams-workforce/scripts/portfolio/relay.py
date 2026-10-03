"""Carry depscore.py results to a workflow script, and its commands from it, checkably.

A workflow script cannot read a file or run a command: a command reaches the shell only as
text a runner session types, and its result reaches the script only as the structured return
of that session. A model copying text does not reliably copy it unaltered, so neither copy is
trusted; both are checked deterministically:

- `--argv-sha256 HEX` (first on the command line): the SHA-256 of the canonical JSON of the
  argument list after it. A command line typed differently from the one the script built is
  refused with exit 3 before anything runs, so the script can have it run again.
- `--relay FILE`: the full result is written to FILE as `{"command": ..., "result": ...}`, and
  stdout carries only the result's relay VIEW, the few facts the script branches on (for
  `arch-resume` see `view`), plus `relay: {file, sha256, bytes, checksum}`: FILE's SHA-256 and
  size, and the SHA-256 of the view's canonical JSON. The script computes the same canonical
  JSON of what the runner returned and accepts it only when the checksums match; on a
  mismatch it has `relay-read` print the same envelope again from FILE, re-running nothing.
  Sessions that need the details are given FILE's path.

The canonical form is ASCII only (every other character a `\\uXXXX` escape of its UTF-16
units), keys sorted, no whitespace, numbers spelled as JavaScript spells them, so this module
and the workflow script produce the same bytes.
"""

from __future__ import annotations

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


def _arch_resume_view(result: dict) -> dict:
    """The facts of `arch-resume` the architecture workflow branches on, and nothing else.

    Prose (coverage gap texts, overlap warnings), finding verdicts and files, the dispatch
    files, answers and claim assignments of a pending plan, and the hash rows of the coverage
    checks stay in the relay file and in `ledger.json`, which the sessions read. The checks
    are reduced to their ids and the SHA-256 of their canonical `[{id, revision}]` list
    (sorted by id), which the script compares with a review's verified checks.

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
        "integration": result.get("integration"),
        "coverage": {
            "revision": cov.get("revision"),
            "gapCount": len(gaps) if isinstance(gaps, list) else 0,
            "checkIds": [r["id"] for r in rows],
            "checksSha256": hashlib.sha256(canonical(rows).encode("ascii")).hexdigest(),
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


def view(command: str, result: dict) -> dict:
    """The part of a command's result the workflow script receives.

    Args:
        command: The depscore.py command that produced the result.
        result: Its full result.

    Returns:
        For `arch-resume`, `_arch_resume_view`; for every other command, the result as printed.
    """
    if command == "arch-resume" and not result.get("error"):
        return _arch_resume_view(result)
    return dict(result)


def envelope(command: str, result: dict, path: Path) -> dict:
    """The object printed on stdout for a relayed result.

    Args:
        command: The depscore.py command.
        result: Its full result.
        path: The relay file holding the full result.

    Returns:
        The view with its `relay` block.
    """
    shown = view(command, result)
    data = path.read_bytes()
    return shown | {
        "relay": {
            "file": str(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "checksum": hashlib.sha256(canonical(shown).encode("ascii")).hexdigest(),
        }
    }


def write(command: str, result: dict, path: Path) -> dict:
    """Write the full result to the relay file and return the envelope to print.

    Args:
        command: The depscore.py command.
        result: Its full result.
        path: The relay file.

    Returns:
        The envelope.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"command": command, "result": result}, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return envelope(command, result, path)


def read(path: Path) -> dict:
    """The envelope of a relay file written earlier, re-running nothing.

    Args:
        path: The relay file.

    Returns:
        The same envelope `write` returned for it.

    Raises:
        RelayError: When the file does not hold a relayed result.
    """
    saved = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(saved, dict)
        or not isinstance(saved.get("command"), str)
        or not isinstance(saved.get("result"), dict)
    ):
        raise RelayError(f"{path}: not a relay file")
    return envelope(saved["command"], saved["result"], path)


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
