"""Exercise one repository's spec review with every session launch replaced by a stand-in.

The flow, the receipts, the schemas and the acceptance of each result are the real ones; only the
session itself is replaced, by a function that writes what a session would have written.
"""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))
from hierarchy import SPAN_ELEMENTS_FILE
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.core.agent_context import brief
from orchestrator.core.agents import AgentRunner, validate_output
from orchestrator.core.artifacts import ArtifactStore, load_artifactio
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE, EventName
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.models import AgentStep, RunContext, StepError
from orchestrator.core.tools import Tools
from orchestrator.flows import spec_authoring
from orchestrator.flows.spec_authoring import SpecAuthoring, SpecRequest
from orchestrator.flows.spec_review import (
    DECIDER,
    REVIEWER,
    SpecReviewOutcome,
)
from placement_contract import KEY_FRONTEND, KEY_ITEM_IDS, KEY_PLACEMENTS, KEY_REPO_PATH
from review_criteria import CRITERIA_PATH
from spec_review_contract import (
    DOCUMENT_CRITERIA,
    DOCUMENT_DATA_MODEL,
    DOCUMENT_SPEC,
    RULING_FINDING_STANDS,
    Finding,
    RulingValue,
    SpecDocument,
)

SLUG: Final[str] = "probe"
DOCUMENT_TEXT: Final[str] = "---\ndecisionIds: []\n---\n# Specification\n"
CORRECTED: Final[str] = "\nCorrected.\n"
KINDS: Final[tuple[SpecDocument, ...]] = (DOCUMENT_SPEC, DOCUMENT_DATA_MODEL, DOCUMENT_CRITERIA)


def finding(identifier: str, document: SpecDocument, criterion: str) -> Finding:
    """Build one finding as a reviewer session would write it.

    Returns:
        The finding.

    """
    return {
        "id": identifier,
        "document": document,
        "criterion": criterion,
        "location": "API",
        "observation": "The route states no status codes.",
        "correction": "State the status codes of the route.",
        "doneWhen": "The route lists each status code it returns.",
    }


@dataclass
class Sessions:
    """What the stand-in sessions of one scenario write."""

    findings: list[Finding] = field(default_factory=list)
    reviewer_fails: bool = False
    disputes: dict[SpecDocument, list[str]] = field(default_factory=dict)
    rulings: dict[str, RulingValue] = field(default_factory=dict)


class StandInRunner(AgentRunner):
    """Run a step with the session launch replaced; validate and accept its output as the runner does."""

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def __init__(
        self,
        context: RunContext,
        store: ArtifactStore,
        sessions: Sessions,
        documents: dict[str, Path],
    ) -> None:
        """Bind the scenario and the path of each specification document."""

        def emit(event: EventName, **fields: JsonValue) -> None:
            del event, fields

        super().__init__(context, store, emit=emit)
        self.sessions: Sessions = sessions
        self.documents: dict[str, Path] = documents
        self.steps: list[AgentStep] = []
        self.missing_inputs: list[str] = []

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def run(self, step: AgentStep) -> Path:
        """Stand in for one session, then validate and accept what it wrote.

        Returns:
            The accepted artifact path.

        """
        self.steps.append(step)
        self.missing_inputs.extend(path for path in step.inputs if not Path(path).exists())
        self._stand_in(step)
        final: Path = step.final or step.output
        return self._accept_result(step, final, validate_output(step))

    def _stand_in(self, step: AgentStep) -> None:
        """Write what the step's session would have written.

        Raises:
            StepError: The scenario has the reviewer session fail.

        """
        name: str = step.stage.rsplit(":", 1)[-1]
        step.output.parent.mkdir(parents=True, exist_ok=True)
        if step.output.suffix == ".md":
            step.output.write_text(DOCUMENT_TEXT, encoding="utf-8")
        elif step.agent == REVIEWER:
            if self.sessions.reviewer_fails:
                raise StepError(step.stage, OTHER_CAUSE, ("the stand-in reviewer session failed",))
            write_json(step.output, json_object({"findings": self.sessions.findings, "summary": "Reviewed."}))
        elif step.agent == DECIDER:
            write_json(
                step.output,
                {
                    "rulings": [
                        {"findingId": identifier, "ruling": ruling, "reason": "Measured.", "directive": "Apply it."}
                        for identifier, ruling in self.sessions.rulings.items()
                    ],
                    "summary": "Ruled.",
                },
            )
        else:
            kind: str
            turn: str
            kind, turn = name.rsplit(".", 1)
            disputed: list[str] = [] if turn == "revision" else self.sessions.disputes.get(_kind(kind), [])
            own: list[str] = [item["id"] for item in self.sessions.findings if item["document"] == kind]
            if not own or set(own) - set(disputed):
                with self.documents[kind].open("a", encoding="utf-8") as handle:
                    handle.write(CORRECTED)
            write_json(
                step.output,
                {
                    "disputes": [
                        {"findingId": identifier, "reason": "The route is internal.", "evidence": "trd.md#T3"}
                        for identifier in disputed
                    ],
                    "summary": "Corrected.",
                },
            )


