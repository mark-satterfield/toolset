#!/usr/bin/env python3
"""
check_reference — Reference-tree integrity for the CDS plugin.

Asserts PROPERTIES of the live reference tree against the live elements YAML.
No theme names, swatch values, or counts are hardcoded: a different valid
configuration must still pass. Every file is read fresh on each run.

Checks (all config-agnostic):

  1. SHAPE-HEADERS  — every entry in reference/libraries/shapes/ is a well-formed
                      Shape: typed frontmatter whose `kind` is `shape`, whose
                      `name` matches its filename, carrying the `slots` and
                      `variants` contract keys, above a body title.
  2. COMPONENTS     — every entry in reference/libraries/components/ is a
                      well-formed Component: `kind: component`, `name` matching
                      its filename, carrying the `token_bindings` contract.
  3. ROLE-PREFIX    — no `--role-` token survives in the reference tree or the
                      generated stylesheet set. Roles are emitted BARE
                      (`--surface-primary`) per $conventions.role_var_pattern
                      `--{role key}`; a `--role-` prefix is a regression of the
                      bare-role reconcile. (Bare role tokens are resolution-
                      checked by check_token_coverage on the generated CSS.)
  4. FROM_PALETTE   — every `from_palette` value declared on a role in the YAML
                      names a palette present in color_catalog.palettes.
  5. SCOPE-TAGS     — every `[scope: ...]` tag in reference/compliance.md is one
                      of both | standalone | app-embedded.

Entry point:
    run(repo_root) -> list[str]   ([] means all checks passed)
"""
import os
import re

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a declared dependency
    yaml = None


# --- locations (relative to the plugin under <repo_root>/plugins/cds) ----------

def _plugin_root(repo_root):
    return os.path.join(repo_root, "plugins", "cds")


def _elements_path(repo_root):
    """Default elements YAML, honoring $CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS."""
    override = os.environ.get("CUSTOMIZABLE_DESIGN_SYSTEM_ELEMENTS")
    if override:
        return override
    return os.path.join(
        _plugin_root(repo_root), "setup", "customizable-design-elements.yaml"
    )


def _ref(repo_root, *parts):
    return os.path.join(_plugin_root(repo_root), "reference", *parts)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# --- valid scope tokens are a closed set defined by the compliance contract ----
_VALID_SCOPES = {"both", "standalone", "app-embedded"}

# A forbidden role-token prefix. Roles are emitted bare; any `--role-` is a
# regression of the bare-role reconcile (#4).
_ROLE_PREFIX_RE = re.compile(r"--role-")
# A scope tag: "[scope: <value>]".
_SCOPE_TAG_RE = re.compile(r"\[scope:\s*([^\]]+?)\s*\]")

# Non-entry files that live in the library dirs.
_NON_ENTRIES = {"FORMAT.md", "CONVENTIONS.md"}


