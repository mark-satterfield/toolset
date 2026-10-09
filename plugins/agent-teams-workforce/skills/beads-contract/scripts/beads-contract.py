#!/usr/bin/env python3
"""beads-contract — reads and writes the pipeline's data on a bead.

Every command reads `bd show --json` (read-only) unless it is a `metadata set`, and prints one
JSON object on stdout naming where each value came from. `bd` runs every other `bd` command,
printing what `bd` prints.

Every command runs `bd` against the CENTRAL beads database, the control repository's
(`$ATW_CONTROL_REPO`), wherever it is run from. A write to a bead filed in a fleet
repository's own database runs in that database, because the one-way fleet sync copies the
fleet copy over the central one.

Usage:
  beads-contract.py fingerprint <id> [--explain] [--scope readiness|judging]
  beads-contract.py fingerprint-batch [id ...] [--explain] [--scope readiness|judging]
  beads-contract.py criteria <id>
  beads-contract.py contract <id>
  beads-contract.py ancestors <id>
  beads-contract.py record <id>
  beads-contract.py metadata get <id> [key ...]
  beads-contract.py metadata set <id> key=value [key=value ...]
  beads-contract.py cds-audit <id> '<cdsAudit JSON>'
  beads-contract.py bd <bd arguments ...>     (the plugin's `atw-bd` command runs this)

Common flags:
  -C <path>          The central repository, when it is not `$ATW_CONTROL_REPO`.
  --records <file>   Read records from a JSON array in <file> instead of calling `bd`, or
                     `-` to read that array from stdin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

#: `readiness` hashes the record content and the build contract; `judging` hashes only the
#: title, description, issue_type and priority.
SCOPE_READINESS = "readiness"
SCOPE_JUDGING = "judging"
SCOPES = (SCOPE_READINESS, SCOPE_JUDGING)

#: The pause before each retry of a `bd` command that could not reach the beads server, in
#: seconds: 6 attempts, 62s of waiting in all, then the error is raised.
CONNECTION_BACKOFF = (2, 4, 8, 16, 32)

#: The `bd` subcommands that only read; any other subcommand without `--readonly` writes.
READ_COMMANDS = frozenset(
    {"list", "ready", "show", "search", "count", "stats", "blocked"}
)

#: A write whose commit `bd` reports as indeterminate may have applied; it is never retried.
NEVER_RETRIED = re.compile(
    r"write commit result indeterminate|not retried to avoid double-apply",
    re.IGNORECASE,
)

#: (pattern, retried for a write too, reason). A write is retried only on an error that
#: shows the command never reached the database; a read is retried on every entry.
RETRYABLE_CONNECTION: tuple[tuple[re.Pattern[str], bool, str], ...] = (
    (
        re.compile(r"failed to open database", re.IGNORECASE),
        True,
        "bd failed opening the database (schema skew check included), before the command ran",
    ),
    (
        re.compile(r"connection refused", re.IGNORECASE),
        True,
        "the beads server refused the connection, so the command never reached it",
    ),
    (
        re.compile(r"dial tcp[^\n]*i/o timeout", re.IGNORECASE),
        True,
        "opening the connection timed out, so the command never reached the server",
    ),
    (
        re.compile(r"i/o timeout", re.IGNORECASE),
        False,
        "the beads server did not answer in time; a read is safe to run again",
    ),
    (
        re.compile(r"invalid connection|bad connection", re.IGNORECASE),
        False,
        "the connection to the beads server dropped; a read is safe to run again",
    ),
)


#: What `bd` prints on standard error when another writer held a lock.
LOCK_CONTENTION = re.compile(
    r"database is locked|lock wait timeout|deadlock", re.IGNORECASE
)
#: What `bd` prints on standard error when the beads server or its connection failed.
SERVER_FAILURE = re.compile(
    r"i/o timeout|connection refused|deadline exceeded|"
    r"invalid connection|bad connection|failed to open database|"
    r"write commit result indeterminate",
    re.IGNORECASE,
)


def failure_cause(stderr: str) -> str:
    """The cause of a failed `bd` command, from what `bd` printed on standard error.

    Args:
        stderr: `bd`'s standard error, without the command line.

    Returns:
        `contention` when another writer held a lock, `bd-timeout` when the beads server
        or its connection failed, else `other`.
    """
    if LOCK_CONTENTION.search(stderr):
        return "contention"
    return "bd-timeout" if SERVER_FAILURE.search(stderr) else "other"


def connection_retryable(args: list[str], stderr: str) -> str:
    """The reason a failed `bd` command may be run again, or "" when it may not.

    Args:
        args: Arguments after `bd`.
        stderr: What `bd` printed on standard error.

    Returns:
        The reason from RETRYABLE_CONNECTION, or "".
    """
    if NEVER_RETRIED.search(stderr):
        return ""
    is_read = "--readonly" in args or (bool(args) and args[0] in READ_COMMANDS)
    for pattern, safe_for_write, reason in RETRYABLE_CONNECTION:
        if pattern.search(stderr) and (safe_for_write or is_read):
            return reason
    return ""


#: The environment variable naming the control repository; its beads database is the
#: central one, where the pipeline files its Epics, Stories and Tasks.
CONTROL_REPO_ENV = "ATW_CONTROL_REPO"

#: A bead id: a prefix, a hyphen, a hash or number, and any hierarchical suffixes.
BEAD_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*-[A-Za-z0-9]+(?:\.[0-9]+)*$")

#: `bd` subcommands whose bead operand follows a verb: `dep add <id>`, `label add <id>`.
VERB_GROUPS = frozenset({"dep", "label", "comment", "comments"})

#: The flags that would point `bd` at another database; `bd` passthrough refuses them,
#: because choosing the database is what it is for.
DATABASE_FLAGS = frozenset({"-C", "--directory", "--db", "--database", "--global"})

#: Every bead the one-way fleet sync copied into the central database, with the
#: repository (relative to the central one) whose database it was filed in.
FLEET_QUERY = (
    "SELECT id, source_repo FROM issues WHERE source_repo <> '' AND source_repo <> '.'"
)


def central_repo(explicit: str = "") -> str:
    """The repository whose beads database is the central one.

    Args:
        explicit: A repository the caller named with `-C`, or "".

    Returns:
        `explicit`, else `$ATW_CONTROL_REPO`, else "" (the working directory), with a
        warning on stderr, since the working directory is central only in the control repo.
    """
    if explicit:
        return explicit
    control = os.environ.get(CONTROL_REPO_ENV, "").strip()
    if control:
        return control
    print(
        f"[beads-contract] ${CONTROL_REPO_ENV} is unset: `bd` runs in {os.getcwd()}, "
        "which holds the central beads database only when it is the control repository",
        file=sys.stderr,
    )
    return ""


def is_read(args: list[str]) -> bool:
    """Whether a `bd` command only reads.

    Args:
        args: Arguments after `bd`.

    Returns:
        True for `--readonly` or a subcommand in READ_COMMANDS.
    """
    words = [a for a in args if not a.startswith("-")]
    return "--readonly" in args or (bool(words) and words[0] in READ_COMMANDS)


def bead_operand(args: list[str]) -> str:
    """The bead a `bd` command acts on: the operand after its subcommand (or verb).

    Args:
        args: Arguments after `bd`.

    Returns:
        The bead id, or "" when the command names none (`create`, `list`, `dep add --file`).
    """
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 1
    if i >= len(args):
        return ""
    sub = args[i]
    i += 1
    if (
        sub in VERB_GROUPS
        and i < len(args)
        and not args[i].startswith("-")
        and not BEAD_ID.match(args[i])
    ):
        i += 1
    return args[i] if i < len(args) and BEAD_ID.match(args[i]) else ""


def fleet_homes(rows: object, central: str) -> dict[str, str]:
    """Map each bead filed in a fleet repository's database to that repository.

    The fleet-to-central sync is one-way and copies a fleet bead over the central copy
    each time it runs, so a fleet bead is written in its own database, never centrally.

    Args:
        rows: The decoded `bd sql --json` result of FLEET_QUERY.
        central: The central repository, or "" for the working directory.

    Returns:
        bead id -> absolute repository path.
    """
    base = central or os.getcwd()
    homes: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        source = str(row.get("source_repo") or "").strip()
        if source and source != ".":
            homes[str(row["id"])] = os.path.normpath(os.path.join(base, source))
    return homes


#: The record keys the readiness fingerprint is taken over; keys outside
#: CONTENT_HASH_PRESENT are hashed as null.
CONTENT_HASH_FIELDS = (
    "acceptance",
    "acceptance_criteria",
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

CONTENT_HASH_PRESENT = frozenset(
    {
        "acceptance_criteria",
        "description",
        "design",
        "issue_type",
        "priority",
        "title",
    }
)

#: The record keys the judging fingerprint is taken over; keys outside JUDGING_HASH_PRESENT
#: are hashed as null.
JUDGING_HASH_FIELDS = (
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
JUDGING_HASH_PRESENT = frozenset({"description", "issue_type", "priority", "title"})

CONTENT_HASH_LENGTH = 16

CONTENT_HASH_KEY = "ready_content_hash"


def content_hash(rec: dict, scope: str = SCOPE_READINESS) -> str:
    """Return a bead record's content fingerprint for a scope.

    The first sixteen hex characters of the SHA-256 of `fingerprint_payload` serialized
    with sorted keys, two-space indent and a trailing newline.

    Args:
        rec: One bead record, as `bd show --json` or `bd list --json` returned it.
        scope: `readiness` or `judging`.

    Returns:
        The fingerprint, or "" for a record with no content at all.
    """
    if not rec:
        return ""
    payload = fingerprint_payload(rec, scope)
    text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:CONTENT_HASH_LENGTH]


def fingerprint_payload(rec: dict, scope: str = SCOPE_READINESS) -> dict:
    """Return the object a fingerprint is taken over.

    Args:
        rec: One bead record.
        scope: `judging`, or anything else for `readiness`.

    Returns:
        The scope's record-level keys, nulls included, plus — for `readiness` — a
        `metadata` member holding the build contract keys.
    """
    if scope == SCOPE_JUDGING:
        return {
            key: (rec.get(key) if key in JUDGING_HASH_PRESENT else None)
            for key in JUDGING_HASH_FIELDS
        }
    metadata = metadata_of(rec)
    payload: dict = {
        key: (rec.get(key) if key in CONTENT_HASH_PRESENT else None)
        for key in CONTENT_HASH_FIELDS
    }
    payload["metadata"] = {
        source: metadata.get(source)
        for source, _, _ in CONTRACT_SCHEMA
        if source not in CONTRACT_HASHED_WHEN_PRESENT or source in metadata
    }
    return payload


#: A markdown heading or labelled line that opens an acceptance criteria section.
_CRITERIA_HEADING = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*)?acceptance[ _-]*criteria\s*:?\s*$", re.IGNORECASE
)

#: Any markdown heading, which ENDS a criteria section.
_ANY_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+\S")

#: A list item, bulleted or numbered.
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?P<text>.*\S)\s*$")

#: A criterion written as one Given/When/Then sentence.
_GIVEN_WHEN_THEN = re.compile(r"\bgiven\b.*\bwhen\b.*\bthen\b", re.IGNORECASE)

#: The three homes criteria can occupy on one bead, in search order.
SOURCE_METADATA = "metadata.acceptance_criteria"
SOURCE_ACCEPTANCE = "acceptance_criteria"
SOURCE_DESCRIPTION = "description"

#: The record field `bd create/update --acceptance` writes.
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
                return {
                    "values": values,
                    "sourceId": bead_id,
                    "sourceField": SOURCE_METADATA,
                }

    searched.append(f"{bead_id} {SOURCE_ACCEPTANCE}")
    stated = str(bead.get(ACCEPTANCE_FIELD) or "").strip()
    if stated:
        values = criteria_in_text(stated) or [
            line.strip() for line in stated.splitlines() if line.strip()
        ]
        if values:
            return {
                "values": values,
                "sourceId": bead_id,
                "sourceField": SOURCE_ACCEPTANCE,
            }

    searched.append(f"{bead_id} {SOURCE_DESCRIPTION}")
    values = criteria_in_text(bead.get("description") or "")
    if values:
        return {
            "values": values,
            "sourceId": bead_id,
            "sourceField": SOURCE_DESCRIPTION,
        }
    return None


def resolve_criteria(bead_id: str, reader: Reader) -> dict:
    """Find a Task's acceptance criteria.

    Searches the Task's metadata, its `--acceptance` field and its description, then each
    ancestor nearest first, and returns the first found.

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
        return {
            "values": [],
            "sourceId": "",
            "sourceField": "",
            "inherited": False,
            "searched": searched,
        }
    found["inherited"] = (
        found["sourceId"] != bead_id or found["sourceField"] != SOURCE_METADATA
    )
    found["searched"] = searched
    return found


