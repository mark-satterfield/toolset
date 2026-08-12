#!/usr/bin/env python3
"""
check-values-parity — verify value preservation across an elements-YAML migration.

Compares two customizable-design-elements YAMLs (OLD, NEW) and asserts that every
value expressible in OLD survives in NEW with an equal resolved value:

  * every primitive hex in the color catalog (common_colors + palettes);
  * every semantic-palette alias target, resolved through its var() chain to a
    terminal hex;
  * every role key;
  * every theme binding (theme -> mode -> role), resolved through the var() alias
    chain to a terminal hex;
  * every geometry scalar value.

Three classes of difference are SANCTIONED (schema 1.x -> 2.0, per
analysis/schema-2-migration-notes.md) and reported as "sanctioned correction"
rather than a loss:

  1. `dark: mirror` expansion — a dark mode written as the literal string
     `mirror` expands to the theme's own light bindings.
  2. containers -> elements move — `conversion-card` changes geometry group
     (`--container-conversion-card` -> `--element-conversion-card`); its value is
     unchanged.
  3. the documented contrast rebindings — tile inks in the light modes of the
     themes the migration notes §3 table lists, near-black ink -> ivory. The
     table is read at run time; whatever rows it carries are the sanctioned set.

Exit 0 if every OLD value is preserved (sanctioned corrections allowed); exit 1
on any unsanctioned loss or value change. stdlib + PyYAML only; errors surface.

Usage:
    python3 tools/check-values-parity.py OLD.yaml NEW.yaml
    python3 tools/check-values-parity.py OLD.yaml NEW.yaml --notes path/to/notes.md
"""
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "check-values-parity: PyYAML is required (pip install pyyaml)\n"
    )
    sys.exit(2)


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_NOTES = os.path.join(
    HERE, "..", "analysis", "schema-2-migration-notes.md"
)
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")


# --- loading & resolution (mirrors validation/lint-elements.py semantics) ------

