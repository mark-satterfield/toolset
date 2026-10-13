# The matrix: requirements

The matrix is the one record of how Epics and their PRDs, features, technical requirements
and constraints, architecture documents, services, components, infrastructure, stacks, apps,
packages, layers and repositories relate to each other. This document states what the matrix must do and why. How
it is stored, read and written belongs in `blueprint/design/matrix.md`.

## 1. Purpose

### 1.1 The chain of four questions

The pipeline needs the same chain of answers for every Epic. Each answer depends on the one
after it.

1. To write a Story, the pipeline must know which repositories are relevant to the Epic.
2. To know that, it must know which services, components and infrastructure are relevant to
   the Epic.
3. To know that, it must know the architecture and software design needed to completely
   cover everything in the Epic, including requirements and constraints that come from
   other arc42 documents.
4. To know that, it must know what is already approved architecture and what is missing and
   still has to be worked out and documented. In particular: which parts of the PRD are
   covered by which approved arc42 documents.

### 1.2 Why answering by scanning fails

Without a record, a pipeline run answers the chain by scanning: it reads the code in every
repository and tries to match it to arc42 documents, searches arc42 for the Epic's or PRD's
name, or designs a new architecture and then looks for something that matches it.

- It takes a long time and uses a large number of tokens in every run.
- It often gives a different answer each run.
- It makes mistakes. Runs have re-created architecture from scratch when the documents, and
  most of the code, already existed.

SkillSpoke shares services, components and libraries and iterates on what exists. One piece
of architecture or code supports many features and many PRDs. So "what already exists for
this PRD" cannot be read from names or from one-to-one mappings. It is recorded as
relationships, in one place, and looked up.

### 1.3 The goal

No pipeline run spends tokens looking for the architecture documents or repositories that
support an Epic, because the answer is in one convenient location.

## 2. What the pipeline looks up

Each question below is answered from the matrix alone, without reading documents or code.

| # | Question | Shape of the answer |
|---|---|---|
| Q1 | Which PRD belongs to this Epic, and which Epic to this PRD? | One Epic beads id with one PRD. |
| Q2 | Which features does this PRD need? | For each requirement of the PRD, the features derived from it; and the requirements with no feature yet. |
| Q3 | Does this feature, or one like it, already exist? | The matching features, each with the PRDs it serves. |
| Q4 | Which arc42 documents cover this requirement of this PRD, and which requirements have no covering document? | For each requirement, the documents that cover it and the feature that connects them; and the list of requirements with none. |
| Q5 | Which requirements and constraints from other arc42 documents apply to this Epic? | A list of constraints, each with the document it comes from and what it applies to. |
| Q6 | Which services, components and infrastructure implement this feature? | A list of them, each with the stack that is its home in code. |
| Q7 | What does this stack do? | Its stated purpose. |
| Q8 | Where does this piece of functionality already live? | The stacks whose purpose matches, found by describing the functionality. |
| Q9 | What does this stack depend on across stack boundaries, among the project's own stacks, libraries, layers, services and infrastructure, of any kind (a shared library it imports, a layer it uses, a shared service it calls, an event it publishes or consumes and the rule that routes it, a value it reads that another stack stored, shared infrastructure it runs in), and how is each related? | A list of the things it depends on, each with the stack that holds it and the kind of the relationship, followed to any depth; for a shared library, also the distribution (package, layer) that brings it to this stack's code. |
| Q10 | Where is this stack's source? | One repository. |
| Q11 | What type of stack is this? | One type, from the stack's name. |
| Q12 | Which repositories are relevant to this Epic? | The set of repositories, each with the stacks that make it relevant and the features that lead to them. |
| Q13 | What is missing for this Epic? | Requirements with no feature, features with no covering document, and described services, components and infrastructure with no stack. |
| Q14 | Which of this is proved by a build? | For each piece of information, verified or not verified. |
| Q15 | Which of the project's own stacks, libraries, layers, services and infrastructure depend on this stack, service, component, library, layer or piece of infrastructure, and how? | A list of the things that depend on it, each with the stack that holds it and the kind of the relationship, followed to any depth. |
| Q16 | Which layers exist, what packages does each contain, and which Lambdas use each? | A list of layers, each with its packages and the Lambdas that use it. |
| Q17 | Which app does this stack belong to, and which stacks belong to this app? | One app for a stack; the list of stacks for an app. |
| Q18 | Which arc42 documents describe this service, component or piece of infrastructure? | A list of documents, each with the heading that describes it and whether the document is effective. |
| Q19 | Which stack is this Story or Task placed in and what does it build, and which Stories and Tasks are placed in this stack? | One stack with its repository and the things built; for a stack, the open Stories and Tasks placed in it, each with its Epic. |
| Q20 | What rests on this architecture document, feature, service, component, piece of infrastructure or stack? | The features, constraints and dependents that rest on it, the requirements and Epics those serve, and the open Stories and Tasks that build it. For a component, this includes which requirements of which PRDs it implements. |
| Q21 | Which other Epics share a feature, architecture document, service, component or stack with this Epic, or drive or rest on the same architecture decision? | A list of Epics, each with what is shared and how. |
| Q22 | What does this stack publish and deploy, and which commands test, publish and deploy it? | Whether it publishes a package, deploys with CDK, or both, and the three commands. |
| Q23 | Which stacks hold infrastructure of a given resource type? | A list of stacks, each with the matching infrastructure. |
| Q24 | Which expertise does this Epic need? | A list of skills. |
| Q25 | Which stacks does this repository hold? | A list of stacks. |

