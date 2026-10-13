"""A temporary Epic, vault, matrix and plugin for the architecture flow checks; not a check itself.

Every session is a stand-in (``journal_bench.StandIns``): it reads the brief the runner sent,
writes a result that satisfies the architecture work contract, and where the scenario says so
edits the journal, the vault and the matrix as the agent would with ``atw-step-journal`` and
``atw-matrix``. Beads and ``git push`` are stood in at the ``Tools`` boundary. The vault is a
git repository in the temporary directory and the matrix a file beside it.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed argv: git in a temporary repository.
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, override

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))

import matrixstore
import matrixsync
from architecture_work_contract import (
    CRITERION_NOT_APPLICABLE,
    ArchitectureResult,
    Conclusion,
    CriterionAnswer,
    ScopeFinding,
    ScopeReview,
    validate_architecture_result,
    validate_scope_review,
)
from driver_surface_types import PRD_DIR_ENV
from matrix_contract import APPROVAL_APPROVED, BASIS_REVIEWED, MATRIX_ENV, Matrix
from orchestrator.checks.check_support import require
from orchestrator.checks.journal_bench import StandIns
from orchestrator.core import step_journal as sj
from orchestrator.core.agents import AgentRunner
from orchestrator.core.driver_contracts import dispatch_arguments
from orchestrator.core.events import EventWriter
from orchestrator.core.frontmatter import split_front_matter
from orchestrator.core.journal_run import JournalRunner, open_journal
from orchestrator.core.models import RunContext
from orchestrator.core.tools import CommandResult, Tools
from orchestrator.flows.architecture_files import PLUGIN
from orchestrator.flows.elaboration_support import ARCHITECTURE_PHASE
from orchestrator.flows.prd_to_spec import outermost_steps
from review_criteria import LEVEL_ARCHITECTURE, LEVEL_TECHNICAL_REQUIREMENT, load_criteria
from step_journal_contract import BEAD_TYPE_EPIC, PIPELINE_ELABORATION, BeadId, Journal, Step, StepPlan

if TYPE_CHECKING:
    from collections.abc import Sequence

    from orchestrator.core.io import JsonValue

BEAD: Final[BeadId] = BeadId("ssbd-arch.1")
ARCH: Final = Path("docs") / "tech" / "architecture"
SDLC: Final = Path("docs") / "sdlc"
PRD: Final = SDLC / "mvp" / "prds" / "address-proof.md"
CONSTRAINTS: Final = ARCH / "arc42" / "02-architecture-constraints" / "README.md"
CONCEPT: Final = ARCH / "arc42" / "08-crosscutting-concepts" / "email-channel.md"
STAMP: Final[matrixstore.Stamp] = matrixstore.Stamp("2026-01-01T00:00:00Z", "check")
IDENTITY: Final[tuple[str, ...]] = (
    "-c",
    "user.name=check",
    "-c",
    "user.email=check@example.invalid",
    "-c",
    "commit.gpgsign=false",
)


def git(repository: Path, *arguments: str) -> str:
    """Run one git command in a temporary repository, as a committer made for the check.

    Returns:
        What the command printed.

    """
    done: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv; git in a temporary repository.
        [shutil.which("git") or "git", *IDENTITY, *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout


class BenchTools(Tools):
    """The deterministic tools with beads, the push and the control repository's git stood in."""

    def __init__(self, evidence: Path, vault: Path) -> None:
        """Bind the temporary vault, the one repository whose git commands really run."""
        super().__init__(evidence)
        self.vault: Path = vault
        self.calls: list[tuple[str, ...]] = []
        self.fail_once: set[str] = set()
        self.pushed: str = git(vault, "rev-parse", "HEAD").strip()

    def note(self, *call: str) -> None:
        """Record one stood-in call, and fail it when a failure is injected for its first word.

        Raises:
            RuntimeError: A failure was injected for this kind of call; it is injected once.

        """
        self.calls.append(call)
        if call[0] in self.fail_once:
            self.fail_once.discard(call[0])
            message: str = f"injected failure in {call[0]}"
            raise RuntimeError(message)

    def count(self, *call: str) -> int:
        """Count the recorded calls that begin with some words.

        Returns:
            How many calls begin with ``call``.

        """
        return sum(1 for made in self.calls if made[: len(call)] == call)

    @override
    def bd(self, args: list[str], *, stage: str, stdin: str | None = None) -> str:
        """Answer ``bd show`` for the Epic of the check; no beads command runs.

        Returns:
            The JSON beads would print for the Epic.

        """
        self.note("bd", *args)
        epic: dict[str, JsonValue] = {
            "id": BEAD,
            "title": "Address proof",
            "issue_type": "epic",
            "labels": ["prd:address-proof"],
            "metadata": {},
        }
        return json.dumps([epic])

    @override
    def git(
        self,
        repo: Path,
        args: list[str],
        *,
        stage: str,
        branch: str = "main",
        remote: str = "origin",
    ) -> CommandResult:
        """Run git in the temporary vault, record a push, and record anything in another repository.

        Returns:
            The command result.

        """
        if repo.resolve() != self.vault:
            return CommandResult(("git", *args), 0, "", "")
        if args[:1] == ["push"]:
            self.note("push")
            self.pushed = git(repo, "rev-parse", "HEAD").strip()
            return CommandResult(("git", *args), 0, "", "")
        return CommandResult(("git", *args), 0, git(repo, *args), "")

    @override
    def command(
        self,
        argv: Sequence[str],
        *,
        stage: str,
        cwd: Path | None = None,
        timeout: float = 120,
        check: bool = True,
    ) -> CommandResult:
        """Run a read-only git command in the temporary vault; answer one elsewhere with nothing.

        Returns:
            The command result.

        """
        if cwd is None or cwd.resolve() != self.vault:
            return CommandResult(tuple(argv), 0, "", "")
        if "rev-list" in argv:
            ahead: int = int(git(cwd, "rev-parse", "HEAD").strip() != self.pushed)
            return CommandResult(tuple(argv), 0, f"{ahead}\n", "")
        return CommandResult(tuple(argv), 0, git(cwd, *argv[1:]), "")


