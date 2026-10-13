"""Run the architecture part of an elaboration through the journal runner with stand-in sessions.

No agent, workflow or pipeline is started: every session is a stand-in that writes a result which
satisfies the architecture work contract. The checks cover the design's two walk-throughs and the
journal each leaves; a restart after a kill at every step boundary and after a failure of each
session and of two script steps; an invalidation from the check step; a review that returns a
finding, settled by a correction and, in a second run, by the decider; a result the architect
could not settle; and a mechanical defect that goes back to the architect before any reviewer.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/pipeline-contracts/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/artifact-handoff/scripts"))

from driver_surface_types import ARCH_PATH_ENV, CONTROL_REPO_ENV, HEADLESSENV_MODULE, STOP_FILE_ENV, HeadlessEnvironment
from orchestrator.checks.architecture_bench import (
    BEAD,
    CONCEPT,
    ArchBench,
)
from orchestrator.checks.architecture_standins import (
    ARCHITECT,
    CORRECT,
    DECIDER,
    GUARDIAN,
    LEAD,
    MAINTAINER,
    RECHECK,
    REVIEWERS,
    SPECIALISTS,
    TRD_AUTHOR,
    Scenario,
    install,
)
from orchestrator.checks.check_support import expected_error, report, require
from orchestrator.core import step_journal as sj
from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import driver_module
from orchestrator.core.models import StepError
from orchestrator.flows.architecture import ARCHITECT_DESCRIPTION, ARCHITECT_PURPOSE, ARCHITECT_REQUEST
from orchestrator.flows.architecture_check import (
    CHECK_DESCRIPTION,
    CORRECTION_DESCRIPTION,
    PROMOTE_DESCRIPTION,
    SELECTED,
)
from orchestrator.flows.architecture_earlier import EarlierWork, carry
from orchestrator.flows.architecture_files import (
    APPROVE,
    CHECK,
    CONFIRM_TRD,
    EARLIER_PREFIX,
    EARLIER_WORK,
    OPEN_RUN,
)
from orchestrator.flows.prd_to_spec import outermost_steps
from step_journal_contract import BEAD_TYPE_EPIC, PIPELINE_ELABORATION

if TYPE_CHECKING:
    from orchestrator.checks.journal_bench import Call
    from orchestrator.core.io import JsonValue
    from step_journal_contract import Journal, Step

WORK_REVIEWERS: Final[list[str]] = [GUARDIAN, REVIEWERS["runtime-failure"], REVIEWERS["trd"]]
OUTERMOST: Final[list[str]] = [
    "Open the run",
    "Architecture",
    "TRD",
    "Specs and Stories",
    "Tasks",
    "Task edges",
    "Score the Tasks",
    "Apply the done rule",
    "Story edges",
    "Mark the Epic elaborated",
]
TWICE: Final = 2
THRICE: Final = 3


def names(step: Step) -> list[str]:
    """List the names of a step's artifacts, leaving out the records of the steps it planned.

    Returns:
        The artifact names in the order recorded.

    """
    return [held["name"] for held in step["artifacts"] if not held["name"].startswith(sj.PLANNED_FOR_PREFIX)]


def values(step: Step, name: str) -> list[JsonValue]:
    """Read the value artifacts of a step that have one name.

    Returns:
        The values, in the order recorded.

    """
    return [held["value"] for held in step["artifacts"] if held["kind"] == "value" and held["name"] == name]


def started(root: Path, name: str, scenario: Scenario) -> ArchBench:
    """Make one scenario's bench with its stand-ins registered.

    Returns:
        The bench.

    """
    bench: ArchBench = ArchBench(root / name)
    install(bench, scenario)
    return bench


def run(bench: ArchBench) -> None:
    """Run the journal of a bench, in its own environment, until the TRD step is done."""
    with patch.dict(os.environ, bench.environment()):
        bench.run_architecture()


def architecture(bench: ArchBench) -> list[Step]:
    """List the child steps of the Architecture container.

    Returns:
        The steps, in order.

    """
    return bench.step("Architecture")["steps"]


def check_work_needed(root: Path) -> ArchBench:
    """Check walk-through 1: architecture work with two questions, a maintainer and three reviewers.

    Returns:
        The bench, for the checks that continue from its finished journal.

    """
    bench: ArchBench = started(root, "work", Scenario())
    run(bench)
    journal: Journal = bench.journal()
    require([step["description"] for step in journal["steps"]] == OUTERMOST, "the outermost steps, in order")
    opened: Step = bench.step("Open the run")
    owner, check, *reviews, promote = architecture(bench)
    require(opened.get("script") == OPEN_RUN and names(opened) == ["prd", "matrix prd row", "context"], "open the run")
    require(
        bench.step("Architecture").get("inputs") == [opened["id"]],
        "the Architecture container follows the open run",
    )
    require(
        (owner["description"], owner["purpose"], owner.get("agent"), owner.get("inputs"))
        == (ARCHITECT_DESCRIPTION, ARCHITECT_PURPOSE, ARCHITECT, [opened["id"]]),
        "the architect's step is the one the design states",
    )
    require(
        [child.get("agent") for child in owner["steps"]]
        == [TRD_AUTHOR, *SPECIALISTS, MAINTAINER, TRD_AUTHOR, ARCHITECT],
        "the architect's helpers and its Finish are its child steps",
    )
    require(names(owner) == ["state of the architecture"], "the architect's own output is its state")
    require(names(owner["steps"][-1]) == ["architecture result", "conclusion"], "Finish carries the result")
    require(
        (check["description"], check.get("script"), check.get("inputs")) == (CHECK_DESCRIPTION, CHECK, [owner["id"]]),
        "check",
    )
    require(names(check) == ["check result", "review scope", SELECTED], f"the check's artifacts: {names(check)}")
    require(values(check, SELECTED) == [WORK_REVIEWERS], f"the rule selects three reviewers: {values(check, SELECTED)}")
    require([step.get("agent") for step in reviews] == WORK_REVIEWERS, "one step per selected reviewer")
    require(
        all(step.get("inputs") == [check["id"]] and names(step) == ["review", "findings"] for step in reviews),
        "reviews",
    )
    require(
        (promote["description"], promote.get("script"), promote.get("inputs"))
        == (PROMOTE_DESCRIPTION, APPROVE, [step["id"] for step in reviews]),
        "the promotion follows the reviews",
    )
    require(names(promote) == ["approved items", "vault commit"], f"the promotion's artifacts: {names(promote)}")
    confirmed: Step = bench.step("TRD")
    require(
        confirmed.get("script") == CONFIRM_TRD and confirmed.get("inputs") == [bench.step("Architecture")["id"]],
        "TRD",
    )
    require(names(confirmed) == ["TRD", "TRD hash on the Epic bead"], f"the TRD step's artifacts: {names(confirmed)}")
    calls: list[Call] = bench.sessions.calls
    by_agent: dict[str, Call] = {call.agent: call for call in calls}
    require(calls[0].agent == ARCHITECT and len(calls) == len(by_agent), "the architect's session is the first")
    require(sorted(by_agent) == sorted([ARCHITECT, *WORK_REVIEWERS]), "four sessions; no lead and no decider")
    require(list(calls[0].inputs) == ["prd", "criteria", "context", "state", "step journal"], "the architect's labels")
    require(
        list(by_agent[GUARDIAN].inputs) == ["prd", "review scope", "architecture result", "criteria", "step journal"]
        and list(by_agent[REVIEWERS["trd"]].inputs)
        == ["prd", "review scope", "architecture result", "criteria", "trd", "step journal"],
        "a reviewer's labels, and the TRD for the reviewer of the TRD",
    )
    require(
        "lifecycle_state: effective" in (bench.vault / CONCEPT).read_text(encoding="utf-8"),
        "promoted in the vault",
    )
    require(bench.tools.count("push") == 1 and bench.tools.count("bd", "show") == TWICE, "one push; beads read twice")
    report("PASS: walk-through 1 leaves the design's journal: architect with helpers, check, three reviews, promotion")
    return bench


def check_already_approved(root: Path) -> None:
    """Check walk-through 2: everything approved, so the TRD's reviewer alone, and no vault commit."""
    bench: ArchBench = started(root, "approved", Scenario(work=False))
    run(bench)
    owner, check, review, promote = architecture(bench)
    require([child.get("agent") for child in owner["steps"]] == [TRD_AUTHOR, ARCHITECT], "one helper and Finish")
    require(values(check, SELECTED) == [[REVIEWERS["trd"]]], "the rule selects the TRD's reviewer only")
    require(review.get("agent") == REVIEWERS["trd"] and names(promote) == ["approved items"], "no vault commit")
    require([call.agent for call in bench.sessions.calls] == [ARCHITECT, REVIEWERS["trd"]], "two sessions")
    require(bench.tools.count("push") == 0, "nothing is pushed when no document changed")
    report("PASS: walk-through 2: the TRD's reviewer alone, promotion without a vault commit")


