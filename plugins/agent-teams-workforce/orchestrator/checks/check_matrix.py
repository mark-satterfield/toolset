"""Quick checks of the matrix: its contract, its behaviour, its command and how it is loaded.

Pure checks against a temporary vault (a git repository made here) and temporary files; no
workflow, flow, tracker or real vault is touched. They cover: the generated contract is current
with its schema and the schema's vocabularies and tables agree with the generated values; the
carry-over of a small element matrix; reading changed documents only, and what an edit, a revert
and a deletion mark; PRD rows; every read; what the consistency rules and the roles refuse; two
processes writing at once, each loading the store by file path; and every sub-command of
bin/atw-matrix run as a subprocess from another directory.
"""

import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs this interpreter, git and the plugin's own command with fixed argv, no shell.
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator
from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "portfolio"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "artifact-handoff" / "scripts"))
import matrix as command
import matrixcarry
import matrixquery
import matrixstore
import matrixsync
from matrix_contract import (
    APPROVAL_APPROVED,
    APPROVAL_CHANGED_SINCE_APPROVAL,
    APPROVAL_UNVERIFIED,
    CODE_BUILT,
    CODE_DEPLOYED,
    COMMAND_RULES,
    COVERAGE_APPROVED,
    COVERAGE_NOT_ASSESSED,
    DISAGREEMENT_APPLIED,
    DISAGREEMENT_SETTLED,
    FACT_RULE,
    FEATURE_PRD,
    KIND_DISAGREEMENT,
    KIND_DOCUMENT,
    KIND_FACT,
    KIND_FEATURE,
    KIND_LAYER,
    KIND_PRD,
    KIND_SERVICE,
    KIND_TERM,
    KINDS,
    LIFECYCLE_RETIRED,
    LINK_DESCRIBED_BY,
    LINK_NEEDS,
    LINK_REALIZED_BY,
    LINK_RULES,
    LINK_TYPES,
    LINK_USES,
    ROLE_ENV,
    ROLE_SCRIPT,
    ROLE_SOLUTIONS_ARCHITECT,
    ROLES,
    ApprovalState,
    DocumentsSyncedAt,
    JsonValue,
    Matrix,
    MatrixError,
    Node,
    NodeId,
    json_value,
    load_schema,
)
from orchestrator.checks.check_support import expected_error, report, require

