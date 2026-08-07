'use strict';

/**
 * ssbd-ja5d — contract tests: static assertions over configuration and
 * documentation artifacts of the agent-teams-workforce plugin. No guard
 * process is spawned here.
 *
 * Threat model entries covered:
 *   root cause (A) — AC-ORCH-01c: hooks.json must register an
 *     Edit|Write|MultiEdit|NotebookEdit PreToolUse guard.
 *   root cause (B) — AC-ORCH-02d: SKILL.md must not describe a
 *     forbidden-action guard as non-blocking.
 *   root cause (E) — AC-ORCH-05a/05b/05c: the claimed behavioral layer
 *     (rules/CLAUDE.md and its seven items) must exist as claimed.
 *   root cause (F) — AC-ORCH-06c: ROUTING.md must document pinned dispatch
 *     or the stale-snapshot failure mode with its guard.
 *
 * SUT copy: the repo source at plugins/agent-teams-workforce (canonical; the
 * cache copy under ~/.claude/plugins/cache/.../4.1.0/ is a distribution copy
 * whose divergence is REQ-ORCH-07, integration-routed). Override with
 * ATW_PLUGIN_ROOT to point these same assertions at the cache copy.
 *
 * INTENDED RED STATE: every test in this file fails against the current
 * artifacts, each for the documented configuration defect.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const helpers = require('./helpers.cjs');

const PLUGIN_ROOT = process.env.ATW_PLUGIN_ROOT || helpers.PLUGIN_ROOT;
const HOOKS_JSON = path.join(PLUGIN_ROOT, 'hooks', 'hooks.json');
const SKILL_MD = path.join(PLUGIN_ROOT, 'skills', 'orchestrator-discipline', 'SKILL.md');
const ROUTING_MD = path.join(PLUGIN_ROOT, 'workflows', 'ROUTING.md');
const RULES_CLAUDE_MD = path.join(PLUGIN_ROOT, 'rules', 'CLAUDE.md');

const EDIT_TOOLS = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'];

/**
 * The seven behavioral items SKILL.md:29-35 promises rules/CLAUDE.md provides.
 * Each maps to a detection regex applied to the rules file content.
 */
const SEVEN_PROMISED_ITEMS = [
  { item: 'Read permission/prohibition lists with a falsifiable test', re: /read\s+(permission|prohibition)/i },
  { item: 'Delegation constraint definitions (no exemption categories)', re: /delegation\s+constraint/i },
  { item: 'Investigation escalation anti-pattern documentation', re: /investigation\s+escalation/i },
  { item: 'Tool use denial protocol (HARD STOP — no workarounds)', re: /denial\s+protocol|HARD STOP/i },
  { item: 'Bash built-in tool enforcement', re: /built-?in\s+tool\s+enforcement/i },
  { item: 'Diagnostic command delegation patterns', re: /diagnostic\s+command\s+delegation/i },
  { item: 'Epistemic identity scoping for orchestrator role', re: /epistemic\s+identity/i },
];

test('AC-ORCH-01c: hooks.json registers a PreToolUse matcher covering Edit, Write, MultiEdit, and NotebookEdit, whose command resolves to an existing script', () => {
  const config = JSON.parse(fs.readFileSync(HOOKS_JSON, 'utf8'));
  const entries = (config.hooks && config.hooks.PreToolUse) || [];
  const coveringEntries = entries.filter((entry) => {
    let re;
    try {
      re = new RegExp(String(entry.matcher || ''));
    } catch {
      return false;
    }
    return EDIT_TOOLS.every((tool) => re.test(tool));
  });
  assert.ok(
    coveringEntries.length > 0,
    `MISSING CONTROL [root cause A, ssbd-ja5d]: no PreToolUse entry in ${HOOKS_JSON} matches ` +
      `all four of ${EDIT_TOOLS.join(', ')}. Registered matchers: ` +
      `[${entries.map((e) => JSON.stringify(e.matcher)).join(', ')}] (REQ-ORCH-01).`,
  );
  for (const entry of coveringEntries) {
    for (const h of entry.hooks || []) {
      const scriptPath = helpers.extractScriptPath(h.command, PLUGIN_ROOT);
      assert.ok(scriptPath, `registered command must reference a script file: ${h.command}`);
      assert.ok(
        fs.existsSync(scriptPath),
        `AC-ORCH-01c: registered guard command must resolve to an existing file on disk; ` +
          `missing: ${scriptPath}`,
      );
    }
  }
});

test('AC-ORCH-02d: SKILL.md does not describe any forbidden-action guard as non-blocking', () => {
  const skill = fs.readFileSync(SKILL_MD, 'utf8');
  // Guards covering the four forbidden orchestrator actions. The Diagnostic
  // Command Gate covers self-verification; the Source File Read Warning covers
  // context absorption. Documenting either as non-blocking contradicts
  // REQ-ORCH-02/03 (root cause B records SKILL.md:23 as deliberate design).
  const forbiddenActionGuards = ['Source File Read Warning', 'Diagnostic Command Gate'];
  for (const guardName of forbiddenActionGuards) {
    for (const block of skill.split(/\n{2,}/).filter((b) => b.includes(guardName))) {
      assert.ok(
        !/non-?blocking/i.test(block),
        `AC-ORCH-02d [root cause B]: SKILL.md describes "${guardName}" as non-blocking. ` +
          `No guard covering a forbidden orchestrator action may be advisory. ` +
          `Offending passage: ${block.trim().slice(0, 200)}`,
      );
    }
  }
});

