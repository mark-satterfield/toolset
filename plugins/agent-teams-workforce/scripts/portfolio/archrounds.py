"""Durable round plans consumed by archresume and architecture.js; no dispatch here."""

from __future__ import annotations

import json
import os
from pathlib import Path


def save_ledger(path: Path, payload: dict) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    temporary.replace(path)


def overlap_justified(plan: dict, claim: dict, reviewers: list) -> bool:
    """Return whether the plan states a reason for several reviewers sharing one claim.

    The coordinator states one reason per overlap in the plan's ``overlaps``. A plan
    saved before that field existed counts as justified when any overlapping dispatch
    carries a non-empty ``overlapReason``.

    Returns:
        True when a plan-level overlap entry or a legacy dispatch reason covers it.
    """
    names = {d.get("agentType") for d in reviewers}
    for entry in plan.get("overlaps") or []:
        if not isinstance(entry, dict) or not str(entry.get("reason", "")).strip():
            continue
        agents = {str(a).strip() for a in entry.get("agentTypes") or [] if a}
        if agents and not names <= agents:
            continue
        files = {str(f).strip().lstrip("/") for f in entry.get("files") or [] if f}
        if claim["id"] in (entry.get("claimIds") or []) or claim.get("file") in files:
            return True
    return any(str(d.get("overlapReason", "")).strip() for d in reviewers)


