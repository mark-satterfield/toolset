// Build dispatch identity and skill requirements from the plugin's owned agent definitions.
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

export function agentContracts(root) {
  const contracts = {}
  for (const file of readdirSync(join(root, 'agents')).filter(x => x.endsWith('.md')).sort()) {
    const raw = readFileSync(join(root, 'agents', file), 'utf8')
    const front = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/)
    if (!front) throw new Error(`Missing frontmatter: ${file}`)
    const name = file.slice(0, -3)
    const inline = front[1].match(/^skills:\s*\[([^\]]*)\]/m)
    const block = front[1].match(/^skills:\s*\n((?:[ \t]*-.*\n?)*)/m)
    const skills = inline ? inline[1].split(',') : block ? block[1].split('\n').map(x => x.replace(/^\s*-\s*/, '')) : []
    const values = field => {
      const match = front[1].match(new RegExp(`^${field}:\\s*(.*)$`, 'm'))
      return match ? match[1].replace(/^\[|\]$/g, '').split(',').map(x => x.trim()).filter(Boolean) : null
    }
    const tools = values('tools')
    const denied = values('disallowedTools') || []
    contracts[name] = {
      artifactCapable: ['Write', 'Bash'].every(tool => (!tools || tools.includes(tool)) && !denied.includes(tool)),
      agentType: /^mcpServers:/m.test(front[1]) ? name : `agent-teams-workforce:${name}`,
      skills: skills.map(x => x.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean),
    }
  }
  return contracts
}
