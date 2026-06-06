#!/usr/bin/env python3
"""
check_schema — schema self-validation.

Asserts that the CDS JSON Schema is itself a structurally valid JSON Schema
under the 2020-12 dialect, and that it declares the two identity keywords a
well-formed schema document should carry: $schema (the dialect it speaks) and
$id (its stable identifier).

This check asserts PROPERTIES of the live schema file. It hardcodes no theme
names, palette keys, role names, counts, or swatch values — a different valid
CDS configuration must still pass, because nothing here inspects the data file
at all; it only inspects the schema document itself.

Entry point:
    run(repo_root) -> list[str]   # empty list == all checks passed
"""
import json
import os

# Path of the schema, relative to the monorepo root. The plugin lives at
# <repo_root>/plugins/cds; the schema is read LIVE on every run.
SCHEMA_RELPATH = os.path.join(
    "plugins", "cds", "validation", "customizable-design-elements.schema.json"
)


def run(repo_root):
    failures = []

    schema_path = os.path.join(repo_root, SCHEMA_RELPATH)

    # --- Load the schema file LIVE ------------------------------------------
    if not os.path.isfile(schema_path):
        return [f"SCHEMA missing: expected schema at {schema_path}"]

    try:
        with open(schema_path) as f:
            schema = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [f"SCHEMA unreadable: {schema_path}: {e}"]

    if not isinstance(schema, dict):
        return [
            f"SCHEMA malformed: top-level value in {schema_path} is "
            f"{type(schema).__name__}, expected a JSON object"
        ]

    # --- jsonschema must be importable (it is a dependency of the linter) ----
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return ["SCHEMA cannot validate: jsonschema is not importable "
                "(pip install jsonschema)"]

    # --- The schema must itself be a valid JSON Schema -----------------------
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as e:
        # check_schema raises SchemaError; report its message verbatim so the
        # offending keyword/path is visible.
        msg = getattr(e, "message", str(e))
        failures.append(f"SCHEMA metaschema error: {msg}")

    # --- Identity keywords ---------------------------------------------------
    if "$schema" not in schema:
        failures.append("SCHEMA missing $schema: the document does not declare "
                        "its JSON Schema dialect")
    elif not isinstance(schema["$schema"], str) or not schema["$schema"].strip():
        failures.append(f"SCHEMA invalid $schema: expected a non-empty string, "
                        f"got {schema['$schema']!r}")

    if "$id" not in schema:
        failures.append("SCHEMA missing $id: the document does not declare a "
                        "stable identifier")
    elif not isinstance(schema["$id"], str) or not schema["$id"].strip():
        failures.append(f"SCHEMA invalid $id: expected a non-empty string, "
                        f"got {schema['$id']!r}")

    return failures