Illustration (invented, to show the use; it specifies nothing): a PRD asks for an email to
be sent to a recruiter. The matrix already has a feature for sending an email to a person.
That feature leads to its architecture documents, and they lead to the stacks involved: an
email service that is called by a notifications service, which accepts an event and not a
direct API call, and an EventBridge rule in an infra stack that routes one event type to the
notifications service. The finding is small and exact: the rule must also route a new event
type for recruiter emails. Nothing else is designed again.

## 3. What is recorded and how the things relate

### 3.1 The kinds of thing

This list is not complete.

| Kind | What one is |
|---|---|
| Epic and PRD | One Epic, by its beads id, together with its PRD. Every Epic and its PRD is in the matrix. |
| Feature | One capability. PRD requirements become features; a feature is what connects a PRD to architecture. |
| Technical requirement or constraint | One obligation that architecture places on a design, including one that comes from an arc42 document other than the one that describes the feature. |
| Architecture document | One arc42 document. |
| Service, component, infrastructure | One thing the architecture documents describe. |
| Stack | The home in code of services, components and infrastructure. The primary reference point for everything implemented. |
| App | One sub-folder of the project's apps directory. The scope a stack belongs to. An attribute of a stack. |
| Package | One Python package: a custom library published to CodeArtifact, or a third-party package. |
| Layer | One AWS Lambda layer. It contains packages and is used by Lambdas. |
| Repository | Where a stack's source can currently be found. An attribute of a stack. |
| Story and Task | One open Story or Task, by its beads id, placed in the stack it lands in, with the things it builds. |

### 3.2 The relationships

Any kind can relate to many of any other. That is why it is a matrix.

- A PRD has several features. A feature can serve several PRDs.
- A feature is implemented across several services and components in different stacks.
- A shared service relates to many other services and to many PRDs.
- An architecture document describes several features and several services, components and
  pieces of infrastructure; each of those can be described by several documents.
- A stack uses other stacks. Example: a service's Lambdas include the chassis, which uses
  the events service client, which uses the shared API client library.
- A stack has one repository at a time. A repository can hold several stacks.
- A stack belongs to exactly one app. An app has many stacks.
- A layer contains several packages. A package can be in several layers, and a custom
  library can be in none.
- A Lambda uses several layers. A layer is used by several Lambdas.

### 3.3 What is recorded about a stack

- Its purpose: what it actually does, stated so that an agent quickly recognizes where a
  piece of functionality lives. Example: the shared API client library provides consistent
  encapsulated code and helper functions to get and refresh OAuth2 tokens from client ids
  and secrets, and to wrap calling APIs with common features such as trapping and handling
  errors and retries with backoff.
- Its type: the last token of its name, as the naming conventions document defines it
  (service, infra, lib, mobile, web and so on).
