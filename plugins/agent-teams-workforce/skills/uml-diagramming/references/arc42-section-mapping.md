# Mapping UML diagrams to arc42 sections

arc42 is a template for architecture documentation; this project's SAD uses eleven numbered sections. A diagram is not just a picture — it occupies a slot in that narrative, and putting it in the wrong section confuses readers who navigate arc42 by section number. This reference fixes which UML type belongs in which section, and why.

## The four sections this skill targets

| arc42 section | Name | UML type that belongs here | What it answers |
|---|---|---|---|
| 5 | Building Block View | **Component** diagram | What are the parts of the system and how are they wired? |
| 6 | Runtime View | **Sequence** and **State** diagrams | How do the parts behave and interact over time? |
| 7 | Deployment View | **Deployment** diagram | Where does the software run, on what infrastructure? |
| 8 | Crosscutting Concepts | **Class** diagram (domain model) | What is the system's domain vocabulary and structure? |

## Section 5 — Building Block View → Component diagram

Section 5 is the static decomposition of the system into building blocks, refined level by level (the "white box / black box" hierarchy arc42 describes). This is exactly what a **component diagram** communicates: the major parts, their responsibilities, and the interfaces between them.

- Level 1 component diagram = the overall system broken into top-level building blocks.
- Each building block can be expanded into its own lower-level component diagram, mirroring arc42's nested white-box refinement.
- Keep it interface-focused. Internal class detail does not belong in section 5.

## Section 6 — Runtime View → Sequence and State diagrams

Section 6 describes behavior: how building blocks collaborate at runtime to carry out important scenarios. Both behavioral UML types live here.

- **Sequence diagrams** capture *scenarios* — one use case or request traced through the participants in order ("place order", "authenticate"). arc42's runtime view is explicitly scenario-driven, which is the sequence diagram's native job.
- **State diagrams** capture the *lifecycle* of a key stateful entity whose behavior over time the reader must understand (an order's states, a connection's modes). When the important runtime behavior is "what state is it in and what moves it", a state diagram belongs in section 6.

Pick the behavioral diagram by what the scenario needs: ordered collaboration between many participants → sequence; the changing mode of one entity → state.

## Section 7 — Deployment View → Deployment diagram

Section 7 maps software building blocks onto infrastructure — hardware, VMs, containers, networks, and their distribution. That is precisely the **deployment diagram**: nodes, the artifacts that run on them, and the communication paths between nodes.

- Show regions/zones, hosts/clusters/containers, and the protocols on the links.
- This is *where*, not *what* — keep logical decomposition out (that is section 5).
- A reader in section 7 is usually ops, SRE, or security reasoning about failure domains and network paths; give them the topology, not the class model.

## Section 8 — Crosscutting Concepts → Class diagram (domain model)

Section 8 holds concepts that cut across building blocks — and the **domain model** is the prime example. A **class diagram** of the domain entities, their attributes, and their relationships is the canonical artifact here. It establishes the shared vocabulary the rest of the document (and the code) relies on.

- Model domain concepts and their relationships (association, composition, inheritance, multiplicity).
- This is the "ubiquitous language" rendered visually — nouns and rules, not framework classes.
- Other crosscutting concerns (security model, persistence, error handling) may also carry class-level diagrams in section 8 when they describe a structural concept used throughout.

## At a glance

```
arc42 §5  Building Block View   ──▶  Component diagram   (parts + interfaces)
arc42 §6  Runtime View          ──▶  Sequence diagram    (scenario, ordered)
arc42 §6  Runtime View          ──▶  State diagram       (entity lifecycle)
arc42 §7  Deployment View       ──▶  Deployment diagram  (nodes + artifacts)
arc42 §8  Crosscutting Concepts ──▶  Class diagram       (domain model)
```

## Why the mapping matters

Readers navigate arc42 by intent: "show me the structure" → 5, "show me how it behaves" → 6, "show me where it runs" → 7, "show me the domain" → 8. Placing a deployment diagram in the Building Block View, or a class diagram in the Runtime View, breaks that navigation and makes the document harder to trust. Author the right UML type, then drop it into the section a reader will look for it in.
