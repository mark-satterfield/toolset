# The pipelines

## What the pipelines are

There are three pipelines. Each works one kind of bead and hands its result to the next.

| Pipeline | Runs once per | Takes in | Produces |
|---|---|---|---|
| Elaboration | Epic | A ready Epic and its PRD | The architecture and design the PRD needs, the TRD, a Spec and a Story for each repository the Epic's work reaches, and the Tasks under each Story, scored and ordered |
| Build | Task | A Task with its build contract, on its Story's branch | The Task's code and tests committed to the Story's branch, with the repository's whole test suite passing |
| Deploy | Story | A Story whose Tasks are all built | The Story's repository published and deployed to the development environment and verified, the record of what was built, and one merged pull request |

Every unit of work the pipelines do is an Epic, a Story or a Task, and reaches a pipeline
as one of those.

## The Elaboration pipeline

### The owner's requirements

The owner's statements below are the requirements of the Elaboration pipeline, quoted as
given from the owner's messages of 2026-10-19 (the last TRD statement is dated 2026-10-20
UTC). They are not reinterpreted, softened or summarised. Where the tooling or another
blueprint document differs from them, the tooling or that document is what changes, and a
requirement that cannot be met as written goes back to the owner.

The owner: "None of this is a new requirement. The requirements have been consistent, but, for some reason, Claude Code seems to want to streamline the process, and it's just more complex that Claude Code wants it to be." and "Unfortunately, there is no quick-and-easy way to do this."

#### Agents may start agents

The owner: "That's our plugin. That's our plugin.  Why the helldoes it say "an agent started by another agent starts no one"" and "If so, add "remove the insane  "an agent started by another agent starts no one" statement."

The owner: "Yeah. Let's be clear about this. I do prefer to spin up agents in headless claude sessions to do work, and then get out." and "I know a subagent can start a workflow with subagents, etc.  There can be nested subagents."

#### What architecture covers

The owner:

- "When I've said architecture in this project, I've always included everything from a high-level network diagram, to the design of the classes, object models, APIs, database column, data types, etc."
- "I always included everything."
- "Because of I always put everything under the same umbrella for architecture, I ended up with a blindspot on this project when I realized that Cloude Code (and probably language in the arc42 framework and skills) was forcing architecture to stay at a high level of abstraction."
- "As I work through this for you, it tells me that my first instinct of call all high, medium, and detailed architecture and design needs to happen when during what we call "architecture"."
- "arc42 holds archutecture and design documents. This can include standards, constraints, diagrams, or more."
- "But we need a lot of the details to be documented in in the vault somewhere. If arc42 isn't the right place then we need to create a cononical place ASAP."
- "We can't just have each individual spec not know about the decisions of any previously built spec."
- "All of these details that I thought were already in the Architecture documents and matrix, and now I'm understanding are postponed decision until spec authoring, still need be documented and stored in the matrix,"
- "I also know for a fact that some things that are in arc42 (whis is deemed architecture only for some reason), does contain some details already that ae postponed to sec authoring. This means, the spec authors are very likely to re-invent a decision that has already been made because that information wasn't provided to them because it was considered to be too detailed for the architecture phase."
- "The matrix isn't (just) for architecture in arc42" and "I has to include the alot of the details from the design step, too."
- "All of those specialest agents that weren't happening until spec writing still have to be done before you know what repos can be determined."

The owner decided: "So, I think we push everything that was considered design and not architecture up so they happen all at the same time, and the only distinction is where the documents are stored: the things that go in arc42 go there, and the rest go wherever you decided it should go."

On rule A12 of `skills/effective-architecture/review-standard.md`, the owner: "Even this is hardcoded: " Rule A12 keeps architecture documents free of route paths, fields, keys, schemas and parameter names. "  I don't know what Rule A12, or where it even exists, but I guarantee it is a list of very specific things."

