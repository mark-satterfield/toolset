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
| Q2 | Which features does this PRD need? | For each requirement of the PRD, the features that serve it; and the requirements with no feature yet. |
| Q3 | Does this feature, or one like it, already exist? | The matching features, each with the Epics whose requirements it serves. |
| Q4 | Which arc42 documents cover this requirement of this PRD, and which requirements have no covering document? | For each requirement, the documents that cover it and the feature that connects them; and the list of requirements with none. |
| Q5 | Which requirements and constraints from other arc42 documents apply to this Epic? | A list of constraints, each with the document it comes from and what it applies to. |
| Q6 | Which services, components and infrastructure implement this feature? | A list of them, each with the stack that is its home in code. |
| Q7 | What does this stack do? | Its stated purpose. |
| Q8 | Where does this piece of functionality already live? | The stacks whose purpose matches, found by describing the functionality. |
| Q9 | What does this stack depend on across stack boundaries, among the project's own stacks, libraries, layers, services and infrastructure, of any kind (a shared library it imports, a layer it uses, a shared service it calls, an event it publishes, the EventBridge rule that matches an event and the targets it routes it to, a value it reads that another stack stored, shared infrastructure it runs in), and how is each related? | A list of the things it depends on, each with the stack that holds it and the kind of the relationship, followed to any depth; for a shared library, also the distribution (package, layer) that brings it to this stack's code. |
| Q10 | Where is this stack's source? | One repository. |
| Q11 | What type of stack is this? | One type, from the stack's name. |
| Q12 | Which repositories are relevant to this Epic? | The set of repositories, each with the stacks that make it relevant and the features that lead to them. |
| Q13 | Which links of this Epic have nothing recorded at the other end? | Requirements with no feature, features with no covering document, described services, components and infrastructure with no stack, stacks with no repository, and things arc42 describes with no corresponding thing in a repository. |
| Q14 | Which of this is approved, and which is proved by a build? | For each piece of information, approved or not approved, and verified or not verified. |
| Q15 | Which of the project's own stacks, libraries, layers, services and infrastructure depend on this stack, service, component, library, layer or piece of infrastructure, and how? | A list of the things that depend on it, each with the stack that holds it and the kind of the relationship, followed to any depth. |
| Q16 | Which layers exist, what packages does each contain, and which Lambdas use each? | A list of layers, each with its packages and the Lambdas that use it. |
| Q17 | Which app does this stack belong to, and which stacks belong to this app? | One app for a stack; the list of stacks for an app. |
| Q18 | Which arc42 documents describe this service, component or piece of infrastructure? | A list of documents, each with the heading that describes it and whether the document is effective. |
| Q19 | What rests on this architecture document, feature, service, component, piece of infrastructure or stack? | The features, constraints and dependents that rest on it, the requirements and Epics those serve. For a component, this includes which requirements of which PRDs it implements. |
| Q20 | Which other Epics share a feature, architecture document, service, component or stack with this Epic, or drive or rest on the same architecture decision? | A list of Epics, each with what is shared and how. |
| Q21 | What does this stack publish and deploy, and which commands test, publish and deploy it? | Whether it publishes a package, deploys with CDK, or both, and the three commands. |
| Q22 | Which stacks hold infrastructure of a given resource type? | A list of stacks, each with the matching infrastructure. |
| Q24 | Which stacks does this repository hold? | A list of stacks. |
| Q27 | Which AWS resources does this Epic reach, and which stacks and repositories hold them? | A list of resources, each with its resource type, its stack and that stack's repository; the stacks grouped with their repositories; the resources no stack holds. |
| Q28 | Which SSM parameters does this stack write, and which stacks read each? Which does it read, and which stack writes each? | For each parameter the stack writes, its name and the entries that read it with their stacks; for each parameter it reads, its name and the stack that writes it. |
| Q29 | Which architecture and design documents relate to this service, or to any entry? | Every document related to the entry or to what belongs to it, each with the relationships that join it. |
| Q30 | Where do this entry's links lead? | Its links followed to any depth, in either direction, each with its type and the entry at the far end. |

