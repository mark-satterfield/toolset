'use strict';

/**
 * Scope test for the orchestrator guards.
 *
 * The guards govern sessions that USE this plugin. They must not govern the
 * session that BUILDS it: authoring a hook means writing .cjs and .json files
 * from a top-level session, which is exactly what the edit guard denies. A
 * guard that blocks its own development is a guard nobody can maintain.
 *
 * The distinction is machine-observable and needs nothing self-reported. The
 * session is building this plugin when both hold:
 *
 *   1. the project directory contains .claude-plugin/marketplace.json — the
 *      registry manifest, which exists only in the source monorepo and never
 *      in a consuming project or in the installed cache copy; and
 *   2. this plugin's own directory lives inside that project.
 *
 * Installed under ~/.claude/plugins/cache/... , condition 2 fails. In a
 * consuming project, condition 1 fails. Neither can be satisfied by intent,
 * assertion, or a flag the actor sets — only by where the files actually are.
 *
 * This is a scope boundary, not an exemption: inside the source repo the
 * guards are not the applicable ruleset, rather than being waived for an actor
 * that asked nicely.
 */

const fs = require('node:fs');
const path = require('node:path');

/** This plugin's root — hooks/lib/ is two levels below it. */
const PLUGIN_ROOT = path.resolve(__dirname, '..', '..');

/**
 * True when the given project directory is the source monorepo that contains
 * this plugin.
 *
 * @param {string} projectDir
 * @param {string} [pluginRoot]
 * @returns {boolean}
 */
function isPluginSourceRepo(projectDir, pluginRoot = PLUGIN_ROOT) {
  if (!projectDir) return false;

  let manifestExists = false;
  try {
    manifestExists = fs.existsSync(path.join(projectDir, '.claude-plugin', 'marketplace.json'));
  } catch {
    return false;
  }
  if (!manifestExists) return false;

  // The plugin directory must be a strict descendant of the project.
  const rel = path.relative(projectDir, pluginRoot);
  if (!rel) return false;
  if (rel.startsWith('..') || path.isAbsolute(rel)) return false;

  return true;
}

/**
 * True when the orchestrator guards apply to this hook event.
 *
 * @param {object} event parsed hook input; `cwd` names the project directory
 * @param {string} [pluginRoot]
 * @returns {boolean}
 */
function guardsApplyHere(event, pluginRoot = PLUGIN_ROOT) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || (event && event.cwd) || '';
  return !isPluginSourceRepo(projectDir, pluginRoot);
}

module.exports = { PLUGIN_ROOT, isPluginSourceRepo, guardsApplyHere };
