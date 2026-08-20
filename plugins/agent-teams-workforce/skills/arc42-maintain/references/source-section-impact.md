# Source-section impact — downstream reconciliation map

The arc42 SAD is the upstream source for two downstream artifacts:

- the **TRD** (Technical Requirements Document) — derives system-level technical
  and non-functional requirements from the architecture;
- the **Specs** — per-feature specifications whose scope and acceptance criteria
  assume the architecture and the TRD.

When you change a **source** section (2 Constraints, 4 Solution Strategy, 8
Crosscutting Concepts, 9 Architecture Decisions), some downstream item may have
been derived from the *old* content and is now stale. This skill does **not**
edit the TRD or Specs. It **flags** the at-risk items so the owners of those
artifacts can reconcile them.

A reconciliation flag has three parts:

1. **Source** — the SAD section that changed.
2. **Downstream artifact** — the specific TRD requirement or Spec section at risk.
3. **Claim to re-check** — the exact assertion the downstream item made on the
   basis of the old SAD content.

## Section 2 (Constraints) changed

Constraints bound the whole solution, so they reach the *quantified* parts of
downstream artifacts most directly.

| Downstream consumer | Why it is at risk | Re-check |
|---|---|---|
| TRD non-functional requirements | NFRs are usually written *to* a constraint (latency budget, residency, runtime version, cost ceiling, supported platforms) | Does each NFR still match the new constraint's bound? |
| TRD technology/standards requirements | A mandated or banned technology constraint drives "must use / must not use" requirements | Is any required tech now banned, or any banned tech now required? |
| Spec acceptance criteria that quantify a constraint | Criteria like "responds within 200 ms" or "stores data in region eu-central-1" encode the old constraint value | Does each quantified criterion still hold under the new constraint? |
| Spec scope assumptions | A scope may have assumed a capability the new constraint removes (or vice versa) | Is the scope still feasible under the new constraint? |

**Flag template:** `Source: SAD §2 (constraint <name> changed) → Risk: TRD NFR
<id> / Spec <name> §<acceptance> → Re-check: <old quantified value> still valid?`

## Section 4 (Solution Strategy) changed

Strategy changes alter the *shape* of the system, so they reach decomposition
and scope.

| Downstream consumer | Why it is at risk | Re-check |
|---|---|---|
| TRD system-decomposition requirements | The TRD often mirrors the strategy's component/integration breakdown | Does each decomposition requirement still name real components? |
| TRD integration/interface requirements | A move (e.g. sync → async, monolith → service split) changes interface obligations | Are the required interfaces still the ones the new strategy implies? |
| Spec scope that assumed the old structure | A feature scoped against the old component layout may now span different blocks | Is the feature's scope still bounded by the new structure? |
| Spec dependencies | A Spec may depend on a component the strategy removed or relocated | Does each dependency still exist where the Spec expects it? |

**Flag template:** `Source: SAD §4 (strategy change: <from> → <to>) → Risk: TRD
decomposition req <id> / Spec <name> scope → Re-check: <component/interface>
still as assumed?`

## Section 8 (Crosscutting Concepts) changed

Crosscutting concepts are referenced by *many* downstream items at once, so a
change here has the broadest fan-out.

| Downstream consumer | Why it is at risk | Re-check |
|---|---|---|
| TRD crosscutting requirements | Security, logging, error-handling, observability, persistence requirements are derived from section 8 | Does each crosscutting requirement match the new concept? |
| Every Spec that inherits a contract | Specs assume the project-wide auth/logging/error contract without restating it | Does any Spec implicitly rely on the old contract's behaviour? |
| TRD compliance/security requirements | Auth and data-handling concepts often back compliance requirements | Is each compliance requirement still satisfied by the new concept? |

Because the fan-out is wide, flag the **concept** that changed and instruct the
TRD/Spec owners to re-check **every** consumer of that contract, not a single
item. A logging-format change touches all Specs that assert on log output; an
auth-model change touches all Specs with authenticated flows.

**Flag template:** `Source: SAD §8 (concept <name> changed) → Risk: TRD
crosscutting req <id> + ALL Specs inheriting the <name> contract → Re-check:
behaviour assertions against the old <name> contract.`

## How to emit the flags

After reconciling the SAD's internal sections, produce a single **reconciliation
flag list** as the last output of the maintenance pass. Rules:

- One flag per at-risk downstream item (except section-8 wide-fan-out, where one
  flag may name a contract plus "all inheriting Specs").
- Each flag names Source, Downstream artifact, and Claim to re-check.
- Do **not** edit the TRD or Specs. Surfacing the list is the deliverable; the
  owners of those artifacts perform the actual reconciliation.
- If a source change touches no downstream item (rare — usually a purely
  internal clarification), state explicitly "no downstream impact" so the empty
  result is a deliberate finding, not an omission.
