"""One repository's specification documents and its Story, as steps of the Epic's journal.

The span step plans one container per repository with its first step, the repository context.
That step gathers what the repository builds, writes the spec pack its spec sessions read
(``spec_pack``), and plans the rest as the kinds of entry the Story builds call for
(:func:`story_surfaces`): for a document the Story does not need, the script step that writes
it; for a frontend repository whose Story builds a UI item the UI bundle listing and the UI
design-source session, which runs together with the data-model session, then its normalization;
one ``api-specification-author`` session that writes the contracts, when the Story needs them,
and then the acceptance criteria, from the data model already written, which runs together with
the data-model access-pattern review for a repository whose stacks hold a DynamoDB store and
whose Story builds a data store; the UI section; the review; the Story document; and the Story
bead write. Each step takes
the files it reads from the artifacts of the steps its inputs name, and records what it writes
right after writing it.

What a repository's Story is handed about the architecture is the context file
(``spec-context.schema.json``), which names each stack the Story builds in with the entries it
builds there, the documents and headings ``atw-matrix story-scope`` names, and every architecture
and design document of the component the Story builds (``atw-matrix documents``); and the spec
pack (``spec-pack.schema.json``), which holds the constraints and TRD requirements that bind the
entries and the repository's contract files. A session reads the text of a heading the context
names with ``atw-matrix heading``, only when its work turns on it. The authors write specs: every design
detail was decided during architecture and is in those documents and the matrix.

What a spec covers for each entry comes from its verified state (``buildScope``), never from an
architecture delta: where the build is verified at the version before this Epic's change, the
spec covers that change alone; otherwise it covers all the work that brings the build up to the
entry's approved architecture. Every spec document ends with the links to the architecture and
design documents of the component it covers, written by :func:`story_document`.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "pipeline-contracts" / "scripts"))
import beadgraph
import beadwrite
import cdsbundles
import hierarchy
import specui
from matrix_contract import (
    KIND_COMPONENT,
    KIND_EVENT,
    KIND_FILE,
    KIND_INFRASTRUCTURE,
    KIND_LAYER,
    KIND_PACKAGE,
    KIND_SERVICE,
)
from matrixquery import documents_view, story_scope
from matrixstore import Matrix, as_entry_id, matrix_path, read_matrix
from recon_contract import KEY_MOCKS_DIR
from target_contract import KEY_ELEMENT, KEY_ID, KEY_MATRIX_ID, KEY_PUBLISHED_BY, KEY_TRIGGER
from typeguard import check_type

from orchestrator.core import step_journal
from orchestrator.core.agents import strict_json
from orchestrator.core.driver_contracts import DispatchArguments, dispatch_arguments
from orchestrator.core.handback_contract import OTHER_CAUSE
from orchestrator.core.io import JsonValue, json_object, write_json
from orchestrator.core.journal_changes import create_child_journal
from orchestrator.core.journal_registry import agent_step, script_step
from orchestrator.core.journal_steps import (
    UNDER_CONTAINER,
    AgentLaunch,
    Completion,
    NewStep,
    StepGroup,
    StepRun,
    file_artifact,
    value_artifact,
)
from orchestrator.core.models import StepError
from orchestrator.flows.architecture_files import ARTIFACT_TRD, read_context
from orchestrator.flows.elaboration_files import (
    ARTIFACT_ELEMENTS,
    ARTIFACT_SPAN,
    AUTHOR_CONTRACTS,
    AUTHOR_DATA_MODEL,
    CONTEXT,
    CRITERIA,
    DATA_MODEL,
    DATA_MODEL_REVIEWER,
    REPOSITORY,
    REVIEWER,
    SPEC,
    SPEC_CONTEXT,
    SPEC_CONTEXT_SCHEMA,
    SPEC_NOT_APPLICABLE,
    SPEC_PACK,
    SPEC_PACK_SCHEMA,
    STORY,
    STORY_DOCUMENT,
    STORY_DOCUMENT_SCHEMA,
    STORY_DOCUMENT_STEP,
    STORY_WRITE,
    TASK_CONTEXT,
    TASKS_CONTAINER,
    UI_APPEND,
    UI_BUNDLE_LIST,
    UI_BUNDLES,
    UI_BUNDLES_SCHEMA,
    UI_CANDIDATE,
    UI_NORMALIZE,
    UI_SELECTOR,
    UI_SOURCES,
    WARNINGS,
    WORK,
    Repository,
    control_repository,
    creating,
    handed_on,
    objects,
    project_root,
    repository,
    repository_of,
    span_files,
    story_files,
    strings,
    write_contract,
)
from orchestrator.flows.elaboration_support import SPEC_AUTHORING_PHASE, enter_phase
from orchestrator.flows.repo_scoping import BuildContext, build_context, item_stacks
from orchestrator.flows.spec_authoring_ui import normalize_ui
from orchestrator.flows.spec_pack import (
    contract_files,
    entry_rows,
    scope_bindings,
    trd_requirements,
)
from orchestrator.flows.trd_authoring import SPEC_FRONT_MATTER, document

# isort: split
# The journal modules put the pipeline-contracts scripts directory on sys.path.
from step_journal_contract import BEAD_TYPE_STORY, BeadId

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from matrix_contract import Entry, EntryId
    from matrixquery import Described, StoryScope
    from step_journal_contract import Artifact, Step, StepPlan

    from orchestrator.core.models import OutputValidator, ValidationResult

WORK_DOCUMENT: Final = "document"
"""What a step of an author agent, planned by the repository context step, does."""
KEY_RESOURCE_TYPE: Final = "resourceType"
DYNAMODB_RESOURCE_PREFIX: Final = "dynamodb-"
"""An infrastructure entry whose resource type starts with this prefix is a DynamoDB resource."""
DATA_STORE_RESOURCE_PREFIXES: Final[tuple[str, ...]] = (
    "dynamodb-",
    "rds-",
    "aurora-",
    "neptune-",
    "docdb-",
    "elasticache-",
    "memorydb-",
    "timestream-",
    "opensearch-",
    "keyspaces-",
    "redshift-",
)
"""An infrastructure entry whose resource type starts with one of these is a data store: the data model specifies it."""
INTERFACE_KINDS: Final[frozenset[str]] = frozenset({
    KIND_SERVICE,
    KIND_COMPONENT,
    KIND_EVENT,
    KIND_FILE,
    KIND_PACKAGE,
    KIND_LAYER,
})
"""The kinds of entry that expose or consume an API, event, error or UI contract, which the contracts specify."""
INTERFACE_RESOURCE_PREFIXES: Final[tuple[str, ...]] = (
    "rest-api",
    "websocket-api",
    "api-gateway-",
    "appsync-",
    "eventbridge-",
    "sqs-",
    "sns-",
    "bedrock-agentcore-gateway",
)
"""An infrastructure entry whose resource type starts with one of these carries an API or event contract."""
KEY_DOCUMENT: Final = "document"
"""The parameter that names the spec document a step records as not applicable."""
KEY_DOCUMENTS: Final = "documents"
"""The parameter that names the spec documents an author step works on, in the order it writes them:
by artifact name for the step that writes them, by document kind for a correction or a revision."""
NOT_APPLICABLE_SUBJECT: Final[dict[str, str]] = {
    SPEC: "API, event, error or UI contract",
    DATA_MODEL: "data store",
}
"""What a repository's Story builds none of, when its contracts or its data model is not applicable."""
DOCUMENT_TITLE: Final[dict[str, str]] = {SPEC: "Contracts", DATA_MODEL: "Data model"}
DECISION_IDS: Final = "decision ids"
KEY_STACKS: Final = "stacks"
"""The member of the repository context that lists the stacks the Story builds in, with their entries."""
STORY_SUMMARY: Final = "story write"
SUFFIX: Final[dict[str, str]] = {SPEC: ".md", DATA_MODEL: ".data-model.md", CRITERIA: ".criteria.md"}
OUTCOME: Final[dict[str, str]] = {
    SPEC: "The spec of the API, event and error contracts this repository's Story builds.",
    DATA_MODEL: "The spec of the data this repository's Story builds.",
    CRITERIA: "Acceptance criteria and definition of done for the saved specifications.",
}
"""What a session writes, for each spec document it works on."""
WRITTEN_AS: Final[dict[str, str]] = {SPEC: "the contracts", DATA_MODEL: "the data model", CRITERIA: "the criteria"}
"""How a request names each spec document."""
UI_SCHEMA: Final = "skills/artifact-handoff/schemas/spec-ui.schema.json"
CONTEXT_PURPOSE: Final = "The items this repository builds and the steps that specify them are known"
TASKS_PURPOSE: Final = "The Story has Tasks that name what to build"
SCOPE_DELTA: Final = "delta"
SCOPE_FULL: Final = "full"
"""What a spec covers for one entry: this Epic's change alone, or all the work that brings the build
up to the entry's approved architecture."""
KEY_BUILD_SCOPE: Final = "buildScope"
KEY_COMPONENT_DOCUMENTS: Final = "componentDocuments"
LINKS_HEADING: Final = "## Architecture and design documents"
"""The last section of every spec document: the links to the documents of the component it covers."""
DOCUMENT_ENTRY_KINDS: Final[frozenset[str]] = frozenset({"document"})
"""The kinds of the matrix entries that are architecture and design documents (arc42 and ``detailed/``)."""
STORY_KEY_PREFIX: Final = "S"
"""The prefix of a Story's key: the span keys its Stories ``S<n>`` in the order it names their repositories."""


