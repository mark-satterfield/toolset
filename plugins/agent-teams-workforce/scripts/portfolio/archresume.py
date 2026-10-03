"""Read the architecture step's saved work on disk and report only what its control flow needs.

`depscore.py arch-resume` runs `resume_facts`. The architecture step saves every session's
result under the Epic's working directory: `survey.json`, `rounds/r<n>-<seq>-<role>-<agent>.json`,
`decision.json`, `architecture-update.json`, `integrate-before.json` and `conformance-<n>.json`.
This command reads them, folds the round results into the claim and finding ledger, writes the
whole ledger to `ledger.json` in that directory for the sessions that need it, and prints the
compact facts the workflow branches on: which steps finished, the last round, the open
findings by id, the number of unreviewed claims of each writer, the decision's verdict, and the integration's file lists.
No saved content travels back to the workflow: sessions read the files by path.

A saved file that cannot be read or parsed is an error naming the file, never an empty result,
so a resumed step stops instead of starting the work again.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from archcoverage import coverage_facts, integration_revision
from archevidence import digest, evidence_state, view_bindings, view_content
from archrounds import compact_plan, round_facts, save_ledger

ROUND_FILE = re.compile(
    r"^r(\d+)-(\d+)-(proposer|diagram|reviewer|cost)-([a-z0-9-]+)\.json$"
)
REVIEW_FILE = re.compile(r"^conformance-(\d+)\.json$")
WRITER_ROLES = ("proposer", "diagram")
OWNER_CONCERN_KINDS = ("business-conflict", "architecture-conflict")
AGENT_PREFIX = "agent-teams-workforce:"
LEDGER_NAME = "ledger.json"


class ResumeError(Exception):
    """A saved file of the architecture step cannot be read or parsed."""


def _text(value: object) -> str:
    """Return a value as stripped text, or empty when it is not a string.

    Args:
        value: Any JSON value.

    Returns:
        The stripped string, or "".
    """
    return value.strip() if isinstance(value, str) else ""


def _load(path: Path) -> object:
    """Parse one saved JSON file.

    Args:
        path: The file.

    Returns:
        The parsed value.

    Raises:
        ResumeError: The file cannot be read or is not JSON.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResumeError(f"{path}: {exc}") from exc


def _paths(value: object) -> list[str]:
    """Return the non-empty strings of a list value.

    Args:
        value: Any JSON value.

    Returns:
        The stripped strings, in order.
    """
    return [_text(x) for x in value if _text(x)] if isinstance(value, list) else []


def parse_roster(spec: str) -> dict[str, str]:
    """Parse `role=a,b;role=c` into each agent's role.

    Args:
        spec: The roster as the workflow passes it.

    Returns:
        The role of each agent named.
    """
    roles: dict[str, str] = {}
    for part in spec.split(";"):
        role, _, names = part.partition("=")
        for name in names.split(","):
            if name.strip() and role.strip():
                roles[name.strip()] = role.strip()
    return roles


def parse_assign(spec: str) -> dict[str, str]:
    """Parse `F1.2.3=agent,F2.1.1=agent` into each finding's assigned owner.

    Args:
        spec: The assignments as the workflow passes them.

    Returns:
        The owner the coordinator assigned to each finding id.
    """
    out: dict[str, str] = {}
    for part in spec.split(","):
        fid, _, owner = part.partition("=")
        if fid.strip() and owner.strip():
            out[fid.strip()] = owner.strip()
    return out


