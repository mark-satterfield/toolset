"""atw-matrix: the one command through which the matrix is read and written.

The matrix is the index of how things in the project relate: repositories, stacks, services,
components, libraries, layers, infrastructure, PRDs, features, architecture documents, design
facts and disagreements, with the approval marker and the code-trust marker. Its shape is
``skills/artifact-handoff/schemas/matrix.schema.json``; the file is
``ops/sdlc-automation/matrix.json`` in the control repository unless ``--matrix`` or the matrix
variable names another.

Every sub-command prints one JSON object on stdout. The read sub-commands (``prd``, ``find``,
``node``, ``uses``, ``disagreements``, ``summary``) answer from the file and change nothing.
``check`` reports every way the file fails its contract. ``sync-prds`` and ``sync-documents``
bring the file up to date with beads and the vault. ``carry-over`` builds the file once from the
element matrix. ``matrixcli`` holds the sub-commands that record a design (``put``, ``link``,
``claim``, ``settle``, ``note-sendback``, ``add-resource-type``, ``expertise``), open and close
its review (``unapproved``, ``approve``), mark what was built (``mark-built``,
``mark-deployed``, ``mark-merged``) and check reuse (``check-reuse``). The schema's command
table says which role may run each; the role is the value of the role variable, and the
operator when it is not set.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final, TypedDict

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
from driver_surface_types import ARCH_PATH_ENV, CONTROL_REPO_ENV, PRD_DIR_ENV
from matrix_contract import (
    COMMAND_RULES,
    KIND_PRD,
    KINDS,
    Claim,
    DocumentsSyncedAt,
    Kind,
    Matrix,
    MatrixError,
    Node,
    NodeId,
)
from matrixcall import EXIT_OK, EXIT_REFUSED, PROGRAM, Call, Outcome, decoded_file
from matrixcarry import CarryReport, CarrySources, carry_over, parse_inventory, parse_old_matrix, parse_type_map
from matrixcli import COMMANDS as DESIGN_COMMANDS
from matrixcli import add_parsers, elements_of_task
from matrixquery import (
    DEFAULT_LIMIT,
    disagreements_for,
    elements_of_repository,
    find,
    node_view,
    prd_view,
    resolve,
    summarize,
    uses_view,
    words,
)
from matrixstore import (
    CHANGED_BY_CARRY_OVER,
    CHANGED_BY_SYNC,
    CONTROL_REPO_FALLBACK_ENV,
    DEFAULT_LOCK_WAIT,
    MatrixRefusedError,
    Stamp,
    create_matrix,
    file_problems,
    make_id,
    read_matrix,
    require_role,
    role_of,
    timestamp,
    update_matrix,
)
from matrixsync import (
    DocumentRead,
    DocumentsSynced,
    Epic,
    PrdsSynced,
    VaultChange,
    hold_for_review,
    parse_epics,
    read_documents,
    read_epics,
    sync_documents,
    sync_prds,
    vault_change,
    vault_problems,
    vault_root,
)

KIND_SEPARATOR: Final = ","
SYNC_STEP: Final = "sync-documents"
"""The journal step named on a claim the vault read places when the caller names none."""


class DisagreementsResult(TypedDict):
    """What ``disagreements`` prints."""

    document: str
    disagreements: list[Node]


class CheckResult(TypedDict):
    """What ``check`` prints."""

    valid: bool
    problems: list[str]
    vaultChecked: bool
    """False when no architecture root was given, so the two rules that need the documents were not checked."""


def _run_prd(call: Call) -> Outcome:
    """Run ``prd``.

    Returns:
        The PRD row of the Epic, the features it needs, and with ``--closure`` everything it reaches.

    """
    return Outcome(prd_view(read_matrix(call.matrix()), call.required("epic"), closure=call.flag("closure")))


def _kinds(call: Call) -> tuple[Kind, ...]:
    """Read the kinds a ``find`` is limited to.

    Returns:
        The kinds ``--kinds`` names, or every kind when it was not given.

    Raises:
        MatrixRefusedError: ``--kinds`` names something that is not a row kind.

    """
    stated: str | None = call.text("kinds")
    if stated is None:
        return KINDS
    names: list[str] = [name.strip() for name in stated.split(KIND_SEPARATOR) if name.strip()]
    unknown: list[str] = [name for name in names if name not in KINDS]
    if unknown:
        message: str = f"--kinds names {', '.join(unknown)}, which are not among {', '.join(KINDS)}"
        raise MatrixRefusedError(message)
    return tuple(kind for kind in KINDS if kind in names)


def _run_find(call: Call) -> Outcome:
    """Run ``find``.

    Returns:
        The rows that match the words given.

    Raises:
        MatrixRefusedError: Neither ``--text`` nor ``--provides`` holds a word, or ``--limit`` is negative.

    """
    text: str = call.text("text") or ""
    provides: str = call.text("provides") or ""
    limit: object = getattr(call.args, "limit", DEFAULT_LIMIT)
    message: str
    if not words(f"{text} {provides}"):
        message = "give --text or --provides with at least one word of two or more letters"
        raise MatrixRefusedError(message)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        message = "--limit must be 0 or more"
        raise MatrixRefusedError(message)
    matrix: Matrix = read_matrix(call.matrix())
    return Outcome(find(matrix, text, provides=provides, kinds=_kinds(call), limit=limit))


def _run_node(call: Call) -> Outcome:
    """Run ``node``.

    Returns:
        The row the id or name refers to, with the links that point at it.

    """
    matrix: Matrix = read_matrix(call.matrix())
    return Outcome(node_view(matrix, resolve(matrix, call.required("row"))))


def _run_uses(call: Call) -> Outcome:
    """Run ``uses``.

    Returns:
        The shared capabilities the elements of a repository, the elements named, or the
        elements a Task builds, must use.

    Raises:
        MatrixRefusedError: Not exactly one of ``--repository``, ``--elements`` and ``--task``
            was given.

    """
    matrix: Matrix = read_matrix(call.matrix())
    repository: str | None = call.text("repository")
    task: str | None = call.text("task")
    named: list[str] = call.texts("elements")
    if sum([repository is not None, task is not None, bool(named)]) != 1:
        message: str = "give exactly one of --repository, --elements and --task"
        raise MatrixRefusedError(message)
    if task is not None:
        named = elements_of_task(call, task)
    elements: list[NodeId] = (
        [resolve(matrix, name) for name in named] if repository is None else elements_of_repository(matrix, repository)
    )
    return Outcome(uses_view(matrix, elements))


def _run_disagreements(call: Call) -> Outcome:
    """Run ``disagreements``.

    Returns:
        The recorded disagreements that quote the document, with their settlements.

    """
    document: str = call.required("document")
    return Outcome({"document": document, "disagreements": disagreements_for(read_matrix(call.matrix()), document)})


def _run_summary(call: Call) -> Outcome:
    """Run ``summary``.

    Returns:
        The counts of rows by kind and by marker.

    """
    return Outcome(summarize(read_matrix(call.matrix())))


def _run_check(call: Call) -> Outcome:
    """Run ``check``.

    Returns:
        Whether the matrix file conforms and every problem found; the status is the refusal
        status when it does not conform.

    """
    path: Path = call.matrix()
    problems: list[str] = file_problems(path)
    arch: Path | None = call.folder("arch", [ARCH_PATH_ENV])
    bead: str | None = call.text("bead")
    if not problems:
        matrix: Matrix = read_matrix(path)
        if arch is not None:
            problems.extend(vault_problems(matrix, arch))
        if bead is not None and make_id(KIND_PRD, bead) not in matrix["nodes"]:
            problems.append(f"the matrix has no PRD row for {bead}")
    result: CheckResult = {"valid": not problems, "problems": problems, "vaultChecked": arch is not None}
    return Outcome(result, EXIT_REFUSED if problems else EXIT_OK)


def _saved_epics(path: Path, bead: str | None) -> list[Epic]:
    """Read the Epics from a file holding what ``bd list --json`` printed.

    Returns:
        The Epics in the file; only the one named when ``bead`` is given.

    Raises:
        MatrixError: The file cannot be read.

    """
    try:
        epics: list[Epic] = parse_epics(path.read_text(encoding="utf-8"))
    except OSError as error:
        message: str = f"cannot read the Epics file {path}: {error}"
        raise MatrixError(message) from error
    return [epic for epic in epics if bead is None or epic.bead == bead]


def _run_sync_prds(call: Call) -> Outcome:
    """Run ``sync-prds``.

    Returns:
        The PRD rows created and refreshed, and the Epics that could not be given one.

    """
    prd_dir: Path = call.required_folder("prd_dir", [PRD_DIR_ENV])
    bead: str | None = call.text("bead")
    saved: str | None = call.text("epics_file")
    epics: list[Epic] = (
        read_epics(call.required_folder("control", [CONTROL_REPO_ENV, CONTROL_REPO_FALLBACK_ENV]), bead)
        if saved is None
        else _saved_epics(Path(saved).expanduser(), bead)
    )
    stamp: Stamp = Stamp(timestamp(), CHANGED_BY_SYNC)

    def change(matrix: Matrix) -> PrdsSynced:
        return sync_prds(matrix, epics, prd_dir, stamp)

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_sync_documents(call: Call) -> Outcome:
    """Run ``sync-documents``.

    Returns:
        What reading the vault changed in the matrix. With ``--bead``, the read is an Epic's:
        the headings it finds changed are claimed for the Epic, and an effective document that
        now holds unreviewed text is set to in-review in the vault.

    """
    arch: Path = call.required_folder("arch", [ARCH_PATH_ENV])
    bead: str | None = call.text("bead")
    stamp: Stamp = Stamp(timestamp(), bead or CHANGED_BY_SYNC)
    full: bool = call.flag("full")

    def change(matrix: Matrix) -> DocumentsSynced:
        synced: DocumentsSynced = sync_documents(matrix, arch, stamp, full=full)
        if bead is not None:
            held: Claim = {"bead": bead, "step": call.text("step") or SYNC_STEP, "at": stamp.at}
            synced["inReview"] = hold_for_review(matrix, arch, [*synced["added"], *synced["changed"]], held)
        return synced

    return Outcome(update_matrix(call.matrix(), change, wait=call.lock_wait()))


def _run_carry_over(call: Call) -> Outcome:
    """Run ``carry-over``.

    Returns:
        The account of what became of every part of the element matrix.

    """
    arch: Path = call.required_folder("arch", [ARCH_PATH_ENV])
    inventory: str | None = call.text("inventory")
    sources: CarrySources = CarrySources(
        old=parse_old_matrix(decoded_file(Path(call.required("source")).expanduser(), "the element matrix")),
        types=parse_type_map(decoded_file(Path(call.required("type_map")).expanduser(), "the mapping file")),
        inventory=None
        if inventory is None
        else parse_inventory(decoded_file(Path(inventory).expanduser(), "the repository inventory")),
    )
    vault: Path = vault_root(arch)
    stamp: Stamp = Stamp(timestamp(), CHANGED_BY_CARRY_OVER)
    never: DocumentsSyncedAt = {"vaultCommit": "", "at": stamp.at, "dirtyPaths": []}
    state: VaultChange = vault_change(vault, arch, never, full=True)
    documents: list[DocumentRead] = read_documents(vault, arch)
    synced: DocumentsSyncedAt = {"vaultCommit": state.commit, "at": stamp.at, "dirtyPaths": list(state.dirty)}
    matrix: Matrix
    report: CarryReport
    matrix, report = carry_over(sources, documents, synced, stamp)
    create_matrix(call.matrix(), matrix, replace=call.flag("replace"), wait=call.lock_wait())
    return Outcome(report)


COMMANDS: Final[dict[str, Callable[[Call], Outcome]]] = {
    "prd": _run_prd,
    "find": _run_find,
    "node": _run_node,
    "uses": _run_uses,
    "disagreements": _run_disagreements,
    "summary": _run_summary,
    "check": _run_check,
    "sync-prds": _run_sync_prds,
    "sync-documents": _run_sync_documents,
    "carry-over": _run_carry_over,
    **DESIGN_COMMANDS,
}
"""Every sub-command, by the name the schema's command table gives it."""