- Its app: the one app it belongs to (section 3.4).
- Its execution use (section 3.4).
- Its repository.
- What it uses, and for each shared library it uses, the distribution through which that
  library reaches its code (section 3.4).

### 3.4 Scope, execution use and distribution

Three facts are separate from a stack's type and from each other.

**Scope.** Which app a stack belongs to. Every stack belongs to exactly one app. The apps
are the sub-folders of the project's apps directory:

| App | What it holds |
|---|---|
| `employer` | A future use case. |
| `marketing` | The marketing web site and marketing-specific stacks. |
| `personal-agent` | The core product. An alias of the SkillSpoke app. |
| `shared` | What is not specific to any one application and is intended for reuse by several. It is enterprise-wide in scope. |

`shared` is recorded as the stack's app, the same way as the other three. "Shared" is a
scope.

**Execution use.** Whether a thing is executable or callable (a service, a Lambda) or is
shared code that other code imports (a library). "Library" is an execution use.

**Distribution.** How shared code reaches the code that uses it. A custom Python library is
always published as a package to CodeArtifact. It may also be deployed as an AWS Lambda
layer. "Layer" is a distribution method.

Packages and layers relate as follows:

- Every custom Python library is a CodeArtifact package.
- Some custom libraries have no Lambda layer of their own.
- One layer can contain several packages.
- A layer can contain only third-party packages.

So libraries and layers relate many-to-many. A layer is recorded as its own thing, which
contains packages and is used by Lambdas.

### 3.5 Two kinds of trust

**Architecture.** An arc42 document that is effective is approved and can be trusted as of
the moment it is read. That says nothing about whether it covers the PRD in hand: the same
document may need additions as the next feature is designed.

**Implementation.** The matrix has one code mark: verified. It is set when a Story's code
has been built and tested and has passed, including its CI/CD and its CDK. It is recorded on
the stack and its components, with the commit. This is the whole definition. No deployed
mark and no merged mark exists. Whether something is currently deployed is not recorded and
has no bearing on verified: the environment is a development environment where stacks are
deployed and torn down freely.

A relationship that the Story's code makes real is verified with the stack or component it
starts from. "This service uses the chassis" is a relationship, and it is planned until a
build proves it.

Everything in the matrix is used, verified or not. Verified never decides whether an entry
or a relationship is read, linked to, designed against or built on. The mark changes what
the pipeline assumes, and it never blocks a step:

- **Not verified** means "this still has to be made real". The entry or relationship
  describes what is designed or planned, and it is theoretical until proven. The pipeline
  uses it like any other and assumes it may still have to be built. Existing code for it is
  a hint, and a difference between that code and an arc42 document is not a finding.
- **Verified** means "this is real". The entry or relationship describes something that
  exists. The pipeline counts on it existing, and its code is trusted.

## 4. How the matrix is kept

| Point | What happens | Who records |
|---|---|---|
| Seeded | The matrix starts with what is known today: every existing stack and the repository that holds it; the purpose of each stack; every Epic and its PRD; the services, components and infrastructure the architecture documents describe, mapped to the stacks and repositories that are their home in code. | The seeding work, once, from the repositories, beads and the effective arc42 documents. |
| Filled in and corrected | As elaboration runs: the features derived from PRD requirements; which existing features and documents cover them; what the architect designs; each new or changed architecture document, mapped to the feature it supports; corrections to anything the run finds wrong. | The elaboration pipeline (`prd-to-spec`): the architect for features, design and their links; the `polyrepo-steward` for a stack's repository. |
| Confirmed | A stack and its components are marked verified, with the commit, once a Story's code has been built and tested and has passed, including its CI/CD and its CDK. | The build pipeline (`task-to-deploy` and the driver in `ops/sdlc-automation`), with no judgment by an agent. |
| Kept current | When a stack, repository, feature or document is renamed, deprecated or removed, the matrix is updated in the same piece of work. | Whoever does that work. |

## 5. Requirements

### Lookups

- **R1.** The matrix answers every question in section 2 without any reading of documents or
  repositories, because scanning is slow, costly and gives a different answer each run.