Illustration (invented, to show the use; it specifies nothing): a PRD asks for an email to
be sent to a recruiter. The matrix already has a feature for sending an email to a person.
That feature leads to its architecture documents, and they lead to the stacks involved: an
email service that is called by a notifications service, which accepts an event and not a
direct API call, and the notifications service's own EventBridge rule, which matches one event
type and routes it to the service. The finding is small and exact: the rule must also match a
new event type for recruiter emails. Nothing else is designed again.

## 3. What is recorded and how the things relate

### 3.1 The kinds of thing

This list is not complete.

| Kind | What one is |
|---|---|
| Epic and PRD | One Epic, by its beads id, together with its PRD. Every Epic and its PRD is in the matrix. |
| Feature | One discrete capability of the product, recorded once (section 3.1.1). A feature is what connects requirements to architecture. |
| Technical requirement or constraint | One obligation that architecture places on a design, including one that comes from an arc42 document other than the one that describes the feature. |
| Architecture document | One arc42 document. |
| Service, component, infrastructure | One thing the architecture documents describe. |
| SSM parameter | One parameter in SSM Parameter Store, named by its path: a piece of infrastructure held by the stack that writes it and read by other stacks (R59). |
| File | A file in a repository that the architecture or design names, such as a service's saved OpenAPI document (R60). |
| Stack | The home in code of services, components and infrastructure. The primary reference point for everything implemented. |
| App | One sub-folder of the project's apps directory. The scope a stack belongs to. An attribute of a stack. |
| Package | One Python package: a custom library published to CodeArtifact, or a third-party package. |
| Layer | One AWS Lambda layer. It contains packages and is used by Lambdas. |
| Repository | Where a stack's source can currently be found. An attribute of a stack. |

### 3.1.1 What a feature is

This section is the one full statement of what a feature is. Every other place states it
briefly or points here.

- A feature is one discrete capability of the product, stated as something the product can
  do. Examples: "send an email", "export data to a file or files".
- Each feature is recorded once and is unique. No two features name the same capability.
- Features are derived from two sources: the requirements of Epics, and the architecture
  (arc42). A capability the architecture provides that no requirement names is a feature.
- One feature commonly serves several requirements, in one Epic or in different Epics.
  Example: the requirement to send each customer a daily email according to their
  preferences, and the requirement to let a customer reply by email to the person who
  interviewed them, are both served by the one feature "send an email".
- A feature is linked to the requirements it serves and reaches the Epic bead through them.
  A requirement stays recorded under its Epic. A feature has no link of its own to an
  Epic's document.
- A feature is tied to the services, components and infrastructure that make it possible,
  through the arc42 documents that describe it.

The working test for telling features apart, applied wherever a feature is derived, named
or merged:

- A condition, quality or rule about how a capability behaves ("a sent message is kept when
  its reply is slow") is a requirement or a constraint that a capability serves ("hold a
  conversation with the agent"). It is not a feature of its own.
- Two candidate features are one feature when the same part of the architecture would
  provide both and a new requirement needing either would be answered by the same thing.
- One candidate is several features when it bundles capabilities that different parts of the
  architecture provide. "Manage the profile" is too coarse when the architecture has
  distinct capabilities for entering, importing and exporting it.

### 3.2 The relationships

Any kind can relate to many of any other. That is why it is a matrix. Any entry can link to
any other, and every link has a type. A type is named, and a new type needs no list of which
kinds it may join.

- A requirement is served by one or more features. A feature commonly serves several
  requirements, of one Epic or of different Epics.
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
- Its type: the last token of its name, which the `resource-naming` command (the command in
  `ATW_NAMING_COMMAND`) knows as a stack type (service, infra, lib, mobile, web and so on).
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

### 3.5 Effective, approved and verified

**Architecture.** An arc42 document that is effective is approved and can be trusted as of
the moment it is read. That says nothing about whether it covers the PRD in hand: the same
document may need additions or changes as the next feature is designed.

**Approved.** The matrix has an approved flag. It is similar to, but is not the same as,
arc42's `effective`. What was seeded into the matrix from arc42 is not approved: the seeded
architecture is high-level, and missing details and mistakes are expected in it. Once an
Epic's elaboration has validated and filled out the architecture and design (the lower-level
details) for the Epic, all of that is approved, and the matrix is filled out or corrected for
that Epic, the matrix content the Epic reaches is set to approved. The corrections to arc42
are made with it. That content is the Epic, its requirements, every entry the architecture
side states that the Epic reaches from them by the rule of reach (what its elaboration needs,
never the closure), and the architecture-side relationships between those entries; it is the
same set the Epic's architect reviews. What is read from the repositories is a hint and is never
approved. The flag names its owner, the Epic whose approval set it, and an approval never
replaces a flag that names another Epic. The approval clears from an entry or a relationship
when anything other than its flags changes: when the entry or relationship is replaced by one
that differs, when the text that describes it in a document changes (only the entries whose
describing text changed lose the flag; the other entries the same document describes keep it,
and the move of a document to effective changes no text), and when an architecture-side
relationship is added, changed or removed (the entry it starts from loses the flag). It does
not matter who makes the change. The flag returns when an Epic that reaches the content has
its architecture and design approved again.

**Verified.** The matrix has a verified flag. It says an item has been built and tested.
Tested includes the CI checks and the CDK, and testing the CDK means testing that its
deployment works: the stacks may be deployed to the development environment, checked and
removed again, because what counts is the test that the deployment works, not that the
deployment stays. An item is set to verified when that test passes. The test passing is the
trigger. The work is committed and merged after it is tested, as a separate next step, and no
merge and no branch decides whether anything is verified. An approved change that has not yet
been built and tested is not verified.

What is set to verified is everything that was built and tested: each stack, and each
service, component, piece of infrastructure, event, package, layer and file in it that was
built, and every relationship, of any kind and on either side, that starts at one of them.
Requirements, features, documents and constraints are never set to verified by a build.
Anything a stack or a Task only uses was already verified when it was itself built and
tested.

Verified is a property of the item itself (a stack, a component, or any finer entry or
relationship), valid for every Epic that relates to it.
An Epic owns no stack and no component: an Epic is a vehicle for requirements, and many Epics
relate to many stacks and components. So verified is not a link between an Epic and its
architecture documents, and it is neither set nor held per Epic.

At the start nothing is verified, so the first builds verify everything they build. After
that, Epics and builds are incremental: the matrix holds the verified current state, only
changes show up as not verified, and only changes become Tasks.

Verification is the only way to prove that the architecture is likely to work. When the
architecture or design of something that is verified changes (for example, an existing service
needs a new feature), that item's verified flag is cleared. When the change has been built and tested,
the CDK deployment test included, the item is set to verified again. Any number of changes may
be made before the next build; the item stays not verified until a build and test covers them
all. A build leaves not verified anything that carries an approved change the build did not
build and test. The verified
flag is available on every entry and every relationship, and required on none. No deployed
mark and no merged mark exists. Whether something is currently deployed is not recorded: the
environment is a development environment where stacks are deployed and torn down freely.

**How the two flags change.** Both work like dirty bits. A known change clears a flag and
marks the item dirty; approving the architecture sets approved again; building and testing the
Story's Tasks, the CDK deployment test included, sets verified again. Each flag clears on its
own kind of change, independently of the other: approved on any change to what the matrix or a
document records about the item, verified on a change to what the item must be built as. They
are separate flags: one change may clear only approved, only verified, or each at a different
time; clearing one never clears the other. The flags sit on individual items at the finest grain the
matrix records: architecture items and design details each carry their own flags, and only the
item that changes becomes dirty. A service-to-service communication diagram that does not change
stays clean while one detail of one feature that changes in the next Epic becomes dirty.

An Epic can change the architecture at any point, and many Epics can go through elaboration
with nothing built, so approved and verified apply to every Epic, not only to what was
seeded. A relationship the code makes real is planned until a build proves it. "This service
uses the chassis" is a relationship.

