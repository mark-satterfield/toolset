"""Accept an artifact and record its provenance in one deterministic invocation.

The artifact-handoff skill owns this operation. Acceptance remains delegated to
jsonartifact.py; a rejected or pending candidate never invokes the recorder.
A recording failure keeps the accepted result: the receipt says `recorded: false` and why.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def publish(accept_args: list[str], record_argv: list[str]) -> dict:
    """Return the acceptance receipt, with whether its provenance was recorded."""
    if not record_argv or any(not isinstance(x, str) or not x for x in record_argv):
        raise ValueError("record argv must be a nonempty array of nonempty strings")
    accepted = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("jsonartifact.py")),
            *accept_args,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if accepted.returncode:
        raise ValueError(
            f"artifact acceptance exited {accepted.returncode}: "
            f"{(accepted.stdout + accepted.stderr).strip()[-1000:]}"
        )
    receipt = json.loads(accepted.stdout)
    if not isinstance(receipt, dict):
        raise TypeError("artifact acceptance did not return an object")
    if receipt.get("pending") is True:
        return receipt
    artifact = receipt.get("artifactPath")
    if not isinstance(artifact, str) or not artifact:
        raise ValueError("artifact acceptance did not return an artifact path")
    # The caller supplies the existing recorder's argv, never shell text. Require
    # that it records precisely the accepted path, not another artifact.
    if len(record_argv) < 4 or record_argv[2:4] != ["record", artifact]:
        raise ValueError("record argv must name the accepted artifact")
    try:
        recorded = subprocess.run(
            record_argv, capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {**receipt, "recorded": False, "recordError": str(exc)[-1000:]}
    if recorded.returncode:
        return {
            **receipt,
            "recorded": False,
            "recordError": f"artifact recording exited {recorded.returncode}: "
            f"{(recorded.stdout + recorded.stderr).strip()[-1000:]}",
        }
    return {**receipt, "recorded": True}


def main() -> int:
    """Forward acceptance options after -- and emit one result object."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-argv-json", required=True)
    parser.add_argument("accept_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        record_argv = json.loads(args.record_argv_json)
        if not isinstance(record_argv, list):
            raise TypeError("record argv must be an array")
        accept_args = args.accept_args
        if accept_args[:1] == ["--"]:
            accept_args = accept_args[1:]
        print(json.dumps(publish(accept_args, record_argv)))
        return 0
    except (OSError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