PLUGIN: Path = Path(__file__).resolve().parents[2]
STORE: Path = PLUGIN / "scripts" / "portfolio" / "matrixstore.py"
COMMAND: Path = PLUGIN / "bin" / "atw-matrix"
GENERATOR: Path = PLUGIN / "skills" / "artifact-handoff" / "scripts" / "generate_matrix_contract.py"
ARCH: Path = Path("docs") / "tech" / "architecture"
SDLC: Path = Path("docs") / "sdlc"
PRD: Path = SDLC / "mvp" / "prds" / "myagent-proof.md"
CHASSIS: str = "docs/tech/architecture/arc42/05-building-block-view/chassis.md"
EVENTS: str = "docs/tech/architecture/arc42/08-crosscutting-concepts/events.md"
CONSTRAINTS: str = "docs/tech/architecture/arc42/02-architecture-constraints/README.md"
BEAD: str = "ssbd-check1"
STAMP: matrixstore.Stamp = matrixstore.Stamp("2026-01-01T00:00:00Z", "check")
LIB: str = "shared-chassis-lib"
AUTH: str = "skillspoke-auth-service"
AUTH_NAME: str = "SkillSpoke-auth-service"
OLD_ROWS: int = 8
SHOWN_RESOLVED: int = 3
SMALL_ROWS: int = 3
SMALL_MATRIX_ROWS: int = 12
"""Three carried rows, a service, three documents, four terms and a PRD."""
WRITES_EACH: int = 6
LAYER: NodeId = NodeId(f"layer:{LIB}/{LIB}/{LIB}")
PUBLISHER: NodeId = NodeId(f"component:{LIB}/@repository/eventpublisher")
TOKENS: NodeId = NodeId(f"infrastructure:{AUTH}/{AUTH}/proof tokens")
HANDLER: NodeId = NodeId(f"component:{AUTH}/{AUTH}/sign-in handler")
CAPABILITY: NodeId = NodeId(f"feature:{LIB}")
FEATURE: NodeId = NodeId("feature:address proof")
FACT: NodeId = NodeId("fact:proof secrets are hashed")
EVENTS_ROW: NodeId = matrixstore.make_id(KIND_DOCUMENT, EVENTS)
PRD_ROW: NodeId = matrixstore.make_id(KIND_PRD, BEAD)
WRITER: str = """
import importlib.util
import sys
from pathlib import Path

name = "_atw_matrixstore_by_path"
spec = importlib.util.spec_from_file_location(name, sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)


def add(matrix, index):
    key = f"term:{sys.argv[3]} {index}"
    change = {"at": module.timestamp(), "by": "sync"}
    matrix["nodes"][key] = {"id": key, "kind": "term", "name": key, "links": [], "changed": change}


for index in range(int(sys.argv[4])):
    module.update_matrix(Path(sys.argv[2]), lambda matrix, index=index: add(matrix, index))
"""
DOCUMENTS: dict[str, str] = {
    CONSTRAINTS: "---\nlifecycle_state: effective\n---\n# Constraints\n\n## Idempotency\n\nUse the chassis.\n",
    CHASSIS: (
        "---\nlifecycle_state: effective\nview_type: module diagram\nscope: component\n"
        'subject: "Shared Chassis"\nshows:\n  - "shared-chassis-lib"\n  - "EventPublisher"\n  - "Job seeker"\n---\n'
        "# Shared Chassis\n\n## Responsibility\n\nOne handler shape.\n\n## Notes\n\nFirst.\n\n## Notes\n\nSecond.\n"
    ),
    EVENTS: (
        "---\nlifecycle_state: effective\nshows: [proof tokens, SkillSpoke-auth-service]\n---\n# Events\n\n"
        "## Proof tokens\n\nProof secrets are stored only as hashes.\n\n```\n# not a heading\n```\n"
    ),
    PRD.as_posix(): "# Address proof\n\nThe seeker proves the address.\n",
}
TYPE_MAP: dict[str, JsonValue] = {
    "version": 1,
    "resourceTypes": {
        "package-component": {"kind": "component", "resourceType": "package-component"},
        "lambda-layer": {"kind": "layer", "resourceType": "lambda-layer"},
        "table": {"kind": "infrastructure", "resourceType": "dynamodb-table"},
    },
    "rows": {f"element:{AUTH}/{AUTH}/sign-in handler": {"kind": "component", "resourceType": "handler"}},
    "conflicts": {
        "statuses": {"missing-declaration": "settled"},
        "withDisposition": "settled",
        "openQuestion": "open",
        "inventoryStatement": {"document": "expected-inventory.json", "lifecycle": "retired"},
    },
    "sharedRepositories": {"prefixes": ["shared-"], "suffixes": ["-lib"]},
    "serviceRepositories": {"suffix": "-service", "inventoryRole": "service"},
    "noCodeLifecycles": ["planned"],
}


def _git(vault: Path, *arguments: str) -> None:
    """Run one git command in the temporary vault, as a committer made for the check."""
    git: str = shutil.which("git") or "git"
    identity: list[str] = ["-c", "user.name=check", "-c", "user.email=check@example.invalid"]
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv; the resolved git in a temporary repository.
        [git, *identity, "-c", "commit.gpgsign=false", *arguments],
        cwd=vault,
        check=True,
        capture_output=True,
    )


def _commit(vault: Path, message: str) -> None:
    """Commit everything in the temporary vault."""
    _git(vault, "add", "-A")
    _git(vault, "commit", "-q", "--no-verify", "-m", message)


def _vault(work: Path) -> Path:
    """Make the temporary vault: a git repository with three architecture documents and one PRD.

    Returns:
        The vault root.

    """
    vault: Path = (work / "vault").resolve()
    relative: str
    text: str
    for relative, text in DOCUMENTS.items():
        (vault / relative).parent.mkdir(parents=True, exist_ok=True)
        (vault / relative).write_text(text, encoding="utf-8")
    _git(vault, "init", "-q")
    _commit(vault, "vault")
    return vault


def _row(key: str, name: str, repository: str, **extra: JsonValue) -> tuple[str, dict[str, JsonValue]]:
    """Build one row of a small element matrix.

    Returns:
        The row's id and the row.

    """
    row: dict[str, JsonValue] = {"id": key, "kind": key.partition(":")[0], "name": name, "repository": repository}
    row.update({"purpose": f"Purpose of {name}.", "contains": [], "evidence": [], **extra})
    return key, row


