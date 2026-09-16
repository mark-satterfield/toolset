#!/usr/bin/env python3
"""beads-contract — the one executable statement of how this pipeline stores work on a bead.

WHY THIS IS CODE AND NOT PROSE. Two defects reached production because agents each
guessed the storage layout. The content-hash recipe was written twice — once as `jq`
prose in `skills/issue-ready/SKILL.md`, once in `ops/sdlc-automation/readiness.py` — and
the two copies disagreed about `labels`, so they disagreed about exactly the beads the
rule existed for. Separately, two work packages assumed acceptance criteria are a metadata
key; they are PROSE, and may live on a parent. Prose read by a model is not deterministic.
This is.

Every command reads `bd show --json` (read-only) unless it is a `metadata set`, prints one
JSON object on stdout, and says WHERE each value came from. Nothing here forms a judgment
about a bead: it reports what is recorded and where it was found.

Usage:
  beads-contract.py fingerprint <id> [--explain]
  beads-contract.py criteria <id>
  beads-contract.py contract <id> [--require]
  beads-contract.py ancestors <id>
  beads-contract.py record <id>
  beads-contract.py metadata get <id> [key ...]
  beads-contract.py metadata set <id> key=value [key=value ...]
  beads-contract.py selftest

Common flags:
  -C <path>          Run `bd` from this repository (passed through as `bd -C`).
  --records <file>   Read records from a JSON array in <file> instead of calling `bd`.
                     For exercising the parent and prose paths against synthesised
                     input; every read command honours it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys

# --------------------------------------------------------------------------------------
# The content fingerprint. THE SINGLE IMPLEMENTATION OF THIS RECIPE.
# --------------------------------------------------------------------------------------

#: The keys the fingerprint is taken over, in the order `jq -S` sorts them. SIX OF THESE
#: ARE ALWAYS NULL: `bd show --json` returns none of them, so they hash as null on every
#: bead. They are listed anyway — the digest is over the ten-key object, and dropping the
#: nulls would change it.
CONTENT_HASH_FIELDS = (
    "acceptance",
    "dependencies",
    "deps",
    "description",
    "design",
    "issue_type",
    "labels",
    "priority",
    "title",
    "type",
)

#: The only ones of those that carry a value. `labels` is EXCLUDED ON PURPOSE even though
#: `bd show` returns it: the pipeline writes a `needs-correction` label onto every held
#: bead, so hashing labels would make the act of RECORDING a hold invalidate the very
#: watermark the hold was recorded against, and the next sweep would re-buy the review.
CONTENT_HASH_PRESENT = frozenset({"description", "issue_type", "priority", "title"})

#: How many hex characters of the digest are stored (`cut -c1-16` on the shell side).
CONTENT_HASH_LENGTH = 16

#: The metadata key the readiness gate stores the fingerprint under.
CONTENT_HASH_KEY = "ready_content_hash"


def content_hash(rec: dict) -> str:
    """Return the content fingerprint for one bead record.

    The recipe: take the ten-key object above with only the four present keys carrying a
    value, serialize it as `jq -S` does (sorted keys, two-space indent, trailing newline),
    SHA-256 it, keep the first sixteen hex characters.

    Args:
        rec: One bead record, as `bd show --json` or `bd list --json` returned it.

    Returns:
        The fingerprint, or "" for a record with no content at all.
    """
    if not rec:
        return ""
    payload = fingerprint_payload(rec)
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:CONTENT_HASH_LENGTH]


def fingerprint_payload(rec: dict) -> dict:
    """Return the exact object the fingerprint is taken over.

    Args:
        rec: One bead record.

    Returns:
        The ten-key payload, nulls included.
    """
    return {key: (rec.get(key) if key in CONTENT_HASH_PRESENT else None) for key in CONTENT_HASH_FIELDS}


# --------------------------------------------------------------------------------------
# Acceptance criteria. PROSE, and they may live on a parent.
# --------------------------------------------------------------------------------------

#: A heading that opens a criteria section — a markdown heading (`## Acceptance Criteria`)
#: or a bare labelled line (`Acceptance criteria:`).
_CRITERIA_HEADING = re.compile(r"^\s{0,3}(?:#{1,6}\s*)?acceptance[ _-]*criteria\s*:?\s*$", re.IGNORECASE)

#: Any markdown heading, which ENDS a criteria section.
_ANY_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S")

#: A list item, bulleted or numbered.
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?P<text>.*\S)\s*$")

#: A criterion written as one Given/When/Then sentence, recognised anywhere — plenty of
#: issues state criteria that way under no heading at all.
_GIVEN_WHEN_THEN = re.compile(r"\bgiven\b.*\bwhen\b.*\bthen\b", re.IGNORECASE)

#: The three homes criteria can occupy on one bead, in search order.
SOURCE_METADATA = "metadata.acceptance_criteria"
SOURCE_ACCEPTANCE = "acceptance_criteria"
SOURCE_DESCRIPTION = "description"

#: The record field `bd create/update --acceptance` writes — first-class, neither metadata
#: nor prose, and invisible to anything that looks only at the other two.
ACCEPTANCE_FIELD = "acceptance_criteria"


def criteria_in_text(text: str) -> list[str]:
    """Pull acceptance criteria out of prose.

    Two shapes, in order: an `Acceptance Criteria` heading (taking the list items beneath
    it, or its non-empty prose lines when it has no list), then Given/When/Then sentences
    anywhere in the text.

    Args:
        text: The description or acceptance field to read.

    Returns:
        The criteria found, in the order they appear. Empty is a finding, not a failure.
    """
    lines = str(text or "").splitlines()
    found: list[str] = []
    in_section = False
    for line in lines:
        if _CRITERIA_HEADING.match(line):
            in_section = True
            continue
        if not in_section:
            continue
        if _ANY_HEADING.match(line):
            in_section = False
            continue
        bullet = _BULLET.match(line)
        if bullet:
            found.append(bullet.group("text").strip())
        elif line.strip():
            found.append(line.strip())
    if found:
        return found
    for line in lines:
        stripped = line.strip()
        if not stripped or not _GIVEN_WHEN_THEN.search(stripped):
            continue
        bullet = _BULLET.match(line)
        found.append(bullet.group("text").strip() if bullet else stripped)
    return found


def _criteria_on(bead_id: str, bead: dict, searched: list[str]) -> dict | None:
    """Return the criteria one bead carries, wherever on it they live.

    Args:
        bead_id: The bead being read.
        bead: Its record.
        searched: The running list of places looked. Appended to.

    Returns:
        The finding, or None when this bead carries none anywhere.
    """
    metadata = metadata_of(bead)
    searched.append(f"{bead_id} {SOURCE_METADATA}")
    raw = metadata.get("acceptance_criteria")
    if raw is not None and str(raw).strip():
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            values = [text for text in (str(item).strip() for item in parsed) if text]
            if values:
                return {"values": values, "sourceId": bead_id, "sourceField": SOURCE_METADATA}

    searched.append(f"{bead_id} {SOURCE_ACCEPTANCE}")
    stated = str(bead.get(ACCEPTANCE_FIELD) or "").strip()
    if stated:
        values = criteria_in_text(stated) or [line.strip() for line in stated.splitlines() if line.strip()]
        if values:
            return {"values": values, "sourceId": bead_id, "sourceField": SOURCE_ACCEPTANCE}

    searched.append(f"{bead_id} {SOURCE_DESCRIPTION}")
    values = criteria_in_text(bead.get("description") or "")
    if values:
        return {"values": values, "sourceId": bead_id, "sourceField": SOURCE_DESCRIPTION}
    return None


def resolve_criteria(bead_id: str, reader: "Reader") -> dict:
    """Find a Task's acceptance criteria wherever they were written down.

    THE REQUIREMENT IS THAT CRITERIA EXIST, not that a producer serialized them under one
    key. Looked for on the Task — metadata, the `--acceptance` record field, then its own
    description prose — and then on each ancestor in turn, NEAREST FIRST, because a Story
    or Epic that states the criteria for the work beneath it has stated them for this Task.

    Args:
        bead_id: The Task.
        reader: The record source.

    Returns:
        The finding: values, sourceId, sourceField, inherited, and every place looked.
    """
    searched: list[str] = []
    found = _criteria_on(bead_id, reader.get(bead_id), searched)
    if found is None:
        for ancestor in reader.ancestors(bead_id):
            found = _criteria_on(ancestor, reader.get(ancestor), searched)
            if found is not None:
                break
    if found is None:
        return {"values": [], "sourceId": "", "sourceField": "", "inherited": False, "searched": searched}
    found["inherited"] = found["sourceId"] != bead_id or found["sourceField"] != SOURCE_METADATA
    found["searched"] = searched
    return found


# --------------------------------------------------------------------------------------
# The build contract: the metadata keys this pipeline owns.
# --------------------------------------------------------------------------------------

#: The literal a producer writes when a field is UNDECIDED rather than empty. Compared
#: exactly — never case-folded, never trimmed into. UNKNOWN IS NOT EMPTY: a null `surfaces`
#: means nobody ruled and the phase falls back to its own lead, while `[]` means somebody
#: checked and the work crosses no boundary, which skips the phase outright.
UNKNOWN = "unknown"

KIND_TEXT = "text"
KIND_LIST = "list"
KIND_LIST_OR_UNKNOWN = "list-or-unknown"
KIND_OBJECT_OR_UNKNOWN = "object-or-unknown"

#: The build contract a Task carries: metadata key -> (argument name, shape). `bd` metadata
#: is flat key=value text, so every value is a string; lists and the strategy object are
#: compact JSON.
CONTRACT_SCHEMA = (
    ("spec_path", "specPath", KIND_TEXT),
    ("spec_paths", "specPaths", KIND_LIST),
    ("spec_sections", "specSections", KIND_LIST),
    ("acceptance_criteria", "acceptanceCriteria", KIND_LIST),
    ("definition_of_done", "definitionOfDone", KIND_LIST),
    ("requirement_ids", "requirementIds", KIND_LIST),
    ("surfaces", "surfaces", KIND_LIST_OR_UNKNOWN),
    ("test_strategy", "testStrategy", KIND_OBJECT_OR_UNKNOWN),
)

#: Either of these satisfies the spec reference, which IS required: the composite builds
#: against a contract it reads from disk, and with no path every downstream phase falls
#: back to the Task's own prose.
SPEC_REFERENCE = ("specPath", "specPaths")

#: Keys outside the build contract that the READINESS GATE owns on a bead.
GATE_KEYS = (
    "build_state",
    CONTENT_HASH_KEY,
    "review_status",
    "review_missing",
    "reviewed_at",
    "wsjf",
    "wsjf_calculated_at",
)

#: Keys the ELABORATION lane owns. Listed so `metadata get` can say which keys on a bead
#: belong to a known lane and which are strangers, and so a `metadata set` typo of one of
#: them is refused rather than written into a key nothing reads.
LANE_KEYS = (
    "artifact_spec_path",
    "elaboration_state",
    "elaboration_state_at",
    "elaboration_state_cause",
)

#: Every metadata key this pipeline owns. A `metadata set` of anything else is refused —
#: a typo'd key is silently invisible to every reader, which is the failure mode this
#: whole module exists to end.
KNOWN_KEYS = frozenset([source for source, _, _ in CONTRACT_SCHEMA] + list(GATE_KEYS) + list(LANE_KEYS))


class ContractError(ValueError):
    """Raised when a recorded contract value does not match the shape the schema states."""


def _read_value(source: str, kind: str, raw: str) -> object:
    """Return one recorded value in the shape the composite takes.

    Args:
        source: The metadata key, for the refusal text.
        kind: One of the KIND_* shapes.
        raw: The recorded text.

    Returns:
        The value to forward.

    Raises:
        ContractError: If the recorded value does not match the field's shape.
    """
    if kind == KIND_TEXT:
        return raw.strip()
    if kind == KIND_LIST:
        return _text_items(source, _parse_json(source, raw))
    if raw.strip() == UNKNOWN:
        return None
    if kind == KIND_LIST_OR_UNKNOWN:
        return _text_items(source, _parse_json(source, raw))
    parsed = _parse_json(source, raw)
    if not isinstance(parsed, dict):
        msg = f"metadata {source!r} is a {type(parsed).__name__}, not the JSON object the schema states (or {UNKNOWN!r})"
        raise ContractError(msg)
    return parsed


def _parse_json(source: str, raw: str) -> object:
    """Parse one metadata value, refusing rather than guessing.

    Args:
        source: The metadata key, for the refusal text.
        raw: The recorded text.

    Returns:
        The parsed value.

    Raises:
        ContractError: If the text is not JSON.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"metadata {source!r} is not valid JSON ({exc.msg} at char {exc.pos}); recorded as {raw[:120]!r}"
        raise ContractError(msg) from exc


