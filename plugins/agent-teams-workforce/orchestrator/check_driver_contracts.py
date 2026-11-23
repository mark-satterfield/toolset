"""Check the contracts the driver and the plugin share: their types and their values.

The type check runs strict mypy over the real driver producers against the plugin's Protocols, and over
the driver's Protocols against the plugin modules it loads by path. The value check reads the driver's
modules without importing them and compares every value they share with the plugin (finding kinds, the
deploy steps the driver runs, the elaboration steps its done rule names, the plugin files it loads, the
bead metadata names and handback line fields it reads) with the plugin's definitions.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed static checker argv, no shell or workflow.
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "pipeline-contracts" / "scripts"))

from driver_surface_types import CONTROL_REPO_ENV, DRIVER_DIR_PARTS
from finding_contract import FINDING_KINDS, FINDING_SOURCES
from typeguard import CollectionCheckStrategy, check_type, typechecked

PROBE: str = """from collections.abc import Callable, Mapping
from pathlib import Path
import dispatchargs
import headlessenv
import fablewall
import breaker
import childproc
import findingrecord
import finding_contract
import handbackcontract
from orchestrator.core import handback_contract
from orchestrator.core.driver_contracts import HeadlessEnvironment, FableWall, Breaker, ChildProcess

arguments_parser: Callable[[object, str], dispatchargs.TransportArguments] = dispatchargs.parse_arguments
consumer_parser: Callable[[object, str], Mapping[str, object]] = arguments_parser
arguments_builder: Callable[[Mapping[str, object], float | None, str], dispatchargs.TransportArguments] = (
    dispatchargs.build_arguments
)
arguments_command: Callable[[str, Path, str, str, Path], list[str]] = dispatchargs.command
orchestrated_flows: Callable[[], frozenset[str]] = dispatchargs.orchestrated_flows

headless: HeadlessEnvironment = headlessenv
wall: FableWall = fablewall
quota: Breaker = breaker
process: ChildProcess = childproc
handback_module: handbackcontract.HandbackModule = handback_contract
findings: findingrecord.FindingContract = finding_contract
handback_rules: handbackcontract.HandbackContract = handbackcontract.HandbackContract(
    wire=handback_contract.wire,
    validate=handback_contract.validate,
    validate_event=handback_contract.validate_event,
    validate_waiting_prerequisites=handback_contract.validate_waiting_prerequisites,
    diagnostic=handback_contract.diagnostic,
    failure=handback_contract.failure,
    interrupted_failure=handback_contract.interrupted_failure,
    rejected=handback_contract.rejected,
)
"""
DEPENDENCIES: tuple[str, ...] = (
    "typeguard",
    "types-PyYAML",
    "types-jsonschema",
    "boto3-stubs[cognito-idp,ssm]",
    "chromadb==1.5.2",
    "ollama==0.6.1",
)
CHECK_TIMEOUT: int = 300
PLUGIN_TOP_DIRS: frozenset[str] = frozenset({"skills", "orchestrator", "scripts"})
"""The first path part of a driver tuple that names a file in the plugin."""
BEADMETA_READERS: frozenset[str] = frozenset({"constant", "members"})
"""The ``beadmeta`` functions whose first argument names a ``bead_metadata`` module member."""
SHARED_FIELD_READER: str = "line_values"
"""The ``handbackcontract`` function whose argument names a handback line schema field."""
DEPLOY_PIPELINE: str = "deploy"
DRIVER_RUNNER: str = "driver"

type Constants = dict[str, str | tuple[str, ...]]


def _value(node: ast.expr, known: Constants) -> str | tuple[str, ...] | None:
    """Evaluate a module-level string, or a tuple, list, set or frozenset of strings and names.

    Returns:
        The value, or None when the expression is not one of those.

    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return known.get(node.id)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "frozenset" and node.args:
        return _value(node.args[0], known)
    if not isinstance(node, ast.Tuple | ast.List | ast.Set):
        return None
    items: list[str | tuple[str, ...] | None] = [_value(item, known) for item in node.elts]
    texts: list[str] = [item for item in items if isinstance(item, str)]
    return tuple(texts) if len(texts) == len(items) else None