def _old_matrix() -> dict[str, JsonValue]:
    """Build a small element matrix.

    Returns:
        Two repositories (a shared library and a service), their stacks and four elements, an
        ambiguous alias, one conflict note and one repository the architecture names without a row.

    """
    cited: JsonValue = [{"path": CHASSIS, "section": "Responsibility", "line": 12, "quote": "One handler shape."}]
    hashed: str = "Proof secrets are stored only as hashes."
    events: JsonValue = [{"path": EVENTS, "section": "Proof tokens", "quote": hashed}]
    note: JsonValue = {"issue": "Inventory had no stack.", "resolution": "Keep it.", "status": "missing-declaration"}
    stray: JsonValue = [{"path": ".polyrepo/manifest.yaml", "quote": "x"}]
    publisher: str = f"element:{LIB}/@repository/eventpublisher"
    layer: str = f"element:{LIB}/{LIB}/{LIB}"
    tokens: str = f"element:{AUTH}/{AUTH}/proof tokens"
    held: JsonValue = [f"stack:{LIB}/{LIB}", publisher, layer]
    rows: dict[str, JsonValue] = dict([
        _row(f"repository:{LIB}", LIB, LIB, evidence=cited, conflicts=[note], contains=held),
        _row(f"stack:{LIB}/{LIB}", LIB, LIB, evidence=cited),
        _row(publisher, "EventPublisher", LIB, resourceType="package-component", evidence=cited),
        _row(layer, LIB, LIB, stack=LIB, resourceType="lambda-layer", evidence=cited),
        _row(f"repository:{AUTH}", AUTH_NAME, AUTH_NAME, evidence=events, contains=[f"stack:{AUTH}/{AUTH}"]),
        _row(f"stack:{AUTH}/{AUTH}", AUTH_NAME, AUTH_NAME, evidence=events),
        _row(tokens, "proof tokens", AUTH_NAME, stack=AUTH_NAME, resourceType="table", evidence=events),
        _row(f"element:{AUTH}/{AUTH}/sign-in handler", "sign-in handler", AUTH_NAME, stack=AUTH_NAME, evidence=stray),
    ])
    aliases: JsonValue = {
        LIB: [f"repository:{LIB}", layer],
        "eventpublisher": [publisher],
        "proof tokens": [tokens],
        AUTH: [f"repository:{AUTH}"],
    }
    unresolved: JsonValue = [{"name": "skillSpoke-push-service", "reason": "Not registered.", "evidence": events}]
    return {"version": 2, "elements": rows, "aliases": aliases, "unresolved": unresolved}


def _check_contract() -> None:
    """Require a valid schema, a current generated contract, and generated values that agree with the schema."""
    schema: dict[str, JsonValue] = load_schema()
    Draft202012Validator.check_schema(schema)
    result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv: this interpreter and the plugin's generator.
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    require(result.returncode == 0, f"matrix_contract.py is stale: {result.stderr.strip()}")
    definitions: JsonValue = schema.get("$defs")
    vocabularies: dict[str, tuple[str, ...]] = {"kind": KINDS, "linkType": LINK_TYPES, "role": ROLES}
    name: str
    values: tuple[str, ...]
    for name, values in vocabularies.items():
        entry: JsonValue = definitions.get(name) if isinstance(definitions, dict) else None
        require(isinstance(entry, dict) and entry.get("enum") == list(values), f"the {name} values match the schema")
    require(set(LINK_RULES) == set(LINK_TYPES), "every link type has its rule")
    require(set(command.COMMANDS) <= set(COMMAND_RULES), "every built sub-command is in the schema's command table")
    require(not COMMAND_RULES["find"].writes, "the command table says a read does not write")
    require(COMMAND_RULES["sync-prds"].writes, "the command table says a sync writes")


def _state(matrix: Matrix, key: NodeId) -> ApprovalState:
    """Read the approval state of one row.

    Returns:
        The state; unverified for a row with no approval.

    """
    node: Node = matrix["nodes"][key]
    return node["approval"]["state"] if "approval" in node else APPROVAL_UNVERIFIED


