"""Fail when the generated ``infra_vocabulary.py`` is stale against its schema.

Regenerates the module in memory from ``schemas/infra-vocabulary.schema.json`` with
``gen_infra_vocabulary.render`` and compares it with the committed file. Exits 0 when they are
equal and 1, naming the file, when they differ or the file is missing.
"""

from __future__ import annotations

import sys

from gen_infra_vocabulary import OUTPUT_FILE, load_schema, render


def main() -> int:
    """Compare the committed module with a fresh rendering of the schema.

    Returns:
        0 when ``infra_vocabulary.py`` is current, 1 when it is stale or missing.

    """
    expected: str = render(load_schema())
    if not OUTPUT_FILE.is_file():
        sys.stderr.write(f"{OUTPUT_FILE} is missing: run python3 {OUTPUT_FILE.parent / 'gen_infra_vocabulary.py'}\n")
        return 1
    if OUTPUT_FILE.read_text(encoding="utf-8") != expected:
        sys.stderr.write(f"{OUTPUT_FILE} is stale: run python3 {OUTPUT_FILE.parent / 'gen_infra_vocabulary.py'}\n")
        return 1
    sys.stdout.write(f"{OUTPUT_FILE.name} is current\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
