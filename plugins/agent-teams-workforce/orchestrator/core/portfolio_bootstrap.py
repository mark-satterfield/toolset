"""Step execution and durable artifact contracts."""

import sys
from pathlib import Path

# Portfolio tools use a single top-level module namespace in both source and cache.
_PORTFOLIO: str = str(Path(__file__).resolve().parents[2] / "scripts" / "portfolio")
if _PORTFOLIO not in sys.path:
    sys.path.insert(0, _PORTFOLIO)

_BEADS: str = str(Path(__file__).resolve().parents[2] / "skills" / "beads-contract" / "scripts")
if _BEADS not in sys.path:
    sys.path.insert(0, _BEADS)

_WSJF: str = str(Path(__file__).resolve().parents[2] / "skills" / "wsjf" / "scripts")
if _WSJF not in sys.path:
    sys.path.insert(0, _WSJF)
