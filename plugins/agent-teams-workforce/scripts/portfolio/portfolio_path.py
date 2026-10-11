"""Expose the bundled orchestrator package and skill contracts to standalone portfolio commands."""

import sys
from pathlib import Path
from typing import Final

_PLUGIN_DIR: Final[Path] = Path(__file__).resolve().parents[2]
PLUGIN_ROOT: Final[str] = str(_PLUGIN_DIR)
ARTIFACT_HANDOFF_SCRIPTS: Final[str] = str(_PLUGIN_DIR / "skills" / "artifact-handoff" / "scripts")
BEADS_CONTRACT_SCRIPTS: Final[str] = str(_PLUGIN_DIR / "skills" / "beads-contract" / "scripts")

_entry: str
for _entry in (BEADS_CONTRACT_SCRIPTS, ARTIFACT_HANDOFF_SCRIPTS, PLUGIN_ROOT):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)
