#!/usr/bin/env node
'use strict';

/**
 * PreToolUse hook — elaboration does not read what is deployed in AWS.
 *
 * Architecture, TRD, repository scoping, spec authoring and task decomposition
 * design from the architecture documentation and the repositories, not from the
 * dev account. A subagent named in aws-cli-denied-agents.json may use Bash, but
 * not to run the AWS CLI; its AWS MCP documentation tools are untouched.
 *
 * A subagent definition's disallowedTools cannot carry a command pattern (a
 * specifier removes the whole Bash tool), so the rule is enforced here, keyed on
 * the agent_type the hook input carries for a subagent.
 *
 * Decision order:
 *   1. unparseable input            -> exit 0
 *   2. not a Bash call              -> exit 0
 *   3. not a subagent               -> exit 0
 *   4. agent not in the list        -> exit 0
 *   5. no AWS CLI invocation        -> exit 0
 *   6. AWS CLI invocation           -> exit 2
 */

const fs = require('node:fs');
const path = require('node:path');

const LIST_FILE = path.join(__dirname, 'aws-cli-denied-agents.json');
const PLUGIN_PREFIX = 'agent-teams-workforce:';

/**
 * `aws` at a command position: start of line, after ; & | newline ( $( or a
 * backtick, or as the string `bash -c` / `sh -c` runs; optionally after
 * variable assignments, a wrapper (sudo, env, command, exec, time, nohup, xargs)
 * or a directory path.
 */
const AWS_CLI = new RegExp(
  String.raw`(?:^|[;&|\n(\x60]|\$\(|-c\s+['"])\s*` +
    String.raw`(?:(?:sudo|env|command|exec|time|nohup|xargs)\s+|[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*` +
    String.raw`(?:\S*\/)?aws(?=\s|$|['"])`,
);

function readStdin() {
  try {
    return fs.readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

function deniedAgents() {
  const data = JSON.parse(fs.readFileSync(LIST_FILE, 'utf8'));
  return new Set((Array.isArray(data.agents) ? data.agents : []).map((name) => String(name).trim()));
}

function main() {
  const raw = readStdin();
  if (!raw.trim()) process.exit(0);

  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  if ((data.tool_name || '') !== 'Bash') process.exit(0);
  const agentType = String(data.agent_type || '').trim();
  if (!agentType) process.exit(0);

  let denied;
  try {
    denied = deniedAgents();
  } catch (err) {
    process.stderr.write(`elaboration AWS CLI guard: cannot read ${LIST_FILE}: ${err.message}\n`);
    process.exit(1);
  }
  const name = agentType.startsWith(PLUGIN_PREFIX) ? agentType.slice(PLUGIN_PREFIX.length) : agentType;
  if (!denied.has(name)) process.exit(0);

  const command = String(data.tool_input?.command || '');
  if (!AWS_CLI.test(command)) process.exit(0);

  process.stderr.write(
    `${[
      '--- AWS CLI Blocked ---',
      '',
      `Agent: ${agentType}`,
      `Command: ${command.substring(0, 200)}`,
      '',
      'This agent works in elaboration, which designs from the architecture documentation',
      'and the repositories, not from what is deployed in AWS. Use the AWS MCP documentation',
      'tools (search_documentation, read_documentation, retrieve_skill, list_regions,',
      'get_regional_availability) for AWS facts.',
      '--- End ---',
    ].join('\n')}\n`,
  );
  process.exit(2);
}

main();
