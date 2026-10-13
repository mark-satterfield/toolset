"""The matrix file: where it is, how it is locked, read and written, and the rules a schema cannot state.

The matrix is one JSON file (``ops/sdlc-automation/matrix.json`` in the control repository unless
the caller or the environment names another). Its shape is defined once, in
``skills/artifact-handoff/schemas/matrix.schema.json``; every type, value and schema check used
here comes from ``matrix_contract``, the module generated from that schema.

This module and the modules beside it that build on it (``matrixquery``, ``matrixsync``,
``matrixcarry``, and the command ``matrix``) are the only readers and writers of a matrix file.
Every change is one read-modify-write under an exclusive lock (:func:`update_matrix`), written to
a temporary file in the matrix's directory and moved into place, and every document read or
written is validated. A read takes no lock: a write replaces the file in one move.
"""

import fcntl
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from driver_surface_types import CONTROL_REPO_ENV
from matrix_contract import (
    APPROVAL_APPROVED,
    APPROVAL_CHANGED_SINCE_APPROVAL,
    APPROVAL_UNVERIFIED,
    COMMAND_RULES,
    DEFAULT_MATRIX_PARTS,
    ELEMENT_KINDS,
    FEATURE_SUPPORTING,
    KIND_DOCUMENT,
    KIND_FACT,
    KIND_FEATURE,
    KIND_PRD,
    KIND_REPOSITORY,
    KIND_STACK,
    KINDS,
    LINK_RULES,
    LINK_USES,
    LOCK_DIRECTORY,
    LOCK_SUFFIX,
    MATRIX_ENV,
    NODE_ID_PATTERN,
    OPERATOR_ROLE,
    PLACED_KINDS,
    ROLE_ENV,
    ROLES,
    VERSION,
    Anchor,
    Approval,
    ApprovalState,
    Change,
    HeadingHash,
    Kind,
    Link,
    Matrix,
    MatrixError,
    Node,
    NodeId,
    Role,
    validate_matrix,
    validate_node,
)

TIMESTAMP_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_LOCK_WAIT: Final = 60.0
"""Seconds a change waits for another process's change to the same matrix to finish."""
LOCK_POLL: Final = 0.05
FILE_MODE: Final = 0o644
"""The mode of a matrix file: it is committed to the control repository and read by every session."""
CONTROL_REPO_FALLBACK_ENV: Final = "SKILLSPOKE_CC"
"""The project's own variable for the control repository, read when the driver's is not set."""
ID_SEPARATOR: Final = ":"
PART_SEPARATOR: Final = "/"
CHANGED_BY_SYNC: Final = "sync"
CHANGED_BY_CARRY_OVER: Final = "carry-over"


class MatrixRefusedError(MatrixError):
    """The matrix refuses the request in the state it is in, or for the role that asked."""


class MatrixLockTimeoutError(MatrixError):
    """Another process held the matrix's lock for the whole wait."""


