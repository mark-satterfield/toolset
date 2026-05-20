# Federal Circuit and Supreme Court patent-eligibility cases

The controlling cases that determine software-patent eligibility under 35 USC 101 / Alice. Cite by name AND fact pattern, not just holding — fact-pattern analogy is how Step 2 close calls are won.

For each case: facts, holding, and the analogy hook (what claim shapes can use this case as support or face it as a risk).

---

## Alice Corp. v. CLS Bank International, 573 U.S. 208 (2014)

**Facts**: Alice's patents claimed a computer-implemented method, system, and computer-readable medium for mitigating settlement risk in financial transactions. The system used a neutral third-party intermediary to ensure both parties of a transaction settled their obligations.

**Holding**: Claims directed to the abstract idea of intermediated settlement, implemented on a generic computer. Step 2a: directed to an abstract idea (a fundamental economic practice). Step 2b: the generic computer implementation added nothing more — no inventive concept. INVALID.

**Two-step test established**:
1. Is the claim directed to an abstract idea, law of nature, or natural phenomenon?
2. If yes, is there an inventive concept that amounts to "significantly more" than the abstract idea?

**Analogy hook (risk side)**: Use as the controlling risk citation when a claim looks like "do [known concept] but on a computer". The closer the claim is to "implement [known practice] using generic computer functions", the closer it is to Alice.

---

## Bilski v. Kappos, 561 U.S. 593 (2010)

**Facts**: Claims directed to a method of hedging risk in commodities trading. The Federal Circuit had applied the "machine-or-transformation" test; the Supreme Court rejected this as the sole test but agreed the claims were unpatentable.

**Holding**: Hedging is a fundamental economic practice and therefore an abstract idea. The machine-or-transformation test is "a useful and important clue" but not the only test. INVALID.

**Analogy hook (risk side)**: Use when a claim is in the domain of finance, contracts, insurance, supply chain, or any "fundamental economic practice". Bilski is the controlling case for "method of doing business" rejections.

---

## Mayo Collaborative Services v. Prometheus Laboratories, 566 U.S. 66 (2012)

**Facts**: Claims directed to administering a drug, measuring metabolite levels, and adjusting the dose based on the level. The claims invoked a law of nature (the correlation between metabolite level and therapeutic effect).

**Holding**: Claims directed to laws of nature with conventional steps appended are not eligible. Step 2b requires an inventive concept beyond conventional application. INVALID.

**Analogy hook (risk side)**: Most relevant to bio/pharma, but the principle — "law of nature + conventional steps = ineligible" — applies to software claims that wrap a known algorithm with conventional steps. Mayo is the case that established Alice's two-step framework.

---

## DDR Holdings, LLC v. Hotels.com, L.P., 773 F.3d 1245 (Fed. Cir. 2014)

**Facts**: Claims directed to generating a composite web page combining content from a third-party merchant with the look-and-feel of a host website, when a user clicks a third-party link. The technical problem was retaining users on the host site rather than losing them to the merchant.

**Holding**: Eligible. The claims address a problem "specifically arising in the realm of computer networks" — namely, the loss of host-site visitors when they click outbound links. The solution is "necessarily rooted in computer technology" and overrides the routine and conventional sequence of events ordinarily triggered by clicking a hyperlink.

**Analogy hook (supporting side)**: Use when the invention solves a problem that exists only because of the computer environment — not a real-world problem that has been computerized. The technical problem and the technical solution must both be computer-specific.

---

## Enfish, LLC v. Microsoft Corp., 822 F.3d 1327 (Fed. Cir. 2016)

**Facts**: Claims directed to a "self-referential" database table structure where the table includes definitions of its own columns, eliminating the need for separate schema tables.

**Holding**: Eligible at Step 2a. The claims are directed to an improvement in the way computers operate — specifically, a new data structure that improves database functionality. Not directed to an abstract idea.

**Analogy hook (supporting side)**: Use when the invention is a structural improvement to a computational substrate (data structures, memory layout, cache behavior, computer architecture). The claim survives Step 2a entirely, no Step 2b analysis needed. The closer the invention is to "a better way for the computer to do something the computer already does", the closer to Enfish.

---

## McRO, Inc. v. Bandai Namco Games America Inc., 837 F.3d 1299 (Fed. Cir. 2016)

**Facts**: Claims directed to a method of automatic lip-sync animation, using specific rules for determining the timing of phoneme transitions in animated characters. Previously, this required manual animator judgment.

**Holding**: Eligible at Step 2a. The claims are directed to a specific improvement (the rule-based method) rather than to the abstract idea of animation. The specificity of the rules ensures the claim does not preempt all approaches.

**Analogy hook (supporting side)**: Use when the invention is a specific algorithmic approach that does not preempt the broader field. The presence of specific rules — narrow enough that other approaches remain available — is what saves the claim. Cite McRO for "specific rules, non-preempting" framings.

---

## Berkheimer v. HP Inc., 881 F.3d 1360 (Fed. Cir. 2018)