def _check_carry_over(vault: Path, path: Path) -> None:
    """Carry the small element matrix over, write the matrix file, and check what became of each part."""
    with expected_error(matrixcarry.CarryOverError):
        matrixcarry.parse_type_map({**TYPE_MAP, "resourceTypes": {"table": {"kind": "teapot", "resourceType": "x"}}})
    sources: matrixcarry.CarrySources = matrixcarry.CarrySources(
        matrixcarry.parse_old_matrix(_old_matrix()),
        matrixcarry.parse_type_map(TYPE_MAP),
    )
    documents: list[matrixsync.DocumentRead] = matrixsync.read_documents(vault, vault / ARCH)
    never: DocumentsSyncedAt = matrixstore.empty_matrix(STAMP.at)["documentsSyncedAt"]
    commit: str = matrixsync.vault_change(vault, vault / ARCH, never, full=True).commit
    matrix: Matrix
    account: matrixcarry.CarryReport
    matrix, account = matrixcarry.carry_over(
        sources,
        documents,
        {"vaultCommit": commit, "at": STAMP.at, "dirtyPaths": []},
        STAMP,
    )
    require(account["rowsBefore"] == OLD_ROWS and account["carried"] == OLD_ROWS, "every row is carried")
    require(not account["notCarried"], "no row is left behind")
    require(matrix["nodes"][LAYER]["kind"] == KIND_LAYER, "an element takes its mapped kind")
    require(matrix["nodes"][TOKENS].get("resourceType") == "dynamodb-table", "and its mapped resource type")
    former: str = f"element:{LIB}/@repository/eventpublisher"
    require(matrixquery.resolve(matrix, former) == PUBLISHER, "a former id still finds its row")
    require(account["unregisteredRepositories"] == ["skillSpoke-push-service"], "an unregistered repository is added")
    require(account["services"] == 1, "a service repository gets a service row")
    require(account["supportingFeatures"] == [CAPABILITY], "a shared repository gets a supporting feature")
    require(matrix["nodes"][CAPABILITY].get("provides") == [], "which provides nothing yet")
    require(account["showsResolved"] == SHOWN_RESOLVED, "shown names resolve to their rows")
    require(account["showsAmbiguous"] == 1 and account["showsUnresolved"] == 1, "or are ambiguous, or are terms")
    require(matrixstore.make_id(KIND_TERM, "Job seeker") in matrix["nodes"], "an unresolved shown name is a term row")
    require(len(account["disagreements"]) == 1, "a conflict note becomes a disagreement")
    require(bool(account["evidenceDropped"]), "a citation of something that is no document is dropped")
    coded: list[Node] = [node for node in matrix["nodes"].values() if "code" in node]
    trusted: list[Node] = [node for node in coded if node["code"]["state"] in {CODE_BUILT, CODE_DEPLOYED}]
    require(bool(coded) and not trusted, "nothing is marked built")
    require(_state(matrix, LAYER) == APPROVAL_APPROVED, "a row described by effective documents is approved")
    require(_state(matrix, HANDLER) == APPROVAL_UNVERIFIED, "a row no document describes is unverified")
    matrixstore.create_matrix(path, matrix)
    with expected_error(matrixstore.MatrixRefusedError):
        matrixstore.create_matrix(path, matrix)
    require(not matrixstore.file_problems(path), "the carried matrix has no problems")


def _sync(path: Path, vault: Path, *, full: bool = False) -> matrixsync.DocumentsSynced:
    """Read the vault's documents into the matrix file.

    Returns:
        What the read did.

    """

    def change(matrix: Matrix) -> matrixsync.DocumentsSynced:
        return matrixsync.sync_documents(matrix, vault / ARCH, STAMP, full=full)

    return matrixstore.update_matrix(path, change)


def _sync_prds(path: Path, vault: Path, epics: list[matrixsync.Epic]) -> matrixsync.PrdsSynced:
    """Give the Epics their PRD rows in the matrix file.

    Returns:
        What the read did.

    """

    def change(matrix: Matrix) -> matrixsync.PrdsSynced:
        return matrixsync.sync_prds(matrix, epics, vault / SDLC, STAMP)

    return matrixstore.update_matrix(path, change)


