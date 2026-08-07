#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — roster dispatch enforcement.
 *
 * (Filename retained for the hooks.json registration and the test harness's
 * HOOK_SCRIPTS.blockExplore anchor; the scope is now every generic agent type,
 * not Explore alone.)
 *
 * A generic agent carries no role boundary. A roster agent's system prompt
 * carries its charter — "decides only, never analyzes", "reports findings,
 * never fixes", separation of duties — and a generic agent carries none of it.
 * So work routed to general-purpose comes back looking like a completed
 * workflow step while every maker/checker/decider constraint silently lapsed.
 * That failure is quieter than a missing tool, which at least errors.
 *
 * This guard denies generic dispatch of domain work and names the roster agent
 * or workflow that owns it.
 *
 * Decision order:
 *   1. unparseable input                      -> exit 0
 *   2. subagent session                       -> exit 0
 *   3. non-Agent/Task tool                    -> exit 0
 *   4. roster agent (namespaced)              -> exit 0
 *   5. generic type + no domain/analysis hit  -> exit 0
 *   6. generic type + domain/analysis hit     -> exit 2
 */

const fs = require('node:fs');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

/**
 * Agent types that carry no roster charter. Anything lacking a plugin
 * namespace (`plugin:agent`) is treated as generic too.
 */
const GENERIC_TYPES = new Set([
  'Explore',
  'Plan',
  'general-purpose',
  'claude',
  'fork',
]);

/**
 * Domain routing table. The first entry whose pattern matches the task text
 * supplies the remediation. Ordered most-specific first so that, e.g., an
 * architecture task is not captured by the broader review/analysis entry.
 */
const DOMAIN_ROUTES = [
  {
    domain: 'Architecture',
    pattern:
      /\b(architect|architecture|architectural|adr|trade-?off|design decision|system design|bounded context|c4|arc42|sad)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/architecture.js" }) — the full decide-and-record path',
      'agent-teams-workforce:architecture-decider — rules on options (never analyzes)',
      'agent-teams-workforce:integration-pattern-architect — integration options and tradeoffs',
      'agent-teams-workforce:security-architecture-designer — threat model, IAM, encryption',
    ],
  },
  {
    domain: 'Requirements / PRD',
    pattern: /\b(prd|product requirement|persona|okr|stakeholder|business objective|brd)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/prd-creation.js" })',
      'Workflow({ scriptPath: ".../workflows/prd-validation.js" })',
      'agent-teams-workforce:requirements-clarifier — ambiguity and conflict findings',
    ],
  },
  {
    domain: 'Technical requirements (TRD)',
    pattern: /\b(trd|technical requirement|nfr|non-functional)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/trd-authoring.js" })',
      'agent-teams-workforce:trd-author / agent-teams-workforce:trd-validator',
    ],
  },
  {
    domain: 'Specification',
    pattern:
      /\b(spec|specification|openapi|graphql schema|api contract|acceptance criteri|definition of done|data model)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/spec-authoring.js" })',
      'agent-teams-workforce:api-specification-author',
      'agent-teams-workforce:acceptance-criteria-writer',
    ],
  },
  {
    domain: 'Task decomposition',
    pattern: /\b(decompos|task breakdown|backlog|wsjf|story|stories|dependency dag|beads?)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/task-decomposition.js" })',
      'agent-teams-workforce:task-decomposer / agent-teams-workforce:wsjf-scorer',
    ],
  },
  {
    domain: 'Bug diagnosis',
    pattern: /\b(bug|defect|root cause|repro|reproduce|regression|triage)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/bug-triage.js" })',
      'agent-teams-workforce:root-cause-analyst — classifies where a failure escalates',
    ],
  },
  {
    domain: 'Test design',
    pattern: /\b(test plan|test strateg|test design|coverage|tdd|failing test|red phase)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/tdd-red.js" })',
      'agent-teams-workforce:test-design-lead / agent-teams-workforce:test-coverage-gap-reviewer',
    ],
  },
  {
    domain: 'Refactor / performance',
    pattern: /\b(refactor|complexity|duplication|optimi[sz]|performance|cold start|bundle size)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/tdd-refactor.js" })',
      'agent-teams-workforce:complexity-analyzer — advises, read-only',
    ],
  },
  {
    domain: 'Security / adversarial',
    pattern:
      /\b(security|vulnerab|injection|auth bypass|privilege escalation|threat|cve|exploit|pen ?test)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/adversarial.js" })',
      'agent-teams-workforce:infrastructure-security-scanner',
      'agent-teams-workforce:dependency-cve-auditor',
    ],
  },
  {
    domain: 'Deployment',
    pattern: /\b(deploy|rollout|runbook|slo|error budget|cdk|pipeline|finops|drift)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/deploy.js" })',
      'agent-teams-workforce:deployment-strategy-decider',
    ],
  },
  {
    domain: 'Integration testing',
    pattern: /\b(integration test|e2e|end-to-end|contract test|event flow|smoke test)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/integration.js" })',
      'agent-teams-workforce:integration-testing-lead',
    ],
  },
  {
    domain: 'Documentation',
    pattern: /\b(readme|changelog|user guide|api doc|documentation)\b/i,
    route: [
      'Workflow({ scriptPath: ".../workflows/documentation.js" })',
      'agent-teams-workforce:documentation-lead',
    ],
  },
];

