'use strict';

/**
 * The agents this plugin runs from the user-level agents directory.
 *
 * Claude Code ignores the `mcpServers` frontmatter of an agent defined in a
 * plugin. An agent that needs an MCP server therefore runs from its copy in
 * `~/.claude/agents/`, which every session on the machine loads whatever
 * repository it runs in, and is dispatched by its plain name. Every agents/*.md
 * whose frontmatter has an `mcpServers:` entry is one of them.
 */

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

/** This plugin's root — hooks/lib/ is two levels below it. */
const PLUGIN_ROOT = path.resolve(__dirname, '..', '..');

/** Names the copies this plugin owns in the user-level agents directory. */
const OWNED_MANIFEST = '.agent-teams-workforce-owned.json';

/**
 * True when the YAML frontmatter of an agent file has an `mcpServers:` key.
 *
 * @param {string} raw
 * @returns {boolean}
 */
function declaresMcpServers(raw) {
  const lines = raw.split('\n');
  if (lines[0].trim() !== '---') return false;
  const end = lines.indexOf('---', 1);
  if (end === -1) return false;
  return lines.slice(1, end).some((line) => /^mcpServers:/.test(line));
}

/**
 * The names of this plugin's agents that run from the user-level directory.
 *
 * @param {string} [pluginRoot]
 * @returns {string[]}
 */
function userLevelAgentNames(pluginRoot = PLUGIN_ROOT) {
  const agentsDir = path.join(pluginRoot, 'agents');
  return fs
    .readdirSync(agentsDir)
    .filter((f) => f.endsWith('.md'))
    .filter((f) => declaresMcpServers(fs.readFileSync(path.join(agentsDir, f), 'utf8')))
    .map((f) => path.basename(f, '.md'))
    .sort();
}

/**
 * The user-level agents directory: `$CLAUDE_CONFIG_DIR/agents`, defaulting to
 * `~/.claude/agents`.
 *
 * @returns {string}
 */
function userAgentsDir() {
  const configDir = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
  return path.join(configDir, 'agents');
}

module.exports = {
  OWNED_MANIFEST,
  PLUGIN_ROOT,
  declaresMcpServers,
  userAgentsDir,
  userLevelAgentNames,
};
