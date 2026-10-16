"""The sessions that review unapproved architecture, route findings and rule on what stays disputed.

A reviewer is handed only the unapproved items its criteria apply to, and, for a conclusion that the
Epic needs nothing added or changed, the effective documents the architect cites as meeting it.
A finding outside that scope
is dropped and counted. The first review that returns a finding, or asks for alternatives, plans
one step for the lead after the last reviewer; the lead decides what each finding needs and adds
the steps for it under its own step. The decider rules only where the lead sends a matter to it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from architecture_work_contract import (
    ROUTING_REJECT,
    validate_architecture_question,
    validate_architecture_ruling,
    validate_lead_routing,
    validate_scope_review,
)
from matrix_contract import KIND_DISAGREEMENT, REL_DISPUTES
from matrixstore import read_matrix
from step_journal_contract import STATUS_DONE

from orchestrator.core import step_journal
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, write_json
from orchestrator.core.journal_registry import agent_step
from orchestrator.core.journal_steps import (
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_check import (
    FINDINGS_LEAD_DESCRIPTION,
    FINDINGS_LEAD_PURPOSE,
    validate_reviewer_scope,
)
from orchestrator.flows.architecture_files import (
    ARCHITECTURE_FOLDER,
    ARTIFACT_RESOLVED,
    ARTIFACT_REVIEW,
    HUMAN_ACTION_STAGE,
    LABEL_FINDINGS,
    LABEL_PRD,
    LABEL_QUESTION,
    LABEL_RESULT,
    LABEL_RULING,
    LABEL_SCOPE,
    LABEL_TRD,
    PLUGIN,
    PROMOTE,
    ROLE_DECIDER,
    ROLE_LEAD,
    ROLE_REVIEWER,
    ArchitectureContext,
    ArchitectureStepError,
    agents_with_role,
    checked_file,
    cited_document,
    document_path,
    is_finish,
    matrix_file,
    output_check,
    planned_params,
    read_context,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from architecture_work_contract import (
        ArchitectureRuling,
        LeadRouting,
        ScopeFinding,
        ScopeReview,
        UnsettledMatter,
    )
    from matrixstore import Matrix
    from step_journal_contract import Artifact, Journal, Step, StepId, StepPlan

    from orchestrator.flows.architecture_check import ReviewerScope

FINDINGS: Final = "findings"
"""The value a review records: how many of its findings are inside the reviewer's scope.

The findings themselves are in the review file, the artifact ``review``.
"""
OUTSIDE_SCOPE: Final = "findings outside the scope"
ALTERNATIVES: Final = "alternatives requested"
ROUTING: Final = "routing"
STANDS: Final = "stands"
SETTLED: Final = "disagreements settled"
ATTR_STANDS: Final = "stands"
ATTR_HEADING: Final = "heading"
SCOPE_PARAM: Final = "scope"
TRD_PARAM: Final = "trd"
ID_LENGTH: Final = 8
"""How much of a step id names a file the step's session writes."""


def _original(run: StepRun) -> Step | None:
    """Find the review the rule planned for the agent of a step.

    Returns:
        The first step of the journal that this agent performs and that the check step handed a
        review scope; None when the journal holds none.

    """
    journal: Journal = run.journal()
    step: Step
    for step in step_journal.steps_in_order(journal):
        if step.get("agent") == run.step.get("agent") and SCOPE_PARAM in planned_params(journal, step["id"]):
            return step
    return None


def _in_scope(finding: ScopeFinding, scope: ReviewerScope) -> bool:
    """Tell whether a finding is about an item of the reviewer's scope.

    Returns:
        True when the finding names a document or a heading of the scope, by its item or by its
        location, and for every finding of a reviewer whose scope is the TRD.

    """
    if scope["trd"] is not None:
        return True
    items: set[str] = set()
    documents: set[str] = set()
    headings: set[tuple[str, str]] = set()
    for listed in scope["documents"]:
        path: str = document_path(listed["id"])
        items.update({listed["id"], listed["name"], path})
        documents.add(path)
        for heading in listed["headings"]:
            items.update({heading, f"{path}#{heading}"})
            headings.add((path, heading))
    source: str = finding["location"]["source"]
    return (
        finding["item"] in items
        or (source, finding["location"]["heading"]) in headings
        or any(source.endswith(document) for document in documents)
    )


