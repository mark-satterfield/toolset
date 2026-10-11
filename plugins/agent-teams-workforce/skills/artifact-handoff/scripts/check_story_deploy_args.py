"""Fail when the Story deploy argument contract's derived copies are stale against its schema.

Checks three things and exits 1, naming each problem, when any fails:

1. ``story_deploy_args.py`` equals a fresh rendering of ``schemas/story-deploy-args.schema.json``
   by ``generate_story_deploy_args.expected`` (its ``SCHEMA_SHA256`` is part of that rendering).
2. The canonical shared block ``scripts/shared-blocks/story-deploy-args.js`` carries the schema
   placeholder that ``scripts/shared-blocks.mjs`` fills from the schema.
3. Every workflow copy of that shared block embeds exactly the current schema.

Exits 0 when all three hold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

from generate_story_deploy_args import OUTPUT_FILE, SCHEMA_FILE, expected

PLUGIN_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
BLOCK_NAME: Final[str] = "story-deploy-args"
BLOCK_FILE: Final[Path] = PLUGIN_ROOT / "scripts" / "shared-blocks" / f"{BLOCK_NAME}.js"
WORKFLOWS: Final[Path] = PLUGIN_ROOT / "workflows"
PLACEHOLDER: Final[str] = "const STORY_DEPLOY_ARGS_SCHEMA = /* STORY_DEPLOY_ARGS_SCHEMA */ {}"
FILLED_PREFIX: Final[str] = "const STORY_DEPLOY_ARGS_SCHEMA = "
BEGIN: Final[str] = f"// ===== SHARED BLOCK {BLOCK_NAME} — BEGIN"
END: Final[str] = f"// ===== SHARED BLOCK {BLOCK_NAME} — END ====="


def _module_problems() -> list[str]:
    generator: Path = OUTPUT_FILE.parent / "generate_story_deploy_args.py"
    if not OUTPUT_FILE.is_file():
        return [f"{OUTPUT_FILE} is missing: run python3 {generator}"]
    if OUTPUT_FILE.read_text(encoding="utf-8") != expected():
        return [f"{OUTPUT_FILE} is stale: run python3 {generator}"]
    return []


def _block_problems() -> list[str]:
    if not BLOCK_FILE.is_file():
        return [f"{BLOCK_FILE} is missing"]
    if PLACEHOLDER not in BLOCK_FILE.read_text(encoding="utf-8").splitlines():
        return [f"{BLOCK_FILE} lacks the line {PLACEHOLDER!r}"]
    return []


def _copy_problems() -> list[str]:
    schema: object = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    problems: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.js")):
        source: str = path.read_text(encoding="utf-8")
        begin: int = source.find(BEGIN)
        end: int = source.find(END)
        if begin < 0 or end < begin:
            continue
        lines: list[str] = [line for line in source[begin:end].splitlines() if line.startswith(FILLED_PREFIX)]
        if len(lines) != 1:
            problems.append(f"{path.name}: the {BLOCK_NAME} block embeds no single schema line")
            continue
        try:
            embedded: object = json.loads(lines[0].removeprefix(FILLED_PREFIX))
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name}: the embedded schema is not JSON: {exc}")
            continue
        if embedded != schema:
            problems.append(f"{path.name}: the embedded schema is stale (run node scripts/shared-blocks.mjs --write)")
    return problems


def main() -> int:
    """Check the generated module, the canonical block and its workflow copies.

    Returns:
        0 when every derived copy is current, 1 otherwise.

    """
    problems: list[str] = [*_module_problems(), *_block_problems(), *_copy_problems()]
    for problem in problems:
        sys.stderr.write(problem + "\n")
    if problems:
        return 1
    sys.stdout.write(f"{OUTPUT_FILE.name} and the {BLOCK_NAME} shared block are current\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
