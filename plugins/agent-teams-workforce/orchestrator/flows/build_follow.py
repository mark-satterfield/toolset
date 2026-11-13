"""The build corrects the matrix from the code: ``build:matrix-follow``.

The matrix is a best guess. Once a Task's code is committed (``build:commit`` adds this step), the
step hands the Task's ids, its Story worktree and the files its own commits changed to
:func:`matrixfollow.follow_code` under the matrix's lock, so the ``supportedBy`` relationships of
the features the Task builds match what the code uses. It records what it changed and what it left
as the ``matrixFollow`` value. Divergence is never a failure here; only a matrix write or read that
cannot be made fails the step, as a tooling fault.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from matrix_contract import EntryId, MatrixError
from matrixfollow import FollowResult, FollowScope, follow_code
from matrixstore import update_matrix
from matrixtasks import TaskBead, read_tasks
from typeguard import check_type

from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object
from orchestrator.core.journal_steps import Completion, StepRun, value_artifact
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import matrix_file
from orchestrator.flows.build_state import workspace_of
from orchestrator.flows.elaboration_files import control_repository

if TYPE_CHECKING:
    from matrixstore import Matrix

    from orchestrator.flows.build_workspace import Workspace

STAGE: Final = "build:matrix-follow"
RECORD: Final = "matrixFollow"
ELEMENTS: Final = "matrix_elements"


def _own_commit_pattern(bead: str) -> str:
    """Match the two commit messages the build writes for one Task.

    Returns:
        An extended regular expression for ``feat(build): checkpoint <bead>`` and
        ``feat(build): <bead> <title>``.

    """
    literal: str = re.sub(r"([.()\[\]^$*+?{}|\\])", r"[\1]", bead)
    return rf"^feat\(build\): (checkpoint )?{literal}( |$)"


def _own_files(run: StepRun, workspace: Workspace) -> tuple[str, ...]:
    """List the files the Task's own commits changed.

    Returns:
        Each path once, relative to the worktree, in the order git first names it.

    """
    printed: str = run.tools.git(
        workspace.tree,
        ["log", "-E", f"--grep={_own_commit_pattern(run.bead)}", "--format=", "--name-only", "HEAD"],
        stage=STAGE,
    ).stdout
    return tuple(dict.fromkeys(line.strip() for line in printed.splitlines() if line.strip()))


def follow(run: StepRun) -> Completion:
    """Correct the matrix from the Task's committed code and record what changed.

    Args:
        run: The ``build:matrix-follow`` step.

    Returns:
        The ``matrixFollow`` value: the relationships removed, narrowed and linked, the divergence
        left as it was with its reason, and the ids the matrix holds no entry for.

    Raises:
        StepError: The matrix or the worktree could not be read, or the write could not be made.

    """
    bead: dict[str, JsonValue] = json_object(run.context.args["bead"])
    ids: tuple[EntryId, ...] = tuple(EntryId(entry_id) for entry_id in check_type(bead.get(ELEMENTS, []), list[str]))
    workspace: Workspace = workspace_of(run)
    tasks: list[TaskBead] = run.tools.portfolio_read(STAGE, read_tasks, control_repository())
    scope: FollowScope = FollowScope(run.bead, ids, workspace.tree, _own_files(run, workspace), tuple(tasks))

    def change(matrix: Matrix) -> FollowResult:
        return follow_code(matrix, scope)

    try:
        result: FollowResult = update_matrix(matrix_file(), change)
    except MatrixError as error:
        raise StepError(STAGE, OTHER_CAUSE, (f"the matrix could not be corrected from the code: {error}",)) from error
    return Completion(artifacts=(value_artifact(RECORD, json_object(result)),))