@dataclass(frozen=True)
class Surfaces:
    """Which spec sessions a repository's Story needs, from the kinds of entry it builds."""

    contracts: bool
    """The Story builds an entry with an API, event, error or UI contract."""
    data_model: bool
    """The Story builds a data store."""
    ui: bool
    """The repository is a frontend repository and the Story builds a UI item."""


CRITERION_PREFIX: Final = "AC"
DONE_PREFIX: Final = "DOD"
_CRITERION_LINE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?[*`]*"
    r"(?P<id>(?:AC|DOD)-[A-Za-z0-9][A-Za-z0-9.-]*)[*`]*[:.]?\s*(?P<text>.*)$",
)
"""A list item that opens with a criterion id (``AC-<n>``) or a Definition of Done id (``DOD-<n>``)."""


def criteria_document(path: Path) -> None:
    """Require the structure of a criteria document that Tasks cite by id.

    Each acceptance criterion is a list item that opens with its id, ``AC-<n>``, and each
    Definition of Done statement one that opens with ``DOD-<n>``. The document holds at least one
    of each, every id once, every id followed by its statement, and a criterion that states a
    ``Given`` also states its ``When`` and ``Then``.

    Raises:
        ValueError: Every structural problem the document has, one per line.

    """
    seen: dict[str, int] = {}
    problems: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        found: re.Match[str] | None = _CRITERION_LINE.match(line)
        if found is None:
            continue
        criterion: str = found["id"]
        text: str = found["text"].strip()
        if criterion in seen:
            problems.append(
                f"line {number}: {criterion} is also the id on line {seen[criterion]}; give each its own id",
            )
        seen.setdefault(criterion, number)
        if not text:
            problems.append(f"line {number}: {criterion} states nothing after its id")
        elif re.search(r"\bGiven\b", text) and not (re.search(r"\bWhen\b", text) and re.search(r"\bThen\b", text)):
            problems.append(f"line {number}: {criterion} states a Given with no When and Then")
    for prefix, what in ((CRITERION_PREFIX, "acceptance criterion"), (DONE_PREFIX, "Definition of Done statement")):
        if not any(criterion.startswith(f"{prefix}-") for criterion in seen):
            problems.append(f"no {what}: each is a list item that opens with its id, {prefix}-<n>")
    if problems:
        message: str = f"the criteria document {path} is not structured as Tasks cite it:\n" + "\n".join(problems)
        raise ValueError(message)


def architecture_root(run: StepRun) -> Path:
    """Name the architecture root of the dispatch.

    Returns:
        The path the dispatch arguments give.

    """
    return Path(check_type(run.context.args[dispatch_arguments().KEY_ARCH_PATH], str)).resolve()


