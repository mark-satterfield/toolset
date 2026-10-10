#!/usr/bin/env python3
"""Read the tracker once and normalize it into a graph that sequencing and scoring reason over.

The tracker is read live through `bd`, and only through `bd`. The `.beads/issues.jsonl`
export is never read: `bd` exports only after a state-changing command, at most once per
`export.interval`, and the export can be blocked, so it can lag the tracker by hours.
Every live `bd` command holds the shared driver gate and has a timeout.
Failures carry structured causes; the orchestrator owns retries of keyed operations.

Two dependency types carry order, one per level. An Epic-to-Epic dependency is a `tracks`
edge: it orders ELABORATION, and `tracks` is non-blocking in beads, so it never removes an
Epic, or anything beneath one, from `bd ready`. A Task-to-Task dependency is a `blocks` edge:
it orders the BUILD, and `bd ready` releases the dependent Task when its blocker closes.
`parent-child` also appears in a record's `dependencies`; it is hierarchy and is never read
as a dependency.
"""

from __future__ import annotations

import argparse
import functools
import importlib
import importlib.util
import json
import math
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Serialized bd transport uses argv without a shell.
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

#: The `beads-contract` CLI — the one writer of this pipeline's bead metadata. Going
#: through it is what keeps ONE statement of which keys exist and how they merge; a
#: hand-rolled `bd update --metadata` here would be a second, silently divergent one.
CONTRACT = Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts" / "beads-contract.py"

#: The dependency type of a Task-to-Task edge: a build prerequisite `bd ready` enforces.
BLOCKS = "blocks"

#: The dependency type of an Epic-to-Epic edge: an elaboration prerequisite. Non-blocking in
#: beads, so it never holds an Epic's Stories or Tasks out of `bd ready`.
TRACKS = "tracks"


def edge_type(kind: str) -> str:
    """Return the dependency type for an edge onto this issue type.

    Args:
        kind: The issue type of the dependent bead.

    Returns:
        `tracks` for an Epic, `blocks` for everything else.

    """
    return TRACKS if kind == "epic" else BLOCKS


#: Statuses that mean the bead is finished. An edge onto one of these is inert.
CLOSED = frozenset({"closed"})

#: Metadata key on the DEPENDENT bead listing the Epic edges this system created, as a
#: comma-separated id list of the beads it depends on. An edge absent from it was made by
#: hand and is never removed.
OWNED_KEY = "seq_owned_blockers"
OWNED_AT_KEY = "seq_owned_blockers_at"


#: The cause of a failure the beads server or its connection made, not the command.
BD_TIMEOUT = "bd-timeout"
#: The cause of a failure another writer's lock made: the command collided, it did not fail.
CONTENTION = "contention"
#: The causes a write is made again for.
RETRIED_CAUSES = frozenset({BD_TIMEOUT, CONTENTION})
#: The cause of any other failure.
OTHER_CAUSE = "other"


class GraphError(RuntimeError):
    """The tracker could not be read, or answered with something unusable.

    `cause` is CONTENTION when acquiring the shared lock timed out, BD_TIMEOUT when the
    subprocess timed out, and OTHER_CAUSE for other failures. No message text is classified.
    """

    def __init__(self, message: str, cause: str = OTHER_CAUSE) -> None:
        """Keep the message and the cause.

        Args:
            message: What failed.
            cause: CONTENTION, BD_TIMEOUT or OTHER_CAUSE.

        """
        super().__init__(message)
        self.cause = cause


@dataclass(frozen=True)
class Bead:
    """One tracker record, reduced to the fields sequencing reasons about."""

    id: str
    title: str
    kind: str
    status: str
    parent: str | None
    metadata: dict[str, str]
    blockers: tuple[str, ...]
    tracked: tuple[str, ...] = ()
    description: str = ""

    @property
    def closed(self) -> bool:
        """Whether the bead is finished."""
        return self.status in CLOSED

    @property
    def depends_on(self) -> tuple[str, ...]:
        """The beads this one depends on, read from the edge type its level is stored as.

        An Epic's dependencies are its `tracks` edges; every other bead's are its `blocks`
        edges.
        """
        return self.tracked if edge_type(self.kind) == TRACKS else self.blockers

    @property
    def owned_blockers(self) -> tuple[str, ...]:
        """The Epic edges on this bead that this system created, per its own record."""
        return tuple(split_ids(self.metadata.get(OWNED_KEY, "")))


