"""The code-trust marker: what the build and deploy pipelines record when they build, deploy and merge.

Code no pipeline built is ``legacy``: a clue to how something was once solved, and never a
finding against the architecture. Three events, and nothing else, make code trusted:

- :func:`mark_built` when a Task's whole test suite passed and its commit landed on the Story
  branch: the Task's repository, the service made of that repository and the elements the Task
  names become ``built``. Nothing else in the repository changes.
- :func:`mark_deployed` when a Story's deploy to AWS dev was verified: everything the Story
  built, and the stacks deployed, become ``deployed``.
- :func:`mark_merged` when the Story's pull request merged: the trusted code is on the default
  branch.

No architecture session writes the marker. The driver records it through the ``record_*``
functions, which it loads from this file by path; ``atw-matrix`` runs the same code.
"""

import sys
from pathlib import Path
from typing import Final, NotRequired, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
from matrix_contract import (
    BASIS_BUILT_CORRECTION,
    CODE_BUILT,
    CODE_DEPLOYED,
    CODE_NONE,
    KIND_REPOSITORY,
    KIND_SERVICE,
    KIND_STACK,
    LIFECYCLE_EFFECTIVE,
    LINK_CONTAINS,
    LINK_DESCRIBED_BY,
    PLACED_KINDS,
    ROLE_BUILD_DRIVER,
    TASK_ELEMENTS_KEY,
    Code,
    CodeState,
    Kind,
    Link,
    Matrix,
    Node,
    NodeId,
    Role,
)
from matrixquery import resolve
from matrixreview import Approved, Remaining, approve_built_correction
from matrixstore import (
    DEFAULT_LOCK_WAIT,
    MatrixRefusedError,
    Stamp,
    make_id,
    matrix_path,
    name_index,
    name_key,
    require_role,
    timestamp,
    update_matrix,
)
from matrixsync import set_lifecycle, sync_documents, vault_root

COMMAND_BUILT: Final = "mark-built"
COMMAND_DEPLOYED: Final = "mark-deployed"
COMMAND_MERGED: Final = "mark-merged"
COMMAND_STORY_BUILT: Final = "story-built"
COMMAND_SYNC_DOCUMENTS: Final = "sync-documents"
COMMAND_APPROVE: Final = "approve"
BUILD_DRIVER_ROLE: Final[Role] = ROLE_BUILD_DRIVER
"""The role the build and deploy driver records the marker as."""
ELEMENTS_KEY: Final = TASK_ELEMENTS_KEY
"""The key under which a Task names the matrix ids of the elements it builds."""
TRUSTED: Final[frozenset[CodeState]] = frozenset({CODE_BUILT, CODE_DEPLOYED})
"""The states of code a pipeline built."""


class Built(TypedDict):
    """One Task whose tests passed and whose commit landed on its Story branch."""

    task: str
    story: str
    repository: str
    commit: str
    ref: str
    """The branch that holds the commit: the Story branch."""
    elements: list[str]
    """The ids, former ids or unique names of the elements the Task built; may be empty."""


class Deployed(TypedDict):
    """One Story whose deploy to AWS dev was verified."""

    story: str
    repository: str
    commit: str
    stacks: list[str]
    """The names of the stacks that were verified."""


class BuiltCorrection(TypedDict):
    """One reviewed correction of the effective architecture to what a Story built."""

    epic: str
    story: str
    arch: str
    """The architecture root inside the vault."""
    files: list[str]
    """The corrected documents: absolute paths, or paths relative to the architecture root."""
    steps: list[str]
    """The journal step ids of the reviews that passed."""


class CorrectionRecorded(TypedDict):
    """What recording a reviewed correction did."""

    command: str
    at: str
    approved: list[NodeId]
    headings: int
    """How many headings took their present hash as the approved one."""
    remaining: list[Remaining]
    promoted: list[str]
    """The documents set to effective in the vault, relative to the vault root."""


class Merged(TypedDict):
    """One Story whose pull request merged."""

    story: str
    ref: str
    """The branch the code is on now: the repository's default branch."""
    pr: NotRequired[str]