Everything in the matrix is used, verified or not. Verified never decides whether an entry
or a relationship is read, linked to, designed against or built on. The mark changes what
the pipeline assumes, and it never blocks a step:

- **Not verified** means "this still has to be made real". The entry or relationship
  describes what is designed or planned, and it is theoretical until proven. The pipeline
  uses it like any other and assumes it may still have to be built. Existing code for it is
  a hint, and a difference between that code and an arc42 document is not a finding.
- **Verified** means "this is real". The entry or relationship describes something that
  exists. The pipeline counts on it existing, and its code is trusted.

### 3.6 What the owner said the matrix holds and links

The owner:

- "The matrix is like an index that help map requirement, architecture, services, repos, and more together, so that agents do not need the scan a perform complicated searches over and over just to figure out answer to simple questions like, "this repository contains the stack for this service?""
- "Regarding the matrix: It's entire purpose is to mintain a mapping (a matrix) between things to every step of every pipeline doesn't need to research and scan or rediscover what pertains the task that step is performing."
- "For an Epic, I should be able to instantly know what AWS resources are invalidated and what stacks and repos those AWS resources are in. And for each stack, I should be able to see what SSM parameters it would write. And if an AWS resource was a lambda function, I wold be able to see that the stack owns the vpc and subnets and service groups, and their SSM parameters. If a stack is a service, and the service as an AWS resource that is an AWS API Gateway API, and the OpenAI document was saved, then I should see the link to that file. I should be able to go to a service in the matrix, and find all architecture and design documents that are related to that service."
- "This is the entire concept of the matrix. I should be able to drill down into any relationships."
- "Not onnly are most connections or dependencies netween things not through events, the most are probably because of imports or API calls.  Event a lambda's connection with a VPC and subnets and security groups need to show in the matrix, especially since theVPC and subnets and security grous are in their own stact and repo."
- "Your question should be, "How can stack-B know what ssm stack-A is saving (or will saved once deployed)?" The answer for that is, it should look in the matrix."
- "Everything should be linkable to eerything else."
- "So think of nodes. A node can a have a type. And a node can link to anything else. That lonkage can also have a type. The linkage could have a verified flag. The node could have a verified flag. Neither wold be required for every situation."
- "So a node for a lambda could link to VPV (runsIn) and that VPC could be linked to a stack and that stack could be linked to it's contents, so forth and so on."
- "The entire point is that the matrix should be able to help in multiple use cases in different ways. It doesn't prevent the need to perform scans, or review or research code, or perform gap analasys beween an architectual solution and a PRD, but once we know things, and then approve and verify them, the matrix should reflect that for the next agent or pipeline to use."
- "We seeded everything with what we know today, which should eliminate hours of unnecessary research, analysis, and searching in the pipelines."
- "If resourceType is only resources, thats fine. How is it being used, that's what matters. Like I wouldn't use resourceType for and event type, or a SSM Paramater path. These slightly different. But if it's an actual AWS resource, then of course, that fine in the matrix. I just didn't likle if for routering a specialist agent."

## 4. How the matrix is kept