class Ledger:
    """The claims and findings of the rounds, folded in round order."""

    def __init__(self, assign: dict[str, str], lead: str = "") -> None:
        """Start an empty ledger.

        Args:
            assign: Owners the coordinator assigned to findings that had none.
        """
        self.assign = assign
        self.lead = lead
        self.claims: list[dict] = []
        self.findings: list[dict] = []
        self.writers: list[str] = []
        self.reviewers: list[str] = []
        self.proposer_claims: dict[str, int] = {}
        self.files: list[str] = []
        self.saved: list[str] = []
        self.last = 0
        self.resolutions = []

    def absorb(
        self, n: int, seq: int, role: str, agent: str, result: object, file: str
    ) -> None:
        """Fold one round result into the ledger.

        Args:
            n: The round.
            seq: The dispatch's place in the round.
            role: proposer, diagram, reviewer or cost.
            agent: The agent that wrote the result.
            result: The parsed result.
            file: The result file.

        Raises:
            ResumeError: The result is not a JSON object.
        """
        if not isinstance(result, dict):
            raise ResumeError(f"{file}: not a JSON object")
        self.files.append(file)
        self.saved.append(f"r{n}-{seq}")
        self.last = max(self.last, n)
        if role in WRITER_ROLES:
            self._absorb_writer(n, seq, role, agent, result)
            return
        if agent not in self.reviewers:
            self.reviewers.append(agent)
        self.resolutions.extend(
            {**r, "by": agent, "round": n}
            for r in result.get("resolutions", [])
            if isinstance(r, dict)
        )
        raw = result.get("findings")
        for k, x in enumerate(raw if isinstance(raw, list) else []):
            if not isinstance(x, dict) or not _text(x.get("verdict")):
                continue
            claim_id = _text(x.get("claimId"))
            claim = (
                next((c for c in self.claims if c["id"] == claim_id), None)
                if claim_id
                else None
            )
            revision = _text(x.get("claimRevision"))
            if (
                claim
                and agent != claim["by"]
                and _text(x.get("evidence"))
                and (revision == claim["revision"])
            ):
                claim["verdicts"].append(
                    {
                        "by": agent,
                        "verdict": _text(x.get("verdict")),
                        "revision": claim["revision"],
                        "evidence": x.get("evidence") or "",
                    }
                )
            named = _text(x.get("owner"))
            owner = claim["by"] if claim else named if named in self.writers else ""
            fid = f"F{n}.{seq}.{k + 1}"
            self.findings.append(
                {
                    "id": fid,
                    "round": n,
                    "by": agent,
                    "claimId": claim["id"] if claim else "",
                    "claimRevision": revision or (claim["revision"] if claim else ""),
                    "claim": x.get("claim") or "",
                    "file": x.get("file") or "",
                    "verdict": _text(x.get("verdict")),
                    "evidence": x.get("evidence") or "",
                    "owner": self.assign.get(fid) or owner,
                    "answer": None,
                }
            )

    def _absorb_writer(
        self, n: int, seq: int, role: str, agent: str, result: dict
    ) -> None:
        """Fold a writer's claims and answers into the ledger.

        Args:
            n: The round.
            seq: The dispatch's place in the round.
            role: proposer or diagram.
            agent: The writer.
            result: The parsed result.
        """
        if agent not in self.writers:
            self.writers.append(agent)
        raw = result.get("claims")
        stated = 0
        for k, c in enumerate(raw if isinstance(raw, list) else []):
            if isinstance(c, dict) and _text(c.get("claim")):
                stated += 1
                cid = _text(c.get("claimId")) or f"C{n}.{seq}.{k + 1}"
                old = next((x for x in self.claims if x["id"] == cid), None)
                if c.get("claimId") and not old:
                    raise ResumeError(f"unknown revised claim {cid}")
                if old and old["by"] != agent and agent != self.lead:
                    raise ResumeError(
                        f"claim {cid} belongs to {old['by']}; do not silently transfer ownership"
                    )
                refs = c.get("evidenceRefs", [])
                evidence, errors = evidence_state(refs)
                file = c.get("file") or ""
                view = (
                    str(Path(self.files[-1]).parent.parent / "draft" / file)
                    if file
                    else ""
                )
                views = [view] if view else []
                state = view_bindings(views, refs)
                revision = digest(
                    {
                        "claim": c.get("claim"),
                        "citation": c.get("citation"),
                        "evidence": evidence,
                        "views": state,
                    }
                )
                fresh = {
                    "id": cid,
                    "round": n,
                    "by": agent,
                    "claim": c.get("claim"),
                    "file": file,
                    "citation": c.get("citation") or "",
                    "evidenceRefs": refs,
                    "evidenceState": evidence,
                    "evidenceErrors": errors,
                    "views": views,
                    "viewState": state,
                    "revision": revision,
                    "active": True,
                    "legacy": "claimId" not in c,
                    "verdicts": [],
                    "history": [],
                }
                if old:
                    fresh["history"] = old["history"] + [
                        {k: v for k, v in old.items() if k != "history"}
                    ]
                    if old["revision"] == revision:
                        fresh["verdicts"] = old["verdicts"]
                    self.claims[self.claims.index(old)] = fresh
                else:
                    self.claims.append(fresh)
                for superseded in c.get("supersedes", []):
                    target = next(
                        (x for x in self.claims if x["id"] == superseded), None
                    )
                    if (
                        not target
                        or (target["by"] != agent and agent != self.lead)
                        or target["id"] == cid
                    ):
                        raise ResumeError(f"invalid superseded claim {superseded}")
                    target["active"] = False
                    target["supersededBy"] = cid

        if role == "proposer":
            self.proposer_claims[agent] = self.proposer_claims.get(agent, 0) + stated
        answers = result.get("answers")
        for ans in answers if isinstance(answers, list) else []:
            if not isinstance(ans, dict):
                continue
            f = next(
                (x for x in self.findings if x["id"] == ans.get("findingId")), None
            )
            if not f or (f["owner"] and f["owner"] != agent):
                continue
            f["owner"] = agent
            f["answer"] = {
                "round": n,
                "response": ans.get("response"),
                "evidence": ans.get("evidence") or "",
            }