def _text_items(source: str, value: object) -> list[str]:
    """Return a JSON array as the list of non-empty strings a reader takes.

    Args:
        source: The metadata key, for the refusal text.
        value: The parsed value.

    Returns:
        The items, stripped, with empties removed.

    Raises:
        ContractError: If the value is not a JSON array.
    """
    if not isinstance(value, list):
        msg = f"metadata {source!r} is a {type(value).__name__}, not the JSON array the schema states"
        raise ContractError(msg)
    return [text for text in (str(item).strip() for item in value) if text]


def read_contract(bead: dict) -> dict:
    """Read the build contract a Task records, in the shape the composite takes.

    A KEY THE BEAD DOES NOT CARRY IS ABSENT FROM THE RESULT, never defaulted. A Task
    written before the producer recorded contracts says nothing about its surfaces, and
    saying `[]` on its behalf would be a claim.

    Args:
        bead: The Task's record.

    Returns:
        The contract fields, keyed by argument name.

    Raises:
        ContractError: If a recorded value does not match the schema's shape.
    """
    metadata = metadata_of(bead)
    carried: dict = {}
    for source, name, kind in CONTRACT_SCHEMA:
        raw = metadata.get(source)
        if raw is None or not str(raw).strip():
            continue
        carried[name] = _read_value(source, kind, str(raw))
    return carried


