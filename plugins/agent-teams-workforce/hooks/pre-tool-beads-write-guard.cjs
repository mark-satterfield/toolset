#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — beads is the inter-agent channel, not an orchestrator
 * scratchpad.
 *
 * Workflow phases hand findings to each other through beads. Downstream agents
 * read those notes as authoritative upstream input and act on them. An
 * orchestrator that writes into a bead can therefore instruct a purpose-built
 * agent to skip its own analysis — recording a decision the agent was supposed
 * to make, and having it read back as though an agent had made it.
 *
 * That channel needs a writer boundary: agents write beads, the orchestrator
 * reads them. Reads are untouched.
 *
 * The boundary covers BOTH ways of reaching beads. Matching only the `bd` shell
 * command left the MCP tools (mcp__beads__create, mcp__beads__update) wide open,
 * which is not a smaller hole than the one being closed — it is the same hole
 * with a different door.
 *
 * Decision order:
 *   1. unparseable input     -> exit 0 (other Bash guards still run)
 *   2. subagent session      -> exit 0
 *   3. beads MCP write tool  -> exit 2
 *   4. non-Bash tool         -> exit 0
 *   5. beads read command    -> exit 0
 *   6. beads write command   -> exit 2
 */

const fs = require('node:fs');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

/**
 * beads subcommands that mutate tracker state. Matched against a `bd`
 * invocation at the start of the command or after a shell separator.
 */
/**
 * The hazard is PROSE reaching a downstream agent's prompt. A bead's description
 * and notes are read by the agents that later work it, so text written there
 * arrives indistinguishable from an agent's own finding — "decision already made"
 * was enough to skip a phase that never ran.
 *
 * Tracker ADMINISTRATION is a different thing and is not blocked. Closing a
 * resolved bead, reopening one, or moving its status injects no instruction into
 * anyone's prompt; blocking it only forces the operator to disarm the guards to
 * do routine bookkeeping, which is how a guard trains people to work around it.
 */
const BD_WRITE_SUBCOMMANDS = [
  'create', 'new', 'add',
  'update', 'edit', 'set',
  'note', 'notes', 'comment',
  'label', 'unlabel', 'tag',
  'priority', 'estimate', 'score',
  'dep', 'depend', 'link', 'unlink',
  'rename',
  'import', 'sync', 'merge',
];

/** Administrative subcommands that carry no prose into an agent prompt. */
const BD_ADMIN_SUBCOMMANDS = ['close', 'reopen', 'delete', 'rm', 'assign', 'unassign', 'move', 'defer'];

/** Matches a `bd <write-subcommand>` invocation anywhere a command may start. */
const BD_WRITE_PATTERN = new RegExp(
  `(?:^|[;&|]|&&|\\|\\|)\\s*bd\\s+(?:${BD_WRITE_SUBCOMMANDS.join('|')})\\b`,
  'i',
);

/**
 * MCP beads tools that mutate. The read-side tools (context, ready, show) are
 * deliberately absent: the orchestrator reading beads is the intended flow.
 */
const BD_MCP_WRITE_TOOLS = new Set([
  'mcp__beads__create',
  'mcp__beads__update',
  'mcp__beads__note',
  'mcp__beads__comment',
  'mcp__beads__dep',
  'mcp__beads__label',
]);

/** Emits the denial feedback on stderr and terminates with exit 2. */
function deny(what, detail) {
  process.stderr.write(
    `${[
      '--- Beads Write Blocked ---',
      '',
      what,
      ...(detail ? [`Input: ${detail}`] : []),
      '',
      'beads carries findings between workflow phases. Downstream agents read bead',
      'notes as authoritative upstream input, so a note written here reaches them',
      'indistinguishable from one an agent produced — and can tell a purpose-built',
      'agent its analysis is already done. A note reading "decision already made"',
      'is enough to skip a phase that was never run.',
      '',
      'Agents write beads; the orchestrator reads them.',
      '',
      'To record something in a bead, route it through the agent that owns the',
      'finding:',
      '  - architecture decisions   -> architecture-decider (architecture workflow)',
      '  - spec content             -> spec-authoring workflow',
      '  - task breakdown / scores  -> task-decomposition workflow',
      '  - run outcomes             -> run-ledger-writer',
      '',
      'Unaffected: reads (bd list/show/ready/stats, mcp__beads__ read tools) and',
      `tracker admin (${BD_ADMIN_SUBCOMMANDS.join(', ')}, bd update --status).`,
      '',
      'Rule source: agent-teams-workforce — beads writer boundary',
      '--- End ---',
    ].join('\n')}\n`,
  );
  process.exit(2);
}

/** Reads all of stdin synchronously; returns '' when unreadable. */
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

  if (event.agent_id) {
    process.exit(0);
  }

  // Out of scope in the monorepo that builds this plugin.
  if (!guardsApplyHere(event)) {
    process.exit(0);
  }

  const toolName = String(event.tool_name ?? '');

  // The MCP route reaches the same tracker as the shell command.
  if (BD_MCP_WRITE_TOOLS.has(toolName)) {
    deny(`MCP tool: ${toolName}`, JSON.stringify(event.tool_input ?? {}).slice(0, 200));
  }

  if (toolName !== 'Bash') {
    process.exit(0);
  }

  const command = String((event.tool_input ?? {}).command ?? '');
  if (!command.trim()) {
    process.exit(0);
  }

  const match = BD_WRITE_PATTERN.exec(command);
  if (!match) {
    process.exit(0);
  }

  // `bd update --status <x>` moves a bead through the workflow and carries no
  // prose; only the text-bearing flags are the hazard.
  if (/(?:^|\s)bd\s+update\b/.test(command) && !/(?:--notes?|--desc|--description|--comment|--title)\b/.test(command)) {
    process.exit(0);
  }

  // `bd create --help` writes nothing — it prints usage. The pattern matches on
  // the subcommand NAME, which is not the same as judging whether the call
  // mutates anything, so a help lookup was being blocked as a write. Same for
  // dry-run and version flags: all reads.
  if (/(?:^|\s)(?:--help|-h|--dry-run|--version|-V)(?:\s|$)/.test(command)) {
    process.exit(0);
  }

  deny(`Command: ${command.trim()}`);
}

main();
