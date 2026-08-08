'use strict';

/**
 * What each guard governs, and therefore who it binds.
 *
 * Guards fall into two kinds, and the difference decides whether a subagent is
 * exempt. Until this registry existed the distinction was implicit — every guard
 * happened to be the first kind, so a test could assert "all guards exempt
 * subagents" and be right by accident. The first guard of the second kind then
 * failed that test for being correct.
 *
 *   'orchestrator-role' — a rule about WHO may act. The orchestrator sequences and
 *       delegates; it does not implement, verify its own output, or write into the
 *       channel agents read. Subagents are EXEMPT, because doing those things is
 *       exactly their job, and a role guard that blocked them would block the work.
 *
 *   'universal' — a rule about WHERE work may land or WHAT may be done, by anyone.
 *       Subagents are NOT exempt. Writing to the default branch in a main working
 *       tree is wrong whoever does it, and the failure that motivated the rule was
 *       a test-writing subagent doing precisely that. Exempting subagents there
 *       would exempt the actor that caused the problem.
 *
 * A new guard MUST be declared here. The contract test asserts that every hook
 * registered in hooks.json appears in this registry, so the choice has to be made
 * deliberately and stated, rather than inherited from whichever test happens to
 * exercise it first.
 */

const GUARD_SCOPE = {
  // Rules about who may act. Subagents exempt.
  'pre-tool-orchestrator-edit-guard.cjs': 'orchestrator-role',
  'pre-tool-self-verification-gate.cjs': 'orchestrator-role',
  'pre-tool-diagnostic-command-gate.cjs': 'orchestrator-role',
  'pre-tool-beads-write-guard.cjs': 'orchestrator-role',
  'pre-tool-workflow-dispatch-guard.cjs': 'orchestrator-role',
  'pre-tool-block-explore-for-analysis.cjs': 'orchestrator-role',
  'pre-tool-orchestrator-read-warning.cjs': 'orchestrator-role',
  'post-tool-workflow-payload-cap.cjs': 'orchestrator-role',

  // Rules about where work may land. Everyone bound.
  'pre-tool-protect-main-worktree.cjs': 'universal',

  // Not guards: they report or maintain, and block nothing.
  'session-start-config-conflict-check.cjs': 'advisory',
  'init-update-project.sh': 'advisory',
};

/** @returns {'orchestrator-role'|'universal'|'advisory'|null} */
function scopeOf(scriptFileName) {
  return GUARD_SCOPE[scriptFileName] ?? null;
}

/** True when a subagent (agent_id present) must pass this guard untouched. */
function exemptsSubagents(scriptFileName) {
  return scopeOf(scriptFileName) !== 'universal';
}

module.exports = { GUARD_SCOPE, scopeOf, exemptsSubagents };