def module_constants(path: Path) -> Constants:
    """Read a module's top-level string constants and string collections without importing it.

    Returns:
        Each name bound at module level to a string or a collection of strings.

    """
    known: Constants = {}
    for statement in ast.parse(path.read_text(encoding="utf-8")).body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign):
            target, value = statement.target, statement.value
        if isinstance(target, ast.Name) and value is not None:
            evaluated: str | tuple[str, ...] | None = _value(value, known)
            if evaluated is not None:
                known[target.id] = evaluated
    return known


def _calls(tree: ast.AST, module: str, functions: frozenset[str]) -> list[ast.Call]:
    """Find the calls of ``module.function`` for the named functions.

    Returns:
        The call nodes.

    """
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == module
        and node.func.attr in functions
    ]


def _check_findings(drivers: Path) -> list[str]:
    """Compare every finding kind and the source the driver writes with the plugin's finding contract.

    Returns:
        One problem per value the contract does not define.

    """
    constants: Constants = module_constants(drivers / "findingrecord.py")
    problems: list[str] = [
        f"findingrecord.{name} = {value!r} is not a finding kind of finding_contract.py"
        for name, value in constants.items()
        if name.startswith("KIND_") and value not in FINDING_KINDS
    ]
    if constants.get("SOURCE") not in FINDING_SOURCES:
        problems.append(f"findingrecord.SOURCE = {constants.get('SOURCE')!r} is not a finding source")
    return problems


def _check_deploy_steps(drivers: Path, plugin_root: Path) -> list[str]:
    """Compare the deploy steps the driver implements with the steps the plugin says the driver runs.

    Returns:
        A problem naming each step only one side has.

    """
    path: Path = drivers / "storydeploy.py"
    constants: Constants = module_constants(path)
    steps: list[ast.Dict] = [
        statement.value
        for statement in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == "STEPS"
        and isinstance(statement.value, ast.Dict)
    ]
    keys: list[ast.expr] = [key for table in steps for key in table.keys if key is not None]
    named: list[str | tuple[str, ...] | None] = [_value(key, constants) for key in keys]
    implemented: set[str] = {name for name in named if isinstance(name, str)}
    document = check_type(
        json.loads((plugin_root / "skills/pipeline-contracts/schemas/pipeline-steps.json").read_text(encoding="utf-8")),
        dict[str, object],
    )
    pipelines = check_type(document["pipelines"], dict[str, object])
    kinds = check_type(check_type(pipelines[DEPLOY_PIPELINE], dict[str, object])["kinds"], dict[str, dict[str, object]])
    declared: set[str] = {name for name, kind in kinds.items() if kind.get("runBy") == DRIVER_RUNNER}
    return [
        *(
            f"storydeploy.STEPS implements {name!r}, which pipeline-steps.json gives no driver"
            for name in sorted(implemented - declared)
        ),
        *(
            f"pipeline-steps.json has the driver run {name!r}, which storydeploy.STEPS lacks"
            for name in sorted(declared - implemented)
        ),
    ]


def _schema_types(value: object) -> frozenset[str]:
    """Read the primitive types a projected field schema admits.

    Returns:
        Its explicit types, including anyOf alternatives.

    """
    node = check_type(value, dict[str, object])
    if "anyOf" in node:
        branches = check_type(node["anyOf"], list[object])
        return frozenset(kind for branch in branches for kind in _schema_types(branch))
    kind: object = node.get("type")
    return frozenset({kind}) if isinstance(kind, str) else frozenset(check_type(kind, list[str]))


