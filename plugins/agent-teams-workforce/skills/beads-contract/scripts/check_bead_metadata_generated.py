#!/usr/bin/env python3
"""Fail when bead_metadata.py is not what schemas/bead-metadata.schema.json generates.

Regenerates the module in memory with generate_bead_metadata.py and compares it with the
file on disk. Exit 0 when current, 1 when stale (the diff is printed on stderr).
"""

from __future__ import annotations

import difflib
import sys

from generate_bead_metadata import MODULE_PATH, generated_text


def main() -> int:
    """Compare the generated module with the file on disk.

    Returns:
        0 when bead_metadata.py is current; 1 when it is stale or missing.

    """
    expected: str = generated_text()
    current: str = MODULE_PATH.read_text(encoding="utf-8") if MODULE_PATH.is_file() else ""
    if current == expected:
        sys.stdout.write(f"{MODULE_PATH.name} is current with its schema\n")
        return 0
    diff: list[str] = list(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=f"{MODULE_PATH.name} (on disk)",
            tofile=f"{MODULE_PATH.name} (generated)",
        ),
    )
    sys.stderr.write("".join(diff))
    sys.stderr.write(f"{MODULE_PATH} is stale: run generate_bead_metadata.py to regenerate it\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
