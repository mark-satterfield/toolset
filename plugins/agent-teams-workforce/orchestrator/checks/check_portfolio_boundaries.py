"""Local populated portfolio producer/consumer checks; no workflow or agent launch."""

from __future__ import annotations

import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Git fixture repositories in a temporary directory.
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))

import archbaseline
import archcoverage
import archevidence
import archresume
import archrounds
import jsonartifact
from architecture_artifacts import (
    VERDICT_VERIFIED,
    ReviewResult,
    WriterResult,
    parse_review_result,
    parse_writer_result,
)
from contracts import (
    SEAL_DIGEST_KEYS,
    SEAL_FORM_V2,
    SEAL_FORMS,
    SEAL_UNREADABLE_WARNING,
    JsonObject,
    SurveySeal,
    json_object,
    parse_survey_seal,
    survey_seal_path,
)
from orchestrator.checks.check_support import expected_error, require
from survey_contract import (
    ACTION_UNCHANGED,
    CODE_COMPLETE,
    COVERAGE_REQUIRED,
    DESIGN_REUSE,
    DISPOSITION_RETAIN,
    DOC_NONE,
    IMPL_NONE,
    KIND_BEHAVIOR,
    STATUS_PRESENT_AND_SUFFICIENT,
    SURVEY_FILE,
    EvidenceRef,
    Survey,
    parse_survey,
)

if TYPE_CHECKING:
    from contracts import FreshnessResult
    from roundcontracts import Dispatch, RoundPlan


def _evidence(path: str, repo: str = "") -> EvidenceRef:
    return {"path": path, "heading": "", "repo": repo, "revision": "", "url": ""}


def _survey(
    name: str,
    subject: str,
    view: Path,
    ref: EvidenceRef,
    *,
    cited: bool,
) -> Survey:
    """Build one valid single-capability survey whose code is complete and retained.

    Returns:
        A survey typed by, and accepted by the parser of, the generated survey contract.

    """
    survey: Survey = {
        "subject": subject,
        "subjectReason": "fixture requirement",
        "summary": "local contract fixture",
        "capabilities": [
            {
                "name": name,
                "requirements": ["R1"],
                "effectiveViews": [str(view)] if cited else [],
                "code": [ref["path"]] if cited else [],
                "openBeads": [],
                "openTargets": [],
            },
        ],
        "businessConflicts": [],
        "openTargets": [],
        "coverage": [
            {
                "id": f"coverage-{name}",
                "subject": subject,
                "scope": "service",
                "obligation": "serve callers",
                "reason": "R1",
                "status": STATUS_PRESENT_AND_SUFFICIENT,
                "action": ACTION_UNCHANGED,
                "sources": [str(view)],
                "views": [str(view)],
                "disposition": COVERAGE_REQUIRED,
                "dispositionReason": "required behavior",
                "evidenceRefs": [_evidence(str(view))],
            },
        ],
        "baseline": [
            {
                "id": name,
                "kind": KIND_BEHAVIOR,
                "requirements": ["R1"],
                "subjects": [subject],
                "documents": [],
                "code": {"state": CODE_COMPLETE, "behaviorEvidenceRefs": [ref], "infrastructureEvidenceRefs": []},
                "awsGuidance": [],
                "designAction": DESIGN_REUSE,
                "documentationAction": DOC_NONE,
                "implementationAction": IMPL_NONE,
                "rationale": "implemented",
                "conflicts": [],
                "current": "implemented",
                "target": "implemented",
                "disposition": DISPOSITION_RETAIN,
                "suitabilityEvidenceRefs": [ref],
            },
        ],
    }
    return parse_survey(survey)


def survey_fixture(root: Path) -> Survey:
    """Produce a populated coverage survey referencing a local architecture view.

    Returns:
        The input artifact for the real coverage and resume producers.

    """
    view: Path = root / "view.md"
    view.write_text("# Authentication\nA caller authenticates.\n", encoding="utf-8")
    return _survey("authentication", "authentication", view, _evidence(str(view)), cited=False)


def dispatch_fixture() -> Dispatch:
    """Produce a full coordinator dispatch before the round consumer enriches it.

    Returns:
        A valid author dispatch including optional selection and coverage fields.

    """
    return {
        "agentType": "architect",
        "role": "proposer",
        "task": "document authentication",
        "files": ["auth.md"],
        "answers": [],
        "selectionReason": "design owner",
        "repairIds": [],
        "claimIds": [],
        "claimFiles": [],
        "coverageIds": ["coverage-auth"],
    }


