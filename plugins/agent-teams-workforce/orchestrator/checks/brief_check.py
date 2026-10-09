"""Check fact-only Epic briefs and shared artifact contracts without running a flow."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

import jsonschema
import yaml

FACT_FIELDS = frozenset({"bead", "inputs", "output", "outcome"})
SCHEMA_WORDS = frozenset(
    {"$schema", "properties", "additionalProperties", "required", "$defs"}
)
BRIEF_NAMES = re.compile(r"(?:^|_)(?:brief|prompt|instructions|template)(?:_|$)", re.I)
FORBIDDEN_PROSE = re.compile(
    r"\b(?:must|never|do not|required fields|follow these|schema)\b", re.I
)


def table(text: str, heading: str) -> list[list[str]]:
    """Read the intentionally simple tables in the human-readable contract register."""
    section = text.split(heading + "\n", 1)[1].split("\n## ", 1)[0]
    return [
        line.strip("| ").split(" | ")
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("|---")
    ][1:]


def index_artifacts(text: str) -> set[str]:
    """Return every artifact row, including explicit legacy/portfolio dispositions."""
    return {
        line.strip("| ").split(" | ")[0]
        for line in text.split("## Bead writes", 1)[0].splitlines()
        if line.startswith("| ") and not line.startswith("| Path pattern")
    }


def frontmatter(path: Path) -> dict:
    """Read an agent's actual skill declarations."""
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def check_outcome(
    node: ast.AST, assignments: dict[str, ast.AST], *, forwarded: bool = False
) -> str | None:
    """Only static, one-line outcome facts may cross the brief boundary."""
    seen = set()
    while isinstance(node, ast.Name) and node.id in assignments and node.id not in seen:
        seen.add(node.id)
        node = assignments[node.id]
    if isinstance(node, ast.IfExp):
        return check_outcome(
            node.body, assignments, forwarded=forwarded
        ) or check_outcome(node.orelse, assignments, forwarded=forwarded)
    if (
        forwarded
        and isinstance(node, ast.Name)
        and node.id == "outcome"
        and node.id not in assignments
    ):
        return None  # Forwarded helper parameter; every call site is checked below.
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return "outcome must be a statically inspectable one-line literal"
    text = node.value
    if not text.strip() or len(text) > 240 or "\n" in text or "\r" in text:
        return "outcome must be nonempty, one line and at most 240 characters"
    if FORBIDDEN_PROSE.search(text) or any(word in text for word in SCHEMA_WORDS):
        return "outcome carries instructions or schema text"
    if ";" in text or re.search(r"[.!?]\s+\S", text):
        return "outcome carries multiple statements rather than one expected result"
    return None


