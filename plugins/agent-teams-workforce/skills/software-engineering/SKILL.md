---
name: software-engineering
description: The owner's language-neutral coding rules — read the task and every place the change must reach before writing, take the smallest complete change (skip what nobody asked for, reuse what the codebase already has, then the standard library, then an installed dependency, then the minimum code), finish every caller, test and fixture the change breaks, never cut validation, error handling, security or accessibility, leave the check the tier requires, and refactor through GitNexus without exception. Use whenever writing, editing, refactoring, reviewing or testing code in any language, together with that language's coding skill (python-coding, typescript-coding, shell-coding, cdk-coding, web-frontend-coding).
user-invocable: true
---

# Software engineering: the smallest complete change

These rules apply to every piece of code an agent writes, changes, refactors, reviews or tests, in any language. A
reviewer judges a change against them.

They hold for every language. The language's own coding skill (`python-coding`, `typescript-coding`, `shell-coding`,
`cdk-coding`, `web-frontend-coding`) is loaded with this one and holds the rules specific to that language. Where a
language skill states a more specific rule on the same subject, follow the language skill. For example: a docstring or
TSDoc comment the language skill requires is part of the code, not a comment this skill limits; parsing boundary data
into a typed model, wrapping an untyped third-party API at the edge, or extracting a helper to keep complexity down is
code the language skill asks for, not an abstraction nobody asked for.

## Before you write

Read the task and the code it touches. List every place your change must reach: callers, tests, fixtures, config,
exports. Check what your change could break for users: data it would destroy or expose, callers that stop working.
That is scope. Extra features are not.

## The smallest complete change

Take the first option that fully works:

1. Does it need to exist? Skip features, options and flexibility nobody asked for, and name them in one line. A vague
   request ("build me X") gets the smallest version that does the core job.
2. Already in this codebase (a helper, component, service, pattern)? Use it the way the surrounding code does. Use
   mcp-graphrag-server and gitnexus to search; the `graphrag-lookup` skill says which tool answers which question.
3. Standard library or a platform feature? Use it, unless the project has its own. A house component beats a native
   widget.
4. An installed dependency? Use it. Never add a dependency for a few lines.
5. Can it be one line a reader gets at a glance? One line.
6. Otherwise: the minimum code that works.

- Be willing to update existing code. This project iterates on its own code.
- Be lazy about the solution, never about the change itself: finish every part the task needs, including the callers,
  tests and fixtures your change breaks.
- No abstraction, wrapper, type conversion, option, config, boilerplate or "for later" code nobody asked for. Keep
  values in the form the platform already gives you. Deletion beats addition. Keep the structure the codebase already
  has: its layers, interfaces and conventions.
- The shortest working diff wins, once you know everything it must touch. A one-liner that needs decoding is not short.
- Comment only the why the code cannot show, in one line.
- Bug fix: before you edit, grep every caller of the function you touch, then fix the root cause once in the shared
  code.
- Code you move or merge keeps its error handling and validation.
- Between options of equal size, take the one that is correct on edge cases.
- Lazy code without its check is unfinished. The check depends on the tier (the project's instructions define the tiers,
  for example in its root `AGENTS.md`):
  - Tier 1, the project's product code: new non-trivial logic (a branch, a loop, a parser, money or security, or a whole
    new script or app) leaves one small test or an assert-based self-check. Trivial changes need none.
  - Tier 2, the owner's tooling (this plugin and everything else in the toolset repository, the project's own build and
    operations tooling, and every repository's `AGENTS.md`, `CLAUDE.md` and `.claude/`): the check is one throwaway probe. Import the changed
    code and call the changed function or entry point once with realistic input. The probe is not kept, committed,
    wired into a hook, or run again by a later step, and no test suite is written.
- A shortcut with a known limit gets a code comment in this form: `shortcut: <the limit>, <when to upgrade>`.

Never cut: validation at trust boundaries, error handling that prevents data loss, security, accessibility, the
calibration real hardware needs, anything the user asked for.

## Refactoring

Every refactor (a rename, an extract, a move, a split, a restructure) goes through GitNexus, without exception, as the
`graphrag-lookup` skill describes each tool:

- Before changing any function, class or method, run `impact` on it with `direction: "upstream"`, and report its
  blast radius: the direct callers, the affected execution flows and the risk level.
- Rename every symbol with `rename`, `dry_run: true` first, never with find-and-replace. An agent not granted
  `rename` reports the rename the work needs.
- Before finishing, run `detect_changes` and compare the symbols and flows it reports with the ones you meant to
  change.
- When GitNexus does not answer, or its index is stale and re-indexing as `graphrag-lookup` says does not fix it, the
  refactor stops and reports a named blocker: the tool, the repository and the error. It never goes on without
  GitNexus.