class PortfolioBoundaries(unittest.TestCase):
    """Exercise actual coverage, round persistence and enriched record consumers."""

    @staticmethod
    def test_populated_coverage_resume_roundtrip() -> None:
        """Preserve full coverage while projecting its revision-only round binding."""
        with tempfile.TemporaryDirectory() as temporary:
            root: Path = Path(temporary)
            survey: Survey = survey_fixture(root)
            (root / SURVEY_FILE).write_text(json.dumps(survey), encoding="utf-8")
            coverage, _ = archcoverage.coverage_facts(survey, [])
            require(bool(coverage["coverage"][0]["evidenceState"]), "coverage fixture must contain real evidence")
            plan: RoundPlan = {
                "round": 1,
                "dispatches": [dispatch_fixture()],
                "reason": "new authored view",
                "overlaps": [],
                "readyForDecision": False,
            }
            initial = archresume.resume_facts(
                str(root),
                archresume.ResumeOptions(roster="proposer=architect", plan=json.dumps(plan)),
            )
            saved = json_object(jsonartifact.read_artifact(root / "ledger.json", strict=False))
            require(bool(saved["coverage"]), "saved ledger lost enriched coverage")
            resumed = archresume.resume_facts(str(root), archresume.ResumeOptions(roster="proposer=architect"))
            require(
                initial["rounds"]["pendingPlan"] == resumed["rounds"]["pendingPlan"],
                "saved enriched plan does not resume",
            )
            require(resumed["rounds"]["pendingRound"] == 1, "author work must remain pending")
            (root / "view.md").write_text("# Changed authentication\n", encoding="utf-8")
            changed = archresume.resume_facts(str(root), archresume.ResumeOptions(roster="proposer=architect"))
            require(
                changed["coverage"]["revision"] != resumed["coverage"]["revision"],
                "changed real view must invalidate coverage",
            )

    @staticmethod
    def test_stale_assigned_claim_stays_pending() -> None:
        """A removed writer result must create a review gap, never finish its plan."""
        with tempfile.TemporaryDirectory() as temporary:
            reviewer: Dispatch = {
                **dispatch_fixture(),
                "agentType": "reviewer",
                "role": "reviewer",
                "assignedClaims": [{"id": "old-claim", "revision": "previous"}],
            }
            plan: RoundPlan = {
                "round": 1,
                "dispatches": [reviewer],
                "readyForDecision": True,
                "reason": "review the assigned claim",
                "overlaps": [],
            }
            facts = archrounds.round_facts(
                Path(temporary),
                archrounds.RoundInputs([plan], None, {"reviewer": "reviewer"}),
                archresume.Ledger({}),
            )
            require(any("old-claim" in gap for gap in facts["reviewGaps"]), "missing assignment must be diagnosed")
            require(facts["pendingPlan"] is not None, "missing claim cannot complete the plan")
            require(not facts["plans"][0]["complete"], "missing claim plan was marked complete")

    @staticmethod
    def test_claim_review_ledger_to_round_consumer() -> None:
        """Fold actual writer/reviewer records before consuming their enriched ledger."""
        with tempfile.TemporaryDirectory() as temporary:
            root: Path = Path(temporary)
            draft: Path = root / "draft"
            draft.mkdir()
            (draft / "auth.md").write_text("# Authentication\n", encoding="utf-8")
            rounds: Path = root / "rounds"
            rounds.mkdir()
            writer_path: Path = rounds / "r1-1-proposer-architect.json"
            reviewer_path: Path = rounds / "r1-2-reviewer-reviewer.json"
            writer: WriterResult = {
                "files": ["auth.md"],
                "claims": [
                    {
                        "claimId": "",
                        "claim": "callers authenticate",
                        "file": "auth.md",
                        "citation": "R1",
                        "evidenceRefs": [],
                        "supersedes": [],
                    },
                ],
                "answers": [],
                "businessConflicts": [],
                "coverage": [],
                "summary": "documented authentication",
            }
            writer_path.write_text(json.dumps(writer), encoding="utf-8")
            ledger: archresume.Ledger = archresume.Ledger({})
            ledger.absorb_writer(
                archresume.RoundSource(1, 1, "proposer", "architect", str(writer_path)),
                parse_writer_result(writer_path),
            )
            reviewer: ReviewResult = {
                "findings": [
                    {
                        "claimId": ledger.claims[0]["id"],
                        "claim": "callers authenticate",
                        "file": "auth.md",
                        "verdict": VERDICT_VERIFIED,
                        "evidence": "read the authored view",
                        "owner": "architect",
                    },
                ],
                "coverageChecks": [],
                "resolutions": [],
                "summary": "verified the authored claim",
            }
            reviewer_path.write_text(json.dumps(reviewer), encoding="utf-8")
            ledger.absorb_review(
                archresume.RoundSource(1, 2, "reviewer", "reviewer", str(reviewer_path)),
                parse_review_result(reviewer_path),
            )
            plan: RoundPlan = {
                "round": 1,
                "dispatches": [
                    dispatch_fixture(),
                    {
                        **dispatch_fixture(),
                        "agentType": "reviewer",
                        "role": "reviewer",
                        "claimIds": [ledger.claims[0]["id"]],
                    },
                ],
                "reason": "author and review authentication",
                "overlaps": [],
                "readyForDecision": False,
            }
            result = archrounds.round_facts(
                root,
                archrounds.RoundInputs([plan], None, {"architect": "proposer", "reviewer": "reviewer"}),
                ledger,
            )
            require(bool(ledger.claims[0]["verdicts"]), "actual reviewer verdict was lost")
            require(bool(result["plans"]), "actual enriched ledger rejected by rounds")

    @staticmethod
    def test_boolean_round_number_is_not_a_plan() -> None:
        """A coordinator plan whose round is a JSON boolean is dropped, never read as round 1."""
        with tempfile.TemporaryDirectory() as temporary:
            plans: list[RoundPlan] = json.loads(
                json.dumps(
                    [
                        {
                            "round": True,
                            "dispatches": [dispatch_fixture()],
                            "readyForDecision": False,
                            "reason": "boolean round",
                            "overlaps": [],
                        },
                    ],
                ),
            )
            facts = archrounds.round_facts(
                Path(temporary),
                archrounds.RoundInputs(plans, None, {"architect": "proposer"}),
                archresume.Ledger({}),
            )
            require(not facts["plans"], "boolean round accepted as a plan")
            require(facts["pendingPlan"] is None, "boolean round produced pending work")