# --------------------------------------------------------------------------------------
# Reading beads.
# --------------------------------------------------------------------------------------


def metadata_of(rec: dict) -> dict:
    """Return a record's custom metadata.

    Tolerates the two shapes `bd` emits: a JSON object, or that object serialized as a
    string. A key that was never set is ABSENT from the result, not empty.

    Args:
        rec: One bead record.

    Returns:
        The metadata mapping, or an empty dict.
    """
    raw = (rec or {}).get("metadata")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}
    return {}


class BeadsError(RuntimeError):
    """Raised when `bd` could not be run, or returned something unreadable."""


class Reader:
    """Resolves bead records, from `bd` or from a synthesised file."""

    def __init__(self, repo: str = "", records_file: str = "") -> None:
        """Build a reader.

        Args:
            repo: Repository to run `bd` from, or "" for the current directory.
            records_file: A JSON array of records to read instead of calling `bd`.
        """
        self.repo = repo
        self.cache: dict[str, dict] = {}
        self.offline = bool(records_file)
        if records_file:
            with open(records_file, encoding="utf-8") as handle:
                loaded = json.load(handle)
            for rec in loaded if isinstance(loaded, list) else [loaded]:
                self.cache[str(rec.get("id") or "")] = rec

    def _bd(self, args: list[str]) -> str:
        """Run one `bd` command and return its stdout.

        Args:
            args: Arguments after `bd`.

        Returns:
            The stdout text.

        Raises:
            BeadsError: If `bd` is absent or exited nonzero.
        """
        command = ["bd"] + (["-C", self.repo] if self.repo else []) + args
        try:
            done = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            msg = f"could not run `bd`: {exc}"
            raise BeadsError(msg) from exc
        if done.returncode != 0:
            msg = f"`{' '.join(command)}` exited {done.returncode}: {done.stderr.strip()[:400]}"
            raise BeadsError(msg)
        return done.stdout

    def get(self, bead_id: str) -> dict:
        """Return one bead's record, read-only.

        Args:
            bead_id: The bead.

        Returns:
            The record, or {} when the tracker does not know the id.

        Raises:
            BeadsError: If `bd` failed or its output could not be decoded.
        """
        if bead_id in self.cache:
            return self.cache[bead_id]
        if self.offline:
            self.cache[bead_id] = {}
            return {}
        text = self._bd(["show", bead_id, "--json", "--readonly"])
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            msg = f"`bd show {bead_id} --json` did not return JSON: {exc}"
            raise BeadsError(msg) from exc
        if isinstance(payload, list):
            rec = payload[0] if payload else {}
        elif isinstance(payload, dict):
            rec = payload.get("issue") if isinstance(payload.get("issue"), dict) else payload
        else:
            rec = {}
        self.cache[bead_id] = rec or {}
        return self.cache[bead_id]

    def ancestors(self, bead_id: str) -> list[str]:
        """Return the ancestor ids, nearest first, stopping at any cycle.

        Args:
            bead_id: The bead to walk up from.

        Returns:
            The chain of parent ids.
        """
        chain: list[str] = []
        seen = {bead_id}
        current = self.get(bead_id).get("parent")
        while current:
            parent_id = str(current)
            if parent_id in seen:
                break
            seen.add(parent_id)
            chain.append(parent_id)
            current = self.get(parent_id).get("parent")
        return chain


