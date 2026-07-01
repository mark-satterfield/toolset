# FORGE

**Framework for Objective-Rooted, Gated Execution**

A methodology for writing instructions an AI agent can execute without interpretation.
Forged instructions have no voids. Every gap you leave is a judgment call you handed to the agent.

---

# Structured Instruction Framework

A methodology for writing unambiguous, executable instructions intended for an AI Agent.

---

## Philosophy

An AI Agent does not infer intent. It executes instructions. Every gap in an instruction set
is an opportunity for the agent to fill that gap with its own reasoning — which may or may not
match what you wanted. This framework exists to close those gaps systematically.

The framework is **modular and progressive**. The only required section is ANCHOR — the objective.
Every other section is included only when it contributes information the agent would not reliably
have or correctly assume. An empty section is noise. A missing section that was needed is a defect.

The default assumption throughout the framework is that **the agent is the sole actor**. You do
not annotate agent steps. You only annotate steps where a human or external system acts. The
moment you find yourself writing actor annotations on every step, you are working too hard — the
agent is the subject unless stated otherwise.

---

## When to Write Instructions vs. When to Have a Conversation

Not every task requires a formal instruction set. Use this framework when:

- The task has more than one step with ordering constraints
- Ambiguous terms exist that the agent might interpret differently than you intend
- Failure has a cost — data loss, irreversible action, external side effects
- The task will be repeated, reused, or handed to someone else to run
- A human decision point exists mid-execution

A conversational prompt is sufficient for exploratory, low-stakes, single-step tasks.
Reserve the framework for tasks where precision matters.

---

## The Sections

### [CONTEXT] — Optional

**Purpose:** Align the agent on facts, definitions, scope, and starting state before it acts.

Use CONTEXT when the agent might otherwise bring incorrect assumptions to the task. Do not use
it to restate things that are universally known or inferrable from the task itself.

**Sub-keywords:**

`Fact:` — A truth that is fixed and not arguable within this task. Use for domain rules,
business rules, or physical constraints that the agent must treat as immutable.

> Example: `Fact: Tomatoes qualify as a fruit.`
> Example: `Fact: The production database is read-only from this service account.`

`Define:` — Assigns a specific meaning to a term for the duration of this instruction block.
DEFINE overrides common usage everywhere in the block — including inside PROCESS and SAFEGUARDS.
If you define "complete" as "all records written and verified," that definition holds in every
conditional, loop, and gate in this block.

> Example: `Define: "bunch" = any quantity strictly greater than 100 items.`
> Example: `Define: "stale" = any cache entry older than 72 hours.`

`Scope:` — Explicit boundaries. Use when the agent might reasonably include or exclude something
you don't intend.

```
Scope:
  In:   What is explicitly included.
  Out:  What is explicitly excluded.
```

> Example:
> ```
> Scope:
>   In:  All .py files under /src
>   Out: /src/vendor, /src/generated, test files matching *_test.py
> ```

`Setup:` — The starting state, configuration, or physical layout at the moment execution begins.
Use when the agent needs to know what it is walking into, not what it should build.

> Example: `Setup: The S3 bucket exists and is empty. The IAM role has been pre-provisioned.`
> Example: `Setup: Four labeled produce baskets are staged at the sorting station.`

**CONTEXT vs. ANCHOR:** CONTEXT describes the world as it is. ANCHOR describes the world as it
should be after the task completes. Never put objectives in CONTEXT. Never put environmental
facts in ANCHOR.

**CONTEXT vs. SAFEGUARDS:** Environmental constraints that are static belong in CONTEXT.
Behavioral rules that govern how the agent acts during execution belong in SAFEGUARDS. "The
production database is read-only" is a Fact. "Do not write to production under any
circumstances" is a Guideline.

---

### [WHEN] — Optional

**Purpose:** Define the condition, event, or schedule that activates this instruction block.

WHEN answers: *Should I run this?*
Gate.Before answers: *Am I ready to run this?*

They are sequential. WHEN fires first. If the trigger condition is met, Gate.Before runs next.
If there is no WHEN section, the instruction block executes immediately on receipt.

**Sub-keywords:**

`Trigger:` — A specific event or state change that initiates execution.

> Example: `Trigger: A new pull request is opened against the main branch.`
> Example: `Trigger: The nightly export job completes with status SUCCESS.`

`Schedule:` — Time-based or recurring activation.

> Example: `Schedule: Every day at 02:00 UTC.`
> Example: `Schedule: The first Monday of each month.`

`Condition:` — A boolean state that must become true for this block to activate.

> Example: `Condition: The pending queue depth exceeds 500 items.`
> Example: `Condition: All upstream services report healthy.`

