#!/usr/bin/env node
'use strict';

/**
 * SessionStart and FileChanged hook — keeps the user-level copies of this
 * plugin's MCP agents identical to the newest installed release of the plugin.
 *
 * Every agents/*.md with an `mcpServers:` entry runs from its copy in the
 * user-level agents directory (see lib/user-level-agents.cjs). This hook copies
 * each one there, with `${CLAUDE_PLUGIN_ROOT}` replaced by the absolute path of
 * the install it copies from, when the copy is missing or differs from that, and removes a copy it
 * wrote for an agent that no longer declares `mcpServers`. It records the names
 * it owns in `.agent-teams-workforce-owned.json` in that directory and never
 * writes or removes any other file: a same-named file it does not own is left
 * as it is and reported.
 *
 * Claude Code has no hook event for a plugin install, update or reload. So the
 * hook runs at SessionStart in every session, whatever the repository, and its
 * SessionStart output asks Claude Code to watch installed_plugins.json, which
 * Claude Code rewrites when it installs or updates a plugin. When that file
 * changes, FileChanged runs the hook again, which copies from the newest
 * install path the file records. It never fails the session.
 */

const fs = require('node:fs');
const path = require('node:path');
const {
  OWNED_MANIFEST,
  PLUGIN_ROOT,
  installedPluginsPath,
  newestPluginRoot,
  renderUserLevelAgent,
  userAgentsDir,
  userLevelAgentNames,
} = require('./lib/user-level-agents.cjs');

/** Reads the owned-name manifest, or an empty one when absent or malformed. */
function readOwned(manifestPath) {
  try {
    const parsed = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    return Array.isArray(parsed.agents) ? parsed.agents : [];
  } catch {
    return [];
  }
}

/** Reads the hook input from stdin; an empty object when absent or malformed. */
function readInput() {
  try {
    return JSON.parse(fs.readFileSync(0, 'utf8'));
  } catch {
    return {};
  }
}

/** Reads a file as bytes, or null when absent. */
function readBytes(filePath) {
  try {
    return fs.readFileSync(filePath);
  } catch {
    return null;
  }
}

function sync() {
  const pluginRoot = newestPluginRoot(process.env.CLAUDE_PLUGIN_ROOT || PLUGIN_ROOT);
  const destDir = userAgentsDir();
  const manifestPath = path.join(destDir, OWNED_MANIFEST);
  const previouslyOwned = new Set(readOwned(manifestPath));
  const names = userLevelAgentNames(pluginRoot);

  fs.mkdirSync(destDir, { recursive: true });

  const owned = [];
  const written = [];
  const removed = [];
  const foreign = [];

  for (const name of names) {
    const source = Buffer.from(
      renderUserLevelAgent(fs.readFileSync(path.join(pluginRoot, 'agents', `${name}.md`), 'utf8'), pluginRoot),
      'utf8'
    );
    const destPath = path.join(destDir, `${name}.md`);
    const current = readBytes(destPath);
    if (current && !previouslyOwned.has(name) && !current.equals(source)) {
      foreign.push(name);
      continue;
    }
    owned.push(name);
    if (!current || !current.equals(source)) {
      fs.writeFileSync(destPath, source);
      written.push(name);
    }
  }

  for (const name of previouslyOwned) {
    if (names.includes(name)) continue;
    const destPath = path.join(destDir, `${name}.md`);
    if (fs.existsSync(destPath)) {
      fs.unlinkSync(destPath);
      removed.push(name);
    }
  }

  const manifest = `${JSON.stringify({ plugin: 'agent-teams-workforce', agents: owned }, null, 2)}\n`;
  const currentManifest = readBytes(manifestPath);
  if (!currentManifest || currentManifest.toString('utf8') !== manifest) {
    fs.writeFileSync(manifestPath, manifest);
  }

  if (written.length || removed.length) {
    process.stderr.write(
      `agent-teams-workforce: user-level agents in ${destDir} — ` +
        `${written.length} written, ${removed.length} removed. ` +
        'They take effect in sessions started from now on.\n'
    );
  }
  if (foreign.length) {
    process.stderr.write(
      `agent-teams-workforce: ${foreign.length} file(s) in ${destDir} share a name with a plugin MCP agent ` +
        `but were not written by this plugin, so they were left as they are: ${foreign.join(', ')}. ` +
        'Dispatches of those names run that file, not the plugin agent.\n'
    );
  }
}

const input = readInput();
const watched = installedPluginsPath();
const isFileChange = input.hook_event_name === 'FileChanged';

if (!isFileChange || path.resolve(String(input.file_path || '')) === watched) {
  try {
    sync();
  } catch (error) {
    process.stderr.write(`agent-teams-workforce: user-level agent sync failed — ${error.message}\n`);
  }
}

if (!isFileChange) {
  process.stdout.write(
    `${JSON.stringify({ hookSpecificOutput: { hookEventName: 'SessionStart', watchPaths: [watched] } })}\n`
  );
}
process.exit(0);