/**
 * General reasoning verbs. A generic agent asked to do any of these is doing
 * judgement work that some roster agent is chartered for, even when no domain
 * route matches.
 */
const ANALYSIS_KEYWORDS = [
  'analyze', 'analysis', 'analyse',
  'assess', 'assessment',
  'audit', 'review', 'evaluate', 'evaluation',
  'compare', 'comparison', 'critique',
  'design', 'recommend', 'recommendation',
  'propose', 'proposal', 'improve', 'improvement',
  'plan', 'planning',
  'diagnose', 'diagnosis',
  'reason about', 'reasoning',
  'judgement', 'judgment', 'opinion',
  'best approach', 'best way', 'how should', 'should i', 'what should',
  'decide', 'decision',
];

const KEYWORD_PATTERN = new RegExp(
  `\\b(${ANALYSIS_KEYWORDS.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\b`,
  'i',
);

/**
 * Strips quoted substrings so keywords used as literal search targets
 * (grep for 'review') do not trigger a match.
 */
function stripQuotedSpans(text) {
  return text
    .replace(/`[^`]*`/g, ' ')
    .replace(/'[^']*'/g, ' ')
    .replace(/"[^"]*"/g, ' ');
}

/** Reads all of stdin synchronously. */
function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

function main() {
  const raw = readStdin();
  if (!raw.trim()) {
    process.exit(0);
  }

  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  // Subagents dispatch freely — this guard governs the orchestrator.
  if (event.agent_id) {
    process.exit(0);
  }

  // Out of scope in the monorepo that builds this plugin.
  if (!guardsApplyHere(event)) {
    process.exit(0);
  }

  const toolName = String(event.tool_name ?? '');
  if (toolName !== 'Agent' && toolName !== 'Task') {
    process.exit(0);
  }

  const toolInput = event.tool_input ?? {};
  const subagentType = String(toolInput.subagent_type ?? '');

  // A namespaced roster agent carries its charter — allow it.
  const isGeneric = GENERIC_TYPES.has(subagentType) || !subagentType.includes(':');
  if (!isGeneric) {
    process.exit(0);
  }

  const description = String(toolInput.description ?? '');
  const prompt = String(toolInput.prompt ?? '');
  const haystack = stripQuotedSpans(`${description}\n${prompt}`);

  const domainHit = DOMAIN_ROUTES.find((r) => r.pattern.test(haystack));
  const keywordMatch = KEYWORD_PATTERN.exec(haystack);

  // Pure search or mechanical work — a generic agent is the right tool.
  if (!domainHit && !keywordMatch) {
    process.exit(0);
  }

  const lines = [
    '--- Generic Agent Blocked for Roster Work ---',
    '',
    `Requested subagent_type: ${subagentType || '(none)'}`,
  ];

  if (domainHit) {
    lines.push(`Domain detected: ${domainHit.domain}`);
  }
  if (keywordMatch) {
    lines.push(`Reasoning verb detected: "${keywordMatch[1]}"`);
  }

  lines.push(
    '',
    'A generic agent carries no charter. The roster agents carry theirs in their',
    'system prompts — who decides, who only analyzes, who may not fix what they',
    'found. Routing this work generically drops those constraints silently and',
    'returns something that still looks like a finished workflow step.',
    '',
  );

  if (domainHit) {
    lines.push('Route it to the owner:', ...domainHit.route.map((r) => `  ${r}`));
  } else {
    lines.push(
      'Pick the roster agent chartered for this work — the roster is in',
      'plugins/agent-teams-workforce/agents/, and the workflows that sequence',
      'them are in plugins/agent-teams-workforce/workflows/.',
    );
  }

  lines.push(
    '',
    'If this really is a pure file-pattern or keyword search, remove the',
    'reasoning verbs from the description and prompt and retry.',
    '',
    'Rule source: agent-teams-workforce — roster dispatch enforcement',
    '--- End ---',
  );

  process.stderr.write(`${lines.join('\n')}\n`);
  process.exit(2);
}

main();
