"""Fail when the generated ``target_contract.py`` is stale against its schema or the schema is invalid.

Checks ``schemas/target-report.schema.json`` against the JSON Schema 2020-12 meta-schema,
regenerates the module in memory with ``generate_target_contract.render`` and compares it with
the file on disk. Exits 0 when the schema is valid and the module is current, and 1, naming the
problem, otherwise.
"""

from __future__ import annotations

import sys

from generate_target_contract import OUTPUT_PATH, SCHEMA_PATH, load_schema, render
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


def main() -> int:
    """Check the schema and compare the generated module with a fresh rendering of it.

    Returns:
        0 when the schema is valid and ``target_contract.py`` is current, 1 otherwise.

    """
    schema: dict[str, object] = load_schema()
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        sys.stderr.write(f"{SCHEMA_PATH} is not a valid JSON Schema: {exc.message}\n")
        return 1
    expected: str = render(schema)
    regenerate: str = f"run python3 {OUTPUT_PATH.parent / 'generate_target_contract.py'}"
    if not OUTPUT_PATH.is_file():
        sys.stderr.write(f"{OUTPUT_PATH} is missing: {regenerate}\n")
        return 1
    if OUTPUT_PATH.read_text(encoding="utf-8") != expected:
        sys.stderr.write(f"{OUTPUT_PATH} is stale against {SCHEMA_PATH}: {regenerate}\n")
        return 1
    sys.stdout.write(f"{OUTPUT_PATH.name} is current\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
