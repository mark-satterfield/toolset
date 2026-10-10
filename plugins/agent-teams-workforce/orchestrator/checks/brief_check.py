"""Check fact-only Epic briefs and shared artifact contracts without running a flow."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

import jsonschema
import yaml
from typeguard import CollectionCheckStrategy, check_type, typechecked

type SignatureKey = str | tuple[str, str | None, str]
MAX_OUTCOME_LENGTH = 240

FACT_FIELDS = frozenset({"bead", "inputs", "output", "outcome"})
SCHEMA_WORDS = frozenset(
    {"$schema", "properties", "additionalProperties", "required", "$defs"},
)
BRIEF_NAMES = re.compile(r"(?:^|_)(?:brief|prompt|instructions|template)(?:_|$)", re.IGNORECASE)
FORBIDDEN_PROSE = re.compile(
    r"\b(?:must|never|do not|required fields|follow these|schema)\b",
    re.IGNORECASE,
)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def table(text: str, heading: str) -> list[list[str]]:
    """Read the intentionally simple tables in the human-readable contract register.

    Returns:
        The validated result or detected contract findings.

    """
    section = text.split(heading + "\n", 1)[1].split("\n## ", 1)[0]
    return [
        line.strip("| ").split(" | ")
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("|---")
    ][1:]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def index_artifacts(text: str) -> set[str]:
    """Return every artifact row, including explicit legacy/portfolio dispositions.

    Returns:
        The validated result or detected contract findings.

    """
    return {
        line.strip("| ").split(" | ")[0]
        for line in text.split("## Bead writes", 1)[0].splitlines()
        if line.startswith("| ") and not line.startswith("| Path pattern")
    }


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def frontmatter(path: Path) -> dict[str, object]:
    """Read an agent's actual skill declarations.

    Returns:
        The validated result or detected contract findings.

    """
    return check_type(
        yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1]),
        dict[str, object],
        collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_outcome(
    node: ast.AST,
    assignments: dict[str, ast.AST],
    *,
    forwarded: bool = False,
) -> str | None:
    """Only static, one-line outcome facts may cross the brief boundary.

    Returns:
        The validated result or detected contract findings.

    """
    seen = set()
    while isinstance(node, ast.Name) and node.id in assignments and node.id not in seen:
        seen.add(node.id)
        node = assignments[node.id]
    if isinstance(node, ast.IfExp):
        return check_outcome(
            node.body,
            assignments,
            forwarded=forwarded,
        ) or check_outcome(node.orelse, assignments, forwarded=forwarded)
    if forwarded and isinstance(node, ast.Name) and node.id == "outcome" and node.id not in assignments:
        return None  # Forwarded helper parameter; every call site is checked below.
    return _outcome_literal(node)


def _outcome_literal(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return "outcome must be a statically inspectable one-line literal"
    text = node.value
    if not text.strip() or len(text) > MAX_OUTCOME_LENGTH or "\n" in text or "\r" in text:
        return "outcome must be nonempty, one line and at most 240 characters"
    if FORBIDDEN_PROSE.search(text) or any(word in text for word in SCHEMA_WORDS):
        return "outcome carries instructions or schema text"
    if ";" in text or re.search(r"[.!?]\s+\S", text):
        return "outcome carries multiple statements rather than one expected result"
    return None


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def outcome_signatures(path: Path) -> dict[SignatureKey, int]:
    """Key positional contracts by defining module/class, never bare method name.

    Returns:
        The validated result or detected contract findings.

    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: dict[SignatureKey, int] = {}

    def visit(nodes: list[ast.stmt], owner: str = "") -> None:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit(node.body, node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names = [arg.arg for arg in (*node.args.posonlyargs, *node.args.args) if arg.arg not in {"self", "cls"}]
                if "outcome" in names:
                    result[path.stem, owner, node.name] = names.index("outcome")

    visit(tree.body)
    return result


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def call_position(
    node: ast.Call,
    tree: ast.Module,
    path: Path,
    parents: dict[ast.AST, ast.AST],
    signatures: dict[SignatureKey, int],
) -> int | None:
    """Resolve local methods and imported helpers from receiver declarations.

    Returns:
        The validated result or detected contract findings.

    """
    name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
    imports = {
        alias.asname or alias.name: ((item.module or "").split(".")[-1], alias.name)
        for item in tree.body
        if isinstance(item, ast.ImportFrom)
        for alias in item.names
    }
    scope = parents.get(node)
    while scope is not None and not isinstance(
        scope,
        (ast.FunctionDef, ast.AsyncFunctionDef),
    ):
        scope = parents.get(scope)
    key: SignatureKey | None
    if isinstance(node.func, ast.Name):
        module, symbol = imports.get(name, (path.stem, name))
        key = (module, "", symbol)
    elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        receiver = node.func.value.id
        owner = None
        if receiver in {"self", "cls"}:
            ancestor = parents.get(node)
            while ancestor is not None and not isinstance(ancestor, ast.ClassDef):
                ancestor = parents.get(ancestor)
            owner = ancestor.name if isinstance(ancestor, ast.ClassDef) else None
        elif isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = _receiver_owner(scope, receiver)
        module, symbol = imports.get(owner, (path.stem, owner)) if owner is not None else (path.stem, None)
        key = (module, symbol, name)
    else:
        key = None
    # Bare keys support callers that explicitly supply one known helper contract.
    return signatures.get(key, signatures.get(name)) if key is not None else signatures.get(name)


def _receiver_owner(scope: ast.FunctionDef | ast.AsyncFunctionDef, receiver: str) -> str | None:
    owner = None
    for arg in (*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs):
        if arg.arg == receiver and isinstance(arg.annotation, ast.Name):
            owner = arg.annotation.id
    for assignment in ast.walk(scope):
        if (
            isinstance(assignment, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == receiver for t in assignment.targets)
            and isinstance(assignment.value, ast.Call)
            and isinstance(assignment.value.func, ast.Name)
        ):
            owner = assignment.value.func.id
    return owner


class _FlowCheck:
    def __init__(self, path: Path, outcome_positions: dict[SignatureKey, int]) -> None:
        self.path = path
        self.outcome_positions = outcome_positions
        self.tree = ast.parse(self.path.read_text(encoding="utf-8"), filename=str(self.path))
        self.findings: list[str] = []
        self.assignments: dict[str, ast.AST] = {
            target.id: node.value
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }

        self.assignments.update(
            {
                node.target.id: node.value
                for node in ast.walk(self.tree)
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None
            },
        )
        self.parents = {child: node for node in ast.walk(self.tree) for child in ast.iter_child_nodes(node)}

    def _outcome_problem(self, node: ast.AST) -> str | None:
        ancestor = self.parents.get(node)
        while ancestor is not None and not isinstance(
            ancestor,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            ancestor = self.parents.get(ancestor)
        forwarded = isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            arg.arg == "outcome"
            for arg in (
                *ancestor.args.posonlyargs,
                *ancestor.args.args,
                *ancestor.args.kwonlyargs,
            )
        )
        return check_outcome(node, self.assignments, forwarded=forwarded)

    def _report(self, node: ast.AST, reason: str) -> None:
        self.findings.append(f"{self.path}:{getattr(node, 'lineno', 0)}: {reason}")

    def _check_assignment(self, node: ast.Assign | ast.AnnAssign) -> None:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and BRIEF_NAMES.search(target.id):
                # A schema path is validation metadata, never a brief payload.
                value = node.value
                if not (isinstance(value, ast.BinOp) and isinstance(value.op, ast.Div)):
                    self._report(
                        node,
                        f"inline brief/schema/template construction in {target.id}",
                    )

    def _check_dictionary(self, node: ast.Dict) -> None:
        keys = {key.value for key in node.keys if isinstance(key, ast.Constant)}
        if keys & SCHEMA_WORDS:
            self._report(
                node,
                "inline JSON schema text; reference the shared schema file",
            )
        if "outcome" in keys and keys - FACT_FIELDS:
            self._report(
                node,
                "brief object carries fields beyond bead/inputs/output/outcome",
            )
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == "outcome" and (problem := self._outcome_problem(value)):
                self._report(value, problem)

    def _check_call(self, node: ast.Call) -> None:
        name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        position = call_position(node, self.tree, self.path, self.parents, self.outcome_positions)
        if (
            position is not None
            and len(node.args) > position
            and (problem := self._outcome_problem(node.args[position]))
        ):
            self._report(node, problem)
        if name in {"brief", "prompt", "format_brief", "build_brief"}:
            self._report(node, "flow must declare AgentStep facts, not construct a brief")
        for keyword in node.keywords:
            if keyword.arg in {
                "prompt",
                "brief",
                "instructions",
                "system_prompt",
                "messages",
            }:
                self._report(
                    keyword.value,
                    f"flow passes {keyword.arg} prose outside fact fields",
                )
            if keyword.arg == "outcome" and (problem := self._outcome_problem(keyword.value)):
                self._report(keyword.value, problem)
        if name == "AgentStep" and node.args:
            self._report(
                node,
                "AgentStep uses positional fields; outcome must be mechanically inspectable",
            )

    @typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
    def collect(self) -> list[str]:
        """Inspect every AST node.

        Returns:
            The accumulated findings.

        """
        for node in ast.walk(self.tree):
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ) and BRIEF_NAMES.search(node.name):
                self._report(
                    node,
                    "flow defines a brief/schema/template helper; use the core fact formatter",
                )
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                self._check_assignment(node)
            if isinstance(node, ast.Dict):
                self._check_dictionary(node)
            if isinstance(node, ast.Call):
                self._check_call(node)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
                if ('"properties"' in text or '"$schema"' in text) and ("{" in text):
                    self._report(node, "JSON schema embedded in a string")
        return self.findings


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def flow_findings(path: Path, outcome_positions: dict[SignatureKey, int]) -> list[str]:
    """Inspect source code without executing a flow.

    Returns:
        Every brief or schema contract violation found in the module.

    """
    return _FlowCheck(path, outcome_positions).collect()


