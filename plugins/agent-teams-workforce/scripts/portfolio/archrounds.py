"""Durable round plans consumed by archresume and architecture.js; no dispatch here."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from archevidence import digest
from jsonartifact import read_artifact


def set_aside(path: Path) -> str:
    """Move a saved file that cannot be used out of the way, with its receipt sidecars.

    The file is renamed `<name>.unreadable-<timestamp>`, a name no reader of the working
    directory matches, so the step it belongs to runs again.

    Args:
        path: The file.

    Returns:
        The new path.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    moved = path.with_name(f"{path.name}.unreadable-{stamp}")
    path.rename(moved)
    for suffix in (".receipt", ".publish"):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.is_file():
            sidecar.rename(moved.with_name(moved.name + suffix))
    return str(moved)


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
    """Settle existing plan identities and bind post-writer review without another agent.

    A saved plan stands: an incoming plan for a round that already has one, or for a new
    round while an earlier one is unfinished, is not saved and `planKept` says so. A plan
    entry that is not a plan is dropped, a dispatch's role is the roster's, a dispatch whose
    agent the roster does not name is dropped, a review assignment keeps only the claims the
    ledger holds, and a saved result missing a list it must carry is set aside so its
    dispatch runs again. Each of these is named in `warnings`.
    """
    plans = json.loads(json.dumps(plans))
    kept = ""
    notes: list[str] = []
    legacy_round = ledger.last if not plans else 0
    decision_path = work / "decision.json"
    decision = (
        read_artifact(decision_path, strict=False) if decision_path.is_file() else {}
    )
    if not isinstance(decision, dict):
        decision = {}
    newer_results = decision_path.is_file() and any(
        Path(name).name.startswith(f"r{legacy_round}-")
        and Path(name).stat().st_mtime > decision_path.stat().st_mtime
        for name in ledger.files
    )
    resume_round = (
        legacy_round
        if legacy_round and (legacy_round > decision.get("round", 0) or newer_results)
        else None
    )
    if incoming:
        same = next((p for p in plans if p["round"] == incoming.get("round")), None)
        if same is not None and same is plans[-1] and not _done(work, same):
            # The saved plan of an unfinished round stands; its missing dispatches run.
            kept = (
                f"round {same['round']} already has a saved plan that is not complete; "
                "the saved plan is kept and the new plan was not saved"
            )
        elif same is not None:
            kept = (
                f"round {same['round']} already has a saved plan; "
                "the saved plan is kept and the new plan was not saved"
            )
        elif plans and not _done(work, plans[-1]):
            kept = (
                f"round {plans[-1]['round']} is unfinished; its saved plan is kept "
                "and the new plan was not saved"
            )
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

    gaps = []
    warnings = []
    usable = []
    for plan in plans:
        n = plan.get("round") if isinstance(plan, dict) else None
        if (
            not isinstance(n, int)
            or n < 1
            or not isinstance(plan.get("dispatches"), list)
        ):
            notes.append(f"a saved round plan that is not a plan was dropped: {n!r}")
            continue
        usable.append(plan)
        kept_dispatches = []
        for d in plan["dispatches"]:
            role = roles.get(d.get("agentType")) if isinstance(d, dict) else None
            if role is None:
                notes.append(
                    f"round {n}: dispatch {d.get('agentType') if isinstance(d, dict) else d!r} "
                    "is not on the roster and was dropped"
                )
                continue
            if d.get("role") != role:
                notes.append(
                    f"round {n}: {d['agentType']} runs as {role}, its roster role"
                )
                d["role"] = role
            kept_dispatches.append(d)
        plan["dispatches"] = kept_dispatches
    plans = usable
    for plan in plans:
        n = plan.get("round")
        dispatches = plan["dispatches"]
        writers = [d for d in dispatches if d.get("role") in ("proposer", "diagram")]
        # A plan saved before the last writer was chosen by position may carry this field.
        plan.pop("designOwner", None)
        for seq, d in enumerate(dispatches, 1):
            seq = (
                d.get("seq", seq)
                if d.get("legacySaved")
                else max([x.get("seq", 0) for x in dispatches[: seq - 1]] + [0]) + 1
            )
            d["seq"] = seq
            d.pop("designOwner", None)
            file = work / "rounds" / f"r{n}-{seq}-{d['role']}-{d['agentType']}.json"
            d["file"] = str(file)
            d["complete"] = file.is_file()
            if file.is_file():
                try:
                    result = read_artifact(file, strict=False)
                except (OSError, UnicodeDecodeError, ValueError):
                    result = None
                required = (
                    ("files", "claims", "answers") if d in writers else ("findings",)
                )
                if not d.get("legacySaved"):
                    required += ("coverage",) if d in writers else ("coverageChecks",)
                if not isinstance(result, dict) or any(
                    not isinstance(result.get(k), list) for k in required
                ):
                    notes.append(
                        f"malformed saved dispatch result set aside: {set_aside(file)}"
                    )
                    d["complete"] = False
        if all(d["complete"] for d in writers):
            for d in dispatches:
                if d in writers or "assignedClaims" in d:
                    continue
                ids, files = d.get("claimIds", []), d.get("claimFiles", [])
                known = {c["id"] for c in ledger.claims}
                unknown = [i for i in ids if i not in known]
                if unknown:
                    notes.append(
                        f"round {n}: {d.get('agentType')} was assigned unknown claim(s) "
                        f"{', '.join(unknown)}; they were dropped"
                    )
                    ids = [i for i in ids if i in known]
                    d["claimIds"] = ids
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
                if not claim["active"]:
                    continue
                for d in reviewers:
                    if not any(v["by"] == d["agentType"] for v in claim["verdicts"]):
                        gaps.append(
                            f"claim {cid} lacks assigned review by {d['agentType']}"
                        )
        for d in dispatches:
            if d in writers:
                continue
            selected = {c["id"] for c in d.get("assignedClaims", [])}
            scope = set(d.get("coverageIds") or [])
            rows = [
                row for row in coverage or [] if not scope or row.get("id") in scope
            ]
            d["reviewInputRevision"] = digest(
                {
                    "task": d.get("task", ""),
                    "selectionReason": d.get("selectionReason", ""),
                    "claims": [
                        {"id": c["id"], "revision": c["revision"]}
                        for c in ledger.claims
                        if c["id"] in selected
                    ],
                    "coverage": [
                        {"id": row["id"], "revision": row["revision"]} for row in rows
                    ],
                    "repairs": d.get("repairIds", []),
                    "findings": [
                        finding
                        for finding in ledger.findings
                        if d.get("repairIds") or finding.get("claimId") in selected
                    ],
                }
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
        "warnings": notes,
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
                "coverageIds": list(d.get("coverageIds") or []),
                "claimIds": list(d.get("claimIds") or []),
                "claimFiles": list(d.get("claimFiles") or []),
                "reviewInputRevision": d.get("reviewInputRevision", ""),
                "files": list(d.get("files") or []),
                "answers": list(d.get("answers") or []),
                "assignedClaimCount": len(d.get("assignedClaims") or []),
            }
            for d in plan["dispatches"]
        ],
    }
