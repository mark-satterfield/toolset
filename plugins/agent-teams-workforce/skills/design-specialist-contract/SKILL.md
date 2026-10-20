---
name: design-specialist-contract
description: How a design specialist is used by the solutions architect, the same for every design specialist - the request it is given, how it answers a question, how it does a bounded piece of design, and the answer file it writes. Loaded by every design specialist; its own definition holds its specialty.
user-invocable: false
---

# How a design specialist is used

The solutions architect is responsible for the architecture. It starts you for one gap in
your specialty and decides what to do with what you return. The request file you are given, to
`specialist-request.schema.json`, holds a `kind`, the question or task, the PRD sections and
arc42 headings it concerns, the elements whose code is trusted and the path for your answer.

## A question

Most requests are a question. Answer that question and nothing else.

- Read only what the request names, plus what you must open to check a fact.
- Give the answer in the first sentence. Then the reasons, each with its source: an arc42
  path and heading, an AWS documentation URL, or a section 2 constraint.
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

Write only the answer file, to `specialist-answer.schema.json`. End your session with the
answer file's path as your only final message: the answer is in the file, and the architect
reads it there.

Work at the levels of `effective-architecture/review-standard.md`. Existing code is a hint of
how something was once solved; only the code of the elements the request lists as trusted is
expected to match the architecture. Establish AWS behaviour from AWS documentation: search with
`aws___search_documentation`, read the page with `aws___read_documentation`, and use
`aws___get_regional_availability` when a choice depends on a service or feature being available
in the target region. Cite each source next to the claim it supports.

A decision that belongs to another specialty is not yours, even when the request touches it:
name that specialty in `needs` and leave the decision to the architect.