def _add_design(matrix: Matrix) -> None:
    """Record a PRD feature, a fact and the links an architect would write, and approve them."""
    matrix["nodes"][FEATURE] = {
        "id": FEATURE,
        "kind": KIND_FEATURE,
        "name": "Address proof",
        "featureType": FEATURE_PRD,
        "requirements": ["EV-1"],
        "approval": {"state": APPROVAL_APPROVED},
        "changed": STAMP.change(),
        "links": [
            {"type": LINK_REALIZED_BY, "to": TOKENS},
            {"type": LINK_USES, "to": CAPABILITY},
            {"type": LINK_DESCRIBED_BY, "to": EVENTS_ROW, "heading": "Proof tokens"},
        ],
    }
    matrix["nodes"][FACT] = {
        "id": FACT,
        "kind": KIND_FACT,
        "name": "Proof secrets are hashed",
        "statement": "Proof secrets are stored only as hashes.",
        "factKind": FACT_RULE,
        "home": {"document": EVENTS, "heading": "Proof tokens"},
        "linkedFrom": [CHASSIS],
        "approval": {"state": APPROVAL_APPROVED},
        "links": [],
        "changed": STAMP.change(),
    }
    matrix["nodes"][CAPABILITY]["approval"] = {"state": APPROVAL_APPROVED}
    matrix["nodes"][PRD_ROW]["links"] = [{"type": LINK_NEEDS, "to": FEATURE}]
    matrix["nodes"][PRD_ROW]["coverage"] = COVERAGE_APPROVED


def _check_prds(path: Path, vault: Path) -> None:
    """Give an Epic its PRD row, record a design for it, change the PRD, and require the row to follow."""
    listed: str = json.dumps([
        {"id": BEAD, "title": "Address proof", "issue_type": "epic", "labels": ["prd:myagent-proof"]},
        {"id": "ssbd-check2", "title": "No file", "issue_type": "epic", "labels": ["prd:absent"]},
        {"id": "ssbd-check3", "title": "A task", "issue_type": "task", "labels": []},
    ])
    epics: list[matrixsync.Epic] = matrixsync.parse_epics(listed)
    first: matrixsync.PrdsSynced = _sync_prds(path, vault, epics)
    require(first["created"] == [PRD_ROW], "an Epic gets a PRD row")
    require([item["bead"] for item in first["unresolved"]] == ["ssbd-check2"], "an Epic without a file is reported")
    matrixstore.update_matrix(path, _add_design)
    again: matrixsync.PrdsSynced = _sync_prds(path, vault, epics)
    require(again["unchanged"] == 1 and not again["refreshed"], "an unchanged PRD changes nothing")
    view: matrixquery.PrdView = matrixquery.prd_view(matrixstore.read_matrix(path), BEAD, closure=True)
    require(view["fullyApproved"], "an approved PRD whose rows are all approved is fully approved")
    reached: matrixquery.Closure = view["closure"]
    require([row["id"] for row in reached["facts"]] == [FACT], "the closure reaches the facts at the home headings")
    require({row["name"] for row in reached["repositories"]} == {AUTH_NAME, LIB}, "and the repositories")
    require([row["id"] for row in reached["supportingFeatures"]] == [CAPABILITY], "and the shared capabilities")
    (vault / PRD).write_text(DOCUMENTS[PRD.as_posix()] + "\nMore.\n", encoding="utf-8")
    require(_sync_prds(path, vault, epics)["refreshed"] == [PRD_ROW], "a changed PRD is refreshed")
    refreshed: Node = matrixstore.read_matrix(path)["nodes"][PRD_ROW]
    require(refreshed.get("coverage") == COVERAGE_NOT_ASSESSED, "and is not assessed any more")
    _commit(vault, "prd")


def _disagreement(path: Path) -> Node:
    """Read the one disagreement row of the matrix file.

    Returns:
        The row.

    """
    return next(node for node in matrixstore.read_matrix(path)["nodes"].values() if node["kind"] == KIND_DISAGREEMENT)


