# Choosing a UML diagram type

UML defines fourteen diagram types; five of them carry almost all the value in software architecture documentation. Pick by the question you are answering, not by habit. A diagram that tries to answer several questions answers none of them well.

## The five types that earn their place

### Class diagram — structure of the domain

**Answers:** What are the entities (types), what do they hold (attributes), what can they do (operations), and how do they relate (association, aggregation, composition, generalization, dependency)?

**Communicates:** The static structure of the system's vocabulary — the nouns of the domain and the rules that connect them. A class diagram is the canonical way to render a domain model.

**Use it when:**
- You are capturing a domain model or the shape of a bounded context.
- You need to show inheritance hierarchies or interface-to-implementation relationships.
- You are documenting an entity/aggregate structure that the persistence layer mirrors.

**Relationship notation that matters:**
- **Association** (plain line) — one type references another.
- **Aggregation** (hollow diamond) — "has-a", parts can outlive the whole.
- **Composition** (filled diamond) — "owns-a", parts die with the whole.
- **Generalization** (hollow triangle) — inheritance / "is-a".
- **Realization** (dashed line, hollow triangle) — a class implements an interface.
- **Multiplicity** (`1`, `0..1`, `*`, `1..*`) — how many of each end participate.

**Avoid:** Reproducing every getter/setter or framework class. Model concepts, not code.

### Sequence diagram — ordered interaction over time

**Answers:** Which participants exchange which messages, in what order, to fulfill one scenario?

**Communicates:** Dynamic, time-ordered behavior. Lifelines run top to bottom as the vertical axis is time; messages are horizontal arrows. Activation bars show when a participant is doing work.

**Use it when:**
- You are tracing a single use case or request end to end (e.g., "checkout", "OAuth login").
- You need to show synchronous vs asynchronous calls, returns, or the order of side effects.
- A reviewer keeps asking "but what calls what, and when?"

**Notation that matters:** solid arrow = synchronous call, dashed arrow = return, open arrowhead = asynchronous message, `alt`/`opt`/`loop`/`par` fragments for conditional, optional, repeated, and parallel flows.

**Avoid:** One sprawling diagram for the whole system. One scenario per diagram. If you have more than ~7 participants, your boundary is wrong.

### State diagram — lifecycle of one entity

**Answers:** What discrete states can a single entity occupy, and which events trigger transitions between them?

**Communicates:** The behavior of one stateful thing over its lifetime — an order, a connection, a job, a feature flag. A start (initial) pseudostate, named states, transitions labeled with their triggering event, and an end (final) state.

**Use it when:**
- An entity has a meaningful lifecycle (`draft → submitted → approved → shipped`).
- Transitions are guarded by conditions or have side effects worth naming.
- You need to prove that illegal transitions are impossible.

**Notation that matters:** `[*]` for initial and final pseudostates, `event [guard] / action` on transitions, composite (nested) states for substates, and concurrent regions when a thing is in two orthogonal states at once.

**Avoid:** Modeling control flow that isn't really state — a state diagram is about *modes of being*, not a flowchart of steps.

### Component diagram — building blocks and their interfaces

**Answers:** What are the major parts of the system, what interfaces do they provide and require, and how are they wired together?

**Communicates:** Coarse-grained static structure above the class level — services, modules, subsystems, and the contracts between them. The emphasis is interfaces (provided "lollipop", required "socket") rather than internals.

**Use it when:**
- You are decomposing the system into deployable or buildable units.
- You want to show which component depends on which interface (not which concrete class).
- You are filling arc42's Building Block View.

**Avoid:** Drilling into class-level detail. A component diagram stops at the interface boundary; what is inside a component is a separate, lower-level diagram.

### Deployment diagram — runtime topology

**Answers:** What physical or virtual nodes exist, what artifacts run on them, and how are the nodes connected?

**Communicates:** The mapping from software to infrastructure — hosts, containers, VMs, availability zones, and the communication paths (HTTPS, gRPC, queue) between them.

**Use it when:**
- You need to show where components actually run (regions, clusters, edge).
- Operations, SRE, or security need the topology to reason about failure domains and network paths.
- You are filling arc42's Deployment View.

**Avoid:** Mixing logical decomposition into the deployment picture. Deployment is about *where*, not *what the parts are* — that is the component diagram's job.

## Quick decision guide

| If the question is… | …draw a |
|---|---|
| "What are the things and how do they relate?" | Class diagram |
| "Who talks to whom, in what order, for this scenario?" | Sequence diagram |
| "What modes does this entity move through over its life?" | State diagram |
| "What are the parts and what interfaces connect them?" | Component diagram |
| "Where does each part run, and over what links?" | Deployment diagram |

## Structure vs behavior

A useful split when you are unsure:

- **Structure (static):** class, component, deployment — they describe what exists and how it is arranged.
- **Behavior (dynamic):** sequence, state — they describe what happens over time.

Most architecture documents need at least one structural and one behavioral diagram. A class diagram with no sequence or state diagram tells readers the nouns but never the verbs.
