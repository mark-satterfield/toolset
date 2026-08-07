#!/usr/bin/env node
'use strict';

/**
 * SessionStart hook — REQ-ORCH-09 (ssbd-ja5d, root cause I).
 *
 * A rule recorded as non-negotiable in AGENTS.md and a setting that contradicts
 * it can both be in force at once, and nothing notices. The session then starts
 * with an unresolved conflict, and the first agent to encounter it is left to
 * arbitrate between a policy document and a config value at runtime — a
 * decision no agent has the standing to make.
 *
 * This check runs before that can happen. It compares the live permission
 * settings against the non-negotiable rules and reports any conflict, naming
 * both sides and the resolution the human must make. It reports; it does not
 * resolve, and it does not fail the session.
 *
 * A conflict is treated as resolved only by an explicit dated exception in
 * AGENTS.md that names the setting.
 */

const fs = require('node:fs');
const path = require('node:path');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

/** Settings keys whose value can contradict a recorded non-negotiable. */
const PERMISSIVE_MODES = new Set(['bypassPermissions', 'acceptEdits', 'dontAsk']);

/** Reads all of stdin synchronously; returns '' when unreadable. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

/** Parses JSON from a path, or returns null when absent or malformed. */
function readJsonIfPresent(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

/** Reads a text file, or returns '' when absent. */
function readTextIfPresent(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return '';
  }
}

/** Resolves the permission default mode a settings document sets, if any. */
function defaultModeOf(settings) {
  if (!settings) return null;
  return settings.defaultMode ?? settings.permissions?.defaultMode ?? null;
}

/**
 * Extracts lines from AGENTS.md that record a non-negotiable rule. A rule is
 * any line under a "non-negotiable" heading, or any line naming the term
 * directly.
 */
function nonNegotiableLines(agentsMd) {
  if (!agentsMd) return [];
  const lines = agentsMd.split('\n');
  const out = [];
  let inSection = false;

  for (const line of lines) {
    if (/^#{1,6}\s/.test(line)) {
      inSection = /non-?negotiable/i.test(line);
      continue;
    }
    if (inSection && line.trim()) out.push(line.trim());
    else if (/non-?negotiable/i.test(line)) out.push(line.trim());
  }
  return out;
}

/**
 * True when AGENTS.md records a dated exception naming the given setting —
 * the only way a conflict counts as resolved.
 */
function hasDatedException(agentsMd, settingName) {
  if (!agentsMd) return false;
  for (const line of agentsMd.split('\n')) {
    if (!line.includes(settingName)) continue;
    if (!/exception|waiver|approved/i.test(line)) continue;
    if (/\b\d{4}-\d{2}-\d{2}\b/.test(line)) return true;
  }
  return false;
}

/** Emits a SessionStart additionalContext payload and exits 0. */
function emit(context) {
  if (!context) {
    process.stdout.write(JSON.stringify({}));
    process.exit(0);
  }
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: context },
    }),
  );
  process.exit(0);
}

function main() {
  const raw = readStdin();
  let event = {};
  if (raw.trim()) {
    try {
      event = JSON.parse(raw);
    } catch {
      event = {};
    }
  }

  // Out of scope in the monorepo that builds this plugin.
  if (!guardsApplyHere(event)) {
    emit(null);
  }

  const projectDir = process.env.CLAUDE_PROJECT_DIR || event.cwd || process.cwd();
  const agentsMd = readTextIfPresent(path.join(projectDir, 'AGENTS.md'));
  const rules = nonNegotiableLines(agentsMd);

  // No recorded non-negotiables means nothing to contradict.
  if (rules.length === 0) {
    emit(null);
  }

  const conflicts = [];
  for (const name of ['settings.json', 'settings.local.json']) {
    const settingsPath = path.join(projectDir, '.claude', name);
    const settings = readJsonIfPresent(settingsPath);
    const mode = defaultModeOf(settings);
    if (!mode || !PERMISSIVE_MODES.has(mode)) continue;

    // A non-negotiable that prohibits this mode, by name or by description.
    const prohibiting = rules.filter(
      (r) => r.includes(mode) || /permission|approval|confirm|bypass/i.test(r),
    );
    if (prohibiting.length === 0) continue;
    if (hasDatedException(agentsMd, mode)) continue;

    conflicts.push({ settingsPath, mode, prohibiting });
  }

  if (conflicts.length === 0) {
    emit(null);
  }

  const lines = ['<configuration-conflict-report>', 'UNRESOLVED CONFIGURATION CONFLICT AT SESSION START.', ''];
  for (const c of conflicts) {
    lines.push(
      `Setting:  defaultMode = ${c.mode}`,
      `File:     ${c.settingsPath}`,
      'Contradicts these non-negotiable rules in AGENTS.md:',
      ...c.prohibiting.slice(0, 3).map((r) => `  ${r}`),
      '',
    );
  }
  lines.push(
    'Both the prohibition and the setting are in force. AGENTS.md records no',
    'dated exception naming the setting, so the conflict is unresolved.',
    '',
    'No agent has the standing to arbitrate this. Do not resolve it in session,',
    'and do not treat either side as the settled position because it is more',
    'convenient. Raise it with the human, who resolves it by either removing the',
    'setting or recording a dated exception in AGENTS.md that names it.',
    '</configuration-conflict-report>',
  );

  emit(lines.join('\n'));
}

main();