def _kind(value: str) -> SpecDocument:
    """Narrow a stage name part to a specification document kind.

    Returns:
        The kind.

    Raises:
        ValueError: The value is not a specification document kind.

    """
    kind: SpecDocument
    for kind in KINDS:
        if kind == value:
            return kind
    message: str = f"not a specification document kind: {value!r}"
    raise ValueError(message)


@dataclass
class Scenario:
    """One repository's flow with stand-in sessions, in its own directory."""

    flow: SpecAuthoring
    runner: StandInRunner
    store: ArtifactStore


def build_scenario(root: Path, sessions: Sessions) -> Scenario:
    """Build a repository's spec authoring flow over the files the earlier phases leave.

    Returns:
        The flow, its stand-in runner and its receipt store.

    """
    dispatch: DispatchArguments = dispatch_arguments()
    work: Path = root / "work"
    repo: Path = root / "repo"
    arch: Path = root / "arch"
    prd: Path = root / "prd" / "prd.md"
    directory: Path
    for directory in (work, repo, arch, prd.parent):
        directory.mkdir(parents=True, exist_ok=True)
    if not prd.exists():
        prd.write_text("# PRD\n", encoding="utf-8")
        # The TRD phase writes its document at this path before any repository's specs are written.
        (work / "trd.md").write_text(DOCUMENT_TEXT, encoding="utf-8")
        write_json(
            work / "repo-scoping.json",
            {
                KEY_PLACEMENTS: [
                    {
                        KEY_REPO_PATH: str(repo),
                        "repoName": "probe",
                        KEY_ITEM_IDS: ["W1"],
                        KEY_FRONTEND: False,
                        "rationale": "The one placed item.",
                    },
                ],
                "missingRepos": [],
                "noCode": [],
                "spanRationale": "One repository.",
            },
        )
        write_json(
            work / SPAN_ELEMENTS_FILE,
            {
                "ok": True,
                "refusals": [],
                "summary": {"ok": True, "refusals": []},
                "items": [{"id": "W1", "element": "sign-up handler", "views": []}],
            },
        )
    context: RunContext = RunContext(
        "epic",
        dispatch.FLOW_PRD_TO_SPEC,
        {
            "slug": SLUG,
            "repoPath": str(repo),
            "storyKey": "S1",
            dispatch.KEY_ARCH_PATH: str(arch),
            dispatch.KEY_PRD: {dispatch.PRD_PATH: str(prd)},
        },
        work,
        "spec-review-probe",
    )
    store: ArtifactStore = ArtifactStore(load_artifactio(), root, work, "epic", "spec-review-probe")
    documents: dict[str, Path] = {
        kind: work / name
        for kind, name in zip(
            KINDS,
            (f"spec-{SLUG}.md", f"spec-{SLUG}.data-model.md", f"spec-{SLUG}.criteria.md"),
            strict=True,
        )
    }
    runner: StandInRunner = StandInRunner(context, store, sessions, documents)
    flow: SpecAuthoring = SpecAuthoring(context, store, runner, Tools(root / "evidence"))
    require(list(flow.docs) == list(documents.values()), "the flow writes its documents at other paths")
    return Scenario(flow, runner, store)


def step_names(steps: list[AgentStep]) -> list[str]:
    """Name each step by the last part of its stage.

    Returns:
        The names, in the order the steps ran.

    """
    return [step.stage.rsplit(":", 1)[-1] for step in steps]


def _resumed_without_sessions(root: Path) -> None:
    """Require a later run over the same files to start no session at all."""
    again: Scenario = build_scenario(root, Sessions(reviewer_fails=True))
    again.flow.documents()
    again.flow.review()
    require(not again.runner.steps, f"an unchanged repository started sessions again: {step_names(again.runner.steps)}")


def _review_passes(root: Path) -> None:
    """Check a review with no finding: one reviewer session, handed exactly six files, and nothing after it."""
    scenario: Scenario = build_scenario(root, Sessions())
    scenario.flow.documents()
    authored: list[AgentStep] = list(scenario.runner.steps)
    ended: SpecReviewOutcome = scenario.flow.review()
    after: list[AgentStep] = scenario.runner.steps[len(authored) :]
    require(step_names(after) == ["review"], f"a passing review ran {step_names(after)}")
    reviewer: AgentStep = after[0]
    require(reviewer.agent == REVIEWER, "the review step does not start openapi-contract-reviewer")
    work: Path = scenario.flow.work
    documents: set[str] = {str(step.output) for step in authored}
    others: list[str] = [str(work / "trd.md"), str(work / f"spec-{SLUG}.context.json"), str(CRITERIA_PATH)]
    handed: list[str] = list(reviewer.inputs)
    # Two authors run at the same time, so the order their sessions were recorded in is not fixed.
    require(
        set(handed[: len(documents)]) == documents and handed[len(documents) :] == others,
        f"the reviewer is handed {handed}, not the documents {sorted(documents)} and then {others}",
    )
    require(
        not scenario.runner.missing_inputs,
        f"a step names a file no earlier step wrote: {scenario.runner.missing_inputs}",
    )
    sent: object = json.loads(brief("epic", reviewer, [(Path(path).stem, Path(path)) for path in reviewer.inputs]))
    named: list[object] = [item.get("path") for item in sent.get("inputs", [])] if isinstance(sent, dict) else []
    require(named == [str(Path(path).resolve()) for path in handed], "the reviewer's brief names other files")
    require(
        reviewer.add_dirs == (work, CRITERIA_PATH.parent),
        "the reviewer may read more than its inputs' directories",
    )
    require(not ended["findings"] and not ended["corrected"] and not ended["disputed"], "a passing review had findings")
    require((work / f"spec-{SLUG}.review-outcome.json").is_file(), "the review left no recorded result")
    require(scenario.flow.review() == ended and len(scenario.runner.steps) == len(authored) + 1, "the review ran twice")
    _resumed_without_sessions(root)


