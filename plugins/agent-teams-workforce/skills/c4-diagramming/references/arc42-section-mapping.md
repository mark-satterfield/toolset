# Mapping C4 levels onto arc42 sections

arc42 is a 12-section template for documenting software and system architectures. C4 is a
notation for the *static structure* diagrams. They are complementary: arc42 tells you
*what to document and where*, C4 gives you *how to draw the structure pictures*. This file
fixes which C4 artifact goes into which arc42 section, so a documentation set built with
both stays coherent.

## The relevant arc42 sections

The full template has twelve sections. The three that consume C4 diagrams are:

| arc42 § | Section name | What it documents |
|---|---|---|
| 1 | Introduction & Goals | Requirements, quality goals, stakeholders |
| 2 | Architecture Constraints | Constraints the team must respect |
| **3** | **Context & Scope** | System boundary; external interfaces (business + technical) |
| 4 | Solution Strategy | Top-level approach / key decisions, summarized |
| **5** | **Building Block View** | Static decomposition of the system into building blocks |
| 6 | Runtime View | Behaviour — how building blocks collaborate at runtime |
| **7** | **Deployment View** | Technical infrastructure and the mapping of software to it |
| 8 | Crosscutting Concepts | Recurring patterns and concepts |
| 9 | Architecture Decisions | ADRs |
| 10 | Quality Requirements | Quality tree and scenarios |
| 11 | Risks & Technical Debt | Known risks and debt |
| 12 | Glossary | Terms and definitions |

C4 maps cleanly into sections **3, 5, and 7** (bold above).

---

## Section 3 — Context & Scope  ←  C4 Level 1 (System Context)

arc42 section 3 documents the system's boundary and its communication partners: who and
what is outside the system, and the interfaces across the boundary. arc42 splits this into:

- **3.1 Business Context** — the domain-level partners (users, neighbouring systems) and
  the business data/events exchanged.
- **3.2 Technical Context** — the same boundary expressed in technical terms: channels,
  protocols, and the mapping of domain interfaces onto technical ones.

A **C4 Level 1 System Context diagram is exactly the picture arc42 section 3 asks for.**
Place the System Context diagram here. If business and technical context warrant separate
pictures, draw two Context diagrams (one annotated with business meaning, one with
protocols/technologies) — the same `System`/`Person`/`System_Ext` boxes, different labels
on the relationships.

---

## Section 5 — Building Block View  ←  C4 Levels 2, 3, (4)

arc42 section 5 is the static decomposition of the system, documented as a **hierarchy of
levels**: Level 1 (whitebox of the overall system → its top-level building blocks), Level 2
(whitebox of each of those building blocks), Level 3, and so on. This is precisely the C4
"zoom in one notch at a time" idea, so the mapping is direct:

- **arc42 BBV Level 1**  ←  **C4 Container diagram (C4 Level 2).** The overall system
  opened up into its top-level building blocks = the deployable/runnable containers.
- **arc42 BBV Level 2**  ←  **C4 Component diagram (C4 Level 3).** Each container opened up
  into its components. One Component diagram per container that is worth decomposing.
- **arc42 BBV Level 3 (deepest)**  ←  **C4 Code (C4 Level 4),** if and only if a component
  is complex enough to justify it — usually generated from code, rarely hand-drawn.

Note the off-by-one in the *numbering*: C4 Level 1 (System Context) lives in arc42 **§3**,
not in the Building Block View. The Building Block View starts at the C4 Container level.
Keep that straight: **C4 L1 → arc42 §3; C4 L2/L3/L4 → arc42 §5.**

For each building block, arc42 also wants a short "whitebox/blackbox" template (purpose,
interface, responsibility). The C4 diagram supplies the picture; you still write the
one-paragraph blackbox description beside it.

---

## Section 7 — Deployment View  ←  C4 Deployment diagram

arc42 section 7 documents the technical infrastructure (environments, hosts, nodes,
networks) and the **mapping of software building blocks (containers) onto that
infrastructure.** A **C4 Deployment diagram** — containers placed inside
`Deployment_Node`s representing regions, clusters, VMs, browsers, and devices — is exactly
this artifact. Place it here, typically one per environment (e.g. one for "Production", one
for "Staging") when they differ.

---

## What does NOT come from C4

C4 is a static-structure notation, so it does not feed every arc42 section:

- **Section 6 (Runtime View)** is about *behaviour over time* — scenarios, sequences,
  collaborations. That is the territory of UML sequence/communication diagrams (or C4's own
  `C4Dynamic` diagram for a specific scenario), not the static C4 levels.
- **Sections 1, 2, 4, 8–12** are mostly prose, decisions, and quality models. C4 diagrams
  may be *referenced* from them but are not authored there.

---

## Quick mapping table

| C4 artifact | arc42 section |
|---|---|
| Level 1 — System Context | **3 — Context & Scope** (3.1 business, 3.2 technical) |
| Level 2 — Container | **5 — Building Block View**, decomposition level 1 |
| Level 3 — Component | **5 — Building Block View**, decomposition level 2 |
| Level 4 — Code (optional) | **5 — Building Block View**, deepest level |
| Deployment diagram | **7 — Deployment View** |
| Dynamic diagram (`C4Dynamic`) | 6 — Runtime View (behaviour, not static structure) |

Remember the one trap: **C4 numbering and arc42 numbering do not line up.** C4 Level 1 goes
to arc42 section 3; the Building Block View (section 5) begins at C4 Level 2 (Container).