#: The literal a producer writes for an undecided value; read as None.
UNKNOWN = "unknown"

KIND_TEXT = "text"
KIND_LIST = "list"
KIND_LIST_OR_UNKNOWN = "list-or-unknown"
KIND_OBJECT_OR_UNKNOWN = "object-or-unknown"

#: The build contract a Task carries: metadata key -> (argument name, shape). Lists and the
#: strategy object are stored as compact JSON strings.
CONTRACT_SCHEMA = (
    ("repoPath", "repoPath", KIND_TEXT),
    ("spec_path", "specPath", KIND_TEXT),
    ("spec_paths", "specPaths", KIND_LIST),
    ("spec_sections", "specSections", KIND_LIST),
    ("acceptance_criteria", "acceptanceCriteria", KIND_LIST),
    ("definition_of_done", "definitionOfDone", KIND_LIST),
    ("requirement_ids", "requirementIds", KIND_LIST),
    ("decision_ids", "decisionIds", KIND_LIST),
    ("surfaces", "surfaces", KIND_LIST_OR_UNKNOWN),
    ("test_strategy", "testStrategy", KIND_OBJECT_OR_UNKNOWN),
    ("cds_design_source", "cdsDesignSource", KIND_TEXT),
    ("cds_artifact", "cdsArtifact", KIND_OBJECT_OR_UNKNOWN),
    ("cds_bundle_path", "cdsBundlePath", KIND_TEXT),
    ("cds_build_specs", "cdsBuildSpecs", KIND_LIST),
)