| Point | What happens | Who records |
|---|---|---|
| Seeded | The matrix starts with what is known today, on two sides kept apart (section 4.1): every open Epic in beads with its PRD; every requirement of each of those PRDs with the feature or features that serve it, and every capability the effective arc42 documents provide that no requirement names, as a feature; every effective arc42 document with every service, component and piece of infrastructure it describes and the stack the document says each is in; every known repository, the stacks it contains and what is in each stack today; the purpose of each stack; and every link between these that can be established now. Nothing is seeded as approved or verified. | The seeding work, once, before the first pipeline run uses the matrix, from beads, the PRDs, the effective arc42 documents and the repositories. arc42 is the authority for how the product is to be built. The repositories are the source for which stacks and repositories exist and for what is in each stack today, which is recorded as what is there, not verified, a hint (R43, R45, R47 to R51). |
| Filled in and corrected | As elaboration runs: the features derived from the Epic's requirements and from the architecture; which existing features and documents cover them; what the architect designs; each new or changed architecture document, mapped to the feature it supports; corrections to anything the run finds wrong. | The elaboration pipeline (`prd-to-spec`): the architect for features, design and their links; the `polyrepo-steward` for a stack's repository. |
| Approved | The architecture-side matrix content an Epic reaches is set to approved once the Epic's architecture and design are approved and the matrix and arc42 are filled out or corrected for that Epic (section 3.5). | The elaboration pipeline (`prd-to-spec`), in the step that promotes the Epic's architecture once its reviews pass, after the documents are set effective and the matrix is corrected. |
| Confirmed | What was built and tested, and every relationship that starts at it, is set to verified when its test passes: the CI checks and the test that its CDK deployment works (section 3.5). | The build pipeline (the driver in `ops/sdlc-automation`, when the test passes, before and apart from the commit and merge that follow), with no judgment by an agent. |
| Kept current | When a stack, repository, feature or document is renamed, deprecated or removed, the matrix is updated in the same piece of work. | Whoever does that work. |

### 4.1 Seeding

**What seeding puts in the matrix.**

1. Every open Epic in beads, each with its PRD.
2. The features (section 3.1.1). Every requirement in a PRD is recorded, with the feature or
   features that serve it. A capability the effective arc42 documents provide that no
   requirement names is recorded as a feature too. A feature is recorded once and linked to
   every requirement it serves, across Epics.
3. Every effective arc42 document. From each one: every service, component and piece of
   infrastructure it describes, and the stack the document says each is in.
4. Every known repository, the stacks each repository contains, and what is in each stack
   today: the code, packages, layers and CDK-defined infrastructure that are there now.

**The mapping.** Seeding establishes every link between those four that can be established
now:

- an Epic to its PRD;
- a requirement to the features that serve it;
- a feature to the arc42 documents that cover it;
- a feature to the services, components, infrastructure, layers, packages and stacks that
  realize it;
- an arc42 document to the services, components and infrastructure it describes;
- each of those to its stack, and each stack to its repository;
- each stack to what it depends on;
- a thing arc42 describes to the thing in a repository that corresponds to it, where one
  exists.

Seeding goes as far as what is known today makes possible. A link that cannot be established
from what exists today is left out, and it then shows up as having nothing at the other end
for that Epic (Q13). Nothing is invented to fill it.

**Two sides, kept apart.**

- The architecture side is what arc42 states. It is how the product is to be built, and it
  is the authority. Architecture and design are how you build, not a record of what was
  built. A document is effective when it is approved. Many documents are effective today.
- The repository side is what is in the stacks and repositories today. It was built by hand
  a long time ago, not by the pipeline. It is recorded as what is there, marked not
  verified, and treated as a hint. It never overrides arc42, and a difference between the
  two sides is not a finding.
- Both sides are needed and both are recorded. Every fact in the matrix shows which side it
  came from.

**Approved and verified.** Nothing is seeded as approved (section 3.5). Verified means all
tests pass, including the CDK tests and any CI/CD (section 3.5). No build is verified today,
so nothing is seeded as verified.

**When.** All of this is in the matrix before the first pipeline run uses it.

**Why it must be there before the first run.**

- For each Epic the pipeline asks the matrix what exists. If the matrix has not been seeded,
  a run cannot tell "this does not exist" from "this was never recorded", so it designs
  architecture that is already effective and plans code that is already in a repository.
- SkillSpoke shares almost everything: one service, component or library supports many
  features and many PRDs. A first run that cannot see the shared pieces invents its own, and
  every Epic after it builds on the duplicate or invents another.
- A run that cannot look something up scans, which is slow and costly and gives a different
  answer each run.
- A pipeline run is long and expensive and must make real progress.
- The mapping matters as much as the entries. One absent link in the chain from Epic to PRD
  requirement to feature to arc42 document to service or component to stack to repository
  breaks the answer to "which repositories are relevant to this Epic" (Q12), even when both
  ends are recorded.