def _frontmatter(text):
    """Parse a leading `---` YAML frontmatter block into a dict, or None."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    try:
        data = yaml.safe_load(text[3:end])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _library_entries(repo_root, *subparts):
    """Absolute paths of every `.md` entry in a library dir (excluding the
    FORMAT/CONVENTIONS meta files)."""
    d = _ref(repo_root, "libraries", *subparts)
    if not os.path.isdir(d):
        return None
    return [
        os.path.join(d, fn)
        for fn in sorted(os.listdir(d))
        if fn.endswith(".md") and fn not in _NON_ENTRIES
    ]


def _check_shapes(repo_root, fails):
    entries = _library_entries(repo_root, "shapes")
    if entries is None:
        fails.append(
            "SHAPE-HEADERS: reference/libraries/shapes/ directory not found"
        )
        return
    if not entries:
        fails.append("SHAPE-HEADERS: reference/libraries/shapes/ has no entries")
        return
    for path in entries:
        base = os.path.basename(path)[:-len(".md")]
        fm = _frontmatter(_read(path))
        if fm is None:
            fails.append(f"SHAPE-HEADERS: {base} has no YAML frontmatter block")
            continue
        if fm.get("kind") != "shape":
            fails.append(
                f"SHAPE-HEADERS: {base} declares kind '{fm.get('kind')}', "
                f"expected 'shape'"
            )
        if fm.get("name") != base:
            fails.append(
                f"SHAPE-HEADERS: {base} frontmatter name '{fm.get('name')}' "
                f"does not match its filename"
            )
        for key in ("slots", "variants"):
            if key not in fm:
                fails.append(
                    f"SHAPE-HEADERS: {base} is missing the '{key}' contract key"
                )


def _check_components(repo_root, fails):
    entries = _library_entries(repo_root, "components")
    if entries is None:
        fails.append(
            "COMPONENTS: reference/libraries/components/ directory not found"
        )
        return
    if not entries:
        fails.append("COMPONENTS: reference/libraries/components/ has no entries")
        return
    for path in entries:
        base = os.path.basename(path)[:-len(".md")]
        fm = _frontmatter(_read(path))
        if fm is None:
            fails.append(f"COMPONENTS: {base} has no YAML frontmatter block")
            continue
        if fm.get("kind") != "component":
            fails.append(
                f"COMPONENTS: {base} declares kind '{fm.get('kind')}', "
                f"expected 'component'"
            )
        if fm.get("name") != base:
            fails.append(
                f"COMPONENTS: {base} frontmatter name '{fm.get('name')}' "
                f"does not match its filename"
            )
        if "token_bindings" not in fm:
            fails.append(
                f"COMPONENTS: {base} is missing the 'token_bindings' contract key"
            )


def _check_role_prefix(repo_root, fails):
    """Fail if any `--role-` token survives in the reference tree or the
    generated stylesheet set. Roles are emitted bare (`--<key>`); a surviving
    prefix is a regression of the bare-role reconcile (#4). Resolution of the
    bare tokens themselves is enforced by check_token_coverage on the CSS."""
    ref_dir = _ref(repo_root)
    targets = []
    for dirpath, _dirs, files in os.walk(ref_dir):
        for fn in files:
            if fn.endswith(".md"):
                targets.append(os.path.join(dirpath, fn))
    styles = os.path.join(
        _plugin_root(repo_root), "test", "visual-proof-out", "styles"
    )
    if os.path.isdir(styles):
        for fn in os.listdir(styles):
            if fn.endswith(".css"):
                targets.append(os.path.join(styles, fn))
    for full in sorted(targets):
        text = _read(full)
        if _ROLE_PREFIX_RE.search(text):
            rel = os.path.relpath(full, _plugin_root(repo_root))
            n = len(_ROLE_PREFIX_RE.findall(text))
            fails.append(
                f"ROLE-PREFIX: {rel} contains {n} `--role-` token(s); roles are "
                f"emitted bare (--<key>) per $conventions.role_var_pattern "
                f'"--{{role key}}"'
            )


def _check_from_palette(repo_root, data, fails):
    if data is None:
        return
    roles = data.get("roles")
    cc = data.get("color_catalog") or {}
    palettes = cc.get("palettes") or {}
    if not isinstance(roles, dict):
        fails.append("FROM_PALETTE: elements YAML has no `roles` map")
        return
    if not isinstance(palettes, dict):
        fails.append("FROM_PALETTE: color_catalog.palettes is missing or not a map")
        return
    palette_names = set(palettes.keys())
    for role_key, role in roles.items():
        if not isinstance(role, dict) or "from_palette" not in role:
            continue
        fp = role["from_palette"]
        wanted = [fp] if isinstance(fp, str) else list(fp)
        for p in wanted:
            if p not in palette_names:
                fails.append(
                    f"FROM_PALETTE: role '{role_key}' declares from_palette "
                    f"'{p}', which is not a palette in color_catalog.palettes"
                )


def _check_scope_tags(repo_root, fails):
    path = _ref(repo_root, "compliance.md")
    if not os.path.isfile(path):
        fails.append(f"SCOPE-TAGS: reference/compliance.md not found at {path}")
        return
    text = _read(path)
    tags = _SCOPE_TAG_RE.findall(text)
    if not tags:
        fails.append("SCOPE-TAGS: no [scope: ...] tags found in reference/compliance.md")
        return
    for raw in tags:
        val = raw.strip()
        if val not in _VALID_SCOPES:
            fails.append(
                f"SCOPE-TAGS: [scope: {val}] is not one of "
                f"{sorted(_VALID_SCOPES)}"
            )


def run(repo_root):
    """Run reference-tree integrity checks. Returns a list of failure strings."""
    fails = []

    if yaml is None:
        return ["check_reference: PyYAML is required but not importable"]

    elements_path = _elements_path(repo_root)
    data = None
    if not os.path.isfile(elements_path):
        fails.append(f"elements YAML not found at {elements_path}")
    else:
        try:
            with open(elements_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:  # surface a parse error as a single failure
            fails.append(f"elements YAML failed to parse ({elements_path}): {exc}")
            data = None

    _check_shapes(repo_root, fails)
    _check_components(repo_root, fails)
    _check_role_prefix(repo_root, fails)
    _check_from_palette(repo_root, data, fails)
    _check_scope_tags(repo_root, fails)

    return fails