def _git(repo: Path, *arguments: str) -> str:
    executable: str | None = shutil.which("git")
    if executable is None:
        message = "git is required by the named-repository evidence fixture"
        raise FileNotFoundError(message)
    done: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Resolved Git executable and fixed argv.
        [executable, "-C", str(repo), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    output: str = done.stdout
    return output.strip()


def _commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", f"fixture {name}")


def _named_survey(work: Path, repo_name: str, governed_view: Path) -> Survey:
    survey: Survey = _survey("cap", "service", governed_view, _evidence("source.py", repo_name), cited=True)
    (work / SURVEY_FILE).write_text(json.dumps(survey), encoding="utf-8")
    return survey


def _menu(work: Path, rows: list[JsonObject]) -> None:
    (work / "repositories.json").write_text(json.dumps(rows), encoding="utf-8")


class EvidenceBoundaries(unittest.TestCase):
    """Actual repository menu, survey seal and source binding producers to their consumers."""

    @staticmethod
    def test_named_repository_evidence_through_seal_and_bindings() -> None:
        """Bind named citations to the saved menu's checkout; approval excludes governed views."""
        with tempfile.TemporaryDirectory() as temporary:
            root: Path = Path(temporary)
            work: Path = root / "architecture"
            work.mkdir()
            repo: Path = root / "repo"
            repo.mkdir()
            _git(repo, "init", "-q", "-b", "main")
            _git(repo, "config", "user.name", "Fixture")
            _git(repo, "config", "user.email", "fixture@example.invalid")
            _commit(repo, "source.py", "original\n")
            arc42: Path = root / "arch" / "arc42"
            arc42.mkdir(parents=True)
            view: Path = arc42 / "service.md"
            view.write_text("# Service\n", encoding="utf-8")
            prd: Path = root / "prd.md"
            prd.write_text("# Requirement\n", encoding="utf-8")
            _named_survey(work, "named-service", view)
            _menu(work, [{"name": "named-service", "path": str(repo), "role": "service", "lifecycle": "active"}])
            survey_path: Path = work / SURVEY_FILE

            def fresh(*, seal: bool = False) -> FreshnessResult:
                return archbaseline.survey_freshness(
                    survey_path,
                    archbaseline.FreshnessOptions(
                        inputs=[prd] if seal else None,
                        seal=seal,
                        form=SEAL_FORM_V2,
                        context_sha="a" * 64,
                    ),
                )

            require(fresh(seal=True)["current"], "named evidence must seal current")
            saved = json_object(json.loads(survey_seal_path(survey_path).read_text(encoding="utf-8")))
            require("evidenceReadable" not in saved, "readability must stay a live fact, not a persisted field")
            produced: SurveySeal = parse_survey_seal(saved)
            require(produced.get("form") == SEAL_FORM_V2, "the produced seal must validate as the requested form")
            require(fresh()["current"], "unchanged named evidence must stay current")
            approval = archevidence.source_binding(work, governed=arc42)
            completion = archevidence.source_binding(work)
            require(not approval["errors"] and not completion["errors"], "resolved citations reported errors")
            require(len(completion["states"]) > len(approval["states"]), "governed view was not excluded")
            _commit(repo, "unrelated.txt", "unrelated\n")
            require(fresh()["current"], "an unrelated main commit invalidated cited evidence")
            view.write_text("# Service rewritten by integration\n", encoding="utf-8")
            require(
                archevidence.source_binding(work, governed=arc42) == approval,
                "an integration write to a governed view revoked approval",
            )
            require(archevidence.source_binding(work) != completion, "completion ignored a changed cited view")
            _commit(repo, "source.py", "changed\n")
            require(not fresh()["current"], "a changed cited source stayed current")
            require(archevidence.source_binding(work, governed=arc42) != approval, "approval ignored a cited source")
            require(fresh(seal=True)["current"], "resealed named evidence must be current")
            clone: Path = root / "clone"
            _git(root, "clone", "-q", str(repo), str(clone))
            _menu(work, [{"name": "named-service", "path": str(clone), "role": "service", "lifecycle": "active"}])
            require(not fresh()["current"], "a moved checkout kept the old binding")
            _menu(work, [{"name": "named-service", "path": None, "role": "service", "lifecycle": "active"}])
            unresolved = fresh(seal=True)
            require(not unresolved["current"], "an uncloned repository sealed current")
            require(any("no resolved checkout" in w for w in unresolved["warnings"]), "unresolved name not reported")
            require(bool(archevidence.source_binding(work)["errors"]), "approval accepted an unresolved citation")

    @staticmethod
    def test_repository_menu_contract() -> None:
        """Reject menus that are not the producer's exact name/nullable-path rows."""
        with tempfile.TemporaryDirectory() as temporary:
            work: Path = Path(temporary)
            require(archevidence.load_repository_paths(work) == {}, "a missing menu must map nothing")
            _menu(work, [{"name": "a", "path": None}, {"name": "b", "path": "/abs/b"}, {"name": "b", "path": "/abs/b"}])
            require(archevidence.load_repository_paths(work) == {"b": "/abs/b"}, "null or duplicate rows mis-mapped")
            invalid: list[tuple[type[Exception], str]] = [
                (ValueError, json.dumps([{"name": "a"}])),
                (ValueError, json.dumps([{"name": "a", "path": "relative"}])),
                (ValueError, json.dumps([{"name": "", "path": None}])),
                (ValueError, json.dumps([{"name": "a", "path": "/x"}, {"name": "a", "path": "/y"}])),
                (TypeError, json.dumps({"name": "a", "path": None})),
            ]
            for kind, text in invalid:
                (work / "repositories.json").write_text(text, encoding="utf-8")
                with expected_error(kind):
                    archevidence.load_repository_paths(work)
            with expected_error(ValueError):
                archevidence.evidence_state([], repository_paths={"a": "relative"})

    @staticmethod
    def test_malformed_seals_are_not_current() -> None:
        """A malformed or wrongly typed seal is a warning and never a current survey."""
        with tempfile.TemporaryDirectory() as temporary:
            work: Path = Path(temporary)
            view: Path = work / "view.md"
            view.write_text("# View\n", encoding="utf-8")
            survey_path: Path = work / SURVEY_FILE
            survey_path.write_text(json.dumps(survey_fixture(work)), encoding="utf-8")
            seal: Path = survey_seal_path(survey_path)
            digest: str = "b" * 64
            sealed: SurveySeal = {
                "inputs": [],
                "repos": [],
                "revision": digest,
                "surveySha256": digest,
                "contextSha": "",
            }
            undigested: dict[str, object] = {k: v for k, v in sealed.items() if k not in SEAL_DIGEST_KEYS}
            unknown_form: str = "v3"
            require(unknown_form not in SEAL_FORMS, "the unknown-form fixture names a real seal form")
            cases: list[object] = [
                [],
                {**undigested, "form": []},
                {**sealed, "form": SEAL_FORM_V2, "inputs": None},
                {**sealed, "form": unknown_form},
                {**sealed, "repos": [""]},
                {**sealed, "form": SEAL_FORM_V2, "revision": "short"},
            ]
            for malformed in cases:
                seal.write_text(json.dumps(malformed), encoding="utf-8")
                result = archbaseline.survey_freshness(survey_path, archbaseline.FreshnessOptions())
                require(not result["current"], f"malformed seal was current: {malformed!r}")
                require(
                    any(SEAL_UNREADABLE_WARNING in w for w in result["warnings"]),
                    f"not reported: {malformed!r}",
                )
                require(archbaseline.survey_binding(seal) is None, f"binding accepted: {malformed!r}")


if __name__ == "__main__":
    unittest.main()