## 5. Requirements

### Lookups

- **R1.** The matrix answers every question in section 2 without any reading of documents or
  repositories, because scanning is slow, costly and gives a different answer each run.
- **R2.** The matrix gives the same answer to the same question until something recorded in
  it changes, so that two runs of one Epic start from the same facts.
- **R3.** The matrix is the one location for these relationships. No second record of them
  is kept anywhere, because two records drift apart and a run cannot tell which is right.
- **R4.** The matrix hands the architect the Epic's own brief: its requirements, its
  features with the arc42 headings that describe them, the entries that realize them with
  their stacks and repositories, and the constraints that apply to those, not the impact view
  of everything the Epic reaches. The architect runs `atw-matrix impact --id <id>` itself for
  an entry it means to change (Q19). The brief states which realizers have no stack as exactly
  as it states what exists (Q13). The architect's question is then plain: here is the current architecture, here are the new
  requirements; what should the architecture be so that it does everything the current
  architecture does and also meets these requirements? (R52 to R55.)
- **R5.** The matrix finds a stack from a description of functionality (Q8), so that an
  agent that needs a behaviour finds its existing home before it designs or codes one.

### What is recorded

- **R6.** The matrix records every Epic by its beads id together with its PRD. The beads id
  is how every pipeline run names the Epic it is working. An Epic closes only after a human
  has tested it and signed off. No Epic has completed elaboration with all of its Tasks
  built, and none is signed off, so a closed Epic in beads is one created in error and is
  not in the matrix.
- **R7.** The matrix records features as things in their own right, as section 3.1.1 defines
  one: each a discrete capability, each once and unique, linked to every requirement it
  serves, in one Epic or in several. A feature reaches an Epic through the requirements it
  serves and has no link of its own to an Epic's document. Requirements overlap, and a
  feature recorded per requirement or per Epic would be designed again for each.
- **R8.** The matrix records a feature derived from the architecture in the same way as a
  feature a requirement names. That includes a capability the architecture provides that no
  requirement names, and a feature that supports other features, because a shared
  capability is the one most often re-invented.
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
  publishes, the EventBridge rule that matches an event and the targets it routes it to, a
  value it reads that another stack stored, shared infrastructure it runs in. A relationship between two stacks is recorded
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
- **R18.** The matrix takes a stack's type from the last token of its name, which the
  `resource-naming` command (the command in `ATW_NAMING_COMMAND`) knows as a stack type. The
  types are extended in that command; the matrix defines no type of its own. Scope, execution use and distribution are not types.
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
- **R24.** The matrix has two flags, approved and verified (section 3.5). Approved is
  similar to, but is not the same as, arc42's `effective`. The verified flag is available on
  every entry and every relationship and required on none. A verified entry or relationship
  describes something that exists: the pipeline counts on it existing and trusts its code. An
  entry or relationship that is not verified describes what is designed or planned and is
  theoretical until a build proves it.
- **R25.** The build pipeline sets the verified flag on what was built and tested and on every
  relationship that starts at it (section 3.5), when its test passes. Tested always includes
  the CI checks and the CDK, and testing the CDK means testing that its deployment works; the
  deployment may be removed again after the test. The test passing is the trigger: a merge is
  not, and neither a merge nor a branch decides verified. The flag is a property of the stack
  or component, or of a finer entry or relationship, valid for every Epic that relates to it,
  and is never set per Epic. A change to what a verified item must be built as clears its flag
  on that item alone, independently of the approved flag, and the next build and test of the
  item sets it again.
  Nothing else sets it. No deployed mark and no merged mark exists. No elaboration step reads code to
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

- **R27.** The seeding work records everything section 4 lists under "Seeded" and section
  4.1 states (R47 to R51) before the first pipeline run uses the matrix, so that the first
  run already looks up and does not scan. Section 4.1 gives the reasons: an unseeded matrix
  cannot tell "this does not exist" from "this was never recorded"; a first run that cannot
  see the shared pieces invents its own; a run that cannot look something up scans; a
  pipeline run is long and expensive and must make real progress; and one absent link in the
  chain breaks the answer to which repositories are relevant to an Epic.
