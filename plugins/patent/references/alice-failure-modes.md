# Alice failure-mode catalog

The recurring patterns that get software patents invalidated under 35 USC 101 / Alice. Use this to triage idea framings in `patent-ideation` and to identify risk in `patent-patentability`.

## How to use this catalog

For each idea framing, ask: does the framing, as phrased, look like any of these patterns? If yes, identify which mechanism within the user's description might survive eligibility, and reframe around it. Do not reject the idea — reframe it.

---

## Failure Mode 1 — Pure business method

**Signature**: The claim describes organizing or executing a transaction, contract, financial scheme, marketing strategy, or business workflow.

**Examples**:
- "A method of arranging insurance contracts so that risk is shared between parties"
- "A method of presenting personalized advertisements based on user purchase history"
- "A method of optimizing supply chain delivery routes"

**Why it fails**: Falls into Alice Step 2a as a "fundamental economic practice" or "method of organizing human activity". Step 2b rarely saves it because the "computer implementation" is generic.

**Reframing path**: Look for a technical mechanism that enables the business outcome. Is there a novel data structure, a non-obvious algorithm, a specific signaling protocol? Reframe around that mechanism, not the business outcome. Example: instead of "optimizing supply chain delivery routes", frame as "a routing algorithm that maintains a real-time index of vehicle positions using a self-balancing geohash structure, achieving sub-linear lookup time under continuous insertion".

---

## Failure Mode 2 — Abstract algorithm with no technical effect

**Signature**: The claim describes a mathematical procedure or formula in the abstract, with no tie to a physical or computational improvement.

**Examples**:
- "A method of computing the moving average of a stream of numbers"
- "A method of normalizing a data set by subtracting the mean and dividing by the standard deviation"
- "A method of clustering data points using k-means"

**Why it fails**: The Federal Circuit has consistently held that "an algorithm in the abstract" is unpatentable. Benson, Flook, and Bilski all hit this. Even with a "computer implementation" wrapper, generic computation doesn't survive Step 2b.

**Reframing path**: Identify what technical problem the algorithm solves and reframe around the problem-solution pair. The algorithm + the technical improvement + the inherent technical effect can be patentable. Example: instead of "a method of clustering data points using k-means", frame as "a method of indexing high-dimensional vectors for retrieval that uses k-means cluster assignment to reduce per-query distance calculations from O(N) to O(N/K + K), where the cluster assignments are stored in a memory-aligned segmented array enabling cache-line-coherent access during retrieval".

---

## Failure Mode 3 — Mental process

**Signature**: The claim describes a process that could be performed entirely by a human with pen and paper, even if slowly.

**Examples**:
- "A method of classifying documents by reading them and assigning a category"
- "A method of determining the best chess move by evaluating possible board positions"
- "A method of identifying patterns in a sequence of events"

**Why it fails**: The Federal Circuit recognizes "mental processes" as abstract ideas (Electric Power Group, CyberSource). A claim that reads on what a human can do mentally is presumptively abstract.

**Reframing path**: Identify what the computer does that a human cannot — scale, speed, real-time response, integration with sensors, persistence in a particular data structure. Reframe around the computer-specific mechanism. Example: instead of "a method of identifying patterns in a sequence of events", frame as "a method of detecting anomalies in high-frequency telemetry streams using a sliding-window Bloom filter that maintains false-positive rate below a threshold while bounding memory to O(log N)".

---

## Failure Mode 4 — Method of organizing human activity

**Signature**: The claim describes how people interact, how gameplay works, how teaching is structured, or social/legal/economic interactions.

**Examples**:
- "A method of facilitating online matchmaking between buyers and sellers"
- "A method of teaching students a foreign language using spaced repetition"
- "A method of scoring contestants in a game show"

**Why it fails**: Falls into Alice Step 2a as a "method of organizing human activity". Step 2b again rarely saves it because the implementation is generic.

**Reframing path**: Identify the technical infrastructure that enables the activity, not the activity itself. Is there a novel synchronization protocol, a state-management mechanism, a real-time inference mechanism? Reframe around that. Example: instead of "facilitating online matchmaking", frame as "a method of computing real-time compatibility scores from a sparse, multi-attribute user feature space using locality-sensitive hashing, returning ranked candidates in sub-100ms with a hit rate above X%".