- **R2.** The matrix gives the same answer to the same question until something recorded in
  it changes, so that two runs of one Epic start from the same facts.
- **R3.** The matrix is the one location for these relationships. No second record of them
  is kept anywhere, because two records drift apart and a run cannot tell which is right.
- **R4.** The matrix states what is missing for an Epic as exactly as what exists (Q13), so
  that the architect designs only what is missing and extends what exists.
- **R5.** The matrix finds a stack from a description of functionality (Q8), so that an
  agent that needs a behaviour finds its existing home before it designs or codes one.

### What is recorded

- **R6.** The matrix records every Epic by its beads id together with its PRD. The beads id
  is how every pipeline run names the Epic it is working. An Epic closes only after a human
  has tested it and signed off. No Epic has completed elaboration with all of its Tasks
  built, and none is signed off, so a closed Epic in beads is one created in error and is
  not in the matrix.
- **R7.** The matrix records features as things in their own right, each once, linked to
  every PRD requirement it serves. PRDs overlap, and a feature recorded per PRD would be
  designed again for each.
- **R8.** The matrix records a feature that supports other features and is named by no PRD
  in the same way as a feature a PRD names, because a shared capability is the one most
  often re-invented.
- **R9.** The matrix records coverage per requirement of a PRD: which arc42 documents cover
  that requirement. A PRD-level statement of coverage does not show which parts are missing.
- **R10.** The matrix records the requirements and constraints that arc42 documents place on
  an Epic's design, including those from documents that do not describe the Epic's own
  features, so that a design is complete without a search of arc42.
- **R11.** The matrix records the services, components and infrastructure the architecture
  documents describe, each mapped to the stack that is its home in code.
- **R12.** The matrix records every relationship as many-to-many wherever the things relate
  that way (section 3.2). A one-to-one mapping misstates shared architecture. Every
  relationship records its kind: how the two things are related. A lookup returns the kind
  from either side of the relationship.
- **R13.** The matrix records links and short statements that identify a thing. The content
  of a design stays in its arc42 document, so that the matrix and arc42 never state the same
  design twice.

### Stacks and repositories

- **R14.** The matrix uses the stack as the primary reference point: everything implemented
  is found through its stack.
- **R15.** The matrix records a repository as an attribute of a stack. Nothing in the matrix
  is identified, grouped or looked up by repository first. Stacks can all move into one
  repository, and a repository can be renamed so that its name no longer matches its stacks;
  either change alters that one attribute and nothing else.
- **R16.** The matrix records a purpose for every stack, in the form section 3.3 shows. The
  purpose is what lets an agent recognize where functionality lives, and it matters most for
  anything shared.
- **R17.** The matrix records how the project's own code and infrastructure relate to each
  other: its stacks, services, components, libraries, layers and infrastructure. Among
  these it records every dependency that crosses a stack boundary, of any kind: a
  shared library a stack imports, a layer it uses, a shared service it calls, an event it
  publishes or consumes and the rule that routes it, a value it reads that another stack
  stored, shared infrastructure it runs in. A relationship between two stacks is recorded
  whether the thing depended on is code or infrastructure. The matrix answers both
  directions to any depth: what a stack depends on (Q9) and what depends on a stack,
  service, component, library, layer or piece of infrastructure (Q15). This gives the
  pipeline the full picture around anything it designs or changes, keeps each elaboration
  run's architecture consistent with what exists, and keeps logic that belongs in a shared
  library or the chassis out of a Lambda. The third-party packages a repository installs are
  listed in that repository's `pyproject.toml` and are not recorded in the matrix as
  dependencies. A layer the project deploys is the project's own infrastructure and is
  recorded, including one that contains only third-party packages; the third-party packages
  inside it are recorded only as the contents of that layer and have no relationships of
  their own.
- **R18.** The matrix takes a stack's type from the last token of its name, as the naming
  conventions document defines it. The list of types is extended in that document; the
  matrix defines no type of its own. Scope, execution use and distribution are not types.
- **R19.** The matrix records scope, execution use and distribution as three facts, separate
  from a stack's type and from each other (section 3.4). "Shared" is a scope, "library" is
  an execution use and "layer" is a distribution method; none is a value of another fact or
  of the type.

