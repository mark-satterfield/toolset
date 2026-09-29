export const meta = {
  name: 'infra-intent',
  description:
    'Leaf mini — Infrastructure provisioning intent. The cdk-infrastructure-designer authors concrete, CDK-expressible provisioning intent for a change. Returns { ok, ready, provisioningIntent, affectedStacks }.',
  phases: [{ title: 'Provisioning intent', detail: 'cdk-infrastructure-designer authors the intent' }],
}
// settleAgent(prompt, opts): calls agent(); returns its result, or null when the agent returns nothing or fails deterministically. A transient API failure is retried with capped backoff until it clears.
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  if (TRANSIENT_ERROR_TEXT.test(text)) return 'transient'
  return 'deterministic'
}
function transientWaitMs(name, attempt) {
  const scheduled = Math.min(300000, 5000 * Math.pow(3, Math.max(0, attempt - 1)))
  let h = 2166136261
  const key = `${name}#${attempt}`
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  return Math.round(scheduled * (0.5 + 0.5 * ((h >>> 0) / 4294967296)))
}
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const name = o.label || o.agentType || 'agent'
  for (let attempt = 1; ; attempt++) {
    try {
      const out = await agent(prompt, o)
      if (!out) log(`${name}: returned nothing`)
      return out || null
    } catch (err) {
      const message = String((err && err.message) || err).slice(0, 300)
      if (failureCause(err) !== 'transient' || (!SETTLE_CAN_WAIT && attempt >= 3)) {
        log(`${name}: failed — ${message}`)
        return null
      }
      const wait = transientWaitMs(name, attempt)
      log(`${name}: transient failure on attempt ${attempt}, retrying in ${Math.round(wait / 1000)}s — ${message}`)
      if (SETTLE_CAN_WAIT) await new Promise((resolve) => setTimeout(resolve, wait))
    }
  }
}

// args: { change: { id?, title?, description?, repoPath? }, feedback?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const change = a.change || {}
const repo = change.repoPath || '(repo path not provided)'

phase('Provisioning intent')

const intent = await settleAgent(
  `Produce the concrete provisioning intent for the change below. Work within the repository at: ${repo}

${change.id ? `Change ${change.id}: ` : ''}${change.title || '(untitled change)'}
${change.description || ''}
${a.feedback ? `\nFeedback to address:\n${a.feedback}` : ''}

Deliver CDK-expressible provisioning intent:
- resources: each AWS resource to provision, with the CDK-expressible properties. Every s3.Bucket sets versioning enabled and SSE-S3 (S3_MANAGED) encryption. No public exposure and no over-broad IAM.
- stacks: the CDK stacks the resources belong to.
- crossStackRefs: cross-stack references expressed via SSM Parameter Store (never CloudFormation exports).
- affectedStacks: the stacks created or modified by this intent (names).
- rationale: why this shape, tied to the change.
Size every resource for the load the change and the project state; prefer per-request pricing over provisioned always-on capacity unless that load requires it.`,
  {
    label: 'intent:author',
    phase: 'Provisioning intent',
    agentType: 'cdk-infrastructure-designer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['resources', 'stacks', 'crossStackRefs', 'affectedStacks', 'rationale'],
      properties: {
        resources: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['logicalId', 'type', 'stack', 'properties'],
            properties: {
              logicalId: { type: 'string' },
              type: { type: 'string' },
              stack: { type: 'string' },
              properties: { type: 'string' },
            },
          },
        },
        stacks: { type: 'array', items: { type: 'string' } },
        crossStackRefs: { type: 'array', items: { type: 'string' } },
        affectedStacks: { type: 'array', items: { type: 'string' } },
        rationale: { type: 'string' },
      },
    },
  }
)

if (!intent) {
  return { ok: false, dispatchFailed: true, ready: false, reason: 'the cdk-infrastructure-designer returned nothing' }
}

return {
  ok: true,
  ready: true,
  provisioningIntent: intent,
  affectedStacks: intent.affectedStacks,
}