**Facts**: Claims directed to a method of archiving files by parsing, comparing, and storing them in a way that eliminates redundancy. HP sought summary judgment of invalidity under Step 2b, arguing the claim elements were "well-understood, routine, and conventional".

**Holding**: Whether claim elements are "well-understood, routine, and conventional" is a question of fact, not law. Summary judgment of invalidity at the pleading stage is improper when the patent owner can plausibly allege the elements were not conventional.

**Analogy hook (supporting side)**: Use during prosecution and litigation to argue that Step 2b is a fact question. In `eligibility.md`, this case supports the framing: "Even where the claim is directed to an abstract idea, factual evidence of unconventional implementation supports the inventive concept." Pair with Aatrix.

---

## Aatrix Software, Inc. v. Green Shades Software, Inc., 882 F.3d 1121 (Fed. Cir. 2018)

**Facts**: Claims directed to a system for designing, creating, and importing data into a viewable form on a computer. Aatrix alleged the specific implementation (data file structure, viewer, design tool) was inventive.

**Holding**: Where the complaint alleges plausible factual allegations of inventive concept, the patent survives a Rule 12 motion to dismiss. Eligibility is not a pure question of law when factual allegations of inventiveness are non-conclusory.

**Analogy hook (supporting side)**: Use alongside Berkheimer to defeat early-stage eligibility challenges. In `eligibility.md`, this case supports the framing: "Specific allegations about the inventive nature of [specific implementation] preserve the eligibility question for fact development."

---

## Electric Power Group, LLC v. Alstom S.A., 830 F.3d 1350 (Fed. Cir. 2016)

**Facts**: Claims directed to performing real-time analysis of power-grid data — collecting data from multiple sources, analyzing for unusual events, and displaying the results.

**Holding**: Not eligible. The claims are directed to the abstract idea of collecting, analyzing, and displaying information. Step 2b is not satisfied by generic computer collection, analysis, or display.

**Analogy hook (risk side)**: Use when a claim's overall structure is "collect data, analyze data, display result". This is the canonical "abstract mental process" failure mode for software claims. Pair the Electric Power Group risk with the McRO supporting line: did the inventor specify rules narrow enough to avoid preempting all collect-analyze-display approaches?

---

## CyberSource Corp. v. Retail Decisions, Inc., 654 F.3d 1366 (Fed. Cir. 2011)

**Facts**: Claims directed to a method of verifying credit-card transactions by using prior transaction information to build a fraud profile. The Federal Circuit found that all the steps could be performed mentally.

**Holding**: Not eligible. A method that can be performed by a human in their mind, even if slowly, is an abstract mental process.

**Analogy hook (risk side)**: Use when assessing whether a claim could be performed by a human. CyberSource is the "mental process" risk citation. The reframe (per `eligibility-reframings.md`) is to identify computer-specific aspects (scale, real-time, sensor integration) that distinguish from human capability.

---

## Affinity Labs of Texas, LLC v. DIRECTV, LLC, 838 F.3d 1253 (Fed. Cir. 2016)

**Facts**: Claims directed to streaming a regional broadcast to a cellular telephone outside the broadcast region.

**Holding**: Not eligible. Directed to the abstract idea of delivering content to a user outside its native region. Generic computer implementation does not save it.

**Analogy hook (risk side)**: Use when a claim is "extend [known activity] to [new device/location] using a computer". The novelty is in the deployment context, not in any technical mechanism. Affinity Labs joins Alice as a "generic implementation" risk citation.

---

## BSG Tech LLC v. Buyseasons, Inc., 899 F.3d 1281 (Fed. Cir. 2018)

**Facts**: Claims directed to a database design for self-evolving generic indexing of items in a wide variety of databases.

**Holding**: Not eligible. The claim is directed to the abstract idea of considering historical usage information while inputting data. The specific database structure was not enough of an inventive concept.

**Analogy hook (risk side)**: Demonstrates that even data-structure inventions can fail Alice if the data structure itself is too generic. Contrast with Enfish (self-referential table = specific structural improvement).

---

## Cite-and-fact-pattern protocol

In `eligibility.md`, every eligibility conclusion must:

1. Name the controlling case
2. State the case's fact pattern in one sentence
3. State why the user's idea is similar to (or different from) those facts

Example:

> "The idea is analogous to McRO: it claims specific rules (token-bucket leak rate adjustment based on per-tenant feature flags) that produce a measurable technical effect (sub-millisecond per-request rate-limiting decisions). Like McRO's lip-sync rules, these rules do not preempt the broader field of rate-limiting because countless other approaches remain available."

Not:

> "This is patent-eligible under McRO."

The first form is defensible. The second is not.

## Tracking changes in eligibility law

This catalog reflects controlling case law as of plan creation. Eligibility law is actively developed. Before relying on a borderline case:

- Check whether the case has been distinguished, limited, or overruled
- Check the USPTO Patent Eligibility Guidance updates
- Check for recent Federal Circuit decisions on similar fact patterns

The MPEP 2106 series and the USPTO Patent Eligibility Guidance are the official examiner-facing references. The Federal Circuit case law evolves these.
