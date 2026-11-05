"""Check real driver contracts and every statically imported pipeline producer."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed static checker argv, no shell or workflow.
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "pipeline-contracts" / "scripts"))

from driver_surface_types import CONTROL_REPO_ENV, DRIVER_DIR_PARTS
from typeguard import CollectionCheckStrategy, check_type, typechecked

PROBE: str = """from collections.abc import Callable, Mapping
from pathlib import Path
import dispatchargs
import headlessenv
import fablewall
import breaker
import childproc
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
    problems: list[str] = check_task_projection(plugin_root)
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