**WHEN vs. CONTEXT:** A WHEN condition is active and evaluated at runtime. A CONTEXT Fact is
passive background truth. "The queue is processed nightly" is a Fact. "When the queue depth
exceeds 500" is a Trigger.

---

### [ANCHOR] — **Mandatory**

**Purpose:** State what must be achieved, completely isolated from how to achieve it.

This is the only required section. It names the objective, the thing being acted upon, and the
measurable outcome that declares the job finished. ANCHOR should be writable without knowing
anything about the procedure. If you find yourself describing steps in ANCHOR, move them to
PROCESS.

**Sub-keywords:**

`Objective:` — One sentence. The high-level action to take.

> Example: `Objective: Move a bunch of fruit from the shipping container to the color-coded baskets.`
> Example: `Objective: Identify and report all file naming convention inconsistencies in the project.`

`Target:` — The exact subject, dataset, system, file, or physical materials being acted upon.
Be specific. Replace "the system," "the codebase," or "the data" with explicit identifiers.

> Example: `Target: All .py files under /src excluding /src/vendor.`
> Example: `Target: The primary shipping container staged at dock 3.`

`Success Criteria:` — A measurable, observable outcome. Not a qualitative judgment. Not a
process description. The criteria must be evaluable by the agent without human interpretation.

> Example: `Success Criteria: Total fruit items placed across all baskets exceeds 100.`
> Example: `Success Criteria: Zero files remain with mixed naming conventions in the target scope.`

**Writing Success Criteria correctly:** Avoid qualitative modifiers. "Successfully completed,"
"properly handled," and "fully verified" allow the agent to invent its own definition of success.
Write the specific observable state that must be true. If success requires a count, name the
count. If it requires a file to exist, name the file and its location.

---

### [PROCESS] — Optional

**Purpose:** Describe how to achieve the ANCHOR objective.

PROCESS is the execution algorithm. It is absent only when the objective is completely
self-evident to the agent and no procedure guidance is needed. In practice, if the task has
more than one step, PROCESS is present.

**Approach types — choose exactly one per PROCESS block:**

#### Sequential

Numbered, ordered, non-deviatable steps. The agent executes them in order. No step may be
skipped or reordered. Use when the order of operations matters or when you want no discretion
left to the agent.

```
Sequential:
  1. Step one.
  2. Step two.
  3. Step three.
```

#### White-Listed

Multiple valid approaches, any of which is acceptable. The agent chooses one. Use when more
than one correct path exists and you want to permit but bound that choice.

```
White-Listed:
  Option 1 (label):
    1. ...
    2. ...
  Option 2 (label):
    1. ...
    2. ...
```

#### Black-Listed

Total execution freedom except for named exclusions. Use when the valid approach space is
large and easier to define by what to exclude than by what to permit.

```
Black-Listed:
  Restriction: Do not use approach X.
  Exclude: Y and Z are not permitted.
```

**Approach type selection guidance:**

Use Sequential when failure order matters, when steps have side effects that subsequent steps
depend on, or when you want no ambiguity about what the agent does next.

Use White-Listed when you genuinely do not care which approach the agent takes as long as it
stays within the named set. Do not use White-Listed as a shortcut when you actually have a
preference — state the preference in ANCHOR or as a Guideline in SAFEGUARDS.

Use Black-Listed when the universe of valid approaches is large and well-understood, and
only specific approaches are dangerous, deprecated, or out of scope. Black-Listed requires
the most trust in the agent's judgment; use it when that trust is warranted.

**Do not mix approach types at the same level.** A Sequential block that contains an
Option mid-stream is a White-Listed block. Restructure it. Nesting is the correct mechanism:
a White-Listed block can contain Sequential sub-steps within each Option.

#### Conditional Sub-Keywords

Valid inside any approach type, at any nesting depth:

```
IF [condition] THEN:
  ...
OTHERWISE:
  ...
```

Every IF must have an OTHERWISE. If the false branch is "do nothing," write `OTHERWISE: Continue.`
Do not leave the false branch implicit — the agent will fill it in.

```
LOOP [target] UNTIL [termination condition]:
  ...
```

Every LOOP must have an explicit termination condition. Define what happens if the termination
condition is never reached: continue indefinitely, halt, or trigger a fallback.

#### Actor Annotation

The default actor is the agent. Do not annotate agent steps.

When a human or external system performs a step, annotate that step only:

```
  3. [Human: Mark] Review the output and provide one of: approval, a corrected file, or stop.
```

When execution must pause for a human decision and then resume, use PAUSE:

```
PAUSE:
  [Human: name]  What the human does.
  RESUME IF:     The condition or input that allows execution to continue.
  BRANCH:        (optional) How the human's response routes execution.
    "Response A" → What happens next.
    "Response B" → What happens next.
```

**When to use PAUSE vs. splitting into separate instruction blocks:**

