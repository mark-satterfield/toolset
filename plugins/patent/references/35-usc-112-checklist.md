# 35 USC 112 claim-formalism checklist

The four subsections of 35 USC 112 that the `patent-claim-drafting` skill applies to every claim. Use this checklist on every independent and dependent claim before writing `claims.md`.

## 112(a) — Written description and enablement

**Written description**: The specification must demonstrate that the inventor possessed the claimed invention at the time of filing. The full scope of the claim must be supported in the spec, not just a single embodiment.

**Enablement**: A person of ordinary skill in the art must be able to make and use the full scope of the claim from the spec without undue experimentation.

### Checklist

- [ ] Every claim element is described in `idea.md` (the de facto spec at this stage)
- [ ] The spec describes the full scope, not just one embodiment
  - If the claim covers multiple data structures, the spec shows at least the most disparate examples
  - If the claim covers multiple algorithms, the spec shows enough to enable practice across the range
- [ ] Numerical limitations have a basis in the spec or are unambiguously implied
- [ ] If the claim uses functional language (e.g., "configured to"), the structure or algorithm is described

### Failure example

> Claim: "A method comprising configuring the model with sparsity parameters such that inference latency is reduced."
> 
> Spec describes only one sparsity pattern. Other patterns are theoretically possible but the spec does not enable them.
> 
> **Problem**: The claim's scope ("sparsity parameters") is broader than the enabled scope (one specific pattern). Either narrow the claim to match the spec, or expand the spec.

---

## 112(b) — Definiteness

The claims must "particularly point out and distinctly claim" the invention. The Supreme Court (Nautilus v. Biosig Instruments, 2014) restated the test: a claim is indefinite if it fails to inform, with reasonable certainty, those skilled in the art about the scope of the invention.

### Checklist

- [ ] Every term has a clear meaning to a person of ordinary skill
- [ ] Relative terms ("substantially", "about", "approximately", "high", "low") have a basis in the spec for what the reference point is
- [ ] No "means for [function]" without corresponding structure in the spec (otherwise indefinite per Williamson v. Citrix Online)
- [ ] No claim limitation depends on a measurement procedure that is not specified
- [ ] No internal contradiction (e.g., "a list comprising one element" — is the cardinality fixed?)
- [ ] Antecedent basis: every "the X" refers back to a previously-introduced "a X" or "an X"

### Watch list — common indefiniteness traps

- "approximately X" without explanation of tolerance
- "substantially perpendicular" without context
- "user-friendly" — relative to what user?
- "optimized" — toward what objective?
- "secure" — secure against what threat model?
- "real-time" — latency under what bound?

### Resolution patterns

- For "substantially": add a tolerance ("substantially perpendicular, defined as within 5 degrees of perpendicular")
- For "optimized": specify the objective ("optimized to minimize per-request latency under a memory cap of M")
- For "secure": specify the threat model ("secure against an adversary who can observe but not modify network traffic")
- For "real-time": specify the latency bound ("real-time, with each request processed in under T milliseconds at the 99th percentile")

---

## 112(c) and 112(d) — Form of claims, dependent claims

**112(c)**: The specification shall conclude with one or more claims particularly pointing out and distinctly claiming the subject matter.

**112(d)**: A claim in dependent form shall contain a reference to a claim previously set forth and then specify a further limitation of the subject matter claimed.

### Checklist for dependent claims

- [ ] Every dependent claim references an existing claim by number ("of claim N", "of claim N or claim M")
- [ ] Every dependent claim adds at least one limitation not present in the referenced claim
- [ ] No dependent claim merely restates the parent ("The method of claim 1, wherein the method is performed by a computer" — if claim 1 already involves a computer, this is improper)
- [ ] No dependent claim contradicts the parent
- [ ] No circular dependency

### Style note: multiple-dependent claims

A multiple-dependent claim ("of claim 1 or claim 2") is allowed but counts as multiple claims for fee purposes and is sometimes disfavored. Default to single-dependent claims unless the multi-dep meaningfully reduces total claim count.

---

## 112(f) — Means-plus-function

Optional. If the claim uses "means for [function]" or "step for [function]", it is interpreted under 112(f) — the claim covers the corresponding structure described in the spec and its equivalents.

### When to use

- When the inventor genuinely wants the broadest scope tied to a specific structure
- Rare in modern software-patent practice; modern style avoids "means for"

### When NOT to use

- When the spec does not disclose specific structure (the claim becomes indefinite)
- When the inventor wants a broader scope than the spec's structure (use general structural language instead)

### Checklist if using 112(f)

- [ ] The spec discloses corresponding structure for every "means for [function]" claim
- [ ] The structure is specific (algorithm steps, hardware component) — not just "a computer"
- [ ] The spec describes alternative structures, broadening the equivalents reach

---

## Application protocol in `patent-claim-drafting`

In Step 5 of `patent-claim-drafting`, walk every claim through this checklist. For each ❌:

1. Identify whether the problem is solvable by claim revision or requires spec expansion
2. If claim revision: rewrite the term, add a tolerance, specify a reference point
3. If spec expansion: identify which `idea.md` field needs additional content. Add it.
4. Re-check.

A claim that fails 112(b) (indefiniteness) almost always also fails 112(a) (enablement) somewhere — they tend to co-occur. Treat as a single quality check.

## Definiteness escape hatches

If a term is genuinely well-known in the art (e.g., "TCP congestion window"), the standard interpretation suffices and no spec definition is needed. But: if there is any ambiguity in how a skilled person would interpret the term in this specific context, define it explicitly in the spec.

When in doubt, define. The cost of an extra definition in the spec is trivial; the cost of indefiniteness invalidation later is total.