- **R28.** The elaboration pipeline records, during the run that produces them: the features
  it derives from the Epic's requirements and from the architecture (section 3.1.1), what
  the architect designs, and each new or changed architecture document mapped to the feature
  it supports. The next Epic then finds them. Seeding derives features from the requirements
  of the Epics that are open at seeding and from the effective arc42 documents (R47);
  elaboration derives the features of every Epic created after seeding, and adds to
  or corrects the features of an Epic it runs, so that each stays one discrete capability
  recorded once.
- **R29.** An elaboration run that finds the matrix wrong corrects it in that run, so that
  the same error is not met again. A build or deploy run reports what it finds wrong and
  changes nothing but the verified mark (R46).
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
  is needed or becomes known: in elaboration, in build, in deploy and in repository work. In
  build and in deploy the one thing maintained is the verified mark (R46). A fact that
  becomes known at a step and is recorded only later, or elsewhere, is found again by
  scanning.

### Stories and Tasks

- **R40.** The matrix records no Story and no Task. Beads is the authority for both.
- **R41.** A Task states in full what it builds, using the matrix's ids for the stack, the
  components and the shared capabilities. Elaboration reads the matrix to write that into
  the Task, and may reference architecture documents and other detail the matrix led it to.
- **R42.** Three things are answered by a script that reads open Task beads and matches
  their ids against the matrix, not by entries in the matrix: which entries a Story built
  (for the verified mark); which open work from other Epics touches an entry; which open
  Tasks a change affects.

### Sources

- **R43.** The matrix records two sides and keeps them apart (section 4.1). The architecture
  side is what arc42 states about implementation structure: the stacks and what is in each
  stack; which Lambdas use which layers; which infrastructure of each resource type a stack
  holds; every dependency that crosses a stack boundary. arc42 is the authority for all of
  it. It states how the product is to be built, and architecture and design are how you
  build, not a record of what was built.
- **R44.** No pipeline build has happened. Everything now in the repositories was built by
  hand a long time ago, not by the pipeline. Most repositories have little or nothing in
  their CDK, and few have a layer.
- **R45.** The repository side is what is in the stacks and repositories today: the code,
  packages, layers and CDK-defined infrastructure that are there now. The packages recorded
  are the project's own packages and the layers; the third-party packages a repository
  installs stay out (R17). It is always recorded,
  for every stack, and not only where arc42 lacks information. It is recorded as what is
  there today, marked not verified, and treated as a hint. CDK code in a repository, or a
  synthesized CDK assembly, is never the authority for anything: the repository side never
  overrides arc42, and a difference between the two sides is not a finding. What is there is
  counted on as real only when the entry reaches the verified state (section 3.5, R24 to
  R26).
- **R46.** A stack's facts do not arrive later, when its Story deploys. Seeding records both
  sides before the first pipeline run (R27), and elaboration records what the architect
  designs or reads. A deploy adds no new facts to the matrix. The build pipeline sets the
  verified mark and nothing else.

### Seeding

- **R47.** Seeding records four things, each in full as section 4.1 lists them: every open
  Epic in beads with its PRD; every requirement of each of those PRDs with the feature or
  features that serve it, and every capability the effective arc42 documents provide that
  no requirement names, each feature recorded once and linked to every requirement it
  serves, across Epics (section 3.1.1); every effective arc42 document with every service, component and
  piece of infrastructure it describes and the stack the document says each is in; and every
  known repository with the stacks it contains and what is in each stack today, which is
  the code, packages, layers and CDK-defined infrastructure that are there now.
- **R48.** Seeding establishes every link between those four that can be established now:
  an Epic to its PRD; a requirement to the features that serve it; a feature to the
  arc42 documents that cover it; an arc42 document to the services, components and
  infrastructure it describes; each of those to its stack, and each stack to its repository;
  each stack to what it depends on; and a thing arc42 describes to the thing in a repository
  that corresponds to it, where one exists.