Use PAUSE when you can write the BRANCH table now. If you know all the possible responses and
what follows each one, PAUSE handles it cleanly — even if the most likely branch is "continue."

Split into a separate instruction block when the next phase cannot be written yet because it
depends on information that does not exist until the human decides. The current block ends with
a STOP step that names what input or decision is required before the next block can be authored.

A task that takes twenty seconds end-to-end with a human review in the middle is a single block
with a PAUSE. A task whose second phase depends on a budget number that hasn't been determined
is two blocks written at different times.

---

### [SAFEGUARDS] — Optional

**Purpose:** Execution controls. Behavioral rules, gates, error handling, and rollback logic.

SAFEGUARDS does not describe what to do. It constrains how the agent behaves and what it does
when execution goes wrong. All sub-keywords are independent and optional.

**Sub-keywords:**

`Gate.Before:` — A precondition. Must be true before execution starts. If not met, do not
proceed. The agent does not attempt to fix a failed Gate.Before — it halts and reports.

> Example: `Gate.Before: All four baskets must be present and correctly labeled.`
> Example: `Gate.Before: The target S3 bucket must exist and be empty.`

`Gate.After:` — A postcondition. Must be true after execution completes before declaring
success. The agent verifies this actively — it does not assume success from a clean run.

> Example: `Gate.After: Total fruit items across all baskets exceeds 100.`
> Example: `Gate.After: Zero files with mixed conventions remain in the target scope.`

`Guideline:` — A behavioral policy active during execution. Choose the type that applies:

- `Stop If:` — Halt immediately if this condition is encountered. Report state. Do not proceed.
- `Keep Going:` — Override normal stop behavior. Proceed despite minor errors or ambiguity.
- `No Deviation:` — PROCESS is strict. Do not improvise, reorder, or substitute steps.
- `Best Effort:` — Partial completion is acceptable. Proceed with available information.

`Stop If` and `Keep Going` are mutually exclusive for the same class of error. You cannot
instruct the agent to both halt and continue on the same condition.

> Example: `Guideline — Stop If: You cannot determine whether an item is a fruit or vegetable.`
> Example: `Guideline — Keep Going: This is a smoke test. Minor color-sorting errors are acceptable.`

`On Error:` — What to do when something unexpected happens that no other rule covers. This is
the catch-all. Write it as a specific instruction, not a philosophy.

> Example: `On Error: Halt execution, preserve current state, and report the exact condition encountered.`

`Rollback:` — Instructions to revert to the initial state if execution cannot safely complete.

```
Rollback:
  Trigger:  The condition that initiates rollback.
  Steps:    Ordered instructions to undo the work.
  Verify:   How to confirm the rollback succeeded.
```

**SAFEGUARDS vs. PROCESS:** If it describes what to do, it belongs in PROCESS. If it describes
how to behave or what to do when something goes wrong, it belongs in SAFEGUARDS. A step that
says "if the file doesn't exist, create it" is a PROCESS conditional. A rule that says "if any
file operation fails, halt immediately" is a SAFEGUARDS Guideline.

**Gate.Before vs. WHEN Condition:** A WHEN Condition asks "should this block activate at all?"
A Gate.Before asks "is the environment ready for me to start?" WHEN is evaluated before the
agent begins reading the instruction block. Gate.Before is evaluated after the agent has begun
and is about to execute.

---

### [WHY] — Optional

**Purpose:** The rationale that governs edge-case judgment.

One paragraph. Write WHY only when the reason behind the task would change how the agent
handles a situation not covered by PROCESS or SAFEGUARDS. If WHY would not change any decision,
omit it.

> Example: "This is a smoke test of the sorting workflow, not a production run. Accuracy of
> color sorting is secondary to validating that the end-to-end process completes without
> structural failure. Rollback is guaranteed regardless of outcome."

WHY is not a summary of ANCHOR. It is not a history of the project. It is the answer to
"if the agent hits a wall and has to make a judgment call, what does it need to know to make
the right one?"

---

## Chaining Instruction Blocks

A single instruction block covers one phase of work. When work has phases, use multiple blocks.

Block B may reference the Gate.After of Block A as its Gate.Before:

```
[Block A]
  [SAFEGUARDS]
    Gate.After: Export file written to /output/export.csv.

[Block B]
  [SAFEGUARDS]
    Gate.Before: /output/export.csv exists and is non-empty.
```

This makes the dependency explicit without embedding Block B's logic inside Block A.

---

## Writing Precise Instructions — Common Failure Modes

These are the most frequent ways instruction sets fail. Review your instructions against
this list before delivering them.

**Ambiguous success definitions**
Avoid "successfully completed," "properly handled," "fully verified." These allow the agent
to invent its own criteria. Write the specific observable state that must be true.

