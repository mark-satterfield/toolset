---
description: Audit a plugin's agents and skills for structural anti-patterns (role vs playbook, fork, duplication)
argument-hint: [plugin-or-repo-root]
---

Run the architectural audit from the `agent-skills-analyzer` skill against the path
in `$ARGUMENTS`. If no path is given, use the root of the plugin (or repository)
containing the current working directory.

Use the Bash tool to run, substituting that path for `<root>`:

python3 "${CLAUDE_PLUGIN_ROOT}/skills/agent-skills-analyzer/scripts/audit_plugin.py" <root> --pretty

Then apply the `agent-skills-analyzer` review workflow: group the JSON findings by
severity, and for each affected file give a verdict — keep, patch, refactor, or
delete — with a one-line rationale. Do not rewrite any files; surface the findings
and let me decide.
