"""Ask the Claude CLI whether the account serves: the account-wall probe the driver runs.

While a quota hold stands the driver runs this command (the driver-surface contract's
``WALL_PROBE_COMMAND``) with its own Python interpreter and ``--stream <file>``. It runs one
tool-less ``haiku`` prompt in a temporary directory with the inherited environment, saves what the
prompt printed to the stream file, and prints one ``WallProbeResult`` as JSON on standard output.
It exits 0 whenever it printed a result, unavailable included.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.core.agent_process import WALL_PROBE_ARGUMENTS, WALL_PROBE_PROMPT, WallProbe, wall_probe_result

# isort: split
# agent_process puts the pipeline-contracts scripts directory on sys.path; the contract import follows it.
from driver_surface_types import WALL_PROBE_TIMEOUT, WallProbeResult


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def probe(stream: Path, executable: str = "claude") -> WallProbeResult:
    """Run the account-wall probe once.

    Args:
        stream: The file the prompt's output is saved to.
        executable: The Claude CLI to run.

    Returns:
        The probe's result.

    """
    with tempfile.TemporaryDirectory(prefix="atw-wall-probe-") as directory:
        return wall_probe_result(
            WallProbe(
                [
                    shutil.which(executable) or executable,
                    "-p",
                    "--output-format",
                    "stream-json",
                    "--verbose",
                    *WALL_PROBE_ARGUMENTS,
                ],
                WALL_PROBE_PROMPT,
                Path(directory),
                dict(os.environ),
                stream,
                WALL_PROBE_TIMEOUT,
            ),
        )


def main(argv: list[str] | None = None) -> int:
    """Run the probe and print its result.

    Args:
        argv: Command-line arguments, or None for sys.argv.

    Returns:
        0 once the result is printed.

    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, required=True, help="file the prompt's output is saved to")
    parser.add_argument("--executable", default="claude", help="the Claude CLI to run")
    options: argparse.Namespace = parser.parse_args(argv)
    stream: Path = options.stream
    stream.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout.write(json.dumps(probe(stream, str(options.executable))) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