def design_system(run: StepRun) -> dict[str, JsonValue]:
    """Read the design system facts of the dispatch.

    Returns:
        The dispatch's design system argument; empty when it gives none.

    """
    return json_object(run.context.args.get(dispatch_arguments().KEY_DESIGN_SYSTEM) or {})


def document_file(run: StepRun, held: Repository, name: str) -> Path:
    """Name the file one spec document of a repository is written to.

    Returns:
        The file in the Epic's work directory.

    """
    return run.context.work / f"spec-{held.slug}{SUFFIX[name]}"


def document_check(run: StepRun, name: str) -> OutputValidator:
    """Give the check a spec document must pass each time its author has written it.

    Returns:
        The check: every architecture citation of the contracts and of the data model names a
        document and heading the matrix holds; the criteria document has the structure Tasks cite
        (:func:`criteria_document`).

    """
    if name == CRITERIA:
        return criteria_document
    matrix: Matrix = run.tools.portfolio(name, read_matrix, matrix_path(None, os.environ))
    return lambda path: document(path, matrix, SPEC_FRONT_MATTER)


def author_files(run: StepRun, names: Sequence[str]) -> tuple[tuple[str, Path], ...]:
    """Name the files an author session reads for the spec documents it works on.

    Args:
        run: The author step.
        names: The spec documents the session works on, by artifact name.

    Returns:
        The TRD, the span and the elements; the UI sources for the contracts of a frontend
        repository; for the criteria, the contracts and the data model the session does not
        itself write; then the repository context, which names the PRD, whose headings the TRD
        cites, and the architecture headings; and the spec pack, which holds the constraints and
        the TRD requirements the session reads.

    """
    files: list[tuple[str, Path]] = [
        (label, run.inputs.file(label)) for label in (ARTIFACT_TRD, ARTIFACT_SPAN, ARTIFACT_ELEMENTS)
    ]
    sources: Path | None = run.inputs.optional_file(UI_SOURCES)
    if SPEC in names and sources is not None:
        files.append((UI_SOURCES, sources))
    if CRITERIA in names:
        files.extend((label, run.inputs.file(label)) for label in (SPEC, DATA_MODEL) if label not in names)
    return (*files, (CONTEXT, run.inputs.file(CONTEXT)), (SPEC_PACK, run.inputs.file(SPEC_PACK)))


def author_dirs(run: StepRun, held: Repository) -> tuple[Path, ...]:
    """Name the directories an author session may read.

    Returns:
        The Epic's work directory, where the session writes, and the repository the Story builds
        in. The architecture documents and headings are named in the repository context.

    """
    return (run.context.work, Path(held.path))


def _step(  # ruff: ignore[too-many-arguments] - One plan field each.
    ref: str,
    description: str,
    purpose: str,
    inputs: list[str],
    *,
    agent: str | None = None,
    script: str | None = None,
    work: str | None = None,
    document: str | None = None,
    documents: Sequence[str] = (),
) -> NewStep:
    """Plan one step of a repository with the parameters that say what it does.

    Returns:
        The planned step; it is handed the planning step's artifacts with its parameters.

    """
    plan: StepPlan = {"ref": ref, "description": description, "purpose": purpose, "inputs": inputs}
    if agent is not None:
        plan["agent"] = agent
    if script is not None:
        plan["script"] = script
    params: dict[str, JsonValue] = {} if work is None else {WORK: work}
    if document is not None:
        params[KEY_DOCUMENT] = document
    if documents:
        params[KEY_DOCUMENTS] = list(documents)
    return NewStep(plan, params)


def _repository_steps(run: StepRun, held: Repository, surfaces: Surfaces, *, dynamodb: bool) -> StepGroup:
    """Plan every step of one repository that follows its context step.

    A spec document whose session the Story does not need (:func:`story_surfaces`) is written by
    a script step instead, which states that the Story builds nothing it would specify; those
    steps come first. The data-model session runs together with the UI design-source session.
    One ``api-specification-author`` session then writes the contracts, when the Story needs them,
    and the acceptance criteria, which are derived from the contracts and the data model, so it
    starts once the data model is written; the data-model access-pattern review runs together
    with it.

    Args:
        run: The context step.
        held: The repository.
        surfaces: The spec sessions the Story needs.
        dynamodb: Whether a stack the Story builds in holds a DynamoDB store, which plans the
            data-model access-pattern review beside the contracts and criteria session when the
            Story builds a data store.

    Returns:
        The steps in the order they run, after the context step.

    """
    name: str = Path(held.path).name
    upstream: list[str] = list(run.step.get("inputs", []))
    sources: list[str] = ["sources"] if surfaces.ui else []
    absent: list[NewStep] = [
        _step(
            ref,
            f"Record that {name} builds no {NOT_APPLICABLE_SUBJECT[document]}",
            f"The repository's {DOCUMENT_TITLE[document].lower()} document says it specifies nothing",
            [],
            script=SPEC_NOT_APPLICABLE,
            document=document,
        )
        for ref, document, needed in (
            ("contracts", SPEC, surfaces.contracts),
            ("data-model", DATA_MODEL, surfaces.data_model),
        )
        if not needed
    ]
    steps: list[NewStep] = list(absent)
    if surfaces.ui:
        steps.extend((
            _step(
                "bundles",
                f"List the UI bundles supplied for {name}",
                "The author knows the bundles",
                [],
                script=UI_BUNDLES,
            ),
            _step(
                "ui",
                f"Choose the UI design source of each UI item of {name}",
                "Every UI item has a design source",
                ["bundles", *upstream],
                agent=UI_SELECTOR,
            ),
        ))
    if surfaces.data_model:
        steps.append(
            _step(
                "data-model",
                f"Write the data model of {name}",
                "The repository's data model is specified",
                upstream,
                agent=AUTHOR_DATA_MODEL,
                work=WORK_DOCUMENT,
                documents=(DATA_MODEL,),
            ),
        )
    if surfaces.ui:
        steps.append(
            _step(
                "sources",
                f"Check the UI design sources of {name} against the supplied bundles",
                "Every design source can be built from",
                ["ui", "bundles"],
                script=UI_NORMALIZE,
            ),
        )
    contracts: list[str] = [] if surfaces.contracts else ["contracts"]
    steps.append(
        _step(
            "criteria",
            (
                f"Write the API, event and error contracts and the acceptance criteria of {name}"
                if surfaces.contracts
                else f"Write the acceptance criteria of {name}"
            ),
            "The repository's contracts are specified, and its work has criteria a test can be derived from",
            [*contracts, "data-model", *upstream, *sources],
            agent=AUTHOR_CONTRACTS,
            work=WORK_DOCUMENT,
            documents=(SPEC, CRITERIA) if surfaces.contracts else (CRITERIA,),
        ),
    )
    reviewed: list[str] = ["data-model-review"] if dynamodb and surfaces.data_model else []
    if reviewed:
        steps.append(
            _step(
                "data-model-review",
                f"Review the DynamoDB access patterns of the data model of {name}",
                "Every DynamoDB access pattern the data model states can be served as stated",
                ["data-model", *upstream],
                agent=DATA_MODEL_REVIEWER,
            ),
        )
    if surfaces.ui and surfaces.contracts:
        steps.append(
            _step(
                "ui-section",
                f"Add the UI design sources to the contracts of {name}",
                "The contracts name the design source of each UI item",
                ["criteria", "sources"],
                script=UI_APPEND,
            ),
        )
    documents: list[str] = [*contracts, "data-model", "criteria"]
    steps.extend((
        _step(
            "review",
            f"Review the specification documents of {name}",
            "Every finding against the implementation criteria is settled",
            [*documents, *reviewed, *upstream],
            agent=REVIEWER,
        ),
        _step(
            "story",
            f"Write the Story document of {name}",
            "The Story names the repository, its items and its specifications",
            documents,
            script=STORY_DOCUMENT_STEP,
        ),
        _step(
            "story-bead",
            f"Write the Story bead of {name}",
            "The Epic has one Story for this repository",
            ["story", *documents, *upstream, *sources],
            script=STORY_WRITE,
        ),
    ))
    return StepGroup(tuple(steps))