def load(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def token_map(data):
    """Every color-catalog node, keyed by its emitted `--color-{group}-{key}`."""
    cc = data["color_catalog"]
    groups = {"common_colors": cc["common_colors"], **cc["palettes"]}
    tok = {}
    for pk, pal in groups.items():
        for ck, v in pal.get("colors", {}).items():
            tok[f"--color-{pk}-{ck}"] = v
    return tok


def resolve(token, tok, seen=None):
    """Follow the alias chain to a terminal hex. Returns (hex|None, error|None)."""
    seen = seen or []
    if token in seen:
        return None, f"cycle: {' -> '.join(seen + [token])}"
    if token not in tok:
        return None, f"undefined token: {token}"
    v = tok[token]
    if not isinstance(v, dict):
        return None, f"malformed color node: {token}"
    if "hex" in v:
        return v["hex"].upper(), None
    if "var" in v:
        return resolve(v["var"], tok, seen + [token])
    return None, f"no hex/var: {token}"


# --- theme binding enumeration (mirror expansion, alias skipping) --------------

def theme_bindings(data):
    """Yield ((theme, mode, role) -> var-token) for every concrete binding.

    `dark: mirror` expands to the theme's own light bindings. A theme that is a
    pure `alias` of another declares no values of its own and is skipped — its
    resolved values are the target theme's, compared under that theme.
    """
    out = {}
    themes = data.get("themes", {}) or {}
    for tname, tdef in themes.items():
        if not isinstance(tdef, dict):
            continue
        if "alias" in tdef and "modes" not in tdef:
            continue  # pure alias — no values of its own
        modes = tdef.get("modes", {}) or {}
        # First materialize each mode's bindings map, expanding `mirror`.
        materialized = {}
        for mname, mdef in modes.items():
            if mdef == "mirror":
                continue  # resolved after the light block is known
            if isinstance(mdef, dict):
                materialized[mname] = mdef.get("bindings", {}) or {}
        for mname, mdef in modes.items():
            if mdef == "mirror":
                materialized[mname] = dict(materialized.get("light", {}))
        for mname, bindings in materialized.items():
            for role, val in bindings.items():
                if isinstance(val, dict) and "var" in val:
                    out[(tname, mname, role)] = val["var"]
    return out


# --- geometry enumeration ------------------------------------------------------

def geometry_values(data):
    """(group, key) -> value string for every geometry scalar."""
    out = {}
    geo = data.get("geometry", {}) or {}
    for group, entries in geo.items():
        if not isinstance(entries, dict):
            continue
        for key, node in entries.items():
            if isinstance(node, dict) and "value" in node:
                out[(group, key)] = node["value"]
    return out


# --- sanctioned contrast rebindings (read from the migration notes §3 table) ---

def load_sanctioned_rebindings(notes_path):
    """Parse the §3 contrast-rebinding table into a lookup:

        (theme, mode, role) -> (old_hex_upper, new_hex_upper)

    The table columns are: Theme | Mode | Role | Ground | Old ink | New ink.
    Whatever rows the notes carry are the sanctioned set — nothing is hardcoded.
    """
    if not os.path.isfile(notes_path):
        raise FileNotFoundError(
            f"migration notes not found at {notes_path}; pass --notes <path>"
        )
    with open(notes_path, encoding="utf-8") as f:
        text = f.read()
    sanctioned = {}
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 6:
            continue
        theme, mode, role, _ground, old_cell, new_cell = cells[:6]
        # Skip the header row and its separator.
        if theme.lower() == "theme" or set(theme) <= set("-: "):
            continue
        old_hex = _HEX_RE.search(old_cell)
        new_hex = _HEX_RE.search(new_cell)
        if not (old_hex and new_hex):
            continue
        sanctioned[(theme, mode, role)] = (
            old_hex.group(0).upper(),
            new_hex.group(0).upper(),
        )
    return sanctioned


# --- comparison ----------------------------------------------------------------

def compare(old, new, sanctioned):
    """Return (failures, sanctioned_notes) — both lists of strings."""
    failures = []
    notes = []

    old_tok = token_map(old)
    new_tok = token_map(new)

    # 1. Color catalog: every OLD color node resolves equally in NEW.
    for token, node in sorted(old_tok.items()):
        kind = "primitive hex" if (isinstance(node, dict) and "hex" in node) \
            else "semantic alias"
        old_hex, old_err = resolve(token, old_tok)
        if old_err:
            failures.append(f"[color-catalog] OLD {token} unresolvable: {old_err}")
            continue
        if token not in new_tok:
            failures.append(
                f"[color-catalog] {kind} {token} ({old_hex}) is absent from NEW"
            )
            continue
        new_hex, new_err = resolve(token, new_tok)
        if new_err:
            failures.append(f"[color-catalog] NEW {token} unresolvable: {new_err}")
            continue
        if old_hex != new_hex:
            failures.append(
                f"[color-catalog] {kind} {token}: OLD {old_hex} != NEW {new_hex}"
            )

    # 2. Roles: every OLD role key exists in NEW.
    old_roles = set((old.get("roles") or {}).keys())
    new_roles = set((new.get("roles") or {}).keys())
    for role in sorted(old_roles - new_roles):
        failures.append(f"[roles] role '{role}' present in OLD, absent from NEW")

    # 3. Theme bindings: every OLD (theme, mode, role) resolves equally in NEW,
    #    unless the difference is a sanctioned contrast rebinding.
    old_bindings = theme_bindings(old)
    new_bindings = theme_bindings(new)
    for key, old_var in sorted(old_bindings.items()):
        theme, mode, role = key
        old_hex, old_err = resolve(old_var, old_tok)
        if old_err:
            failures.append(
                f"[theme] OLD {theme}.{mode}.{role} {old_var} unresolvable: "
                f"{old_err}"
            )
            continue
        if key not in new_bindings:
            failures.append(
                f"[theme] binding {theme}.{mode}.{role} ({old_hex}) is absent "
                f"from NEW"
            )
            continue
        new_hex, new_err = resolve(new_bindings[key], new_tok)
        if new_err:
            failures.append(
                f"[theme] NEW {theme}.{mode}.{role} {new_bindings[key]} "
                f"unresolvable: {new_err}"
            )
            continue
        if old_hex == new_hex:
            continue
        sanc = sanctioned.get(key)
        if sanc and sanc[0] == old_hex and sanc[1] == new_hex:
            notes.append(
                f"sanctioned correction: {theme}.{mode}.{role} "
                f"{old_hex} -> {new_hex} (contrast rebinding, notes §3)"
            )
        else:
            failures.append(
                f"[theme] {theme}.{mode}.{role}: OLD {old_hex} != NEW {new_hex}"
                + (
                    f" (a rebinding is sanctioned for this role but the hexes "
                    f"do not match the notes: expected {sanc[0]} -> {sanc[1]})"
                    if sanc else ""
                )
            )

    # 4. Geometry: every OLD scalar value survives in NEW, allowing the
    #    conversion-card containers -> elements move.
    old_geo = geometry_values(old)
    new_geo = geometry_values(new)
    for (group, key), old_val in sorted(old_geo.items()):
        if (group, key) in new_geo:
            if new_geo[(group, key)] != old_val:
                failures.append(
                    f"[geometry] {group}.{key}: OLD {old_val} != "
                    f"NEW {new_geo[(group, key)]}"
                )
            continue
        # Not found under the same group — look for a sanctioned move to another
        # group under the same key, with the value preserved.
        moved_to = [
            g for (g, k), v in new_geo.items()
            if k == key and v == old_val and g != group
        ]
        if group == "containers" and "elements" in moved_to:
            notes.append(
                f"sanctioned move: geometry.{group}.{key} -> "
                f"geometry.elements.{key} (value {old_val} preserved)"
            )
        elif moved_to:
            notes.append(
                f"sanctioned move: geometry.{group}.{key} -> "
                f"geometry.{moved_to[0]}.{key} (value {old_val} preserved)"
            )
        else:
            failures.append(
                f"[geometry] {group}.{key} ({old_val}) is absent from NEW"
            )

    return failures, notes


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    notes_path = DEFAULT_NOTES
    if "--notes" in sys.argv:
        i = sys.argv.index("--notes")
        if i + 1 >= len(sys.argv):
            sys.stderr.write("check-values-parity: --notes needs a path\n")
            sys.exit(2)
        notes_path = sys.argv[i + 1]
        args = [a for a in args if a != notes_path]
    if len(args) != 2:
        sys.stderr.write(
            "usage: check-values-parity.py OLD.yaml NEW.yaml [--notes NOTES.md]\n"
        )
        sys.exit(2)
    old_path, new_path = args

    old = load(old_path)
    new = load(new_path)
    sanctioned = load_sanctioned_rebindings(os.path.abspath(notes_path))

    failures, notes = compare(old, new, sanctioned)

    print(f"OLD: {old_path}")
    print(f"NEW: {new_path}")
    print(f"sanctioned contrast rebindings loaded: {len(sanctioned)}")
    print()

    if notes:
        print(f"{len(notes)} sanctioned correction(s):")
        for n in notes:
            print("  ~ ", n)
        print()

    if failures:
        print(f"{len(failures)} UNSANCTIONED VALUE LOSS(ES):")
        for fmsg in failures:
            print("  ✗  ", fmsg)
        sys.exit(1)

    print("PASS — every OLD value is preserved in NEW "
          "(sanctioned corrections above are expected).")


if __name__ == "__main__":
    main()
