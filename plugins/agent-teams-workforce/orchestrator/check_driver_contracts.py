"""Check real driver contracts and every statically imported pipeline producer."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed static checker argv, no shell or workflow.
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "pipeline-contracts" / "scripts"))

from driver_surface_types import CONTROL_REPO_ENV, DRIVER_DIR_PARTS
from typeguard import CollectionCheckStrategy, check_type, typechecked

PROBE: str = """import headlessenv
import fablewall
import breaker
import childproc
import handbackcontract
from orchestrator.core import handback_contract
from orchestrator.core.driver_contracts import HeadlessEnvironment, FableWall, Breaker, ChildProcess

headless: HeadlessEnvironment = headlessenv
wall: FableWall = fablewall
quota: Breaker = breaker
process: ChildProcess = childproc
handback_rules: handbackcontract.HandbackContract = handbackcontract.HandbackContract(
    wire=handback_contract.wire,
    validate=handback_contract.validate,
    validate_event=handback_contract.validate_event,
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
        drivers / f"{name}.py" for name in ("headlessenv", "fablewall", "breaker", "childproc", "handbackcontract")
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
        ),
    )
    temporary: str
    with tempfile.TemporaryDirectory(prefix="atw-driver-contract-") as temporary:
        probe: Path = Path(temporary) / "producer_conformance.py"
        probe.write_text(PROBE, encoding="utf-8")
        command.extend((str(probe), str(plugin_root / "orchestrator")))
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
        default=os.environ.get(CONTROL_REPO_ENV) or os.environ.get("SKILLSPOKE_CC"),
        help=f"Control checkout (defaults to {CONTROL_REPO_ENV}, then SKILLSPOKE_CC)",
    )
    parser.add_argument("--plugin-root", type=Path, default=Path(__file__).resolve().parents[1])
    args: argparse.Namespace = parser.parse_args()
    if args.control_root is None:
        parser.error(
            f"set {CONTROL_REPO_ENV} or SKILLSPOKE_CC, or pass --control-root for the real control checkout",
        )
    try:
        return check_contracts(check_type(args.control_root, Path), check_type(args.plugin_root, Path))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"Driver contract check failed: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
