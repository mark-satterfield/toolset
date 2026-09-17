"""The material-change queue, and the pass that drains it.

NOTHING HERE IS DERIVED FROM A TIMESTAMP, AN MTIME OR A HASH. A declaration is in the
queue because an agent that produced a work product SAID what it changed was something
others depend on. This module reads what was said; it never infers a change from the state
of a file, because a file's date moves when a formatter runs and its hash changes when a
sentence is reworded, and neither fact says whether anything else rests on what changed.

WHERE THE QUEUE IS. Each declaring agent writes ONE JSON object to
`<repo>/.claude/workflow-runs/artifacts/<epic-id>/material-change-<slot>.json` — the same
directory, and the same Write, that every other artifact of that Epic's run uses. One file
per declaration rather than one shared append-only log, because appending reliably needs a
shell and writing a file does not.

DRAINING IS A LEDGER, NOT A DELETE. A drained declaration stays exactly where it is; its
path and its content digest go into `drained.json` beside it. The artifact is evidence of
what the run did and deleting it to mark a queue empty would destroy the record. A file
whose content changes after it was drained comes back as pending, which is the honest
reading: it is a different declaration in the same slot.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

#: Where a run's artifacts live, relative to the repository the tracker is in.
ARTIFACT_ROOT = Path(".claude/workflow-runs/artifacts")
#: The per-Epic file name a declaring agent writes.
DECLARATION_GLOB = "material-change-*.json"
#: The ledger of declarations already acted on, written beside the artifacts.
DRAINED = "drained.json"


class QueueError(Exception):
    """Raised when the queue cannot be read or the ledger cannot be written."""


@dataclass(frozen=True)
class Declaration:
    """One agent's statement that what it produced is something others depend on."""

    #: Repo-relative path of the file the declaration was read from.
    path: str
    #: The Epic whose run produced it — the artifact directory's name.
    epic: str
    #: Content digest, so a rewritten slot is a new declaration rather than a drained one.
    digest: str
    material: bool
    kind: str | None
    summary: str | None
    decision_ids: tuple[str, ...]
    suspected_impact: tuple[str, ...]
    confidence: str | None
    producer: str | None
    at: str | None

    def as_dict(self) -> dict:
        """Return the declaration as a plain JSON-ready object.

        Returns:
            One object per declaration, with the queue's own fields (path, epic, digest)
            alongside what the agent declared.
        """
        return {
            "path": self.path,
            "epic": self.epic,
            "digest": self.digest,
            "material": self.material,
            "kind": self.kind,
            "summary": self.summary,
            "decisionIds": list(self.decision_ids),
            "suspectedImpact": list(self.suspected_impact),
            "confidence": self.confidence,
            "producer": self.producer,
            "at": self.at,
        }


def _texts(value: object) -> tuple[str, ...]:
    """Return a value as a tuple of non-empty strings, whatever shape it arrived in."""
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _artifact_root(directory: Path | None) -> Path:
    """Return the artifact root for a repository.

    Args:
        directory: The repository the tracker is in, or None for the working directory.

    Returns:
        The absolute artifact root. It may not exist; a missing root is an empty queue.
    """
    return (directory or Path.cwd()).resolve() / ARTIFACT_ROOT


def _read(path: Path, root: Path) -> Declaration | None:
    """Read one declaration file, or None when it is not a usable declaration.

    Args:
        path: The declaration file.
        root: The artifact root, for the reported relative path and the Epic name.

    Returns:
        The declaration, or None when the file is not valid JSON or is not an object. A
        malformed file is skipped rather than raised on: one agent's bad write must not
        make the whole queue unreadable.
    """
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return Declaration(
        path=str(path.relative_to(root.parent.parent.parent)),
        epic=path.parent.name,
        digest=hashlib.sha256(raw).hexdigest(),
        material=payload.get("material") is True,
        kind=payload.get("kind") if isinstance(payload.get("kind"), str) else None,
        summary=payload.get("summary") if isinstance(payload.get("summary"), str) else None,
        decision_ids=_texts(payload.get("decisionIds")),
        suspected_impact=_texts(payload.get("suspectedImpact")),
        confidence=payload.get("confidence")
        if isinstance(payload.get("confidence"), str)
        else None,
        producer=payload.get("producer") if isinstance(payload.get("producer"), str) else None,
        at=payload.get("at") if isinstance(payload.get("at"), str) else None,
    )


def _ledger(root: Path) -> dict[str, str]:
    """Return the drained ledger: declaration path -> digest drained.

    Args:
        root: The artifact root.

    Returns:
        The ledger, empty when it has never been written or cannot be read.
    """
    path = root / DRAINED
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in payload.items()} if isinstance(payload, dict) else {}


def queue(directory: Path | None, *, drain: bool = False) -> dict:
    """Report the material-change declarations waiting for a sequencing pass.

    Args:
        directory: The repository holding the run artifacts, or None for the working dir.
        drain: True to record the pending declarations as acted on. The files themselves
            are never touched — they are the run's evidence.

    Returns:
        An object naming the artifact root, the pending declarations, the union of the
        decision ids they name, and whether the ledger was written.

    Raises:
        QueueError: The drained ledger could not be written.
    """
    root = _artifact_root(directory)
    if not root.is_dir():
        return {
            "root": str(root),
            "pending": [],
            "decisionIds": [],
            "drained": False,
            "note": "no artifact directory — nothing has declared anything here",
        }
    seen = _ledger(root)
    pending: list[Declaration] = []
    for path in sorted(root.glob(f"*/{DECLARATION_GLOB}")):
        declaration = _read(path, root)
        if declaration is None or not declaration.material:
            continue
        if seen.get(declaration.path) == declaration.digest:
            continue
        pending.append(declaration)
    payload = {
        "root": str(root),
        "pending": [d.as_dict() for d in pending],
        # The union the sequencing pass acts on: every decision id some producer said
        # others depend on, and which nothing has been re-sequenced against yet.
        "decisionIds": sorted({i for d in pending for i in d.decision_ids}),
        "drained": False,
    }
    if drain and pending:
        seen.update({d.path: d.digest for d in pending})
        try:
            (root / DRAINED).write_text(json.dumps(seen, indent=2, sort_keys=True) + "\n")
        except OSError as exc:
            raise QueueError(f"the drained ledger could not be written: {exc}") from exc
        payload["drained"] = True
    return payload
