---
name: "patent-claim-drafting"
description: Drafts patent claims for an assessed idea — one broad independent claim at the maximum scope the eligibility analysis supports, five to ten dependent claims as narrower fallbacks, with 35 USC 112 formalism checks (antecedent basis, definiteness, enablement). Generates method, system, and computer-readable-medium variants. Use when the user asks to draft claims, write claim language, get independent and dependent claims, or has an idea.md at funnel stage `assessed`.
triggers:
  - draft claims
  - write claims
  - independent claim
  - dependent claims
  - claim drafting
  - claim language
  - 35 USC 112
  - method claim
  - system claim
  - computer-readable medium claim
  - CRM claim
  - claim variants
---

# patent-claim-drafting

You draft patent claims for a shaped and assessed idea. Output is `claims.md` in the idea directory.

## Inputs

- `patents/ideas/{slug}/idea.md` at funnel stage `assessed`
- `patents/ideas/{slug}/eligibility.md` — the eligibility conclusions that bound claim scope
- Optionally `patents/ideas/{slug}/prior-art.md` — to ensure claim language carves around the closest prior art

If the idea is not at stage `assessed`, route to `patent-patentability` first.

## Claim-drafting principles

The claim is the legal scope of the invention. Three working principles:

1. **Broad enough to capture all embodiments** — the independent claim should read on every alternative-embodiment the inventor listed in `idea.md`, otherwise it leaves designability headroom.
2. **Narrow enough to be eligible and novel** — the claim must survive Alice Step 2 and not read on any prior-art reference identified in `prior-art.md`.
3. **Element-by-element correspondence** — every term in the claim must have antecedent basis in the spec (the spec is `idea.md` + `eligibility.md` content for now).

## Step 1 — Identify the inventive core

Read the `delta`, `technical effect`, and `alternative embodiments` fields in `idea.md`. Identify the smallest mechanical formulation that:

- Is common across all alternative embodiments
- Carries the technical effect
- Distinguishes from every reference in `prior-art.md`

This formulation is the inventive core. Write it down before drafting claim 1.

## Step 2 — Draft the independent claim (claim 1)

Use this structure for a method claim (the most common starting form):

```
1. A method of [stated purpose, mirroring the technical problem], comprising:
   [first step naming the actor and the action];
   [second step naming the actor and the action, referencing antecedent terms by "the X"];
   [...];
   wherein [the key inventive limitation that distinguishes from prior art];
   such that [the technical effect].
```

Drafting rules:

- Use "comprising" (open-ended, broadest) not "consisting of" (closed)
- The first mention of every noun phrase introduces it with "a" or "an"; subsequent mentions use "the"
- Each step is a verb-led action; do not list nouns as steps
- The `wherein` clause is the inventive limitation — the thing that survives Alice Step 2
- The `such that` clause is optional but pins the technical effect to the claim, strengthening eligibility

Read the claim back against `prior-art.md`. Does any reference disclose all of these elements? If yes, narrow the `wherein` clause. Iterate until no single reference covers all elements.

Read the claim back against `eligibility.md`. Is the claim still directed to an abstract idea per Step 2a, with the inventive concept of Step 2b carried in the `wherein` clause? If not, restructure.

## Step 3 — Draft five to ten dependent claims

Each dependent claim narrows the independent claim along one dimension. Pull from the `alternative embodiments` list in `idea.md`. Useful narrowing axes:

- A specific data structure used to implement an abstract step
- A specific ordering of steps when multiple orderings work
- A specific threshold, rate, or magnitude when the independent claim is parameterless
- A specific input type or domain
- A specific hardware boundary (e.g., "wherein the [step] is performed on a GPU")
- An optional secondary feature ("further comprising [extra step]")

Format:

```
2. The method of claim 1, wherein [narrowing limitation].
3. The method of claim 1, further comprising [additional step].
4. The method of claim 2, wherein [further narrowing limitation].
```