def _rounds(
    work: Path, roles: dict[str, str], assign: dict[str, str], lead: str = ""
) -> Ledger:
    """Fold every saved round result, in round order.

    Args:
        work: The architecture working directory.
        roles: Each roster agent's role.
        assign: Owners the coordinator assigned to findings.

    Returns:
        The ledger.
    """
    ledger = Ledger(assign, lead)
    folder = work / "rounds"
    found = []
    for p in folder.iterdir() if folder.is_dir() else []:
        m = ROUND_FILE.match(p.name)
        if p.is_file() and m and roles.get(m.group(4)) == m.group(3):
            found.append((int(m.group(1)), int(m.group(2)), m.group(3), m.group(4), p))
    for n, seq, role, agent, p in sorted(found):
        ledger.absorb(n, seq, role, agent, _load(p), str(p))
    return ledger


def _decision(work: Path, roles: dict[str, str]) -> dict | None:
    """Read the saved decision's verdict and the fields branching uses.

    Args:
        work: The architecture working directory.
        roles: Each roster agent's role.

    Returns:
        The verdict, its round, the proposers it returned the target to and its owner-concern
        kinds; None when no decision is saved.
    """
    path = work / "decision.json"
    if not path.is_file():
        return None
    dec = _load(path)
    if not isinstance(dec, dict):
        raise ResumeError(f"{path}: not a JSON object")
    returned = []
    for r in dec.get("returnTo") if isinstance(dec.get("returnTo"), list) else []:
        name = (
            _text(r.get("agentType")).replace(AGENT_PREFIX, "")
            if isinstance(r, dict)
            else ""
        )
        if roles.get(name) == "proposer" and name not in returned:
            returned.append(name)
    concerns = [
        c
        for c in (
            dec.get("ownerConcerns")
            if isinstance(dec.get("ownerConcerns"), list)
            else []
        )
        if isinstance(c, dict) and _text(c.get("concern"))
    ]
    kinds = [_text(c.get("kind")) for c in concerns]
    return {
        "verdict": _text(dec.get("verdict")),
        "coverageRevision": _text(dec.get("coverageRevision")),
        "round": dec.get("round") if isinstance(dec.get("round"), int) else 0,
        "returnTo": returned,
        "ownerConcerns": len(concerns),
        "ownerConcernKinds": kinds,
        "ownerOnly": bool(kinds) and all(k in OWNER_CONCERN_KINDS for k in kinds),
        "choices": len(dec.get("choices"))
        if isinstance(dec.get("choices"), list)
        else 0,
    }


