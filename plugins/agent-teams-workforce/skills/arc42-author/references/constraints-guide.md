# Section 2 — the owner's constraints

## What a constraint is

A constraint is a rule the owner imposes to guide design. Constraints are few, global (enterprise or
project level) and not specific to one implementation, and they are kept short on purpose: the owner
removes a constraint when they want to be free to deviate from it, or when the established patterns
make it unnecessary.

A constraint is not a design outcome. A choice a design made, however widely it now applies, is part
of the architecture description: a pattern used across services is a section 8 concept, an
enterprise-level direction is section 4, and a feature's or service's design is in its views in
sections 5, 6 and 7. Those are followed as established patterns, not enforced as constraints.

## Who writes it

The owner. `arc42/02-architecture-constraints/README.md` is written by the owner alone, and no
agent, skill or workflow writes to it in any version, because a constraint an agent wrote would bind
every later design without the owner having imposed it.

## How the pipeline uses it

- Every design reads section 2 as the boundary it works within.
- A design that would need a constraint to change does not change it. The agent reports the
  constraint, the design that conflicts with it and the reason, to its caller, who takes it to the
  owner.
- A reviewer checks a target against section 2 and reports any conflict as a finding.