#: Contract keys the readiness fingerprint covers only on a bead that carries them: a bead
#: with none (every Task without a `web-ui` surface) hashes as if they were not in the contract.
CONTRACT_HASHED_WHEN_PRESENT = frozenset(
    {"cds_design_source", "cds_artifact", "cds_bundle_path", "cds_build_specs"}
)

SPEC_REFERENCE = ("specPath", "specPaths")

REPO_REFERENCE = "repoPath"

#: Metadata keys the readiness gate writes.
GATE_KEYS = (
    "build_state",
    CONTENT_HASH_KEY,
    "review_status",
    "review_missing",
    "reviewed_at",
)

#: Metadata keys WSJF scoring writes.
WSJF_KEYS = (
    "wsjf",
    "wsjf_calculated_at",
    "wsjf_rubric",
    "wsjf_ubv",
    "wsjf_tc",
    "wsjf_rroe",
    "wsjf_unblocks",
    "wsjf_reaches",
    "wsjf_cod",
    "wsjf_size",
    "wsjf_size_source",
    "wsjf_size_estimate",
    "wsjf_size_low",
    "wsjf_size_high",
    "wsjf_size_confidence",
    "wsjf_size_outside_range",
    "wsjf_confidence",
    "wsjf_value_from",
    "wsjf_content_hash",
)