def _findings_reach_authors(root: Path) -> None:
    """Check that findings go once to each author, a dispute is ruled on and an upheld finding is revised."""
    sessions: Sessions = Sessions(
        findings=[
            finding("F1", DOCUMENT_SPEC, "I1"),
            finding("F2", DOCUMENT_DATA_MODEL, "I2"),
            finding("F3", DOCUMENT_CRITERIA, "A5"),
        ],
        disputes={DOCUMENT_DATA_MODEL: ["F2"]},
        rulings={"F2": RULING_FINDING_STANDS},
    )
    scenario: Scenario = build_scenario(root, sessions)
    scenario.flow.documents()
    authored: int = len(scenario.runner.steps)
    ended: SpecReviewOutcome = scenario.flow.review()
    after: list[AgentStep] = scenario.runner.steps[authored:]
    require(
        step_names(after)
        == [
            "review",
            "spec.correction",
            "data-model.correction",
            "criteria.correction",
            "ruling",
            "data-model.revision",
            "criteria.revision",
        ],
        f"the findings were routed as {step_names(after)}",
    )
    requests: tuple[SpecRequest, SpecRequest, SpecRequest] = scenario.flow.requests()
    work: Path = scenario.flow.work
    review: str = str(work / f"spec-{SLUG}.review.json")
    correction: AgentStep = after[1]
    require(correction.agent == requests[0].agent, "a finding on the contracts document went to another agent")
    require(
        review in correction.inputs and str(requests[0].output) in correction.inputs,
        "the author's correction is not handed the review and its own document",
    )
    ruling: AgentStep = after[4]
    require(ruling.agent == DECIDER, "the ruling seat changed")
    require(
        str(work / f"spec-{SLUG}.data-model.correction.json") in ruling.inputs
        and str(work / f"spec-{SLUG}.spec.correction.json") not in ruling.inputs,
        "the decider is not handed exactly the corrections that state a dispute",
    )
    require(str(work / f"spec-{SLUG}.ruling.json") in after[5].inputs, "the revision is not handed the ruling")
    require(
        not scenario.runner.missing_inputs,
        f"a step names a file no earlier step wrote: {scenario.runner.missing_inputs}",
    )
    require(
        (ended["findings"], ended["dropped"], ended["disputed"], ended["upheld"])
        == (["F1", "F2"], ["F3"], ["F2"], ["F2"]),
        f"the recorded result is {ended}",
    )
    require(ended["corrected"] == list(KINDS), f"documents corrected: {ended['corrected']}")
    require(ended["revised"] == [DOCUMENT_DATA_MODEL, DOCUMENT_CRITERIA], f"documents revised: {ended['revised']}")
    require(any("F3" in warning for warning in ended["warnings"]), "a dropped finding left no warning")
    request: SpecRequest
    for request in requests:
        require(CORRECTED in request.output.read_text(encoding="utf-8"), f"{request.output.name} was not corrected")
        require(
            scenario.store.reusable(request.inputs, (request.output,)),
            f"{request.output.name} was left without a receipt for its corrected bytes",
        )
    _resumed_without_sessions(root)


def _reviewer_fails(root: Path) -> None:
    """Check that a failed reviewer session raises, records nothing and sends nothing to an author."""
    scenario: Scenario = build_scenario(root, Sessions(reviewer_fails=True))
    scenario.flow.documents()
    authored: int = len(scenario.runner.steps)
    with expected_error(StepError):
        scenario.flow.review()
    require(
        step_names(scenario.runner.steps[authored:]) == ["review"],
        "a failed review was followed by other sessions",
    )
    require(
        not (scenario.flow.work / f"spec-{SLUG}.review-outcome.json").exists(),
        "a failed review left a recorded result",
    )
    source: str = inspect.getsource(spec_authoring.run)
    require(
        0 <= source.find("flow.documents()") < source.find("flow.review()") < source.find("flow.story_document()"),
        "spec_authoring.run does not review the documents before it writes the Story",
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Exercise a passing review, findings with a dispute, and a failed reviewer session."""
    with tempfile.TemporaryDirectory() as temporary:
        root: Path = Path(temporary).resolve()
        _review_passes(root / "passes")
        _findings_reach_authors(root / "findings")
        _reviewer_fails(root / "fails")
    report("PASS: spec review passes, routes findings to one correction each with a ruled dispute, and fails closed")


if __name__ == "__main__":
    main()