def _agent_contracts(
    plugin: Path,
    agents: list[list[str]],
    rules: str,
    findings: list[str],
) -> dict[str, dict[str, object]]:
    metadata: dict[str, dict[str, object]] = {}
    for name, definition, skills, produces, reads in agents:
        path = plugin / definition
        if not path.is_file():
            findings.append(f"{name}: missing definition {definition}")
            continue
        actual = frontmatter(path)
        metadata[name] = actual
        declared = [item.strip() for item in skills.split(",")]
        if sorted(declared) != sorted(
            check_type(
                actual.get("skills", []),
                list[str],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ),
        ):
            findings.append(f"{name}: table skill list differs from frontmatter")
        findings.extend(
            f"{name}: no shared rules for {contract}"
            for contract in (produces + "," + reads).split(",")
            if f"## {contract.strip()}\n" not in rules
        )
        for skill in declared:
            prefix, _, stem = skill.partition(":")
            if prefix == "agent-teams-workforce" and not (plugin / "skills" / stem / "SKILL.md").is_file():
                findings.append(f"{name}: missing declared skill {skill}")
    return metadata


def _artifact_contracts(
    artifacts: list[list[str]],
    rules: str,
    metadata: dict[str, dict[str, object]],
    findings: list[str],
) -> None:
    for artifact, contract, producers, consumers, skill, anchor in artifacts:
        if f"## {anchor}\n" not in rules:
            findings.append(
                f"{artifact}: missing shared field/completion rules {anchor}",
            )
        if contract in {"retired", "legacy", "out-of-scope"}:
            if skill != "none" or producers != "python" or consumers != "python":
                findings.append(
                    f"{artifact}: inactive row incorrectly declares an agent contract",
                )
            continue
        if skill != "artifact-handoff":
            findings.append(
                f"{artifact}: shared contract skill is not artifact-handoff",
            )
        for actor in (producers + "," + consumers).split(","):
            if actor == "python":
                continue
            if actor not in metadata:
                findings.append(f"{artifact}: unmapped agent {actor}")
            elif f"agent-teams-workforce:{skill}" not in check_type(
                metadata[actor].get("skills", []),
                list[str],
                collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS,
            ):
                findings.append(
                    f"{artifact}: {actor} does not load shared contract skill {skill}",
                )


