# arc42 section model

arc42 is a free, open template for software architecture documentation. This project's SAD uses eleven numbered sections — 1 through 8 and 10 through 12. The template prescribes *what* each section holds, not *how* the system is built — it is a structure for communicating architecture, not a method for designing it. Every sub-skill in this toolkit reads this file for the authoritative section list; none of them redefines it.

A section may legitimately be empty if the system does not warrant it (small systems often collapse 5–7 into a few paragraphs and skip 11). An empty section is stated as "Not applicable" with a one-line reason, never deleted from the structure.

## The eleven sections

### 1. Introduction and Goals
The short version of the requirements. The essential business goals, the top three to five quality goals that drive architecture (the **most important** prioritized quality attributes, expressed as concrete scenarios, not adjectives), and the key stakeholders with their expectations. This section answers "why does this system exist and what must it be good at?"

### 2. Architecture Constraints — SOURCE
Anything that constrains design freedom and is *not* itself a decision the architect gets to make: mandated technologies, regulatory and compliance rules, organizational conventions, target platforms, licensing, team or budget limits. Split into technical, organizational, and conventions constraints. **This is a SOURCE section**: the TRD author and spec authors read it as the boundary conditions every downstream design must respect.

### 3. Context and Scope
The system's boundaries and its environment. **Business context** names the external actors and neighboring systems and the domain-level inputs/outputs exchanged with each. **Technical context** maps those same relationships onto concrete channels, protocols, and interfaces. This is exactly the scope a C4 *System Context* diagram visualizes; `c4-diagramming` reads this section to draw level 1.

### 4. Solution Strategy — SOURCE
The fundamental decisions and solution approaches that shape the architecture: technology choices, top-level decomposition style, how the key quality goals are achieved, and the organizational approach. It is a *summary* — the dense, high-signal overview that sets direction. **This is a SOURCE section**: it is the primary feed for the TRD's technical-approach narrative.

### 5. Building Block View
The static decomposition of the system into building blocks, refined hierarchically. Level 1 is the whitebox of the whole system; each contained block can be expanded into its own level. This is the structural backbone and maps directly to C4 *Container* and *Component* levels and to UML component/class structure.

### 6. Runtime View
How the building blocks collaborate at runtime for the important scenarios: key use cases, startup, error and recovery flows, cross-cutting interactions. Behavior over time — naturally expressed as UML sequence, activity, or state diagrams drawn by `uml-diagramming`.

### 7. Deployment View
The technical infrastructure the system runs on — environments, nodes, networks, and the mapping of building blocks onto that infrastructure. Maps to C4 *Deployment* diagrams and UML deployment diagrams.

### 8. Crosscutting Concepts — SOURCE
Overarching regularities and solution ideas relevant in multiple parts of the system: domain model, persistence, session handling, security and identity, error handling and logging, internationalization, transaction handling, build and test approach, architectural and design patterns applied. **This is a SOURCE section**: spec authors read it so that individual specs inherit the system-wide concepts instead of re-inventing them.

### 10. Quality Requirements
The full quality tree and concrete quality scenarios, refining the top goals from section 1. Each scenario is testable: a stimulus, the system, and a measurable response. This is what `arc42-verify` checks the rest of the document against.

### 11. Risks and Technical Debt
Known technical risks and accumulated debt, prioritized, each with a mitigation or pay-down note. An honest register, not a marketing page.

### 12. Glossary
The shared vocabulary — domain and technical terms with definitions — so that every other section, every diagram label, and every downstream document means the same thing by the same word.

## The three SOURCE sections

| # | Section | Why it is a SOURCE |
|---|---|---|
| 2 | Architecture Constraints | Boundary conditions every downstream design must respect |
| 4 | Solution Strategy | The high-level technical approach the TRD elaborates |
| 8 | Crosscutting Concepts | System-wide concepts that specs inherit rather than re-derive |

`arc42-extract` reads exactly these three sections and nothing else when producing the feed described in `source-of-truth-map.md`.
