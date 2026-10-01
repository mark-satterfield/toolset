export const meta = {
  name: 'deploy-mechanism',
  description:
    "Leaf mini — asks one polyrepo-steward session what a Story's repository publishes and deploys, before the Story's deploy. A repository can publish a package to CodeArtifact, deploy with CDK, both, or neither; the steward answers from its records and the repository's own declarations, and names the command that publishes the package as the repository declares it. A Taskfile is a convenience and does not decide the mechanism. The host runs what applies (publish, then `cdk deploy`) and stops a repository that does neither. Returns { ok, stage, beadId, headline, detailPath, mechanism: { repository, publishes, publishCommand, deploys, reason } }.",
  phases: [{ title: 'Ask', detail: "the polyrepo-steward rules what the Story's repository publishes and deploys" }],
}

// Retries a dispatch that failed transiently (overload, rate limit, network) with capped backoff;
// returns null on any other failure.
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
const isTransient = (err) => {
  const e = err && typeof err === 'object' ? err : {}
  const text = String(e.message || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return false
  const status = Number(e.status || e.statusCode || (e.response && e.response.status))
  return TRANSIENT_STATUS.has(status) || TRANSIENT_ERROR_TEXT.test(text)
}
async function settleAgent(prompt, opts) {
  const call = opts || {}
  const name = call.label || call.agentType || 'agent'
  for (let attempt = 1; ; attempt++) {
    try {
      const out = await agent(prompt, call)
      if (!out) log(`${name}: returned nothing`)
      return out || null
    } catch (err) {
      const message = String((err && err.message) || err)
      if (isTransient(err) && typeof setTimeout === 'function') {
        const wait = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
        log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s — ${message.slice(0, 160)}`)
        await new Promise((resolve) => setTimeout(resolve, wait))
        continue
      }
      log(`${name}: ended without a structured result — ${message.slice(0, 160)}`)
      return null
    }
  }
}

// args: { beadId?: string, story: { id, title? }, repoPath: string (the Story's repository, not its worktree) }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const story = a.story && typeof a.story === 'object' ? a.story : {}
const beadId = String(a.beadId || story.id || '').trim()
const repo = String(a.repoPath || '').trim().replace(/\/+$/, '')
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'

const handback = (ok, stage, headline, extra) => ({ ok, stage, beadId: beadId || null, headline: String(headline || ''), detailPath: null, ...(extra || {}) })

if (!beadId) return handback(false, 'input', 'no Story id supplied')
if (!repo) return handback(false, 'input', `no repository supplied for Story ${beadId}`)

phase('Ask')
const got = await settleAgent(
  `Story ${beadId}${story.title ? ` (${story.title})` : ''} is about to deploy from this repository:
${repo}

Rule, from your records of this repository and the repository's own declarations (its AGENTS.md or CLAUDE.md, its CI workflows, its package manifest, its CDK app), what it publishes and what it deploys. A repository can do one, both, or neither:
- publishes: true when the repository publishes a package to CodeArtifact. Then publishCommand is the command, as an argument list run from the repository root, that builds and publishes that package the way the repository itself declares it (for example ["task", "publish"] when its Taskfile declares that task). A Taskfile is a convenience: it does not decide whether the repository publishes, and a Taskfile task with no other declaration behind it is not evidence that the repository publishes.
- deploys: true when the repository deploys AWS infrastructure with CDK (it holds a CDK app this pipeline deploys with \`cdk deploy\`).
The project's control repository and the documentation vault publish and deploy nothing.

Read only; change nothing. Return repository (the path exactly as given above), publishes, publishCommand (an empty list when publishes is false), deploys, and reason (the records and files that decide it, in a sentence or two).`,
  {
    label: 'deploy:mechanism',
    phase: 'Ask',
    agentType: 'agent-teams-workforce:polyrepo-steward',
    effort: 'low',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['repository', 'publishes', 'publishCommand', 'deploys', 'reason'],
      properties: {
        repository: { type: 'string' },
        publishes: { type: 'boolean' },
        publishCommand: { type: 'array', items: { type: 'string' } },
        deploys: { type: 'boolean' },
        reason: { type: 'string' },
      },
    },
  }
)
if (!got) return handback(false, DISPATCH_FAILED_STAGE, `the polyrepo-steward gave no ruling on what ${repo} publishes and deploys`)

const publishCommand = (Array.isArray(got.publishCommand) ? got.publishCommand : []).map((p) => String(p)).filter((p) => p.length)
const mechanism = {
  repository: repo,
  publishes: got.publishes === true,
  publishCommand,
  deploys: got.deploys === true,
  reason: String(got.reason || '').trim(),
}
const does = [mechanism.publishes ? `publishes (${publishCommand.join(' ') || 'no command named'})` : '', mechanism.deploys ? 'deploys with CDK' : ''].filter(Boolean)
return handback(true, 'ask', `${repo}: ${does.length ? does.join(' and ') : 'publishes and deploys nothing'} — ${mechanism.reason}`.slice(0, 900), { mechanism })
