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

/** This plugin's key in installed_plugins.json. */
const PLUGIN_KEY = 'agent-teams-workforce@mark-satterfield';

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
 * The text of a user-level copy of an agent: the plugin file with every
 * `${CLAUDE_PLUGIN_ROOT}` (or `$CLAUDE_PLUGIN_ROOT`) replaced by the absolute
 * path of the plugin install it was copied from. The variable is set only for
 * a plugin's own hooks and commands, never for an agent's Bash calls, so the
 * copy names the install directly.
 *
 * @param {string} raw
 * @param {string} pluginRoot
 * @returns {string}
 */
function renderUserLevelAgent(raw, pluginRoot) {
  return raw.replace(/\$\{CLAUDE_PLUGIN_ROOT\}|\$CLAUDE_PLUGIN_ROOT\b/g, () => pluginRoot);
}

/** Plugin-only variables a user-level copy cannot resolve and the copy does not substitute. */
const UNRESOLVABLE_IN_COPY = /\$\{?CLAUDE_PLUGIN_DATA\b/;

/**
 * The user-level agents directory: `$CLAUDE_CONFIG_DIR/agents`, defaulting to
 * `~/.claude/agents`.
 *
 * @returns {string}
 */
function userAgentsDir() {
  return path.join(configDir(), 'agents');
}

/** `$CLAUDE_CONFIG_DIR`, defaulting to `~/.claude`. */
function configDir() {
  return process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
}

/**
 * The file Claude Code rewrites when it installs or updates a plugin.
 *
 * @returns {string}
 */
function installedPluginsPath() {
  return path.join(configDir(), 'plugins', 'installed_plugins.json');
}

/** The version a plugin root declares in .claude-plugin/plugin.json, or null. */
function versionOf(root) {
  try {
    return JSON.parse(fs.readFileSync(path.join(root, '.claude-plugin', 'plugin.json'), 'utf8')).version || null;
  } catch {
    return null;
  }
}

/** Compares two dotted numeric versions; a missing version sorts lowest. */
function compareVersions(a, b) {
  if (!a || !b) return a ? 1 : b ? -1 : 0;
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d) return d;
  }
  return 0;
}

/**
 * The highest-versioned install of this plugin with an agents/ directory: every
 * install path installed_plugins.json records for it, plus the given root.
 *
 * @param {string} fallbackRoot
 * @returns {string}
 */
function newestPluginRoot(fallbackRoot) {
  const roots = [fallbackRoot];
  try {
    const installed = JSON.parse(fs.readFileSync(installedPluginsPath(), 'utf8'));
    const entries = (installed.plugins || {})[PLUGIN_KEY];
    if (Array.isArray(entries)) roots.push(...entries.map((e) => e.installPath).filter(Boolean));
  } catch {
    // No installed_plugins.json: the given root is the only install known.
  }
  return roots
    .filter((root) => fs.existsSync(path.join(root, 'agents')))
    .reduce((best, root) => (compareVersions(versionOf(root), versionOf(best)) > 0 ? root : best), fallbackRoot);
}

module.exports = {
  OWNED_MANIFEST,
  PLUGIN_ROOT,
  UNRESOLVABLE_IN_COPY,
  declaresMcpServers,
  installedPluginsPath,
  newestPluginRoot,
  renderUserLevelAgent,
  userAgentsDir,
  userLevelAgentNames,
};
