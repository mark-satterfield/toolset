# Eligibility reframings catalog

Patterns for moving an idea from an Alice-failing framing to an Alice-surviving framing without changing the underlying invention. Used by `patent-ideation` to course-correct user phrasing and by `patent-patentability` to recommend revised claim language.

## How to use

Each pattern has:
- **Trigger phrasing** — what the user said that suggests the failure mode
- **Reframed phrasing** — the pattern to push the framing toward
- **Why it works** — the doctrinal basis

These are not magic incantations. The underlying invention must contain the technical content the reframing references. If it does not, no reframing helps — the idea is genuinely ineligible.

---

## Reframing 1 — Business outcome → Technical mechanism

| Original framing | Reframed framing |
|---|---|
| "A method of [business outcome]" | "A method of [technical mechanism] that, as an inherent consequence, produces [business outcome]" |
| "A system for [business process]" | "A system that solves [technical problem in the process] by [structural mechanism]" |
| "A platform for [activity]" | "A method of [computational mechanism] enabling [activity], wherein [structural limitation]" |

**Why**: The Federal Circuit looks at what the claim is "directed to" (Enfish step). If directed to the technical mechanism, Step 2a may be satisfied without reaching Step 2b. Even when Step 2a is not satisfied, the technical mechanism provides the inventive concept for Step 2b (Berkheimer factor).

---

## Reframing 2 — Result → Specific algorithmic structure

| Original framing | Reframed framing |
|---|---|
| "A method that achieves [result]" | "A method comprising [specific steps in order] using [specific data structure], such that [result is the inherent consequence]" |
| "A model that learns to [task]" | "A training method comprising [specific procedure: loss function, regularization, sampling, etc.], such that [task accuracy improves over baseline]" |
| "A search that returns relevant results" | "A method comprising [indexing structure] and [ranking algorithm], wherein [specific signal] is computed using [specific procedure]" |

**Why**: McRO specifically held that claims directed to "specific rules" (not preempting all approaches) are eligible. Specifying the algorithmic structure differentiates from "the abstract idea of [task]" and provides non-preemption.

---

## Reframing 3 — Mental process → Computer-specific mechanism

| Original framing | Reframed framing |
|---|---|
| "A method of identifying [pattern]" | "A method of identifying [pattern] in [data type] at [throughput or latency requirement] using [computer-specific mechanism]" |
| "A method of classifying [items]" | "A method of classifying [items] using [feature-extraction step that requires computer-scale operation] such that [scale/speed/integration property]" |
| "A method of deciding [outcome]" | "A method of deciding [outcome] using [signal that is only computer-collectable: sensor data, network telemetry, real-time stream]" |

**Why**: Electric Power Group rejected "collect-analyze-display" as a mental process. The reframe must tie the operation to capabilities only computers have — scale, speed, sensor integration, real-time response. McRO and DDR both used computer-specific properties (animation rules requiring per-frame computation; internet-specific dual-frame rendering) to survive.

---

## Reframing 4 — Generic "on a computer" → Improves the computer

| Original framing | Reframed framing |
|---|---|
| "[Activity] on a computer" | "A method that improves [computational property — memory, latency, throughput, cache behavior, network bandwidth, energy] of the computer by [specific structural change]" |
| "[Activity] performed by a server" | "A distributed method that resolves [specific technical problem — consistency, replication lag, contention, hot-spot] by [structural mechanism]" |

**Why**: Enfish established that claims directed to improving the functioning of the computer itself are eligible at Step 2a — no Step 2b analysis needed. The reframe explicitly invokes this lane.

---

## Reframing 5 — AI/ML application → Specific ML contribution

| Original framing | Reframed framing |
|---|---|
| "Using ML to [task]" | "A training method comprising [novel procedure], or a model architecture comprising [novel structure], or an inference-time optimization comprising [novel mechanism] that, when applied to [task], achieves [measurable improvement over baseline]" |
| "A neural network for [task]" | "A neural-network method wherein [specific architectural feature] enables [computational property: parameter efficiency, sparsity exploitation, inference latency, memory footprint]" |
| "An LLM-based [tool]" | "A method comprising [novel prompting/decoding/post-processing/grounding/retrieval procedure] that, when combined with a large language model, produces [measurable improvement]" |

**Why**: The patentable contribution in ML is almost never "applying ML to a task". It is a specific contribution to the training procedure, model architecture, inference optimization, or data pipeline. Reframe around that contribution.

---

## Reframing 6 — Abstract algorithm → Algorithm tied to technical effect

| Original framing | Reframed framing |
|---|---|
| "A method of computing [mathematical operation]" | "A method of computing [mathematical operation] for [specific technical purpose] using [data structure or hardware] such that [physical-resource property: memory, latency, energy]" |
| "An algorithm for [problem]" | "A method of solving [technical problem] using an algorithm comprising [steps], wherein [step] reduces [resource consumption] from [O(X)] to [O(Y)]" |

**Why**: An algorithm in the abstract is unpatentable (Benson). An algorithm tied to a specific technical purpose and producing a specific measurable improvement may survive Step 2b. The reframe must include both the purpose tie and the measurable improvement.

---

## Reframing 7 — Generic computer + idea → Improves a specific technical field

| Original framing | Reframed framing |
|---|---|
| "A computer-implemented method of [task]" | "A method of improving [specific technical field — networking, cryptography, image processing, storage, etc.] by [specific structural change], such that [measurable improvement]" |

**Why**: DDR Holdings survived because the claimed solution was "necessarily rooted in computer technology in order to overcome a problem specifically arising in the realm of computer networks". The reframe must identify a specific technical field and a problem specific to that field that the invention solves.

---

## Reframing 8 — Functional language → Means + corresponding structure

| Original framing | Reframed framing |
|---|---|
| "Means for [function]" without structural support | Either: rewrite without "means for" (use specific structural language); OR: add corresponding structure in the spec and ensure the spec describes the specific algorithm or hardware that performs the function |

**Why**: 112(f) "means-plus-function" claims require the spec to disclose corresponding structure. Without structure, the claim is indefinite under 112(b). Most claim-drafting failures here are claim-side, not eligibility-side, but they interact: an indefinite claim is rarely eligible.

---

## Application protocol

In `patent-ideation`:

1. After each user answer in Clusters A–E, check whether the answer drifts toward any of the failure modes in `alice-failure-modes.md`.
2. If yes, identify the matching reframing pattern here, and state the reframe in one sentence.
3. Update the relevant field of `idea.md` with the reframed phrasing.
4. Continue to the next cluster.

In `patent-patentability`:

1. During Step 2b analysis, when the eligibility is risky, identify whether a reframing pattern would convert the claim language to a surviving form.
2. If yes, note in `eligibility.md` that the eligibility is conditional on adopting the reframed language in claim drafting.
3. Pass the reframed language to `patent-claim-drafting` via `eligibility.md`.

In `patent-claim-drafting`:

1. When drafting the independent claim's `wherein` clause, use the reframed phrasing from `eligibility.md`.
2. Verify that the resulting claim language reads on the actual invention as described in `idea.md`. If it doesn't, the reframe was incompatible with the invention — return to ideation.
