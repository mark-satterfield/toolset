#!/usr/bin/env node
'use strict';

// Read-only: the owner supplies the workflow release and host configuration being evaluated.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { renderUserLevelAgent, declaresMcpServers, OWNED_MANIFEST } = require('../hooks/lib/user-level-agents.cjs');

function readJson(file, issues) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (error) {
    issues.push(`${file}: ${error.message}`);
    return null;
  }
}

function frontmatterList(raw, key) {
  const front = raw.startsWith('---\n') ? raw.split('\n---', 2)[0] : '';
  const lines = front.split('\n');
  const inline = lines.find((line) => line.startsWith(`${key}: [`));
  if (inline) return inline.slice(inline.indexOf('[') + 1, inline.lastIndexOf(']')).split(',').map((value) => value.trim().replace(/^['"]|['"]$/g, '')).filter(Boolean);
  const start = lines.findIndex((line) => line === `${key}:`);
  const values = [];
  if (start < 0) return values;
  for (const line of lines.slice(start + 1)) {
    const match = /^\s+-\s+([^#]+?)\s*$/.exec(line);
    if (match) values.push(match[1].replace(/^['"]|['"]$/g, ''));
    else if (line.trim()) break;
  }
  return values;
}

function report(options) {
  const issues = [];
  const root = path.resolve(options['workflow-root']);
  const config = path.resolve(options['config-dir'] || process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude'));
  const project = options.project ? path.resolve(options.project) : null;
  const manifest = readJson(path.join(root, '.claude-plugin/plugin.json'), issues);
  const registry = readJson(path.join(config, 'plugins/installed_plugins.json'), issues);
  const installs = registry?.plugins?.['agent-teams-workforce@mark-satterfield'] || [];
  const matchingInstalls = installs.filter((entry) => !project || !entry.projectPath || path.resolve(entry.projectPath) === project);
  const owned = readJson(path.join(config, 'agents', OWNED_MANIFEST), issues);
  const ownedNames = new Set(owned?.agents || []);
  const mcpFile = options['mcp-config'] ? path.resolve(options['mcp-config']) : null;
  const mcp = mcpFile ? readJson(mcpFile, issues) : null;
  const servers = new Set(Object.keys(mcp?.mcpServers || {}));
  const copies = [];
  const skills = new Set();
  const requiredServers = new Set();
  let agentFiles = [];
  try {
    agentFiles = fs.readdirSync(path.join(root, 'agents')).filter((file) => file.endsWith('.md')).sort();
  } catch (error) {
    issues.push(`Cannot read workflow agents: ${error.message}`);
  }
  for (const file of agentFiles) {
    const raw = fs.readFileSync(path.join(root, 'agents', file), 'utf8');
    for (const skill of frontmatterList(raw, 'skills')) skills.add(skill);
    for (const server of frontmatterList(raw, 'mcpServers')) requiredServers.add(server);
    if (!declaresMcpServers(raw)) continue;
    const name = path.basename(file, '.md');
    const target = path.join(config, 'agents', file);
    const exists = fs.existsSync(target);
    const current = exists ? fs.readFileSync(target, 'utf8') : null;
    const exact = current === renderUserLevelAgent(raw, root);
    const matchingRoots = installs.filter((entry) => {
      const source = path.join(entry.installPath || '', 'agents', file);
      return current !== null && fs.existsSync(source) && current === renderUserLevelAgent(fs.readFileSync(source, 'utf8'), entry.installPath);
    }).map((entry) => ({ root: entry.installPath, version: entry.version }));
    copies.push({ name, path: target, status: !exists ? 'missing' : !ownedNames.has(name) ? 'foreign' : exact ? 'matches-workflow' : 'differs-from-workflow', exactContentMatch: exact, matchingInstalledReleases: matchingRoots });
  }
  const skillResolution = [...skills].sort().map((name) => {
    const parts = name.split(':');
    const internal = parts.length === 1 || parts[0] === 'agent-teams-workforce';
    const resolved = internal ? path.join(root, 'skills', parts.at(-1), 'SKILL.md') : null;
    return { name, status: !internal ? 'external-not-verified' : fs.existsSync(resolved) ? 'present' : 'missing', path: resolved };
  });
  return {
    workflow: { root, version: manifest?.version || null }, configDir: config, project,
    matchingInstalledReleases: matchingInstalls.map(({ installPath, version, scope, projectPath }) => ({ root: installPath, version, scope, projectPath })),
    workflowRootRegistered: matchingInstalls.some((entry) => path.resolve(entry.installPath || '') === root),
    copies, skills: skillResolution,
    mcp: { configPath: mcpFile, required: [...requiredServers].sort().map((name) => ({ name, status: !mcpFile ? 'not-checked' : servers.has(name) ? 'declared' : 'not-declared-in-supplied-file' })) },
    readErrors: issues,
    limits: 'File/configuration comparison only. Matching content is not proof of copy provenance or active session loading. External skills, merged MCP configuration, credentials and live server health are not verified.',
  };
}

if (require.main === module) {
  const options = {};
  const values = process.argv.slice(2);
  for (let i = 0; i < values.length; i += 2) {
    const key = values[i].replace(/^--/, '');
    if (!['workflow-root', 'config-dir', 'project', 'mcp-config'].includes(key) || !values[i + 1]) {
      process.stderr.write('Usage: report-release-coherence.cjs --workflow-root PATH [--config-dir PATH] [--project PATH] [--mcp-config PATH]\n');
      process.exit(2);
    }
    options[key] = values[i + 1];
  }
  if (!options['workflow-root']) {
    process.stderr.write('--workflow-root is required; name the release whose workflows will run.\n');
    process.exit(2);
  }
  process.stdout.write(`${JSON.stringify(report(options), null, 2)}\n`);
}

module.exports = { frontmatterList, report };