def check_restarts(root: Path) -> None:
    """Check that a restart of walk-through 1 lands on exactly the next step, at every boundary."""
    once: dict[str, int] = dict.fromkeys([ARCHITECT, *WORK_REVIEWERS], 1)
    boundaries: int = 0
    for stop in range(1, 6):
        killed: ArchBench = started(root, f"killed-{stop}", Scenario())
        with patch.dict(os.environ, killed.environment()):
            loop = killed.runner()
            for _ in range(stop):
                require(loop.run_next(), "a step ran before the kill")
            killed.run_architecture()
        require(dict(killed.counts) == once, f"after a kill at boundary {stop} each session ran once: {killed.counts}")
        require(killed.tools.count("push") == 1 and killed.tools.count("bd", "show") == TWICE, "script steps ran once")
        boundaries += 1
    for key in (ARCHITECT, *WORK_REVIEWERS):
        failed: ArchBench = started(root, f"failed-{key}", Scenario())
        failed.fail_once.add(key)
        with expected_error(StepError):
            run(failed)
        run(failed)
        require(dict(failed.counts) == {**once, key: TWICE}, f"after {key} failed only it ran again: {failed.counts}")
        again: Call = [call for call in failed.sessions.calls if call.agent == key][-1]
        require(again.resume, f"{key}: the failed step's session is resumed")
    for word in ("bd", "push"):
        broken: ArchBench = started(root, f"failed-{word}", Scenario())
        broken.tools.fail_once.add(word)
        with expected_error(RuntimeError):
            run(broken)
        run(broken)
        require(dict(broken.counts) == once, f"after a failed {word} no session ran again: {broken.counts}")
        require(broken.tools.count("push") == TWICE - (word == "bd"), f"{word}: the push is made as often as needed")
    report(f"PASS: a restart after a kill at {boundaries} boundaries and after 6 failures runs the next step onward")


