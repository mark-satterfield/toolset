#!/usr/bin/env python3
"""Fail when composites_contract.py or composite-phases.js is not what composites.json generates.

Validates schemas/composites.json under schemas/composites.schema.json, regenerates both files in
memory with generate_composites.py and compares them with the files on disk. Exit 0 when both are
current, 1 when either is stale or the data is invalid (the reason and any diff go to stderr).
"""

from __future__ import annotations

import difflib
import sys
from typing import TYPE_CHECKING

from generate_composites import ContractError, generated

if TYPE_CHECKING:
    from pathlib import Path


def main() -> int:
    """Compare each generated file with the file on disk.

    Returns:
        0 when both files are current; 1 when the data is invalid or a file is stale or missing.

    """
    try:
        expected: dict[Path, str] = generated()
    except ContractError as exc:
        sys.stderr.write(f"composites.json is invalid: {exc}\n")
        return 1
    status: int = 0
    for path, text in expected.items():
        current: str = path.read_text(encoding="utf-8") if path.is_file() else ""
        if current == text:
            sys.stdout.write(f"{path.name} is current with composites.json\n")
            continue
        diff: list[str] = list(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                text.splitlines(keepends=True),
                fromfile=f"{path.name} (on disk)",
                tofile=f"{path.name} (generated)",
            ),
        )
        sys.stderr.write("".join(diff))
        sys.stderr.write(f"{path} is stale: run generate_composites.py to regenerate it\n")
        status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