# --------------------------------------------------------------------------------------
# Commands.
# --------------------------------------------------------------------------------------


def cmd_fingerprint(args: argparse.Namespace, reader: Reader) -> dict:
    """Report the content fingerprint of one bead.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The result object.
    """
    rec = reader.get(args.id)
    stored = str(metadata_of(rec).get(CONTENT_HASH_KEY) or "").strip()
    current = content_hash(rec)
    result = {
        "id": args.id,
        "found": bool(rec),
        "fingerprint": current,
        "stored": stored,
        "fresh": bool(stored) and bool(current) and stored == current,
    }
    if args.explain:
        result["hashed"] = fingerprint_payload(rec)
        result["note"] = (
            "Six of the ten keys are null on every bead because `bd show --json` does not return them. "
            "`labels` is nulled deliberately: the pipeline labels every held bead `needs-correction`, so "
            "hashing labels would make recording a hold invalidate the watermark it was recorded against."
        )
    return result


def cmd_criteria(args: argparse.Namespace, reader: Reader) -> dict:
    """Report a Task's acceptance criteria and where they came from.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The result object.
    """
    found = resolve_criteria(args.id, reader)
    return {
        "id": args.id,
        "criteria": found["values"],
        "count": len(found["values"]),
        "sourceId": found["sourceId"],
        "sourceField": found["sourceField"],
        "inherited": found["inherited"],
        "searched": found["searched"],
        "note": (
            "Acceptance criteria are PROSE. They exist when they are found anywhere in the search order — "
            "this bead's metadata key, its `--acceptance` record field, its own description, then each "
            "ancestor nearest-first. An empty result means nowhere searched carried any."
        ),
    }


