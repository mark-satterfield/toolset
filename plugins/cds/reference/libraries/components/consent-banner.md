---
kind: component
name: consent-banner
page_family: shared
aliases: [consent banner, cookie banner, cookie consent]
status: stable
slots:
  - { name: heading, required: true, accepts: [heading] }
  - { name: body, required: true, accepts: [text] }
  - { name: accept-action, required: true, accepts: [primary-button] }
  - { name: reject-action, required: true, accepts: [secondary-button] }
  - { name: preferences-link, required: false, accepts: [tertiary-button] }
sizing:
  radius: "24px"
  padding: "32px desktop; 16px mobile"
behavior: [non-blocking, persistence]
accessibility: [region-role, natural-tab-order]
token_bindings:
  - --text-primary
  - --text-secondary
composite: false
---

# Consent banner

A bottom-right pinned card for cookie or consent disclosures that does not block page interaction: pinned card + heading + body + accept/reject actions. Uses a local `deep` wrapper for its ground. Static at rest.

## Determinations

- 24px radius; 32px desktop / 16px mobile padding.
- The card is bottom-right pinned, never a centered modal. The page underneath remains fully interactive — no backdrop wash.

## Action buttons

Two actions: Accept rendered as a primary button and Reject rendered as a secondary button (`libraries/components/button.md`), Accept leading. An optional "Manage preferences" tertiary link sits below the action row.

## Focus order

When the banner mounts, focus is not auto-moved (the banner is non-blocking and the page stays interactive). The banner's controls insert into the natural Tab order immediately after the topbar so a keyboard user reaches them early. The banner is a `role="region"` with `aria-label="Cookie consent"`.

## Persistence semantics

Both Accept and Reject persist the user's choice (cookie or local-storage flag) so the banner does not reappear on subsequent visits. Dismissing without choosing is not offered — the banner stays until an explicit Accept or Reject. "Manage preferences" opens the dialog (`libraries/components/dialog.md`) for granular category toggles.
