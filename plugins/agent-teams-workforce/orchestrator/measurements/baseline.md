# Token baseline before the Python rewrite (step S00)

Recorded 2026-10-09 from existing records only. No pipeline run was started.

Units: weighted = input + 5 x output + 1.25 x cacheCreate + 0.1 x cacheRead (the `runcost.py` weights). Not dollars.

## State at measurement

- Toolset repository: on `main`, clean.
- Control repository: on `main`; the only uncommitted path is the untracked `.claude/workflow-runs/relay/`.
- Installed plugin `agent-teams-workforce@mark-satterfield`: version `6.99.19`
  (`~/.claude-skillspoke/plugins/cache/mark-satterfield/agent-teams-workforce/6.99.19`).

## Headline numbers: the 29 `prd-to-spec` runs of 2026-10-09

| Measure | Value |
|---|---|
| Runs | 29 (8 Epics: `ssbd-guuuz` 8 runs, `ssbd-mb689` 8, `ssbd-hdqid` 7, `ssbd-abm28` 2, and one each for `ssbd-2d577`, `ssbd-5j84x`, `ssbd-ffouc`, `ssbd-nc8z`) |
| Total weighted tokens | 68,973,529 |
| Median weighted tokens per run | 1,837,843 |
| Mean weighted tokens per run | 2,378,398 |
| Sessions (all roles, host included) | 438 |
| Run outcomes (`stage`) | `epic-lifecycle`, `interrupted`, `agent-dispatch-failed`, `account-quota-exhausted`, `requires-human-action`; none completed |

## Command-runner sessions

Role `[workflow-command-runner]` (agent `agent-teams-workforce:workflow-command-runner`, Sonnet):

| Measure | Value |
|---|---|
| Sessions | 352 of 438 (80.4% of all sessions) |
| Weighted tokens | 33,331,059 |
| Share of total weighted tokens | 48.3% |
| Weighted tokens per session | about 94,700 |

Largest roles by weighted tokens (all 29 runs):

| Role | Weighted | Sessions | Share |
|---|---|---|---|
| survey [prd-reality-reconciler] | 12,813,906 | 10 | 18.6% |
| round1 [workflow-command-runner] | 10,933,493 | 115 | 15.9% |
| survey [workflow-command-runner] | 6,124,799 | 64 | 8.9% |
| (host session) | 5,817,459 | 29 | 8.4% |
| round1 [architecture-decision-workflow-coordinator] | 4,151,435 | 16 | 6.0% |
| epic [workflow-command-runner] | 3,465,745 | 37 | 5.0% |

## Survey-redo share

Agent `prd-reality-reconciler` (Opus) in the `survey` phase: 12,813,906 weighted tokens, 18.6% of the total, in 10 sessions.
For every Epic, none of this appeared in its first run of the day; all of it was spent in the later runs (restarts) of
`ssbd-abm28`, `ssbd-guuuz`, `ssbd-hdqid` and `ssbd-mb689`. The whole 18.6% is therefore survey work redone on restarts.
That is about 1.28M weighted tokens per survey session, higher than the 850k figure in `CONTEXT.md` section 4, which counts
only part of the cost.

## Startup tokens per fresh session

First assistant turn of each agent transcript in one run (`ssbd-abm28`, run `...T042105-81942-a98d07`; 10 transcripts), usage
fields input / cache_creation / cache_read:

| Agent | Model | input | cacheCreate | cacheRead | Context loaded |
|---|---|---|---|---|---|
| `workflow-command-runner` (8 sessions) | Sonnet | 2 | 66,245 to 70,125 | 3,239 | about 69,500 |
| `prd-reality-reconciler` | Opus | 2 | 107,235 | 14,933 | about 122,200 |
| `polyrepo-steward` | Sonnet | 2 | 0 | 99,869 | about 99,900 |

A fresh command-runner session loads about 69.5k tokens before it runs its one command. This matches the roughly 68k in `CONTEXT.md`.

## Reproduction

Commands (run from any directory; `<driver>` = `/Users/msat1971/projects/SkillSpoke/apps/personal-agent/SkillSpoke/ops/sdlc-automation`):

```
git -C /Users/msat1971/projects/mark-satterfield/toolset status --short
git -C /Users/msat1971/projects/SkillSpoke/apps/personal-agent/SkillSpoke status --short
grep -A8 "agent-teams-workforce@mark-satterfield" ~/.claude-skillspoke/plugins/installed_plugins.json
python3 <driver>/runcost.py summary
python3 <driver>/runcost.py profile 2026-10-09
python3 <scratchpad>/s00_baseline.py 20261009
```

- `runcost.py summary` gives `byDay` for 2026-10-09: 29 runs, 438 sessions, 68,973,529 weighted.
- `runcost.py profile 2026-10-09` lists the 29 runs but returns null weights and an empty `byRole`, so it is not the source of the role numbers.
- The role numbers come from the `roles` object in each `<driver>/state/runs/*-prd-to-spec-20261009T*.cost.json`,
  summed by `s00_baseline.py` (a read-only script: it sums `weighted` and `sessions` per role over those files, takes the
  median of the per-run `weighted`, and reads the first assistant turn's `usage` from the agent transcripts under
  `~/.claude-skillspoke/projects/<project>/<sessionId>/` for the startup tokens). The script is a scratchpad file and is not committed.
- The survey-redo split compares each Epic's first run of the day (ordered by `startedAt`) with its later runs.
- Targets to compare against after the owner's runs (`CONTEXT.md` section 5): zero command-runner sessions; restart cost near zero tokens.
