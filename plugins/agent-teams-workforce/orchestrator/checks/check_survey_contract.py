"""Fail when skills/artifact-handoff/survey_contract.py is stale against survey.schema.json.

The survey schema is the one definition of the architecture survey and baseline; the Python module
is generated from it by skills/artifact-handoff/scripts/gen_survey_contract.py. This check runs that
generator's ``--check`` mode, which exits non-zero when the generated module differs from what the
schema produces.
"""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs the plugin's own generator with a fixed argv, no shell.
import sys
from pathlib import Path

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.checks.check_support import report, require

PLUGIN: Path = Path(__file__).resolve().parents[2]
GENERATOR: Path = PLUGIN / "skills" / "artifact-handoff" / "scripts" / "gen_survey_contract.py"


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Run the survey contract generator in check mode and require a current module."""
    result: subprocess.CompletedProcess[str] = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv: this interpreter and the plugin's generator.
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    require(result.returncode == 0, f"survey_contract.py is stale: {result.stderr.strip() or result.stdout.strip()}")
    report("PASS: survey_contract.py is current with survey.schema.json")


if __name__ == "__main__":
    main()
