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

/** Where the per-project mode lives, relative to the project directory. */
const MODE_FILE = path.join('.claude', 'agent-teams-workforce.local.md');

/**
 * Reads orchestrator mode for a project.
 *
 * The guards constrain one role: an orchestrator sequencing an SDLC run. Most
 * sessions in a repo are not that — troubleshooting, one-off scripts, work that
 * has nothing to do with the pipelines. Enforcing the orchestrator contract on
 * those sessions blocks honest work and teaches the operator to route around the
 * guards, which is the behavior the guards exist to prevent.
 *
 * So the mode is explicit and OFF by default. Turn it on when starting a run.
 *
 * This is not the actor granting itself an exemption (REQ-ORCH-02): the mode is
 * a human decision recorded on disk before the work starts, machine-observable,
 * and identical for every call in the session. It is not a per-call judgement the
 * actor makes about its own intent.
 *
 * @param {string} projectDir
 * @returns {'on'|'off'}
 */
function orchestratorMode(projectDir) {
  if (!projectDir) return 'off';
  let raw;
  try {
    raw = fs.readFileSync(path.join(projectDir, MODE_FILE), 'utf8');
  } catch {
    return 'off';
  }
  // Frontmatter form: `orchestrator_mode: on` in the leading --- block.
  const match = /^\s*orchestrator_mode\s*:\s*["']?(\w+)["']?\s*$/m.exec(raw);
  if (!match) return 'off';
  const value = String(match[1]).toLowerCase();
  return value === 'on' || value === 'true' || value === 'enabled' ? 'on' : 'off';
}

/**
 * True when the orchestrator guards apply to this hook event.
 *
 * Two independent conditions must both hold:
 *   1. this is not the monorepo that builds the plugin, and
 *   2. the project has orchestrator mode switched on.
 *
 * @param {object} event parsed hook input; `cwd` names the project directory
 * @param {string} [pluginRoot]
 * @returns {boolean}
 */
function guardsApplyHere(event, pluginRoot = PLUGIN_ROOT) {
  const projectDir = process.env.CLAUDE_PROJECT_DIR || (event && event.cwd) || '';
  if (isPluginSourceRepo(projectDir, pluginRoot)) return false;
  return orchestratorMode(projectDir) === 'on';
}

/** Absolute path to a project's mode file. */
function modeFilePath(projectDir) {
  return path.join(projectDir || '', MODE_FILE);
}

module.exports = {
  PLUGIN_ROOT,
  MODE_FILE,
  isPluginSourceRepo,
  orchestratorMode,
  modeFilePath,
  guardsApplyHere,
};