def cmd_contract(args: argparse.Namespace, reader: Reader) -> dict:
    """Report the full build contract a Task carries, with provenance.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The result object.

    Raises:
        ContractError: If a recorded contract value is malformed.
    """
    rec = reader.get(args.id)
    contract = read_contract(rec)
    criteria = resolve_criteria(args.id, reader)
    if criteria["values"]:
        contract["acceptanceCriteria"] = criteria["values"]
    metadata = metadata_of(rec)
    missing: list[str] = []
    if not any(contract.get(name) for name in SPEC_REFERENCE):
        missing.append("spec_path or spec_paths")
    if not criteria["values"]:
        missing.append("acceptance criteria (nowhere in the search order)")
    result = {
        "id": args.id,
        "found": bool(rec),
        "type": str(rec.get("issue_type") or ""),
        "parent": str(rec.get("parent") or ""),
        "contract": contract,
        "acceptanceCriteriaSource": (
            {"beadId": criteria["sourceId"], "field": criteria["sourceField"]} if criteria["inherited"] else None
        ),
        "criteriaSearched": criteria["searched"],
        "gate": {key: metadata[key] for key in GATE_KEYS if key in metadata},
        "missing": missing,
        "complete": not missing,
    }
    if args.require and missing:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(3)
    return result


def cmd_ancestors(args: argparse.Namespace, reader: Reader) -> dict:
    """Report a bead's parent chain, nearest first.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The result object.
    """
    chain = reader.ancestors(args.id)
    rec = reader.get(args.id)
    return {
        "id": args.id,
        "type": str(rec.get("issue_type") or ""),
        "ancestors": [
            {"id": anc, "type": str(reader.get(anc).get("issue_type") or ""), "title": str(reader.get(anc).get("title") or "")}
            for anc in chain
        ],
        "note": (
            "A parent is resolved from the record's own `parent` field, which `bd show --json` returns only "
            "when the bead has one. A Story is a roll-up parent for reporting; it is never a dispatch "
            "precondition. A BUG IS NEVER PARENTED and never walks this chain."
        ),
    }


