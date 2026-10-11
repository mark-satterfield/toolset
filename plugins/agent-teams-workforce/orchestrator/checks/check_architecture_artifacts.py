"""Fail when the architecture artifact types or their inlined workflow copies are stale.

The architecture writer, review and conformance schemas (with architecture-common.schema.json) are
the one definition of those artifacts. Two consumers are generated from them:

- skills/artifact-handoff/scripts/architecture_artifacts.py, by generate_architecture_types.py,
  checked with that generator's ``--check`` mode;
- the ``architecture-artifacts`` shared block that scripts/shared-blocks.mjs fills from the schemas
  and inlines into every workflow its SHARED_BLOCKS entry requires, checked by comparing each
  workflow's copy with the block shared-blocks.mjs builds now.
"""

from __future__ import annotations

import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Runs the plugin's own generators with a fixed argv, no shell.
import sys
from pathlib import Path
from typing import Final

from typeguard import CollectionCheckStrategy, typechecked

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from orchestrator.checks.check_support import report, require

PLUGIN: Final[Path] = Path(__file__).resolve().parents[2]
GENERATOR: Final[Path] = PLUGIN / "skills" / "artifact-handoff" / "scripts" / "generate_architecture_types.py"
SHARED_BLOCKS_MODULE: Final[Path] = PLUGIN / "scripts" / "shared-blocks.mjs"
WORKFLOWS: Final[Path] = PLUGIN / "workflows"
BLOCK_NAME: Final[str] = "architecture-artifacts"
BLOCK_CHECK: Final[str] = """
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
const [name, workflows, modulePath] = process.argv.slice(1)
const { SHARED_BLOCKS, canonicalBlock, extractBlock } = await import(pathToFileURL(modulePath).href)
const entry = SHARED_BLOCKS.find((block) => block.name === name)
if (!entry) { console.error(`shared-blocks.mjs lists no block ${name}`); process.exit(1) }
const text = canonicalBlock(name)
const copyOf = (file) => extractBlock(readFileSync(join(workflows, file), 'utf8'), name)
const stale = entry.requiredIn.filter((file) => copyOf(file) !== text)
if (stale.length) { console.error(`stale ${name} copies: ${stale.join(', ')}`); process.exit(1) }
console.log(`${name} current in ${entry.requiredIn.join(', ')}`)
"""


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one fixed argv without a shell and capture its text output.

    Args:
        argv: The program and its arguments.

    Returns:
        The completed process.

    Raises:
        ValueError: ``argv`` is empty.

    """
    if not argv:
        message: str = "argv must name a program"
        raise ValueError(message)
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - Fixed argv built from plugin paths.
        argv,
        capture_output=True,
        text=True,
        check=False,
    )


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def _output(result: subprocess.CompletedProcess[str]) -> str:
    """Return the most useful text a finished process printed.

    Returns:
        Its stripped stderr, or its stripped stdout when stderr is empty.

    """
    return result.stderr.strip() or result.stdout.strip()


@typechecked(collection_check_strategy=CollectionCheckStrategy.ALL_ITEMS)
def main() -> None:
    """Require the generated Python module and every inlined workflow copy to be current.

    Raises:
        AssertionError: A generated copy is stale, or node is not on PATH.

    """
    generated: subprocess.CompletedProcess[str] = _run([sys.executable, str(GENERATOR), "--check"])
    require(generated.returncode == 0, f"architecture_artifacts.py is stale: {_output(generated)}")
    node: str | None = shutil.which("node")
    if node is None:
        message: str = "node is not on PATH; cannot check the architecture-artifacts workflow block"
        raise AssertionError(message)
    inlined: subprocess.CompletedProcess[str] = _run(
        [node, "--input-type=module", "-e", BLOCK_CHECK, BLOCK_NAME, str(WORKFLOWS), str(SHARED_BLOCKS_MODULE)],
    )
    require(inlined.returncode == 0, f"workflow architecture-artifacts block is stale: {_output(inlined)}")
    report("PASS: architecture_artifacts.py and the inlined workflow block are current with the architecture schemas")


if __name__ == "__main__":
    main()
