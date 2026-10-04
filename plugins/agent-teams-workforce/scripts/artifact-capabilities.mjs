// Static ownership check; inspect source data only, never execute workflows.
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { agentContracts } from './agent-contracts.mjs'
import { scanSource } from './workflow-runner-constraints.mjs'

export function artifactCapabilityProblems(root) {
  const contracts = agentContracts(root)
  const problems = []
  for (const file of readdirSync(join(root, 'workflows')).filter(x => x.endsWith('.js'))) {
    const source = scanSource(readFileSync(join(root, 'workflows', file), 'utf8')).stripped
    const roster = source.match(/const ROSTER = ([\s\S]*?)\nconst WRITER_ROLES/)
    const rosterNames = roster ? [...roster[1].matchAll(/'([a-z][a-z0-9-]+)'\s*:/g)].map(m => m[1]) : []
    for (const match of source.matchAll(/schema:\s*(?:relayKit\.)?ARTIFACT(?:_RETURN)?_SCHEMA\b/g)) {
      // Dispatch options use a bounded literal data grammar. Unrecognized forms
      // fail this build check; runtime also checks every resolved dynamic owner.
      const prefix = source.slice(Math.max(0, match.index - 500), match.index)
      const token = [...prefix.matchAll(/\bagentType\s*[:,]/g)].at(-1)
      const owner = token && prefix.slice(token.index).match(/^agentType:\s*(['"])([^'"]+)\1|^agentType:\s*(dispatchName\(d\.agentType\)|d\.agentType)\s*,|^agentType\s*,/)
      if (!owner) { problems.push(`${file}: unresolved artifact producer capability`); continue }
      const literal = owner[2]
      const dynamic = owner[3]
      const authorNames = [...source.matchAll(/\bauthor\([^,]+,\s*[A-Z_]+,\s*['"]([^'"]+)['"]/g)].map(m => m[1])
      const names = (literal ? [literal] : dynamic ? rosterNames : authorNames).map(name => name.replace(/^agent-teams-workforce:/, ''))
      if (!names.length) problems.push(`${file}: unresolved artifact producer capability`)
      for (const name of names) if (!contracts[name]?.artifactCapable) problems.push(`${file}: artifact producer ${name} requires effective Write and Bash tools`)
    }
  }
  return [...new Set(problems)]
}
