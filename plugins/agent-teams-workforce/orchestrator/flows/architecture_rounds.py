"""Bounded author, review and decision rounds, resumed by absolute round identity."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..core.io import write_json
from .architecture_support import ROLES, Architecture, read, value_input
from .architecture_survey import adopt_result, produce_survey

OWNER_KINDS = {"business-conflict", "architecture-conflict"}


def owner_actions(decision: dict, path: Path) -> list[str]:
    concerns = decision.get("ownerConcerns", [])
    if (
        decision.get("verdict") != "owner-concern"
        or not concerns
        or any(c["kind"] not in OWNER_KINDS for c in concerns)
    ):
        return []
    return [
        f"{c['kind']}: {c['concern']} Evidence: {c['evidence']}" for c in concerns
    ] + [f"After the PRD or section 2 records the resolution, delete {path}."]


def settle_plan(flow: Architecture, plan: dict, number: int, facts: dict) -> dict:
    findings = {f["id"]: f for f in facts["rounds"]["openFindings"]}
    dispatches: dict[str, dict] = {}
    assignments = {}
    for entry in plan.get("dispatches", []):
        name = entry.get("agentType", "").removeprefix("agent-teams-workforce:")
        if name not in ROLES:
            continue
        role = ROLES[name]
        files = entry.get("files", [])
        if role in {"proposer", "diagram"} and any(
            Path(f).is_absolute()
            or ".." in Path(f).parts
            or "02-architecture-constraints" in Path(f).parts
            for f in files
        ):
            continue
        answers = []
        for fid in entry.get("answers", []):
            finding = findings.get(fid)
            if finding and finding.get("owner") in {None, "", name}:
                answers.append(fid)
                if not finding.get("owner"):
                    assignments[fid] = name
        normalized = {**entry, "agentType": name, "role": role, "answers": answers}
        if name in dispatches:
            existing = dispatches[name]
            for field in (
                "files",
                "answers",
                "coverageIds",
                "claimIds",
                "claimFiles",
                "repairIds",
            ):
                existing[field] = list(
                    dict.fromkeys(existing.get(field, []) + normalized.get(field, []))
                )
            existing["task"] = (
                existing.get("task", "") + "; " + normalized.get("task", "")
            )
        else:
            dispatches[name] = normalized
    baseline = facts["baseline"]
    scope = (
        set(baseline["designWork"])
        | set(baseline["docWork"])
        | set(baseline["unknowns"])
    )
    authored = {
        cid
        for prior in read(flow.work / "ledger.json").get("roundPlans", [])
        for item in prior.get("dispatches", [])
        if item.get("role") in {"proposer", "diagram"} and item.get("complete")
        for cid in item.get("coverageIds", [])
    }
    missing = scope - authored
    if missing and not any(
        d["role"] in {"proposer", "diagram"} for d in dispatches.values()
    ):
        for capability in sorted(missing):
            kind = baseline["kindOf"].get(capability)
            name = {
                "infrastructure": "cdk-infrastructure-designer",
                "documentation": "architecture-diagram-author",
            }.get(kind, "integration-pattern-architect")
            entry = dispatches.setdefault(
                name,
                {
                    "agentType": name,
                    "role": ROLES[name],
                    "task": "Author the scoped capability views.",
                    "selectionReason": "Unwritten design scope",
                    "files": [],
                    "answers": [],
                    "coverageIds": [],
                    "repairIds": [],
                },
            )
            entry["coverageIds"].append(capability)
    ordered = sorted(
        dispatches.values(), key=lambda row: row["role"] not in {"proposer", "diagram"}
    )
    # One clarified resend for an unanswered owned finding; the ledger persists the count.
    previous = read(flow.work / "ledger.json").get("roundPlans", [])
    for entry in ordered:
        for fid, finding in findings.items():
            attempts = sum(
                fid in d.get("answers", [])
                for p in previous
                for d in p.get("dispatches", [])
                if d.get("agentType") == entry["agentType"]
            )
            if (
                finding.get("owner") == entry["agentType"]
                and not finding["answered"]
                and attempts == 1
                and fid not in entry["answers"]
            ):
                entry["answers"].append(fid)
    if assignments:
        flow.facts(
            assign=",".join(f"{key}={value}" for key, value in assignments.items())
        )
    return {
        "round": number,
        "readyForDecision": bool(plan.get("readyForDecision")),
        "reason": plan.get("reason", ""),
        "dispatches": [
            {**entry, "seq": index} for index, entry in enumerate(ordered, 1)
        ],
        "overlaps": plan.get("overlaps", []),
    }


def execute_plan(flow: Architecture, plan: dict) -> None:
    number = plan["round"]
    path = flow.work / "plans" / f"round{number}-plan-0.json"
    writers = [d for d in plan["dispatches"] if d["role"] in {"proposer", "diagram"}]

    def dispatch(entry: dict) -> None:
        role, name, seq = entry["role"], entry["agentType"], entry["seq"]
        final = flow.work / "rounds" / f"r{number}-{seq}-{role}-{name}.json"
        canonical = next(
            (
                d
                for d in read(path).get("dispatches", [])
                if d.get("seq") == seq and d.get("agentType") == name
            ),
            entry,
        )
        identity = {
            key: value
            for key, value in canonical.items()
            if key
            not in {
                "complete",
                "file",
                "result",
                "reviewInputRevision",
                "assignedClaims",
                "assignedClaimCount",
            }
        }
        inputs = flow.base_inputs() + (str(path), value_input("plan-entry", identity))
        writer = role in {"proposer", "diagram"}
        if not writer:
            inputs += (str(flow.draft),)
        ledger = flow.ledger_input(f"r{number}-{seq}")
        inputs += (str(ledger),)
        if writer:
            adopt_result(flow, final, inputs, name)
        # Plan order communicates reconciliation through the shared contract skill.
        outcome = (
            "Write and reconcile the round's architecture views."
            if writer and entry == writers[-1]
            else "Write the assigned architecture views."
            if writer
            else "Review the round's architecture views."
        )
        flow.agent(
            name,
            final,
            "architecture-writer" if writer else "architecture-review",
            inputs,
            outcome,
        )

    for entry in writers:
        dispatch(entry)
        flow.facts()
    flow.target(seed=True)
    flow.target(dry_run=True)
    reviewers = [d for d in plan["dispatches"] if d not in writers]
    # Freeze the ledger inputs before threads start; shared ledger folding is sequential.
    for entry in reviewers:
        flow.ledger_input(
            f"r{number}-{entry['seq']}",
            refresh=any(p.name.startswith(f"r{number}-") for p in flow.ran),
        )
    with ThreadPoolExecutor(
        max_workers=max(1, int(os.environ.get("ATW_ORCH_SESSIONS", "4")))
    ) as pool:
        list(pool.map(dispatch, reviewers))
    flow.facts()


def decide(flow: Architecture, number: int) -> dict:
    flow.target(seed=True)
    path = flow.work / "decision.json"
    ledger = flow.ledger_input(
        f"decision-{number}",
        refresh=any(p.name.startswith(f"r{number}-") for p in flow.ran),
    )
    inputs = flow.base_inputs() + (
        str(flow.draft),
        str(ledger),
        value_input("round", number),
    )
    result = flow.agent(
        "architecture-decider",
        path,
        "decision",
        inputs,
        "Decide the architecture round.",
    )
    actionable = result.get("returnTo") or flow.facts().get("repairs", {}).get("open")
    if result["verdict"] == "return" and not actionable:
        error = flow.work / f"decision-{number}.errors.json"
        write_json(
            error,
            {
                "round": number,
                "errors": ["The return names no agent or unresolved repair."],
            },
        )
        result = flow.agent(
            "architecture-decider",
            path,
            "decision",
            inputs + (str(error),),
            "Resolve the non-actionable architecture return.",
        )
        if (
            result["verdict"] == "return"
            and not result.get("returnTo")
            and not flow.facts().get("repairs", {}).get("open")
        ):
            raise flow.tools.failure("decide", "other", result)
    if result["round"] != number:
        raise flow.tools.failure(
            "decide", "other", {"expectedRound": number, "decision": result}
        )
    companion = flow.work / "decision.md"
    companion.write_text(
        f"# Architecture decision\n\n{result['verdict']}\n\n{result['summary']}\n",
        encoding="utf-8",
    )
    flow.store.accept("architecture:decision", inputs, (companion,), producer="python")
    return result


def run_rounds(flow: Architecture) -> dict:
    facts = flow.facts()
    decision = read(flow.work / "decision.json")
    if (
        decision.get("round", 0) >= 3
        and decision.get("verdict") != "approve"
        and not owner_actions(decision, flow.work / "decision.json")
    ):
        raise flow.tools.failure(
            "rounds", "other", {"decision": decision, "roundLimit": 3}
        )
    baseline = facts["baseline"]
    check_only = not (
        baseline["designWork"] or baseline["docWork"] or baseline["unknowns"]
    )
    plans = read(flow.work / "ledger.json").get("roundPlans", [])
    last = max([facts["rounds"]["last"], *[p["round"] for p in plans]], default=0)
    if decision.get("round", 0) >= last and not facts["rounds"].get("pendingPlan"):
        if owner_actions(decision, flow.work / "decision.json"):
            return decision
        if decision.get("verdict") == "approve":
            ledger = flow.work / "inputs" / f"decision-{decision['round']}.ledger.json"
            inputs = flow.base_inputs() + (
                str(flow.draft),
                str(ledger),
                value_input("round", decision["round"]),
            )
            if flow.store.reusable(
                inputs + (str(flow.context_path),), (flow.work / "decision.json",)
            ):
                return decision
    pending = facts["rounds"].get("pendingRound") or facts["rounds"].get("resumeRound")
    start = (
        pending
        or (last if decision.get("verdict") == "approve" and last else 0)
        or max(1, last if decision.get("round", 0) < last else last + 1)
    )
    for number in range(start, 4):
        saved = next((p for p in plans if p["round"] == number), None)
        if saved:
            plan = saved
            saved_path = flow.work / "plans" / f"round{number}-plan-0.json"
            saved_inputs = flow.base_inputs() + (
                str(flow.ledger_input(f"plan-{number}")),
                value_input("round", number),
            )
            adopt_result(
                flow,
                saved_path,
                saved_inputs,
                "architecture-decision-workflow-coordinator",
            )
        elif check_only and number == 1:
            plan = {
                "round": 1,
                "readyForDecision": True,
                "dispatches": [
                    {
                        "seq": 1,
                        "agentType": "architecture-boundary-guardian",
                        "role": "reviewer",
                        "task": "Check effective architecture coverage.",
                        "files": [],
                        "answers": [],
                    }
                ],
                "overlaps": [],
            }
        else:
            ledger = flow.ledger_input(f"plan-{number}")
            path = flow.work / "plans" / f"round{number}-plan-0.json"
            inputs = flow.base_inputs() + (str(ledger), value_input("round", number))
            adopt_result(
                flow, path, inputs, "architecture-decision-workflow-coordinator"
            )
            raw = flow.agent(
                "architecture-decision-workflow-coordinator",
                path,
                "coordinator-plan",
                inputs,
                "Plan the architecture round.",
            )
            plan = settle_plan(flow, raw, number, flow.facts())
        path = flow.work / "plans" / f"round{number}-plan-0.json"
        if not saved:
            write_json(path, plan)
            plan_inputs = flow.base_inputs() + (
                str(flow.ledger_input(f"plan-{number}")),
                value_input("round", number),
            )
            flow.store.accept(
                f"architecture:plan-{number}", plan_inputs, (path,), producer="python"
            )
        flow.facts(plan=json.dumps(plan))
        execute_plan(flow, plan)
        facts = flow.facts()
        if check_only and number == 1 and facts["rounds"]["openFindings"]:
            produce_survey(flow, recheck=True)
            facts = flow.facts()
            check_only = not (
                facts["baseline"]["designWork"]
                or facts["baseline"]["docWork"]
                or facts["baseline"]["unknowns"]
            )
            if not check_only:
                plans = read(flow.work / "ledger.json").get("roundPlans", [])
                continue
        if not plan.get("readyForDecision") and number < 3:
            plans = read(flow.work / "ledger.json").get("roundPlans", [])
            continue
        decision = decide(flow, number)
        if decision["verdict"] == "approve" or owner_actions(
            decision, flow.work / "decision.json"
        ):
            if number > 1:
                flow.runner.emit(
                    "note",
                    kind="rounds-warning",
                    phase="architecture",
                    rounds=number,
                    drivers=facts["rounds"]["openFindings"],
                )
            return decision
        plans = read(flow.work / "ledger.json").get("roundPlans", [])
    raise flow.tools.failure("rounds", "other", {"decision": decision, "roundLimit": 3})