def _schema_contracts(plugin: Path, rules: str, findings: list[str]) -> None:
    schema_dir = plugin / "skills/artifact-handoff/schemas"
    for schema_name in re.findall(r"\]\(schemas/([\w-]+\.schema\.json)\)", rules):
        path = schema_dir / schema_name
        if not path.is_file():
            findings.append(f"missing shared schema {schema_name}")
            continue
        try:
            jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text()))
        except (ValueError, jsonschema.SchemaError) as exc:
            findings.append(f"{schema_name}: invalid schema: {exc}")
    survey = json.loads((schema_dir / "survey.schema.json").read_text())
    baseline = json.loads(
        (schema_dir / "architecture-baseline.schema.json").read_text(),
    )
    if survey["properties"]["baseline"] != baseline:
        findings.append("survey baseline differs from canonical saved-survey schema")


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def contract_findings(plugin: Path) -> tuple[list[str], int, int]:
    """Cross-check INDEX, the register, agent frontmatter and shared rules/schemas.

    Returns:
        The validated result or detected contract findings.

    """
    specs = plugin / "orchestrator/specs/epic"
    register = (specs / "agent-contracts.md").read_text(encoding="utf-8")
    rules = (plugin / "skills/artifact-handoff/epic-contracts.md").read_text(
        encoding="utf-8",
    )
    agents = table(register, "## Agents")
    artifacts = table(register, "## Artifacts")
    findings: list[str] = []
    metadata = _agent_contracts(plugin, agents, rules, findings)
    expected = index_artifacts((specs / "INDEX.md").read_text(encoding="utf-8"))
    actual_paths = [row[0] for row in artifacts]
    findings.extend(
        f"INDEX artifact lacks contract mapping: {missing}" for missing in sorted(expected - set(actual_paths))
    )
    findings.extend(f"contract artifact absent from INDEX: {extra}" for extra in sorted(set(actual_paths) - expected))
    if len(actual_paths) != len(set(actual_paths)):
        findings.append("duplicate artifact mappings")
    _artifact_contracts(artifacts, rules, metadata, findings)
    _schema_contracts(plugin, rules, findings)
    # DESIGN is a separate roster authority; deleting a table row cannot hide a dispatch.
    design = (plugin / "orchestrator/DESIGN.md").read_text()
    roster = design.split("### 5.4 ", 1)[1].split("### 5.5 ", 1)[0]
    expected_agents = {
        path.stem for path in (plugin / "agents").glob("*.md") if re.search(r"`" + re.escape(path.stem) + r"`", roster)
    } - {"user-story-writer"}
    findings.extend(
        f"DESIGN agent missing from register: {missing}" for missing in sorted(expected_agents - metadata.keys())
    )
    return findings, len(agents), len(artifacts)


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> int:
    """Print every finding and return a command-verifiable completion status.

    Returns:
        The validated result or detected contract findings.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--flow-root",
        type=Path,
        help="alternate flow directory for negative probes",
    )
    args = parser.parse_args()
    try:
        findings, agents, artifacts = contract_findings(args.plugin)
        flows = sorted(
            (args.flow_root or args.plugin / "orchestrator/flows").rglob("*.py"),
        )
        outcome_positions: dict[SignatureKey, int] = {}
        for path in flows:
            outcome_positions.update(outcome_signatures(path))
        for path in flows:
            findings.extend(flow_findings(path, outcome_positions))
    except (
        ValueError,
        KeyError,
        IndexError,
        OSError,
        SyntaxError,
        yaml.YAMLError,
    ) as exc:
        sys.stdout.write(f"FAIL: cannot verify contract inputs: {exc}\n")
        return 1
    for finding in findings:
        sys.stdout.write(f"FAIL: {finding}\n")
    if findings:
        return 1
    sys.stdout.write(
        f"PASS: {len(flows)} flow modules; {agents} agents; {artifacts} INDEX artifacts; "
        "shared schemas and fact-only briefs\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