def _resource_type(entry: Entry) -> str:
    """Read an entry's resource type.

    Returns:
        The type; empty when the entry has none.

    """
    held: JsonValue = entry.attributes.get(KEY_RESOURCE_TYPE)
    return held if isinstance(held, str) else ""


def story_surfaces(matrix: Matrix, entries: Sequence[EntryId], *, frontend: bool) -> Surfaces:
    """Decide which spec sessions a repository's Story needs, from the kinds of entry it builds.

    Args:
        matrix: The matrix.
        entries: The entries the Story builds.
        frontend: Whether the repository is a frontend repository.

    Returns:
        Contracts when the Story builds an entry of an interface kind (:data:`INTERFACE_KINDS`)
        or infrastructure whose resource type carries an API or event contract; a data model
        when it builds infrastructure whose resource type is a data store; the UI design sources
        when the repository is a frontend repository and the Story builds a component that is
        no AWS resource (a page, a shell, a view or a component they show). An entry the matrix
        does not hold calls for every session.

    """
    found: list[Entry | None] = [matrix.find(entry_id) for entry_id in entries]
    unknown: bool = any(entry is None for entry in found)
    held: list[Entry] = [entry for entry in found if entry is not None]
    infrastructure: list[str] = [_resource_type(entry) for entry in held if entry.kind == KIND_INFRASTRUCTURE]
    interface: bool = any(entry.kind in INTERFACE_KINDS for entry in held) or any(
        kind.startswith(INTERFACE_RESOURCE_PREFIXES) for kind in infrastructure
    )
    store: bool = any(kind.startswith(DATA_STORE_RESOURCE_PREFIXES) for kind in infrastructure)
    ui: bool = any(entry.kind == KIND_COMPONENT and not _resource_type(entry) for entry in held)
    return Surfaces(contracts=unknown or interface, data_model=unknown or store, ui=frontend and (unknown or ui))


def _scope_documents(arch: Path, scopes: Sequence[StoryScope]) -> list[JsonValue]:
    """List the architecture documents some story scopes name, each with the headings to read.

    Returns:
        One row per document, in id order: its entry id, its file under the architecture root,
        and the headings the scopes name in it (none when a scope names the document as a whole).

    """
    headings: dict[EntryId, dict[str, None]] = {}
    scope: StoryScope
    for scope in scopes:
        described: list[Described] = [
            *scope["documents"],
            *(found for built in scope["entries"] for found in built["documents"]),
            *(found for binding in scope["constraints"] for found in binding["statedIn"]),
        ]
        for found in described:
            named: dict[str, None] = headings.setdefault(found["document"], {})
            if found["heading"]:
                named[found["heading"]] = None
    rows: list[JsonValue] = []
    for identifier in sorted(headings):
        listed: list[JsonValue] = list(headings[identifier])
        rows.append({
            "document": identifier,
            "path": str(arch / identifier.partition(":")[2]),
            "headings": listed,
        })
    return rows


def entry_scope(matrix: Matrix, entry_id: EntryId) -> dict[str, JsonValue]:
    """Decide what a spec covers for one entry the Story builds, from its verified state.

    Args:
        matrix: The matrix.
        entry_id: The entry.

    Returns:
        The entry, whether it carries the verified mark, and its scope: ``delta`` when it
        is verified, so nothing it must be built as has changed since its last build and test and
        the spec covers this Epic's own work for it alone; ``full`` when it is not verified (a
        change cleared the flag, or it was never built), so the spec covers all the work that
        brings the build up to the entry's approved architecture.

    """
    found: Entry | None = matrix.find(entry_id)
    verified: bool = found is not None and found.verified
    return {
        "entry": entry_id,
        "verified": verified,
        "scope": SCOPE_DELTA if verified else SCOPE_FULL,
    }