Every dependent claim must:

- Reference an existing claim by number ("of claim N")
- Add at least one limitation not present in the referenced claim
- Be internally consistent (no contradiction with parent claim)
- Carry antecedent basis for every term it introduces

## Step 4 — Generate variants for method / system / CRM

Patent claims for software inventions are commonly drafted in three statutory categories — these are mirror claims, not separate inventions:

**Method claim** (already drafted as claim 1)

**System claim** — same invention, framed as an apparatus:

```
N. A system comprising:
   one or more processors;
   memory storing instructions that, when executed by the one or more processors, cause the system to:
   [first step from method claim, rephrased as an instruction the system performs];
   [...];
   wherein [the inventive limitation, identical to method claim];
   such that [the technical effect].
```

**Computer-readable medium (CRM) claim** — same invention, framed as an article of manufacture:

```
M. A non-transitory computer-readable medium storing instructions that, when executed by one or more processors, cause the one or more processors to:
   [step list identical to method claim];
   wherein [the inventive limitation];
   such that [the technical effect].
```

Use "non-transitory" — transitory media (signals) are not statutory subject matter under In re Nuijten.

Each variant gets its own independent claim number, plus its own set of dependent claims mirroring the method dependents.

## Step 5 — 35 USC 112 compliance check

Open `references/35-usc-112-checklist.md`. Walk every claim against this list:

**112(a) — written description and enablement**

- [ ] Every term in every claim has antecedent basis somewhere in the spec (idea.md + eligibility.md content)
- [ ] A person of ordinary skill could practice the invention from the spec without undue experimentation
- [ ] The spec teaches the full scope of the claim, not just a single embodiment

**112(b) — definiteness**

- [ ] Every term has a clear, definite meaning. Flag and resolve: "substantially", "about", "approximately", "high", "low" (these are not automatically indefinite but require the spec to provide a clear point of comparison)
- [ ] No relative terms without a reference point ("faster than" → faster than what?)
- [ ] No purely functional language without structural support ("means for X" invokes 112(f) — only use if you can name the corresponding structure in the spec)

**112(d) — proper dependent form**

- [ ] Every dependent claim adds a limitation, not merely restates the parent
- [ ] No "claim N, wherein the method is the method of claim N" tautologies

**112(f) — means-plus-function**

- [ ] If any claim uses "means for [function]", the spec must disclose corresponding structure. If you cannot identify the structure, rewrite without "means for".

## Step 6 — Write `claims.md` and advance

`claims.md` structure:

```markdown
# Claims — {slug}

## Inventive core

[One-paragraph statement of the smallest mechanical formulation carrying the inventive contribution]

## Method claims

1. [Independent method claim]
2. [Dependent claim]
3. [...]

## System claims

N. [Independent system claim]
N+1. [Dependent system claim]
...

## Computer-readable medium claims

M. [Independent CRM claim]
M+1. [Dependent CRM claim]
...

## 112 compliance notes

- [Any flagged ambiguities and their resolutions]
- [Any "substantially"/"about" terms and the spec passages that define their meaning]
- [Any means-plus-function claims and the corresponding structure in the spec]

## Prior-art carve-out

For each top reference in prior-art.md, state which claim element distinguishes the invention.

| Reference | Distinguishing claim element |
|---|---|
```

Set `funnel stage: claim-ready` in `idea.md`.

Recommend: "Claims are drafted. Run `/patent:enforce` to score how defensible and enforceable these claims are."

## Acceptance criteria

- Every independent claim has at least one dependent claim that narrows it
- No claim depends on a non-existent antecedent claim
- Each variant (method / system / CRM) is internally consistent and mirrors the others
- Every claim term has antecedent basis in the spec
- The prior-art carve-out table identifies, for each top reference, which element of the independent claim is not disclosed

## References

- `references/35-usc-112-checklist.md` — formalism checklist
- `references/state-model.md` — `claims.md` schema