def cmd_record(args: argparse.Namespace, reader: Reader) -> dict:
    """Report one bead's record and which fields it actually carries.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The result object.
    """
    rec = reader.get(args.id)
    return {
        "id": args.id,
        "found": bool(rec),
        "fields": sorted(rec.keys()),
        "fieldCount": len(rec),
        "record": rec,
        "note": (
            "`bd show --json` OMITS a field the bead does not carry, so the key set varies per bead. "
            "Never assume a fixed field list; ask this command."
        ),
    }


def cmd_metadata(args: argparse.Namespace, reader: Reader) -> dict:
    """Read or write the pipeline's metadata keys on one bead.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The result object.

    Raises:
        ContractError: If a write names a key outside the pipeline's namespace, or a
            value that does not match the shape the schema states for that key.
        BeadsError: If the write could not be run.
    """
    if args.op == "get":
        metadata = metadata_of(reader.get(args.id))
        if args.pairs:
            return {
                "id": args.id,
                "metadata": {key: metadata[key] for key in args.pairs if key in metadata},
                "absent": [key for key in args.pairs if key not in metadata],
            }
        # A BARE GET REPORTS EVERYTHING THE BEAD CARRIES, not just the keys this module
        # knows. Filtering to the known set would report a bead with metadata as having
        # none, which is exactly the kind of confident wrong answer this skill exists to
        # stop. Unknown keys are reported as unknown, never hidden.
        return {
            "id": args.id,
            "metadata": dict(metadata),
            "contract": {key: metadata[key] for key, _, _ in CONTRACT_SCHEMA if key in metadata},
            "gate": {key: metadata[key] for key in GATE_KEYS if key in metadata},
            "lane": {key: metadata[key] for key in LANE_KEYS if key in metadata},
            "unrecognized": sorted(key for key in metadata if key not in KNOWN_KEYS),
        }

    if reader.offline:
        msg = "`metadata set` writes to the tracker and cannot run against --records"
        raise ContractError(msg)
    updates: list[tuple[str, str]] = []
    for pair in args.pairs:
        if "=" not in pair:
            msg = f"{pair!r} is not key=value"
            raise ContractError(msg)
        key, value = pair.split("=", 1)
        key = key.strip()
        if key not in KNOWN_KEYS:
            msg = f"{key!r} is not a key this pipeline owns; known keys are {', '.join(sorted(KNOWN_KEYS))}"
            raise ContractError(msg)
        for source, _, kind in CONTRACT_SCHEMA:
            if source == key and value.strip():
                _read_value(source, kind, value)
        updates.append((key, value))

    command = ["update", args.id]
    for key, value in updates:
        command += ["--set-metadata", f"{key}={value}"]
    # `--set-metadata` MERGES. Never reach for `--metadata`, which replaces the whole
    # object and would drop every key this write did not name.
    reader._bd(command)  # noqa: SLF001 - the reader owns the one `bd` invocation path
    reader.cache.pop(args.id, None)
    written = metadata_of(reader.get(args.id))
    return {
        "id": args.id,
        "wrote": dict(updates),
        "verified": {key: written.get(key) for key, _ in updates},
        "ok": all(str(written.get(key) or "") == value for key, value in updates),
    }