def check_invalidation(bench: ArchBench) -> None:
    """Check that invalidating from the check step reruns exactly from there."""
    check: Step = bench.step(CHECK_DESCRIPTION)
    with patch.dict(os.environ, bench.environment()):
        sj.update_journal(bench.path, lambda journal: sj.invalidate_from(journal, check["id"], sj.timestamp()))
        bench.counts.clear()
        bench.run_architecture()
    require(ARCHITECT not in bench.counts and bench.counts, f"the architect is not run again: {bench.counts}")
    require(all(count == 1 for count in bench.counts.values()), "each reviewer the check selects again runs once")
    require(bench.step(CHECK_DESCRIPTION)["id"] == check["id"] and bench.step("TRD")["status"] == "done", "rerun")
    report("PASS: an invalidation from the check step reruns the check, its reviewers, the promotion and the TRD step")


def check_findings(root: Path) -> None:
    """Check a finding: the lead, one correction, the re-check, promotion; and the decider when it stays disputed."""
    bench: ArchBench = started(root, "finding", Scenario(finding=True))
    run(bench)
    steps: list[Step] = architecture(bench)
    require(
        [step.get("agent") or step.get("script") for step in steps]
        == [ARCHITECT, CHECK, *WORK_REVIEWERS, LEAD, APPROVE],
        "lead",
    )
    routed: Step = steps[-2]
    require(routed.get("inputs") == [step["id"] for step in steps[2:5]], "the lead is handed every review of the group")
    require(
        [child.get("agent") for child in routed["steps"]] == [ARCHITECT, GUARDIAN, LEAD],
        "correction, re-check, Finish",
    )
    first, fixed, recheck = (
        next(call for call in bench.sessions.calls if call.request == request)
        for request in (ARCHITECT_REQUEST, CORRECT, RECHECK)
    )
    original: Call = next(call for call in bench.sessions.calls if call.agent == GUARDIAN)
    require(fixed.resume and fixed.session == first.session, "the correction resumes the architect's own session")
    require(recheck.resume and recheck.session == original.session, "the re-check resumes the reviewer's own session")
    reviewed: Step = steps[2]
    require([held["name"] for held in reviewed["artifacts"]][:2] == ["review", "findings outside the scope"], "dropped")
    expected: dict[str, int] = {
        ARCHITECT: TWICE,
        GUARDIAN: TWICE,
        LEAD: TWICE,
        WORK_REVIEWERS[1]: 1,
        WORK_REVIEWERS[2]: 1,
    }
    require(dict(bench.counts) == expected, f"the sessions of a finding: {bench.counts}")
    lead_call: Call = next(call for call in bench.sessions.calls if call.agent == LEAD)
    require(
        list(lead_call.inputs) == ["findings", "architecture result", "criteria", "specialists", "step journal"],
        f"the lead's labels: {list(lead_call.inputs)}",
    )
    disputed: ArchBench = started(root, "disputed", Scenario(finding=True, disputed=True))
    run(disputed)
    require(disputed.counts[DECIDER] == 1 and disputed.counts[LEAD] == THRICE, f"the decider: {disputed.counts}")
    require(disputed.counts[ARCHITECT] == TWICE, "a disputed item never goes to the architect a second time")
    require(disputed.step(PROMOTE_DESCRIPTION)["status"] == "done", "the promotion follows the ruling")
    report("PASS: a finding goes to the lead, one resumed correction and re-check; a disputed one to the decider")