def _check_edits(path: Path, vault: Path) -> None:
    """Edit and revert a document, and require each read to mark exactly what changed."""
    require(_sync(path, vault)["read"] == 0, "a commit that changes no document reads none")
    require(_sync(path, vault)["skipped"], "nothing is done when the vault is at the commit last read")
    events: Path = vault / EVENTS
    events.write_text(DOCUMENTS[EVENTS].replace("only as hashes", "as salted hashes"), encoding="utf-8")
    edited: matrixsync.DocumentsSynced = _sync(path, vault)
    require(edited["read"] == 1 and edited["changed"] == [EVENTS], "only the edited document is read again")
    require(edited["headingsChanged"] == [{"document": EVENTS, "heading": "Proof tokens"}], "its heading is reported")
    matrix: Matrix = matrixstore.read_matrix(path)
    require(_state(matrix, EVENTS_ROW) == APPROVAL_CHANGED_SINCE_APPROVAL, "an edited document is not approved")
    require(_state(matrix, FACT) == APPROVAL_CHANGED_SINCE_APPROVAL, "so is a fact whose home is the edited heading")
    require(FACT in edited["rowsChanged"], "and the read reports the fact")
    require(matrix["documentsSyncedAt"]["dirtyPaths"] == [EVENTS], "the uncommitted document is remembered")
    events.write_text(DOCUMENTS[EVENTS], encoding="utf-8")
    require(_sync(path, vault)["read"] == 1, "the document that differed is read again after it is reverted")
    require(_state(matrixstore.read_matrix(path), FACT) == APPROVAL_APPROVED, "a reverted edit is approved again")
    require(_disagreement(path).get("disagreementStatus") == DISAGREEMENT_SETTLED, "a standing quotation stays settled")


def _check_commits_and_removal(path: Path, vault: Path) -> None:
    """Commit a change, break and mend a link and the constraints, and delete a document."""
    chassis: Path = vault / CHASSIS
    chassis.write_text(DOCUMENTS[CHASSIS].replace("One handler shape.", "Two shapes."), encoding="utf-8")
    _commit(vault, "edit")
    committed: matrixsync.DocumentsSynced = _sync(path, vault)
    require(committed["read"] == 1 and committed["changed"] == [CHASSIS], "a committed change is found through git")
    applied: Node = _disagreement(path)
    require(applied.get("disagreementStatus") == DISAGREEMENT_APPLIED, "a quotation that is gone is applied")
    missing: list[str] = matrixsync.vault_problems(matrixstore.read_matrix(path), vault / ARCH)
    require(len(missing) == 1 and "holds no link" in missing[0], "a linking document without the link is reported")
    chassis.write_text(chassis.read_text(encoding="utf-8") + "\nSee [[events#Proof tokens]].\n", encoding="utf-8")
    (vault / CONSTRAINTS).write_text(DOCUMENTS[CONSTRAINTS] + "\nA new rule.\n", encoding="utf-8")
    problems: list[str] = matrixsync.vault_problems(matrixstore.read_matrix(path), vault / ARCH)
    require(len(problems) == 1 and "constraints heading" in problems[0], "only the changed constraints are reported")
    (vault / CONSTRAINTS).write_text(DOCUMENTS[CONSTRAINTS], encoding="utf-8")
    (vault / EVENTS).unlink()
    require(_sync(path, vault)["retired"] == [EVENTS], "a deleted document is retired")
    retired: Node = matrixstore.read_matrix(path)["nodes"][EVENTS_ROW]
    require(retired.get("lifecycle") == LIFECYCLE_RETIRED, "and its row says so")
    (vault / EVENTS).write_text(DOCUMENTS[EVENTS], encoding="utf-8")
    require(_sync(path, vault, full=True)["full"], "a full read reads every document")
    _commit(vault, "settle")


def _check_reads(path: Path) -> None:
    """Ask every question of the matrix."""
    matrix: Matrix = matrixstore.read_matrix(path)
    found: matrixquery.FindResult = matrixquery.find(matrix, "proof tokens")
    require(found["matches"][0]["exact"] and found["matches"][0]["row"]["id"] == TOKENS, "an exact name comes first")
    shared: matrixquery.FindResult = matrixquery.find(matrix, "", provides="chassis handler")
    require([match["row"]["id"] for match in shared["matches"]] == [CAPABILITY], "a behaviour finds the capability")
    require(matrixquery.node_view(matrix, CAPABILITY)["reverse"] == {"usedBy": [FEATURE]}, "reverse links are computed")
    elements: list[NodeId] = matrixquery.elements_of_repository(matrix, AUTH_NAME)
    capabilities: list[matrixquery.Capability] = matrixquery.uses_view(matrix, elements)["capabilities"]
    require([item["feature"]["id"] for item in capabilities] == [CAPABILITY], "an element is told what it must use")
    require(len(matrixquery.disagreements_for(matrix, CHASSIS)) == 1, "a document's disagreements are found")
    require(matrixquery.summarize(matrix)["byKind"][KIND_SERVICE] == 1, "rows are counted by kind")
    with expected_error(matrixstore.MatrixRefusedError):
        matrixquery.resolve(matrix, LIB)


