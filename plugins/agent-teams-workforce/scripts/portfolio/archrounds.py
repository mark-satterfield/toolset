"""Durable round plans consumed by archresume and architecture.js; no dispatch here."""

from __future__ import annotations

import json
import os
from pathlib import Path


def save_ledger(path: Path, payload: dict) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    temporary.replace(path)


def round_facts(
    work: Path,
    plans: list,
    incoming: dict | None,
    ledger: object,
    roles: dict,
    team: dict,
) -> dict:
    """Settle existing plan identities and bind post-writer review without another agent."""
    plans = json.loads(json.dumps(plans))
    if incoming:
        if any(p["round"] == incoming.get("round") for p in plans):
            raise ValueError("cannot replace a durable round plan")
        if plans and not plans[-1].get("complete"):
            raise ValueError("finish pending round before selecting another")
        plans.append(incoming)
    gaps = []
    for plan in plans:
        n = plan.get("round")
        dispatches = plan.get("dispatches")
        if not isinstance(n, int) or n < 1 or not isinstance(dispatches, list):
            raise ValueError("invalid durable round plan")
        writers = [d for d in dispatches if d.get("role") in ("proposer", "diagram")]
        proposers = [d["agentType"] for d in writers if d["role"] == "proposer"]
        if (
            len(proposers) > 2
            or len(set(proposers)) != len(proposers)
            or any(w not in (team.get("lead"), team.get("second")) for w in proposers)
        ):
            raise ValueError("durable plan exceeds retained proposal budget")
        for seq, d in enumerate(dispatches, 1):
            if roles.get(d.get("agentType")) != d.get("role"):
                raise ValueError("durable plan names invalid role")
            d["seq"] = seq
            file = work / "rounds" / f"r{n}-{seq}-{d['role']}-{d['agentType']}.json"
            d["file"] = str(file)
            d["complete"] = file.is_file()
            if file.is_file():
                result = json.loads(file.read_text())
                required = (
                    ("files", "claims", "answers", "coverage")
                    if d in writers
                    else ("findings", "coverageChecks")
                )
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
                if len(reviewers) > 1 and any(
                    not d.get("overlapReason", "").strip() for d in reviewers
                ):
                    raise ValueError(
                        f"overlapping review of {cid} requires explicit reason"
                    )
                claim = next(c for c in ledger.claims if c["id"] == cid)
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
    return {"plans": plans, "last": last, "pendingPlan": pending, "reviewGaps": gaps}
