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
// quoted agentType literal, and fail each one that carries this plugin's prefix; a plain name with
// no agents/<name>.md is reported.
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
//
// THE SAME FAILURE, ONE STEP EARLIER: `skills:` IN AGENT FRONTMATTER.
//
// An agent declares the skills it loads as plain strings, resolved when the agent starts. A name
// with no skill behind it is not an error anybody sees — the skill simply never loads, and the
// agent runs on whatever it already believed. That is indistinguishable from the agent having the
// skill and ignoring it, which is the most expensive kind of silence. It is the identical defect
// class this file already guards for `agentType`, so it is checked the identical way, with the
// identical exemption: a name outside this plugin's prefix is REPORTED, never failed.
//
// PLAIN NAMES. A workflow names every agent by its plain front-matter name, and the fable shared
// block (scripts/shared-blocks/fable.js) resolves it at dispatch: Claude Code registers a plugin
// agent only as `agent-teams-workforce:<name>`, so an agent with no user-level copy is dispatched
// under that prefix, and an agent with `mcpServers` keeps its plain name, which names its
// user-level copy and the MCP servers it carries. A literal agentType under this plugin's prefix
// FAILS: it would bypass that resolution. A user-level agent may use ${CLAUDE_PLUGIN_ROOT},
// which the sync hook replaces with the install path in the copy, and FAILS on any other
// plugin-only variable, which nothing resolves in the copy.
import { readdirSync, readFileSync, existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = process.argv[2] || path.join(here, '..')
const workflowsDir = path.join(root, 'workflows')
const agentsDir = path.join(root, 'agents')
const skillsDir = path.join(root, 'skills')
const { userLevelAgentNames, UNRESOLVABLE_IN_COPY } = createRequire(import.meta.url)(
  '../hooks/lib/user-level-agents.cjs'
)
const userLevel = new Set(userLevelAgentNames(root))

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

// Every `skills:` entry declared in an agent's YAML frontmatter, in either spelling YAML
// allows: `skills: [a, b]` on one line, or a block of `  - a` items beneath it.
function declaredSkills(raw) {
  const lines = raw.split('\n')
  if (lines[0].trim() !== '---') return []
  const end = lines.indexOf('---', 1)
  if (end === -1) return []
  const head = lines.slice(1, end)
  const at = head.findIndex((l) => /^skills:/.test(l))
  if (at === -1) return []
  const inline = head[at].slice('skills:'.length).trim()
  if (inline.startsWith('[')) {
    return inline
      .replace(/^\[|\]$/g, '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  }
  const names = []
  for (const line of head.slice(at + 1)) {
    const item = line.match(/^\s+-\s*(\S+)\s*$/)
    if (!item) break
    names.push(item[1])
  }
  return names
}

const missing = []
const prefixed = []
const unresolvable = [...userLevel].filter((name) =>
  UNRESOLVABLE_IN_COPY.test(readFileSync(path.join(agentsDir, `${name}.md`), 'utf8'))
)
const external = []
const missingSkills = []
const externalSkills = []
let skillRefs = 0
let computed = 0
let references = 0

for (const file of files) {
  const raw = readFileSync(path.join(workflowsDir, file), 'utf8')
  const lineOf = (index) => raw.slice(0, index).split('\n').length
  for (const m of raw.matchAll(LITERAL)) {
    references++
    const name = m[2]
    const where = { file, line: lineOf(m.index), name }
    if (name.startsWith(PREFIX)) {
      prefixed.push(where)
      continue
    }
    if (!defined.has(name) || !existsSync(path.join(agentsDir, `${name}.md`))) external.push(where)
  }
  computed += [...raw.matchAll(COMPUTED)].length
}

for (const file of readdirSync(agentsDir).filter((f) => f.endsWith('.md')).sort()) {
  const raw = readFileSync(path.join(agentsDir, file), 'utf8')
  for (const name of declaredSkills(raw)) {
    skillRefs++
    if (!name.startsWith(PREFIX)) {
      externalSkills.push({ file, name })
      continue
    }
    const bare = name.slice(PREFIX.length)
    if (!existsSync(path.join(skillsDir, bare, 'SKILL.md'))) missingSkills.push({ file, name, bare })
  }
}

for (const { file, line, name } of prefixed) {
  console.log(
    `FAIL  workflows/${file}:${line}  —  agentType '${name}' carries the plugin prefix. ` +
      `Name it by its plain name '${name.slice(PREFIX.length)}'; the fable shared block adds the prefix where Claude Code needs it.`
  )
}

for (const name of unresolvable) {
  console.log(
    `FAIL  agents/${name}.md  —  a user-level agent names a plugin-only variable other than \${CLAUDE_PLUGIN_ROOT}; ` +
      'its copy in the user-level agents directory cannot resolve it.'
  )
}

for (const { file, line, name } of external) {
  console.log(
    `NOTE  workflows/${file}:${line}  —  agentType '${name}' is not an agent of this plugin. ` +
      `It must be provided by the consuming project (.claude/agents/${name}.md); this plugin cannot verify it.`
  )
}

for (const { file, name, bare } of missingSkills) {
  console.log(
    `FAIL  agents/${file}  —  skills entry '${name}' has no definition. ` +
      `Expected skills/${bare}/SKILL.md. An unresolvable skill does not error — it silently never ` +
      `loads, and the agent runs on whatever it already believed.`
  )
}

for (const { file, name } of externalSkills) {
  console.log(
    `NOTE  agents/${file}  —  skills entry '${name}' is not a ${PREFIX} skill. ` +
      `It must be provided by another plugin or the consuming project; this plugin cannot verify it.`
  )
}

console.log(
  prefixed.length
    ? `\n${prefixed.length} of ${references} dispatched agentType(s) carry the plugin prefix`
    : `all ${references - external.length} plugin agentType(s) across ${files.length} workflow scripts resolve to an agents/*.md definition` +
        `${external.length ? ` (plus ${external.length} project-level name(s) listed above)` : ''}` +
        `${computed ? `; ${computed} computed reference(s) were not text-visible` : ''}`
)

console.log(
  missingSkills.length
    ? `${missingSkills.length} of ${skillRefs} declared skills entr(ies) resolve to NO skill definition`
    : `all ${skillRefs - externalSkills.length} plugin skills entr(ies) across agents/ resolve to a skills/*/SKILL.md definition` +
        `${externalSkills.length ? ` (plus ${externalSkills.length} out-of-plugin name(s) listed above)` : ''}`
)

process.exit(prefixed.length || missingSkills.length || unresolvable.length ? 1 : 0)
