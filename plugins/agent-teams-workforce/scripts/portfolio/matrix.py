"""atw-matrix: the one command through which the matrix is read and written.

The matrix is one JSON file of entries and relationships: Epics and their requirements,
features, constraints, architecture documents, services, components, infrastructure, events, stacks,
packages, layers and disagreements, each carrying the side it came from (architecture or
repository) and, where set, the approved and verified flags. Its shape is
``skills/artifact-handoff/schemas/matrix.schema.json`` and its kinds are
``skills/artifact-handoff/schemas/matrix-kinds.json``; the file is
``ops/sdlc-automation/matrix.json`` in the control repository unless ``--matrix`` or the matrix
variable names another.

Every sub-command prints one JSON object on stdout. This module holds the reads, which answer
from the file and change nothing (``epic``, ``find``, ``node``, ``deps``, ``stacks``,
``layers``, ``resources``, ``parameters``, ``documents``, ``links``, ``impact``, ``related``,
``uses``, ``approval``, ``story-scope``, ``review-scope``, ``summary``),
and ``check``, which reports every way the file fails its contract. ``matrixcli`` holds the
sub-commands that change the matrix, bring it up to date, seed it and mark it. The registry's
command table says which role may run each; the role is the value of the role variable, and the
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
from matrix_contract import COMMAND_RULES, ENTRY_KINDS, EntryKind, RelationshipKind, entry_kind, relationship_kind
from matrixcall import EXIT_OK, EXIT_REFUSED, PROGRAM, Call, Outcome
from matrixcli import COMMANDS as CHANGE_COMMANDS
from matrixcli import add_parsers
from matrixquery import (
    DEFAULT_LIMIT,
    LINK_DIRECTIONS,
    LINK_OUT,
    EpicView,
    approval_view,
    deps_view,
    documents_view,
    epic_view,
    find,
    impact_view,
    layers_view,
    links_view,
    node_view,
    parameters_view,
    realizers_view,
    related_view,
    resources_view,
    stacks_view,
    story_scope,
    summarize,
    uses_view,
)
from matrixreview import review_scope
from matrixstore import (
    DEFAULT_LOCK_WAIT,
    Matrix,
    MatrixRefusedError,
    file_problems,
    read_matrix,
    require_role,
    role_of,
)

KIND_SEPARATOR: Final = ","


class CheckResult(TypedDict):
    """What ``check`` prints."""

    valid: bool
    problems: list[str]


def _run_epic(call: Call) -> Outcome:
    """Run ``epic``.

    Returns:
        The Epic with its PRD, its requirements with their features and covering documents, and
        what each flag adds: the constraints, everything the Epic reaches, the links with
        nothing recorded at the other end, and what realizes each feature.

    """
    matrix: Matrix = read_matrix(call.matrix())
    bead: str = call.required("epic")
    view: EpicView = epic_view(
        matrix,
        bead,
        closure=call.flag("closure"),
        constraints=call.flag("constraints"),
        unlinked=call.flag("unlinked"),
    )
    if not call.flag("realizers"):
        return Outcome(view)
    return Outcome({**view, "realizers": realizers_view(matrix, bead)})


def _kinds(call: Call) -> tuple[EntryKind, ...]:
    """Read the kinds a ``find`` is limited to.

    A name that is not an entry kind raises ``MatrixError`` from ``entry_kind``.

    Returns:
        The kinds ``--kinds`` names, in registry order, or every kind when it was not given.

    """
    stated: str | None = call.text("kinds")
    if stated is None:
        return ENTRY_KINDS
    named: set[EntryKind] = {entry_kind(name.strip()) for name in stated.split(KIND_SEPARATOR) if name.strip()}
    return tuple(kind for kind in ENTRY_KINDS if kind in named)


def _run_find(call: Call) -> Outcome:
    """Run ``find``.

    Returns:
        The entries that share words with the text, ranked, or the Epic whose PRD is the path.

    Raises:
        MatrixRefusedError: ``--limit`` is negative.

    """
    limit: int | None = call.number("limit")
    if limit is not None and limit < 0:
        message: str = "--limit must be 0 or more"
        raise MatrixRefusedError(message)
    matrix: Matrix = read_matrix(call.matrix())
    return Outcome(
        find(
            matrix,
            call.text("text") or "",
            kinds=_kinds(call),
            prd=call.text("prd"),
            limit=DEFAULT_LIMIT if limit is None else limit,
        ),
    )


def _run_node(call: Call) -> Outcome:
    """Run ``node``.

    Returns:
        The entry with its relationships from both ends.

    """
    return Outcome(node_view(read_matrix(call.matrix()), call.entry("id")))


def _run_deps(call: Call) -> Outcome:
    """Run ``deps``.

    Returns:
        What the entry depends on (``--of``) or what depends on it (``--on``), to any depth.

    """
    inward: bool = call.text("on") is not None
    return Outcome(deps_view(read_matrix(call.matrix()), call.entry("on" if inward else "of"), inward=inward))


def _run_stacks(call: Call) -> Outcome:
    """Run ``stacks``.

    Returns:
        The stacks, or those of one app, of one repository, or that hold one resource type.

    """
    return Outcome(
        stacks_view(
            read_matrix(call.matrix()),
            app=call.text("app"),
            repository=call.text("repository"),
            resource_type=call.text("resource_type"),
        ),
    )


def _run_resources(call: Call) -> Outcome:
    """Run ``resources``.

    Returns:
        The AWS resources the Epic reaches, with their stacks and repositories.

    """
    return Outcome(resources_view(read_matrix(call.matrix()), call.required("epic")))


def _run_parameters(call: Call) -> Outcome:
    """Run ``parameters``.

    Returns:
        The SSM parameters the stack writes, with the entries that read each, and those it reads.

    """
    return Outcome(parameters_view(read_matrix(call.matrix()), call.entry("stack")))


def _run_documents(call: Call) -> Outcome:
    """Run ``documents``.

    Returns:
        Every architecture and design document related to the entry and what belongs to it.

    """
    return Outcome(documents_view(read_matrix(call.matrix()), call.entry("id")))


def _run_links(call: Call) -> Outcome:
    """Run ``links``.

    Returns:
        The entry's links followed to the depth asked, or to any depth.

    """
    kinds: tuple[RelationshipKind, ...] = tuple(
        relationship_kind(name.strip()) for name in (call.text("kinds") or "").split(KIND_SEPARATOR) if name.strip()
    )
    return Outcome(
        links_view(
            read_matrix(call.matrix()),
            call.entry("id"),
            depth=call.number("depth"),
            direction=call.text("direction") or LINK_OUT,
            kinds=kinds,
        ),
    )


def _run_layers(call: Call) -> Outcome:
    """Run ``layers``.

    Returns:
        Every layer with the packages it carries and the components that attach it.

    """
    return Outcome(layers_view(read_matrix(call.matrix())))


def _run_impact(call: Call) -> Outcome:
    """Run ``impact``.

    Returns:
        What a change to the entry reaches.

    """
    return Outcome(impact_view(read_matrix(call.matrix()), call.entry("id")))


def _run_related(call: Call) -> Outcome:
    """Run ``related``.

    Returns:
        The Epics that reach what the Epic reaches, each with what is shared.

    """
    return Outcome(related_view(read_matrix(call.matrix()), call.required("epic")))


def _run_approval(call: Call) -> Outcome:
    """Run ``approval``.

    Returns:
        The matrix content the Epic reaches, split into what carries the approved flag and what
        does not.

    """
    return Outcome(approval_view(read_matrix(call.matrix()), call.required("epic")))


def _run_uses(call: Call) -> Outcome:
    """Run ``uses``.

    Returns:
        The shared capabilities the work that builds the entries must use.

    """
    return Outcome(uses_view(read_matrix(call.matrix()), call.entries("ids")))


def _run_story_scope(call: Call) -> Outcome:
    """Run ``story-scope``.

    Returns:
        The stack and its repository, the documents that describe each entry, the constraints
        that apply and the shared capabilities.

    """
    return Outcome(story_scope(read_matrix(call.matrix()), call.entry("stack"), call.entries("ids")))


def _run_review_scope(call: Call) -> Outcome:
    """Run ``review-scope``.

    Returns:
        The documents the Epic reaches that are not effective, each with the headings reached.

    """
    return Outcome(review_scope(read_matrix(call.matrix()), call.required("epic")))


def _run_summary(call: Call) -> Outcome:
    """Run ``summary``.

    Returns:
        The counts of entries and relationships by kind, by side and by mark, and with
        ``--unlinked`` the repository-side entries with no architecture-side counterpart.

    """
    return Outcome(summarize(read_matrix(call.matrix()), unlinked=call.flag("unlinked")))


def _run_check(call: Call) -> Outcome:
    """Run ``check``.

    Returns:
        Whether the matrix file conforms and every problem found; the status is the refusal
        status when it does not conform.

    """
    problems: list[str] = file_problems(call.matrix())
    result: CheckResult = {"valid": not problems, "problems": problems}
    return Outcome(result, EXIT_REFUSED if problems else EXIT_OK)


COMMANDS: Final[dict[str, Callable[[Call], Outcome]]] = {
    "epic": _run_epic,
    "find": _run_find,
    "node": _run_node,
    "deps": _run_deps,
    "stacks": _run_stacks,
    "layers": _run_layers,
    "resources": _run_resources,
    "parameters": _run_parameters,
    "documents": _run_documents,
    "links": _run_links,
    "impact": _run_impact,
    "related": _run_related,
    "uses": _run_uses,
    "approval": _run_approval,
    "story-scope": _run_story_scope,
    "review-scope": _run_review_scope,
    "summary": _run_summary,
    "check": _run_check,
    **CHANGE_COMMANDS,
}
"""Every sub-command, by the name the registry's command table gives it."""


