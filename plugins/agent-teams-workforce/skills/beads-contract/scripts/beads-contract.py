#!/usr/bin/env python3
"""beads-contract — reads and writes the pipeline's data on a bead.

Every command reads `bd show --json` (read-only) unless it is a `metadata set`, and prints one
JSON object on stdout naming where each value came from.

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

Common flags:
  -C <path>          Run `bd` from this repository (passed through as `bd -C`).
  --records <file>   Read records from a JSON array in <file> instead of calling `bd`, or
                     `-` to read that array from stdin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys

#: `readiness` hashes the record content and the build contract; `judging` hashes only the
#: title, description, issue_type and priority.
SCOPE_READINESS = "readiness"
SCOPE_JUDGING = "judging"
SCOPES = (SCOPE_READINESS, SCOPE_JUDGING)

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


def resolve_criteria(bead_id: str, reader: "Reader") -> dict:
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
    ("cds_bundle_path", "cdsBundlePath", KIND_TEXT),
    ("cds_build_specs", "cdsBuildSpecs", KIND_LIST),
)

#: Contract keys the readiness fingerprint covers only on a bead that carries them: a bead
#: with neither (every Task without a `web-ui` surface) hashes as if they were not in the contract.
CONTRACT_HASHED_WHEN_PRESENT = frozenset({"cds_bundle_path", "cds_build_specs"})

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
    """Raised when `bd` could not be run, or returned something unreadable."""


def _load_records(records_file: str) -> object:
    """Read a JSON array of records from a file, or from stdin for "-".

    Args:
        records_file: The path, or "-" for stdin.

    Returns:
        The decoded payload.

    Raises:
        BeadsError: If the text is not readable JSON.
    """
    text = (
        sys.stdin.read()
        if records_file == "-"
        else open(records_file, encoding="utf-8").read()
    )  # noqa: SIM115
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
            repo: Repository to run `bd` from, or "" for the current directory.
            records_file: A JSON array of records to read instead of calling `bd`,
                or "-" to read that array from stdin.

        Raises:
            BeadsError: If the supplied records are not readable JSON.
        """
        self.repo = repo
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

    def _read(self, args: list[str]) -> object:
        """Run one read-only `bd` command live, once, and parse its JSON.

        A failure is raised on the first occurrence, naming the command and the error `bd`
        printed.

        Args:
            args: Arguments after `bd`.

        Returns:
            The parsed stdout.

        Raises:
            BeadsError: `bd` failed or printed no JSON.
        """
        out = self._bd(args)
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
    reader._bd(command)  # noqa: SLF001
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
        The `metadata set` result for the three cds audit keys.

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
        "-C", dest="repo", default="", help="run `bd` from this repository"
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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one command.

    Args:
        argv: Argument vector, or None for sys.argv.

    Returns:
        The process exit status.
    """
    args = build_parser().parse_args(argv)
    try:
        reader = Reader(repo=args.repo, records_file=args.records)
        result = args.run(args, reader)
    except (ContractError, BeadsError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False)
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