### Current state

- **R20.** The matrix describes only what is current. Git holds history. An entry for
  something that no longer exists, or a field whose only use is to record a past state,
  makes a lookup return things that are not there.
- **R21.** The work that renames, deprecates or removes a stack, repository, feature or
  document updates the matrix in the same piece of work, so that the matrix is never behind
  what it describes.

### Trust

- **R22.** The matrix shows, for what an arc42 document describes, whether that document is
  effective. It mirrors arc42 and is not a second approval.
- **R23.** The matrix keeps "this document is approved" separate from "this document covers
  this requirement", because an effective document can be trusted and still not cover the
  PRD in hand.
- **R24.** The matrix has one code mark, verified, and records it on the stack and its
  components, with the commit. Each is marked separately from every other, and a
  relationship the code makes real is verified with the stack or component it starts from.
  A verified entry or relationship describes something that exists: the pipeline counts on
  it existing and trusts its code. An entry or relationship that is not verified describes
  what is designed or planned and is theoretical until a build proves it.
- **R25.** The build pipeline sets the verified mark only when a Story's code has been built
  and tested and has passed, and that always includes its CI/CD and its CDK. Nothing else
  sets it. No deployed mark and no merged mark exists. No elaboration step reads code to
  decide whether something is built. Whether something is currently deployed is not recorded
  and has no bearing on verified.
- **R26.** The pipeline uses everything in the matrix, verified or not. Verified never
  decides whether an entry or a relationship is read, linked to, designed against or built
  on, and it never blocks a step. The mark changes only what the pipeline assumes: an entry
  or relationship that is not verified may still have to be built, and a verified one is
  real. The matrix presents existing code that no build has verified as a hint only, so
  that an architecture agent does not treat a difference between that code and arc42 as a
  finding.

### Keeping

- **R27.** The seeding work records everything section 4 lists under "Seeded" before the
  first pipeline run uses the matrix, so that the first run already looks up and does not
  scan.
- **R28.** The elaboration pipeline records, during the run that produces them: the features
  it derives from PRD requirements, what the architect designs, and each new or changed
  architecture document mapped to the feature it supports. The next Epic then finds them.
- **R29.** A pipeline run that finds the matrix wrong corrects it in that run, so that the
  same error is not met again.
- **R30.** A pipeline step looks up what exists. A step that rediscovers what exists by
  scanning is the failure the matrix exists to remove.
- **R31.** What the matrix records is decided by what the pipeline looks up to answer the
  chain in section 1.1. A status, classification or marker is recorded when a lookup in
  section 2 needs it, and for no other reason.

### Scope, execution use and distribution

- **R32.** The matrix records, for every stack, the one app it belongs to: `employer`,
  `marketing`, `personal-agent` or `shared` (section 3.4), and answers both directions
  (Q17). `shared` is recorded as the stack's app in the same way as the other three.
- **R33.** The matrix records the execution use of a thing: executable or callable (a
  service, a Lambda), or shared code that other code imports (a library).
- **R34.** The matrix records every custom Python library as a package published to
  CodeArtifact, and records separately each Lambda layer that also carries it.
- **R35.** The matrix records a layer as a thing in its own right, with the packages it
  contains and the Lambdas that use it (Q16). The relation between libraries and layers is
  many-to-many: a custom library can have no layer of its own, one layer can contain several
  packages, and a layer can contain only third-party packages.
- **R36.** The matrix records, for each shared library a stack's code uses, the distribution
  (package, layer) through which that library reaches it (Q9).

### Growth and use

- **R37.** The matrix accepts new kinds of entry and new kinds of relationship without
  restructuring what it already holds, because the owner expects to add things not yet
  thought of.
- **R38.** No pipeline step discovers by scanning what the matrix holds. Each such step reads
  the matrix, and a change that introduces a matrix lookup removes the mechanism it replaces
  in the same change, so that the old way of finding out never runs beside the new one.
- **R39.** The matrix is read and maintained at every pipeline step where something it holds
  is needed or becomes known: in elaboration, in build, in deploy and in repository work. A
  fact that becomes known at a step and is recorded only later, or elsewhere, is found again
  by scanning.