# --------------------------------------------------------------------------------------
# Selftest — exercises the paths no live bead currently covers.
# --------------------------------------------------------------------------------------

_SELFTEST_RECORDS = [
    {
        "id": "syn-task-parent-criteria",
        "title": "Task whose criteria live only on its parent Story",
        "description": "Implement the thing. No criteria stated here.",
        "issue_type": "task",
        "priority": 2,
        "parent": "syn-story",
    },
    {
        "id": "syn-story",
        "title": "Story stating the criteria for the work beneath it",
        "description": "## Acceptance Criteria\n- The endpoint returns 201 on success\n- A duplicate returns 409\n\n## Notes\nnot a criterion",
        "issue_type": "story",
        "priority": 2,
        "parent": "syn-epic",
    },
    {
        "id": "syn-epic",
        "title": "Epic above it all",
        "description": "No criteria here either.",
        "issue_type": "epic",
        "priority": 1,
    },
    {
        "id": "syn-task-own-prose",
        "title": "Task stating its own criteria as prose",
        "description": "Acceptance criteria:\n- Given a signed-in user, when they save, then the record persists",
        "issue_type": "task",
        "priority": 2,
    },
    {
        "id": "syn-task-gwt-bare",
        "title": "Task stating criteria as bare Given/When/Then, no heading",
        "description": "Background.\nGiven an expired token, when the client retries, then it gets a 401.",
        "issue_type": "task",
        "priority": 2,
    },
    {
        "id": "syn-task-acceptance-field",
        "title": "Task using the --acceptance record field",
        "description": "Nothing in the description.",
        "acceptance_criteria": "The job exits 0\nThe report names every skipped bead",
        "issue_type": "task",
        "priority": 2,
    },
    {
        "id": "syn-task-metadata",
        "title": "Task with criteria mirrored into the metadata key",
        "description": "Nothing here.",
        "issue_type": "task",
        "priority": 2,
        "metadata": {
            "acceptance_criteria": '["Criterion from metadata"]',
            "spec_paths": '["docs/spec/thing.md"]',
            "surfaces": "unknown",
            "test_strategy": '{"pyramid": "unit-heavy"}',
        },
    },
    {
        "id": "syn-task-none",
        "title": "Task with criteria nowhere at all",
        "description": "Just prose, no criteria.",
        "issue_type": "task",
        "priority": 2,
    },
]


