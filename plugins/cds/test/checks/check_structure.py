#!/usr/bin/env python3
"""
check_structure — plugin structure + manifest integrity.

Asserts the structural contract of the CDS plugin, independent of any specific
design configuration. Everything is read LIVE from the working tree on each run;
no theme names, palette keys, role names, command names, skill names, counts, or
swatch values are hardcoded. A different but valid plugin layout (different
commands, skills, agents) must still pass — only the PROPERTIES below are
asserted.

Properties asserted:

  1. MANIFEST   — plugins/cds/.claude-plugin/plugin.json is valid JSON and
                  carries non-empty name, version, and description fields.
  2. EXTENDED   — if plugins/cds/plugin.json exists, it must be non-empty,
                  valid JSON. (Its absence is allowed; only a present-but-broken
                  file is a violation.)
  3. COMMANDS   — every commands/*.md has well-formed YAML frontmatter with a
                  non-empty `description`.
  4. SKILLS     — every skills/*/SKILL.md has well-formed YAML frontmatter with a
                  non-empty `description` and a `name` matching its directory.
  5. SKILL REFS — every "skills/<x>/SKILL.md" path mentioned in a command body
                  points to a file that exists.
  6. AGENT REFS — every skill named in an agent's `skills:` frontmatter (or in
                  an agent body's "skills/<x>/SKILL.md" reference) resolves to a
                  skill directory that exists.
  7. MARKETPLACE — the repo-root .claude-plugin/marketplace.json lists a plugin
                  entry whose source resolves to plugins/cds.

Entry point:
    run(repo_root) -> list[str]   # empty list == all checks passed
"""
import json
import os
import re
import glob

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a linter dependency
    yaml = None


# Paths relative to the monorepo root. The plugin lives at <repo_root>/plugins/cds.
PLUGIN_RELDIR = os.path.join("plugins", "cds")
CORE_MANIFEST_REL = os.path.join(PLUGIN_RELDIR, ".claude-plugin", "plugin.json")
EXTENDED_MANIFEST_REL = os.path.join(PLUGIN_RELDIR, "plugin.json")
MARKETPLACE_REL = os.path.join(".claude-plugin", "marketplace.json")

# Matches references like  skills/compose-page/SKILL.md  embedded in prose.
SKILL_REF_RE = re.compile(r"skills/([A-Za-z0-9_.-]+)/SKILL\.md")