def round_facts(
    work: Path,
    plans: list,
    incoming: dict | None,
    ledger: object,
    roles: dict,
    team: dict,
    coverage: list | None = None,
) -> dict:
    """Settle existing plan identities and bind post-writer review without another agent."""
    plans = json.loads(json.dumps(plans))
    kept = ""
    legacy_round = ledger.last if not plans else 0
    decision_path = work / "decision.json"
    decision = json.loads(decision_path.read_text()) if decision_path.is_file() else {}
    resume_round = legacy_round if legacy_round > decision.get("round", 0) else None
    if incoming:
        same = next((p for p in plans if p["round"] == incoming.get("round")), None)
        if same is not None and same is plans[-1] and not _done(work, same):
            # The saved plan of an unfinished round stands; its missing dispatches run.
            kept = (
                f"round {same['round']} already has a saved plan that is not complete; "
                "the saved plan is kept and the new plan was not saved"
            )
        elif same is not None:
            raise ValueError("cannot replace a durable round plan")
        elif plans and not _done(work, plans[-1]):
            raise ValueError("finish pending round before selecting another")
        else:
            if resume_round:
                incoming = json.loads(json.dumps(incoming))
                incoming["round"] = resume_round
                saved = []
                for name in ledger.files:
                    path = Path(name)
                    rn, seq, role, agent = path.stem.split("-", 3)
                    if int(rn[1:]) == resume_round:
                        saved.append(
                            {
                                "seq": int(seq),
                                "role": role,
                                "agentType": agent,
                                "legacySaved": True,
                                "task": "Preserve completed saved work",
                                "files": [],
                                "answers": [],
                            }
                        )
                incoming["dispatches"] = (
                    sorted(saved, key=lambda d: d["seq"]) + incoming["dispatches"]
                )
                incoming["legacyContinuation"] = True
            plans.append(incoming)
    if plans:
        reconcile_scope(work, plans[-1], coverage or [], team)

    gaps = []
    warnings = []
    for plan in plans:
        n = plan.get("round")
        dispatches = plan.get("dispatches")
        if not isinstance(n, int) or n < 1 or not isinstance(dispatches, list):
            raise ValueError("invalid durable round plan")
        writers = [d for d in dispatches if d.get("role") in ("proposer", "diagram")]
        proposers = [
            d["agentType"]
            for d in writers
            if d["role"] == "proposer"
            and not d.get("legacySaved")
            and not d.get("scopeCoverageIds")
        ]
        if (
            len(proposers) > 2
            or len(set(proposers)) != len(proposers)
            or any(w not in (team.get("lead"), team.get("second")) for w in proposers)
        ):
            raise ValueError("durable plan exceeds retained proposal budget")
        for seq, d in enumerate(dispatches, 1):
            if roles.get(d.get("agentType")) != d.get("role"):
                raise ValueError("durable plan names invalid role")
            seq = (
                d.get("seq", seq)
                if d.get("legacySaved")
                else max([x.get("seq", 0) for x in dispatches[: seq - 1]] + [0]) + 1
            )
            d["seq"] = seq
            file = work / "rounds" / f"r{n}-{seq}-{d['role']}-{d['agentType']}.json"
            d["file"] = str(file)
            d["complete"] = file.is_file()
            if file.is_file():
                result = json.loads(file.read_text())
                required = (
                    ("files", "claims", "answers") if d in writers else ("findings",)
                )
                if not d.get("legacySaved"):
                    required += ("coverage",) if d in writers else ("coverageChecks",)
                if not isinstance(result, dict) or any(
                    not isinstance(result.get(k), list) for k in required
                ):
                    raise ValueError(f"malformed saved dispatch result: {file}")
        if all(d["complete"] for d in writers):
            for d in dispatches:
                if d in writers or "assignedClaims" in d:
                    continue
                ids, files = d.get("claimIds", []), d.get("claimFiles", [])
                if any(i not in {c["id"] for c in ledger.claims} for i in ids):
                    raise ValueError("review assignment names unknown claim")
                d["assignedClaims"] = [
                    {"id": c["id"], "revision": c["revision"]}
                    for c in ledger.claims
                    if c["active"]
                    and (c["id"] in ids or (c["file"] in files and c["round"] == n))
                ]
            by_claim = {}
            for d in dispatches:
                for c in d.get("assignedClaims", []):
                    by_claim.setdefault((c["id"], c["revision"]), []).append(d)
            for (cid, revision), reviewers in by_claim.items():
                claim = next(c for c in ledger.claims if c["id"] == cid)
                if len(reviewers) > 1 and not overlap_justified(plan, claim, reviewers):
                    warning = (
                        f"round {n}: claim {cid} is reviewed by "
                        f"{', '.join(d['agentType'] for d in reviewers)} "
                        "with no stated overlap reason"
                    )
                    if warning not in warnings:
                        warnings.append(warning)
                if not claim["active"] or claim["revision"] != revision:
                    continue
                for d in reviewers:
                    if not any(
                        v["by"] == d["agentType"] and v.get("revision") == revision
                        for v in claim["verdicts"]
                    ):
                        gaps.append(
                            f"claim {cid} revision {revision} lacks assigned review by {d['agentType']}"
                        )
        plan["complete"] = all(d["complete"] for d in dispatches)
    pending = next((p for p in plans if not p["complete"]), None)
    last = max(
        [ledger.last if not pending else pending["round"] - 1]
        + [p["round"] for p in plans if p["complete"]]
    )
    return {
        "plans": plans,
        "resumeRound": resume_round if not plans else None,
        "last": last,
        "pendingPlan": pending,
        "reviewGaps": gaps,
        "overlapWarnings": warnings,
        "planKept": kept,
    }


def _done(work: Path, plan: dict) -> bool:
    """Return whether every dispatch of a saved plan has its result file on disk.

    Returns:
        True when each dispatch's result file exists (an empty plan is done).
    """
    n = plan.get("round")
    return all(
        (
            work
            / "rounds"
            / f"r{n}-{d.get('seq', seq)}-{d.get('role')}-{d.get('agentType')}.json"
        ).is_file()
        for seq, d in enumerate(plan.get("dispatches") or [], 1)
    )


def compact_plan(plan: dict | None) -> dict | None:
    """Return the pending plan as the few facts architecture.js branches on.

    The full plan (each dispatch's task, claim assignments and result file) stays in
    ledger.json, where the dispatched sessions read it; printing it would pass tens of
    kilobytes through the runner that relays this output.

    Returns:
        None for no plan, else round, readyForDecision and each dispatch's identity.
    """
    if not plan:
        return None
    return {
        "round": plan["round"],
        "readyForDecision": bool(plan.get("readyForDecision")),
        "complete": bool(plan.get("complete")),
        "dispatches": [
            {
                "seq": d["seq"],
                "role": d.get("role"),
                "agentType": d.get("agentType"),
                "complete": bool(d.get("complete")),
                "files": list(d.get("files") or []),
                "answers": list(d.get("answers") or []),
                "assignedClaimCount": len(d.get("assignedClaims") or []),
            }
            for d in plan["dispatches"]
        ],
    }