---

## Failure Mode 5 — "Using AI/ML to do X"

**Signature**: The invention is described as applying machine learning (or AI, deep learning, neural networks) to do some task. The novelty is alleged to be "using AI" rather than a specific contribution to the ML training, inference, or model architecture itself.

**Examples**:
- "A method of detecting fraud using machine learning"
- "A method of recommending products to users using a neural network"
- "A method of summarizing documents using a large language model"

**Why it fails**: "Using a generic ML model to perform a known task" is the modern Alice failure mode. Like "on a computer" of the 2010s, "using AI" of the 2020s adds nothing inventive at Step 2b. The Federal Circuit has rejected ML-applied claims in cases like People.ai v. Clari.

**Reframing path**: The patentable invention is almost never the ML model running on a task. It is one of:
- A novel training procedure (curriculum, data augmentation, loss function)
- A novel architecture component (attention mechanism variant, sparsity pattern, gating)
- A novel inference-time optimization (quantization, caching, speculative decoding)
- A novel data pipeline that solves a specific technical bottleneck
- A novel feature engineering or signal-processing pre-step
- An integration of ML output with a downstream technical control system

Identify which of these the inventor actually invented and reframe.

---

## Failure Mode 6 — "On the internet" / "on a computer"

**Signature**: The claim takes a previously-known offline or analog activity and claims it as new when performed on a computer or online.

**Examples**:
- "A method of conducting a sealed-bid auction online"
- "A method of distributing coupons on a computer"
- "A method of storing customer records electronically"

**Why it fails**: This was the original Alice trigger. Bilski and Alice both directly rejected this pattern. Step 2b is not satisfied by generic computerization.

**Reframing path**: Either the underlying activity has a computer-specific aspect (real-time, network-effect, cryptographic, scale-dependent), or there is no patentable invention. Be honest. If the only contribution is "we did this on a computer", recommend defensive publication or trade-secret protection.

---

## Failure Mode 7 — Result without mechanism

**Signature**: The claim describes the desired outcome but not how that outcome is achieved.

**Examples**:
- "A system that detects malicious network traffic with low false-positive rate"
- "A method of generating photorealistic images"
- "A search engine that returns highly relevant results"

**Why it fails**: This violates both 35 USC 101 (an outcome is an abstract result) and 35 USC 112 (no enabling disclosure). DDR Holdings, McRO, and Enfish all required identifying the specific mechanism, not just the result.

**Reframing path**: Identify the structural or algorithmic feature that produces the result. The patentable invention is the mechanism, not the goal. Example: instead of "detecting malicious network traffic with low false-positive rate", frame as "a packet-classification method that combines a Bloom-filter prescreen, a stateful flow-table lookup, and a deep-inspection fallback such that average-case classification time is O(1) with a false-positive rate bounded by the Bloom filter parameters".

---

## Failure Mode 8 — Generic implementation of a known concept

**Signature**: The claim recites a known concept implemented in conventional ways using conventional components.

**Examples**:
- "A method of caching frequently accessed data" (without specifying eviction policy or topology)
- "A method of compressing data" (without specifying the compression algorithm or its novel aspect)
- "A method of authenticating users using a password" (without specifying anything novel)

**Why it fails**: Step 2b requires "significantly more" than the abstract idea. Generic implementations of known concepts add nothing more.

**Reframing path**: The novel aspect must be specified. If the only novelty is the application of a known technique to a slightly different problem, that may also fail. Look for a structural or algorithmic improvement over the known technique.

---

## Triage protocol

In `patent-ideation` Step 2:

1. Read the user's raw idea
2. Match against this catalog
3. If a match: state which failure mode and one-sentence reframing direction. Then proceed to Cluster A questioning, biased toward extracting the technical mechanism.
4. If no match: proceed directly to Cluster A questioning.

In `patent-patentability` Step 1:

1. Compare the shaped idea's claim shape to these failure-mode signatures.
2. If any signature matches, the eligibility risk is at least MEDIUM. Search for supporting cases (DDR, Enfish, McRO, Berkheimer, Aatrix in `federal-circuit-cases.md`) and risk cases (Alice, Bilski, Electric Power Group) and assess Step 2b.