test('AC-ORCH-05a: either rules/CLAUDE.md exists, or SKILL.md no longer asserts it is loaded — assertion-without-file is the failure', () => {
  const skill = fs.readFileSync(SKILL_MD, 'utf8');
  const asserted = /`rules\/CLAUDE\.md`[^\n]*loaded|rules\/CLAUDE\.md[^\n]*is loaded/i.test(skill);
  const exists = fs.existsSync(RULES_CLAUDE_MD);
  assert.ok(
    !asserted || exists,
    `AC-ORCH-05a [root cause E, ssbd-ja5d]: SKILL.md asserts that rules/CLAUDE.md is loaded ` +
      `into every session, but ${RULES_CLAUDE_MD} does not exist. The claimed behavioral ` +
      `layer does not exist (REQ-ORCH-05).`,
  );
});

test('AC-ORCH-05b: rules/CLAUDE.md contains each of the seven items SKILL.md promises', () => {
  const skill = fs.readFileSync(SKILL_MD, 'utf8');
  const asserted = /rules\/CLAUDE\.md/i.test(skill);
  if (!asserted) {
    // If the claim was removed, 05b is vacuously satisfied; 05a governs.
    return;
  }
  assert.ok(
    fs.existsSync(RULES_CLAUDE_MD),
    `AC-ORCH-05b [root cause E]: SKILL.md promises seven behavioral items in rules/CLAUDE.md, ` +
      `but the file is absent from the plugin (rules/ contains only separation-of-duties.md).`,
  );
  const rules = fs.readFileSync(RULES_CLAUDE_MD, 'utf8');
  const missing = SEVEN_PROMISED_ITEMS.filter((x) => !x.re.test(rules)).map((x) => x.item);
  assert.deepEqual(
    missing,
    [],
    `AC-ORCH-05b: rules/CLAUDE.md is missing promised items: ${missing.join('; ')}`,
  );
});

test('AC-ORCH-05c: every path a SKILL.md or rules document claims is loaded resolves to an existing file — zero unresolved claims', () => {
  const docFiles = [];
  const skillsDir = path.join(PLUGIN_ROOT, 'skills');
  for (const entry of fs.readdirSync(skillsDir, { withFileTypes: true })) {
    const candidate = path.join(skillsDir, entry.name, 'SKILL.md');
    if (entry.isDirectory() && fs.existsSync(candidate)) docFiles.push(candidate);
  }
  const rulesDir = path.join(PLUGIN_ROOT, 'rules');
  if (fs.existsSync(rulesDir)) {
    for (const f of fs.readdirSync(rulesDir)) {
      if (f.endsWith('.md')) docFiles.push(path.join(rulesDir, f));
    }
  }

  const unresolved = [];
  for (const doc of docFiles) {
    const content = fs.readFileSync(doc, 'utf8');
    for (const line of content.split('\n')) {
      if (!/\bloaded\b/i.test(line)) continue;
      for (const m of line.matchAll(/`([^`]+)`/g)) {
        const claimed = m[1];
        if (!claimed.includes('/') && !claimed.endsWith('.md')) continue;
        const resolved = path.isAbsolute(claimed) ? claimed : path.join(PLUGIN_ROOT, claimed);
        if (!fs.existsSync(resolved)) {
          unresolved.push({ doc: path.relative(PLUGIN_ROOT, doc), claimed, resolved });
        }
      }
    }
  }
  assert.deepEqual(
    unresolved,
    [],
    `AC-ORCH-05c [root cause E]: documents claim files are loaded that do not resolve on disk: ` +
      JSON.stringify(unresolved, null, 2),
  );
});

test('AC-ORCH-06c: ROUTING.md documents digest/path-pinned dispatch, or documents the stale-snapshot failure mode and its detecting guard', () => {
  const routing = fs.readFileSync(ROUTING_MD, 'utf8');
  const pinnedDispatch = /scriptPath|sha-?256|digest/i.test(routing);
  const staleness = /stale/i.test(routing) && /snapshot/i.test(routing);
  assert.ok(
    pinnedDispatch || staleness,
    `AC-ORCH-06c [root cause F, ssbd-ja5d]: ROUTING.md documents only name-based dispatch ` +
      `(Workflow({ name: ... }) at lines 88 and 101) with no staleness treatment. It must ` +
      `either document a dispatch form pinning the resolved script by path or digest, or ` +
      `explicitly document the stale-snapshot failure mode together with the guard that ` +
      `detects it (REQ-ORCH-06).`,
  );
});