def _string_arrays(value: object) -> bool:
    """Check the item type of every array alternative in a projected field.

    Returns:
        Whether every array contains strings.

    """
    node = check_type(value, dict[str, object])
    branches = check_type(node.get("anyOf", [node]), list[dict[str, object]])
    return all(
        check_type(branch["items"], dict[str, object]).get("type") == "string"
        for branch in branches
        if branch.get("type") == "array"
    )


def check_task_projection(plugin_root: Path) -> list[str]:
    """Compare the exact Task payload's projected fields with their metadata authority.

    Returns:
        Missing or incompatible field declarations, without running a pipeline.

    """
    metadata_path = plugin_root / "skills/beads-contract/schemas/bead-metadata.schema.json"
    task_path = plugin_root / "skills/pipeline-contracts/schemas/task-build-args.schema.json"
    metadata = check_type(json.loads(metadata_path.read_text(encoding="utf-8")), dict[str, object])
    task = check_type(json.loads(task_path.read_text(encoding="utf-8")), dict[str, object])
    definitions = check_type(task["$defs"], dict[str, object])
    arguments = check_type(definitions["TaskToDeployArgs"], dict[str, object])
    properties = check_type(arguments["properties"], dict[str, object])
    bead = check_type(properties["bead"], dict[str, object])
    fields = check_type(bead["properties"], dict[str, object])
    kinds: dict[str, frozenset[str]] = {
        "text": frozenset({"string"}),
        "list": frozenset({"array"}),
        "list-or-unknown": frozenset({"array", "null"}),
        "object-or-unknown": frozenset({"object", "null"}),
    }
    problems: list[str] = []
    for field in check_type(metadata["properties"], dict[str, object]).values():
        declaration = check_type(field, dict[str, object])
        if "x-contract" not in declaration:
            continue
        contract = check_type(declaration["x-contract"], dict[str, object])
        name = check_type(contract["argument"], str)
        kind = check_type(contract["kind"], str)
        if name not in fields or _schema_types(fields[name]) != kinds[kind]:
            problems.append(f"Task build argument bead.{name} does not match metadata kind {kind}")
            continue
        if kind in {"list", "list-or-unknown"} and not _string_arrays(fields[name]):
            problems.append(f"Task build argument bead.{name} must carry string items")
    if arguments.get("additionalProperties") is not False or bead.get("additionalProperties") is not False:
        problems.append("Task build arguments and bead projection must reject unknown keys")
    return problems


