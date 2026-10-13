// ── STEP JOURNAL: the steps of the bead this workflow works on, and the changes it reports ──
//
// A build or deploy workflow runs the steps the bead's step journal lists. It reads the journal
// once, at its start, through the checked relay (bin/atw-step-journal read), keeps a copy in
// memory, and begins at the first step that is not done. It cannot write a file, so it reports
// each change (step started, step done with its artifacts and the steps its result adds, step
// failed with its cause, child steps planned) as one log line the driver applies to the journal
// file with orchestrator/core/journal_lines.py. The copy here changes exactly as the file does:
// it follows step_journal.next_step, start_step and journal_changes.apply_completion.
//
// The line format and the artifact that hands a planned step its parameters are defined in
// skills/pipeline-contracts/schemas/step-journal.schema.json; the step kinds, what each records
// and adds, and the up-front plans in skills/pipeline-contracts/schemas/pipeline-steps.json. Both
// are inlined below by scripts/shared-blocks.mjs. Never restate any part of them in a workflow.
const stepJournal = (() => {
  const WIRE = /* STEP_JOURNAL_WIRE */ {}
  const PIPELINES = (/* PIPELINE_STEPS */ {}).pipelines || {}
  if (!WIRE.changePrefix || !WIRE.changePartPrefix || !WIRE.changeChunk || !WIRE.plannedForPrefix || !PIPELINES.build || !PIPELINES.deploy) {
    throw new Error('shared block step-journal: the step journal contract was not inlined (run node scripts/shared-blocks.mjs --write)')
  }
  const STEP_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
  const FAILURE_EVIDENCE_CHARS = 4000

  /** An artifact that is a file a step produced. */
  const file = (name, path) => ({ name, kind: 'file', path: String(path) })
  /** An artifact that is a directory a step produced. */
  const directory = (name, path) => ({ name, kind: 'directory', path: String(path) })
  /** An artifact that is a value a step produced; an undefined value is recorded as null. */
  const value = (name, held) => ({ name, kind: 'value', value: held === undefined ? null : held })

  /** Every step of `steps` in walk order: each step before its child steps, siblings in order. */
  const walk = (steps, out = []) => {
    for (const step of steps) {
      out.push(step)
      walk(step.steps, out)
    }
    return out
  }

  /** The copy of one journal step: `key` is its id, or the ref of a step this run added. */
  const copyStep = (raw, params) => {
    const id = String(raw.id || '')
    return {
      key: id,
      id,
      kind: String(raw.script || ''),
      description: String(raw.description || ''),
      purpose: String(raw.purpose || ''),
      status: String(raw.status || 'planned'),
      artifacts: Array.isArray(raw.artifacts) ? raw.artifacts.map((held) => ({ ...held })) : [],
      params: params.get(id) || {},
      steps: (Array.isArray(raw.steps) ? raw.steps : []).map((child) => copyStep(child, params)),
    }
  }

  /** `text` with each {name} replaced by the text parameter of that name. */
  const filled = (text, params, kind) =>
    String(text).replace(/\{([A-Za-z][A-Za-z0-9]*)\}/g, (_match, name) => {
      const held = params ? params[name] : undefined
      if (typeof held !== 'string' || !held) throw new Error(`a step of kind ${kind} needs the text parameter ${name} for its description`)
      return held
    })

  /**
   * Opens the journal a workflow was handed. `journal` is the document atw-step-journal read
   * printed, `run` the name the driver gave this run, `runner` the name of this workflow script as
   * pipeline-steps.json names it, and `under` the id of the step whose child steps this workflow
   * runs (absent for a workflow that runs the bead's outermost steps).
   */
  function open({ journal, run, runner, under = null }) {
    if (!journal || typeof journal !== 'object' || !Array.isArray(journal.steps)) throw new Error('stepJournal.open: no journal was read')
    if (typeof run !== 'string' || !run) throw new Error('stepJournal.open: no run name was supplied')
    const pipeline = PIPELINES[journal.pipeline]
    if (!pipeline) throw new Error(`stepJournal.open: the journal lists ${journal.pipeline} steps, which pipeline-steps.json does not define`)
    const params = new Map()
    for (const raw of walk(journal.steps)) {
      for (const held of Array.isArray(raw.artifacts) ? raw.artifacts : []) {
        const name = String(held.name || '')
        const planned = name.startsWith(WIRE.plannedForPrefix) ? name.slice(WIRE.plannedForPrefix.length) : ''
        if (held.kind === 'value' && STEP_ID.test(planned) && held.value && typeof held.value === 'object') params.set(planned, held.value)
      }
    }
    const roots = journal.steps.map((raw) => copyStep(raw, params))
    const parent = under ? walk(roots).find((step) => step.id === under) || null : null
    if (under && !parent) throw new Error(`stepJournal.open: the journal of ${journal.bead} holds no step ${under}`)
    let changes = 0

    /** Writes one change on the log, as one line or as part lines when it is longer than the chunk. */
    function report(change) {
      changes += 1
      const body = JSON.stringify({ run, n: changes, ...change })
      if (body.length <= WIRE.changeChunk) {
        log(`${WIRE.changePrefix}${body}`)
        return
      }
      const parts = []
      for (let at = 0; at < body.length; ) {
        let end = Math.min(at + WIRE.changeChunk, body.length)
        const last = body.charCodeAt(end - 1)
        if (end < body.length && last >= 0xd800 && last <= 0xdbff) end -= 1
        parts.push(body.slice(at, end))
        at = end
      }
      parts.forEach((part, index) => log(`${WIRE.changePartPrefix}${changes} ${index + 1}/${parts.length} ${part}`))
    }

    const everyStep = () => walk(roots)
    const scope = () => (parent ? parent.steps : roots)
    const kindOf = (key) => {
      const kind = pipeline.kinds[key]
      if (!kind) throw new Error(`pipeline-steps.json defines no ${journal.pipeline} step kind ${key}`)
      return kind
    }
    /** The steps of this workflow's scope before `step` in walk order; every step of the scope when `step` is not one of them. */
    const before = (step) => {
      const all = walk(scope())
      const at = all.indexOf(step)
      return at < 0 ? all : all.slice(0, at)
    }
    /** The step that directly contains `step`, or null for an outermost step. */
    const containerOf = (step) => everyStep().find((candidate) => candidate.steps.includes(step)) || null
    const siblingsOf = (step) => {
      const container = containerOf(step)
      return container ? container.steps : roots
    }
    const heldBy = (step, name) => step.artifacts.filter((held) => held.name === name).map((held) => (held.kind === 'value' ? held.value : held.path))

    /** What a planned step is in the copy, and the plan the driver adds to the journal file. */
    const planned = (adder, entry, ordinal) => {
      const kind = kindOf(entry.kind)
      const handed = entry.params && typeof entry.params === 'object' ? entry.params : null
      const ref = `${adder.key}.${ordinal}`
      const description = filled(kind.description, handed, entry.kind)
      const purpose = typeof entry.purpose === 'string' && entry.purpose.trim() ? entry.purpose.trim() : kind.purpose
      return {
        step: { key: ref, id: '', kind: entry.kind, description, purpose, status: 'planned', artifacts: [], params: handed || {}, steps: [] },
        wire: { plan: { ref, description, purpose, script: entry.kind }, ...(handed ? { params: handed } : {}) },
      }
    }

    return {
      bead: String(journal.bead || ''),
      pipeline: String(journal.pipeline || ''),
      kinds: pipeline.kinds,
      /** The kinds of the child steps pipeline-steps.json plans under a step of `kind` when it first runs. */
      innerPlan: (kind) => (pipeline.inner[kind] || []).map((key) => ({ kind: key })),
      /** The step this workflow runs child steps under, or null. */
      parent: () => parent,
      /** Every step of the journal in walk order. */
      steps: everyStep,
      /** The step this workflow does next: the first step of its scope that has no child steps and is not done. */
      next: () => walk(scope()).find((step) => !step.steps.length && step.status !== 'done') || null,
      /** `step` and the planned steps of its kind that follow it directly, when the kind's steps run together. */
      together(step) {
        if (kindOf(step.kind).together !== true) return [step]
        const siblings = siblingsOf(step)
        const group = [step]
        for (const sibling of siblings.slice(siblings.indexOf(step) + 1)) {
          if (sibling.kind !== step.kind || sibling.steps.length || sibling.status === 'done') break
          group.push(sibling)
        }
        return group
      },
      // The three lookups below read the steps of this workflow's scope: the bead's steps, or the child
      // steps of the step it was handed. A null `step` reads every step of the scope.
      /** The newest artifact named `name` a done step before `step` holds: its value or its path; `fallback` when none holds one. */
      latest(name, step, fallback = null) {
        const earlier = before(step).filter((candidate) => candidate.status === 'done')
        for (let at = earlier.length - 1; at >= 0; at -= 1) {
          const found = heldBy(earlier[at], name)
          if (found.length) return found[found.length - 1]
        }
        return fallback
      },
      /** Every artifact named `name` the done steps before `step` hold, oldest first; with `since`, only those of steps after it. */
      every(name, step, since = null) {
        const earlier = before(step)
        const from = since ? earlier.indexOf(since) + 1 : 0
        return earlier.slice(from).filter((candidate) => candidate.status === 'done').flatMap((candidate) => heldBy(candidate, name))
      },
      /** The done steps before `step` whose kind is one of `kinds`, oldest first; with `since`, only those after it. */
      earlier(kinds, step, since = null) {
        const all = before(step)
        const from = since ? all.indexOf(since) + 1 : 0
        return all.slice(from).filter((candidate) => candidate.status === 'done' && kinds.includes(candidate.kind))
      },
      /** A directory name for the files of `step`, unique in the journal. */
      folder: (step) => step.key.replace(/^([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/, '$1').replace(/[^A-Za-z0-9._-]+/g, '-'),
      /** Marks a step running: it starts from its beginning, so the artifacts of an unfinished run of it are dropped. */
      start(step) {
        step.status = 'running'
        step.artifacts = []
        report({ op: 'start', step: step.key })
      },
      /** Records a step's artifacts, adds the steps its result calls for right after it, and marks it done. */
      done(step, artifacts = [], add = []) {
        const added = add.map((entry, index) => planned(step, entry, index + 1))
        const siblings = siblingsOf(step)
        siblings.splice(siblings.indexOf(step) + 1, 0, ...added.map((entry) => entry.step))
        step.artifacts = [...artifacts]
        step.status = 'done'
        report({ op: 'done', step: step.key, ...(artifacts.length ? { artifacts } : {}), ...(added.length ? { add: added.map((entry) => entry.wire) } : {}) })
        return added.map((entry) => entry.step)
      },
      /** Marks a step failed with its cause: { stage, message, evidence? }. */
      fail(step, cause) {
        const stage = String((cause && cause.stage) || step.kind)
        const message = String((cause && cause.message) || 'the step failed').slice(0, FAILURE_EVIDENCE_CHARS)
        const evidence = cause && cause.evidence ? String(cause.evidence).slice(0, FAILURE_EVIDENCE_CHARS) : ''
        step.status = 'failed'
        report({ op: 'fail', step: step.key, failure: JSON.stringify({ stage, message, ...(evidence ? { evidence } : {}) }) })
      },
      /** Plans child steps under the running step this workflow was handed, in the order they run. */
      planUnder(add) {
        if (!parent) throw new Error('stepJournal: this workflow was handed no step to plan child steps under')
        const added = add.map((entry, index) => planned(parent, entry, parent.steps.length + index + 1))
        parent.steps.push(...added.map((entry) => entry.step))
        report({ op: 'add', step: parent.key, add: added.map((entry) => entry.wire) })
        return added.map((entry) => entry.step)
      },
      /**
       * Runs the steps of this workflow's scope from the next one until none is left or one fails.
       * `table` maps a step kind to the function that runs a step of it: `async (step) => ({ artifacts, add })`
       * when the step is done (`add` lists { kind, params?, purpose? } for the steps its result calls for), or
       * `{ fail: { stage, message, evidence?, ...more } }` when it failed. `interrupted()` returns the
       * interruption of this run's dispatches, or null. Returns { ok: true }, or
       * { ok: false, step, fail } for the step that failed.
       */
      async run(table, interrupted = () => null) {
        const mine = Object.keys(pipeline.kinds).filter((key) => pipeline.kinds[key].runBy === runner && (pipeline.kinds[key].within || null) === (parent ? parent.kind : null))
        const missing = mine.filter((key) => typeof table[key] !== 'function')
        if (missing.length) throw new Error(`${runner} has no function for the step kinds ${missing.join(', ')}`)
        const attempt = async (step) => {
          let out = null
          try {
            const perform = table[step.kind]
            out = typeof perform === 'function' ? await perform(step) : { fail: { stage: step.kind, message: `${runner} runs no step of kind ${step.kind || '(none)'}` } }
          } catch (err) {
            out = { fail: { stage: step.kind, message: `the step threw: ${String((err && err.message) || err).slice(0, 400)}` } }
          }
          const stop = interrupted()
          if (stop) return { fail: { stage: stop.stage, message: stop.message, interrupted: true } }
          return out && typeof out === 'object' ? out : { fail: { stage: step.kind, message: 'the step returned nothing' } }
        }
        for (;;) {
          const first = this.next()
          if (!first) return { ok: true }
          const group = this.together(first)
          for (const step of group) this.start(step)
          const outcomes = group.length === 1 ? [await attempt(group[0])] : await parallel(group.map((step) => () => attempt(step)))
          let failed = null
          group.forEach((step, index) => {
            const out = outcomes[index] || { fail: { stage: step.kind, message: 'the step returned nothing' } }
            if (out.fail) {
              this.fail(step, out.fail)
              failed = failed || { ok: false, step, fail: out.fail }
            } else {
              this.done(step, Array.isArray(out.artifacts) ? out.artifacts : [], Array.isArray(out.add) ? out.add : [])
            }
          })
          if (failed) return failed
        }
      },
    }
  }

  /**
   * Reads the journal file through the checked relay: one command, bin/atw-step-journal read.
   * Returns { journal } or { error, noResult }.
   */
  async function read(dispatch, { runner, pluginRoot, path, relayFile, phase }) {
    const result = await relayKit.run(dispatch, { label: 'journal:read', phase, runner, argv: [`${pluginRoot}/bin/atw-step-journal`, 'read', '--journal', path], file: relayFile })
    if (!result.ok) return { error: result.error, noResult: !!result.noResult }
    if (result.exitCode !== 0 || !result.json || !result.json.journal) return { error: `atw-step-journal read exited ${result.exitCode}; its output is in ${relayFile}` }
    return { journal: result.json.journal }
  }

  return { file, directory, value, open, read, pipelines: PIPELINES }
})()