def component_documents(arch: Path, matrix: Matrix, ids: Sequence[EntryId]) -> list[JsonValue]:
    """List every architecture and design document of the component a Story builds.

    Args:
        arch: The architecture root.
        matrix: The matrix.
        ids: The stacks the Story builds in and the entries it builds there.

    Returns:
        Each document any of them, or anything that belongs to them, is joined to
        (``atw-matrix documents``), once, in id order, with its file under the architecture root.

    """
    found: dict[str, None] = {}
    entry_id: EntryId
    for entry_id in ids:
        view: dict[str, JsonValue] = json_object(documents_view(matrix, entry_id))
        found.update(
            dict.fromkeys(
                check_type(document["id"], str)
                for document in objects(view["documents"])
                if document["kind"] in DOCUMENT_ENTRY_KINDS
            ),
        )
    return [{"document": identifier, "path": str(arch / identifier.partition(":")[2])} for identifier in sorted(found)]


def link_documents(path: Path, documents: Sequence[Mapping[str, JsonValue]]) -> None:
    """End a spec document with the links to the architecture and design documents of its component.

    A section written earlier is replaced, so a rerun writes it once.

    Args:
        path: The spec document.
        documents: The component's documents, as the repository context lists them.

    """
    text: str = path.read_text(encoding="utf-8")
    kept: str = text.split(f"\n{LINKS_HEADING}\n", 1)[0].rstrip()
    links: list[str] = [f"- [{document['document']}]({document['path']})" for document in documents]
    body: list[str] = links or ["- The matrix records no architecture or design document for this component."]
    path.write_text("\n".join((kept, "", LINKS_HEADING, "", *body, "")), encoding="utf-8")


def items_by_story(every_build: Mapping[str, JsonValue]) -> dict[str, list[JsonValue]]:
    """Group what every Story of the Epic builds by the Story's key.

    The span plans one Story per repository, keyed ``S<n>`` in the order its placements name the
    repositories; the items of what the Stories build list the repositories in that order.

    Args:
        every_build: What every Story builds (``hierarchy.story_builds``), by item id.

    Returns:
        Each storyKey with the items of what its Story builds.

    """
    slugs: list[str] = list(dict.fromkeys(str(json_object(item)["slug"]) for item in every_build.values()))
    keys: dict[str, str] = {slug: f"{STORY_KEY_PREFIX}{index}" for index, slug in enumerate(slugs, 1)}
    grouped: dict[str, list[JsonValue]] = {key: [] for key in keys.values()}
    for item in every_build.values():
        grouped[keys[str(json_object(item)["slug"])]].append(item)
    return grouped


def holds_dynamodb(matrix: Matrix, stacks: Collection[EntryId]) -> bool:
    """Tell whether any of some stacks holds a DynamoDB store.

    Args:
        matrix: The matrix.
        stacks: The stacks a Story builds in.

    Returns:
        True when an infrastructure entry whose home is one of the stacks has a resource type
        of DynamoDB (``dynamodb-table``, for example).

    """
    held: frozenset[EntryId] = frozenset(stacks)
    return any(
        isinstance(kind := entry.attributes.get(KEY_RESOURCE_TYPE), str)
        and kind.startswith(DYNAMODB_RESOURCE_PREFIX)
        and matrix.home(entry.id) in held
        for entry in matrix.entries((KIND_INFRASTRUCTURE,))
    )


def story_context(matrix: Matrix, built: Sequence[JsonValue], every_build: Mapping[str, JsonValue]) -> BuildContext:
    """List what a Story depends on.

    Args:
        matrix: The matrix.
        built: The items of what this Story builds.
        every_build: What every Story of the Epic builds, by item id.

    Returns:
        ``repo_scoping.build_context`` for the Story.

    """
    return build_context(matrix, built, items_by_story(every_build))


def _write_pack(
    run: StepRun,
    held: Repository,
    matrix: Matrix,
    *,
    ids: Sequence[EntryId],
    scopes: Sequence[StoryScope],
) -> Path:
    """Write one repository's spec pack (``spec-pack.schema.json``) beside its context file.

    Args:
        run: The context step.
        held: The repository.
        matrix: The matrix.
        ids: The stacks the Story builds in and the entries it builds there.
        scopes: The story scopes of those stacks.

    Returns:
        The pack's file.

    """
    constraints: list[JsonValue]
    capabilities: list[JsonValue]
    constraints, capabilities = run.tools.portfolio(SPEC_CONTEXT, scope_bindings, scopes)
    trd: Path = run.inputs.file(ARTIFACT_TRD)
    requirements: list[JsonValue] = run.tools.portfolio(
        SPEC_CONTEXT,
        trd_requirements,
        matrix,
        str(run.bead),
        trd.read_text(encoding="utf-8"),
        constraints,
    )
    files: list[JsonValue] = list(run.tools.portfolio(SPEC_CONTEXT, contract_files, Path(held.path)))
    return write_contract(
        run.context.work / f"spec-{held.slug}.pack.json",
        {
            "epic": str(run.bead),
            "repoPath": held.path,
            "slug": held.slug,
            "entries": run.tools.portfolio(SPEC_CONTEXT, entry_rows, matrix, ids),
            "constraints": constraints,
            "capabilities": capabilities,
            "trd": {"path": str(trd), "requirements": requirements},
            "contractFiles": files,
        },
        SPEC_PACK_SCHEMA,
    )