def flow_findings(path: Path, outcome_positions: dict[str, int]) -> list[str]:
    """Reject inline schema/brief construction; the runner alone formats fact fields."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings = []
    assignments = {
        target.id: node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assignments.update(
        {
            node.target.id: node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        }
    )
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }

    def outcome_problem(node: ast.AST) -> str | None:
        ancestor = parents.get(node)
        while ancestor is not None and not isinstance(
            ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            ancestor = parents.get(ancestor)
        forwarded = ancestor is not None and any(
            arg.arg == "outcome"
            for arg in (
                *ancestor.args.posonlyargs,
                *ancestor.args.args,
                *ancestor.args.kwonlyargs,
            )
        )
        return check_outcome(node, assignments, forwarded=forwarded)

    def report(node: ast.AST, reason: str) -> None:
        findings.append(f"{path}:{node.lineno}: {reason}")

    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ) and BRIEF_NAMES.search(node.name):
            report(
                node,
                "flow defines a brief/schema/template helper; use the core fact formatter",
            )
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and BRIEF_NAMES.search(target.id):
                    # A schema path is validation metadata, never a brief payload.
                    value = node.value
                    if not (
                        isinstance(value, ast.BinOp) and isinstance(value.op, ast.Div)
                    ):
                        report(
                            node,
                            f"inline brief/schema/template construction in {target.id}",
                        )
        if isinstance(node, ast.Dict):
            keys = {key.value for key in node.keys if isinstance(key, ast.Constant)}
            if keys & SCHEMA_WORDS:
                report(
                    node, "inline JSON schema text; reference the shared schema file"
                )
            if "outcome" in keys and keys - FACT_FIELDS:
                report(
                    node,
                    "brief object carries fields beyond bead/inputs/output/outcome",
                )
            for key, value in zip(node.keys, node.values, strict=True):
                if isinstance(key, ast.Constant) and key.value == "outcome":
                    if problem := outcome_problem(value):
                        report(value, problem)
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else getattr(node.func, "attr", "")
            )
            if name in outcome_positions and len(node.args) > outcome_positions[name]:
                if problem := outcome_problem(node.args[outcome_positions[name]]):
                    report(node, problem)
            if name in {"brief", "prompt", "format_brief", "build_brief"}:
                report(node, "flow must declare AgentStep facts, not construct a brief")
            for keyword in node.keywords:
                if keyword.arg in {
                    "prompt",
                    "brief",
                    "instructions",
                    "system_prompt",
                    "messages",
                }:
                    report(
                        keyword.value,
                        f"flow passes {keyword.arg} prose outside fact fields",
                    )
                if keyword.arg == "outcome":
                    if problem := outcome_problem(keyword.value):
                        report(keyword.value, problem)
            if name == "AgentStep" and node.args:
                report(
                    node,
                    "AgentStep uses positional fields; outcome must be mechanically inspectable",
                )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if ('"properties"' in text or '"$schema"' in text) and ("{" in text):
                report(node, "JSON schema embedded in a string")
    return findings


def contract_findings(plugin: Path) -> tuple[list[str], int, int]:
    """Cross-check INDEX, the register, agent frontmatter and shared rules/schemas."""
    specs = plugin / "orchestrator/specs/epic"
    register = (specs / "agent-contracts.md").read_text(encoding="utf-8")
    rules = (plugin / "skills/artifact-handoff/epic-contracts.md").read_text(
        encoding="utf-8"
    )
    agents = table(register, "## Agents")
    artifacts = table(register, "## Artifacts")
    findings = []
    metadata = {}
    for name, definition, skills, produces, reads in agents:
        path = plugin / definition
        if not path.is_file():
            findings.append(f"{name}: missing definition {definition}")
            continue
        actual = frontmatter(path)
        metadata[name] = actual
        declared = [item.strip() for item in skills.split(",")]
        if sorted(declared) != sorted(actual.get("skills", [])):
            findings.append(f"{name}: table skill list differs from frontmatter")
        for contract in (produces + "," + reads).split(","):
            if f"## {contract.strip()}\n" not in rules:
                findings.append(f"{name}: no shared rules for {contract}")
        for skill in declared:
            prefix, _, stem = skill.partition(":")
            if (
                prefix == "agent-teams-workforce"
                and not (plugin / "skills" / stem / "SKILL.md").is_file()
            ):
                findings.append(f"{name}: missing declared skill {skill}")
    expected = index_artifacts((specs / "INDEX.md").read_text(encoding="utf-8"))
    actual_paths = [row[0] for row in artifacts]
    for missing in sorted(expected - set(actual_paths)):
        findings.append(f"INDEX artifact lacks contract mapping: {missing}")
    for extra in sorted(set(actual_paths) - expected):
        findings.append(f"contract artifact absent from INDEX: {extra}")
    if len(actual_paths) != len(set(actual_paths)):
        findings.append("duplicate artifact mappings")
    for artifact, contract, producers, consumers, skill, anchor in artifacts:
        if f"## {anchor}\n" not in rules:
            findings.append(
                f"{artifact}: missing shared field/completion rules {anchor}"
            )
        if contract in {"retired", "legacy", "out-of-scope"}:
            if skill != "none" or producers != "python" or consumers != "python":
                findings.append(
                    f"{artifact}: inactive row incorrectly declares an agent contract"
                )
            continue
        if skill != "artifact-handoff":
            findings.append(
                f"{artifact}: shared contract skill is not artifact-handoff"
            )
        for actor in (producers + "," + consumers).split(","):
            if actor == "python":
                continue
            if actor not in metadata:
                findings.append(f"{artifact}: unmapped agent {actor}")
            elif f"agent-teams-workforce:{skill}" not in metadata[actor].get(
                "skills", []
            ):
                findings.append(
                    f"{artifact}: {actor} does not load shared contract skill {skill}"
                )
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
        (schema_dir / "architecture-baseline.schema.json").read_text()
    )
    if survey["properties"]["baseline"] != baseline:
        findings.append("survey baseline differs from canonical saved-survey schema")
    # DESIGN is a separate roster authority; deleting a table row cannot hide a dispatch.
    design = (plugin / "orchestrator/DESIGN.md").read_text()
    roster = design.split("### 5.4 ", 1)[1].split("### 5.5 ", 1)[0]
    expected_agents = {
        path.stem
        for path in (plugin / "agents").glob("*.md")
        if re.search(r"`" + re.escape(path.stem) + r"`", roster)
    } - {"user-story-writer"}
    for missing in sorted(expected_agents - metadata.keys()):
        findings.append(f"DESIGN agent missing from register: {missing}")
    return findings, len(agents), len(artifacts)


def main() -> int:
    """Print every finding and return a command-verifiable completion status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument(
        "--flow-root", type=Path, help="alternate flow directory for negative probes"
    )
    args = parser.parse_args()
    try:
        findings, agents, artifacts = contract_findings(args.plugin)
        flows = sorted(
            (args.flow_root or args.plugin / "orchestrator/flows").rglob("*.py")
        )
        outcome_positions = {}
        for path in flows:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names = [
                        arg.arg
                        for arg in node.args.args
                        if arg.arg not in {"self", "cls"}
                    ]
                    if "outcome" in names:
                        outcome_positions[node.name] = names.index("outcome")
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
        print(f"FAIL: cannot verify contract inputs: {exc}")
        return 1
    for finding in findings:
        print(f"FAIL: {finding}")
    if findings:
        return 1
    print(
        f"PASS: {len(flows)} flow modules; {agents} agents; {artifacts} INDEX artifacts; shared schemas and fact-only briefs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