def _walk_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
) -> None:
    """Add the reads that walk out from an Epic, a stack or any entry: resources, parameters, documents, links."""
    resources: argparse.ArgumentParser = commands.add_parser(
        "resources",
        parents=[where],
        help="the AWS resources an Epic reaches, with their stacks and repositories",
    )
    resources.add_argument("--epic", required=True, help="the Epic's beads id")
    parameters: argparse.ArgumentParser = commands.add_parser(
        "parameters",
        parents=[where],
        help="the SSM parameters a stack writes, with their readers, and those it reads",
    )
    parameters.add_argument("--stack", required=True, help="the stack's id")
    documents: argparse.ArgumentParser = commands.add_parser(
        "documents",
        parents=[where],
        help="every architecture and design document related to an entry, such as a service",
    )
    documents.add_argument("--id", required=True, help="the entry's id")
    links: argparse.ArgumentParser = commands.add_parser(
        "links",
        parents=[where],
        help="an entry's links followed to any depth",
    )
    links.add_argument("--id", required=True, help="the id of the entry the walk starts at")
    links.add_argument("--depth", type=int, help="the most relationships from the entry; default: any depth")
    links.add_argument(
        "--direction",
        choices=LINK_DIRECTIONS,
        default=LINK_OUT,
        help="follow the links that start at each entry (out), end at it (in) or either (both); default: out",
    )
    links.add_argument("--kinds", help="the relationship kinds to follow, separated by commas; default: every kind")