def make_vault(root: Path) -> Path:
    """Make the temporary vault: a git repository with the constraints, one concept and one PRD.

    Returns:
        The vault root.

    """
    vault: Path = (root / "vault").resolve()
    texts: dict[Path, str] = {
        CONSTRAINTS: "---\nlifecycle_state: effective\n---\n# Constraints\n\n## Idempotency\n\nUse the chassis.\n",
        CONCEPT: "---\nlifecycle_state: effective\n---\n# Email channel\n\n## Proof\n\nA link proves the address.\n",
        PRD: "# Address proof\n\nThe seeker proves the address by email.\n",
    }
    for relative, text in texts.items():
        (vault / relative).parent.mkdir(parents=True, exist_ok=True)
        (vault / relative).write_text(text, encoding="utf-8")
    git(vault, "init", "-q")
    git(vault, "add", "-A")
    git(vault, "commit", "-q", "--no-verify", "-m", "vault")
    return vault


def make_matrix(path: Path, vault: Path) -> None:
    """Create the temporary matrix with the vault's documents read and approved, as carried over."""
    matrixstore.create_matrix(path, matrixstore.empty_matrix(STAMP.at))

    def carried(matrix: Matrix) -> None:
        matrixsync.sync_documents(matrix, vault / ARCH, STAMP, full=True)
        for node in matrix["nodes"].values():
            for entry in node.get("headings", {}).values():
                entry["approvedHash"] = entry["hash"]
            if "approval" in node:
                node["approval"] = {"state": APPROVAL_APPROVED, "basis": BASIS_REVIEWED}

    matrixstore.update_matrix(path, carried)


def make_plugin(root: Path) -> Path:
    """Write a plugin whose agents have the names, roles and descriptions of the real ones.

    Returns:
        The plugin folder; each definition is a short one a stand-in session is launched with.

    """
    plugin: Path = root / "plugin"
    (plugin / "agents").mkdir(parents=True)
    for source in sorted((PLUGIN / "agents").glob("*.md")):
        fields: dict[str, object] = split_front_matter(source.read_text(encoding="utf-8"), source.stem)[0]
        if "role" not in fields:
            continue
        (plugin / "agents" / source.name).write_text(
            f"---\ndescription: {json.dumps(str(fields.get('description', source.stem)))}\n"
            f"role: {fields['role']}\ntools: Read, Write\nmodel: sonnet\neffort: low\n---\nDo the step.\n",
            encoding="utf-8",
        )
    return plugin


def criteria_answers() -> list[CriterionAnswer]:
    """Answer every architecture and technical-requirement criterion of the criteria file.

    Returns:
        One answer per criterion, each saying it does not apply.

    """
    criteria = load_criteria()
    return [
        {"criterion": entry.id, "status": CRITERION_NOT_APPLICABLE, "satisfiedAt": [], "reason": "The check."}
        for level in (LEVEL_ARCHITECTURE, LEVEL_TECHNICAL_REQUIREMENT)
        for entry in criteria.at_level(level)
    ]


