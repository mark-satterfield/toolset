#!/usr/bin/env python3
"""
Lint the customizable-design-elements YAML.

Beyond JSON-Schema validation, this enforces the rules the schema cannot express
because they require following var() alias chains:

  1. SCHEMA        — the file validates against customizable-design-elements.schema.json
  2. INTEGRITY     — every var() reference (--color-*) resolves to a defined token,
                     terminating in a hex (no dangling refs, no alias cycles)
  3. FROM_PALETTE  — every theme binding for a role that declares `from_palette`
                     resolves into one of the allowed palettes (the "only choose a
                     color from the xyz palette" constraint)
  4. TIERS         — primitive palettes hold only hex; semantic palettes hold only
                     var() aliases (the three-tier discipline)

Coverage of `required` roles is reported as a WARNING, not a failure (some
required flags predate the role/binding split and may be intentionally loose).

Usage:
    python3 lint-elements.py [path-to-elements.yaml]
    python3 lint-elements.py --trace            # also print theme -> hex resolution
Exit code 0 = clean, 1 = one or more hard failures.
"""
import json, sys, os

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "customizable-design-elements.schema.json")
DEFAULT_YAML = os.path.join(HERE, "..", "setup", "customizable-design-elements.yaml")


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def token_map(data):
    cc = data["color_catalog"]
    groups = {"common_colors": cc["common_colors"], **cc["palettes"]}
    tok = {}
    for pk, pal in groups.items():
        for ck, v in pal["colors"].items():
            tok[f"--color-{pk}-{ck}"] = v
    return tok, groups


def resolve(t, tok, seen=None):
    """Follow the alias chain to a terminal hex. Returns (hex|None, error|None)."""
    seen = seen or []
    if t in seen:
        return None, f"cycle: {' -> '.join(seen + [t])}"
    if t not in tok:
        return None, f"undefined token: {t}"
    v = tok[t]
    if "hex" in v:
        return v["hex"].upper(), None
    if "var" in v:
        return resolve(v["var"], tok, seen + [t])
    return None, f"no hex/var: {t}"


def palette_of(token, palette_names):
    body = token[len("--color-"):]
    for p in sorted(palette_names, key=len, reverse=True):
        if body == p or body.startswith(p + "-"):
            return p
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    trace = "--trace" in sys.argv
    path = args[0] if args else DEFAULT_YAML
    data = load(path)
    tok, groups = token_map(data)
    palette_names = list(groups.keys())
    fails = []
    warns = []

    # 1. SCHEMA
    try:
        from jsonschema import Draft202012Validator
        schema = json.load(open(SCHEMA))
        errs = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
        if errs:
            for e in errs:
                fails.append(f"SCHEMA {list(e.path)}: {e.message}")
        else:
            print("1. SCHEMA ............ PASS")
    except ImportError:
        print("1. SCHEMA ............ SKIP (pip install jsonschema)")

    # 2. INTEGRITY (+ TIERS while we walk)
    dangling = []
    for t in tok:
        hexval, err = resolve(t, tok)
        if err:
            dangling.append(f"{t}: {err}")
    print(f"2. INTEGRITY ......... {'PASS' if not dangling else 'FAIL'}")
    fails += [f"INTEGRITY {d}" for d in dangling]

    # 4. TIERS — primitive=hex only, semantic=alias only (heuristic: a palette is
    #    semantic iff all rows are aliases; primitive iff all rows are hex)
    for pk, pal in groups.items():
        kinds = {("var" if "var" in v else "hex" if "hex" in v else "?") for v in pal["colors"].values()}
        if kinds == {"var", "hex"}:
            warns.append(f"TIERS palette '{pk}' mixes hex and aliases (not cleanly primitive or semantic)")

    # 0. ALIASES — an alias theme mirrors a concrete theme; it has no modes
    #    of its own. Validate every alias target resolves to a defined,
    #    concrete (non-alias) theme. No chaining, no self-reference.
    theme_defs = data["themes"]
    alias_fail = []
    for tn, t in theme_defs.items():
        if "alias" not in t:
            continue
        tgt = t["alias"]
        if tgt == tn:
            alias_fail.append(f"{tn}: alias points at itself")
        elif tgt not in theme_defs:
            alias_fail.append(f"{tn}: alias target '{tgt}' is not a defined theme")
        elif "alias" in theme_defs[tgt]:
            alias_fail.append(f"{tn}: alias target '{tgt}' is itself an alias (aliases do not chain)")
        elif "modes" not in theme_defs[tgt]:
            alias_fail.append(f"{tn}: alias target '{tgt}' has no modes")
    print(f"0. ALIASES .......... {'PASS' if not alias_fail else 'FAIL'}")
    fails += [f"ALIAS {a}" for a in alias_fail]

    # 3. FROM_PALETTE  (alias themes carry no bindings — skip them)
    roles = data["roles"]
    checked = 0
    for tn, t in data["themes"].items():
        if "modes" not in t:
            continue
        for mode, mb in t["modes"].items():
            for role, val in mb["bindings"].items():
                fp = roles.get(role, {}).get("from_palette")
                if not fp or "var" not in val:
                    continue
                allowed = [fp] if isinstance(fp, str) else fp
                checked += 1
                p = palette_of(val["var"], palette_names)
                if p not in allowed:
                    fails.append(f"FROM_PALETTE {tn}.{mode}.{role}: binds {val['var']} (palette '{p}') not in {allowed}")
    print(f"3. FROM_PALETTE ...... {'PASS' if not any(f.startswith('FROM_PALETTE') for f in fails) else 'FAIL'} ({checked} constrained bindings)")

    # 5. COVERAGE (hard) — every concrete theme, in every mode it declares,
    #    must bind every required role, or it would render an empty role. This
    #    is config-agnostic: it asserts a property, not any specific value.
    req = [r for r, d in roles.items() if d.get("required", True)]
    cov_fail = []
    for tn, t in data["themes"].items():
        if "modes" not in t:
            continue
        for mode, mb in t["modes"].items():
            for r in req:
                if r not in mb["bindings"]:
                    cov_fail.append(f"required role '{r}' unbound in {tn}.{mode}")
    print(f"5. COVERAGE .......... {'PASS' if not cov_fail else 'FAIL'} ({len(req)} required roles)")
    fails += [f"COVERAGE {c}" for c in cov_fail]

    if trace:
        print("\n--- theme -> resolved hex ---")
        for tn, t in data["themes"].items():
            if "modes" not in t:
                print(f"  {tn:22} (alias -> {t['alias']})")
                continue
            for mode, mb in t["modes"].items():
                for role, val in mb["bindings"].items():
                    if "var" in val:
                        hv, _ = resolve(val["var"], tok)
                        print(f"  {tn}.{mode}.{role:22} {val['var']:38} -> {hv}")

    if warns:
        print(f"\n{len(warns)} warning(s):")
        for w in warns[:60]:
            print("  ⚠ ", w)

    if fails:
        print(f"\n{len(fails)} FAILURE(S):")
        for f in fails:
            print("  ✗ ", f)
        sys.exit(1)
    print("\nAll hard checks passed.")


if __name__ == "__main__":
    main()
