#!/usr/bin/env python3
"""
check_semantic_hash — the elements fingerprint ignores prose, not meaning.

PROPERTY
    lib/cds_hash.py exists and computes an elements fingerprint that is:
      * INVARIANT to comment-only and description-only edits — a YAML change
        that cannot affect the emitted CSS must NOT change the hash (otherwise
        the composers would needlessly regenerate stylesheets on a prose edit);
      * SENSITIVE to a real value change — an edit that DOES affect the CSS must
        change the hash (otherwise a stale set would never be detected).

Config-agnostic: it builds tiny synthetic YAML documents at runtime and asserts
the invariance/sensitivity relations between their hashes. No fixed hash value,
palette name, role name, or count is hardcoded. If the shared hasher is absent,
that is itself the failure (Phase 0 must ship it).

Entry point:
    run(repo_root) -> list[str]   # empty list == passed
"""
import importlib.util
import os
import tempfile

LIB_SUBPATH = os.path.join("plugins", "cds", "lib", "cds_hash.py")

_BASE = (
    "$schema_version: 1\n"
    "color_catalog:\n"
    "  common_colors:\n"
    "    colors:\n"
    "      ink: { hex: '#111111' }\n"
    "  palettes:\n"
    "    brand:\n"
    "      description: Brand colors.\n"
    "      colors:\n"
    "        a: { hex: '#abcdef' }\n"
    "roles:\n"
    "  surface-primary:\n"
    "    type: semantic\n"
    "    description: Primary page ground.\n"
)

# Same meaning, different prose: an added comment line and reworded descriptions.
_PROSE_ONLY = (
    "$schema_version: 1\n"
    "# a comment that means nothing to the emitted CSS\n"
    "color_catalog:\n"
    "  common_colors:\n"
    "    colors:\n"
    "      ink: { hex: '#111111' }\n"
    "  palettes:\n"
    "    brand:\n"
    "      description: A totally different sentence here.\n"
    "      colors:\n"
    "        a: { hex: '#abcdef' }\n"
    "roles:\n"
    "  surface-primary:\n"
    "    type: semantic\n"
    "    description: Reworded with no semantic change at all.\n"
)

# Real change: one hex value differs.
_VALUE_CHANGE = _BASE.replace("#abcdef", "#abcdee")


def _load(lib_path):
    spec = importlib.util.spec_from_file_location("cds_hash", lib_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hash_text(mod, text):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return mod.semantic_hash(path)
    finally:
        os.unlink(path)


def run(repo_root):
    lib_path = os.path.join(repo_root, LIB_SUBPATH)
    if not os.path.isfile(lib_path):
        return [f"SEMANTIC-HASH: missing shared hasher at {LIB_SUBPATH}"]

    try:
        mod = _load(lib_path)
    except Exception as e:  # noqa: BLE001 - any import failure is a real defect
        return [f"SEMANTIC-HASH: lib/cds_hash.py failed to import: {e}"]

    if not hasattr(mod, "semantic_hash"):
        return ["SEMANTIC-HASH: lib/cds_hash.py has no semantic_hash() function"]

    fails = []
    try:
        h_base = _hash_text(mod, _BASE)
        h_prose = _hash_text(mod, _PROSE_ONLY)
        h_value = _hash_text(mod, _VALUE_CHANGE)
    except Exception as e:  # noqa: BLE001
        return [f"SEMANTIC-HASH: semantic_hash() raised: {e}"]

    if h_base != h_prose:
        fails.append(
            "SEMANTIC-HASH: a comment/description-only edit changed the hash "
            f"({h_base[:12]} != {h_prose[:12]}); such an edit must NOT trigger "
            "a stylesheet regeneration"
        )
    if h_base == h_value:
        fails.append(
            "SEMANTIC-HASH: a hex-value edit did NOT change the hash; a real "
            "value change must trigger a regeneration"
        )
    return fails


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    out = run(root)
    print("PASS" if not out else "FAIL")
    for f in out:
        print("  -", f)
