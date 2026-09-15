#!/usr/bin/env node
// Cross-check every `agentType:` a workflow script dispatches against the agent
// definitions that actually exist in agents/.
//
// Usage:  node scripts/check-agent-types.mjs [plugin-dir]
// Exit:   0 = every plugin agentType resolves to an agents/*.md file, 1 = at least one does not
//
// WHY THIS EXISTS.
//
// A spec-authoring dispatch once named `api-design-reviewer` under this plugin's prefix. That
// is a SKILL, not an agent. Nothing rejected it: the name is a plain string, it is only resolved at dispatch,
// and by then the phase is already running inside a headless composite with nobody watching.
// A dispatch that cannot resolve is not a slow phase — it is a phase that produced nothing,
// discovered after the run.
//
// The check is mechanical and total: read the raw bytes of every workflows/*.js, collect every
// quoted agentType literal, and require a matching agents/<name>.md for each one carrying this
// plugin's prefix.
//
// NAMES FROM OUTSIDE THIS PLUGIN are reported, never failed. `filing-clerk` is a project-level
// agent living in the consuming repo's .claude/agents/, which this plugin cannot see and has no
// business asserting about. Failing on it would make the gate unusable; saying nothing would hide
// a real dispatch. So it is listed, and the exit status ignores it.
//
// A COMPUTED agentType (`agentType: m.agentType`) is invisible to a text scan. Those values are
// themselves written as literals in the maker tables this scan already reads, so the coverage is
// in practice complete — but the count of computed references is printed, so a reader knows what
// the scan could not see.
import { readdirSync, readFileSync, existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = process.argv[2] || path.join(here, '..')
const workflowsDir = path.join(root, 'workflows')
const agentsDir = path.join(root, 'agents')

const PREFIX = 'agent-teams-workforce:'
const LITERAL = /agentType:\s*(['"])([^'"]+)\1/g
const COMPUTED = /agentType:\s*(?!['"])[A-Za-z_$][\w$.[\]']*/g

const files = readdirSync(workflowsDir)
  .filter((f) => f.endsWith('.js'))
  .sort()
const defined = new Set(
  readdirSync(agentsDir)
    .filter((f) => f.endsWith('.md'))
    .map((f) => path.basename(f, '.md'))
)

const missing = []
const external = []
let computed = 0
let references = 0

for (const file of files) {
  const raw = readFileSync(path.join(workflowsDir, file), 'utf8')
  const lineOf = (index) => raw.slice(0, index).split('\n').length
  for (const m of raw.matchAll(LITERAL)) {
    references++
    const name = m[2]
    const where = { file, line: lineOf(m.index), name }
    if (!name.startsWith(PREFIX)) {
      external.push(where)
      continue
    }
    const bare = name.slice(PREFIX.length)
    if (!defined.has(bare) || !existsSync(path.join(agentsDir, `${bare}.md`))) missing.push(where)
  }
  computed += [...raw.matchAll(COMPUTED)].length
}

for (const { file, line, name } of missing) {
  console.log(
    `FAIL  workflows/${file}:${line}  —  agentType '${name}' has no definition. ` +
      `Expected agents/${name.slice(PREFIX.length)}.md. A dispatch that cannot resolve produces nothing, ` +
      `and the run only finds out afterwards.`
  )
}

for (const { file, line, name } of external) {
  console.log(
    `NOTE  workflows/${file}:${line}  —  agentType '${name}' is not a ${PREFIX} agent. ` +
      `It must be provided by the consuming project (.claude/agents/${name}.md); this plugin cannot verify it.`
  )
}

console.log(
  missing.length
    ? `\n${missing.length} of ${references} dispatched agentType(s) resolve to NO agent definition`
    : `all ${references - external.length} plugin agentType(s) across ${files.length} workflow scripts resolve to an agents/*.md definition` +
        `${external.length ? ` (plus ${external.length} project-level name(s) listed above)` : ''}` +
        `${computed ? `; ${computed} computed reference(s) were not text-visible` : ''}`
)

process.exit(missing.length ? 1 : 0)
