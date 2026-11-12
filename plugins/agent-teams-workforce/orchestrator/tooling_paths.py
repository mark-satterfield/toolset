"""Print how the build checkpoint treats each changed path of a Story worktree.

The public, stable command for the build's tooling-path rule
(``orchestrator.flows.build_workspace.classify_tooling_paths``), for a caller outside the plugin
such as the control repository's supervisor::

    python <plugin root>/orchestrator/tooling_paths.py <worktree> [<path>...]

With no path it reads the worktree's changed paths from ``git status``. It needs
``ATW_CONTROL_REPO`` and prints one JSON object, ``{"product": [...], "preserved": [...],
"refused": [...]}``: the paths the checkpoint commits, the tooling paths it leaves uncommitted,
and each path whose ownership it refuses, as ``<path>: <reason>``. It exits 0 with that object,
2 on a usage error, and 1 when the rule cannot run, with the reason on standard error; a changed
configuration file it cannot read or decode is such a case, never a refused path.
"""

from __future__ import annotations

import configparser
import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

import yaml
from typeguard import TypeCheckError

if TYPE_CHECKING:
    from collections.abc import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.core.tools import Tools
from orchestrator.flows.build_workspace import ToolingPaths, classify_tooling_paths

USAGE: Final = "usage: tooling_paths.py <worktree> [<path>...]\n"
USAGE_EXIT: Final = 2
FAILURE_EXIT: Final = 1


def main(argv: Sequence[str]) -> int:
    """Classify the named or changed paths of one worktree and print the result as JSON.

    Returns:
        The process exit code.

    """
    if not argv or not Path(argv[0]).is_dir():
        sys.stderr.write(USAGE)
        return USAGE_EXIT
    tree: Path = Path(argv[0]).resolve()
    paths: list[str] | None = list(argv[1:]) or None
    try:
        with tempfile.TemporaryDirectory() as evidence:
            found: ToolingPaths = classify_tooling_paths(Tools(Path(evidence)), tree, paths)
    except (OSError, ValueError, KeyError, TypeCheckError, configparser.Error, yaml.YAMLError) as error:
        sys.stderr.write(f"the tooling-path rule on {tree} did not run: {error}\n")
        return FAILURE_EXIT
    printed: dict[str, list[str]] = {
        "product": list(found.product),
        "preserved": list(found.preserved),
        "refused": list(found.refused),
    }
    sys.stdout.write(json.dumps(printed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
