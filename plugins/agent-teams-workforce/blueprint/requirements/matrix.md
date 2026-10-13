# The matrix: requirements

The matrix is the one record of how Epics and their PRDs, features, technical requirements
and constraints, architecture documents, services, components, infrastructure, stacks and
repositories relate to each other. This document states what the matrix must do and why. How
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
| Q9 | What does this stack use, and what uses it? | The stacks it uses and the stacks that use it, followed to any depth. |
| Q10 | Where is this stack's source? | One repository. |
| Q11 | What type of stack is this? | One type, from the stack's name. |
| Q12 | Which repositories are relevant to this Epic? | The set of repositories, each with the stacks that make it relevant and the features that lead to them. |
| Q13 | What is missing for this Epic? | Requirements with no feature, features with no covering document, and described services, components and infrastructure with no stack. |
| Q14 | Which of this is proved by a build? | For each piece of information, verified or not verified. |

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
| Epic and PRD | One Epic, by its beads id, together with its PRD. |
| Feature | One capability. PRD requirements become features; a feature is what connects a PRD to architecture. |
| Technical requirement or constraint | One obligation that architecture places on a design, including one that comes from an arc42 document other than the one that describes the feature. |
| Architecture document | One arc42 document. |
| Service, component, infrastructure | One thing the architecture documents describe. |
| Stack | The home in code of services, components and infrastructure. The primary reference point for everything implemented. |
| Repository | Where a stack's source can currently be found. An attribute of a stack. |

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

### 3.3 What is recorded about a stack

- Its purpose: what it actually does, stated so that an agent quickly recognizes where a
  piece of functionality lives. Example: the shared API client library provides consistent
  encapsulated code and helper functions to get and refresh OAuth2 tokens from client ids
  and secrets, and to wrap calling APIs with common features such as trapping and handling
  errors and retries with backoff.
- Its type: the last token of its name, as the naming conventions document defines it
  (service, infra, lib, mobile, web and so on).
- Its repository.
- What it uses.

### 3.4 Two kinds of trust

**Architecture.** An arc42 document that is effective is approved and can be trusted as of
the moment it is read. That says nothing about whether it covers the PRD in hand: the same
document may need additions as the next feature is designed.

**Implementation.** Code is verified only when a build pipeline has proved that it exists
and passes its tests. Until then existing code is a hint, and a difference between code and
an arc42 document is not a finding.

## 4. How the matrix is kept

| Point | What happens | Who records |
|---|---|---|
| Seeded | The matrix starts with what is known today: every existing stack and the repository that holds it; the purpose of each stack; every Epic and its PRD; the services, components and infrastructure the architecture documents describe, mapped to the stacks and repositories that are their home in code. | The seeding work, once, from the repositories, beads and the effective arc42 documents. |
| Filled in and corrected | As elaboration runs: the features derived from PRD requirements; which existing features and documents cover them; what the architect designs; each new or changed architecture document, mapped to the feature it supports; corrections to anything the run finds wrong. | The elaboration pipeline (`prd-to-spec`): the architect for features, design and their links; the `polyrepo-steward` for a stack's repository. |
| Confirmed | Information is marked verified once the code is tested and passes. | The build pipeline (`task-to-deploy` and the driver in `ops/sdlc-automation`), with no judgment by an agent. |
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

- **R6.** The matrix records each Epic by its beads id together with its PRD. The beads id
  is how every pipeline run names the Epic it is working.
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
  that way (section 3.2). A one-to-one mapping misstates shared architecture.
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
- **R17.** The matrix records what each stack uses, stack to stack, and answers both
  directions to any depth (Q9). This is what keeps each elaboration run's architecture
  consistent with what exists, and what keeps logic that belongs in a shared library or the
  chassis out of a Lambda.
- **R18.** The matrix takes a stack's type from the last token of its name, as the naming
  conventions document defines it. The list of types is extended in that document; the
  matrix defines no classification of its own.
- **R19.** Each classification in the matrix has values that exclude each other. A service
  can also be shared and a library can also be a layer, so "shared" and "layer" are separate
  descriptions and are never values of the same classification as a type.

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
- **R24.** The matrix marks each piece of information as verified or not verified,
  separately from every other piece.
- **R25.** The build pipeline marks information verified only when a build has proved the
  code exists and its tests pass. Nothing else marks it. No elaboration step reads code to
  decide whether something is built.
- **R26.** The matrix presents existing code that no build has verified as a hint only, so
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

## 6. Open points

1. How each stack's purpose is established, given that no accurate statement of purpose
   exists today, including in the repositories' README files.
2. Whether a technical requirement or constraint is an entry of its own or an attribute of
   features and stacks.
3. The complete list of stack types; the naming conventions document's list is probably
   incomplete.
4. How descriptions that are not exclusive (shared, layer) are recorded beside the type.
5. Which approval markers the lookups need beyond mirroring whether a document is effective
   (in review, changed since approval, approval below the level of a document).
6. Whether "verified" distinguishes built and tested from deployed.
7. What happens to a verified mark when the verified thing is changed afterwards.
8. How a PRD requirement is identified, so that coverage is recorded per requirement.
9. How "the same feature or a similar one" is found.
10. Whether "every Epic" in the seed includes closed Epics.
11. Whether a disagreement between documents and its settlement is recorded in the matrix so
    that it is not raised again.
12. Whether a single design fact, with the one arc42 heading that is its home, is a kind of
    thing the matrix records.
13. Whether a name that an arc42 document uses and nothing else classifies is recorded.
14. How two Epics elaborated at the same time are kept from changing the same thing.
15. Whether the matrix states, for a Task, the shared capabilities it must use, and whether
    the build checks for duplicates of them.