#: Metadata keys dependency assessment writes. `seq_owned_blockers` lists the edges it
#: created; `seq_edge_reasons` and `seq_edge_withdrawn` are JSON objects keyed by blocker id.
SEQUENCING_KEYS = (
    "seq_owned_blockers",
    "seq_owned_blockers_at",
    "seq_content_hash",
    "seq_edge_reasons",
    "seq_edge_withdrawn",
    "seq_assessed_at",
)

#: Metadata keys the elaboration lane writes.
LANE_KEYS = (
    "artifact_spec_path",
    "elaboration_state",
    "elaboration_state_at",
    "elaboration_state_cause",
    "elaboration_state_owner",
    "elab_key",
    "elab_follows",
)

#: Metadata keys on a Story. `story_owned_blockers` lists the Story edges `depscore.py
#: story-edges` created and `story_edge_reasons` is a JSON object keyed by blocker id; the
#: `story_deploy_*`, `story_ssm_missing` and `story_pr_url` keys are the host's record of
#: the Story's deploy.
STORY_KEYS = (
    "story_owned_blockers",
    "story_owned_blockers_at",
    "story_edge_reasons",
    "story_deploy_state",
    "story_deploy_attempt",
    "story_deploy_error",
    "story_ssm_missing",
    "story_pr_url",
)

#: The cds audit verdict of a web-ui Task: task-to-deploy's `cdsAudit` result, written
#: by the build lane and by `cds-audit` for a run dispatched by hand.
CDS_AUDIT_KEYS = (
    "cds_audit_verdict",
    "cds_audit_findings",
    "cds_audit_script_version",
    "cds_audit_design_source",
    "cds_audit_bundle",
)

#: The verdicts task-to-deploy's `cdsAudit` result carries.
CDS_AUDIT_VERDICTS = ("pass", "fail", "blocked", "error")

#: Every metadata key this pipeline writes; `metadata get` lists other keys as unrecognized.
KNOWN_KEYS = frozenset(
    [source for source, _, _ in CONTRACT_SCHEMA]
    + list(GATE_KEYS)
    + list(LANE_KEYS)
    + list(WSJF_KEYS)
    + list(SEQUENCING_KEYS)
    + list(STORY_KEYS)
    + list(CDS_AUDIT_KEYS)
)


class ContractError(ValueError):
    """Raised when a `metadata set` argument is not key=value."""


#: Returned by `_read_value` for a value that does not parse into its shape.
_UNREADABLE = object()


def _read_value(kind: str, raw: str) -> object:
    """Return one recorded contract value in the shape the composite takes.

    Args:
        kind: One of the KIND_* shapes.
        raw: The recorded text.

    Returns:
        The value; None for `unknown` where the shape allows it; `_UNREADABLE` when the
        text does not parse into the shape.
    """
    if kind == KIND_TEXT:
        return raw.strip()
    if kind != KIND_LIST and raw.strip() == UNKNOWN:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _UNREADABLE
    if kind == KIND_OBJECT_OR_UNKNOWN:
        return parsed if isinstance(parsed, dict) else _UNREADABLE
    if not isinstance(parsed, list):
        return _UNREADABLE
    return [text for text in (str(item).strip() for item in parsed) if text]


def read_contract(bead: dict) -> dict:
    """Read the build contract a Task records, in the shape the composite takes.

    Args:
        bead: The Task's record.

    Returns:
        The contract fields, keyed by argument name. A key the bead does not carry, or
        whose value does not parse into its shape, is absent.
    """
    metadata = metadata_of(bead)
    carried: dict = {}
    for source, name, kind in CONTRACT_SCHEMA:
        raw = metadata.get(source)
        if raw is None or not str(raw).strip():
            continue
        value = _read_value(kind, str(raw))
        if value is not _UNREADABLE:
            carried[name] = value
    return carried