def _read_parsers(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    where: argparse.ArgumentParser,
) -> None:
    """Add the sub-commands that read the matrix and change nothing."""
    epic: argparse.ArgumentParser = commands.add_parser("epic", parents=[where], help="what an Epic reaches")
    epic.add_argument("epic", help="the Epic's beads id")
    epic.add_argument("--closure", action="store_true", help="include everything the Epic reaches, by repository")
    epic.add_argument(
        "--constraints",
        action="store_true",
        help="include the constraints that bind the Epic, its features and what realizes them",
    )
    epic.add_argument("--unlinked", action="store_true", help="include the links with nothing at the other end")
    epic.add_argument(
        "--realizers",
        action="store_true",
        help="include what realizes each feature, with each realizer's stack and repository",
    )
    found: argparse.ArgumentParser = commands.add_parser("find", parents=[where], help="entries that match some words")
    found.add_argument("--text", help="the words to look for")
    found.add_argument("--kinds", help="the kinds of entry to search, separated by commas")
    found.add_argument("--prd", help="a PRD's path in the vault: the Epic whose PRD it is")
    found.add_argument("--limit", type=int, help=f"the most entries to print; 0 prints all; default: {DEFAULT_LIMIT}")
    node: argparse.ArgumentParser = commands.add_parser("node", parents=[where], help="one entry and its relationships")
    node.add_argument("id", help="the entry's id")
    deps: argparse.ArgumentParser = commands.add_parser("deps", parents=[where], help="the dependencies of an entry")
    direction: argparse._MutuallyExclusiveGroup = deps.add_mutually_exclusive_group(required=True)
    direction.add_argument("--of", help="the id of the entry whose dependencies are asked for")
    direction.add_argument("--on", help="the id of the entry whose dependents are asked for")
    stacks: argparse.ArgumentParser = commands.add_parser("stacks", parents=[where], help="the stacks, or some of them")
    stacks.add_argument("--app", help="only the stacks of this app")
    stacks.add_argument("--repository", help="only the stacks this repository holds")
    stacks.add_argument("--resource-type", help="only the stacks that hold an entry of this resource type")
    commands.add_parser("layers", parents=[where], help="every layer with its packages and the components that use it")
    _walk_parsers(commands, where)
    impact: argparse.ArgumentParser = commands.add_parser("impact", parents=[where], help="what a change reaches")
    impact.add_argument("--id", required=True, help="the id of the entry to be changed")
    related: argparse.ArgumentParser = commands.add_parser(
        "related",
        parents=[where],
        help="the Epics that reach what an Epic reaches",
    )
    related.add_argument("--epic", required=True, help="the Epic's beads id")
    uses: argparse.ArgumentParser = commands.add_parser(
        "uses",
        parents=[where],
        help="the shared capabilities the work that builds some entries must use",
    )
    uses.add_argument("--ids", nargs="+", required=True, help="the ids of the entries the work builds")
    approval: argparse.ArgumentParser = commands.add_parser(
        "approval",
        parents=[where],
        help="the matrix content an Epic reaches, approved and not approved",
    )
    approval.add_argument("--epic", required=True, help="the Epic's beads id")
    scope: argparse.ArgumentParser = commands.add_parser(
        "story-scope",
        parents=[where],
        help="what a Story that builds some entries of a stack must be handed",
    )
    scope.add_argument("--stack", required=True, help="the id of the stack the Story builds in")
    scope.add_argument("--ids", nargs="+", required=True, help="the ids of the entries the Story builds")
    review: argparse.ArgumentParser = commands.add_parser(
        "review-scope",
        parents=[where],
        help="the documents an Epic reaches that are not effective",
    )
    review.add_argument("--epic", required=True, help="the Epic's beads id")
    summary: argparse.ArgumentParser = commands.add_parser(
        "summary",
        parents=[where],
        help="the counts of entries and relationships",
    )
    summary.add_argument(
        "--unlinked",
        action="store_true",
        help="include the repository-side entries with no architecture-side counterpart",
    )
    commands.add_parser("check", parents=[where], help="check the matrix file against the schema and the registry")