class RowMark(TypedDict):
    """One row whose code marker a call changed."""

    id: NodeId
    was: CodeState
    now: CodeState


class CodeMarked(TypedDict):
    """What marking the code did: also what the three ``mark-*`` sub-commands print."""

    command: str
    at: str
    rows: list[RowMark]
    unknown: list[str]
    """The stack names given that are no stack row, so nothing was marked for them."""


class Described(TypedDict):
    """One arc42 heading that describes a row."""

    document: str
    """The document's path relative to the vault root."""
    heading: NotRequired[str]
    """The heading in that document; absent when the whole document describes the row."""


class BuiltRow(TypedDict):
    """One row whose trusted code a Story built."""

    id: NodeId
    kind: Kind
    name: str
    code: Code
    describedBy: list[Described]


class StoryBuilt(TypedDict):
    """What a Story built that is trusted: also what the ``story-built`` sub-command prints."""

    story: str
    repositories: list[str]
    """The names of the repository rows among ``rows``; empty when the Story has no trusted code."""
    rows: list[BuiltRow]


def _needed(value: str, what: str) -> str:
    """Require one piece of text a marker cannot be recorded without.

    Returns:
        The text, stripped.

    Raises:
        MatrixRefusedError: The text is empty.

    """
    if not value.strip():
        message: str = f"the code marker needs {what}"
        raise MatrixRefusedError(message)
    return value.strip()


def _held(node: Node) -> Code:
    """Read the code marker a row holds.

    Returns:
        The marker; one that says no code is known for a row that has none.

    """
    none: Code = {"state": CODE_NONE}
    return node.get("code", none)


def _set(node: Node, code: Code, stamp: Stamp, marked: CodeMarked) -> None:
    """Give a row its code marker, when it differs from the one it holds.

    The moment is not part of the comparison, so recording the same event twice changes nothing.
    """
    held: Code = _held(node)
    if {**held, "at": ""} == {**code, "at": ""}:
        return
    marked["rows"].append({"id": node["id"], "was": held["state"], "now": code["state"]})
    node["code"] = code
    node["changed"] = stamp.change()


def _services(matrix: Matrix, repository: NodeId) -> list[Node]:
    """Find the services made of a repository.

    Returns:
        The service rows that contain the repository, in id order.

    """
    return [
        matrix["nodes"][key]
        for key in sorted(matrix["nodes"])
        if matrix["nodes"][key]["kind"] == KIND_SERVICE
        and any(link["type"] == LINK_CONTAINS and link["to"] == repository for link in matrix["nodes"][key]["links"])
    ]


def _built_elements(matrix: Matrix, built: Built) -> list[Node]:
    """Find the element rows a Task names.

    Returns:
        The rows, in the order named.

    Raises:
        MatrixRefusedError: A name is no row, or is a row that does not live in the Task's
            repository.

    """
    rows: list[Node] = []
    named: str
    for named in built["elements"]:
        node: Node = matrix["nodes"][resolve(matrix, named)]
        if node["kind"] not in PLACED_KINDS or name_key(node.get("repository") or "") != name_key(built["repository"]):
            message: str = f"{node['id']} does not live in the repository {built['repository']}"
            raise MatrixRefusedError(message)
        rows.append(node)
    return rows


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def mark_built(matrix: Matrix, built: Built, stamp: Stamp) -> CodeMarked:
    """Record that a Task built code the pipeline trusts.

    The repository row, the service made of the repository and each element the Task names take
    the state ``built`` with the Task, the Story, the commit and the branch. A row that was
    deployed is built again: the new commit is not deployed yet, and the row keeps what it
    recorded of the earlier deploy. No other row of the repository changes.

    Args:
        matrix: The matrix, changed in place.
        built: The Task, its Story, its repository, the commit, the branch and the elements built.
        stamp: The moment and the maker to record on each changed row.

    Returns:
        The rows whose marker changed.

    Raises:
        MatrixRefusedError: The Task, the repository, the commit or the branch is not given, the
            repository is not a row, or an element named is not a row of that repository.

    """
    repository: NodeId = make_id(KIND_REPOSITORY, _needed(built["repository"], "the repository"))
    if repository not in matrix["nodes"]:
        message: str = f"the matrix has no repository {built['repository']!r}"
        raise MatrixRefusedError(message)
    marked: CodeMarked = {"command": COMMAND_BUILT, "at": stamp.at, "rows": [], "unknown": []}
    node: Node
    for node in (matrix["nodes"][repository], *_services(matrix, repository), *_built_elements(matrix, built)):
        code: Code = {
            **_held(node),
            "state": CODE_BUILT,
            "ref": _needed(built["ref"], "the branch"),
            "commit": _needed(built["commit"], "the commit"),
            "task": _needed(built["task"], "the Task"),
            "at": stamp.at,
        }
        if built["story"].strip():
            code["story"] = built["story"].strip()
        _set(node, code, stamp, marked)
    return marked