On architecture documents, which follow the owner's `diagram-and-model-types.md` (with `architecture-documentation-model.md` beside it), the owner: "You are trying to create single bespoke documents like you are creating a checklist.", "Noit everything is a service. Not everything is an API. In fact, most repos aren't services.", "So it's not just about open apu schemas and service diagrams.", "There are diagrams that need to be created and then enhanced or updated as each item is built.", "There are diagrams that only pertain to a single component.", "There are doagrams that should only pertain to a single feature." and "There are diagrams that show how components work together."

Where detailed design lives, the owner: "There may be some things in arc42 that you or others may deem to be lower-level or too detailed for arc42. I want you to figure a home under `/docs/tech/architecture` somewhere. Use `filing-clerk`. I want you to help build out and organize (with the `filing-clerk`) the architecture under `/docs/tech/architecture`. This is really where all of our detailed architecture and for anything that doesn't qualify for `arc42`."

#### Architecture, the PRD, arc42 and the matrix

The owner:

- "This statement is not true, and was never true, and I only ever explain to the contrary: ""The matrix holds the Epic's requirements"!"
- "And then you go on to say "Open the PRD only for something specific the matrix does not hold". let me ask you this retorical question. How would you know if the matrix had everything that needed to exist, if you didn't open the PRD? Think about that."
- "Normally, architecture needs to read the PRD for the Epic, then it would use both the arc42 documents, and the matrix as a resource to try to build out the architecture for the PRD."
- "In the pipeline, the architecture can look at the requirements and features as a shortcut, but remember, that only exists because we seeded the information. In the future, that would not have been done yet."
- "When existing data is populated in the matrix for an epic, that is not approved and not verified, then the architecture agents still need to do some due diligents to review ecerything and see if there are gaps."
- "The matrix is to help speed up gathering what we alrdeady know, but it can't show us what we not uet knnow."
- "Normally no infomration will be in the matrix at all for an Epic, and it gets populated as the pipelines run, where each learnine piece of information is to help the next step in the pipelines."
- "We, however, preloaded known information to help speed things up for our initial Epic poplulation."
- "If we hadn't of seeded the architecture (arc42) and matrix, then the pipeline would functin the same way, except that elaboration pipeline run would look in the matrix for the epic is working on, and find nothing.  This would actually be normal."
- "arc42 is fine. the matrix is fine.", "arc42 is both input and out. The matrix is both input and output." and "What is in arc42 and the matrix are not "end results" in their curreent state. They are the starting point."
- "It will not be 100% complete, and it may not be 100% accurate in it's current state, but that's ok. The architecture process is designed to clean up the matrix is it works, and the same with the build."
- "Here is the order of operations when an Epic goes through elaboration: 1. Existing Architecture is read and understood and compared to the PRD 2. Analysis occurs, and any gap in the existing architecture is generated and approved to fullfil the needs of the PRD. 3. Aything new or changed is updated in the matrix."

On repositories, the owner:

- "But the architect skips steps when it immediately looks at the repositories.  Those repositories are only based on the high-level architecure and none of the detailed design."
- "Retorical question: "How would architecture know which repos are needed until it knows which resources are needed? I want to remind you that not all repos have stacks."
- "This means that the detailed-desgnn has to be completed and details added or updated in the matrix, and as part of that, all resources or components or whatever will need a repository."

#### There is no specialist gap

The owner: "I think Claude Code incorrectly interpreted gaps as `specialistGaps`.  There should be not such thing as a specialist gap.  The specialized agents are a tool and are very important, but, and I keep repeating this, and Claude Code simply is refusing to take this to heart: The solutions architect is responsible for all architecture for the agent. There is no `specialistGaps` there are no gaps.  that architecture agent must use all of its tools and resurces and produce and approve the architecture."

#### Choosing specialists takes reasoning, and every agent has a reason to be used

The owner:

- "There has to be some sort of reasoning or expertise or decision making to even know which specialist to use."
- "What I do not want is python code deciding which specialists to use, because pythin doesn't have the reasoning to make that determination."
- "I also do not want a pipeline that blindly sends everything to ever agent, whether it applies or not, which is exactly was was happeing in the pipeline."
- "I saw every single Epic spend 45 minutes in a DynamoDb phase, even if there was no need."
- "Ever agent needs to have a reason to be used."
- "For architecture, that reasoning agent is supposed to be the solutions architect, but I'm not sure how that works currently."
- "When I see you type "Workflows start the specialists directly.", my first questions is, how does the python know which secialest to use?"