def _source(option: str, text: str) -> argparse.ArgumentParser:
    """Build the option group that names one source a sub-command reads.

    Returns:
        A parser holding the one option, for sub-commands to take as a parent.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(option, help=text)
    return parser


def _parser() -> argparse.ArgumentParser:
    """Build the command line: one sub-command per matrix operation.

    Returns:
        The argument parser.

    """
    where: argparse.ArgumentParser = argparse.ArgumentParser(add_help=False)
    where.add_argument("--matrix", help="the matrix file; default: the matrix variable, else the control repository")
    where.add_argument("--lock-wait", type=float, default=DEFAULT_LOCK_WAIT, help="seconds to wait for the lock")
    sources: dict[str, argparse.ArgumentParser] = {
        "control": _source(
            "--control",
            f"the control repository bd runs in; default: {CONTROL_REPO_ENV}",
        ),
        "arch": _source("--arch", f"the architecture root in the vault; default: {ARCH_PATH_ENV}"),
        "prds": _source("--prd-dir", f"the folder of the vault the PRD files are under; default: {PRD_DIR_ENV}"),
        "folder": _source("--directory", "the seeding folder; default: state/seed beside the matrix file"),
    }
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Read and change the matrix. Prints one JSON object on stdout.",
    )
    commands: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(dest="command", required=True)
    _read_parsers(commands, where)
    add_parsers(commands, where, sources)
    return parser


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main(argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    """Run one matrix sub-command.

    Args:
        argv: The arguments after the program name; None reads the process's own.
        environ: The environment to run in; None reads the process's own.

    Returns:
        0 after printing the result as one JSON object on stdout; 1 after printing why the
        matrix refused on stderr. ``check`` and ``apply`` print their JSON object either way and
        return 1 for a matrix that does not conform or a change file that was not applied.

    Raises:
        RuntimeError: The sub-commands built and the registry's command table name different commands.

    """
    stray: list[str] = sorted(set(COMMANDS) ^ set(COMMAND_RULES))
    if stray:
        message: str = f"the registry's command table and the sub-commands built differ on {', '.join(stray)}"
        raise RuntimeError(message)
    args: argparse.Namespace = _parser().parse_args(argv)
    call: Call = Call(args, os.environ if environ is None else environ)
    command: str = call.required("command")
    try:
        require_role(command, role_of(call.environ))
        outcome: Outcome = COMMANDS[command](call)
    except ValueError as error:
        sys.stderr.write(f"{PROGRAM} {command}: {error}\n")
        return EXIT_REFUSED
    sys.stdout.write(json.dumps(outcome.result, ensure_ascii=False) + "\n")
    if outcome.status != EXIT_OK:
        sys.stderr.write(f"{PROGRAM} {command}: refused; see the problems on stdout\n")
    return outcome.status


if __name__ == "__main__":
    sys.exit(main())