def _stacks(matrix: Matrix, deployed: Deployed, marked: CodeMarked) -> list[Node]:
    """Find the stack rows a deploy names.

    Returns:
        The rows of the named stacks: the stack of that name in the Story's repository, or the
        one stack of that name when no repository is given. A name that finds no single row is
        added to ``unknown`` and nothing is marked for it.

    """
    by_name: dict[str, list[NodeId]] = name_index(matrix, [KIND_STACK])
    rows: list[Node] = []
    name: str
    for name in deployed["stacks"]:
        placed: NodeId | None = (
            make_id(KIND_STACK, deployed["repository"], name)
            if deployed["repository"].strip() and name.strip()
            else None
        )
        candidates: list[NodeId] = [placed] if placed in matrix["nodes"] and placed is not None else []
        if not candidates and not deployed["repository"].strip():
            candidates = by_name.get(name_key(name), [])
        if len(candidates) == 1:
            rows.append(matrix["nodes"][candidates[0]])
        else:
            marked["unknown"].append(name)
    return rows


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def mark_deployed(matrix: Matrix, deployed: Deployed, stamp: Stamp) -> CodeMarked:
    """Record that a Story's deploy to AWS dev was verified.

    Every row the Story built, and each stack named, takes the state ``deployed`` with the
    commit deployed and the stacks verified. A stack name that is no stack row is reported and
    marks nothing; the deploy stands whatever the matrix can record of it.

    Args:
        matrix: The matrix, changed in place.
        deployed: The Story, its repository, the commit deployed and the stacks verified.
        stamp: The moment and the maker to record on each changed row.

    Returns:
        The rows whose marker changed, and the stack names that are no row. A deploy that names
        no Story or no commit is refused with ``MatrixRefusedError``.

    """
    story: str = _needed(deployed["story"], "the Story")
    commit: str = _needed(deployed["commit"], "the commit")
    marked: CodeMarked = {"command": COMMAND_DEPLOYED, "at": stamp.at, "rows": [], "unknown": []}
    targets: dict[NodeId, Node] = {node["id"]: node for node in _stacks(matrix, deployed, marked)}
    node: Node
    for node in matrix["nodes"].values():
        if "code" in node and node["code"].get("story") == story and node["code"]["state"] in TRUSTED:
            targets.setdefault(node["id"], node)
    key: NodeId
    for key in sorted(targets):
        code: Code = {
            **_held(targets[key]),
            "state": CODE_DEPLOYED,
            "story": story,
            "deployedCommit": commit,
            "stacks": sorted({name.strip() for name in deployed["stacks"] if name.strip()}),
            "at": stamp.at,
        }
        _set(targets[key], code, stamp, marked)
    return marked


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def mark_merged(matrix: Matrix, merged: Merged, stamp: Stamp) -> CodeMarked:
    """Record that a Story's pull request merged, so its trusted code is on the default branch.

    Every row the Story built or deployed takes the default branch as where its code is, and
    the pull request when one is given. No state changes.

    Args:
        matrix: The matrix, changed in place.
        merged: The Story, the default branch and the pull request.
        stamp: The moment and the maker to record on each changed row.

    Returns:
        The rows whose marker changed. A merge that names no Story or no branch is refused with
        ``MatrixRefusedError``.

    """
    story: str = _needed(merged["story"], "the Story")
    ref: str = _needed(merged["ref"], "the default branch")
    marked: CodeMarked = {"command": COMMAND_MERGED, "at": stamp.at, "rows": [], "unknown": []}
    key: NodeId
    for key in sorted(matrix["nodes"]):
        node: Node = matrix["nodes"][key]
        if "code" not in node or node["code"].get("story") != story or node["code"]["state"] not in TRUSTED:
            continue
        code: Code = {**node["code"], "ref": ref, "at": stamp.at}
        if merged.get("pr", "").strip():
            code["pr"] = merged.get("pr", "").strip()
        _set(node, code, stamp, marked)
    return marked