def check_unsettled_and_mechanical(root: Path) -> None:
    """Check a result the architect could not settle, and a mechanical defect before any reviewer."""
    unsettled: ArchBench = started(root, "unsettled", Scenario(unsettled=True))
    run(unsettled)
    order: list[str | None] = [step.get("agent") or step.get("script") for step in architecture(unsettled)]
    require(order == [ARCHITECT, CHECK, LEAD, CHECK, *WORK_REVIEWERS, APPROVE], f"unsettled goes to the lead: {order}")
    require(unsettled.counts[DECIDER] == 1 and unsettled.counts[LEAD] == TWICE, "the lead sends it to the decider")
    mechanical: ArchBench = started(root, "mechanical", Scenario(mechanical=True))
    run(mechanical)
    steps: list[Step] = architecture(mechanical)
    order = [step.get("agent") or step.get("script") for step in steps]
    require(order == [ARCHITECT, CHECK, ARCHITECT, CHECK, *WORK_REVIEWERS, APPROVE], f"mechanical: {order}")
    require(steps[2]["description"] == CORRECTION_DESCRIPTION and names(steps[1]) == ["check result"], "no scope yet")
    agents: list[str] = [call.agent for call in mechanical.sessions.calls]
    require(
        agents[:2] == [ARCHITECT, ARCHITECT] and LEAD not in agents,
        "the defect goes to the architect, not a reviewer",
    )
    require("findings" in mechanical.sessions.calls[1].inputs, "the correction is handed the check result")
    report("PASS: an unsettled result goes to the lead and the decider; a mechanical defect back to the architect")