@dataclass(frozen=True, slots=True)
class Stamp:
    """When a change is made and what makes it."""

    at: str
    """The date-time of the change."""
    by: str
    """A bead id and journal step id, ``carry-over`` or ``sync``. Never a person's name."""

    def __post_init__(self) -> None:
        """Refuse a stamp that lacks its moment or its maker.

        Raises:
            ValueError: ``at`` or ``by`` is empty.

        """
        if not self.at or not self.by:
            message: str = "a change needs the moment it is made and what makes it"
            raise ValueError(message)

    def change(self) -> Change:
        """Render the stamp as the record a row keeps of its last change.

        Returns:
            The ``changed`` value of a row.

        """
        return {"at": self.at, "by": self.by}


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def timestamp() -> str:
    """Return the present moment as a matrix date-time.

    Returns:
        The UTC time as ``YYYY-MM-DDTHH:MM:SSZ``.

    """
    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def name_key(name: str) -> str:
    """Reduce a name to the form names are compared and ids are built in.

    Args:
        name: A name as a document or a caller writes it.

    Returns:
        The name with runs of white space collapsed to one space, case-folded.

    Raises:
        TypeError: ``name`` is not a string.

    """
    if not isinstance(name, str):
        message: str = "a name must be a string"
        raise TypeError(message)
    return " ".join(name.split()).casefold()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def make_id(kind: Kind, *parts: str) -> NodeId:
    """Build a row id from the row's kind and the parts that identify it within the kind.

    Args:
        kind: The row's kind.
        parts: The identifying parts, outermost first (a repository, then a stack, then a name);
            each is reduced with :func:`name_key`.

    Returns:
        ``<kind>:<part>/<part>...``.

    Raises:
        ValueError: ``kind`` is not a row kind, or no part is left after reduction.

    """
    if kind not in KINDS:
        message: str = f"{kind!r} is not a row kind"
        raise ValueError(message)
    rest: str = PART_SEPARATOR.join(name_key(part) for part in parts)
    if not rest.strip(PART_SEPARATOR):
        message = f"a {kind} row id needs at least one nonempty part"
        raise ValueError(message)
    return NodeId(f"{kind}{ID_SEPARATOR}{rest}")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def as_node_id(text: str) -> NodeId:
    """Accept a string as a row id when it has the form of one.

    Args:
        text: The candidate id.

    Returns:
        The same text, typed.

    Raises:
        MatrixError: The text does not start with a row kind and a colon.

    """
    if not isinstance(text, str) or NODE_ID_PATTERN.search(text) is None:
        message: str = f"{text!r} is not a row id: it must match {NODE_ID_PATTERN.pattern}"
        raise MatrixError(message)
    return NodeId(text)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def kind_of(node_id: NodeId) -> Kind:
    """Read the kind a row id states.

    Args:
        node_id: A row id.

    Returns:
        The kind before the colon.

    Raises:
        MatrixError: The id does not start with a row kind.

    """
    prefix: str = node_id.partition(ID_SEPARATOR)[0]
    kind: Kind
    for kind in KINDS:
        if kind == prefix:
            return kind
    message: str = f"the row id {node_id!r} does not start with a row kind"
    raise MatrixError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def empty_matrix(moment: str) -> Matrix:
    """Build a matrix with no rows.

    Args:
        moment: The date-time to record as the creation of the file.

    Returns:
        A matrix that satisfies the schema and holds nothing.

    Raises:
        ValueError: ``moment`` is empty.

    """
    if not moment:
        message: str = "an empty matrix needs the moment it is created"
        raise ValueError(message)
    return {
        "version": VERSION,
        "documentsSyncedAt": {"vaultCommit": "", "at": moment, "dirtyPaths": []},
        "resourceTypes": [],
        "nodes": {},
    }


def _same_anchor(node: Node, document: str, heading: str) -> bool:
    """Tell whether a row's home is one heading of one document.

    Returns:
        True when the row has that home.

    """
    home: Anchor | None = node.get("home")
    return home is not None and home["document"] == document and home["heading"] == heading


def _link_problems(matrix: Matrix, node: Node) -> list[str]:
    """Check every link of one row against the rows it names and the link rules.

    Returns:
        One sentence per link that names no row, joins kinds its type may not join, or relies on
        a ``provides`` entry its target does not have.

    """
    problems: list[str] = []
    link: Link
    for link in node["links"]:
        target: Node | None = matrix["nodes"].get(link["to"])
        if target is None:
            problems.append(f"{node['id']}: the {link['type']} link names {link['to']}, which is not a row")
            continue
        if (
            node["kind"] not in LINK_RULES[link["type"]].sources
            or target["kind"] not in LINK_RULES[link["type"]].targets
        ):
            problems.append(
                f"{node['id']}: a {link['type']} link may not join a {node['kind']} to {link['to']}",
            )
        if link["type"] == LINK_USES:
            offered: set[str] = {entry["id"] for entry in target.get("provides", [])}
            problems.extend(
                f"{node['id']}: the uses link to {link['to']} relies on {entry!r}, which that row does not provide"
                for entry in link.get("provides", [])
                if entry not in offered
            )
    return problems