@script_step(SPEC_CONTEXT)
def context(run: StepRun) -> Completion:
    """Gather what one repository builds, and plan the steps that specify it.

    The context file (``spec-context.schema.json``) holds pointers, never a copy of what the
    matrix or the architect's result holds: each stack the Story builds in with the entries it
    builds there, for the author's own ``atw-matrix story-scope`` and ``atw-matrix uses``; the
    documents and headings those story scopes name; what the spec covers for each entry
    (:func:`entry_scope`); every architecture and design document of the component
    (:func:`component_documents`); what the Story depends on outside what it
    builds (``repo_scoping.build_context``), as ids with their stack and repository; and the
    paths of the PRD and of the architect's result, whose ``facts`` name the documents that hold
    the design the authors carry.

    Beside it the step writes the spec pack (``spec-pack.schema.json``), what the spec sessions
    read instead of the vault and the matrix: the entries with their approved owners, the text
    of every heading the context's ``documents`` name as the vault's last commit holds it, the
    constraints and shared capabilities that bind the entries, the TRD requirements that bind
    them and the contract files the repository holds. It plans the spec sessions the Story's
    entries call for (:func:`story_surfaces`).

    Returns:
        The repository, its context file and its spec pack as artifacts, with the repository's
        other steps planned after this one.

    Raises:
        StepError: The span places no item in the repository, the matrix cannot answer for its
            entries, or the solutions architect's result cannot be read.

    """
    held: Repository = repository_of(dict(run.params()), SPEC_CONTEXT)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, SPEC_CONTEXT, held.path)
    dispatch: DispatchArguments = dispatch_arguments()
    every_build: dict[str, JsonValue] = json_object(
        run.tools.portfolio(SPEC_CONTEXT, hierarchy.story_builds, span_files(run.inputs)),
    )
    items: list[JsonValue] = [item for item in every_build.values() if json_object(item)["slug"] == held.slug]
    if not items:
        raise StepError(SPEC_CONTEXT, OTHER_CAUSE, (f"the span places no item in {held.path}",))
    matrix: Matrix = run.tools.portfolio(SPEC_CONTEXT, read_matrix, matrix_path(None, os.environ))
    stacks: dict[EntryId, list[EntryId]] = run.tools.portfolio(SPEC_CONTEXT, item_stacks, matrix, items)
    scopes: list[StoryScope] = [
        run.tools.portfolio(SPEC_CONTEXT, story_scope, matrix, stack, built) for stack, built in stacks.items()
    ]
    depended: BuildContext = run.tools.portfolio(SPEC_CONTEXT, story_context, matrix, items, every_build)
    prd: Path = Path(check_type(json_object(run.context.args[dispatch.KEY_PRD])[dispatch.PRD_PATH], str)).resolve()
    stacked: list[JsonValue] = [{"stack": stack, "entries": list(built)} for stack, built in stacks.items()]
    entries: list[EntryId] = list(dict.fromkeys(entry for built in stacks.values() for entry in built))
    scoped: list[JsonValue] = [entry_scope(matrix, entry) for entry in entries]
    component: list[JsonValue] = component_documents(architecture_root(run), matrix, [*stacks, *entries])
    documents: list[JsonValue] = _scope_documents(architecture_root(run), scopes)
    path: Path = write_contract(
        run.context.work / f"spec-{held.slug}.context.json",
        {
            "epic": str(run.bead),
            "repoPath": held.path,
            "slug": held.slug,
            "frontend": held.frontend,
            "items": items,
            KEY_STACKS: stacked,
            "documents": documents,
            KEY_BUILD_SCOPE: scoped,
            KEY_COMPONENT_DOCUMENTS: component,
            "dependsOn": [json_object(dependency) for dependency in depended["dependsOn"]],
            "prd": str(prd),
            "architectureResult": str(Path(read_context(run)["resultPath"]).resolve()),
            dispatch.KEY_DESIGN_SYSTEM: design_system(run),
        },
        SPEC_CONTEXT_SCHEMA,
    )
    return Completion(
        artifacts=(
            value_artifact(REPOSITORY, held.facts()),
            file_artifact(CONTEXT, path),
            file_artifact(
                SPEC_PACK,
                _write_pack(run, held, matrix, ids=[*stacks, *entries], scopes=scopes),
            ),
        ),
        add=(
            _repository_steps(
                run,
                held,
                run.tools.portfolio(SPEC_CONTEXT, story_surfaces, matrix, entries, frontend=held.frontend),
                dynamodb=run.tools.portfolio(SPEC_CONTEXT, holds_dynamodb, matrix, list(stacks)),
            ),
        ),
    )


@script_step(SPEC_NOT_APPLICABLE)
def not_applicable(run: StepRun) -> Completion:
    """Write the contracts or the data model of a repository whose Story builds nothing it specifies.

    The document has the front matter every spec document has, with no citation, and lists what
    the Story builds, so the criteria, the review and the Story read it as they read an authored
    one.

    Returns:
        The document, recorded under its artifact name.

    Raises:
        StepError: The step names no document a script writes in place of a session.

    """
    held: Repository = repository(run.inputs)
    name: JsonValue = run.params().get(KEY_DOCUMENT)
    if not isinstance(name, str) or name not in NOT_APPLICABLE_SUBJECT:
        raise StepError(SPEC_NOT_APPLICABLE, OTHER_CAUSE, (f"no spec document a script writes: {name!r}",))
    built: list[dict[str, JsonValue]] = objects(strict_json(run.inputs.file(SPEC_PACK))["entries"])
    lines: list[str] = [
        "---",
        "decisionIds: []",
        "---",
        "",
        f"# {DOCUMENT_TITLE[name]} of {Path(held.path).name}",
        "",
        f"This repository's Story builds no {NOT_APPLICABLE_SUBJECT[name]}, so this document specifies none.",
        "What the Story builds:",
        "",
        *(
            f"- {entry['id']} ({', '.join(str(entry[key]) for key in ('kind', 'resourceType') if entry[key])})"
            for entry in built
        ),
        "",
    ]
    path: Path = document_file(run, held, name)
    path.write_text("\n".join(lines), encoding="utf-8")
    return Completion(artifacts=(file_artifact(name, path),))


@script_step(UI_BUNDLES)
def bundles(run: StepRun) -> Completion:
    """List the UI bundles the owner supplied, for the author that chooses design sources.

    Returns:
        The listing file.

    """
    held: Repository = repository(run.inputs)
    dispatch: DispatchArguments = dispatch_arguments()
    packages: str | None = check_type(design_system(run).get(dispatch.DS_PACKAGES_DIR), str | None)
    listed: dict[str, JsonValue] = json_object(run.tools.portfolio(UI_BUNDLES, cdsbundles.list_bundles, packages))
    path: Path = write_contract(run.context.work / f"spec-{held.slug}.bundles.json", listed, UI_BUNDLES_SCHEMA)
    return Completion(artifacts=(file_artifact(UI_BUNDLE_LIST, path),))