The owner gave two examples. In the first, "Instead of the architecture agent going to each of the specialty agents, it would pass on what it needs (a request) to a single agent, the lead for Data Persistence and Storage." and "That lead would have expertise for the doman, but to rights or abilities to actually do any work, other than orchestration. It would decide which agents in its team would need to be involved." In the second, "When the agent ends its work, it passes back a json containing information, and it includes a ist of services that needs specialist attention (like SQS)." and "The worflow sees SQS in the list of topics needing expertise attention, and send all of the information in the json to the  SQS specialist." The owner: "One of the these examples, as an Agent orchestrating all of the work, and the other has the agent only making hight-level decisions for something, and then then a specialist works on the details." and "Neither one of these scenarios are perfect or fool proof." Of the first, after describing the hours that reviewers, adversarial reviewers and iteration took: "So I'm not necessarily interested in an agent orchestating with autonomy like this."

The owner decided:

- "I also do not like the concept of resourceType. Thast is the wrong thing."
- "I think the architecture agent can continue to use subagents for basic questions and quick responses."
- "We can add a skill that the architecture agent can use, and the skill has all specialized agents in it (like a table or json file) with descriptions, and the architecture can find agents that way."
- "If the architecture agent needs needs actual work to be done by a specialized agent outside of the architecture agent's headless claude code session, then it can pass the agent and request in the results, and the code can route the request to the agent by name (not by resourceType)."
- "In other words, let the architect decide whih agents are needed."

On resource types, the owner:

- "I am just now learning abou this concept of "resource types". Which makes we think you (Claude Code) wrote code to almost arbitrarily route responsibilities for certain AWS resources to specific agents, whether that agent is equiped for it or not.  This angers me. At the very least I would have likeed to been given the opportunity to update the agent or perhaps create some new agents."
- "Why are resource tyoes in an agent's front matter?  Since when is that a standard subagent yaml front matter field for a Claude Code subagent?"
- "But how we we know if we need a postgressql expert (which we just created an agent to be).  What if the architecture calls for us to to build a container using KMS? I doubt that's even in hour hardcoded resourceType list."
- "This is the problem with Claude Code wanting to base our architecture workflow on our existing architecture, and then limiting and hardcoding the lit of resources to what we have today, and not what we could have tomorrow."

On "lean", the owner:

- "I need to remind you of why I wanted the specialest agents. Specific instructions and skills and expertise and tools, small context, and focused scope and responsabilities."
- "In my experience, the general default training data for Anthropic models isn't good enough when it comes to a lot of specific topics."
- "Without spreading the work to specialist agents, a generic agent ends of doing way too much of the work, filling up it's own context, and then making horrible decisions and producing horrible results"
- "So "Lean by default" often translates into generic with few agents doing too much work."
- "I can't afford to constantly refact the pipelines evey 2 weeks."
- "I need a working pipeline, and for 2 months, you, Claude Code, whatever agent I'm working with at the time, as struggled to give me something that works, and dosn't take 2 hours to run through a single Epic."

On contracts, the owner: "the biggest obstcle ended up being the contracts  through which the agents communicated.  One agent would ignore the specifics of a results contract, and then it's reviewer wouldn't pass the review because of small difference in a json string." and "i'm a huge fan of the contracs being deterministic in files and code, and for agents, a skill can contain both schemas and een the code to read and write and verify the schemas."

On `resourceType` in the matrix, the owner: "If resourceType is only resources, thats fine. How is it being used, that's what matters. Like I wouldn't use resourceType for and event type, or a SSM Paramater path. These slightly different. But if it's an actual AWS resource, then of course, that fine in the matrix. I just didn't likle if for routering a specialist agent." The matrix work is in item 1.13.

#### Evidence that the AWS tools, best practices and the Well-Architected Framework were applied

The owner:

- "2 things I want to note, and that is I want to know that aws-mcp (which include cost analysis) and any other specialized mcp servers, skills, and tools are used."
- "If the architecture defines some architecure the includes  AWS resources, then I need to know it was blessed or reviewed with the AWS tools."
- "I need to inow that all best practive, security best practices were followed, and I would recommend how decisions were made, how we know best practices or whether it was reviewed for AWS well-architected principles be documented in arc42 or at least logged."
- "Is there any indication that the solutions architect used the the mws-mcp or any other skills or tools?"

#### The approved, verified and effective states

The owner:

- "The documents architecture documents have a field in the front matter that whether the architecture is `effective` or `in-review`.  When it is `effective` it means (and please pay attention to this) the document has been approved by the architecture agent responsble for approving the architecture. It does not mean that architecture document is fixed, or static, or permenant, or unchangable.  It means, for this exact mement in time, until something else changes it, this is have been approved."
- "We seeded a bunch of architecture documentation in arc42 that we consider approved (a.k.a. `effective`). Reminder, this means, until something in the architecture changes for any reason, that for the moment you are reading it, it has been approved."
- "A network diagram may not change very often and sit perpetually in an `effectve` or approed state, and a diagram for a specific Epic may get generated once, set to effective and never touched again." and "But some documents, like a diagram for an entire echo system of AWS Services, for example, may get updated every single time an Epic goes through elaboration, constantly flipping from `effective` to `in-review`."
- "The matrix stores relations between Epic (PRDs), architecture (docuemnts), resources, stacks, repos, infra, and more)"
- "The matrix does not include stories and tasks (it isn't a build tracker), and it doesn't care about what has actually been deployed."
- "The matrix has 2 flag fields that help determine the states the information in the matrix. I do not recallk the exact names, but there is one for verified, and one for approved."
- "The approved flag is similar to, but IS NOT the same as the `effective` field in arc42."
- "Because arc42 has been seeded with architecture, and because we know that arcchitecture is somewhere high-level, we expect there to be missing detals and maybe even mistakes. so the initial state of what we seeded in the matrix (using arc42 as a source) is not approved."
- "Once an Epic flows through elaboration, and validates and fills out the architecture and design (lower-level details) for the Epic, and then all of that is approved, and when information in the matrix is filled out or corrected for that Epic, then if gets set to approved. Any updates or corrections to arc42 must also be made."
- "The verified flag remain false or unverified. This means we have an approved, but unverified architecture for that Epic as documented in the matrix, but none of has been verofied by building and testing."
- "Once all of the tasks for all of the stories for and Epic have been built and tested (including CI (CDK), which means deployemen must also work), then all of the architecture and rellationships for the Epic can be set to verified."
- "It isn't just because we seeded the arc42 and matrix to help speed things along that we need to worry about approved or verified, at any point in time, and Epic progress through the pipeline and change the architecture. In fact we can process 20 Epics through elaboration with out building anything.  Verification is the only way to prove tht the architecture is likely to work."
- "That's why verified flag is available to just about anything." and "The linkage could have a verified flag. The node could have a verified flag. Neither wold be required for every situation."

#### The TRD is written, then updated, during architecture

The owner's statements about the TRD, in date order, quoted as given:

- 2026-10-19 18:41 UTC, reporting what a session had said: "I know you said the pipleine leaves out details like openapi, and data models, and database keys, and things like that until after the architecture and TRD are done."
- 2026-10-19 20:40 UTC: "Regarding the TRD: I know I've spoken before about TRD, stating that the TRD probably has be written and then updated if necessary. The TRD drives architecture, some information in the architecture (like standards and contraints) aslo drives the TRD."
- 2026-10-19 23:59 UTC: "I really think I've address TRD twice now, and you are ignoring what I've said"
- 2026-10-20 00:24 UTC, the TRD process:

  > I think the TRD actually gets written and updated in a few phases.
  >
  > Note: I do have future plans to add a separate TRD input document that will go along with and Epic allowing me, the human, to add some technicl guidence and influence for an Epic that isn't directly part arc42 constraints, and because TRD is an artifact that is being actvely written and updated during the pipeline, I do not want to simply write a TRD the same we we write a PRD. But do not focus on this now, I am just mentioingn it in case you want to offer up alternatice processes for the TRD. There is a reason I'm making some of the choices I'm making, and that's to better set us up for something I want to do in the future.
  >
  > **TRD - Initial write**
  > While a Product Requirements Document (PRD) focuses on what the product should do (functional requirements), a TRD focuses on reuirements not considered functional. NFRs act as the quality constraints and operational boundaries that the technical architecture must support. Since many of these are already pre-written in the arc42, they can be easily added to a TRD as one of the very first steps. Note: This is also where we would pull in that human-written Epic-epecific guidence.
  >
  > **TRD Architecture Update**
  > Once the architecture docs are completed (this would be the higher-level architecture that would be in `arc42` that isn't considered detail or design), the TRD would be updated again to reflect technical or architecture decisions made that would impact the detailed design.
  >
  > I'm doing all of this assuming that we are using the TRD as a source of information that impacts any detailed design and build decisions.

#### The spec

The owner:

- "A spec's delta NEVER was supposed to come from an architecture delta."
- "The architecture and design comes before the build. Think of the everuything in terms of version numbers."
- "1. v1.0.0 of the architecture for a specific service is developed.  A spec needs to get the build (meaning the code, IaC, etc) up to the architecture's version for that service (this is where the verified flag comes in to play). 2. Let's assunme want to update the architecture for that same service for a new Epic, making the architecture for that service v1.0.1.  In this case because the v1.0.0 architecure for that service is verified, the spec can focus on the delta between v1.0.0 and v1.0.1. 3. Now let's update the architecture again for that service to v1.1.2 on behalf of another Epic 4. But another Epic goes through architecure, before the build of v1.1.2, and makes another change, brining the architecture for that serivce to v1.1.3. 5. Now when the spec is written for an Epic, it sees that the architecture for that service is no longer verified."
- "This is not an easy or perfect processess to keep track of, and even the verification flag concept isn't perfct, but it help us to know whether what is currently buit matches the architecture and design."
- "No every Epic requires an architecure change.  An epic could contain only changes to the wording of text on a page in the web app.  No architecture change is requured, but there still needs to be a spec with instuctions for the wording change."
- "And, I don't care what kind of software engineering agent is writing the code, even if it has only the specific steps in a task that it needs to perform, it should still have access to the full architecture for the component that it is working on. This is why the specs needs to have links the that architecture (and design) documents."
- "I think right now, a bunch of stuff got stuffed under spec writer." and "The spec writer wasn't supposed to be the lead detail-level engineering designer. It was supposed to be a specialest that could write a spec document."

#### The build trusts upstream

The owner:

- "Since Day 1, my requirement has been that as much as possible should be written into the specs and tasks, so that the build has little to no decisions to make. Everything that can be passed on to the build and determined in advance, should be."
- "That doesn't mean every single build detail has to be made in advance. But the decisions that are made in advance shouldn't be "hidden" from the build agents. I have also been very clear in this: all details do not need to be copied into the tasks and specs (file paths, URLs, etc. can be used to point to the more detailed information). However, the task should be detailed so that the build doesn't need to guess or interpret or decide on how to do anything that was already concluded upstream in the elaboration (and architecture) pipeline. And when I say task, I also mean spec."
- "I'm not sure why the cdk-stack-author and api-gateway-cdk-implementer needs the skill or to name anything.  The tasks that build pipeline read, should already have all names in it, right?  Am I missing something?"
- "Maybe leaving the skill in place can ba a backuo, but I don't want to encourage an agent to start naming things, when the names should have already been provided in the task (or spec)."
- "No. We aren't deleting the `resource-naming` skill."
- "I wouldn't expect a missing name.  Thinkl about it.  If the matrix says an Epic (PRD) will use 2 services, then the architecture and matrix shouldn't say "service-1" and "service-2". They should have actual names."
- On a missing name reported as a spec gap: "This may be a little heavy-handed. For example, there may be some information that just simply isn't known until deploy time, such as the region or environment where we are deploying. We don't want to stop because of that. We need to make sure some of that is accommodated and handled at run time (deploy time). And, I don't want every subsequent step in a process constantly checking that upstream steps were done right."
- "There are many circumstances where this is appropriate (like if B is going to be a universal or shared component), but that isn't always the case. Your default is fault-intolerant. I need more fault-tolerance for the pipeline, and need more trust."

#### The agent roster

The owner:

- "I had created tons and tons of hyperspecialized agents, with the intent that each agent was responsible for a fixed domain." and "I then create more generic or parent-level agents for the specialized agents. And th idea was that the parent-agents would ue the specialists."
- "Do you know why I specifically designed a lot of specialized subagents?" "It's because I wanted to keep their context small.  I wanted to be able to put specialized skills, mcps, and instructions in them that were targeted to their specific responsibilities. Any addition context information is an opportunity for conflicts and misunderstanding,"
- "I wouldn't want clog up an agent that was responsbile for SQS Queues and SNS Tpics with information and instructions for EventBridge Busses."
- "If you look at these subagent markdown files, there is quite a bit of basic boilerplate language, and may 1 line that tell the agent what it does." and "It seems like 99% was still coming to the agent as prose."
- "Taking something, in this case a subagent, and changing what it does while not changing it's name, is no only an anti-pattern, for a human, it would be a firable offense.  It's paramount to being dishonest and misleading."
- "When I see something like "It also defines each routing rule", I wonder, where is the expertise for this coming from? Is it the aws-mcp? Is there a skill that explains exactly the best practices for writing a routing rule? I don't have a clue."
- "There are some detailed decisions that already pre-determined and shouldn't be determined again.  A perfect example is our standardized event schema. It's set in stone, but for some reason, we still have `agents/event-schema-designer.md`.  And I strongly suspect that the pieline will still call on it to do something. And suspect even more that there is no information to tell it to only do something is a payload schema is needed."
- "What the hell is `event-schema-designer` being used for?  That agent was originally written to be used for eventbridge event schemas." and "Do you not see a problem with the name `event-schema-designer` that does everything you say it does?"
- "We need to make sure we have the right level of agents with sufficient instructions and and expertise to do their jobs."
- "Undispatched doesn't mean not needed. Remember, we've never had pipelines and workflows complete."
- "I do not know why Claude Code put the name of reviewers inside of an agent.  An agent should not care or be aware of it's downstream. That should be cleaned uo. Anything unnenecessary or unenforcable is just noise."
- "The leads we can ignore."
- "I notices that postgres seemed to be more related to interfacing with it, and not on pure data architecture, is is that covered somewhere else."
- "We also need specialization on topics such as Bedrock, AI, Machine Learning, Custom Agents and Custom AI patterns."
- On a catalog of 37 AWS specialist agents grouped by operational boundary (compute, databases, storage, networking and edge, API and application integration, streaming and analytics, security, identity and cryptography, AI and machine learning, observability and governance): "Does this list help in any way?" Of the catalog's CI/CD and developer tools entries (38 to 41), the owner: "But remember, we aren't really useing all of these AWS dev pipeline tools."

#### Specialized skills, instructions and MCP servers, and the AWS toolkit

The owner, 2026-10-19: "But everything needs should have specialized skills and/or instructions and/or mcp servers. Remember that we have much more from AWS than just the mcp-server. It's an entire toolkit. Let's take advantage of everything AWS has to offer."

## Bugs

A Bug bead is a report that something is wrong. It is not pipeline work, and the driver
does not dispatch it: both routers skip a Bug and say why.

A person triages a Bug into an Epic, a Task, or a closure. The Epic or Task it becomes is
then pipeline work like any other.

A build that finds a defect fixes it in that run.

## Composites

A composite is a named unit a pipeline dispatches. The contracts declare every composite:
its name, what runs it, its phases and the pipeline role it plays.

Every composite the contracts declare has a workflow script, or is run by the orchestrator
or the driver as the contracts state. A composite that nothing runs is not declared.

## The matrix in the build and deploy lanes

The rewrite of the build and deploy lanes implements their use of the matrix exactly as
section 4 of `blueprint/design/matrix.md` specifies it, in its Build and Deploy tables. The
rewrite is not complete without it.