- **R49.** A link that cannot be established from what exists today is left out. It then
  shows up as having nothing at the other end for that Epic (Q13). Nothing is invented to
  fill it.
- **R50.** Seeding records both sides, because both are needed. Every fact in the matrix
  shows which side it came from, the architecture side or the repository side, and a lookup
  returns the side with the fact.
- **R51.** Nothing is seeded as approved or verified. Verified means all tests pass,
  including the CDK tests and any CI/CD, and no build is verified today.

### The architect and the matrix

- **R52.** The answer to the architect's question (R4) is a design judgment by the
  architect. The matrix does not compute it. What comes out is whatever the answer requires:
  for a given requirement that can be nothing (what exists already meets it), something new,
  or a change to something that exists.
- **R53.** A change to something that exists reaches every feature, PRD and Epic that shares
  it. The architect looks up what rests on it (Q19) and which other Epics share it (Q20)
  before designing the change.
- **R54.** Instructions to the architect do not use steering words such as "missing",
  "extends" or "delta" to describe the design task. Such a word tells the architect how to
  approach the problem before it has looked at it.
- **R55.** The lookup of links with nothing recorded at the other end (Q13) stays, under
  plain wording. It is one input to the architect's judgment and is not the design task.

### Events

- **R56.** An event is not infrastructure and not just a name: it is a fact with a meaning.
  An architecture-side event states its description, as its purpose, and its publishers,
  both as the event catalog in arc42 section 6 states them: the services or components that
  publish it, or, for an event published outside SkillSpoke, that outside system
  (`externalSource`). A publisher calls the events API and knows nothing of the rules that
  match the event or their targets. Its stack is its
  publisher's architecture-side stack; it has no home of its own, and it is built as part of
  the service that publishes it, never as a Story or a Task of its own. The repository side
  never decides what is built: a repository-side fact reaches the Tasks only as a labelled
  hint.

### Architecture approval

- **R57.** The approved flag (R24) is the one record of approval in the matrix: no second
  approval mark exists beside it. It is set on the architecture-side matrix content an Epic's
  elaboration reaches once the Epic's architecture and design are approved and the matrix and
  arc42 are filled out or corrected for that Epic. It is separate from verified, which says
  an item was built and tested, the test that its deployment works included, and each clears
  on its own kind of change. Any change to an entry or a relationship other than to its flags
  clears it on that item alone, whoever makes the change, as section 3.5 states, until an Epic that reaches that content has its architecture and design
  approved again. No session sets it by hand. Nothing is approved today.

### Links and resources

- **R58.** Any entry can link to any other, and every link has a type (section 3.6). A link
  type is named and checked by its form, never by a list of the kinds it may join or of the
  types that exist, so a link of a new type is recorded the day it is needed and a misspelt
  type is still caught. A type the matrix declares carries its reverse name and attributes; one
  it does not declare is recorded with no attributes.
- **R59.** Each SSM parameter is its own entry, named by its path, held by the stack that
  writes it and linked from each entry that reads it (`reads`), so that a stack that needs
  another stack's value finds its name in the matrix (Q28).
- **R60.** The matrix records the links section 3.6 names: a Lambda function to the VPC,
  subnets and security groups it runs in (`runsIn`), each held by its own stack and that
  stack's repository; imports and API calls between any two entries (`imports`, `calls`); an
  API Gateway API to its saved OpenAPI document (`specifiedBy`, to a document or to a file in a
  repository); a service to every related architecture and design document; and an Epic to
  the AWS resources it reaches, with their stacks and repositories.
- **R61.** `resourceType` names the kind of one actual AWS resource, and nothing else: not a
  bundle or set of resources, a code construct, a module, a package, a data set, an event
  type or an SSM parameter path. It is checked by its form, not by a list, so a resource of a
  kind not held before is named the same way. Nothing routes a specialist agent by it.
- **R62.** The matrix answers Q27 to Q30 from the matrix alone, without a scan (R1).