def _placement_problems(matrix: Matrix, node: Node) -> list[str]:
    """Check that the repository, stack and resource type one row names are known.

    Returns:
        One sentence per repository or stack that is not a row, and per resource type that is not
        in the controlled list.

    """
    problems: list[str] = []
    if node["kind"] not in PLACED_KINDS:
        return problems
    repository: str | None = node.get("repository")
    if repository is None or make_id(KIND_REPOSITORY, repository) not in matrix["nodes"]:
        problems.append(f"{node['id']}: the repository {repository!r} is not a row")
        return problems
    stack: str | None = node.get("stack")
    if (
        stack is not None
        and node["kind"] != KIND_STACK
        and make_id(KIND_STACK, repository, stack) not in matrix["nodes"]
    ):
        problems.append(f"{node['id']}: the stack {stack!r} of {repository} is not a row")
    resource_type: str | None = node.get("resourceType")
    if node["kind"] in ELEMENT_KINDS and resource_type is not None and resource_type not in matrix["resourceTypes"]:
        problems.append(f"{node['id']}: the resource type {resource_type!r} is not in the controlled list")
    return problems


def _home_problems(matrix: Matrix, node: Node) -> list[str]:
    """Check that the home of an approved fact or supporting feature is in a document the matrix knows.

    A row that is not approved may name a home that is still to be written: the architect records
    the fact before the document exists. :func:`heading_problems` reports it until it does, and
    nothing is approved without it.

    Returns:
        One sentence when the row is approved and its home document is not a row.

    """
    home: Anchor | None = node.get("home")
    approved: bool = "approval" in node and node["approval"]["state"] == APPROVAL_APPROVED
    if home is None or not approved or make_id(KIND_DOCUMENT, home["document"]) in matrix["nodes"]:
        return []
    return [f"{node['id']}: the home document {home['document']!r} is not a row"]


def _standing_problems(node: Node) -> list[str]:
    """Check that a disagreement names at most one statement that stands.

    Returns:
        One sentence when more than one statement of the row is marked as standing.

    """
    standing: int = sum(1 for statement in node.get("statements", []) if statement.get("stands") is True)
    return [f"{node['id']}: {standing} statements are marked as standing"] if standing > 1 else []


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def heading_problems(matrix: Matrix) -> list[str]:
    """Find every home whose heading its document does not have.

    A document that loses a heading is something a read of the vault must be able to record, so
    this is not a rule a write is refused for; ``check`` reports it, and the row whose home it
    was is changed since approval until its home is corrected.

    Args:
        matrix: A matrix that satisfies the schema.

    Returns:
        One sentence per fact or supporting feature whose home document is not a row yet, or is
        a row that has no such heading now.

    """
    problems: list[str] = []
    node: Node
    for node in matrix["nodes"].values():
        home: Anchor | None = node.get("home")
        if home is None:
            continue
        document: Node | None = matrix["nodes"].get(make_id(KIND_DOCUMENT, home["document"]))
        if document is None:
            problems.append(f"{node['id']}: the home document {home['document']!r} is not a row yet")
            continue
        heading: HeadingHash | None = document.get("headings", {}).get(home["heading"])
        if heading is None or not heading["hash"]:
            problems.append(f"{node['id']}: {home['document']} has no heading {home['heading']!r} now")
    return problems


