// Validation only: whether each owned agent definition grants the tools an artifact producer needs.
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

export function agentContracts(root) {
  const contracts = {}
  for (const file of readdirSync(join(root, 'agents')).filter(x => x.endsWith('.md')).sort()) {
    const raw = readFileSync(join(root, 'agents', file), 'utf8')
    const front = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)
    if (!front) throw new Error(`Missing frontmatter: ${file}`)
    const values = field => {
      const match = front[1].match(new RegExp(`^${field}:\\s*(.*)$`, 'm'))
      return match ? match[1].replace(/^\[|\]$/g, '').split(',').map(x => x.trim()).filter(Boolean) : null
    }
    const tools = values('tools')
    const denied = values('disallowedTools') || []
    contracts[file.slice(0, -3)] = {
      artifactCapable: ['Write', 'Bash'].every(tool => (!tools || tools.includes(tool)) && !denied.includes(tool)),
    }
  }
  return contracts
}