@dataclass
class Graph:
    """Every bead in the tracker, indexed, plus the source it was read from."""

    beads: dict[str, Bead]
    source: str
    records: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def of_kind(self, *kinds: str) -> list[Bead]:
        """Select beads of the given issue types.

        Returns:
            Matching beads in id order.

        """
        wanted = set(kinds)
        return [b for _, b in sorted(self.beads.items()) if b.kind in wanted]

    def ancestors(self, bead_id: str) -> list[Bead]:
        """Walk the parent chain, stopping at a cycle.

        Returns:
            Ancestors nearest first.

        """
        chain: list[Bead] = []
        seen = {bead_id}
        current = self.beads.get(bead_id)
        while current is not None and current.parent:
            if current.parent in seen:
                break
            seen.add(current.parent)
            parent = self.beads.get(current.parent)
            if parent is None:
                break
            chain.append(parent)
            current = parent
        return chain

    def epic_of(self, bead_id: str) -> Bead | None:
        """Find the nearest Epic above a bead.

        Returns:
            The closest Epic ancestor, or None.

        """
        for ancestor in self.ancestors(bead_id):
            if ancestor.kind == "epic":
                return ancestor
        return None

    def descendants(self, bead_id: str) -> list[Bead]:
        """Find every descendant at any depth.

        Returns:
            Descendants in id order.

        """
        children: dict[str, list[Bead]] = {}
        for bead in self.beads.values():
            if bead.parent:
                children.setdefault(bead.parent, []).append(bead)
        out: list[Bead] = []
        stack = list(children.get(bead_id, []))
        seen: set[str] = set()
        while stack:
            bead = stack.pop()
            if bead.id in seen:
                continue
            seen.add(bead.id)
            out.append(bead)
            stack.extend(children.get(bead.id, []))
        return sorted(out, key=lambda b: b.id)


def split_ids(raw: str) -> list[str]:
    """Parse a comma-separated bead-id list.

    Returns:
        Nonempty stripped bead identifiers.

    """
    return [part.strip() for part in raw.split(",") if part.strip()]


def join_ids(ids: list[str] | set[str] | tuple[str, ...]) -> str:
    """Render identifiers in the comma-separated metadata form.

    Returns:
        Sorted unique identifiers separated by commas.

    """
    return ",".join(sorted(set(ids)))


# The orchestrator installs this callable; direct portfolio commands use the same gate.
BD_GATE = None


def _gate_module() -> ModuleType:
    """Load the shared lock implementation for direct portfolio CLI invocations.

    Returns:
        The shared lock module.

    """
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module("orchestrator.core.tool_locks")


@functools.cache
def _contract() -> object:
    """Load the beads-contract module that selects the database for `bd`.

    Returns:
        The loaded module.

    """
    spec = importlib.util.spec_from_file_location("beads_contract", CONTRACT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.cache
def _central() -> Path | None:
    """Resolve the central repository or use the working directory.

    Returns:
        The repository, or None.

    """
    central = _contract().central_repo("")
    return Path(central) if central else None


#: central repository -> {fleet-filed bead id: the repository it was filed in}.
_HOMES: dict[str, dict[str, str]] = {}


def _target(args: list[str], repo: Path | None) -> Path | None:
    """Resolve the repository for a `bd` command by the beads-contract rule.

    Every command runs against the central database (`repo`, else `$ATW_CONTROL_REPO`),
    except a write to a bead filed in a fleet repository's own database, which runs there:
    the one-way fleet sync would copy the fleet copy back over a central edit.

    Args:
        args: The `bd` arguments.
        repo: The central repository the caller named, or None.

    Returns:
        The repository, or None for the working directory.

    """
    contract = _contract()
    central = repo if repo is not None else _central()
    bead_id = contract.bead_operand(args)
    if not bead_id or contract.is_read(args):
        return central
    key = str(central or "")
    if key not in _HOMES:
        rows = _bd_json(["--readonly", "sql", "--json", contract.FLEET_QUERY], central)
        _HOMES[key] = contract.fleet_homes(rows, key)
    home = _HOMES[key].get(bead_id)
    return Path(home) if home else central


def _bd(args: list[str], repo: Path | None, stdin: str | None = None) -> str:
    """Make one serialized, bounded bd call with a cause from structured facts.

    The orchestrator retries the enclosing keyed operation, which rereads existing beads.
    No command output is interpreted to guess whether a failed write is safe to repeat.

    Returns:
        The command stdout.

    Raises:
        GraphError: The lock, process, or tracker command failed.

    """
    command = ["bd", *args]
    where = _target(args, repo)
    if where is not None:
        command += ["-C", str(where)]
    locks = _gate_module()
    gate = BD_GATE or locks.bd_gate
    try:
        with gate(write=not _contract().is_read(args)):
            done = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - bd argv and separate repository argument; shell disabled.
                command,
                input=stdin,
                capture_output=True,
                text=True,
                check=False,
                timeout=locks.seconds("ATW_BD_TIMEOUT", 180),
            )
    except locks.LockTimeoutError as exc:
        raise GraphError(str(exc), CONTENTION) from exc
    except subprocess.TimeoutExpired as exc:
        raise GraphError(str(exc), BD_TIMEOUT) from exc
    except (OSError, ValueError) as exc:
        raise GraphError(str(exc), OTHER_CAUSE) from exc
    if done.returncode:
        msg = f"`{' '.join(command)}` exited {done.returncode}: {done.stdout} {done.stderr}"
        raise GraphError(msg, OTHER_CAUSE)
    return done.stdout


