#!/usr/bin/env python3
"""Epic summaries: which ones are due, the portfolio as sessions read it, and recording them.

An Epic's PRD is its description, and the open portfolio's PRDs together are far more than
one session can hold. So every Epic carries a short stored summary — what it needs and
establishes architecturally, the value and urgency it carries, and what already exists for
it — beside the content fingerprint of the Epic it was written from. A session that must
hold the whole portfolio reads the summaries, and reads in full only the Epics it is
assessing or judging.

A summary is due when the Epic has none, or when the fingerprint it was written from no
longer matches the Epic. Nothing else regenerates one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from beadgraph import TRACKS, fingerprints, now_iso

if TYPE_CHECKING:
    from pathlib import Path

    from beadgraph import Bead, Graph, Writer

#: The summary text.
SUMMARY_KEY = "epic_summary"

#: The content fingerprint of the Epic the summary was written from.
SUMMARY_HASH_KEY = "epic_summary_hash"

#: When the summary was recorded.
SUMMARY_AT_KEY = "epic_summary_at"

#: The longest summary recorded, in words. A summary is a few hundred words; one far
#: longer defeats the purpose of reading the portfolio through summaries.
MAX_WORDS = 600

#: Metadata key set on an Epic by the elaboration pipeline, shown beside each summary.
ELAB_KEY = "elaboration_state"


class SummaryError(RuntimeError):
    """A summary file the recorder cannot work from."""


def _open_epics(graph: Graph, epics: list[str] | None) -> list[Bead]:
    """The open Epics, restricted to the named ones when any are named.

    Args:
        graph: The tracker graph.
        epics: Epic ids to restrict to, or None for every open Epic.

    Returns:
        The Epics, in id order.

    Raises:
        SummaryError: A named id is not an open Epic.
    """
    open_epics = [b for b in graph.of_kind("epic") if not b.closed]
    if epics is None:
        return open_epics
    known = {b.id for b in open_epics}
    stray = sorted(set(epics) - known)
    if stray:
        msg = f"not an open Epic: {', '.join(stray)}"
        raise SummaryError(msg)
    wanted = set(epics)
    return [b for b in open_epics if b.id in wanted]


def write_prds(epics: list[Bead], prd_dir: Path) -> dict[str, str]:
    """Write each Epic's PRD, its description, to its own file.

    Args:
        epics: The Epics.
        prd_dir: The directory to write into; created when absent.

    Returns:
        Epic id -> the file holding its PRD.
    """
    prd_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for epic in epics:
        path = prd_dir / f"{epic.id}.md"
        path.write_text(f"# {epic.title}\n\n{epic.description}\n", encoding="utf-8")
        paths[epic.id] = str(path)
    return paths


def summary_reason(epic: Bead, fingerprint: str) -> str:
    """Why an Epic's summary is due, or "" when the stored one is current.

    Args:
        epic: The Epic.
        fingerprint: Its content fingerprint now.

    Returns:
        The reason, or "".
    """
    if not (epic.metadata.get(SUMMARY_KEY) or "").strip():
        return "no summary"
    if epic.metadata.get(SUMMARY_HASH_KEY) != fingerprint:
        return "its PRD changed since it was summarized"
    return ""


def summary_plan(
    graph: Graph, *, epics: list[str] | None, prd_dir: Path | None
) -> dict:
    """The open Epics whose summary is due, with the fingerprint each is summarized at.

    Args:
        graph: The tracker graph, read with descriptions.
        epics: Epic ids to restrict to, or None for every open Epic.
        prd_dir: Where to write the PRD of each Epic that is due, or None.

    Returns:
        The due Epics with their reason, fingerprint and PRD file, and a summary that
        lists each due Epic's id, title and PRD file.
    """
    prints = fingerprints(graph.records)
    scope = _open_epics(graph, epics)
    due = []
    for epic in scope:
        reason = summary_reason(epic, prints.get(epic.id, ""))
        if reason:
            due.append((epic, reason))
    paths = write_prds([e for e, _ in due], prd_dir) if prd_dir else {}
    items = [
        {
            "id": epic.id,
            "title": epic.title,
            "reason": reason,
            "fingerprint": prints.get(epic.id, ""),
            "prdPath": paths.get(epic.id),
            "prdChars": len(epic.description),
        }
        for epic, reason in due
    ]
    return {
        "due": items,
        "summary": {
            "openEpics": len(scope),
            "due": len(items),
            "current": len(scope) - len(items),
            "epics": [
                {"id": i["id"], "title": i["title"], "prdPath": i["prdPath"]}
                for i in items
            ],
        },
    }


def _summary_text(entry: dict, epic_id: str) -> str:
    """Read one summary, validated.

    Args:
        entry: The summary record for one Epic.
        epic_id: The Epic, for the error message.

    Returns:
        The text, trimmed.

    Raises:
        SummaryError: The text is empty or longer than `MAX_WORDS`.
    """
    text = str(entry.get("summary") or "").strip()
    if not text:
        msg = f"{epic_id}: the summary is empty"
        raise SummaryError(msg)
    words = len(text.split())
    if words > MAX_WORDS:
        msg = f"{epic_id}: the summary is {words} words; the limit is {MAX_WORDS}"
        raise SummaryError(msg)
    return text


def record_summaries(
    graph: Graph, the_plan: dict, entries: list[dict], writer: Writer
) -> dict:
    """Write each summary with the fingerprint of the Epic content it was written from.

    Only Epics the plan named are written, each with the fingerprint the plan recorded,
    which is the content the summarizer read. Every summary is validated before any is
    written, so one bad summary refuses the whole record.

    Args:
        graph: The tracker graph.
        the_plan: The `summary-plan` output.
        entries: `{"id", "summary"}` records from the summarizing sessions.
        writer: The tracker writer; a dry-run writer records the writes instead.

    Returns:
        What was written, what the plan asked for and did not receive, a summary, and —
        in a dry run — every write in order.

    Raises:
        SummaryError: A summary names an Epic outside the plan, is repeated, or is
            invalid.
    """
    asked = {item["id"]: item["fingerprint"] for item in the_plan.get("due", [])}
    got: dict[str, dict] = {}
    for entry in entries:
        epic_id = str(entry.get("id") or "")
        if epic_id in got:
            msg = f"{epic_id}: more than one summary"
            raise SummaryError(msg)
        got[epic_id] = entry
    stray = sorted(set(got) - set(asked))
    if stray:
        msg = f"summaries for Epics the plan did not name: {', '.join(stray)}"
        raise SummaryError(msg)
    pending = []
    for epic_id in sorted(got):
        if epic_id not in graph.beads:
            msg = f"{epic_id}: not in the tracker"
            raise SummaryError(msg)
        pending.append(
            (
                epic_id,
                {
                    SUMMARY_KEY: _summary_text(got[epic_id], epic_id),
                    SUMMARY_HASH_KEY: asked[epic_id],
                    SUMMARY_AT_KEY: now_iso(),
                },
            )
        )
    for epic_id, pairs in pending:
        writer.metadata(epic_id, pairs)
    missing = sorted(set(asked) - set(got))
    return {
        "dryRun": writer.dry_run,
        "written": [epic_id for epic_id, _ in pending],
        "missing": missing,
        "planned": writer.planned,
        "summary": {
            "dryRun": writer.dry_run,
            "written": len(pending),
            "missing": len(missing),
        },
    }


def epic_edges(graph: Graph, epic: Bead) -> list[str]:
    """The Epics an Epic depends on, over every Epic-to-Epic edge whatever its type.

    Args:
        graph: The tracker graph.
        epic: The Epic.

    Returns:
        The ids, sorted.
    """
    upstream = set(epic.tracked) | set(epic.blockers)
    return sorted(
        i for i in upstream if i in graph.beads and graph.beads[i].kind == "epic"
    )


def portfolio(graph: Graph, *, prd_dir: Path | None, markdown: Path) -> dict:
    """Render every open Epic as the document a whole-portfolio session reads.

    Each Epic appears with its title, elaboration state, the Epics it depends on and its
    stored summary; with `prd_dir`, its full PRD is written to a file and named. An Epic
    whose summary is missing or out of date is marked, so the reader opens its PRD
    instead of trusting the summary.

    Args:
        graph: The tracker graph, read with descriptions.
        prd_dir: Where to write every open Epic's PRD, or None.
        markdown: The document to write.

    Returns:
        The document's path and counts.
    """
    prints = fingerprints(graph.records)
    epics = _open_epics(graph, None)
    paths = write_prds(epics, prd_dir) if prd_dir else {}
    blocks = [
        "# Open Epic portfolio",
        "",
        f"{len(epics)} open Epics. Edge type between Epics: `{TRACKS}`. "
        "`Depends on` lists the Epics each one's architecture is designed after.",
        "",
    ]
    stale = 0
    for epic in epics:
        reason = summary_reason(epic, prints.get(epic.id, ""))
        stale += bool(reason)
        upstream = epic_edges(graph, epic)
        lines = [
            f"## {epic.id} — {epic.title}",
            "",
            f"- Elaboration: {epic.metadata.get(ELAB_KEY) or 'unset'}",
            f"- Depends on: {', '.join(upstream) if upstream else 'none'}",
        ]
        if paths.get(epic.id):
            lines.append(f"- PRD: {paths[epic.id]}")
        lines.append("")
        if reason:
            lines.append(f"_Summary unavailable ({reason}): read the PRD._")
        else:
            lines.append(epic.metadata[SUMMARY_KEY].strip())
        lines.append("")
        blocks += lines
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text("\n".join(blocks), encoding="utf-8")
    counts = {
        "openEpics": len(epics),
        "withSummary": len(epics) - stale,
        "withoutSummary": stale,
        "markdown": str(markdown),
    }
    return {"prdPaths": paths, "summary": counts}
