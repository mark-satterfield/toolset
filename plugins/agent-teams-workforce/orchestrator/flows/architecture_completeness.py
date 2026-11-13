"""The independent completeness review of an Epic's architecture, before any TRD write or spec.

The solutions architect reviews and approves its own architecture; the spec stage was the first
independent look at the detailed design, and found what it left unstated one element per round.
``architecture-completeness-reviewer`` looks first. The check plans it once it finds no
mechanical defect and nothing the lead must settle, before the first promotion of the pass
(:func:`review_due`). The reviewer checks every element the Epic adds or changes, and every
element of its reach with no approved mark, against criteria A15 to A20 of the review standard,
and checks the approved documents it reads for statements that contradict each other. It writes
findings only (``completeness-findings.schema.json``).

The step that accepts the findings files them for the solutions architect as the open design
gaps of ``design_gaps.REVIEW_SLUG`` (one file, every repository's elements together), so the
check after the review plans the architect's step that answers them in one round
(``design_gaps.gap_round``), with the document writes, the index and a check after it. The review
runs at most :data:`MAX_REVIEWS` times in one pass through the architecture, and again only after
a review that found something; the findings of the last review still go to the architect.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Final

from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_registry import agent_step
from orchestrator.core.journal_steps import (
    AgentLaunch,
    Completion,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.flows import design_gaps
from orchestrator.flows.architecture_files import (
    LABEL_CONTEXT,
    LABEL_PRD,
    LABEL_RESULT,
    LABEL_SCOPE,
    LABEL_TRD,
    PROMOTE,
    ArchitectureContext,
    architecture_folder,
    journal_file,
    read_context,
)

# isort: split
# step_journal puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from step_journal_contract import KIND_VALUE, STATUS_DONE

if TYPE_CHECKING:
    from step_journal_contract import Journal, Step, StepPlan

REVIEWER: Final = "architecture-completeness-reviewer"
REVIEW_REF: Final = "completeness"
REVIEW_DESCRIPTION: Final = "Review the architecture for what a spec would have to decide"
REVIEW_PURPOSE: Final = (
    "Every route, store, event value, name, idempotency key and timeout a spec needs is stated, and no two "
    "approved documents contradict each other, before any spec is written"
)
SCHEMA: Final = "skills/artifact-handoff/schemas/completeness-findings.schema.json"
FINDINGS: Final = "completeness findings"
FOUND: Final = "completeness findings found"
"""The value artifact that records how many findings the review returned."""
MAX_REVIEWS: Final = 2
"""How many completeness reviews one pass through the architecture runs at most."""
ID_LENGTH: Final = 8


def _reviews(journal: Journal) -> list[Step]:
    """List the done completeness reviews of the journal.

    Returns:
        Each, in walk order.

    """
    return [
        step
        for step in step_journal.steps_in_order(journal)
        if step.get("agent") == REVIEWER and step["status"] == STATUS_DONE
    ]


def _promoted(journal: Journal) -> bool:
    """Tell whether the journal holds a done promotion: specs may have been written against the architecture.

    Returns:
        True when a promotion step is done.

    """
    return any(
        step.get("script") == PROMOTE and step["status"] == STATUS_DONE for step in step_journal.steps_in_order(journal)
    )


def _found(step: Step) -> int:
    """Read how many findings a done review recorded.

    Returns:
        The count; 0 when the step records none.

    """
    counts: list[JsonValue] = [
        held["value"] for held in step["artifacts"] if held["kind"] == KIND_VALUE and held["name"] == FOUND
    ]
    return next((count for count in counts if isinstance(count, int)), 0)


def review_due(run: StepRun) -> bool:
    """Tell whether the check plans a completeness review before the TRD write and the promotion.

    Returns:
        True before the first promotion of the pass, when no review has run, or when fewer than
        :data:`MAX_REVIEWS` have run and the last one found something.

    """
    journal: Journal = run.journal()
    if _promoted(journal):
        return False
    done: list[Step] = _reviews(journal)
    if not done:
        return True
    return len(done) < MAX_REVIEWS and _found(done[-1]) > 0


def review_plan(check: str) -> StepPlan:
    """Plan the completeness review after a check.

    Args:
        check: The check step, whose review scope the reviewer is handed.

    Returns:
        The reviewer's step, with the ref :data:`REVIEW_REF`.

    """
    return {
        "ref": REVIEW_REF,
        "description": REVIEW_DESCRIPTION,
        "purpose": REVIEW_PURPOSE,
        "agent": REVIEWER,
        "inputs": [check],
    }


def _row(finding: dict[str, JsonValue]) -> str:
    """State one finding as the gap row the architect answers.

    Returns:
        The criterion, the element, the finding and its correction, in one line.

    """
    element: JsonValue = finding.get("element")
    about: str = f" {element}" if isinstance(element, str) and element else ""
    return f"{finding['criterion']}{about}: {finding['finding']} Correction: {finding['correction']}"


def file_findings(work: Path, findings: list[dict[str, JsonValue]]) -> Path | None:
    """File the review's findings as the open design gaps of the completeness review.

    Returns:
        The filed file; None, and nothing filed, when there are no findings.

    """
    if not findings:
        return None
    rows: defaultdict[str, list[str]] = defaultdict(list)
    finding: dict[str, JsonValue]
    for finding in findings:
        rows[check_type(finding["documents"], list[str])[0]].append(_row(finding))
    path: Path = design_gaps.open_file(work, design_gaps.REVIEW_SLUG)
    write_json(
        path,
        {
            "repository": design_gaps.REVIEW_SOURCE,
            "documents": [{"document": document, "gaps": gaps} for document, gaps in rows.items()],
        },
    )
    return path


@agent_step(REVIEWER)
def reviewer(run: StepRun) -> AgentLaunch:
    """Build the reviewer's session: the PRD, the TRD, the context, the result and the review scope in, findings out.

    Returns:
        The launch. Its accepted findings are filed for the solutions architect
        (:func:`file_findings`), and the step records the findings file and how many there are.

    """
    context: ArchitectureContext = read_context(run)
    arch: Path = Path(context["architectureRoot"])

    def accept(accepted: StepRun, output: Path) -> Completion:
        findings: list[dict[str, JsonValue]] = [
            json_object(held) for held in check_type(strict_json(output)["findings"], list[JsonValue])
        ]
        file_findings(accepted.context.work, findings)
        return Completion(artifacts=(file_artifact(FINDINGS, output), value_artifact(FOUND, len(findings))))

    return AgentLaunch(
        output=architecture_folder(run.context.work) / f"completeness-{run.step['id'][:ID_LENGTH]}.json",
        validate=run.tools.plugin / SCHEMA,
        outcome="A finding for every value a spec of this Epic would have to decide, and every contradiction found.",
        accept=accept,
        add_dirs=(architecture_folder(run.context.work), arch),
        files=(
            (LABEL_PRD, journal_file(run, LABEL_PRD)),
            (LABEL_TRD, Path(context["trdPath"])),
            (LABEL_CONTEXT, journal_file(run, LABEL_CONTEXT)),
            (LABEL_RESULT, Path(context["resultPath"])),
            (LABEL_SCOPE, run.inputs.file(LABEL_SCOPE)),
        ),
        hand_inputs=False,
    )