@agent_step(UI_SELECTOR)
def ui_sources(run: StepRun) -> AgentLaunch:
    """Build the session that chooses the design source of each UI item of a frontend repository.

    Returns:
        The launch: the choices as the selector wrote them, checked against the spec-ui schema.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, UI_SELECTOR, held.path)

    def accept(_accepted: StepRun, output: Path) -> Completion:
        return Completion(artifacts=(file_artifact(UI_CANDIDATE, output),))

    return AgentLaunch(
        output=run.context.work / "candidates" / f"spec-{held.slug}.ui.json",
        validate=run.tools.plugin / UI_SCHEMA,
        outcome="UI design sources for what this repository's Story builds.",
        accept=accept,
        add_dirs=author_dirs(run, held),
        files=(
            *((label, run.inputs.file(label)) for label in (ARTIFACT_TRD, ARTIFACT_SPAN, ARTIFACT_ELEMENTS)),
            (UI_BUNDLE_LIST, run.inputs.file(UI_BUNDLE_LIST)),
            (CONTEXT, run.inputs.file(CONTEXT)),
        ),
        hand_inputs=False,
    )


@script_step(UI_NORMALIZE)
def normalize(run: StepRun) -> Completion:
    """Keep the UI choices of what the Story builds and replace a bundle that cannot be built from.

    Returns:
        The UI sources file, and the warnings the normalization raised.

    """
    held: Repository = repository(run.inputs)
    every_build: set[str] = {
        check_type(item[KEY_ID], str) for item in objects(strict_json(run.inputs.file(CONTEXT))["items"])
    }
    normalized: dict[str, JsonValue] = normalize_ui(
        strict_json(run.inputs.file(UI_CANDIDATE)),
        every_build,
        strict_json(run.inputs.file(UI_BUNDLE_LIST)),
        run.tools,
    )
    normalized[KEY_MOCKS_DIR] = design_system(run).get(dispatch_arguments().DS_MOCKS_DIR)
    path: Path = run.context.work / f"spec-{held.slug}.ui.json"
    write_json(path, normalized)
    return Completion(artifacts=(file_artifact(UI_SOURCES, path), value_artifact(WARNINGS, normalized["warnings"])))


def author_documents(run: StepRun) -> list[str]:
    """Name the spec documents an author step works on.

    Returns:
        The documents the planning step named, by artifact name, in the order they are written.

    Raises:
        StepError: The step names no spec document.

    """
    named: JsonValue = run.params().get(KEY_DOCUMENTS)
    if not isinstance(named, list) or not named or any(name not in SUFFIX for name in named):
        evidence: str = f"step {run.step['id']} names no spec document to work on: {named!r}"
        raise StepError(run.inputs.stage, OTHER_CAUSE, (evidence,))
    return [check_type(name, str) for name in named]


def documents_check(run: StepRun, held: Repository, names: Sequence[str]) -> OutputValidator:
    """Give the check every spec document a session works on must pass each time it has written them.

    Returns:
        A check that runs :func:`document_check` on each document's file, whichever path it is
        called with, and returns the citations and warnings of the documents that have them.

    """
    checks: list[tuple[Path, OutputValidator]] = [
        (document_file(run, held, name), document_check(run, name)) for name in names
    ]

    def check(_output: Path) -> tuple[list[str], list[str]] | None:
        cited: list[str] = []
        warned: list[str] = []
        found: bool = False
        for path, single in checks:
            result: ValidationResult = single(path)
            if isinstance(result, tuple):
                found = True
                cited.extend(result[0])
                warned.extend(result[1])
        return (cited, warned) if found else None

    return check


def spec_document(run: StepRun) -> AgentLaunch:
    """Build the session that writes the spec documents an author step names, in order.

    The data-model author writes the data model. The contracts author writes the contracts, when
    the Story needs them, and then the acceptance criteria, in one session, so the criteria are
    written by the session that knows the contracts; the session's output is the last document it
    writes, and the request names the path of each. The documents' citations stay in the documents
    and on the Story (``decisionIds``); nothing is recorded in the matrix, whose architecture side
    only arc42 and the architect write.

    Returns:
        The launch: the last document at its file in the work directory, with every document's check.

    """
    held: Repository = repository(run.inputs)
    names: list[str] = author_documents(run)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, "-".join(names), held.path)

    def accept(_accepted: StepRun, _output: Path) -> Completion:
        return Completion(artifacts=tuple(file_artifact(name, document_file(run, held, name)) for name in names))

    written: str = "; then ".join(f"{WRITTEN_AS[name]} at {document_file(run, held, name)}" for name in names)
    return AgentLaunch(
        output=document_file(run, held, names[-1]),
        validate=documents_check(run, held, names),
        outcome=" ".join(OUTCOME[name] for name in names),
        accept=accept,
        add_dirs=author_dirs(run, held),
        files=author_files(run, names),
        request=f"{run.step['description']}. Write {written}.",
        hand_inputs=False,
    )


@script_step(UI_APPEND)
def ui_section(run: StepRun) -> Completion:
    """Write the UI design sources section at the end of a frontend repository's contracts.

    Returns:
        The contracts document, which now names the design source of each UI item.

    """
    spec: Path = run.inputs.file(SPEC)
    run.tools.portfolio(UI_APPEND, specui.spec_ui_append, spec, run.inputs.file(UI_SOURCES))
    return Completion(artifacts=(file_artifact(SPEC, spec),))


def built_line(item: Mapping[str, JsonValue], names: Mapping[str, str], matrix: Matrix) -> str:
    """Render one thing a Story builds, as its Story document lists it.

    An event that names no publisher or no trigger raises ``ValueError`` from
    ``hierarchy.event_text``.

    Args:
        item: The item, as the repository context lists it.
        names: The name of each item of the Story, by item id.
        matrix: The matrix, which gives the purpose of an item that is not an event.

    Returns:
        For an event (an item with a ``trigger``), ``<id>: <name>, published by <publishers>
        when <trigger>``; for any other item, ``<id>: <name>: <purpose>``, or ``<id>: <name>``
        when the matrix gives it no purpose.

    """
    item_id: str = check_type(item[KEY_ID], str)
    name: str = check_type(item[KEY_ELEMENT], str)
    trigger: JsonValue = item.get(KEY_TRIGGER)
    if isinstance(trigger, str):
        published_by: list[str] = strings(item.get(KEY_PUBLISHED_BY) or [])
        return hierarchy.event_text(item_id, name, hierarchy.publisher_names(published_by, names), trigger)
    matrix_id: JsonValue = item.get(KEY_MATRIX_ID)
    found: Entry | None = matrix.find(as_entry_id(matrix_id)) if isinstance(matrix_id, str) else None
    purpose: str = "" if found is None else found.purpose.strip()
    return f"{item_id}: {name}: {purpose}" if purpose else f"{item_id}: {name}"


@script_step(STORY_DOCUMENT_STEP)
def story_document(run: StepRun) -> Completion:
    """Write the Story document of one repository from its reviewed spec documents.

    Each spec document first gets its last section, the links to the architecture and design
    documents of the component it covers (:func:`link_documents`), once every correction is made.

    Returns:
        The Story document and the architecture citations its Story carries.

    """
    held: Repository = repository(run.inputs)
    dispatch: DispatchArguments = dispatch_arguments()
    matrix: Matrix = run.tools.portfolio(STORY_DOCUMENT_STEP, read_matrix, matrix_path(None, os.environ))
    documents: list[Path] = [run.inputs.file(name) for name in (SPEC, DATA_MODEL, CRITERIA)]
    held_context: dict[str, JsonValue] = json_object(strict_json(run.inputs.file(CONTEXT)))
    component: list[dict[str, JsonValue]] = objects(held_context[KEY_COMPONENT_DOCUMENTS])
    for written in documents:
        link_documents(written, component)
    citations: list[str] = list(
        dict.fromkeys(
            value.strip()
            for path in documents[:2]
            for value in document(path, matrix, SPEC_FRONT_MATTER)[0]
            if value.strip()
        ),
    )
    prd: dict[str, JsonValue] = json_object(run.context.args[dispatch.KEY_PRD])
    items: list[dict[str, JsonValue]] = objects(held_context["items"])
    names: dict[str, str] = {check_type(item[KEY_ID], str): check_type(item[KEY_ELEMENT], str) for item in items}
    lines: list[str] = [
        f"Repository: {held.path}",
        "",
        "What the Story builds:",
        *(f"- {built_line(item, names, matrix)}" for item in items),
        "",
        "Specifications:",
        *(f"- {path}" for path in documents),
        "",
        "Architecture and design documents:",
        *(f"- {document['path']}" for document in component),
    ]
    decisions: list[JsonValue] = list(citations)
    path: Path = write_contract(
        run.context.work / f"story-{held.slug}.json",
        {
            "title": f"{Path(held.path).name}: {prd.get(dispatch.PRD_TITLE) or run.bead}",
            "description": "\n".join(lines),
            "decisionIds": decisions,
        },
        STORY_DOCUMENT_SCHEMA,
    )
    return Completion(artifacts=(file_artifact(STORY_DOCUMENT, path), value_artifact(DECISION_IDS, decisions)))


def _task_steps(run: StepRun, held: Repository) -> StepGroup:
    """Plan the Tasks container of one repository with its first step.

    Returns:
        The container, under the Tasks container, named for the repository; its context step is
        handed everything the repository's spec steps recorded.

    """
    name: str = Path(held.path).name
    specified: Step | None = step_journal.parent_step(run.journal(), run.step["id"])
    handed: list[str] = [] if specified is None else [specified["id"]]
    first: StepPlan = {
        "description": f"Gather what the Tasks of {name} are decomposed from",
        "purpose": "The decomposer knows the items, the Tasks that exist and the steps that follow",
        "script": TASK_CONTEXT,
        "inputs": [*handed, *run.step.get("inputs", [])],
    }
    container: StepPlan = {"description": name, "purpose": TASKS_PURPOSE}
    return StepGroup(
        (NewStep(container, children=(NewStep(first, held.facts()),)),),
        UNDER_CONTAINER,
        run.step_named(TASKS_CONTAINER)["id"],
    )


@script_step(STORY_WRITE)
def story_bead(run: StepRun) -> Completion:
    """Write the Story bead of one repository, create its journal, and plan its Tasks.

    The Story is found by its elaboration key under the Epic, so a second run of this step
    refreshes the Story it wrote and creates no other.

    Returns:
        The Story as the dispatch reports it and the write's summary; the repository's Tasks
        container is planned under the Tasks container.

    """
    held: Repository = repository(run.inputs)
    enter_phase(run.context, run.agents.emit, SPEC_AUTHORING_PHASE, STORY_WRITE, held.path)
    files: hierarchy.StoryFiles = story_files(run.inputs)
    control: Path = control_repository()

    def attempt() -> dict[str, JsonValue]:
        graph: beadgraph.Graph = run.tools.portfolio(STORY_WRITE, beadgraph.load, control, with_description=True)
        writer: beadgraph.Writer = run.tools.portfolio(STORY_WRITE, beadgraph.Writer, control)
        return json_object(
            run.tools.portfolio(
                STORY_WRITE,
                beadwrite.write_story,
                graph,
                writer,
                run.bead,
                files,
                root=project_root(),
            ),
        )

    written: dict[str, JsonValue] = run.tools.operation(STORY_WRITE, attempt)
    bead: dict[str, JsonValue] = json_object(written["story"])
    identifier: str = check_type(bead["id"], str)
    story: dict[str, JsonValue] = {
        "key": held.story_key,
        "type": "story",
        "id": identifier,
        "elabKey": bead["elabKey"],
        "title": bead["title"],
        "descriptionPath": f"{files.story}#/description",
        "repoPath": held.path,
        "parentEpicKey": run.bead,
    }
    handed: list[Artifact] = handed_on(run.inputs)
    create_child_journal(run.journal_path.parent, BeadId(identifier), BEAD_TYPE_STORY, [creating(run)], handed)
    carried: list[JsonValue] = list(strings(bead["decisionIds"]))
    return Completion(
        artifacts=(
            value_artifact(STORY, story),
            value_artifact(STORY_SUMMARY, written["summary"]),
            value_artifact(DECISION_IDS, carried),
        ),
        add=(_task_steps(run, held),),
    )