def _integration(work: Path) -> dict:
    """Read what the integration saved: its report's file lists, its fingerprint, its reviews.

    Args:
        work: The architecture working directory.

    Returns:
        The report's changed, created and deleted files with counts of its open items (None
        when no report is saved), whether a fingerprint was saved before it, and the number of
        reviews with the last one's verdict and reviewed files.
    """
    update = None
    path = work / "architecture-update.json"
    if path.is_file():
        u = _load(path)
        if not isinstance(u, dict):
            raise ResumeError(f"{path}: not a JSON object")
        update = {
            "changedFiles": _paths(u.get("changedFiles")),
            "createdFiles": _paths(u.get("createdFiles")),
            "deletedFiles": _paths(u.get("deletedFiles")),
            "constraintIssues": len(_paths(u.get("constraintIssues"))),
            "contradictions": len(_paths(u.get("contradictions"))),
        }
    before = work / "integrate-before.json"
    saved_before = False
    if before.is_file():
        b = _load(before)
        saved_before = isinstance(b, dict) and isinstance(b.get("files"), dict)
    reviews = sorted(
        (int(m.group(1)), p)
        for p in (work.iterdir() if work.is_dir() else [])
        if p.is_file() and (m := REVIEW_FILE.match(p.name))
    )
    last = None
    if reviews:
        n, p = reviews[-1]
        r = _load(p)
        if not isinstance(r, dict):
            raise ResumeError(f"{p}: not a JSON object")
        last = {
            "n": n,
            "path": str(p),
            "conforms": r.get("conforms") is True,
            "coverageRevision": _text(r.get("coverageRevision")),
            "coverageChecks": r.get("coverageChecks", []),
            "reviewedFiles": _paths(r.get("reviewedFiles")),
            "findings": len(r.get("findings"))
            if isinstance(r.get("findings"), list)
            else 0,
        }
    return {
        "update": update,
        "beforeSaved": saved_before,
        "reviews": len(reviews),
        "lastReview": last,
    }


def proposal_team(saved: dict, requested: dict, roles: dict) -> dict:
    """Validate the durable two-person proposal budget consumed by architecture.js."""
    team = requested or saved
    if not team:
        return {}
    if not isinstance(team, dict):
        raise ResumeError("proposalTeam must be an object")
    lead, second = _text(team.get("lead")), _text(team.get("second"))
    if roles.get(lead) != "proposer" or (second and roles.get(second) != "proposer"):
        raise ResumeError(
            "proposalTeam must name a lead and at most one proposer specialist"
        )
    if second == lead:
        raise ResumeError("proposalTeam lead and second must differ")
    if saved and (
        lead != saved.get("lead") or (saved.get("second") and second != saved["second"])
    ):
        raise ResumeError(
            "proposalTeam cannot replace retained proposers with new specialists"
        )
    if second and not all(
        _text(team.get(k)) for k in ("unresolvedIssue", "evidence", "whySecond")
    ):
        raise ResumeError(
            "second proposer needs a specific unresolved issue, evidence and why the lead cannot resolve it alone"
        )
    return {
        k: _text(team.get(k))
        for k in ("lead", "second", "unresolvedIssue", "evidence", "whySecond")
    }