def _bd_json(args: list[str], repo: Path | None) -> object:
    """Run a read-only `bd` command and parse its JSON stdout.

    A failed read raises its structured cause to the caller, which owns retry policy.

    Args:
        args: The `bd` arguments.
        repo: The central repository, or None for `$ATW_CONTROL_REPO`.

    Returns:
        The parsed stdout.

    Raises:
        GraphError: `bd` failed or printed no JSON.

    """
    out = _bd(args, repo)
    try:
        return json.loads(out or "null")
    except json.JSONDecodeError as exc:
        msg = f"`bd {' '.join(args)}` printed no JSON: {exc}: {out.strip()[:400]}"
        raise GraphError(msg) from exc


def now_iso() -> str:
    """Format the current instant in UTC.

    Returns:
        The ISO 8601 timestamp to the second.

    """
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def same_value(stored: object, wanted: str) -> bool:
    """Whether a value read back from the tracker is the value that was written.

    `bd` hands numbers back as JSON numbers, so `3.00` returns as `3`; two values that
    parse to the same number are the same value. It hands a JSON object or list back
    parsed, so two values that both parse as the same object or list are the same value.

    Args:
        stored: The value the read-back reported.
        wanted: The value written.

    Returns:
        True when the read-back holds the written value.

    """
    structured = _structured(stored)
    if structured is not None:
        return structured == _structured(wanted)
    # `bd` hands a `true`/`false` value back as a JSON boolean.
    if isinstance(stored, bool):
        return str(stored).lower() == wanted.strip().lower()
    text = "" if stored is None else str(stored)
    if text == wanted:
        return True
    try:
        return math.isclose(float(text), float(wanted), rel_tol=0.0, abs_tol=0.0)
    except ValueError:
        return False


