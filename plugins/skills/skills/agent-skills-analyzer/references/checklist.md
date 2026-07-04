# Plugin Audit Checklist

This file documents the audit dimensions encoded in `scripts/audit_plugin.py`. Each finding code maps to a check in the script. Read when extending the audit logic or interpreting a finding.

## Subagent checks (.claude/agents/*.md)

`subagent-missing-frontmatter` — error. File does not begin with a `---` block, or frontmatter is malformed.

`subagent-missing-name` — error. Frontmatter has no `name` field.

`subagent-missing-description` — error. Frontmatter has no `description`, or description is under 30 characters.

`subagent-no-constraints` — warn. Frontmatter declares neither `tools` nor `model`, and body is under 20 lines. The subagent has no role-specific identity; convert to a forking skill.

`subagent-body-too-long` — warn. Body exceeds 50 prose lines (excluding code fences). Likely embedded playbook content; extract to a skill.

`subagent-no-output-contract` — info. Body does not contain a section describing the return format. Heuristic: looks for headings or phrases like "output", "return", "respond with", "output format".

`subagent-hollow` — warn. Body is under 5 lines. The subagent envelope adds nothing; expand the role or remove.

## Skill checks (.claude/skills/*/SKILL.md)

`skill-missing-frontmatter` — error. SKILL.md has no `---` block.

`skill-missing-name` — error. Frontmatter lacks `name`.

`skill-missing-description` — error. Frontmatter lacks `description`.

`skill-name-invalid` — error. Name contains uppercase letters, spaces, underscores, or exceeds 64 characters. Required pattern: lowercase letters, digits, hyphens.

`skill-description-too-short` — warn. Description is under 60 characters. Likely insufficient as classifier text.

`skill-description-no-trigger` — warn. Description lacks trigger language ("use when", "triggers", "when", "for"). Routing reliability will suffer.

`skill-body-too-long` — warn. SKILL.md exceeds 250 prose lines. Move detail to `references/`.

`skill-references-dir-unused` — warn. `references/` directory exists with content but is not mentioned in SKILL.md body. References that never load are dead weight.

`skill-scripts-dir-unused` — warn. `scripts/` directory exists with content but is not mentioned in SKILL.md body. Same problem.

`skill-disabled-invocation-undocumented` — warn. `disable-model-invocation: true` is set, but no `/command` usage is present in SKILL.md.

`skill-fork-on-thin-body` — info. `context: fork` declared, body under 20 lines, no references or scripts. Spawn cost likely dominates.

`skill-no-fork-on-macro-body` — info. Body contains macro-shape keywords (read input, write output, transform, batch, process, rewrite, convert) and exceeds 30 lines, but no `context: fork`. Consider forking to keep parent context clean.

## Cross-file checks

`paired-files-duplication` — warn. A subagent in `.claude/agents/X.md` and a skill in `.claude/skills/X/SKILL.md` share name X, and their heading sets show Jaccard similarity above 0.4. The skill should own the playbook; the subagent should reference it.

## Severity levels

`error`: the file is broken or violates a hard rule (missing required frontmatter, invalid name). Fix before publishing.

`warn`: likely design issue; may be intentional but worth reviewing.

`info`: heuristic deviation; review before acting.

## Output format

The script emits JSON to stdout:

```json
{
  "plugin_root": "/abs/path/to/plugin",
  "scanned_at": "2026-05-20T12:34:56+00:00",
  "files_scanned": 12,
  "findings": [
    {
      "file": ".claude/agents/code-reviewer.md",
      "severity": "warn",
      "code": "subagent-body-too-long",
      "message": "Body is 87 prose lines (limit 50). Likely embedded playbook content.",
      "suggestion": "Extract methodology to a skill, leave role declaration in the subagent."
    }
  ]
}
```

## Exit codes

`0`: no findings, or only `info` severity.

`1`: at least one `warn` finding, no errors.

`2`: at least one `error` finding.

`3`: scan failed (plugin root not found, IO error).

## Extending the script

To add a check:

1. Decide which file class it applies to (subagent, skill, or cross-file) and add a function or branch in the appropriate section of `audit_plugin.py`.
2. Use the `finding(rel_path, severity, code, message, suggestion)` helper to build the result.
3. Document the new code in this file under the matching section.
4. The dispatch is data-driven; no central registry to update.

## Known limitations

The frontmatter parser handles single-line scalar values and `- item` lists. Multi-line strings (`|` or `>`) and nested mappings are not parsed and may produce false-negative findings on the affected fields.

Body line counts exclude fenced code blocks but not indented code or HTML comments.

The "macro keyword" detection for fork recommendations is heuristic; review the body before acting on `skill-no-fork-on-macro-body`.

The duplication check compares heading sets only. Body-level prose duplication is not detected.