def reconcile_scope(work: Path, plan: dict, rows: list, team: dict) -> None:
    """Complete restricted legacy assignments without discarding their saved output."""
    dispatches = plan.get("dispatches", [])
    lead = team.get("lead")
    if not lead or not dispatches:
        return
    covered = {key for d in dispatches for key in d.get("scopeCoverageIds", [])}
    needed = {}
    for row in rows:
        if (
            row.get("excluded")
            or row.get("status") in ("Present and sufficient", "Not yet applicable")
            or row.get("id") in covered
        ):
            continue
        paths = []
        for view in row.get("views", []):
            path = Path(view)
            if path.is_relative_to(work / "draft"):
                paths.append(str(path.relative_to(work / "draft")))
        if paths:
            needed[row["id"]] = paths
    if not needed:
        return
    # A saved output is retained. New work gets a distinct result identity in the same round.
    pending_writers = [
        d
        for seq, d in enumerate(dispatches, 1)
        if d.get("role") in ("proposer", "diagram")
        and not (
            work
            / "rounds"
            / f"r{plan['round']}-{d.get('seq', seq)}-{d['role']}-{d['agentType']}.json"
        ).is_file()
    ]
    lead_pending = next(
        (d for d in pending_writers if d.get("agentType") == lead), None
    )
    owned = {
        f for d in pending_writers if d is not lead_pending for f in d.get("files", [])
    }
    files = sorted({f for paths in needed.values() for f in paths} - owned)
    if not files:
        return
    task = (
        "Finish only unresolved required coverage rows "
        + ", ".join(needed)
        + ". Preserve accepted work and the previous producer result. You own the listed "
        "draft views needed by these obligations; create missing views and reconcile "
        "their references. Return changed claims and coverage, without repeating completed work."
    )
    if lead_pending:
        lead_pending["files"] = sorted(set(lead_pending.get("files", [])) | set(files))
        lead_pending["task"] = str(lead_pending.get("task", "")) + "\n" + task
        lead_pending["scopeCoverageIds"] = sorted(
            set(lead_pending.get("scopeCoverageIds", [])) | set(needed)
        )
    else:
        dispatches.append(
            {
                "role": "proposer",
                "agentType": lead,
                "task": task,
                "files": files,
                "answers": [],
                "scopeCoverageIds": list(needed),
            }
        )
    pending_reviews = [
        d
        for seq, d in enumerate(dispatches, 1)
        if d.get("role") in ("reviewer", "cost")
        and not (
            work
            / "rounds"
            / f"r{plan['round']}-{d.get('seq', seq)}-{d['role']}-{d['agentType']}.json"
        ).is_file()
    ]
    if not pending_reviews:
        reviewer = next((d for d in dispatches if d.get("role") == "reviewer"), None)
        if reviewer:
            pending_reviews = [
                {
                    "role": "reviewer",
                    "agentType": reviewer["agentType"],
                    "task": "Independently review only the supplemental coverage repair and its changed claims.",
                    "files": [],
                    "answers": [],
                }
            ]
            dispatches.extend(pending_reviews)
    for reviewer in pending_reviews:
        reviewer.pop("assignedClaims", None)
    if pending_reviews:
        reviewer = pending_reviews[0]
        assigned_elsewhere = {
            f for other in pending_reviews[1:] for f in other.get("claimFiles", [])
        }
        reviewer["claimFiles"] = sorted(
            set(reviewer.get("claimFiles", [])) | (set(files) - assigned_elsewhere)
        )
        reviewer["task"] = (
            str(reviewer.get("task", ""))
            + "\nIndependently verify supplemental coverage rows "
            + ", ".join(needed)
            + " at their current revisions and only the changed claims in the supplemental files."
        )
    plan["readyForDecision"] = False