def _check_refusals(path: Path) -> None:
    """Require the consistency rules and the roles to refuse what they must."""
    before: str = path.read_text(encoding="utf-8")

    def dangling(changed: Matrix) -> None:
        changed["nodes"][FEATURE]["links"].append({"type": LINK_USES, "to": NodeId("feature:absent")})

    def wrong_kinds(changed: Matrix) -> None:
        changed["nodes"][FEATURE]["links"].append({"type": LINK_NEEDS, "to": CAPABILITY})

    def unknown_type(changed: Matrix) -> None:
        changed["nodes"][TOKENS]["resourceType"] = "teapot"

    def second_home(changed: Matrix) -> None:
        again: Node = json.loads(json.dumps(changed["nodes"][FACT]))
        again["id"] = NodeId("fact:again")
        changed["nodes"][again["id"]] = again

    for breaking in (dangling, wrong_kinds, unknown_type, second_home):
        with expected_error(MatrixError):
            matrixstore.update_matrix(path, breaking)
    require(path.read_text(encoding="utf-8") == before, "a refused change leaves the file as it was")
    with expected_error(matrixstore.MatrixRefusedError):
        matrixstore.require_role("carry-over", ROLE_SCRIPT)
    with expected_error(matrixstore.MatrixRefusedError):
        matrixstore.require_role("sync-prds", ROLE_SOLUTIONS_ARCHITECT)
    matrixstore.require_role("sync-documents", matrixstore.role_of({ROLE_ENV: ROLE_SOLUTIONS_ARCHITECT}))
    with expected_error(matrixstore.MatrixRefusedError):
        matrixstore.role_of({ROLE_ENV: "teapot"})


def _check_two_writers(path: Path, work: Path) -> None:
    """Run two processes that load the store by file path and write the same matrix at once."""
    rows: int = len(matrixstore.read_matrix(path)["nodes"])
    writers: list[subprocess.Popen[str]] = [
        subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv: this interpreter and the probe above.
            [sys.executable, "-P", "-c", WRITER, str(STORE), str(path), label, str(WRITES_EACH)],
            cwd=work,
            stderr=subprocess.PIPE,
            text=True,
        )
        for label in ("first", "second")
    ]
    writer: subprocess.Popen[str]
    for writer in writers:
        errors: str = writer.communicate(timeout=120)[1]
        require(writer.returncode == 0, f"a writer that loads the store by path failed: {errors.strip()}")
    written: int = len(matrixstore.read_matrix(path)["nodes"])
    require(written == rows + 2 * WRITES_EACH, "two processes writing at once lose no row")
    require(not list(path.parent.glob("*.tmp")), "no temporary file is left behind")


def _run(work: Path, *arguments: str, status: int = 0, role: str = "") -> dict[str, JsonValue]:
    """Run bin/atw-matrix from another directory and decode what it prints.

    Returns:
        The JSON object on stdout, or an empty object when the command printed none.

    Raises:
        TypeError: The command printed JSON that is not an object.

    """
    result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv: the plugin's own command.
        [str(COMMAND), *arguments],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
        env={**os.environ, ROLE_ENV: role},
    )
    shown: str = f"atw-matrix {' '.join(arguments[:3])}"
    require(result.returncode == status, f"{shown} exited {result.returncode}, not {status}: {result.stderr.strip()}")
    if not result.stdout.strip():
        return {}
    decoded: JsonValue = json_value(json.loads(result.stdout))
    if not isinstance(decoded, dict):
        message: str = f"{shown} printed JSON that is not an object"
        raise TypeError(message)
    return decoded


