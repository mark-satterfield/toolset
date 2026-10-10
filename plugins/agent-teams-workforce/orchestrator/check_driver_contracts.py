"""Statically verify the actual control producers against plugin contracts."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Fixed static checker argv, no shell or workflow.
import sys
import tempfile
from pathlib import Path

from typeguard import CollectionCheckStrategy, check_type, typechecked

PROBE = """import headlessenv
import fablewall
import breaker
import childproc
import artifactio
from orchestrator.core.driver_contracts import HeadlessEnvironment, FableWall, Breaker, ChildProcess
from orchestrator.core.artifact_contract import ArtifactProducer

headless: HeadlessEnvironment = headlessenv
wall: FableWall = fablewall
quota: Breaker = breaker
process: ChildProcess = childproc
artifacts: ArtifactProducer = artifactio.ArtifactProducer()
"""
DEPENDENCIES = (
    "typeguard",
    "types-PyYAML",
    "types-jsonschema",
    "boto3-stubs[cognito-idp,ssm]",
    "chromadb==1.5.2",
    "ollama==0.6.1",
)
CHECK_TIMEOUT = 300


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def check_contracts(control_root: Path, plugin_root: Path) -> int:
    """Type-check real producer assignments without importing or running them.

    Returns:
        The static checker's exit status.

    Raises:
        FileNotFoundError: A required checkout or the uv executable is unavailable.

    """
    control_root = control_root.resolve()
    plugin_root = plugin_root.resolve()
    drivers = control_root / "ops" / "sdlc-automation"
    required = [drivers / f"{name}.py" for name in ("headlessenv", "fablewall", "breaker", "childproc", "artifactio")]
    required.extend(
        plugin_root / "orchestrator" / "core" / name for name in ("driver_contracts.py", "artifact_contract.py")
    )
    for path in required:
        if not path.is_file():
            message = f"Driver contract check requires source file: {path}"
            raise FileNotFoundError(message)
    uv = shutil.which("uv")
    if uv is None:
        message = "Driver contract check requires uv on PATH"
        raise FileNotFoundError(message)
    command = [uv, "tool", "run"]
    for dependency in DEPENDENCIES:
        command.extend(["--with", dependency])
    command.extend(["mypy", "--strict", "--follow-imports=normal", "--no-incremental", "--python-version=3.14"])
    environment = dict(os.environ)
    environment["MYPYPATH"] = os.pathsep.join((str(drivers), str(plugin_root)))
    with tempfile.TemporaryDirectory(prefix="atw-driver-contract-") as temporary:
        probe = Path(temporary) / "producer_conformance.py"
        probe.write_text(PROBE, encoding="utf-8")
        command.append(str(probe))
        # ruff: ignore[subprocess-without-shell-equals-true] - Resolved uv and fixed static mypy argv; no shell.
        return subprocess.run(command, cwd=control_root, env=environment, check=False, timeout=CHECK_TIMEOUT).returncode


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> int:
    """Resolve portable checkout configuration and run the static check.

    Returns:
        Zero on conformance, or a nonzero diagnostic status.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--control-root",
        type=Path,
        default=os.environ.get("ATW_CONTROL_REPO") or os.environ.get("SKILLSPOKE_CC"),
        help="Control checkout (defaults to ATW_CONTROL_REPO, then SKILLSPOKE_CC)",
    )
    parser.add_argument("--plugin-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if args.control_root is None:
        parser.error(
            "set ATW_CONTROL_REPO or SKILLSPOKE_CC, or pass --control-root for the real control checkout",
        )
    try:
        return check_contracts(check_type(args.control_root, Path), check_type(args.plugin_root, Path))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"Driver contract check failed: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