def _review_group(run: StepRun) -> tuple[list[Step], StepId]:
    """List the reviews of the group a review belongs to, and the step before the promotion.

    Returns:
        Every agent step with the review's inputs that comes before the promotion step in the
        review's container, and the id of the step the promotion step follows.

    Raises:
        ArchitectureStepError: No promotion step follows the reviewer in its container.

    """
    journal: Journal = run.journal()
    parent: Step | None = step_journal.parent_step(journal, run.step["id"])
    siblings: list[Step] = journal["steps"] if parent is None else parent["steps"]
    position: int = next(index for index, step in enumerate(siblings) if step["id"] == run.step["id"])
    later: list[int] = [
        index for index, step in enumerate(siblings) if index > position and step.get("script") == PROMOTE
    ]
    if not later:
        raise ArchitectureStepError(run, "no promotion step follows the review in its container")
    reviews: list[Step] = [
        step for step in siblings[: later[0]] if "agent" in step and step.get("inputs") == run.step.get("inputs")
    ]
    return reviews, siblings[later[0] - 1]["id"]


def _holds_raised(step: Step) -> bool:
    """Tell whether a done review holds something for the lead to route.

    Returns:
        True when the step is done and holds a count of findings above zero or a request for
        alternatives.

    """
    return step["status"] == STATUS_DONE and any(
        held["kind"] == "value" and (held["name"] == ALTERNATIVES or (held["name"] == FINDINGS and bool(held["value"])))
        for held in step["artifacts"]
    )


def _lead_group(reviews: list[Step], follows: StepId, lead: str) -> StepGroup:
    """Plan the lead's step after the last reviewer of a review, unless one is planned already.

    Returns:
        The group: one step for the lead, handed every review of the group, placed before the
        promotion step.

    """
    plan: StepPlan = {
        "description": FINDINGS_LEAD_DESCRIPTION,
        "purpose": FINDINGS_LEAD_PURPOSE,
        "agent": lead,
        "inputs": [step["id"] for step in reviews],
    }
    return StepGroup((NewStep(plan),), follows=follows, unless_agent=lead)


def _accept_review(run: StepRun, output: Path, scope_path: Path, *, original: bool) -> Completion:
    """Record a review: its file, how many findings are inside the reviewer's scope, and the lead when needed.

    The lead is planned by an original review when it, or a done review of its group, holds a
    finding or a request for alternatives, so the lead's step is planned again by whichever
    review of the group runs again. A review file or a scope file that does not satisfy its
    contract, or an original review that no promotion step follows, raises
    ``ArchitectureStepError``.

    Returns:
        The completion. A finding about an item outside the scope is taken out of the review
        file and counted; the review as the reviewer returned it is kept beside the file.

    """
    review: ScopeReview = checked_file(run, output, validate_scope_review)
    scope: ReviewerScope = checked_file(run, scope_path, validate_reviewer_scope)
    kept: list[ScopeFinding] = [finding for finding in review["findings"] if _in_scope(finding, scope)]
    dropped: int = len(review["findings"]) - len(kept)
    artifacts: list[Artifact] = [file_artifact(ARTIFACT_REVIEW, output)]
    if dropped:
        write_json(output.with_suffix(".as-returned.json"), review)
        review["findings"] = kept
        write_json(output, review)
        artifacts.append(value_artifact(OUTSIDE_SCOPE, dropped))
    artifacts.append(value_artifact(FINDINGS, len(kept)))
    if review["alternativesRequested"]:
        artifacts.append(value_artifact(ALTERNATIVES, len(review["alternativesRequested"])))
    if not original:
        return Completion(artifacts=tuple(artifacts))
    reviews: list[Step]
    follows: StepId
    reviews, follows = _review_group(run)
    routed: bool = bool(kept or review["alternativesRequested"]) or any(_holds_raised(step) for step in reviews)
    lead: str = agents_with_role(run.tools.plugin, ROLE_LEAD)[0]
    return Completion(artifacts=tuple(artifacts), add=(_lead_group(reviews, follows, lead),) if routed else ())


