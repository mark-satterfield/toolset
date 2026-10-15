---
name: pipeline-contracts
description: The one place for the pipeline contracts agents and code share outside a handback or a bead — the driver surface and ATW_* environment every orchestrator and headless session runs in, the Claude CLI rate-limit event, the composite ids, their phases, phase titles and role sets, the step journal, and the steps of the build and deploy pipelines. Use whenever an agent reads an ATW_* variable, requests a stop, names a composite or a phase, or prints progress; never restate a name or value below from memory.
---

# Pipeline contracts

Four contracts live here. Each is defined once, in this skill's `schemas/`; agents read this file
and the schema, and code loads the generated module or reads the definition through one loader.
Nothing outside this skill restates a variable name, a denied tool, a composite id, a phase id or
title, a role set, a progress marker, a field of the step journal, a journal change line or a step
kind of the build and deploy pipelines.

| Contract | Definition | Generated module | Generator | Staleness check |
|---|---|---|---|---|
| Driver surface and environment | [schemas/driver-surface.schema.json](schemas/driver-surface.schema.json) | `scripts/driver_surface_types.py` | `scripts/generate_types.py` | `scripts/check_generated.py` |
| Composite names and phases | [schemas/composites.json](schemas/composites.json) under [schemas/composites.schema.json](schemas/composites.schema.json) | `scripts/composites_contract.py`, `scripts/shared-blocks/composite-phases.js` (plugin root) | `scripts/generate_composites.py` | `scripts/check_composites_contract.py` |
| Step journal (one file per bead: its steps, each with its status, its session, its inputs and its artifacts), and the journal change a workflow script reports on its log (`definitions/journalChange`) | [schemas/step-journal.schema.json](schemas/step-journal.schema.json) | `scripts/step_journal_contract.py` | `scripts/generate_step_journal_contract.py` | the same script with `--check` |
| Build and deploy steps (every step kind, what it records and reads, which steps its result adds, and the steps planned up front) | [schemas/pipeline-steps.json](schemas/pipeline-steps.json) under [schemas/pipeline-steps.schema.json](schemas/pipeline-steps.schema.json) | none: `orchestrator/core/pipeline_steps.py` reads and validates the file, and `scripts/shared-blocks.mjs` copies it into the `step-journal` shared block | none | `node scripts/shared-blocks.mjs --check` for the shared block |

An agent reads and changes a step journal only through the command `atw-step-journal` (plugin
`bin/`), whose behaviour is `orchestrator/core/step_journal.py`; the orchestrator and the driver
call the same module. A run of any pipeline begins at the first step of the bead's journal that is
not done, and nothing else decides where it begins.

## The build and deploy steps

A Task's journal lists the steps of the build pipeline and a Story's the steps of the deploy
pipeline. Each such step carries its kind (for example `build:green-check`) as its `script` text.
`pipeline-steps.json` defines every kind: its description and purpose, what runs it (the driver or
a workflow script), the artifacts it records and reads, the steps its result adds, the rule by
which it declines to add another correction, and what it waits for. `plan` lists the kinds planned
up front; `inner` lists the child steps a workflow script plans under a step it performs.

- Python: `orchestrator/core/pipeline_steps.py` gives the up-front plan (`plans`), the plan of one
  step a result adds (`step_plan`) and `open_journal`, which makes a bead's journal hold its plan
  whether elaboration created the journal, an earlier dispatch did, or none exists.
  `journal_changes.create_child_journal` plans the same steps when elaboration creates the bead.
- Workflow scripts: the `step-journal` shared block (`scripts/shared-blocks/step-journal.js`) holds a
  copy of the journal, runs its steps from the next one with a table from step kind to function,
  and reports each change as a log line.

## Journal changes a workflow script reports

A workflow script cannot write a file. It reports each change to the journal as one log line:
`x-changePrefix` followed by a `journalChange` object (`run`, `n`, `op`, `step`, and `artifacts`,
`add` or `failure` by `op`). An object longer than `x-changeChunk` characters is written as
`x-changePartPrefix` lines, each `<n> <i>/<k> <text>`. The driver hands every log line of the
session to `orchestrator/core/journal_lines.py` (`ChangeReader.feed`), which applies each change
once, in the order of `n`: a change of another run or one already applied changes nothing, and a
change that skips a number is refused.

Change a contract by editing its schema or `composites.json`, then run its generator. Each check exits
1 when a generated file differs from what its source generates.

## Driver surface and the ATW_* environment

The driver (`ops/sdlc-automation` under `$ATW_CONTROL_REPO`) hands every orchestrator and headless
session the environment `$defs.DriverEnvironment` lists. What an agent uses:

- `ATW_CONTROL_REPO` — the control repository. Always set.
- `ATW_ARCH_PATH` — the architecture root, set only when known. Use the run's `archPath` argument
  first and this variable second.
- `ATW_STOP_FILE` — the stop marker, optional. Its absence means no marker. Touching the file (mode
  0o600) requests a drain; testing whether it exists tells you a drain was requested. It only
  requests a stop: how a stop is classified is the handback contract's business.
- `ATW_EXECUTION_ID` — the driver execution id, always set for an orchestrator dispatch.
- `ATW_ORCH_IDLE` — the orchestrator idle limit in seconds, a positive finite number; default 3600.

The plugin orchestrator reads the driver modules named in `x-driver` (headlessenv, fablewall,
breaker, childproc) from `$ATW_CONTROL_REPO/<DRIVER_DIR_PARTS>`; the generated `HeadlessEnvironment`,
`FableWall`, `Breaker` and `ChildProcess` protocols are their surface. `DENIED_TOOLS` is the exact,
ordered list of tools the driver denies every headless build and deploy Workflow session with
`--disallowedTools`; a markdown-defined agent session takes its tools from its front matter
instead. `TERMINATE_GRACE` is the seconds a terminated child gets
before it is killed.

`$defs.RateLimitEvent` is the Claude CLI stream-json `rate_limit_event`. Only status `rejected` is
acted on. The account windows are `ACCOUNT_WINDOWS`; any other window is model-specific; a window is
exhausted at `EXHAUSTED_UTILIZATION`.

This contract carries no handback classification: `orchestrator/core/handback_contract.py` defines
it.

## Composite names and phases

`composites.json` is the one list of composite ids. Each active composite names its runner
(`orchestrator`, `workflow`, `driver` or `probe`), its phases in run order with the title its
workflow shows, its role sets and, for a composite that opens a run budget, its opening kind.
Retired ids remain only to attribute historical cost. A known composite that declares no phases shows
`fallbackPhases`; an unknown id is an error.

A phase with `"event": true` is one the orchestrator emits as a `phase` event. A headless session
must not print a line that begins with `wire.phaseSentinel`; the driver writes those lines.

Workflow scripts carry `scripts/shared-blocks/composite-phases.js` as a shared block and read
`COMPOSITE_CONTRACT`, `compositePhases(id)` and `compositePhaseTitle(id, phase)` from it.

## Loading from code

- Plugin Python imports `driver_surface_types` and `composites_contract` from this skill's
  `scripts/` directory.
- The driver loads them through `pluginversion.plugin_file("skills", "pipeline-contracts",
  "scripts", <module>)`, in `driversurface.contract()` and `compositecontract.contract()` /
  `compositecontract.wire()`.
- `driver_surface_types.load_schema()` returns the driver-surface schema document.
