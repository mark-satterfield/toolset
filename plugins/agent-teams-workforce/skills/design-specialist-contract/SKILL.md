---
name: design-specialist-contract
description: How a design specialist is used by the solutions architect, the same for every design specialist - the request it is given, how it answers a question, how it does a bounded piece of design, and the answer file it writes. Loaded by every design specialist; its own definition holds its specialty.
user-invocable: false
---

# How a design specialist is used

The solutions architect is responsible for the architecture, and decides what to do with what
you return. The script starts you, as your own session, with the architect's one request to you
for this round: every question and draft review it has in your specialty, numbered in the
request when there are several. The request file you are given, to
`specialist-request.schema.json`, holds a `kind` (`task` when any part is a task), the
questions or tasks, the PRD sections and arc42 headings they concern, the elements whose code is
trusted and the path for your answer. Answer every part in the one answer file: `answer` sums
them up in one sentence, each part's answer is a reason that starts with the part's number, and
a task's decisions are design facts. Nobody can ask you a follow-up: what your answers raise
goes in `needs`, and the architect asks it in a second round.

## A question

Most requests are a question. Answer that question and nothing else.

- Read only what the request names, plus what you must open to check a fact. When it names an
  extract of the architecture, read the parts it names in that extract, not their sources.
- Give the answer in the first sentence. Then the reasons, each with every source it rests on:
  an arc42 path and heading, an AWS documentation URL, or a section 2 constraint.
- State the assumptions the answer rests on.
- Name the alternatives you considered only when the question asks for them.
- When the answer needs another specialty, say which and why, in `needs`. The architect asks
  that specialist.
- A good answer is short: the rest of the PRD and the architect's other decisions are outside
  the question.

## A bounded task

When `kind` is `task`, the request states exactly what is to be decided and what is not.
Return the decisions as design facts: one sentence each with its reason, each with where it
belongs (`belongsIn`): the arc42 section, or the folder of the detailed architecture
(`detailed/system`, `detailed/cross-component`, `detailed/components/<component>`,
`detailed/features/<feature>`) for the detailed design of the whole system, of components
working together, of one component or of one feature. The detailed design is yours to decide
too: names, fields, keys, types and schemas are design facts like any other. Stay inside the
stated bounds.

## In both cases

Write only the answer file. Its shape is `specialist-answer.schema.json`, which is
`architecture-result.schema.json#/$defs/SpecialistAnswer` in the plugin's
`skills/artifact-handoff/schemas/`: read it, and write exactly the shape that schema defines,
and no other fields. This skill and your definition say what to put in those fields, never
their shape. End your session with the answer file's path as your only final message: the
answer is in the file, and the architect reads it there.

Work at the levels of `effective-architecture/review-standard.md`. Existing code is a hint of
how something was once solved; only the code of the elements the request lists as trusted is
expected to match the architecture. Establish AWS behaviour from AWS documentation: search with
`aws___search_documentation`, read the page with `aws___read_documentation`, and use
`aws___get_regional_availability` when a choice depends on a service or feature being available
in the target region. Cite each source next to the claim it supports.

A decision that belongs to another specialty is not yours, even when the request touches it:
name that specialty in `needs` and leave the decision to the architect.