def _command_sources(work: Path) -> None:
    """Write the files the command reads: a three-row element matrix, the mapping file and one Epic."""
    sources: Path = work / "sources"
    sources.mkdir()
    tokens: str = "element:a-service/a-service/proof tokens"
    old: JsonValue = {
        "version": 2,
        "aliases": {"proof tokens": [tokens]},
        "unresolved": [],
        "elements": dict([
            _row("repository:a-service", "a-service", "a-service", contains=["stack:a-service/a-service"]),
            _row("stack:a-service/a-service", "a-service", "a-service"),
            _row(tokens, "proof tokens", "a-service", stack="a-service", resourceType="table"),
        ]),
    }
    epic: JsonValue = {"id": BEAD, "title": "Address proof", "issue_type": "epic", "labels": ["prd:myagent-proof"]}
    (sources / "old.json").write_text(json.dumps(old), encoding="utf-8")
    (sources / "types.json").write_text(json.dumps(TYPE_MAP), encoding="utf-8")
    (sources / "epics.json").write_text(json.dumps([epic]), encoding="utf-8")


def _check_command(work: Path, vault: Path) -> None:
    """Run every sub-command of bin/atw-matrix as a subprocess, from another directory."""
    _command_sources(work)
    where: tuple[str, ...] = ("--matrix", "by-command/matrix.json")
    arch: tuple[str, ...] = ("--arch", str(vault / ARCH))
    files: tuple[str, ...] = ("--source", "sources/old.json", "--type-map", "sources/types.json")
    _run(work, "carry-over", *where, *arch, *files, status=1, role=ROLE_SCRIPT)
    carried: dict[str, JsonValue] = _run(work, "carry-over", *where, *arch, *files)
    require(carried.get("carried") == SMALL_ROWS, "carry-over writes the matrix")
    _run(work, "carry-over", *where, *arch, *files, status=1)
    require(_run(work, "check", *where, *arch).get("valid") is True, "check accepts the carried matrix")
    require(_run(work, "sync-documents", *where, *arch).get("skipped") is True, "sync-documents has nothing to read")
    prds: tuple[str, ...] = ("--prd-dir", str(vault / SDLC), "--epics-file", "sources/epics.json")
    require(_run(work, "sync-prds", *where, *prds).get("created") == [PRD_ROW], "sync-prds creates the PRD row")
    _run(work, "sync-prds", *where, *prds, status=1, role=ROLE_SOLUTIONS_ARCHITECT)
    unassessed: dict[str, JsonValue] = _run(work, "prd", BEAD, "--closure", *where)
    require(unassessed.get("fullyApproved") is False, "prd prints a PRD with no features as not approved")
    _run(work, "prd", "ssbd-absent", *where, status=1)
    found: dict[str, JsonValue] = _run(work, "find", "--text", "proof", "--kinds", "infrastructure", *where)
    require(found.get("total") == 1, "find prints the matching row")
    _run(work, "find", "--kinds", "teapot", "--text", "proof", *where, status=1)
    node: JsonValue = _run(work, "node", "element:a-service/a-service/proof tokens", *where).get("node")
    require(isinstance(node, dict) and node.get("kind") == "infrastructure", "node finds a row by its former id")
    uses: dict[str, JsonValue] = _run(work, "uses", "--repository", "a-service", *where)
    require(uses.get("capabilities") == [], "uses prints no capability for a repository that uses none")
    _run(work, "uses", *where, status=1)
    disputed: dict[str, JsonValue] = _run(work, "disagreements", "--document", EVENTS, *where)
    require(disputed.get("disagreements") == [], "disagreements prints none")
    require(_run(work, "summary", *where).get("rows") == SMALL_MATRIX_ROWS, "summary counts the rows")
    (work / "by-command" / "matrix.json").write_text(json.dumps({"version": 3}), encoding="utf-8")
    require(_run(work, "check", *where, status=1).get("valid") is False, "check rejects a broken file")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Run every matrix check against a temporary vault and temporary files."""
    _check_contract()
    temporary: str
    with tempfile.TemporaryDirectory(prefix="atw-matrix-check-") as temporary:
        work: Path = Path(temporary).resolve()
        vault: Path = _vault(work)
        path: Path = work / "control" / "matrix.json"
        _check_carry_over(vault, path)
        _check_prds(path, vault)
        _check_edits(path, vault)
        _check_commits_and_removal(path, vault)
        _check_reads(path)
        _check_refusals(path)
        _check_two_writers(path, work)
        _check_command(work, vault)
    report("PASS: matrix contract, carry-over, document and PRD reads, queries, refusals, two writers and the command")


if __name__ == "__main__":
    main()