def _parser() -> argparse.ArgumentParser:
    """Build the command line: one sub-command per matrix operation.

    Returns:
        The argument parser.

    """
    where: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    where.add_argument("--matrix", help="the matrix file; default: the matrix variable, else the control repository")
    where.add_argument("--lock-wait", type=float, default=DEFAULT_LOCK_WAIT, help="seconds to wait for the lock")
    arch: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    arch.add_argument("--arch", help=f"the architecture root in the vault; default: {ARCH_PATH_ENV}")
    who: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    who.add_argument("--bead", help="the Epic the change is made for")
    who.add_argument("--step", help="the journal step id of the session that makes the change")
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Read and change the matrix. Prints one JSON object on stdout.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prd: argparse.ArgumentParser = commands.add_parser("prd", parents=[where], help="what the matrix holds for a PRD")
    prd.add_argument("epic", help="the Epic id")
    prd.add_argument("--closure", action="store_true", help="include everything the PRD reaches, with markers")
    found: argparse.ArgumentParser = commands.add_parser("find", parents=[where], help="rows that match some words")
    found.add_argument("--text", help="the words to look for")
    found.add_argument("--provides", help="a behaviour to look for among the shared capabilities")
    found.add_argument("--kinds", help="the kinds of row to search, separated by commas")
    found.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="the most rows to print; 0 prints all")
    node: argparse.ArgumentParser = commands.add_parser("node", parents=[where], help="one row with its reverse links")
    node.add_argument("row", help="the row's id, its former element matrix id, or a name only it answers to")
    uses: argparse.ArgumentParser = commands.add_parser(
        "uses",
        parents=[where],
        help="the shared capabilities some elements must use",
    )
    uses.add_argument("--repository", help="the repository whose elements are asked about")
    uses.add_argument("--elements", nargs="+", help="the ids of the elements asked about")
    uses.add_argument("--task", help="the Task whose elements are asked about")
    uses.add_argument("--task-file", help="a file holding what `bd show <task> --json` printed, read in place of bd")
    uses.add_argument("--control", help=f"the control repository bd runs in; default: {CONTROL_REPO_ENV}")
    disputed: argparse.ArgumentParser = commands.add_parser(
        "disagreements",
        parents=[where],
        help="recorded disagreements that quote a document",
    )
    disputed.add_argument("--document", required=True, help="the document's path relative to the vault root")
    commands.add_parser("summary", parents=[where], help="the counts of rows by kind and by marker")
    check: argparse.ArgumentParser = commands.add_parser(
        "check",
        parents=[where, arch],
        help="check the matrix file against its contract",
    )
    check.add_argument("--bead", help="also require the PRD row of this Epic")
    prds: argparse.ArgumentParser = commands.add_parser("sync-prds", parents=[where], help="PRD rows from beads")
    prds.add_argument("--bead", help="the one Epic to give a PRD row; default: every open Epic")
    prds.add_argument("--prd-dir", help=f"the folder the PRD files are under; default: {PRD_DIR_ENV}")
    prds.add_argument("--control", help=f"the control repository bd runs in; default: {CONTROL_REPO_ENV}")
    prds.add_argument("--epics-file", help="a file holding what `bd list --json` printed, read in place of bd")
    documents: argparse.ArgumentParser = commands.add_parser(
        "sync-documents",
        parents=[where, arch],
        help="document rows, heading hashes and lifecycle from the vault",
    )
    documents.add_argument("--bead", help="the Epic that changed the documents; its review then finds the changes")
    documents.add_argument("--step", help="the journal step id of the session that asks")
    documents.add_argument("--full", action="store_true", help="read every document whatever git reports")
    carry: argparse.ArgumentParser = commands.add_parser(
        "carry-over",
        parents=[where, arch],
        help="build the matrix once from the element matrix and the vault",
    )
    carry.add_argument("--source", required=True, help="the element matrix file")
    carry.add_argument("--type-map", required=True, help="the mapping file from resource type spellings")
    carry.add_argument("--inventory", help="a file holding what `polyrepo inventory` printed")
    carry.add_argument("--replace", action="store_true", help="replace a matrix file that already exists")
    add_parsers(commands, where, arch, who)
    return parser


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main(argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    """Run one matrix sub-command.

    Args:
        argv: The arguments after the program name; None reads the process's own.
        environ: The environment to run in; None reads the process's own.

    Returns:
        0 after printing the result as one JSON object on stdout; 1 after printing why the
        matrix refused on stderr. ``check`` prints its JSON object either way and returns 1 for
        a matrix that does not conform.

    Raises:
        RuntimeError: The sub-commands built and the schema's command table name different commands.

    """
    stray: list[str] = sorted(set(COMMANDS) ^ set(COMMAND_RULES))
    if stray:
        message: str = f"the schema's command table and the sub-commands built differ on {', '.join(stray)}"
        raise RuntimeError(message)
    args: argparse.Namespace = _parser().parse_args(argv)
    call: Call = Call(args, os.environ if environ is None else environ)
    command: str = call.required("command")
    try:
        require_role(command, role_of(call.environ))
        outcome: Outcome = COMMANDS[command](call)
    except MatrixError as error:
        sys.stderr.write(f"{PROGRAM} {command}: {error}\n")
        return EXIT_REFUSED
    sys.stdout.write(json.dumps(outcome.result, ensure_ascii=False) + "\n")
    if outcome.status != EXIT_OK:
        sys.stderr.write(f"{PROGRAM} {command}: the matrix does not conform; see the problems on stdout\n")
    return outcome.status


if __name__ == "__main__":
    sys.exit(main())