def cmd_selftest(_args: argparse.Namespace, _reader: Reader) -> dict:
    """Exercise the parent, prose, field and metadata paths against synthesised records.

    Returns:
        The result object: one entry per case, and an overall pass flag.

    Raises:
        SystemExit: With status 1 when any case fails.
    """
    reader = Reader()
    reader.offline = True
    for rec in _SELFTEST_RECORDS:
        reader.cache[rec["id"]] = rec

    cases = [
        ("criteria inherited from the parent Story", "syn-task-parent-criteria", 2, "syn-story", SOURCE_DESCRIPTION, True),
        ("criteria in the Task's own description prose", "syn-task-own-prose", 1, "syn-task-own-prose", SOURCE_DESCRIPTION, True),
        ("bare Given/When/Then with no heading", "syn-task-gwt-bare", 1, "syn-task-gwt-bare", SOURCE_DESCRIPTION, True),
        ("the --acceptance record field", "syn-task-acceptance-field", 2, "syn-task-acceptance-field", SOURCE_ACCEPTANCE, True),
        ("the metadata key", "syn-task-metadata", 1, "syn-task-metadata", SOURCE_METADATA, False),
        ("criteria nowhere", "syn-task-none", 0, "", "", False),
    ]
    results = []
    ok = True
    for name, bead_id, count, source_id, source_field, inherited in cases:
        found = resolve_criteria(bead_id, reader)
        passed = (
            len(found["values"]) == count
            and found["sourceId"] == source_id
            and found["sourceField"] == source_field
            and found["inherited"] == inherited
        )
        ok = ok and passed
        results.append(
            {
                "case": name,
                "pass": passed,
                "expected": {"count": count, "sourceId": source_id, "sourceField": source_field, "inherited": inherited},
                "observed": {
                    "count": len(found["values"]),
                    "sourceId": found["sourceId"],
                    "sourceField": found["sourceField"],
                    "inherited": found["inherited"],
                },
                "criteria": found["values"],
            }
        )

    # The ancestor walk, and the contract reader's unknown-is-not-empty rule.
    chain = reader.ancestors("syn-task-parent-criteria")
    chain_ok = chain == ["syn-story", "syn-epic"]
    ok = ok and chain_ok
    results.append({"case": "ancestor chain, nearest first", "pass": chain_ok, "observed": chain})

    contract = read_contract(reader.get("syn-task-metadata"))
    contract_ok = (
        contract.get("specPaths") == ["docs/spec/thing.md"]
        and "surfaces" in contract
        and contract["surfaces"] is None
        and contract.get("testStrategy") == {"pyramid": "unit-heavy"}
    )
    ok = ok and contract_ok
    results.append(
        {
            "case": "unknown surfaces becomes null and is not []",
            "pass": contract_ok,
            "observed": {key: contract.get(key) for key in ("specPaths", "surfaces", "testStrategy")},
        }
    )

    # The fingerprint is stable, ignores labels and metadata, and moves with the description.
    base = {"title": "t", "description": "d", "issue_type": "task", "priority": 2}
    labelled = dict(base, labels=["needs-correction"], metadata={"review_status": "INCOMPLETE"})
    changed = dict(base, description="d2")
    hash_ok = content_hash(base) == content_hash(labelled) and content_hash(base) != content_hash(changed)
    ok = ok and hash_ok
    results.append(
        {
            "case": "fingerprint ignores labels and metadata, moves with the description",
            "pass": hash_ok,
            "observed": {"base": content_hash(base), "labelled": content_hash(labelled), "changed": content_hash(changed)},
        }
    )

    if not ok:
        print(json.dumps({"pass": False, "cases": results}, indent=2, ensure_ascii=False))
        raise SystemExit(1)
    return {"pass": True, "cases": results}


# --------------------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(prog="beads-contract.py", description=__doc__.split("\n")[0])
    parser.add_argument("-C", dest="repo", default="", help="run `bd` from this repository")
    parser.add_argument("--records", default="", help="read records from this JSON array instead of calling `bd`")
    sub = parser.add_subparsers(dest="command", required=True)

    fingerprint = sub.add_parser("fingerprint", help="the content fingerprint, and whether the stored one is fresh")
    fingerprint.add_argument("id")
    fingerprint.add_argument("--explain", action="store_true", help="also print the exact object hashed")
    fingerprint.set_defaults(run=cmd_fingerprint)

    criteria = sub.add_parser("criteria", help="acceptance criteria, and where each was found")
    criteria.add_argument("id")
    criteria.set_defaults(run=cmd_criteria)

    contract = sub.add_parser("contract", help="the full build contract, with provenance")
    contract.add_argument("id")
    contract.add_argument("--require", action="store_true", help="exit 3 when a required part is missing")
    contract.set_defaults(run=cmd_contract)

    ancestors = sub.add_parser("ancestors", help="the parent chain, nearest first")
    ancestors.add_argument("id")
    ancestors.set_defaults(run=cmd_ancestors)

    record = sub.add_parser("record", help="the normalized record and the fields it carries")
    record.add_argument("id")
    record.set_defaults(run=cmd_record)

    metadata = sub.add_parser("metadata", help="read or write the pipeline's metadata keys")
    metadata.add_argument("op", choices=["get", "set"])
    metadata.add_argument("id")
    metadata.add_argument("pairs", nargs="*", help="keys to read, or key=value pairs to write")
    metadata.set_defaults(run=cmd_metadata)

    selftest = sub.add_parser("selftest", help="exercise the parent, prose and field paths on synthesised records")
    selftest.set_defaults(run=cmd_selftest)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one command.

    Args:
        argv: Argument vector, or None for sys.argv.

    Returns:
        The process exit status.
    """
    args = build_parser().parse_args(argv)
    reader = Reader(repo=args.repo, records_file=args.records)
    try:
        result = args.run(args, reader)
    except (ContractError, BeadsError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