def _fact_key(node: Node) -> tuple[str, str, str]:
    """Name what a fact states and where, for the one-home rule.

    Returns:
        The home document, the home heading and the fact's subject (its statement when it names none).

    """
    home: Anchor | None = node.get("home")
    subject: str = name_key(node.get("subject") or node.get("statement", ""))
    return ("", "", subject) if home is None else (home["document"], home["heading"], subject)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def consistency_problems(matrix: Matrix) -> list[str]:
    """Check the rules of the matrix that its JSON Schema cannot state.

    Args:
        matrix: A matrix that satisfies the schema.

    Returns:
        One sentence per row filed under an id that is not its own or whose id does not start
        with its kind; per link that names no row, joins kinds its type may not join or relies on
        a missing ``provides`` entry; per repository, stack or resource type that is not known;
        per home whose document is not a row; per fact that shares its home and subject with
        another; per supporting feature that states what it provides without a home; and per
        Epic that has two PRD rows. Empty when the matrix is consistent.

    """
    problems: list[str] = []
    facts: dict[tuple[str, str, str], NodeId] = {}
    beads: dict[str, NodeId] = {}
    key: NodeId
    node: Node
    for key, node in matrix["nodes"].items():
        if node["id"] != key:
            problems.append(f"{key}: the row filed under this id says its id is {node['id']}")
        if kind_of(key) != node["kind"]:
            problems.append(f"{key}: the id does not start with the row's kind, {node['kind']}")
        problems.extend(_link_problems(matrix, node))
        problems.extend(_placement_problems(matrix, node))
        problems.extend(_home_problems(matrix, node))
        problems.extend(_standing_problems(node))
        if node["kind"] == KIND_FACT:
            first: NodeId = facts.setdefault(_fact_key(node), key)
            if first != key:
                problems.append(f"{key}: the fact {first} already states the same subject at the same home")
        if node["kind"] == KIND_PRD:
            earlier: NodeId = beads.setdefault(node.get("bead", ""), key)
            if earlier != key:
                problems.append(f"{key}: the Epic {node.get('bead')} already has the PRD row {earlier}")
        if node["kind"] == KIND_FEATURE and node.get("featureType") == FEATURE_SUPPORTING and "home" not in node:
            problems.extend(
                f"{key}: states what it provides ({entry['id']}) but has no home" for entry in node.get("provides", [])
            )
    return problems


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def checked_matrix(matrix: Matrix, where: str = "matrix") -> Matrix:
    """Require a matrix to satisfy the schema and the rules the schema cannot state.

    Args:
        matrix: The matrix.
        where: What to call the matrix in the error.

    Returns:
        The matrix.

    Raises:
        MatrixError: The matrix breaks one of the rules. A matrix that does not satisfy the
            schema raises it from ``validate_matrix``.

    """
    validate_matrix(matrix, where)
    problems: list[str] = consistency_problems(matrix)
    if problems:
        message: str = f"{where} is not consistent ({len(problems)} problems): " + "; ".join(problems[:20])
        raise MatrixError(message)
    return matrix


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def heading_state(document: Node, heading: str, current: ApprovalState) -> ApprovalState:
    """Work out the approval state of something whose home is one heading of a document.

    An approved thing whose heading no longer matches the hash recorded at approval becomes
    changed since approval, and returns to approved when the heading matches again. Any other
    state is kept.

    Args:
        document: The document row.
        heading: The heading within it.
        current: The state held now.

    Returns:
        The state to hold.

    """
    entry: HeadingHash | None = document.get("headings", {}).get(heading)
    matches: bool = entry is not None and bool(entry["hash"]) and entry["hash"] == entry["approvedHash"]
    if current == APPROVAL_APPROVED and not matches:
        return APPROVAL_CHANGED_SINCE_APPROVAL
    if current == APPROVAL_CHANGED_SINCE_APPROVAL and matches:
        return APPROVAL_APPROVED
    return current


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def unapprove(node: Node, bead: str, stamp: Stamp) -> None:
    """Record that a row was changed, so it is not approved until it is reviewed again.

    The row's ``changed`` is set. A row that carries the approval marker becomes unverified and
    names the Epic that changed it, which is how that Epic's review finds it.

    Args:
        node: The row, changed in place.
        bead: The Epic that made the change; empty when no Epic did.
        stamp: The moment and the maker of the change.

    """
    node["changed"] = stamp.change()
    if "approval" not in node:
        return
    approval: Approval = {"state": APPROVAL_UNVERIFIED}
    if bead:
        approval["bead"] = bead
    node["approval"] = approval


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def owner_of(node: Node) -> str:
    """Name the Epic that holds a row while it is not approved.

    Args:
        node: The row.

    Returns:
        The Epic its approval marker names, or an empty string when the row has no marker, is
        approved, or was recorded by no Epic.

    """
    if "approval" not in node or node["approval"]["state"] == APPROVAL_APPROVED:
        return ""
    return node["approval"].get("bead", "")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def name_index(matrix: Matrix, kinds: Sequence[Kind]) -> dict[str, list[NodeId]]:
    """Index rows of the given kinds by every name they answer to.

    Args:
        matrix: The matrix.
        kinds: The kinds of row to index.

    Returns:
        Each reduced name and alias, and the ids of the rows that carry it, in id order.

    """
    index: dict[str, list[NodeId]] = {}
    key: NodeId
    for key in sorted(matrix["nodes"]):
        node: Node = matrix["nodes"][key]
        if node["kind"] not in kinds:
            continue
        names: set[str] = {name_key(node["name"]), *(name_key(alias) for alias in node.get("aliases", []))}
        name: str
        for name in names:
            index.setdefault(name, []).append(key)
    return index


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def role_of(environ: Mapping[str, str]) -> Role:
    """Read who is running the command from the environment.

    Args:
        environ: The process environment.

    Returns:
        The role the launcher set, or the operator role when it set none.

    Raises:
        MatrixRefusedError: The variable holds something that is not a role.

    """
    stated: str = environ.get(ROLE_ENV, "").strip()
    if not stated:
        return OPERATOR_ROLE
    role: Role
    for role in ROLES:
        if role == stated:
            return role
    message: str = f"{ROLE_ENV} is {stated!r}, which is not one of {', '.join(ROLES)}"
    raise MatrixRefusedError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def require_role(command: str, role: Role) -> None:
    """Refuse a sub-command the role may not run.

    Args:
        command: The sub-command.
        role: Who is running it.

    Raises:
        MatrixRefusedError: The schema's command table does not name the command, or does not
            allow the role to run it.

    """
    if command not in COMMAND_RULES:
        message: str = f"{command!r} is not a command of the matrix"
        raise MatrixRefusedError(message)
    if role not in COMMAND_RULES[command].roles:
        allowed: str = ", ".join(sorted(COMMAND_RULES[command].roles))
        message = f"the role {role} may not run {command}; it is for {allowed}"
        raise MatrixRefusedError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def matrix_path(explicit: str | None, environ: Mapping[str, str]) -> Path:
    """Decide which matrix file a command works on.

    Args:
        explicit: The path the caller gave, or None.
        environ: The process environment.

    Returns:
        The caller's path; else the path in the matrix variable; else the default place under
        the control repository the driver's variable, or the project's, names.

    Raises:
        MatrixError: No path was given and the environment names neither a matrix nor a control
            repository.

    """
    if explicit:
        return Path(explicit).expanduser()
    stated: str = environ.get(MATRIX_ENV, "").strip()
    if stated:
        return Path(stated).expanduser()
    control: str = environ.get(CONTROL_REPO_ENV, "").strip() or environ.get(CONTROL_REPO_FALLBACK_ENV, "").strip()
    if not control:
        message: str = f"give --matrix, or set {MATRIX_ENV}, {CONTROL_REPO_ENV} or {CONTROL_REPO_FALLBACK_ENV}"
        raise MatrixError(message)
    return Path(control).expanduser().joinpath(*DEFAULT_MATRIX_PARTS)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def lock_path(path: Path) -> Path:
    """Name the lock file of a matrix file.

    Args:
        path: The matrix file.

    Returns:
        The file named for the matrix, with the contract's lock suffix, in the contract's lock
        directory beside the matrix.

    """
    return path.parent / LOCK_DIRECTORY / f"{path.stem}{LOCK_SUFFIX}"


