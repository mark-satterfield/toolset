'use strict';

/**
 * ssbd-ja5d / REQ-ORCH-09 — the standing contradiction between AGENTS.md
 * non-negotiable rule #2 ("Never --dangerously-skip-permissions on bare
 * metal") and the live permission configuration must be resolved by an
 * authority, not arbitrated by an agent at runtime.
 *
 * Threat model entry: root cause (I) "STANDING CONTRADICTION" —
 * AGENTS.md:154 vs .claude/settings.local.json:120
 * ("defaultMode": "bypassPermissions"), with implement-all-prds.md:129
 * instructing the agent to "treat the setting as current reality".
 *
 * These are cross-repo contract assertions against the SkillSpoke repo
 * (machine-local paths per the acceptance criteria; override the root with
 * SKILLSPOKE_REPO). No process is spawned.
 *
 * INTENDED RED STATE: all three tests fail against the current files.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const helpers = require('./helpers.cjs');

const REPO = helpers.SKILLSPOKE_REPO;
const AGENTS_MD = path.join(REPO, 'AGENTS.md');
const SETTINGS_JSON = path.join(REPO, '.claude', 'settings.json');
const SETTINGS_LOCAL_JSON = path.join(REPO, '.claude', 'settings.local.json');
const MISSION_MD = path.join(REPO, '.claude', 'missions', 'implement-all-prds.md');

/** Reads a JSON file, returning null when absent. */
function readJsonIfPresent(p) {
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

test('AC-ORCH-09a: bypassPermissions is either absent from settings.local.json or covered by an explicit dated exception in AGENTS.md', () => {
  assert.ok(fs.existsSync(AGENTS_MD), `precondition: ${AGENTS_MD} must exist to evaluate the rule`);
  const agentsMd = fs.readFileSync(AGENTS_MD, 'utf8');
  const prohibition = /--dangerously-skip-permissions/.test(agentsMd);
  assert.ok(prohibition, 'precondition: AGENTS.md still states the non-negotiable prohibition');

  const local = readJsonIfPresent(SETTINGS_LOCAL_JSON);
  const bypassSet =
    local !== null && (local.defaultMode === 'bypassPermissions' ||
      (local.permissions && local.permissions.defaultMode === 'bypassPermissions'));

  // A dated exception is a line naming the setting together with an ISO date.
  const datedException = agentsMd
    .split('\n')
    .some((line) => /bypassPermissions/.test(line) && /\d{4}-\d{2}-\d{2}/.test(line));

  assert.ok(
    !bypassSet || datedException,
    `AC-ORCH-09a [root cause I, ssbd-ja5d]: ${SETTINGS_LOCAL_JSON} sets ` +
      `defaultMode=bypassPermissions while AGENTS.md non-negotiable rule #2 prohibits it and ` +
      `records no dated exception naming the setting. Both the prohibition and the setting ` +
      `are simultaneously in force — the conflict is unresolved (REQ-ORCH-09).`,
  );
});

test('AC-ORCH-09b: the mission file does not instruct an agent to arbitrate a non-negotiable rule against a conflicting setting at runtime', () => {
  assert.ok(fs.existsSync(MISSION_MD), `precondition: ${MISSION_MD} must exist`);
  const mission = fs.readFileSync(MISSION_MD, 'utf8');
  const arbitrationPatterns = [
    /treat the setting as current reality/i,
    /contradicts non-negotiable[^\n]*treat/i,
  ];
  for (const re of arbitrationPatterns) {
    assert.ok(
      !re.test(mission),
      `AC-ORCH-09b [root cause I]: ${MISSION_MD} instructs the agent to resolve a rule marked ` +
        `non-negotiable in AGENTS.md against a conflicting configuration value at runtime ` +
        `(matched ${re}). The mission file must state the resolved position or cite the ` +
        `authority that resolved it — never ask the agent to arbitrate.`,
    );
  }
});

test('AC-ORCH-09c: a session-start configuration conflict check is registered and inspects the non-negotiables against live settings', () => {
  // Structural contract: at least one registered SessionStart hook script must
  // implement the conflict check (references the bypassPermissions setting and
  // the AGENTS.md non-negotiables). Emission of the report for both top-level
  // and subagent sessions is asserted end-to-end by the integration suite.
  const candidates = [];

  for (const settingsPath of [SETTINGS_JSON, SETTINGS_LOCAL_JSON]) {
    const settings = readJsonIfPresent(settingsPath);
    const entries = settings && settings.hooks && settings.hooks.SessionStart;
    for (const entry of entries || []) {
      for (const h of entry.hooks || []) candidates.push({ source: settingsPath, command: h.command });
    }
  }

  const pluginHooks = helpers.loadHooksConfig(helpers.PLUGIN_ROOT);
  for (const entry of helpers.entriesForEvent(pluginHooks, 'SessionStart')) {
    for (const h of entry.hooks || []) {
      candidates.push({ source: 'agent-teams-workforce hooks.json', command: h.command });
    }
  }

  assert.ok(candidates.length > 0, 'precondition: at least one SessionStart hook is registered');

  const implementing = candidates.filter((c) => {
    const scriptPath = helpers.extractScriptPath(
      c.command.replaceAll('$CLAUDE_PROJECT_DIR', REPO),
      helpers.PLUGIN_ROOT,
    );
    if (!scriptPath || !fs.existsSync(scriptPath)) return false;
    const src = fs.readFileSync(scriptPath, 'utf8');
    return /bypassPermissions/.test(src) && /(AGENTS\.md|non-negotiable)/i.test(src);
  });

  assert.ok(
    implementing.length > 0,
    `MISSING CONTROL [root cause I, ssbd-ja5d]: no registered SessionStart hook implements a ` +
      `configuration conflict check (none references both the bypassPermissions setting and ` +
      `the AGENTS.md non-negotiables). Registered SessionStart commands: ` +
      `${JSON.stringify(candidates, null, 2)} (REQ-ORCH-09).`,
  );
});
