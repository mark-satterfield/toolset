// spec-authoring emits the Story that pairs with the Spec.
//
// Nothing executed this mini before: the hierarchy tests stub it and assert against
// a hand-built Story object, which is exactly how two blocking defects survived —
// the script ended with `await main(...)` and returned undefined to every caller,
// and it passed an object map to parallel(), which the runner iterates as an empty
// list. Both are invisible to a stub and fatal in a run.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const specAuthoring = path.resolve(HERE, '..', '..', 'workflows', 'spec-authoring.js')

/** Every maker returns a plausible draft; every checker approves. */
function agentImpl(call) {
  const label = String(call.label || '')
  if (label === 'author:story-bead') {
    return { title: 'Story title', description: 'Story description', outOfRepoFindings: [] }
  }
  if (label.startsWith('author:')) return { summary: 'drafted', content: 'x' }
  if (label.startsWith('review:') || label.includes('check')) {
    return { approved: true, accepted: true, findings: [], issues: [] }
  }
  if (label.startsWith('decide') || label.includes('decider')) return { ruling: 'accept', rationale: 'r' }
  return { approved: true, accepted: true, findings: [] }
}

async function run(args) {
  return runWorkflowScript(specAuthoring, { args, agentImpl, workflowImpl: () => null })
}

test('the mini returns a result at all — not undefined', async () => {
  const { result } = await run({
    spec: { id: 'SPEC-1', title: 'Spec One', summary: 's', repoPath: '/repo-a' },
    repoPath: '/repo-a',
    epic: { key: 'E1', title: 'The Epic' },
    storyKey: 'S1',
  })
  assert.ok(
    result && typeof result === 'object',
    'the runner takes the script completion value as the result; returning undefined makes every caller see nothing',
  )
})

test('it emits exactly one Story, paired with the Spec and scoped to one repo', async () => {
  const { result } = await run({
    spec: { id: 'SPEC-1', title: 'Spec One', summary: 's', repoPath: '/repo-a' },
    repoPath: '/repo-a',
    epic: { key: 'E1', title: 'The Epic' },
    storyKey: 'S1',
  })

  const { story } = result
  assert.ok(story, 'a Spec and its Story are created together — the Story must be emitted here')
  assert.equal(story.type, 'story')
  assert.equal(story.key, 'S1')
  assert.equal(story.repoPath, '/repo-a', 'a Story is scoped to a single repo')
  assert.equal(story.parentEpicKey, 'E1', 'the Story hangs under the Epic it was given')
  assert.ok(story.title, 'the Story carries authored prose, not a placeholder')
})

test('the caller-supplied storyKey is honoured — siblings must not collide', async () => {
  const { result } = await run({
    spec: { id: 'SPEC-1', title: 'Spec One', summary: 's', repoPath: '/repo-b' },
    repoPath: '/repo-b',
    epic: { key: 'E1' },
    storyKey: 'S7',
  })
  assert.equal(result.story.key, 'S7')
})

test('the six spec artifacts are actually authored, not silently empty', async () => {
  const { result, calls } = await run({
    spec: { id: 'SPEC-1', title: 'Spec One', summary: 's', repoPath: '/repo-a' },
    repoPath: '/repo-a',
    epic: { key: 'E1' },
    storyKey: 'S1',
  })

  // parallel() over an object map dispatches nothing; over an array it dispatches six.
  const authorCalls = calls.filter((c) => c.kind === 'agent' && String(c.label).startsWith('author:'))
  assert.ok(
    authorCalls.length >= 6,
    `expected the six spec makers to run, saw ${authorCalls.length}: [${authorCalls.map((c) => c.label).join(', ')}]`,
  )
  assert.ok(result.errorSpec, 'errorSpec must survive to the return')
  assert.ok(result.definitionOfDone, 'definitionOfDone must survive to the return')
})

test('a Story is never emitted without a repo', async () => {
  const { result } = await run({
    spec: { id: 'SPEC-1', title: 'Spec One', summary: 's' },
    epic: { key: 'E1' },
    storyKey: 'S1',
  })
  // Either the mini refuses, or it emits a Story with a real repo. What it must not
  // do is emit a repo-less Story that reads as valid downstream.
  if (result && result.story) {
    assert.ok(
      result.story.repoPath,
      'a Story with a null repo contradicts "scoped to a single repo" yet would be written as if valid',
    )
  } else {
    assert.equal(result.ok, false, 'refusing is fine; emitting a repo-less Story is not')
  }
})