def _described(matrix: Matrix, node: Node) -> list[Described]:
    """List the arc42 headings a row's ``describedBy`` links name.

    Returns:
        One entry per link, in the row's link order: the document's path and the link's heading.

    """
    described: list[Described] = []
    link: Link
    for link in node["links"]:
        if link["type"] != LINK_DESCRIBED_BY or link["to"] not in matrix["nodes"]:
            continue
        document: Node = matrix["nodes"][link["to"]]
        entry: Described = {"document": document.get("path") or document["name"]}
        if "heading" in link:
            entry["heading"] = link["heading"]
        described.append(entry)
    return described


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def story_built(matrix: Matrix, story: str) -> StoryBuilt:
    """List the rows whose trusted code a Story built, each with the headings that describe it.

    Args:
        matrix: The matrix.
        story: The Story's id.

    Returns:
        The rows whose code marker names the Story and is ``built`` or ``deployed``, in id order,
        and the names of the repositories among them. A call that names no Story is refused with
        ``MatrixRefusedError``.

    """
    wanted: str = _needed(story, "the Story")
    built: StoryBuilt = {"story": wanted, "repositories": [], "rows": []}
    key: NodeId
    for key in sorted(matrix["nodes"]):
        node: Node = matrix["nodes"][key]
        if "code" not in node or node["code"].get("story") != wanted or node["code"]["state"] not in TRUSTED:
            continue
        if node["kind"] == KIND_REPOSITORY:
            built["repositories"].append(node["name"])
        built["rows"].append({
            "id": node["id"],
            "kind": node["kind"],
            "name": node["name"],
            "code": node["code"],
            "describedBy": _described(matrix, node),
        })
    return built


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def matrix_file(environ: dict[str, str]) -> Path:
    """Name the matrix file the driver records in.

    Args:
        environ: The driver's environment.

    Returns:
        The file the matrix variable names, else the matrix of the control repository the
        environment names. An environment that names neither raises ``MatrixError``.

    """
    return matrix_path(None, environ)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_built(path: Path, built: Built, role: Role) -> CodeMarked:
    """Record a built Task in a matrix file, as one locked change.

    A role that may not record it, a matrix that is missing or does not conform, or a Task the
    matrix refuses raises ``MatrixError``; the file is then left as it was.

    Args:
        path: The matrix file.
        built: The Task and what it built.
        role: Who records it.

    Returns:
        The rows whose marker changed.

    """
    require_role(COMMAND_BUILT, role)
    stamp: Stamp = Stamp(timestamp(), f"{built['task'].strip() or role} {COMMAND_BUILT}")

    def change(matrix: Matrix) -> CodeMarked:
        return mark_built(matrix, built, stamp)

    return update_matrix(path, change, wait=DEFAULT_LOCK_WAIT)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_deployed(path: Path, deployed: Deployed, role: Role) -> CodeMarked:
    """Record a verified Story deploy in a matrix file, as one locked change.

    A role that may not record it, a matrix that is missing or does not conform, or a deploy the
    matrix refuses raises ``MatrixError``; the file is then left as it was.

    Args:
        path: The matrix file.
        deployed: The Story and what was deployed.
        role: Who records it.

    Returns:
        The rows whose marker changed, and the stack names that are no row.

    """
    require_role(COMMAND_DEPLOYED, role)
    stamp: Stamp = Stamp(timestamp(), f"{deployed['story'].strip() or role} {COMMAND_DEPLOYED}")

    def change(matrix: Matrix) -> CodeMarked:
        return mark_deployed(matrix, deployed, stamp)

    return update_matrix(path, change, wait=DEFAULT_LOCK_WAIT)


