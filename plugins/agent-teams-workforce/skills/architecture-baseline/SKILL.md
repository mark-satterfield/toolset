---
name: architecture-baseline
description: Assess and evolve effective architecture using one shared author, reviewer and decider standard.
---

# Architecture baseline

Read [the review standard](review-standard.md) before surveying, coordinating, authoring,
reviewing, deciding or integrating architecture. That is the common completion basis.
Read artifact-handoff's [Epic contracts](../artifact-handoff/epic-contracts.md) and the relevant
schema there for input and output fields. Contract correctness and architecture correctness are
separate: Python validates structure; independent reviewers judge claims and coverage.

An effective view is reviewed design, not evidence of implementation and not a permanent
constraint on future PRDs. Preserve valid design and evidence, revise what current requirements
change, and fill the implementation-detail gaps in the affected views. Do not redesign unrelated
historical debt. No fixed specialist quota applies; the coordinator selects bounded specialties.

The survey judges design and documentation, never built-ness. Python computes implementationWork
from the matrix snapshot and cited view elements. Fresh survey code.state, implementationAction
and disposition are unknown/unknown/undetermined; legacy values are compatibility context only.
The Closure agent walks views, never repository code or deployments; Python classifies its
reached elements using the matrix. A missing or unknown matrix row creates implementation work.
Open Tasks elsewhere add blockers; they do not remove this Epic's work.
