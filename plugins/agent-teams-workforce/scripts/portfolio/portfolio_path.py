"""Expose the bundled orchestrator package to standalone portfolio commands."""

import sys
from pathlib import Path

PLUGIN_ROOT = str(Path(__file__).resolve().parents[2])
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)