def resume_facts(
    work_dir: str, *, roster: str, assign: str = "", team: str = "", plan: str = ""
) -> dict:
    """Read the architecture step's saved work and return the facts its control flow needs.

    Writes the whole claim and finding ledger to `ledger.json` in the working directory, for the
    sessions that read it; prints none of it.

    Args:
        work_dir: The architecture working directory of one Epic.
        roster: Each role's agents, as `role=a,b;role=c`.
        assign: Owners the coordinator assigned to findings, as `F1.2.3=agent,...`.

    Returns:
        The compact facts: survey, rounds, decision and integration.

    Raises:
        ResumeError: A saved file cannot be read or parsed.
    """
    work = Path(work_dir)
    roles = parse_roster(roster)
    survey = None
    s = {}
    sj = work / "survey.json"
    if sj.is_file():
        s = _load(sj)
        if not isinstance(s, dict):
            raise ResumeError(f"{sj}: not a JSON object")
        caps = s.get("capabilities")
        survey = {
            "saved": (work / "survey.md").is_file() and bool(_text(s.get("subject"))),
            "subject": _text(s.get("subject")),
            "capabilities": len(caps) if isinstance(caps, list) else 0,
            "coverageSaved": bool(s.get("coverage")),
        }
    ledger_path = work / LEDGER_NAME
    previous = _load(ledger_path) if ledger_path.is_file() else {}
    selected = proposal_team(
        previous.get("proposalTeam", {}), json.loads(team) if team else {}, roles
    )
    assignments = dict(previous.get("assignments", {}))
    assignments.update(parse_assign(assign))
    ledger = _rounds(work, roles, assignments, selected.get("lead", ""))
    if selected:
        # Preserve answered history; transfer only outstanding legacy proposer findings.
        active = {selected["lead"], selected["second"]}
        for finding in ledger.findings:
            if (
                finding["verdict"] != "verified"
                and not any(
                    old.get("id") == finding["id"]
                    and (old.get("resolution") or {}).get("verdict") == "accepted"
                    for old in previous.get("findings", [])
                )
                and roles.get(finding["owner"]) == "proposer"
                and finding["owner"] not in active
            ):
                assignments[finding["id"]] = selected["lead"]
        ledger = _rounds(work, roles, assignments, selected.get("lead", ""))
    legacy_without_claims = [
        w
        for w, count in ledger.proposer_claims.items()
        if not count and selected and w not in {selected["lead"], selected["second"]}
    ]
    if selected:
        selected["adoptedAfterRound"] = previous.get("proposalTeam", {}).get(
            "adoptedAfterRound", ledger.last
        )
    consolidation_due = bool(legacy_without_claims) and not any(
        c["by"] == selected["lead"] and c["round"] > selected["adoptedAfterRound"]
        for c in ledger.claims
    )
    coverage, coverage_summary = coverage_facts(work, s, ledger.files)
    old_claims = {c["id"]: c for c in previous.get("claims", [])}
    for claim in ledger.claims:
        old = old_claims.get(claim["id"])
        claim["legacyRevision"] = (old or {}).get(
            "legacyRevision", (old or {}).get("revision", claim["revision"])
        )
        if claim["legacy"] and claim["legacyRevision"] != claim["revision"]:
            claim["verdicts"] = []
        if claim["evidenceErrors"] or any(
            v.startswith(("unreadable:", "invalid:"))
            for v in claim["viewState"].values()
        ):
            claim["verdicts"] = []
    rounds = round_facts(
        work,
        previous.get("roundPlans", []),
        json.loads(plan) if plan else None,
        ledger,
        roles,
        selected,
    )
    previous_findings = {f["id"]: f for f in previous.get("findings", [])}
    for finding in ledger.findings:
        claim = next((c for c in ledger.claims if c["id"] == finding["claimId"]), None)
        current_revision = (
            claim["revision"]
            if claim
            else view_content(str(work / "draft" / finding["file"]))
        )
        finding["initialRevision"] = previous_findings.get(finding["id"], {}).get(
            "initialRevision", finding["claimRevision"] or current_revision
        )
        finding["resolutionRevision"] = current_revision
        finding["resolution"] = next(
            (
                r
                for r in reversed(ledger.resolutions)
                if r.get("findingId") == finding["id"]
                and r.get("evidence")
                and r["by"] != finding["owner"]
                and finding["answer"]
                and r["round"] >= finding["answer"]["round"]
                and r.get("revision") == current_revision
                and (
                    finding["answer"].get("response") == "disputed"
                    or current_revision != finding["initialRevision"]
                )
            ),
            None,
        )
    open_findings = [
        {
            "id": f["id"],
            "verdict": f["verdict"],
            "owner": f["owner"],
            "file": f["file"],
            "answered": bool(f["answer"])
            and not (f["resolution"] and f["resolution"].get("verdict") == "rejected"),
        }
        for f in ledger.findings
        if f["verdict"] != "verified"
        and not (f["resolution"] and f["resolution"].get("verdict") == "accepted")
    ]
    unreviewed: dict[str, int] = {}
    for c in ledger.claims:
        if c["active"] and not c["verdicts"]:
            unreviewed[c["by"]] = unreviewed.get(c["by"], 0) + 1
    # Bind saved approval to claims as well as coverage without changing its consumer field.
    coverage_summary["revision"] = digest(
        {
            "coverage": coverage_summary["revision"],
            "claims": [
                {"id": c["id"], "revision": c["revision"]}
                for c in ledger.claims
                if c["active"]
            ],
        }
    )
    coverage["coverageRevision"] = coverage_summary["revision"]
    coverage_summary["gaps"].extend(rounds["reviewGaps"])
    ledger_path = work / LEDGER_NAME
    if work.is_dir():
        save_ledger(
            ledger_path,
            {
                "contractVersion": 2,
                "proposalTeam": selected,
                "assignments": assignments,
                "roundPlans": rounds["plans"],
                "claims": ledger.claims,
                "findings": ledger.findings,
                "savedResults": ledger.files,
                **coverage,
            },
        )
    integration = _integration(work)
    decision = _decision(work, roles)
    integration["coverageRevision"] = integration_revision(
        coverage_summary["revision"], integration["update"], work
    )
    return {
        "contractVersion": previous.get("contractVersion", 1),
        "dir": str(work),
        "exists": work.is_dir(),
        "ledger": str(ledger_path) if work.is_dir() else None,
        "survey": survey,
        "coverage": coverage_summary,
        "proposalTeam": selected,
        "rounds": {
            "last": rounds["last"],
            "pendingPlan": compact_plan(rounds["pendingPlan"]),
            "pendingRound": rounds["pendingPlan"]["round"]
            if rounds["pendingPlan"]
            else None,
            "pendingDispatches": len(rounds["pendingPlan"]["dispatches"])
            if rounds["pendingPlan"]
            else 0,
            "planKept": rounds["planKept"],
            "readyForDecision": bool(
                rounds["plans"]
                and rounds["plans"][-1].get("complete")
                and rounds["plans"][-1].get("readyForDecision")
            ),
            "results": len(ledger.files),
            "saved": ledger.saved,
            "writers": ledger.writers,
            "reviewers": ledger.reviewers,
            "legacyProposersWithoutClaims": legacy_without_claims
            if consolidation_due
            else [],
            "proposersWithoutClaims": sorted(
                set(
                    [
                        w
                        for w, k in ledger.proposer_claims.items()
                        if not k
                        and (
                            not selected or w in {selected["lead"], selected["second"]}
                        )
                    ]
                    + ([selected["lead"]] if consolidation_due else [])
                )
            ),
            "claims": len(ledger.claims),
            "findings": len(ledger.findings),
            "openFindings": open_findings,
            "unreviewedClaims": unreviewed,
            "overlapWarnings": rounds["overlapWarnings"],
        },
        "decision": decision,
        "integration": integration,
        "summary": {
            "survey": bool(survey and survey["saved"]),
            "lastRound": ledger.last,
            "claims": len(ledger.claims),
            "findings": len(ledger.findings),
            "openFindings": len(open_findings),
            "decision": decision["verdict"] if decision else None,
            "update": integration["update"] is not None,
            "reviews": integration["reviews"],
        },
    }