**Implicit false branches**
Every `IF` must have an `OTHERWISE`. Every `LOOP` must have a termination condition and a
defined behavior if that condition is never reached.

**Vocabulary drift**
If a concept is called a "test" in one step, do not call it a "verification script" or "check"
in another. Align vocabulary strictly across the entire instruction block.

**Softened commands**
An initial strict command followed by explanatory sentences that introduce exceptions or
qualifications. Write the exception as a separate, explicit conditional — not as a softening
clause appended to the original instruction.

**Qualitative modifiers**
"As needed," "where appropriate," "if necessary," "where possible" — these force the agent to
make subjective judgment calls. Replace them with explicit conditions.

**Broad spatial nouns**
"The system," "the codebase," "the environment," "the process." Replace with specific,
unambiguous identifiers: the target file, the specific function, the named service.

**Overlapping scope**
Instructions that cover specific components and also contain broad generic instructions that
could apply to the same components. Verify that specific and general instructions do not
contradict or subsume each other.

**Missing prerequisite behavior**
If a prerequisite is absent, state whether the agent must halt, fix it, skip the dependent
step, or report. Do not leave it to inference.

**Unlisted state handling**
If execution can produce a state that is neither success nor failure — UNKNOWN, TIMEOUT,
PARTIAL — define what the agent does in that state. Do not let the agent extrapolate.

**Exhaustiveness ambiguity**
If a list of steps or criteria is complete and the agent should not infer additional steps,
say so explicitly: "The following steps are exhaustive. Do not add steps."

**Using "unless" and "except" in-line**
Split exceptions into their own conditional block rather than appending them as clauses to
a primary instruction. In-line exceptions invite context mixing.

**Illustrative examples mistaken for rules**
Do not include reasoning examples or analogies inside instruction text. The agent may treat
an illustrative scenario as a literal binding rule.

**Passive voice**
"The file should be written" — by whom? Use direct action verbs: "Write the file to /output/."

---

## Complete Example

A non-technical example using all sections.

```
[CONTEXT]
  Fact:   Tomatoes qualify as a fruit.
  Define: "bunch" = any quantity strictly greater than 100 items.
  Scope:
    In:   Sorting fruit into color-coded baskets.
    Out:  Handling vegetables, damaged produce, or items of unknown origin.
  Setup:  Four produce baskets are pre-staged and labeled by color group:
            Group 1: Reds and oranges
            Group 2: Browns, grays, whites
            Group 3: Greens
            Group 4: Other / Uncertain

[WHEN]
  Trigger: The shipping container is confirmed sealed and ready for unloading.

[ANCHOR]
  Objective:        Move a bunch of fruit from the shipping container to the color-coded baskets.
  Target:           All contents of the primary shipping container at dock 3.
  Success Criteria: Total fruit items placed across all baskets exceeds 100.

[PROCESS]
  White-Listed: Choose Option 1 or Option 2.

  Option 1 (Batch):
    1. Unpack all produce from all shipping containers.
    2. Separate the entire lot into two groups: Fruits and Vegetables.
    3. Subdivide the Fruit group by primary color.
    4. Move each color group into its matching basket.

  Option 2 (Stream):
    LOOP single item from shipping container UNTIL total fruit counter > 100:
      IF item is a fruit THEN:
        Determine its primary color.
        Place it in the matching basket.
        Increment fruit counter by 1.
      OTHERWISE:
        Return the item to the shipping container.

  PAUSE:
    [Human: Mark]  Inspect the sorted baskets and confirm color groupings are correct.
    RESUME IF:     Mark signals approval or provides a correction list.
    BRANCH:
      Approval    → Proceed to Gate.After check.
      Corrections → Apply corrections, then proceed to Gate.After check.
      Stop        → Initiate Rollback.

[SAFEGUARDS]
  Gate.Before:  All four baskets must be present and correctly labeled before starting.
  Gate.After:   Count all fruit items across all baskets. Total must exceed 100.

  Guideline — Keep Going: This is a smoke test. Minor color-sorting errors are acceptable.
  Guideline — Stop If: You cannot determine whether an item is a fruit or vegetable.

  On Error: Halt. Preserve current basket state. Report the exact item and classification
            problem encountered.

  Rollback:
    Trigger:  Execution halted before Success Criteria is met, or Mark instructs stop.
    Steps:
      1. Collect all items currently in all baskets.
      2. Return them to the original shipping container.
    Verify:   All four baskets are empty. Shipping container item count matches
              the pre-execution manifest.

[WHY]
  This is a smoke test of the sorting workflow, not a production run. Accuracy of color
  sorting is secondary to validating that the end-to-end process completes without structural
  failure. Rollback is guaranteed regardless of outcome.
```
