---
name: pipeline-contracts
description: The one place for the pipeline contracts agents and code share outside a handback or a bead — the driver surface and ATW_* environment every orchestrator and headless session runs in, the Claude CLI rate-limit event, and the composite ids, their phases, phase titles and role sets. Use whenever an agent reads an ATW_* variable, requests a stop, names a composite or a phase, or prints progress; never restate a name or value below from memory.
---

# Pipeline contracts

Two contracts live here. Each is defined once, in this skill's `schemas/`; agents read this file and
the schema, and code loads the generated module. Nothing outside this skill restates a variable
name, a denied tool, a composite id, a phase id or title, a role set or a progress marker.

| Contract | Definition | Generated module | Generator | Staleness check |
|---|---|---|---|---|
| Driver surface and environment | [schemas/driver-surface.schema.json](schemas/driver-surface.schema.json) | `scripts/driver_surface_types.py` | `scripts/generate_types.py` | `scripts/check_generated.py` |
| Composite names and phases | [schemas/composites.json](schemas/composites.json) under [schemas/composites.schema.json](schemas/composites.schema.json) | `scripts/composites_contract.py`, `scripts/shared-blocks/composite-phases.js` (plugin root) | `scripts/generate_composites.py` | `scripts/check_composites_contract.py` |

Change a contract by editing its schema or `composites.json`, then run its generator. Each check exits
1 when a generated file differs from what its source generates.

## Driver surface and the ATW_* environment

The driver (`ops/sdlc-automation` under `$ATW_CONTROL_REPO`) hands every orchestrator and headless
session the environment `$defs.DriverEnvironment` lists. What an agent uses:

- `ATW_CONTROL_REPO` — the control repository. Always set.
- `ATW_ARTIFACT_SCRIPT` — the phase-artifact recorder. Always set; record artifacts with it.
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
ordered list of tools no session may use; `TERMINATE_GRACE` is the seconds a terminated child gets
before it is killed.

`$defs.RateLimitEvent` is the Claude CLI stream-json `rate_limit_event`. Only status `rejected` is
acted on. The account windows are `ACCOUNT_WINDOWS`; any other window is model-specific; a window is
exhausted at `EXHAUSTED_UTILIZATION`.

This contract carries no handback classification and no receipt data.

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