def _vault_paths(arch: Path, vault: Path, files: list[str]) -> list[str]:
    """Name corrected documents the way the matrix does: relative to the vault root.

    Returns:
        Each file's path relative to the vault root, once; a file given relative is taken as
        relative to the architecture root.

    Raises:
        MatrixRefusedError: A file is outside the vault.

    """
    paths: dict[str, None] = {}
    name: str
    for name in files:
        given: Path = Path(name)
        located: Path = (given if given.is_absolute() else arch / given).resolve()
        try:
            paths[located.relative_to(vault).as_posix()] = None
        except ValueError as error:
            message: str = f"the corrected document {name} is outside the vault {vault}"
            raise MatrixRefusedError(message) from error
    return list(paths)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_built_correction(path: Path, correction: BuiltCorrection, role: Role) -> CorrectionRecorded:
    """Record a reviewed correction of the effective architecture in a matrix file, as one locked change.

    The document rows are brought up to date with the vault, then the corrected documents are
    approved as they are now with the built-correction basis, the Epic and the review steps; a
    corrected document whose front matter does not say effective is set to effective in the
    vault. A role that may not record it, a matrix that is missing or does not conform, a vault
    that cannot be read or written, or a correction the matrix refuses raises ``MatrixError``;
    the matrix file is then left as it was.

    Args:
        path: The matrix file.
        correction: The Story, its Epic, the corrected documents and the reviews that passed.
        role: Who records it.

    Returns:
        The document rows approved, how many headings took a new approved hash, what was not
        approved and why, and the documents set to effective.

    """
    require_role(COMMAND_SYNC_DOCUMENTS, role)
    require_role(COMMAND_APPROVE, role)
    arch: Path = Path(correction["arch"]).expanduser().resolve()
    vault: Path = vault_root(arch).resolve()
    documents: list[str] = _vault_paths(arch, vault, correction["files"])
    stamp: Stamp = Stamp(timestamp(), f"{correction['story'].strip() or role} {BASIS_BUILT_CORRECTION}")

    def change(matrix: Matrix) -> CorrectionRecorded:
        sync_documents(matrix, arch, stamp)
        approved: Approved = approve_built_correction(
            matrix,
            correction["epic"],
            documents,
            correction["steps"],
            stamp,
        )
        promoted: str
        for promoted in approved["promoted"]:
            set_lifecycle(vault, promoted, LIFECYCLE_EFFECTIVE)
        return {
            "command": BASIS_BUILT_CORRECTION,
            "at": stamp.at,
            "approved": approved["approved"],
            "headings": len(approved["headings"]),
            "remaining": approved["remaining"],
            "promoted": approved["promoted"],
        }

    return update_matrix(path, change, wait=DEFAULT_LOCK_WAIT)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def record_merged(path: Path, merged: Merged, role: Role) -> CodeMarked:
    """Record a merged Story in a matrix file, as one locked change.

    A role that may not record it, a matrix that is missing or does not conform, or a merge the
    matrix refuses raises ``MatrixError``; the file is then left as it was.

    Args:
        path: The matrix file.
        merged: The Story and where its code is now.
        role: Who records it.

    Returns:
        The rows whose marker changed.

    """
    require_role(COMMAND_MERGED, role)
    stamp: Stamp = Stamp(timestamp(), f"{merged['story'].strip() or role} {COMMAND_MERGED}")

    def change(matrix: Matrix) -> CodeMarked:
        return mark_merged(matrix, merged, stamp)

    return update_matrix(path, change, wait=DEFAULT_LOCK_WAIT)