@agent_step(*agents_with_role(PLUGIN, ROLE_REVIEWER))
def reviewer(run: StepRun) -> AgentLaunch:
    """Build the session of a reviewer: its first review, or a re-check the lead ordered.

    A re-check is a step of the same agent that the check step did not plan. It is handed the
    same narrowed scope and continues the reviewer's own session.

    The reviewer is handed its scope, the architect's result and, when its scope names them,
    the TRD and the PRD: a reviewer reads the arc42 headings its scope names under the
    architecture root, and the PRD only when it checks content against the Epic's requirements.

    Returns:
        The launch, with exactly the input labels the reviewers' definitions name.

    Raises:
        ArchitectureStepError: A re-check has no earlier review by the same agent in the journal.

    """
    context: ArchitectureContext = read_context(run)
    params: Mapping[str, JsonValue] = run.params()
    original: bool = SCOPE_PARAM in params
    holder: Step | None = None
    if not original:
        first: Step | None = _original(run)
        holder = run.session_holder()
        if first is None or holder is None:
            raise ArchitectureStepError(run, "a re-check follows a review by this agent, and the journal holds none")
        params = planned_params(run.journal(), first["id"])
    scope_path: Path = Path(str(params[SCOPE_PARAM]))
    trd: JsonValue = params.get(TRD_PARAM)
    prd: str | None = checked_file(run, scope_path, validate_reviewer_scope)["prd"]
    name: str = run.step.get("agent", "")
    suffix: str = "" if original else f".{run.step['id'][:ID_LENGTH]}"

    def accept(accepted: StepRun, output: Path) -> Completion:
        return _accept_review(accepted, output, scope_path, original=original)

    return AgentLaunch(
        output=run.context.work / ARCHITECTURE_FOLDER / "reviews" / f"{name}{suffix}.json",
        validate=output_check(validate_scope_review),
        outcome="The review of every item in the review scope.",
        accept=accept,
        add_dirs=(
            run.context.work,
            Path(context["architectureRoot"]),
            *((Path(prd).parent,) if prd is not None else ()),
        ),
        files=(
            (LABEL_SCOPE, scope_path),
            (LABEL_RESULT, Path(context["resultPath"])),
            *(((LABEL_TRD, Path(trd)),) if isinstance(trd, str) else ()),
            *(((LABEL_PRD, Path(prd)),) if prd is not None else ()),
        ),
        resume_from=None if holder is None else holder["id"],
        hand_inputs=False,
    )


def _raised(run: StepRun, path: Path) -> bool:
    """Tell whether a review raised something for the lead to route.

    Returns:
        True when the review file holds a finding or a request for alternatives.

    """
    review: ScopeReview = checked_file(run, path, validate_scope_review)
    return bool(review["findings"] or review["alternativesRequested"])


@agent_step(*agents_with_role(PLUGIN, ROLE_LEAD))
def lead(run: StepRun) -> AgentLaunch:
    """Build the session of the lead: its routing, or its "Finish" after the steps it added.

    The lead adds the steps its routing calls for under its own step, so its session normally
    ends with child steps and nothing is accepted here. A routing that rejects every item needs
    no step. Launched for "Finish", the lead either records that every item is resolved or adds
    the steps that remain. The design specialists it may ask are the agents whose definitions
    state the design-specialist role; it reads them from the definitions, so nothing is listed
    for it.

    Returns:
        The launch, with exactly the input labels the lead's definition names.

    """
    context: ArchitectureContext = read_context(run)
    folder: Path = run.context.work / ARCHITECTURE_FOLDER
    finishing: bool = is_finish(run)
    owner: Step | None = step_journal.parent_step(run.journal(), run.step["id"]) if finishing else run.step
    owner_id: str = run.step["id"] if owner is None else owner["id"]
    reviews: list[Path] = [path for path in dict.fromkeys(run.inputs.files(ARTIFACT_REVIEW)) if _raised(run, path)]

    def accept(accepted: StepRun, output: Path) -> Completion:
        routing: LeadRouting = checked_file(accepted, output, validate_lead_routing)
        waiting: list[str] = [item["item"] for item in routing["items"] if item["routing"] != ROUTING_REJECT]
        if finishing and not accepted.step["artifacts"]:
            raise ArchitectureStepError(
                accepted,
                "the lead neither recorded that every item is resolved nor added a step for what remains",
            )
        if not finishing and waiting:
            raise ArchitectureStepError(accepted, f"the routing sends {waiting} to further work and adds no step")
        return Completion(artifacts=(file_artifact(ROUTING, output), value_artifact(ARTIFACT_RESOLVED, True)))

    return AgentLaunch(
        output=folder / f"routing-{owner_id[:ID_LENGTH]}.json",
        validate=output_check(validate_lead_routing),
        outcome="The routing of every item.",
        accept=accept,
        add_dirs=(run.context.work, Path(context["architectureRoot"])),
        files=(
            *((LABEL_FINDINGS, path) for path in reviews),
            (LABEL_RESULT, Path(context["resultPath"])),
        ),
        fresh_output=not finishing,
        hand_inputs=False,
    )


