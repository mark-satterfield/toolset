#!/usr/bin/env python3
"""Read the tracker once and normalize it into a graph that sequencing and scoring reason over.

The tracker is `bd`. The `.beads/issues.jsonl` export is a PASSIVE artifact written by
`bd` and can lag it, so it is a fallback only, and whichever source answered is reported
on every command so a caller never has to guess which one it read.

Only `blocks` edges are sequencing edges. `parent-child` also appears in a record's
`dependencies`, and treating it as a blocker would make every child of an open parent
look blocked forever.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: The `beads-contract` CLI — the one writer of this pipeline's bead metadata. Going
#: through it is what keeps ONE statement of which keys exist and how they merge; a
#: hand-rolled `bd update --metadata` here would be a second, silently divergent one.
CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "beads-contract"
    / "scripts"
    / "beads-contract.py"
)

#: The only dependency type this system sets, reads, or removes.
BLOCKS = "blocks"

#: Statuses that mean the bead is finished. An edge onto one of these is inert.
CLOSED = frozenset({"closed"})

#: Metadata key on the BLOCKED bead listing the blockers this system created, as a
#: comma-separated id list. An edge absent from it was made by hand and is never removed.
OWNED_KEY = "seq_owned_blockers"
OWNED_AT_KEY = "seq_owned_blockers_at"


class GraphError(RuntimeError):
    """The tracker could not be read, or answered with something unusable."""


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
    description: str = ""

    @property
    def closed(self) -> bool:
        """Whether the bead is finished."""
        return self.status in CLOSED

    @property
    def owned_blockers(self) -> tuple[str, ...]:
        """The blockers on this bead that this system created, per its own record."""
        return tuple(split_ids(self.metadata.get(OWNED_KEY, "")))


@dataclass
class Graph:
    """Every bead in the tracker, indexed, plus the source it was read from."""

    beads: dict[str, Bead]
    source: str
    records: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def of_kind(self, *kinds: str) -> list[Bead]:
        """Every bead of the given issue types, in id order."""
        wanted = set(kinds)
        return [b for _, b in sorted(self.beads.items()) if b.kind in wanted]

    def ancestors(self, bead_id: str) -> list[Bead]:
        """The parent chain above a bead, nearest first, stopping at a cycle."""
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
        """The nearest Epic above a bead, walking Story -> Epic."""
        for ancestor in self.ancestors(bead_id):
            if ancestor.kind == "epic":
                return ancestor
        return None

    def descendants(self, bead_id: str) -> list[Bead]:
        """Every bead beneath a bead, at any depth."""
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
    """Parse a comma-separated bead-id list, tolerating spaces and empties."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def join_ids(ids: list[str] | set[str] | tuple[str, ...]) -> str:
    """Render a bead-id set as the comma-separated form metadata stores."""
    return ",".join(sorted(set(ids)))


def _bd(args: list[str], repo: Path | None) -> str:
    """Run `bd` and return stdout, raising GraphError on any failure."""
    command = ["bd", *args]
    if repo is not None:
        command += ["-C", str(repo)]
    try:
        done = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:  # pragma: no cover - environment, not logic
        msg = "`bd` is not on PATH"
        raise GraphError(msg) from exc
    if done.returncode != 0:
        msg = f"`{' '.join(command)}` exited {done.returncode}: {done.stderr.strip()}"
        raise GraphError(msg)
    return done.stdout


def bd_write(args: list[str], repo: Path | None) -> str:
    """Run a `bd` command that changes the tracker."""
    return _bd(args, repo)


def now_iso() -> str:
    """The current instant, ISO 8601 UTC, to the second."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_metadata(bead_id: str, pairs: dict[str, str], repo: Path | None) -> None:
    """Write pipeline metadata through the beads-contract CLI, which verifies the write."""
    command = [sys.executable, str(CONTRACT), "metadata", "set", bead_id]
    if repo is not None:
        command += ["-C", str(repo)]
    command += [f"{key}={value}" for key, value in pairs.items()]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        msg = f"metadata set on {bead_id} failed: {done.stdout.strip()} {done.stderr.strip()}"
        raise GraphError(msg)


def fingerprints(records: list[dict]) -> dict[str, str]:
    """The content fingerprint of every record, from the beads-contract CLI in one call.

    The records are handed over rather than re-fetched, so the fingerprint is taken over
    exactly the sweep the caller reasons about.

    Args:
        records: Tracker records as `bd list --json` returned them, descriptions included.

    Returns:
        Bead id -> content fingerprint.

    Raises:
        GraphError: The CLI refused or answered with something unusable.
    """
    command = [sys.executable, str(CONTRACT), "--records", "-", "fingerprint-batch"]
    done = subprocess.run(
        command, input=json.dumps(records), capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        msg = f"fingerprint-batch failed: {done.stdout.strip()} {done.stderr.strip()}"
        raise GraphError(msg)
    payload = json.loads(done.stdout or "{}")
    table = payload.get("fingerprints")
    if not isinstance(table, dict):
        msg = "fingerprint-batch returned no `fingerprints` map"
        raise GraphError(msg)
    return {str(k): str(v) for k, v in table.items()}


def _records_from_bd(repo: Path | None, *, with_description: bool) -> list[dict]:
    """Every issue, closed ones included, from one `bd list` call."""
    args = ["list", "--all", "--json", "-n", "0", "--readonly"]
    if not with_description:
        args.append("--brief")
    payload = json.loads(_bd(args, repo) or "[]")
    if not isinstance(payload, list):
        msg = "`bd list --json` did not return an array"
        raise GraphError(msg)
    return payload


def _records_from_export(repo: Path | None) -> list[dict]:
    """The passive `.beads/issues.jsonl` export — the fallback, never the preference."""
    root = repo or Path.cwd()
    path = root / ".beads" / "issues.jsonl"
    if not path.is_file():
        msg = f"no tracker: `bd` failed and {path} does not exist"
        raise GraphError(msg)
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _bead_of(record: dict) -> Bead:
    """Normalize one tracker record, tolerating every field `bd` omits when unset."""
    metadata = record.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata or "{}")
    blockers = [
        str(dep.get("depends_on_id"))
        for dep in record.get("dependencies") or []
        if dep.get("type") == BLOCKS and dep.get("depends_on_id")
    ]
    return Bead(
        id=str(record["id"]),
        title=str(record.get("title") or ""),
        kind=str(record.get("issue_type") or ""),
        status=str(record.get("status") or ""),
        parent=str(record["parent"]) if record.get("parent") else None,
        metadata={str(k): str(v) for k, v in metadata.items()},
        blockers=tuple(sorted(set(blockers))),
        description=str(record.get("description") or ""),
    )


def load(repo: Path | None = None, *, with_description: bool = False) -> Graph:
    """Read the whole tracker and normalize it, preferring `bd` over the export."""
    warnings: list[str] = []
    try:
        records = _records_from_bd(repo, with_description=with_description)
        source = "bd list --all --json"
    except GraphError as exc:
        warnings.append(f"bd unavailable, fell back to the passive export: {exc}")
        records = _records_from_export(repo)
        source = ".beads/issues.jsonl (export)"
    beads = {}
    for record in records:
        bead = _bead_of(record)
        beads[bead.id] = bead
    return Graph(beads=beads, source=source, records=records, warnings=warnings)