def check_earlier_work(root: Path) -> None:
    """Check a journal created with earlier work: the architect is handed its files, and nothing else changes."""
    bench: ArchBench = started(root, "earlier", Scenario())
    survey: Path = bench.work / "architecture" / "survey.json"
    drafts: Path = bench.work / "architecture" / "draft"
    drafts.mkdir(parents=True)
    survey.write_text("{}", encoding="utf-8")
    work: list[EarlierWork] = [
        EarlierWork("Earlier work: the survey", "The check.", (("survey", survey),)),
        EarlierWork("Earlier work: the draft documents", "The check.", (("draft documents", drafts),)),
    ]
    created: Journal = sj.new_journal(BEAD, BEAD_TYPE_EPIC, PIPELINE_ELABORATION, outermost_steps())
    carried: list[Step] = carry(created, work, ARCHITECT, sj.timestamp())
    sj.create_journal(bench.path, created)
    opened: Step = bench.step("Open the run")
    holder, owner, check = architecture(bench)
    labels: list[str] = [f"{EARLIER_PREFIX}survey", f"{EARLIER_PREFIX}draft documents"]
    require(
        [names(step) for step in holder["steps"]] == [[label] for label in labels]
        and [step["id"] for step in holder["steps"]] == [step["id"] for step in carried]
        and all(step["status"] == "done" and step.get("script") == EARLIER_WORK for step in holder["steps"]),
        "each piece of earlier work is a done step that holds its file",
    )
    require(
        (owner.get("agent"), owner["status"], owner.get("inputs"))
        == (ARCHITECT, "planned", [opened["id"], holder["id"]]),
        "the architect's step is planned after the earlier work and is handed it",
    )
    require(check.get("script") == CHECK and check.get("inputs") == [owner["id"]], "the check follows the architect")
    following: Step | None = sj.next_step(bench.journal())
    require(following is not None and following["id"] == opened["id"], "the run begins at the open-run step")
    require(bench.step("Architecture")["status"] == "running", "the Architecture container is not done")
    run(bench)
    steps: list[Step] = architecture(bench)
    require(
        [step["id"] for step in steps[:3]] == [holder["id"], owner["id"], check["id"]]
        and sum(step.get("agent") == ARCHITECT for step in steps) == 1,
        "the open-run step plans no second step for the architect",
    )
    first: Call = bench.sessions.calls[0]
    require(
        list(first.inputs) == ["prd", "criteria", "context", "state", *labels, "step journal"],
        f"the architect's brief names the earlier work: {list(first.inputs)}",
    )
    require(
        (first.inputs[labels[0]], first.inputs[labels[1]]) == (survey, drafts) and first.agent == ARCHITECT,
        "the earlier work reaches the architect by its paths",
    )
    require(bench.counts[ARCHITECT] == 1 and bench.step("TRD")["status"] == "done", "the architect ran once")
    with patch.dict(os.environ, bench.environment()):
        sj.update_journal(bench.path, lambda journal: sj.invalidate_from(journal, opened["id"], sj.timestamp()))
        bench.sessions.calls.clear()
        bench.run_architecture()
    again: list[Step] = architecture(bench)
    require(
        [step["id"] for step in again[:2]] == [holder["id"], owner["id"]]
        and all(step["status"] == "done" and not names(step) for step in again[0]["steps"]),
        "after a start at the open-run step the earlier work is done again and holds nothing",
    )
    require(
        list(bench.sessions.calls[0].inputs) == ["prd", "criteria", "context", "state", "step journal"],
        "after a start at the open-run step the architect is handed no earlier work",
    )
    report("PASS: a journal created with earlier work hands its files to the architect, whose step runs once")


def main() -> None:
    """Run the architecture flow checks in a temporary directory with stand-in sessions."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-repo", required=True, type=Path)
    options: argparse.Namespace = parser.parse_args()
    control: Path = options.control_repo
    # The driver's modules read the installed plugin, so they are loaded before the check's own
    # configuration directory takes the place of the real one.
    with patch.dict(os.environ, {CONTROL_REPO_ENV: str(control.resolve())}):
        driver_module(HEADLESSENV_MODULE)
    directory: str
    with tempfile.TemporaryDirectory() as directory:
        root: Path = Path(directory).resolve()
        (root / "config").mkdir()
        values: dict[str, str] = {
            "CLAUDE_CONFIG_DIR": str(root / "config"),
            CONTROL_REPO_ENV: str(control.resolve()),
            "ATW_ORCH_SESSIONS": "4",
        }
        recorded: list[str] = []
        with (
            patch.dict(os.environ, values),
            patch.object(AgentRunner, "_version", lambda _runner: None),
            patch("beadgraph.write_metadata", lambda bead, _pairs, _control: recorded.append(bead)),
        ):
            for name in (ARCH_PATH_ENV, STOP_FILE_ENV):
                os.environ.pop(name, None)
            headless: object = driver_module(HEADLESSENV_MODULE)
            with patch.object(
                headless,
                HeadlessEnvironment.child_env.__name__,
                side_effect=lambda _scratch: dict(os.environ),
            ):
                finished: ArchBench = check_work_needed(root)
                require(recorded == [BEAD], "the TRD is marked on the Epic bead once")
                check_already_approved(root)
                check_invalidation(finished)
                check_restarts(root)
                check_findings(root)
                check_unsettled_and_mechanical(root)
                check_earlier_work(root)


if __name__ == "__main__":
    main()