def metadata_of(rec: dict) -> dict:
    """Return a record's custom metadata, stored as a JSON object or a JSON string.

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
    """Raised when `bd` could not be run, or returned something unreadable.

    `cause` is set where `bd` fails, from `bd`'s standard error (`failure_cause`).
    """

    def __init__(self, message: str, cause: str = "other") -> None:
        """Keep the message and the cause.

        Args:
            message: What failed.
            cause: `contention`, `bd-timeout` or `other`.
        """
        super().__init__(message)
        self.cause = cause


def _load_records(records_file: str) -> object:
    """Read a JSON array of records from a file, or from stdin for "-".

    Args:
        records_file: The path, or "-" for stdin.

    Returns:
        The decoded payload.

    Raises:
        BeadsError: If the text is not readable JSON.
    """
    if records_file == "-":
        text = sys.stdin.read()
    else:
        with open(records_file, encoding="utf-8") as handle:
            text = handle.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        where = "stdin" if records_file == "-" else records_file
        msg = f"records from {where} are not valid JSON ({exc.msg} at char {exc.pos})"
        raise BeadsError(msg) from exc


class Reader:
    """Resolves bead records, from `bd` or from a synthesised file."""

    def __init__(self, repo: str = "", records_file: str = "") -> None:
        """Build a reader.

        Args:
            repo: The central repository named with `-C`, or "" for `$ATW_CONTROL_REPO`.
            records_file: A JSON array of records to read instead of calling `bd`,
                or "-" to read that array from stdin.

        Raises:
            BeadsError: If the supplied records are not readable JSON.
        """
        self.repo = central_repo(repo) if not records_file else repo
        self.homes: dict[str, str] | None = None
        self.written: dict[str, str] = {}
        self.cache: dict[str, dict] = {}
        self.supplied: list[str] = []
        self.offline = bool(records_file)
        if records_file:
            self._absorb(_load_records(records_file))

    def _absorb(self, loaded: object) -> None:
        """Index a decoded `bd --json` payload into the cache.

        Args:
            loaded: The decoded payload — a list of records, or a single record.
        """
        for rec in loaded if isinstance(loaded, list) else [loaded]:
            if not isinstance(rec, dict):
                continue
            bead_id = str(rec.get("id") or "")
            if bead_id not in self.cache:
                self.supplied.append(bead_id)
            self.cache[bead_id] = rec

    def home_of(self, bead_id: str) -> str:
        """The repository whose database a bead is written in.

        A bead filed in a fleet repository's database is written there: the one-way sync
        would copy the fleet copy back over a central edit. Every other bead is written in
        the central database. One query, on the first write, lists the fleet beads.

        Args:
            bead_id: The bead.

        Returns:
            The fleet repository the bead was filed in, or the central repository.
        """
        if self.homes is None:
            try:
                rows = self._read(
                    ["--readonly", "sql", "--json", FLEET_QUERY], self.repo
                )
            except BeadsError as exc:
                print(
                    f"[beads-contract] could not list the fleet beads ({exc}); "
                    f"{bead_id} is written in the central database",
                    file=sys.stderr,
                )
                rows = []
            self.homes = fleet_homes(rows, self.repo)
        return self.homes.get(bead_id, self.repo)

    def route(self, args: list[str]) -> str:
        """The repository a `bd` command runs in.

        A write runs in the database its bead was filed in (`home_of`); a read runs in the
        central database, or in the one this process last wrote the bead in.

        Args:
            args: Arguments after `bd`.

        Returns:
            The repository, or "" for the working directory.
        """
        bead_id = bead_operand(args)
        if not bead_id:
            return self.repo
        if is_read(args):
            return self.written.get(bead_id, self.repo)
        home = self.home_of(bead_id)
        self.written[bead_id] = home
        return home

    def _bd(
        self, args: list[str], repo: str | None = None, stdin: str | None = None
    ) -> str:
        """Run one `bd` command and return its stdout.

        A command that could not reach the beads server is run again after each pause in
        CONNECTION_BACKOFF, as connection_retryable allows; every failed attempt is printed
        to stderr with the command and its error.

        Args:
            args: Arguments after `bd`.
            repo: The repository to run it in; None routes it with `route`.
            stdin: Text for its standard input, or None.

        Returns:
            The stdout text.

        Raises:
            BeadsError: If `bd` is absent, or exited nonzero with an error that is not
                retried or on its last attempt.
        """
        where = self.route(args) if repo is None else repo
        command = ["bd"] + (["-C", where] if where else []) + args
        attempts = len(CONNECTION_BACKOFF) + 1
        for attempt in range(1, attempts + 1):
            try:
                done = subprocess.run(
                    command, input=stdin, capture_output=True, text=True, check=False
                )
            except OSError as exc:
                msg = f"could not run `bd`: {exc}"
                raise BeadsError(msg) from exc
            if done.returncode == 0:
                if attempt > 1:
                    print(
                        f"[beads-contract] `{' '.join(command)}` succeeded on attempt {attempt}",
                        file=sys.stderr,
                    )
                return done.stdout
            stderr = done.stderr.strip()
            msg = f"`{' '.join(command)}` exited {done.returncode}: {stderr[:2000]}"
            why = connection_retryable(args, stderr)
            if not why or attempt == attempts:
                if why:
                    msg += f" (failed {attempts} times to reach the beads server)"
                raise BeadsError(msg, failure_cause(stderr))
            pause = CONNECTION_BACKOFF[attempt - 1]
            print(
                f"[beads-contract] attempt {attempt} of {attempts} failed: {msg}; "
                f"retrying in {pause}s because {why}",
                file=sys.stderr,
            )
            time.sleep(pause)
        msg = f"`{' '.join(command)}` was never run"
        raise BeadsError(msg)

    def _read(self, args: list[str], repo: str | None = None) -> object:
        """Run one read-only `bd` command live and parse its JSON.

        A connection failure is retried with backoff by `_bd`, each attempt printed; any
        other failure is raised at once, naming the command and the error `bd` printed.

        Args:
            args: Arguments after `bd`.
            repo: The repository to run it in; None routes it with `route`.

        Returns:
            The parsed stdout.

        Raises:
            BeadsError: `bd` failed or printed no JSON.
        """
        out = self._bd(args, repo)
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            msg = f"`bd {' '.join(args)}` printed no JSON: {exc}: {out.strip()[:400]}"
            raise BeadsError(msg) from exc

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
        payload = self._read(["show", bead_id, "--json", "--readonly"])
        if isinstance(payload, list):
            rec = payload[0] if payload else {}
        elif isinstance(payload, dict):
            rec = (
                payload.get("issue")
                if isinstance(payload.get("issue"), dict)
                else payload
            )
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

    def sweep(self) -> list[str]:
        """Fetch every bead, closed included, in one `bd list` call and index the records.

        Returns:
            The ids the sweep returned, in the order `bd` listed them.

        Raises:
            BeadsError: If `bd` failed or its output could not be decoded.
        """
        payload = self._read(["list", "--json", "--all", "--limit", "0", "--readonly"])
        before = set(self.cache)
        self._absorb(payload)
        return [bead_id for bead_id in self.supplied if bead_id not in before]


#: Printed by `--explain`.
FINGERPRINT_NOTE = (
    "`readiness` hashes the record content and the build contract keys under `metadata`; "
    "`judging` hashes title, description, issue_type and priority. `labels`, `dependencies`, "
    "the gate keys and the WSJF keys are never hashed."
)


def fingerprint_of(
    bead_id: str, rec: dict, explain: bool = False, scope: str = SCOPE_READINESS
) -> dict:
    """Report the fingerprint of one record.

    Args:
        bead_id: The bead the record belongs to.
        rec: Its record, or {} when nothing carries that id.
        explain: Also return the exact object hashed.
        scope: `readiness` or `judging`.

    Returns:
        The per-bead result: scope, found, fingerprint, and `stored` and `fresh` against
        the stored readiness fingerprint.
    """
    stored = str(metadata_of(rec).get(CONTENT_HASH_KEY) or "").strip()
    current = content_hash(rec, scope)
    result = {
        "id": bead_id,
        "scope": scope,
        "found": bool(rec),
        "fingerprint": current,
        "stored": stored,
        "fresh": bool(stored) and bool(current) and stored == current,
    }
    if explain:
        result["hashed"] = fingerprint_payload(rec, scope)
    return result


def cmd_fingerprint(args: argparse.Namespace, reader: Reader) -> dict:
    """Report the content fingerprint of one bead.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The result object.
    """
    result = fingerprint_of(
        args.id, reader.get(args.id), explain=args.explain, scope=args.scope
    )
    if args.explain:
        result["note"] = FINGERPRINT_NOTE
    return result


def cmd_fingerprint_batch(args: argparse.Namespace, reader: Reader) -> dict:
    """Fingerprint many beads: the named ids, or every supplied or swept record.

    With `--records` no tracker call is made; otherwise one `bd list` sweep.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The result object: a map of id to per-bead result, plus what was not found.

    Raises:
        BeadsError: If the sweep failed.
    """
    if reader.offline:
        source = "records"
    else:
        reader.sweep()
        source = "sweep"
    ids = list(args.ids) if args.ids else list(reader.supplied)

    results: dict[str, dict] = {}
    for bead_id in ids:
        if bead_id in results:
            continue
        results[bead_id] = fingerprint_of(
            bead_id, reader.get(bead_id), scope=args.scope
        )

    missing = sorted(
        bead_id for bead_id, entry in results.items() if not entry["found"]
    )
    result = {
        "count": len(results),
        "scope": args.scope,
        "source": source,
        "trackerCalls": 0 if source == "records" else 1,
        "fingerprints": {
            bead_id: entry["fingerprint"] for bead_id, entry in results.items()
        },
        "results": results,
        "missing": missing,
    }
    if args.explain:
        for bead_id, entry in results.items():
            entry["hashed"] = fingerprint_payload(reader.get(bead_id), args.scope)
        result["note"] = FINGERPRINT_NOTE
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
    """
    rec = reader.get(args.id)
    contract = read_contract(rec)
    criteria = resolve_criteria(args.id, reader)
    if criteria["values"]:
        contract["acceptanceCriteria"] = criteria["values"]
    metadata = metadata_of(rec)
    missing: list[str] = []
    if not contract.get(REPO_REFERENCE):
        missing.append(
            "repoPath (the repository is ruled during elaboration and recorded on the Task)"
        )
    if not any(contract.get(name) for name in SPEC_REFERENCE):
        missing.append("spec_path or spec_paths")
    if not criteria["values"]:
        missing.append("acceptance criteria (nowhere in the search order)")
    story_id = next(
        (
            anc
            for anc in reader.ancestors(args.id)
            if str(reader.get(anc).get("issue_type") or "") == "story"
        ),
        "",
    )
    story = (
        {"id": story_id, "title": str(reader.get(story_id).get("title") or "")}
        if story_id
        else None
    )
    if story is None:
        missing.append(
            "story (a Task is built on its Story's branch and deploys with its Story)"
        )
    result = {
        "id": args.id,
        "found": bool(rec),
        "type": str(rec.get("issue_type") or ""),
        "parent": str(rec.get("parent") or ""),
        "contract": contract,
        "bead": {
            "id": args.id,
            "title": str(rec.get("title") or ""),
            "description": str(rec.get("description") or ""),
            **contract,
            **({"story": story} if story else {}),
        },
        "acceptanceCriteriaSource": (
            {"beadId": criteria["sourceId"], "field": criteria["sourceField"]}
            if criteria["inherited"]
            else None
        ),
        "criteriaSearched": criteria["searched"],
        "gate": {key: metadata[key] for key in GATE_KEYS if key in metadata},
        "missing": missing,
        "complete": not missing,
    }
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
            {
                "id": anc,
                "type": str(reader.get(anc).get("issue_type") or ""),
                "title": str(reader.get(anc).get("title") or ""),
            }
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
        The result object; a `set` reports the values read back after the write.

    Raises:
        ContractError: A `set` argument is not key=value.
        BeadsError: The write could not be run.
    """
    if args.op == "get":
        metadata = metadata_of(reader.get(args.id))
        if args.pairs:
            return {
                "id": args.id,
                "metadata": {
                    key: metadata[key] for key in args.pairs if key in metadata
                },
                "absent": [key for key in args.pairs if key not in metadata],
            }
        return {
            "id": args.id,
            "metadata": dict(metadata),
            "contract": {
                key: metadata[key] for key, _, _ in CONTRACT_SCHEMA if key in metadata
            },
            "gate": {key: metadata[key] for key in GATE_KEYS if key in metadata},
            "lane": {key: metadata[key] for key in LANE_KEYS if key in metadata},
            "wsjf": {key: metadata[key] for key in WSJF_KEYS if key in metadata},
            "sequencing": {
                key: metadata[key] for key in SEQUENCING_KEYS if key in metadata
            },
            "cdsAudit": {
                key: metadata[key] for key in CDS_AUDIT_KEYS if key in metadata
            },
            "unrecognized": sorted(key for key in metadata if key not in KNOWN_KEYS),
        }

    updates: list[tuple[str, str]] = []
    for pair in args.pairs:
        if "=" not in pair:
            msg = f"{pair!r} is not key=value"
            raise ContractError(msg)
        key, value = pair.split("=", 1)
        updates.append((key.strip(), value))

    command = ["update", args.id]
    for key, value in updates:
        command += ["--set-metadata", f"{key}={value}"]
    reader._bd(command)
    reader.cache.pop(args.id, None)
    written = metadata_of(reader.get(args.id))
    return {
        "id": args.id,
        "wrote": dict(updates),
        "verified": {key: written.get(key) for key, _ in updates},
        "ok": True,
    }


def cmd_cds_audit(args: argparse.Namespace, reader: Reader) -> dict:
    """Write a web-ui Task's cds audit verdict from task-to-deploy's `cdsAudit` result.

    Args:
        args: Parsed arguments.
        reader: The record source.

    Returns:
        The `metadata set` result for the cds audit keys: the verdict, the finding count,
        the script version, the design source the build used and the bundle it used.

    Raises:
        ContractError: The result is not a cdsAudit object with a known verdict.
    """
    try:
        audit = json.loads(args.result)
    except ValueError as exc:
        msg = f"the cdsAudit result is not JSON: {exc}"
        raise ContractError(msg) from exc
    if not isinstance(audit, dict) or audit.get("verdict") not in CDS_AUDIT_VERDICTS:
        msg = f"the cdsAudit result carries no verdict among {', '.join(CDS_AUDIT_VERDICTS)}"
        raise ContractError(msg)
    findings = audit.get("findings")
    count = (
        findings if isinstance(findings, int) and not isinstance(findings, bool) else 0
    )
    version = str(audit.get("scriptVersion") or "").strip()[:100]
    args.op = "set"
    args.pairs = [
        f"cds_audit_verdict={audit['verdict']}",
        f"cds_audit_findings={count}",
        f"cds_audit_script_version={version}",
        f"cds_audit_design_source={str(audit.get('designSource') or '').strip()[:20]}",
        f"cds_audit_bundle={str(audit.get('bundle') or '').strip()[:1000]}",
    ]
    return cmd_metadata(args, reader)


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="beads-contract.py", description=__doc__.split("\n")[0]
    )
    parser.add_argument(
        "-C",
        dest="repo",
        default="",
        help="the central repository, when it is not $ATW_CONTROL_REPO",
    )
    parser.add_argument(
        "--records",
        default="",
        help="read records from this JSON array instead of calling `bd`; `-` reads the array from stdin",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fingerprint = sub.add_parser(
        "fingerprint",
        help="the content fingerprint, and whether the stored one is fresh",
    )
    fingerprint.add_argument("id")
    fingerprint.add_argument(
        "--explain", action="store_true", help="also print the exact object hashed"
    )
    fingerprint.add_argument("--scope", choices=SCOPES, default=SCOPE_READINESS)
    fingerprint.set_defaults(run=cmd_fingerprint)

    batch = sub.add_parser(
        "fingerprint-batch",
        help="fingerprint many beads in one invocation — one tracker call, or none with --records -",
    )
    batch.add_argument(
        "ids",
        nargs="*",
        help="the beads to fingerprint; omit for every record supplied or swept",
    )
    batch.add_argument(
        "--explain",
        action="store_true",
        help="also print the exact object hashed for each",
    )
    batch.add_argument("--scope", choices=SCOPES, default=SCOPE_READINESS)
    batch.set_defaults(run=cmd_fingerprint_batch)

    criteria = sub.add_parser(
        "criteria", help="acceptance criteria, and where each was found"
    )
    criteria.add_argument("id")
    criteria.set_defaults(run=cmd_criteria)

    contract = sub.add_parser(
        "contract", help="the full build contract, with provenance"
    )
    contract.add_argument("id")
    contract.set_defaults(run=cmd_contract)

    ancestors = sub.add_parser("ancestors", help="the parent chain, nearest first")
    ancestors.add_argument("id")
    ancestors.set_defaults(run=cmd_ancestors)

    record = sub.add_parser(
        "record", help="the normalized record and the fields it carries"
    )
    record.add_argument("id")
    record.set_defaults(run=cmd_record)

    metadata = sub.add_parser(
        "metadata", help="read or write the pipeline's metadata keys"
    )
    metadata.add_argument("op", choices=["get", "set"])
    metadata.add_argument("id")
    metadata.add_argument(
        "pairs", nargs="*", help="keys to read, or key=value pairs to write"
    )
    metadata.set_defaults(run=cmd_metadata)

    cds_audit = sub.add_parser(
        "cds-audit",
        help="write a web-ui Task's cds audit verdict from task-to-deploy's cdsAudit result",
    )
    cds_audit.add_argument("id")
    cds_audit.add_argument("result", help="the run's `cdsAudit` object, as JSON")
    cds_audit.set_defaults(run=cmd_cds_audit)

    sub.add_parser(
        "bd",
        help="run any `bd` command against the central database (a fleet-filed bead's "
        "write against its own); prints what `bd` prints",
    )
    return parser


def passthrough(argv: list[str]) -> tuple[str, list[str]] | None:
    """Split `[-C <repo>] bd <args>` into the central repository and the `bd` arguments.

    Args:
        argv: The argument vector.

    Returns:
        (repo, bd arguments), or None when the command is not `bd`.
    """
    repo = ""
    i = 0
    while i < len(argv):
        if argv[i] == "-C" and i + 1 < len(argv):
            repo = argv[i + 1]
            i += 2
        elif argv[i] == "bd":
            return repo, argv[i + 1 :]
        else:
            return None
    return None


def run_passthrough(repo: str, args: list[str]) -> int:
    """Run one `bd` command against the database it belongs in and print its output.

    Args:
        repo: The central repository named with `-C`, or "".
        args: The `bd` arguments.

    Returns:
        0, or 2 when `bd` failed or the arguments name a database themselves.
    """
    named = sorted(DATABASE_FLAGS.intersection(a.split("=", 1)[0] for a in args))
    if not args or named:
        why = (
            f"`bd` passthrough chooses the database itself; drop {', '.join(named)}"
            if named
            else "name the `bd` command to run"
        )
        print(f"[beads-contract] {why}", file=sys.stderr)
        return 2
    reads_stdin = "-" in args or "--stdin" in args
    stdin = sys.stdin.read() if reads_stdin else None
    try:
        out = Reader(repo=repo)._bd(args, stdin=stdin)
    except BeadsError as exc:
        print(f"[beads-contract] {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(out)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run one command.

    Args:
        argv: Argument vector, or None for sys.argv.

    Returns:
        The process exit status.
    """
    argv = sys.argv[1:] if argv is None else argv
    split = passthrough(argv)
    if split is not None:
        return run_passthrough(*split)
    args = build_parser().parse_args(argv)
    try:
        reader = Reader(repo=args.repo, records_file=args.records)
        result = args.run(args, reader)
    except (ContractError, BeadsError) as exc:
        cause = getattr(exc, "cause", "other")
        print(
            json.dumps(
                {"ok": False, "error": str(exc), "cause": cause},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
