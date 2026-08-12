# CDS — Decision Log

Choices where a live alternative was rejected. One entry per decision, newest first.

---

## A Section is never required to be pre-defined

**Decided:** 2026-08-10

**Decision.** Naming a Page or a Section the library has not seen composes normally. The composer builds it from its attributes — where it pins, its extent, its theme — and resolves its Shape through the Shape-assignment waterfall. The halt codes `SECTION_TYPE_UNKNOWN` and `PAGE_UNKNOWN` are retired.

The library boundary — where an unknown name halts instead of being guessed at — now sits at two places only:

- **Component**, whose markup, sizing, ARIA, and token bindings would have to be fabricated.
- **stored Shell**, which is a file that either exists or does not.

**Rejected alternative.** Requiring every Page and Section to have a library entry, halting otherwise. That was the behaviour from 2026-07-06 (`36f2856`) until this change.

**Why it was wrong.** No requirement ever asked for it. It arrived unremarked inside a large restructure and was then generalised in the README into a principle — "It will not invent catalog entries… An unknown Page, Section, Component, or stored Shell name halts" — which made it far harder to notice as a mistake than a single rule would have been.

The reasoning that justifies halting on a Component does not transfer. A Component carries a contract that must be invented if it is absent. A Section is a Frame: a surface plus a Shape. The Shape is where the contract lives, and Shapes already resolve through a waterfall that reuses the library before generating anything. An unfamiliar Section needs no invention; it needs a Shape, and the waterfall finds one.

The cost was concrete: a Shell could not put a rail on the inline-end edge without a new library entry first, which is a placement decision the library has no business owning.

**Consequences.** `pipeline.md` states the boundary once. README, the compose skills, their commands, and the UI-author agent drop the two codes. Section and Page entries are documented as presets carrying the system's answers, not as a closed set of what may be composed.

---

## A pinned Section's edge is chosen by the Shell, not by the library

**Decided:** 2026-08-10

**Decision.** `shell_edge` (one fixed edge, declared by the entry) is replaced by `pins_to` (the set of edges the Section MAY pin to) plus `extent` (its size on the fixed axis, with `min`, `max`, and `resizable`). The ShellDefinition picks one edge per instance.

`left-rail` is renamed `side-rail` and pins to either inline edge.

**Rejected alternative.** Adding a second `right-rail` entry beside `left-rail`. That duplicates a surface contract of roughly twenty determinations to express one attribute, and leaves placement in the library.

**Why.** There is no such entity as a rail, a top bar, or a footer. Each is a Section with attributes: an edge, an extent, a theme, and a Shape. Naming an entry for a position freezes a decision that belongs to the Shell — and the requirement is explicit that a user can move the navigation between positions at runtime.

**Consequences.** `FORMAT.md` carries `pins_to` and `extent`. `check_frame_regions.py` validates `pins_to` as an edge set. `side-rail` gains `presentation` (expanded / collapsed / hidden) and a resizable extent, with the accessibility contract that collapsing removes labels from view but never from the accessibility tree.
