#!/usr/bin/env python3
"""
check_reference — Reference-tree integrity for the CDS plugin.

Asserts PROPERTIES of the live reference tree against the live elements YAML.
No theme names, swatch values, or counts are hardcoded: a different valid
configuration must still pass. Every file is read fresh on each run.

Checks (all config-agnostic):

  1. SHAPE-HEADERS  — every shape named in the Part A catalog of reference/shapes.md owns a
                      Slots bullet, a Layout bullet, and an Allowed-variants bullet.
  2. COMPONENTS     — reference/components.md enumerates at least one component
                      family header (the family list is enumerable, not empty).
  3. ROLE-TOKENS    — every `--role-<key>` referenced as a role binding in the
                      reference tree names a role defined in the elements YAML
                      roles map. (Template emit-pattern declarations of the form
                      `--role-<x>: var(...)` are placeholders, not references.)
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

# A role token reference: --role-<key> where <key> is lowercase-kebab.
_ROLE_TOKEN_RE = re.compile(r"--role-([a-z0-9][a-z0-9-]*)")
# A shape name token (semantic, lowercase-kebab) as it appears in the Part A catalog
# first column and in each shape's section header "## <name> — ...".
_SHAPE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]+$")
# Component family headers: "## <something>" excluding the catalog preamble row.
_COMPONENT_HDR_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
# A scope tag: "[scope: <value>]".
_SCOPE_TAG_RE = re.compile(r"\[scope:\s*([^\]]+?)\s*\]")


def _section_body(text, start_match, all_starts, idx):
    """Return the body of a section from one `##` header to the next."""
    start = start_match.end()
    end = all_starts[idx + 1].start() if idx + 1 < len(all_starts) else len(text)
    return text[start:end]


def _shape_catalog_names(text):
    """Names from the Part A catalog (first column of each table row)."""
    names = []
    in_part_a = False
    for line in text.splitlines():
        if line.strip().startswith("## Part A"):
            in_part_a = True
            continue
        if in_part_a:
            if line.startswith("## ") and "Part A" not in line:
                break
            if line.startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if cells and _SHAPE_NAME_RE.match(cells[0]):
                    names.append(cells[0])
    return names


def _check_shapes(repo_root, fails):
    path = _ref(repo_root, "shapes.md")
    if not os.path.isfile(path):
        fails.append(f"SHAPE-HEADERS: reference/shapes.md not found at {path}")
        return
    text = _read(path)
    catalog = _shape_catalog_names(text)
    if not catalog:
        fails.append(
            "SHAPE-HEADERS: no shape names found in the Part A catalog of reference/shapes.md"
        )
        return
    catalog_set = set(catalog)
    # Every H2 whose first word is a catalog name is that shape's section header.
    all_h2 = list(_COMPONENT_HDR_RE.finditer(text))
    shape_sections = []
    for i, m in enumerate(all_h2):
        words = m.group(1).split()
        first = words[0] if words else ""
        if first in catalog_set:
            shape_sections.append((first, m, i))
    documented = {name for name, _, _ in shape_sections}
    for name in sorted(catalog_set - documented):
        fails.append(f"SHAPE-HEADERS: catalog shape '{name}' has no '## {name} — ...' section")
    # Each shape section must carry the three definitional bullets. Match the bold
    # bullet labels case-insensitively; tolerate "Allowed variants" / "Allowed-variants".
    for name, m, i in shape_sections:
        body = _section_body(text, m, all_h2, i)
        if not re.search(r"^\s*[-*]\s+\*\*Slots:?\*\*", body, re.MULTILINE | re.IGNORECASE):
            fails.append(f"SHAPE-HEADERS: {name} is missing a **Slots** bullet")
        if not re.search(r"^\s*[-*]\s+\*\*Layout:?\*\*", body, re.MULTILINE | re.IGNORECASE):
            fails.append(f"SHAPE-HEADERS: {name} is missing a **Layout** bullet")
        if not re.search(
            r"^\s*[-*]\s+\*\*Allowed[ -]variants:?\*\*", body, re.MULTILINE | re.IGNORECASE
        ):
            fails.append(
                f"SHAPE-HEADERS: {name} is missing an **Allowed variants** bullet"
            )


def _check_components(repo_root, fails):
    path = _ref(repo_root, "components.md")
    if not os.path.isfile(path):
        fails.append(f"COMPONENTS: reference/components.md not found at {path}")
        return
    text = _read(path)
    headers = [m.group(1).strip() for m in _COMPONENT_HDR_RE.finditer(text)]
    # A component family is any "## " header that names a family. The file always
    # carries at least the §14 component catalog plus per-family headers; assert
    # the family list is enumerable (non-empty) — the property, not a count.
    families = [h for h in headers if h]
    if not families:
        fails.append(
            "COMPONENTS: reference/components.md has no enumerable component "
            "family headers (## ...)"
        )


def _collect_referenced_roles(repo_root):
    """
    Gather every --role-<key> that is REFERENCED (not template-defined) across
    the reference tree, with the file it came from.

    A token is a template-definition placeholder (not a reference) when it
    appears as the left side of a CSS custom-property assignment in an emit
    pattern: `--role-<key>: var(...)`. Those are documentation of the emit
    shape, not bindings to a concrete role.
    """
    ref_dir = _ref(repo_root)
    referenced = {}  # key -> set(relative file paths)
    for dirpath, _dirs, files in os.walk(ref_dir):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, _plugin_root(repo_root))
            text = _read(full)
            for m in _ROLE_TOKEN_RE.finditer(text):
                key = m.group(1)
                tail = text[m.end():]
                # Template emit-pattern: `--role-<key>: var(...)` — placeholder.
                if re.match(r"\s*:\s*var\(", tail):
                    continue
                referenced.setdefault(key, set()).add(rel)
    return referenced


def _check_role_tokens(repo_root, data, fails):
    if data is None:
        return
    roles = data.get("roles")
    if not isinstance(roles, dict):
        fails.append("ROLE-TOKENS: elements YAML has no `roles` map")
        return
    defined = set(roles.keys())
    referenced = _collect_referenced_roles(repo_root)
    for key in sorted(referenced):
        if key not in defined:
            where = ", ".join(sorted(referenced[key]))
            fails.append(
                f"ROLE-TOKENS: --role-{key} is referenced ({where}) but names no "
                f"role in the elements YAML roles map"
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
    _check_role_tokens(repo_root, data, fails)
    _check_from_palette(repo_root, data, fails)
    _check_scope_tags(repo_root, fails)

    return fails
