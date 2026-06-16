# C4 Levels — when to use each, and what belongs at each

The C4 model (created by Simon Brown) describes the static structure of a software system
as a hierarchy of four diagram levels. Think of it as a set of nested maps: you start
zoomed all the way out and zoom in one notch at a time. The core abstractions, from
coarse to fine, are:

**Person → Software System → Container → Component → Code element**

- A **Person** is a human user or role (customer, administrator, support agent).
- A **Software System** is the highest-level thing that delivers value — your system, and
  the external systems it depends on. It is the unit of ownership/responsibility.
- A **Container** (nothing to do with Docker specifically) is a separately
  deployable/runnable thing: a server-side web app, a single-page app, a mobile app, a
  serverless function, a database, a message broker, a file system. If it has to be running
  for part of the system to work, it is a container.
- A **Component** is a grouping of related functionality behind a well-defined interface
  inside a container — a controller, a service, a repository, a façade. Components are not
  separately deployable; they run inside their container's process.
- A **Code element** is a class, interface, function, or similar, implementing a component.

Each diagram level shows exactly one of these abstraction bands as its "boxes."

---

## Level 1 — System Context

**Question it answers:** How does the system fit into the world around it? Who uses it, and
what other systems does it talk to?

**Audience:** Everyone — including non-technical stakeholders, business sponsors, product.
This is the diagram you put at the top of a README or a one-pager.

**Boxes allowed:**
- Exactly one box for *your* system (the system in scope), drawn as the centre of gravity.
- People (actors) who interact with it.
- External software systems it integrates with (payment gateway, email service, identity
  provider, partner APIs).

**Belongs here:** The system boundary; the actors; named external dependencies; one
labeled, directed relationship per interaction ("Sends emails using", "Authenticates via").

**Does NOT belong here:** Anything *inside* your system. No containers, no databases of
your own, no microservices, no technology choices. If you are tempted to draw your own
database or your API service as separate boxes, you have dropped to Level 2 — stop and
keep them collapsed into the single system box.

**Smell:** More than ~10–15 boxes, or internal structure leaking in.

---

## Level 2 — Container

**Question it answers:** What are the high-level technical building blocks (the separately
deployable/runnable units), what are their responsibilities, and how do they communicate?

**Audience:** Technical people inside and around the team — developers, ops, architects.

**Boxes allowed:**
- Each container *inside* your system: web application, API application, single-page app,
  mobile app, database, cache, message queue, scheduled job, serverless function.
- The same people and external systems from Level 1 (kept for orientation).

**Belongs here:** Each deployable/runnable unit with its primary technology stamped on it
("[Spring Boot]", "[React]", "[PostgreSQL]"); the relationships *between* containers with
the protocol/technology annotated on the arrow ("Reads from and writes to [JDBC]", "Makes
API calls to [JSON/HTTPS]", "Publishes events to [AMQP]").

**Does NOT belong here:** The internal structure of any single container (that is Level 3),
and individual classes (Level 4). One box per container, not one box per service-class.

**Smell:** Naming controllers/services as containers; omitting the protocol on inter-container
arrows; showing a container's internals.

---

## Level 3 — Component

**Question it answers:** What are the major structural building blocks *inside one
container*, what are their responsibilities, and how do they collaborate?

**Audience:** Developers working on that specific container.

**Scope rule:** A Level 3 diagram zooms into **exactly one** container from Level 2. You
draw one Component diagram per container that is worth decomposing — you do not put two
containers' internals on the same diagram.

**Boxes allowed:**
- The components inside the chosen container — controllers, services, façades,
  repositories, gateways, mappers — each with a short responsibility and, optionally, its
  technology/library.
- The other containers and external systems it talks to, kept as boundary context.

**Belongs here:** Components and their relationships; which component owns which external
call or database access.

**Does NOT belong here:** Classes and methods (Level 4). Components are interface-bounded
groupings, not individual types.

**Smell:** A box per class; or two containers fully decomposed on one canvas.

---

## Level 4 — Code

**Question it answers:** How is one specific component actually implemented?

**Audience:** A developer who needs the implementation detail of a single component.

**Reality check:** Level 4 is **optional and usually skipped.** It maps to a UML class
diagram (or ER diagram) for one component. It is the fastest-aging level — code changes
under it constantly — so when it is needed at all, generate it on demand from the code
(IDE / UML tooling) rather than drawing and maintaining it by hand. Draw it only when a
component's internal design is genuinely non-obvious and worth a permanent picture.

**Belongs here:** Classes, interfaces, key methods/attributes, and their relationships for
one component.

**Does NOT belong here:** Anything you would not want to re-draw every sprint.

---

## Deployment view (a sibling, not a fifth level)

C4 also defines a **Deployment diagram**, which is orthogonal to the four static levels. It
maps containers (from Level 2) onto the infrastructure that runs them — deployment nodes
such as a cloud region, a Kubernetes cluster, a VM, a browser, a mobile device. One
container can appear on multiple deployment nodes (e.g. replicated instances). Use it to
answer "what runs where." It is the natural input to arc42 section 7.

---

## Choosing fast

| If the reader asks... | Draw |
|---|---|
| "What is this system and who/what does it touch?" | Level 1 System Context |
| "What are the apps/services/datastores and how do they talk?" | Level 2 Container |
| "What's inside the API app?" (one container) | Level 3 Component |
| "How is the OrderProcessor built internally?" (one component) | Level 4 Code (prefer generated) |
| "Where does each container run?" | C4 Deployment |

Golden rule: **one diagram, one level, one question.** When in doubt, draw the higher
(more zoomed-out) level first — it is cheaper, more stable, and orients the reader before
detail arrives.
