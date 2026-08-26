'use strict';

/**
 * Where the expensive model is allowed to go.
 *
 * Fable consumes tokens roughly twice as fast as the alternatives, and the token
 * budget is the binding constraint on how much work a run can do. So the axis that
 * matters is not "planning versus implementation" — it is VOLUME against
 * REVERSIBILITY.
 *
 * Implementers and test writers are the highest-volume roles in the workforce (one
 * integration-test writer was measured at 124.5k tokens in a single Red phase) and
 * they are also the most constrained: a failing test and a spec already fix what
 * they must produce, and a mistake costs one re-run. That is the worst possible
 * place for a 2x model, and 38 of the 66 Fable agents were sitting there.
 *
 * Deciders and gates are the opposite. They run a handful of times, emit short
 * verdicts, and nothing downstream catches their mistakes — an architecture ruling
 * is consolidated into the SAD and every later spec builds on it.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const AGENTS = path.resolve(__dirname, '..', '..', 'agents');
const files = fs.readdirSync(AGENTS).filter((f) => f.endsWith('.md') && f !== 'README.md');

/** model declared in an agent's frontmatter, or null. */
function modelOf(file) {
  const m = /^model:\s*(\w+)\s*$/m.exec(fs.readFileSync(path.join(AGENTS, file), 'utf8'));
  return m ? m[1] : null;
}

const EXPENSIVE = 'fable';

/** Roles whose output volume scales with the size of the change. */
const VOLUME = /implementer|test-writer|test-generator|xcuitest|espresso|optimizer|refactoring-specialist|linting-enforcer|stack-author|smoke-test-author|benchmark-writer|diagram-author/;

/** Roles that rule, and whose rulings nothing downstream re-examines. */
const IRREVERSIBLE = [
  'architecture-decider',
  'phase-gate-enforcer',
  'constitutional-agent',
  'adversarial-critique-adjudicator',
  'advantage-evaluator',
  'spec-decider',
  'trd-decider',
  'test-strategy-decider',
  'deployment-strategy-decider',
];

test('every agent declares a model', () => {
  const missing = files.filter((f) => !modelOf(f));
  assert.deepEqual(missing, [], `agents without a model inherit the session default unpredictably: ${missing.join(', ')}`);
});

for (const file of files.filter((f) => VOLUME.test(f))) {
  test(`${file.replace('.md', '')}: high-volume role is not on the 2x model`, () => {
    assert.notEqual(
      modelOf(file),
      EXPENSIVE,
      `this role's output scales with the change and its work is already fixed by a spec or a ` +
        `failing test. On a 2x model it is the largest avoidable cost in a run, and a mistake ` +
        `here costs one re-run — put the budget where mistakes are expensive instead.`,
    );
  });
}

for (const name of IRREVERSIBLE) {
  test(`${name}: irreversible ruling is on the strongest model`, () => {
    assert.equal(
      modelOf(`${name}.md`),
      'opus',
      `nothing downstream re-examines this agent's ruling — an architecture decision is ` +
        `consolidated into the SAD and every later spec builds on it. It runs rarely and emits ` +
        `little, so the strongest model costs almost nothing here.`,
    );
  });
}

test('makers and their checkers do not share a model', () => {
  // Independent verifiers found four real defects in work whose own tests were
  // green. A checker running the same model as its maker shares its blind spots
  // and agrees for the same wrong reason.
  const PAIRS = [
    ['task-decomposer', 'beads-format-validator'],
    ['trd-author', 'trd-validator'],
    ['code-refactoring-specialist', 'code-correctness-reviewer'],
    ['wsjf-scorer', 'wsjf-scoring-reviewer'],
    ['prd-writer', 'prd-alignment-verifier'],
    // The workspace step: one agent CREATES the worktree, a second and separately
    // dispatched one reports what git says about it. On the same model the checker
    // shares the maker's blind spots and corroborates the same wrong answer, which
    // is the one failure this second dispatch exists to prevent.
    ['github-actions-pipeline-implementer', 'worktree-independent-verifier'],
  ];
  const same = PAIRS.filter(([m, c]) => modelOf(`${m}.md`) && modelOf(`${m}.md`) === modelOf(`${c}.md`))
    .map(([m, c]) => `${m}/${c} both on ${modelOf(`${m}.md`)}`);
  assert.deepEqual(same, [], `maker and checker share a model: ${same.join('; ')}`);
});