def result_document(conclusion: Conclusion, *, failure_behaviours: Sequence[str] = ()) -> ArchitectureResult:
    """Build an architecture result that satisfies its schema.

    Returns:
        The result with every criterion answered and the review signals the scenario states.

    """
    return validate_architecture_result({
        "bead": BEAD,
        "conclusion": conclusion,
        "features": [],
        "newElements": [],
        "sharedCapabilities": [],
        "facts": [],
        "settledDisagreements": [],
        "criteria": criteria_answers(),
        "notesForSpecs": [],
        "unsettled": [],
        "reviewSignals": {
            "failureBehaviours": list(failure_behaviours),
            "newRuntimeResources": [],
            "newBillableResources": [],
            "changedBillableLimits": [],
            "choices": [],
            "newPatterns": [],
        },
        "costEvidence": [],
        "summary": "The check.",
    })


def review_document(findings: Sequence[ScopeFinding] = ()) -> ScopeReview:
    """Build a review that satisfies its schema.

    Returns:
        The review with the findings given and nothing else raised.

    """
    return validate_scope_review({
        "passed": [],
        "findings": list(findings),
        "dependsOnApproved": [],
        "alternativesRequested": [],
        "summary": "The check.",
    })


@dataclass
class ArchBench:
    """One scenario's Epic: its work directory, vault, matrix, services and stand-in sessions."""

    root: Path
    sessions: StandIns = field(default_factory=StandIns)
    counts: Counter[str] = field(default_factory=Counter)
    fail_once: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Make the vault, the matrix, the plugin and a session runner whose sessions are stand-ins."""
        self.vault: Path = make_vault(self.root)
        self.matrix: Path = self.root / "control" / "matrix.json"
        self.matrix.parent.mkdir(parents=True)
        make_matrix(self.matrix, self.vault)
        self.work: Path = self.root / ".claude" / "workflow-runs" / "artifacts" / BEAD
        self.work.mkdir(parents=True)
        self.path: Path = sj.journal_path(sj.journals_directory(self.work), BEAD)
        dispatch = dispatch_arguments()
        args: dict[str, JsonValue] = {
            dispatch.KEY_PRD: {dispatch.PRD_PATH: str(self.vault / PRD)},
            dispatch.KEY_ARCH_PATH: str(self.vault / ARCH),
            dispatch.KEY_BEADS_REPO_PATH: str(self.root / "control"),
            dispatch.KEY_OWNER: "check",
        }
        self.context: RunContext = RunContext(
            BEAD,
            dispatch.FLOW_PRD_TO_SPEC,
            args,
            self.work,
            "check-run",
            stage=ARCHITECTURE_PHASE,
        )
        self.agents: AgentRunner = AgentRunner(
            self.context,
            plugin=make_plugin(self.root),
            emit=EventWriter(io.StringIO()),
        )
        self.agents.processes = self.sessions
        self.tools: BenchTools = BenchTools(self.work / "evidence", self.vault)

    def environment(self) -> dict[str, str]:
        """Name the environment the scenario's steps read.

        Returns:
            The matrix file, the PRD folder and the project root of this scenario.

        """
        return {
            MATRIX_ENV: str(self.matrix),
            PRD_DIR_ENV: str(self.vault / SDLC),
            "SKILLSPOKE_ROOT": str(self.root),
        }

    def enter(self, key: str) -> None:
        """Count one stand-in session of an agent, and fail it when a failure is injected for it.

        Raises:
            RuntimeError: A failure was injected for ``key``; it is injected once.

        """
        self.counts[key] += 1
        if key in self.fail_once:
            self.fail_once.discard(key)
            message: str = f"injected failure in {key}"
            raise RuntimeError(message)

    def runner(self) -> JournalRunner:
        """Open the Epic's journal as one dispatch does.

        Returns:
            The runner of the journal.

        """
        plans: list[StepPlan] = outermost_steps()
        return open_journal(
            self.path.parent,
            BEAD,
            BEAD_TYPE_EPIC,
            PIPELINE_ELABORATION,
            plans,
            self.agents,
            self.tools,
        )

    def journal(self) -> Journal:
        """Read the journal as it stands.

        Returns:
            The journal.

        """
        return sj.read_journal(self.path)

    def steps(self, description: str) -> list[Step]:
        """Find the steps with one description, in walk order.

        Returns:
            The steps.

        """
        return [step for step in sj.steps_in_order(self.journal()) if step["description"] == description]

    def step(self, description: str) -> Step:
        """Find the one step with this description.

        Returns:
            The step.

        """
        found: list[Step] = self.steps(description)
        require(len(found) == 1, f"{len(found)} steps are described {description!r}")
        return found[0]

    def run_architecture(self) -> None:
        """Run the journal until the TRD step is done, or a step fails."""
        loop: JournalRunner = self.runner()
        while self.step("TRD")["status"] != "done":
            require(loop.run_next(), "the journal ran out of steps before the TRD step was done")