def _texts_of(path: Path) -> frozenset[str]:
    """Collect every string literal of a plugin module.

    Returns:
        The module's string literals.

    """
    tree: ast.Module = ast.parse(path.read_text(encoding="utf-8"))
    return frozenset(
        node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def _check_done_rule(drivers: Path, plugin_root: Path) -> list[str]:
    """Check that every elaboration step the driver's done rule names is a step the plugin plans.

    Returns:
        One problem per step description the plugin's elaboration flow does not spell.

    """
    flows: Path = plugin_root / "orchestrator" / "flows"
    planned: frozenset[str] = _texts_of(flows / "prd_to_spec.py") | _texts_of(flows / "elaboration_files.py")
    steps: str | tuple[str, ...] | None = module_constants(drivers / "elabmark.py").get("DONE_RULE_STEPS")
    named: tuple[str, ...] = steps if isinstance(steps, tuple) else ()
    problems: list[str] = [
        f"elabmark.DONE_RULE_STEPS names {step!r}, a step the elaboration plan lacks"
        for step in named
        if step not in planned
    ]
    return problems if named else ["elabmark.DONE_RULE_STEPS is missing or not a collection of step descriptions"]


def _check_plugin_paths(drivers: Path, plugin_root: Path) -> list[str]:
    """Check that every plugin file a driver module names by its path parts exists in the plugin.

    Returns:
        One problem per named file the plugin does not ship.

    """
    named: list[tuple[str, str, tuple[str, ...]]] = [
        (path.stem, name, value)
        for path in sorted(drivers.glob("*.py"))
        for name, value in module_constants(path).items()
        if isinstance(value, tuple) and len(value) > 1 and value[0] in PLUGIN_TOP_DIRS
    ]
    return [
        f"{module}.{name} names {'/'.join(parts)}, which the plugin does not ship"
        for module, name, parts in named
        if not plugin_root.joinpath(*parts).exists()
    ]


def _first_arguments(drivers: Path, module: str, functions: frozenset[str]) -> set[str]:
    """Collect the literal first argument of every driver call of ``module.function``.

    Returns:
        The names the driver passes.

    """
    constants: Constants = {}
    trees: list[ast.Module] = []
    path: Path
    for path in sorted(drivers.glob("*.py")):
        constants.update(module_constants(path))
        trees.append(ast.parse(path.read_text(encoding="utf-8")))
    arguments: list[str | tuple[str, ...] | None] = [
        _value(call.args[0], constants) for tree in trees for call in _calls(tree, module, functions) if call.args
    ]
    return {argument for argument in arguments if isinstance(argument, str)}


def _check_bead_metadata(drivers: Path, plugin_root: Path) -> list[str]:
    """Check that every bead metadata name the driver reads is defined by the plugin's generated module.

    Returns:
        One problem per name the module does not define.

    """
    defined: Constants = module_constants(plugin_root / "skills" / "beads-contract" / "scripts" / "bead_metadata.py")
    required: Constants = module_constants(drivers / "beadmeta.py")
    named: set[str] = _first_arguments(drivers, "beadmeta", BEADMETA_READERS)
    for group in ("REQUIRED_CONSTANTS", "REQUIRED_MEMBERS"):
        listed: str | tuple[str, ...] | None = required.get(group)
        named.update(listed if isinstance(listed, tuple) else ())
    return [
        f"the driver reads bead_metadata.{name}, which the plugin does not define"
        for name in sorted(named - set(defined))
    ]


def _check_handback_line(drivers: Path, plugin_root: Path) -> list[str]:
    """Check that every handback line field whose values the driver reads has an enum in the plugin's schema.

    Returns:
        One problem per field the schema gives no enum.

    """
    schema = check_type(
        json.loads(
            (plugin_root / "skills/pipeline-contracts/schemas/handback-line.schema.json").read_text(encoding="utf-8"),
        ),
        dict[str, object],
    )
    properties = check_type(schema["properties"], dict[str, dict[str, object]])
    fields: set[str] = _first_arguments(drivers, "handbackcontract", frozenset({SHARED_FIELD_READER}))
    return [
        f"the driver reads the values of handback line field {field!r}, which handback-line.schema.json gives no enum"
        for field in sorted(fields)
        if not isinstance(properties.get(field, {}).get("enum"), list)
    ]


def check_shared_values(drivers: Path, plugin_root: Path) -> list[str]:
    """Compare the values the driver and the plugin share, where the type check cannot see them.

    Returns:
        Every disagreement found.

    """
    return [
        *_check_findings(drivers),
        *_check_deploy_steps(drivers, plugin_root),
        *_check_done_rule(drivers, plugin_root),
        *_check_plugin_paths(drivers, plugin_root),
        *_check_bead_metadata(drivers, plugin_root),
        *_check_handback_line(drivers, plugin_root),
    ]


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_contracts(control_root: Path, plugin_root: Path) -> int:
    """Type-check the real driver producers against the plugin's contract Protocols.

    Returns:
        The static checker's exit status.

    Raises:
        FileNotFoundError: A required checkout or the uv executable is unavailable.
        TypeError: A checkout argument is not a path.

    """
    if not isinstance(control_root, Path) or not isinstance(plugin_root, Path):
        message: str = "Contract checking requires concrete checkout paths"
        raise TypeError(message)
    control_root = control_root.resolve()
    plugin_root = plugin_root.resolve()
    drivers: Path = control_root.joinpath(*DRIVER_DIR_PARTS)
    required: list[Path] = [
        drivers / f"{name}.py"
        for name in (
            "headlessenv",
            "fablewall",
            "findingrecord",
            "breaker",
            "childproc",
            "handbackcontract",
            "dispatchargs",
            "orchestrated",
            "workitems",
        )
    ]
    required.extend(
        plugin_root / "orchestrator" / "core" / name for name in ("driver_contracts.py", "handback_contract.py")
    )
    beads_scripts: Path = plugin_root / "skills" / "beads-contract" / "scripts"
    pipeline_scripts: Path = plugin_root / "skills" / "pipeline-contracts" / "scripts"
    required.extend((beads_scripts / "bead_metadata.py", pipeline_scripts / "driver_surface_types.py"))
    path: Path
    for path in required:
        if not path.is_file():
            message = f"Driver contract check requires source file: {path}"
            raise FileNotFoundError(message)
    problems: list[str] = check_task_projection(plugin_root) + check_shared_values(drivers, plugin_root)
    if problems:
        sys.stderr.write("\n".join(problems) + "\n")
        return 1
    uv: str | None = shutil.which("uv")
    if uv is None:
        message = "Driver contract check requires uv on PATH"
        raise FileNotFoundError(message)
    command: list[str] = [uv, "tool", "run"]
    dependency: str
    for dependency in DEPENDENCIES:
        command.extend(["--with", dependency])
    command.extend([
        "mypy",
        "--strict",
        "--disallow-any-explicit",
        "--disallow-any-unimported",
        "--disallow-any-decorated",
        "--follow-imports=normal",
        "--no-incremental",
        "--python-version=3.14",
    ])
    environment: dict[str, str] = dict(os.environ)
    environment["MYPYPATH"] = os.pathsep.join(
        (
            str(drivers),
            str(plugin_root),
            str(plugin_root / "scripts" / "portfolio"),
            str(beads_scripts),
            str(plugin_root / "skills" / "artifact-handoff"),
            str(plugin_root / "skills" / "artifact-handoff" / "scripts"),
            str(plugin_root / "skills" / "wsjf" / "scripts"),
            str(pipeline_scripts),
            str(plugin_root / "skills" / "resource-naming" / "scripts"),
            str(plugin_root / "skills" / "find-specialists" / "scripts"),
            str(plugin_root / "skills" / "log-architecture-review" / "scripts"),
        ),
    )
    temporary: str
    with tempfile.TemporaryDirectory(prefix="atw-driver-contract-") as temporary:
        probe: Path = Path(temporary) / "producer_conformance.py"
        probe.write_text(PROBE, encoding="utf-8")
        command.extend((
            str(probe),
            str(plugin_root / "orchestrator"),
            str(drivers / "dispatchargs.py"),
            str(drivers / "findingrecord.py"),
            str(drivers / "handbackcontract.py"),
            str(drivers / "orchestrated.py"),
            str(drivers / "workitems.py"),
        ))
        # ruff: ignore[subprocess-without-shell-equals-true] - Resolved uv and fixed static mypy argv; no shell.
        return subprocess.run(command, cwd=control_root, env=environment, check=False, timeout=CHECK_TIMEOUT).returncode


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> int:
    """Resolve portable checkout configuration and run the static check.

    Returns:
        Zero on conformance, or a nonzero diagnostic status.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--control-root",
        type=Path,
        default=os.environ.get(CONTROL_REPO_ENV),
        help=f"Control checkout (defaults to {CONTROL_REPO_ENV})",
    )
    parser.add_argument("--plugin-root", type=Path, default=Path(__file__).resolve().parents[1])
    args: argparse.Namespace = parser.parse_args()
    if args.control_root is None:
        parser.error(
            f"set {CONTROL_REPO_ENV}, or pass --control-root for the real control checkout",
        )
    try:
        return check_contracts(check_type(args.control_root, Path), check_type(args.plugin_root, Path))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"Driver contract check failed: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
