"""Bounded author, review and decision rounds, resumed by absolute round identity."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.flows.architecture_support import ROLES, Architecture, ArchitectureStep, read, value_input
from orchestrator.flows.architecture_survey import adopt_result, produce_survey

ROUND_LIMIT = 3

OWNER_KINDS = {"business-conflict", "architecture-conflict"}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def owner_actions(decision: dict[str, JsonValue], path: Path) -> list[str]:
    """Owner actions.

    Returns:
        The validated round outcome.

    """
    concerns = _objects(decision.get("ownerConcerns", []))
    if (
        decision.get("verdict") != "owner-concern"
        or not concerns
        or any(c["kind"] not in OWNER_KINDS for c in concerns)
    ):
        return []
    return [f"{c['kind']}: {c['concern']} Evidence: {c['evidence']}" for c in concerns] + [
        f"After the PRD or section 2 records the resolution, delete {path}.",
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def settle_plan(
    flow: Architecture,
    plan: dict[str, JsonValue],
    number: int,
    facts: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Settle plan.

    Returns:
        The validated round outcome.

    """
    findings = {check_type(f["id"], str): f for f in _objects(json_object(facts["rounds"])["openFindings"])}
    dispatches, assignments = _normalize_dispatches(plan, findings)
    _ensure_authors(flow, facts, dispatches)
    ordered = sorted(
        dispatches.values(),
        key=lambda row: row["role"] not in {"proposer", "diagram"},
    )
    # One clarified resend for an unanswered owned finding; the ledger persists the count.
    previous = _objects(read(flow.work / "ledger.json").get("roundPlans", []))
    for entry in ordered:
        for fid, finding in findings.items():
            attempts = sum(
                fid in _strings(d.get("answers", []))
                for p in previous
                for d in _objects(p.get("dispatches", []))
                if d.get("agentType") == entry["agentType"]
            )
            if (
                finding.get("owner") == entry["agentType"]
                and not finding["answered"]
                and attempts == 1
                and fid not in _strings(entry["answers"])
            ):
                check_type(
                    entry["answers"],
                    list[JsonValue],
                    collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
                ).append(fid)
    if assignments:
        flow.facts(
            assign=",".join(f"{key}={value}" for key, value in assignments.items()),
        )
    return json_object({
        "round": number,
        "readyForDecision": bool(plan.get("readyForDecision")),
        "reason": plan.get("reason", ""),
        "dispatches": [{**entry, "seq": index} for index, entry in enumerate(ordered, 1)],
        "overlaps": plan.get("overlaps", []),
    })


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def execute_plan(flow: Architecture, plan: dict[str, JsonValue]) -> None:
    """Execute the normalized writer and reviewer dispatches."""
    number = plan["round"]
    path = flow.work / "plans" / f"round{number}-plan-0.json"
    writers = [d for d in _objects(plan["dispatches"]) if d["role"] in {"proposer", "diagram"}]

    def dispatch(entry: dict[str, JsonValue]) -> None:
        role, name, seq = entry["role"], entry["agentType"], entry["seq"]
        final = flow.work / "rounds" / f"r{number}-{seq}-{role}-{name}.json"
        canonical = next(
            (
                d
                for d in _objects(read(path).get("dispatches", []))
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
        inputs = (*flow.base_inputs(), str(path), value_input("plan-entry", identity))
        writer = role in {"proposer", "diagram"}
        if not writer:
            inputs += (str(flow.draft),)
        ledger = flow.ledger_input(f"r{number}-{seq}")
        inputs += (str(ledger),)
        if writer:
            adopt_result(flow, final, inputs, check_type(name, str))
        # Plan order communicates reconciliation through the shared contract skill.
        outcome = (
            "Write and reconcile the round's architecture views."
            if writer and entry == writers[-1]
            else "Write the assigned architecture views."
            if writer
            else "Review the round's architecture views."
        )
        flow.agent(
            ArchitectureStep(
                check_type(name, str),
                final,
                "architecture-writer" if writer else "architecture-review",
                inputs,
                outcome,
            ),
        )

    for entry in writers:
        dispatch(entry)
        flow.facts()
    flow.target(seed=True)
    flow.target(dry_run=True)
    reviewers = [d for d in _objects(plan["dispatches"]) if d not in writers]
    # Freeze the ledger inputs before threads start; shared ledger folding is sequential.
    for entry in reviewers:
        flow.ledger_input(
            f"r{number}-{entry['seq']}",
            refresh=any(p.name.startswith(f"r{number}-") for p in flow.ran),
        )
    with ThreadPoolExecutor(
        max_workers=max(1, int(os.environ.get("ATW_ORCH_SESSIONS", "4"))),
    ) as pool:
        list(pool.map(dispatch, reviewers))
    flow.facts()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def decide(flow: Architecture, number: int) -> dict[str, JsonValue]:
    """Decide.

    Returns:
        The validated round outcome.

    """
    stage = "decide"
    flow.target(seed=True)
    path = flow.work / "decision.json"
    ledger = flow.ledger_input(
        f"decision-{number}",
        refresh=any(p.name.startswith(f"r{number}-") for p in flow.ran),
    )
    inputs = (
        *flow.base_inputs(),
        str(flow.draft),
        str(ledger),
        value_input("round", number),
    )
    result = flow.agent(
        ArchitectureStep(
            "architecture-decider",
            path,
            "decision",
            inputs,
            "Decide the architecture round.",
        ),
    )
    actionable = result.get("returnTo") or json_object(flow.facts().get("repairs", {})).get("open")
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
            ArchitectureStep(
                "architecture-decider",
                path,
                "decision",
                (*inputs, str(error)),
                "Resolve the non-actionable architecture return.",
            ),
        )
        if (
            result["verdict"] == "return"
            and not result.get("returnTo")
            and not json_object(flow.facts().get("repairs", {})).get("open")
        ):
            raise flow.tools.failure(stage, "other", result)
    if result["round"] != number:
        raise flow.tools.failure(
            stage,
            "other",
            {"expectedRound": number, "decision": result},
        )
    companion = flow.work / "decision.md"
    companion.write_text(
        f"# Architecture decision\n\n{result['verdict']}\n\n{result['summary']}\n",
        encoding="utf-8",
    )
    flow.store.accept("architecture:decision", inputs, (companion,), producer="python")
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def run_rounds(flow: Architecture) -> dict[str, JsonValue]:
    """Run rounds.

    Returns:
        The validated round outcome.

    """
    stage = "rounds"
    facts = flow.facts()
    decision = read(flow.work / "decision.json")
    if (
        check_type(decision.get("round", 0), int) >= ROUND_LIMIT
        and decision.get("verdict") != "approve"
        and not owner_actions(decision, flow.work / "decision.json")
    ):
        raise flow.tools.failure(
            stage,
            "other",
            {"decision": decision, "roundLimit": ROUND_LIMIT},
        )
    baseline = json_object(facts["baseline"])
    check_only = not (baseline["designWork"] or baseline["docWork"] or baseline["unknowns"])
    plans = _objects(read(flow.work / "ledger.json").get("roundPlans", []))
    last = max(
        [check_type(json_object(facts["rounds"])["last"], int), *[check_type(p["round"], int) for p in plans]],
        default=0,
    )
    if _decision_current(flow, decision, facts, last):
        return decision
    pending = json_object(facts["rounds"]).get("pendingRound") or json_object(facts["rounds"]).get("resumeRound")
    start = (
        pending
        or (last if decision.get("verdict") == "approve" and last else 0)
        or max(1, last if check_type(decision.get("round", 0), int) < last else last + 1)
    )
    for number in range(check_type(start, int), ROUND_LIMIT + 1):
        plan = _round_plan(flow, number, plans, check_only=check_only)
        flow.facts(plan=json.dumps(plan))
        execute_plan(flow, plan)
        facts = flow.facts()
        if check_only and number == 1 and _objects(json_object(facts["rounds"])["openFindings"]):
            produce_survey(flow, recheck=True)
            facts = flow.facts()
            check_only = not (
                json_object(facts["baseline"])["designWork"]
                or json_object(facts["baseline"])["docWork"]
                or json_object(facts["baseline"])["unknowns"]
            )
            if not check_only:
                plans = _objects(read(flow.work / "ledger.json").get("roundPlans", []))
                continue
        if not plan.get("readyForDecision") and number < ROUND_LIMIT:
            plans = _objects(read(flow.work / "ledger.json").get("roundPlans", []))
            continue
        decision = decide(flow, number)
        if decision["verdict"] == "approve" or owner_actions(
            decision,
            flow.work / "decision.json",
        ):
            if number > 1:
                flow.runner.emit(
                    "note",
                    kind="rounds-warning",
                    phase="architecture",
                    rounds=number,
                    drivers=_objects(json_object(facts["rounds"])["openFindings"]),
                )
            return decision
        plans = _objects(read(flow.work / "ledger.json").get("roundPlans", []))
    raise flow.tools.failure(stage, "other", {"decision": decision, "roundLimit": ROUND_LIMIT})


def _objects(value: object) -> list[dict[str, JsonValue]]:
    return check_type(value, list[dict[str, JsonValue]], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _strings(value: object) -> list[str]:
    return check_type(value, list[str], collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)


def _normalize_dispatches(
    plan: dict[str, JsonValue],
    findings: dict[str, dict[str, JsonValue]],
) -> tuple[dict[str, dict[str, JsonValue]], dict[str, str]]:
    dispatches: dict[str, dict[str, JsonValue]] = {}
    assignments = {}
    for entry in _objects(plan.get("dispatches", [])):
        name = check_type(entry.get("agentType", ""), str).removeprefix("agent-teams-workforce:")
        if name not in ROLES:
            continue
        role = ROLES[name]
        files = _strings(entry.get("files", []))
        if role in {"proposer", "diagram"} and any(
            Path(f).is_absolute() or ".." in Path(f).parts or "02-architecture-constraints" in Path(f).parts
            for f in files
        ):
            continue
        answers = []
        for fid in _strings(entry.get("answers", [])):
            finding = findings.get(fid)
            if finding and finding.get("owner") in {None, "", name}:
                answers.append(fid)
                if not finding.get("owner"):
                    assignments[fid] = name
        normalized = json_object({**entry, "agentType": name, "role": role, "answers": answers})
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
                existing[field] = list[JsonValue](
                    dict.fromkeys(_strings(existing.get(field, [])) + _strings(normalized.get(field, []))),
                )
            existing["task"] = (
                check_type(existing.get("task", ""), str) + "; " + check_type(normalized.get("task", ""), str)
            )
        else:
            dispatches[name] = normalized
    return dispatches, assignments


def _ensure_authors(
    flow: Architecture,
    facts: dict[str, JsonValue],
    dispatches: dict[str, dict[str, JsonValue]],
) -> None:
    baseline = json_object(facts["baseline"])
    scope = (
        set(_strings(baseline["designWork"])) | set(_strings(baseline["docWork"])) | set(_strings(baseline["unknowns"]))
    )
    authored = {
        cid
        for prior in _objects(read(flow.work / "ledger.json").get("roundPlans", []))
        for item in _objects(prior.get("dispatches", []))
        if item.get("role") in {"proposer", "diagram"} and item.get("complete")
        for cid in _strings(item.get("coverageIds", []))
    }
    missing = scope - authored
    if missing and not any(d["role"] in {"proposer", "diagram"} for d in dispatches.values()):
        for capability in sorted(missing):
            kind = json_object(baseline["kindOf"]).get(capability)
            name = {
                "infrastructure": "cdk-infrastructure-designer",
                "documentation": "architecture-diagram-author",
            }.get(check_type(kind, str | None), "integration-pattern-architect")
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
            check_type(
                entry["coverageIds"],
                list[JsonValue],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ).append(capability)


def _round_plan(
    flow: Architecture,
    number: int,
    plans: list[dict[str, JsonValue]],
    *,
    check_only: bool,
) -> dict[str, JsonValue]:
    saved = next((p for p in plans if p["round"] == number), None)
    if saved:
        plan = saved
        saved_path = flow.work / "plans" / f"round{number}-plan-0.json"
        saved_inputs = (
            *flow.base_inputs(),
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
                },
            ],
            "overlaps": [],
        }
    else:
        ledger = flow.ledger_input(f"plan-{number}")
        path = flow.work / "plans" / f"round{number}-plan-0.json"
        inputs = (*flow.base_inputs(), str(ledger), value_input("round", number))
        adopt_result(
            flow,
            path,
            inputs,
            "architecture-decision-workflow-coordinator",
        )
        raw = flow.agent(
            ArchitectureStep(
                "architecture-decision-workflow-coordinator",
                path,
                "coordinator-plan",
                inputs,
                "Plan the architecture round.",
            ),
        )
        plan = settle_plan(flow, raw, number, flow.facts())
    path = flow.work / "plans" / f"round{number}-plan-0.json"
    if not saved:
        write_json(path, plan)
        plan_inputs = (
            *flow.base_inputs(),
            str(flow.ledger_input(f"plan-{number}")),
            value_input("round", number),
        )
        flow.store.accept(
            f"architecture:plan-{number}",
            plan_inputs,
            (path,),
            producer="python",
        )
    return plan


def _decision_current(
    flow: Architecture,
    decision: dict[str, JsonValue],
    facts: dict[str, JsonValue],
    last: int,
) -> bool:
    if check_type(decision.get("round", 0), int) >= last and not json_object(facts["rounds"]).get("pendingPlan"):
        if owner_actions(decision, flow.work / "decision.json"):
            return True
        if decision.get("verdict") == "approve":
            ledger = flow.work / "inputs" / f"decision-{decision['round']}.ledger.json"
            inputs = (
                *flow.base_inputs(),
                str(flow.draft),
                str(ledger),
                value_input("round", decision["round"]),
            )
            if flow.store.reusable(
                (*inputs, str(flow.context_path)),
                (flow.work / "decision.json",),
            ):
                return True
    return False
