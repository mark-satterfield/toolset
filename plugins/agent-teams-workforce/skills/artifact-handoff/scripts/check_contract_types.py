"""Fail when a generated artifact-handoff contract module is stale.

Regenerates every module ``generate_contract_types.py`` owns in memory from its schema and exits 1,
naming each file, when the committed module differs (which includes a schema whose hash no longer
matches the module's ``SCHEMA_SHA256``).
"""

from generate_contract_types import main

if __name__ == "__main__":
    raise SystemExit(main(["--check"]))