def _structured(value: object) -> dict | list | None:
    """Parse a value as a JSON object or list when possible.

    Args:
        value: A parsed object or list, or a string that may hold one.

    Returns:
        The object or list, or None.

    """
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except ValueError:
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _metadata_text(value: object) -> str:
    """Render a metadata value as the string a Bead holds.

    Args:
        value: The value as `bd` returned it.

    Returns:
        An object or list as compact JSON with sorted keys; a string unchanged; anything
        else as `str`.

    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value if isinstance(value, str) else str(value)


def write_metadata(bead_id: str, pairs: dict[str, str], repo: Path | None) -> None:
    """Write pipeline metadata through the beads-contract functions and the shared transport.

    Args:
        bead_id: The bead to write.
        pairs: The keys and values to merge onto its metadata.
        repo: The central repository, or None for `$ATW_CONTROL_REPO`.

    Raises:
        GraphError: The contract refused the write or the shared bd transport failed.

    """
    contract = _contract()

    class LockedReader(contract.Reader):
        def _bd(self, args: list[str], repo: str | None = None, stdin: str | None = None) -> str:
            where = self.route(args) if repo is None else repo
            return _bd(args, Path(where) if where else None, stdin)

    reader = LockedReader(str(repo) if repo else "")
    arguments = argparse.Namespace(
        op="set",
        id=bead_id,
        pairs=[f"{key}={value}" for key, value in pairs.items()],
    )
    try:
        contract.cmd_metadata(arguments, reader)
    except (contract.ContractError, contract.BeadsError) as exc:
        raise GraphError(str(exc)) from exc


@dataclass
class Writer:
    """The one path for tracker writes; a dry-run writer records each write instead.

    Attributes:
        repo: The central repository, or None for `$ATW_CONTROL_REPO`.
        dry_run: True to record each write in `planned` and change nothing.
        planned: The writes a dry run would have made, in order.

    """

    repo: Path | None
    dry_run: bool = False
    planned: list[dict] = field(default_factory=list)

    def bd(self, args: list[str], stdin: str | None = None) -> None:
        """Run a `bd` command that changes the tracker, or record it in a dry run.

        Args:
            args: The `bd` arguments.
            stdin: The text the command reads on its standard input, or None.

        """
        if self.dry_run:
            self.planned.append({"op": "bd", "args": list(args), "stdin": stdin})
            return
        _bd(args, self.repo, stdin)

    def create(self, args: list[str], key: str) -> str:
        """Run a `bd create`, or record it in a dry run.

        Args:
            args: The `bd create` arguments.
            key: The name a dry run gives the bead it would create.

        Returns:
            The new bead's id, or `(new:<key>)` in a dry run.

        """
        if self.dry_run:
            self.planned.append({"op": "bd", "args": list(args)})
            return f"(new:{key})"
        return _bd(args, self.repo).strip().splitlines()[-1].strip()

    def metadata(self, bead_id: str, pairs: dict[str, str]) -> None:
        """Write pipeline metadata onto one bead, or record it in a dry run.

        Args:
            bead_id: The bead to write.
            pairs: The keys and values to merge onto its metadata.

        """
        if self.dry_run:
            self.planned.append({"op": "metadata", "id": bead_id, "set": dict(pairs)})
            return
        write_metadata(bead_id, pairs, self.repo)


#: The fingerprint scope a caller asks for. `judging` covers only the material a judging
#: or assessing session is handed; `readiness` also covers the build contract. The scopes
#: themselves are defined once, in `beads-contract.py`; this is only how a caller names one.
SCOPE_JUDGING = "judging"
SCOPE_READINESS = "readiness"


def fingerprints(records: list[dict], scope: str = SCOPE_READINESS) -> dict[str, str]:
    """Compute every record fingerprint through the shared contract.

    The records are handed over rather than re-fetched, so the fingerprint is taken over
    exactly the sweep the caller reasons about.

    Args:
        records: Tracker records as `bd list --json` returned them, descriptions included.
        scope: Which fingerprint — `readiness` or `judging`. A caller must pass the scope
            matching the key it stores the answer under, or it will compare a watermark
            with a fingerprint of something else.

    Returns:
        Bead id -> content fingerprint.


    """
    contract = _contract()
    latest = {str(record.get("id") or ""): record for record in records}
    return {
        bead_id: contract.fingerprint_of(bead_id, record, scope=scope)["fingerprint"]
        for bead_id, record in latest.items()
    }


def _records_from_bd(repo: Path | None, *, with_description: bool) -> list[dict]:
    """Read every issue, including closed ones.

    Returns:
        The tracker records.

    Raises:
        GraphError: The tracker response was not an array.

    """
    args = ["list", "--all", "--json", "-n", "0", "--readonly"]
    if not with_description:
        args.append("--brief")
    payload = _bd_json(args, repo)
    if not isinstance(payload, list):
        msg = "`bd list --json` did not return an array"
        raise GraphError(msg)
    return payload


def children(repo: Path | None, parent: str, kind: str) -> list[dict]:
    """Return every record of one issue type directly under a parent, from one `bd list` call.

    Args:
        repo: The central repository, or None for `$ATW_CONTROL_REPO`.
        parent: The parent id.
        kind: The issue type.

    Returns:
        The records, closed ones included, as `bd list --json` returns them.

    Raises:
        GraphError: `bd` failed or did not return an array.

    """
    args = ["list", "--parent", parent, "--type", kind, "--all", "--json", "-n", "0"]
    payload = _bd_json([*args, "--readonly"], repo)
    if not isinstance(payload, list):
        msg = "`bd list --json` did not return an array"
        raise GraphError(msg)
    return payload


def bead_of(record: dict) -> Bead:
    """Normalize one tracker record, allowing omitted unset fields.

    Returns:
        The normalized bead.

    """
    metadata = record.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata or "{}")

    def targets(kind: str) -> list[str]:
        return [
            str(dep.get("depends_on_id"))
            for dep in record.get("dependencies") or []
            if dep.get("type") == kind and dep.get("depends_on_id")
        ]

    return Bead(
        id=str(record["id"]),
        title=str(record.get("title") or ""),
        kind=str(record.get("issue_type") or ""),
        status=str(record.get("status") or ""),
        parent=str(record["parent"]) if record.get("parent") else None,
        metadata={str(k): _metadata_text(v) for k, v in metadata.items()},
        blockers=tuple(sorted(set(targets(BLOCKS)))),
        tracked=tuple(sorted(set(targets(TRACKS)))),
        description=str(record.get("description") or ""),
    )


def load(repo: Path | None = None, *, with_description: bool = False) -> Graph:
    """Read the whole tracker live through `bd` and normalize it.

    Returns:
        The normalized graph and its source records.

    """
    records = _records_from_bd(repo, with_description=with_description)
    beads = {}
    for record in records:
        bead = bead_of(record)
        beads[bead.id] = bead
    return Graph(beads=beads, source="bd list --all --json", records=records)