def _disagreements(arch: Path, matter: UnsettledMatter) -> tuple[list[JsonValue], list[str]]:
    """Read back from the matrix the disagreements a question to the decider is about.

    A disagreement is one the question is about when the positions' evidence cites every document
    heading the disagreement disputes.

    Returns:
        The ids of those disagreements whose ``stands`` is set, and of those whose ``stands`` is
        unset.

    """
    matrix: Matrix = read_matrix(matrix_file())
    cited: set[tuple[str | None, str]] = {
        (cited_document(arch, citation["source"]), citation["heading"].strip())
        for position in matter["positions"]
        for citation in position["evidence"]
    }
    settled: list[JsonValue] = []
    unset: list[str] = []
    for entry in matrix.entries((KIND_DISAGREEMENT,)):
        disputed: set[tuple[str | None, str]] = {
            (statement.end, str(statement.attributes.get(ATTR_HEADING, "")).strip())
            for statement in matrix.outgoing(entry.id, (REL_DISPUTES,))
        }
        if disputed and disputed <= cited:
            if entry.attributes.get(ATTR_STANDS):
                settled.append(entry.id)
            else:
                unset.append(entry.id)
    return settled, unset


@agent_step(*agents_with_role(PLUGIN, ROLE_DECIDER))
def decider(run: StepRun) -> AgentLaunch:
    """Build the session of the decider: one question file in, one ruling out.

    The decider records its ruling in the matrix itself, with ``atw-matrix settle``, as the
    settlement of the matter. The accept step reads each disagreement the question is about back
    from the matrix and fails the step when its ``stands`` is unset. A ruling that raises an owner
    concern fails the step with the concerns as its evidence.

    Returns:
        The launch, with the question as its only input.

    Raises:
        ArchitectureStepError: The step is handed no question file.

    """
    context: ArchitectureContext = read_context(run)
    question: Path | None = run.inputs.optional_file(LABEL_QUESTION)
    if question is None:
        raise ArchitectureStepError(run, f"its inputs hold no file artifact named {LABEL_QUESTION!r}")
    matter: UnsettledMatter = checked_file(run, question, validate_architecture_question)
    arch: Path = Path(context["architectureRoot"])

    def accept(accepted: StepRun, output: Path) -> Completion:
        ruling: ArchitectureRuling = checked_file(accepted, output, validate_architecture_ruling)
        concerns: tuple[str, ...] = tuple(f"{entry['kind']}: {entry['concern']}" for entry in ruling["ownerConcerns"])
        if concerns:
            raise StepError(HUMAN_ACTION_STAGE, OTHER_CAUSE, concerns)
        settled: list[JsonValue]
        unset: list[str]
        settled, unset = accepted.tools.portfolio(accepted.inputs.stage, _disagreements, arch, matter)
        if unset:
            raise ArchitectureStepError(
                accepted,
                "the matrix holds no ruling for a disagreement the question is about: its `stands` is unset; "
                "the ruling is recorded with atw-matrix settle",
                *unset,
            )
        return Completion(
            artifacts=(
                file_artifact(LABEL_RULING, output),
                value_artifact(STANDS, ruling["stands"]),
                value_artifact(SETTLED, settled),
            ),
        )

    return AgentLaunch(
        output=run.context.work / ARCHITECTURE_FOLDER / f"ruling-{run.step['id'][:ID_LENGTH]}.json",
        validate=output_check(validate_architecture_ruling),
        outcome="The ruling on the question.",
        accept=accept,
        add_dirs=(run.context.work, Path(context["architectureRoot"])),
        files=((LABEL_QUESTION, question),),
        hand_inputs=False,
    )
