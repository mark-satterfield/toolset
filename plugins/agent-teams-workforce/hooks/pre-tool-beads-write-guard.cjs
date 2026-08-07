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
 * Decision order:
 *   1. unparseable input     -> exit 0 (other Bash guards still run)
 *   2. subagent session      -> exit 0
 *   3. non-Bash tool         -> exit 0
 *   4. beads read command    -> exit 0
 *   5. beads write command   -> exit 2
 */

const fs = require('node:fs');
const { guardsApplyHere } = require('./lib/plugin-scope.cjs');

/**
 * beads subcommands that mutate tracker state. Matched against a `bd`
 * invocation at the start of the command or after a shell separator.
 */
const BD_WRITE_SUBCOMMANDS = [
  'create', 'new', 'add',
  'update', 'edit', 'set',
  'close', 'reopen', 'delete', 'rm',
  'note', 'notes', 'comment',
  'assign', 'unassign',
  'label', 'unlabel', 'tag',
  'priority', 'estimate', 'score',
  'dep', 'depend', 'link', 'unlink',
  'move', 'rename',
  'import', 'sync', 'merge',
];

/** Matches a `bd <write-subcommand>` invocation anywhere a command may start. */
const BD_WRITE_PATTERN = new RegExp(
  `(?:^|[;&|]|&&|\\|\\|)\\s*bd\\s+(?:${BD_WRITE_SUBCOMMANDS.join('|')})\\b`,
  'i',
);

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

  if (String(event.tool_name ?? '') !== 'Bash') {
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

  process.stderr.write(
    `${[
      '--- Beads Write Blocked ---',
      '',
      `Command: ${command.trim()}`,
      '',
      'beads carries findings between workflow phases. Downstream agents read',
      'bead notes as authoritative upstream input, so a note written here reaches',
      'them indistinguishable from one an agent produced — and can tell an agent',
      'its analysis is already done.',
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
      'Read access is unaffected: bd list, bd show, bd ready, bd stats.',
      '',
      'Rule source: agent-teams-workforce — beads writer boundary',
      '--- End ---',
    ].join('\n')}\n`,
  );
  process.exit(2);
}

main();