def _decode(path: Path) -> object:
    """Read a matrix file as decoded JSON.

    Returns:
        The decoded document.

    Raises:
        MatrixError: The file is missing, unreadable or not JSON.

    """
    message: str
    try:
        text: str = path.read_text(encoding="utf-8")
    except OSError as error:
        message = f"cannot read the matrix {path}: {error}"
        raise MatrixError(message) from error
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as error:
        message = f"the matrix {path} is not JSON: {error}"
        raise MatrixError(message) from error
    return decoded


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def read_matrix(path: Path) -> Matrix:
    """Read a matrix file and validate it against the schema.

    A read takes no lock: a write replaces the file in one move, so a reader sees the matrix
    before the change or after it. The rules the schema cannot state are checked on every write
    and by :func:`file_problems`, not here, so a read stays quick. A file that is missing,
    unreadable, not JSON or does not satisfy the schema raises ``MatrixError``.

    Args:
        path: The matrix file.

    Returns:
        The validated matrix.

    """
    return validate_matrix(_decode(path), str(path))


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def serialize(matrix: Matrix) -> str:
    """Render a matrix as the text of its file.

    Args:
        matrix: The matrix.

    Returns:
        Indented JSON with sorted keys and a final newline, so a change reads as a small diff.

    """
    return json.dumps(matrix, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def write_text(path: Path, text: str) -> None:
    """Put text in place of a file the matrix command writes, in one move.

    A reader of the file sees it as it was or as it is now, never half written. A file that
    cannot be written raises ``MatrixError``.

    Args:
        path: The file; its directory must exist.
        text: The whole text of the file.

    """
    _write_text(path, text)


def _write_text(path: Path, text: str) -> None:
    """Put text in place of a file in one move.

    Raises:
        MatrixError: The file cannot be written.

    """
    message: str
    descriptor: int
    temporary: str
    try:
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
        os.fchmod(descriptor, FILE_MODE)
    except OSError as error:
        message = f"cannot write {path}: {error}"
        raise MatrixError(message) from error
    scratch: Path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        scratch.replace(path)
    except OSError as error:
        scratch.unlink(missing_ok=True)
        message = f"cannot write {path}: {error}"
        raise MatrixError(message) from error


@contextmanager
@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def matrix_lock(path: Path, wait: float = DEFAULT_LOCK_WAIT) -> Generator[None]:
    """Hold the exclusive lock of a matrix file.

    The lock is an advisory lock on the matrix's lock file (:func:`lock_path`), which is left in
    place afterwards.

    Args:
        path: The matrix file.
        wait: Seconds to wait for another holder before giving up.

    Yields:
        Control while the lock is held.

    Raises:
        ValueError: ``wait`` is not a positive, finite number.
        MatrixError: The lock file cannot be opened.
        MatrixLockTimeoutError: Another process held the lock for the whole wait.

    """
    message: str
    if not 0 < wait < float("inf"):
        message = f"matrix: the lock wait {wait!r} is not a positive, finite number of seconds"
        raise ValueError(message)
    lock: Path = lock_path(path)
    deadline: float = time.monotonic() + wait
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        descriptor: int = os.open(lock, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as error:
        message = f"cannot open the matrix lock {lock}: {error}"
        raise MatrixError(message) from error
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    message = f"the matrix {path} stayed locked by another process for {wait} seconds"
                    raise MatrixLockTimeoutError(message) from error
                time.sleep(LOCK_POLL)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def create_matrix(path: Path, matrix: Matrix, *, replace: bool = False, wait: float = DEFAULT_LOCK_WAIT) -> None:
    """Write a new matrix file, creating its directory when it does not exist.

    A matrix that does not conform, or a lock another process holds for the whole wait, raises
    ``MatrixError``.

    Args:
        path: The matrix file to create.
        matrix: The matrix.
        replace: Whether a matrix file already at ``path`` is replaced.
        wait: Seconds to wait for the matrix's lock.

    Raises:
        MatrixRefusedError: A matrix file already exists at ``path`` and ``replace`` is False.
        MatrixError: The directory cannot be created.

    """
    message: str
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        message = f"cannot create the matrix directory {path.parent}: {error}"
        raise MatrixError(message) from error
    with matrix_lock(path, wait):
        if path.exists() and not replace:
            message = f"a matrix already exists at {path}"
            raise MatrixRefusedError(message)
        _write_text(path, serialize(checked_matrix(matrix, f"the matrix to write to {path}")))


def _row_texts(matrix: Matrix) -> dict[NodeId, str]:
    """Render each row of a matrix as text, to tell afterwards which rows a change touched.

    Returns:
        Each row's id and its JSON text.

    """
    return {key: json.dumps(node, sort_keys=True, ensure_ascii=False) for key, node in matrix["nodes"].items()}


def _checked_change(matrix: Matrix, before: Mapping[NodeId, str], where: str) -> None:
    """Require a changed matrix to conform, validating against the schema only what the change touched.

    The matrix satisfied the schema when it was read, so the rows the change left alone still do.
    The rows it added or changed, and everything of the matrix that is not a row, are validated
    against the schema; the rules the schema cannot state are checked over the whole matrix,
    because a change to one row can break a rule that concerns another.

    Raises:
        MatrixError: A row is filed under something that is not a row id, a changed row or the
            rest of the matrix does not satisfy the schema, or the matrix breaks a rule the
            schema cannot state.

    """
    message: str
    validate_matrix({**matrix, "nodes": {}}, where)
    key: NodeId
    node: Node
    for key, node in matrix["nodes"].items():
        if before.get(key) == json.dumps(node, sort_keys=True, ensure_ascii=False):
            continue
        if NODE_ID_PATTERN.search(key) is None:
            message = f"{where}: {key!r} is not a row id"
            raise MatrixError(message)
        validate_node(node, f"{where}: the row {key}")
    problems: list[str] = consistency_problems(matrix)
    if problems:
        message = f"{where} is not consistent ({len(problems)} problems): " + "; ".join(problems[:20])
        raise MatrixError(message)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def update_matrix[T](path: Path, change: Callable[[Matrix], T], *, wait: float = DEFAULT_LOCK_WAIT) -> T:
    """Apply one change to a matrix file as a single locked read-modify-write.

    The matrix is read and validated under the lock, ``change`` edits it in place, and the result
    is checked and moved into place before the lock is released. Only the rows the change
    touched are validated against the schema again; the rules the schema cannot state are
    checked over the whole matrix. A change that leaves the matrix as it was writes nothing.
    When ``change`` raises, or the changed matrix does not conform, the file is left as it was.

    Args:
        path: The matrix file.
        change: The edit; it receives the matrix and returns whatever the caller wants back.
        wait: Seconds to wait for the matrix's lock.

    Returns:
        What ``change`` returned.

    Raises:
        MatrixError: There is no matrix at ``path``.

    """
    if not path.is_file():
        message: str = f"there is no matrix at {path}"
        raise MatrixError(message)
    with matrix_lock(path, wait):
        matrix: Matrix = read_matrix(path)
        before: str = serialize(matrix)
        rows: dict[NodeId, str] = _row_texts(matrix)
        result: T = change(matrix)
        after: str = serialize(matrix)
        if after != before:
            _checked_change(matrix, rows, f"the matrix to write to {path}")
            _write_text(path, after)
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def file_problems(path: Path) -> list[str]:
    """Describe every way a matrix file fails the schema and the rules the schema cannot state.

    A file that is missing, unreadable or not JSON raises ``MatrixError``.

    Args:
        path: The matrix file.

    Returns:
        The schema's problems when the file does not satisfy it, otherwise the problems
        :func:`consistency_problems` and :func:`heading_problems` find; empty when the file conforms.

    """
    decoded: object = _decode(path)
    try:
        matrix: Matrix = validate_matrix(decoded, str(path))
    except MatrixError as error:
        return [str(error)]
    return [*consistency_problems(matrix), *heading_problems(matrix)]