def _split_frontmatter(text):
    """
    Return (frontmatter_dict_or_None, error_or_None) for a Markdown file whose
    content is `text`. A well-formed file starts with a line that is exactly
    '---', followed by YAML, terminated by another '---' line.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "missing opening '---' frontmatter delimiter"
    closing = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing = i
            break
    if closing is None:
        return None, "missing closing '---' frontmatter delimiter"
    block = "\n".join(lines[1:closing])
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as e:
        return None, f"YAML frontmatter does not parse: {e}"
    if data is None:
        return None, "frontmatter block is empty"
    if not isinstance(data, dict):
        return None, f"frontmatter is {type(data).__name__}, expected a mapping"
    return data, None


def _nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def _agent_skill_names(fm):
    """
    Normalize an agent's `skills:` frontmatter value into a list of skill names.
    Accepts a YAML list, or a comma/space-separated string (the live agents use
    'apply-design-system, audit-against-system').
    """
    val = fm.get("skills")
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        return [p.strip() for p in re.split(r"[,\s]+", val) if p.strip()]
    return []


def run(repo_root):
    failures = []

    if yaml is None:
        return ["STRUCTURE cannot validate: PyYAML is not importable "
                "(pip install pyyaml)"]

    plugin_dir = os.path.join(repo_root, PLUGIN_RELDIR)
    if not os.path.isdir(plugin_dir):
        return [f"STRUCTURE missing: plugin directory not found at {plugin_dir}"]

    # --- 1. Core manifest ----------------------------------------------------
    core_path = os.path.join(repo_root, CORE_MANIFEST_REL)
    if not os.path.isfile(core_path):
        failures.append(f"MANIFEST missing: expected {core_path}")
    else:
        try:
            with open(core_path) as f:
                manifest = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            manifest = None
            failures.append(f"MANIFEST unreadable: {core_path}: {e}")
        if isinstance(manifest, dict):
            for field in ("name", "version", "description"):
                if field not in manifest:
                    failures.append(
                        f"MANIFEST missing field '{field}' in {CORE_MANIFEST_REL}")
                elif not _nonempty_str(manifest[field]):
                    failures.append(
                        f"MANIFEST field '{field}' is empty/non-string in "
                        f"{CORE_MANIFEST_REL}: {manifest[field]!r}")
        elif manifest is not None:
            failures.append(
                f"MANIFEST malformed: top-level value in {CORE_MANIFEST_REL} is "
                f"{type(manifest).__name__}, expected a JSON object")

    # --- 2. Extended manifest (only a violation if present but broken) -------
    ext_path = os.path.join(repo_root, EXTENDED_MANIFEST_REL)
    if os.path.isfile(ext_path):
        try:
            with open(ext_path) as f:
                raw = f.read()
        except OSError as e:
            raw = None
            failures.append(f"EXTENDED unreadable: {ext_path}: {e}")
        if raw is not None:
            if raw.strip() == "":
                failures.append(
                    f"EXTENDED empty: {EXTENDED_MANIFEST_REL} exists but is empty")
            else:
                try:
                    json.loads(raw)
                except json.JSONDecodeError as e:
                    failures.append(
                        f"EXTENDED invalid JSON: {EXTENDED_MANIFEST_REL}: {e}")

    # --- 3. Command frontmatter ---------------------------------------------
    commands_dir = os.path.join(plugin_dir, "commands")
    command_files = sorted(glob.glob(os.path.join(commands_dir, "*.md")))
    if not command_files:
        failures.append(
            f"COMMANDS none found: no *.md files under {commands_dir}")
    for cf in command_files:
        rel = os.path.relpath(cf, repo_root)
        try:
            with open(cf) as f:
                text = f.read()
        except OSError as e:
            failures.append(f"COMMAND unreadable: {rel}: {e}")
            continue
        fm, err = _split_frontmatter(text)
        if err:
            failures.append(f"COMMAND {rel}: {err}")
            continue
        if not _nonempty_str(fm.get("description")):
            failures.append(
                f"COMMAND {rel}: missing/empty required 'description' field")

    # --- 4. Skill frontmatter (name must match its directory) ----------------
    skills_dir = os.path.join(plugin_dir, "skills")
    skill_dirs = sorted(
        d for d in glob.glob(os.path.join(skills_dir, "*"))
        if os.path.isdir(d)
    )
    existing_skill_names = set()
    for sd in skill_dirs:
        dirname = os.path.basename(sd)
        skill_md = os.path.join(sd, "SKILL.md")
        rel = os.path.relpath(skill_md, repo_root)
        if not os.path.isfile(skill_md):
            failures.append(
                f"SKILL missing: directory {os.path.relpath(sd, repo_root)} has "
                f"no SKILL.md")
            continue
        # Record the directory as an existing skill regardless of frontmatter
        # health, so agent/command references resolve by directory presence.
        existing_skill_names.add(dirname)
        try:
            with open(skill_md) as f:
                text = f.read()
        except OSError as e:
            failures.append(f"SKILL unreadable: {rel}: {e}")
            continue
        fm, err = _split_frontmatter(text)
        if err:
            failures.append(f"SKILL {rel}: {err}")
            continue
        if not _nonempty_str(fm.get("description")):
            failures.append(
                f"SKILL {rel}: missing/empty required 'description' field")
        name = fm.get("name")
        if not _nonempty_str(name):
            failures.append(
                f"SKILL {rel}: missing/empty required 'name' field")
        elif name.strip() != dirname:
            failures.append(
                f"SKILL {rel}: frontmatter name '{name}' does not match its "
                f"directory '{dirname}'")

    # --- 5. Command bodies referencing skills/<x>/SKILL.md -------------------
    for cf in command_files:
        rel = os.path.relpath(cf, repo_root)
        try:
            with open(cf) as f:
                text = f.read()
        except OSError:
            continue  # already reported above
        for skill_name in sorted(set(SKILL_REF_RE.findall(text))):
            target = os.path.join(skills_dir, skill_name, "SKILL.md")
            if not os.path.isfile(target):
                failures.append(
                    f"SKILL REF in command {rel}: references "
                    f"skills/{skill_name}/SKILL.md which does not exist")

    # --- 6. Agent skill references ------------------------------------------
    agents_dir = os.path.join(plugin_dir, "agents")
    agent_files = sorted(glob.glob(os.path.join(agents_dir, "*.md")))
    for af in agent_files:
        rel = os.path.relpath(af, repo_root)
        try:
            with open(af) as f:
                text = f.read()
        except OSError as e:
            failures.append(f"AGENT unreadable: {rel}: {e}")
            continue
        fm, err = _split_frontmatter(text)
        if err:
            failures.append(f"AGENT {rel}: {err}")
            named = []
        else:
            named = _agent_skill_names(fm)
        # Skills named in frontmatter must resolve to an existing skill dir.
        for skill_name in named:
            if skill_name not in existing_skill_names:
                failures.append(
                    f"AGENT {rel}: frontmatter names skill '{skill_name}' which "
                    f"has no skills/{skill_name}/SKILL.md")
        # Skills referenced by path in the agent body must also resolve.
        for skill_name in sorted(set(SKILL_REF_RE.findall(text))):
            target = os.path.join(skills_dir, skill_name, "SKILL.md")
            if not os.path.isfile(target):
                failures.append(
                    f"AGENT {rel}: body references skills/{skill_name}/SKILL.md "
                    f"which does not exist")

    # --- 7. Marketplace registration ----------------------------------------
    mkt_path = os.path.join(repo_root, MARKETPLACE_REL)
    if not os.path.isfile(mkt_path):
        failures.append(f"MARKETPLACE missing: expected {mkt_path}")
    else:
        try:
            with open(mkt_path) as f:
                mkt = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            mkt = None
            failures.append(f"MARKETPLACE unreadable: {mkt_path}: {e}")
        if isinstance(mkt, dict):
            plugins = mkt.get("plugins")
            if not isinstance(plugins, list):
                failures.append(
                    f"MARKETPLACE malformed: 'plugins' in {MARKETPLACE_REL} is "
                    f"{type(plugins).__name__}, expected a list")
            else:
                # A plugin entry registers cds iff its source path resolves to
                # the cds plugin directory. We compare resolved absolute paths so
                # the entry's name is irrelevant — only the source matters.
                cds_abs = os.path.realpath(plugin_dir)
                found = False
                for entry in plugins:
                    if not isinstance(entry, dict):
                        continue
                    src = entry.get("source")
                    if not isinstance(src, str) or not src.strip():
                        continue
                    src_abs = os.path.realpath(os.path.join(repo_root, src))
                    if src_abs == cds_abs:
                        found = True
                        break
                if not found:
                    failures.append(
                        f"MARKETPLACE missing cds entry: no plugin in "
                        f"{MARKETPLACE_REL} has a source resolving to "
                        f"{PLUGIN_RELDIR}")
        elif mkt is not None:
            failures.append(
                f"MARKETPLACE malformed: top-level value in {MARKETPLACE_REL} is "
                f"{type(mkt).__name__}, expected a JSON object")

    return failures


if __name__ == "__main__":  # pragma: no cover
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    for line in run(os.path.abspath(root)):
        print(line)
