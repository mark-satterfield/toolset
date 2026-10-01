# Section 4 — the solution strategy

Section 4 holds the enterprise-level direction: the architectural style and the few approaches
everything else follows. For example, an event-based architecture with one API for authoring and
publishing events. It is about one page, in `arc42/04-solution-strategy/README.md`.

## What it holds

- **The architectural style** — how the system is decomposed and how its parts communicate, in a few
  sentences, with the reason a reader needs.
- **The few approaches everything else follows** — the handful of system-wide choices a new design
  starts from, each stated as what the system does, with the reason.
- **How the top quality goals are met** — one line per goal from section 1, naming the approach that
  meets it.

A diagram is welcome when it shows the style better than prose, for example a landscape or N-tier
view at system scope.

## What it does not hold

- Implementation decisions: a technology chosen for one service, a table design, a stack layout.
  They are part of the architecture description, in the section 5, 6, 7 or 8 view the MODEL names.
- A decision table, decision ids, rejected alternatives or a decision log. A design's outcome becomes
  part of the description; there is no decision record.
- Constraints. They are the owner's, in section 2.

## When it changes

Section 4 changes only when a design alters the direction itself, for example adopting a new
architectural style or a new system-wide integration approach. A design that follows the direction
leaves section 4 as it is. A target that does change it carries its own copy of
`04-solution-strategy/README.md`, and its delta states the change.
