---
kind: shape
name: cta-newsletter
family: landing
aliases: [newsletter signup, email capture, subscribe section]
status: stable
slots:
  - { name: headline, required: true, accepts: [headline] }
  - { name: subhead, required: true, accepts: [subhead] }
  - { name: cta-group, required: true, accepts: [button] }
  - { name: newsletter-form, required: true, accepts: [email-input, submit-button] }
  - { name: status-message, required: true, accepts: [status-text] }
variants: [single-cta, dual-cta]
self_contained: true
content_defaults: {}
---

# cta-newsletter — CTA panel with newsletter form

A cta-panel plus an inline email-capture form with submit and status. Inherits the cta-panel slot, layout, and variant contract (`libraries/shapes/cta-panel.md`); the newsletter form sits inline within the band.

## Determinations

- The form sits below the CTAs as the Section's final affordance: the CTAs lead, the form captures intent for those who scroll to it. Input and submit sit on one row at desktop and stack in the mobile-narrow band (`foundations/responsive.md` §17.1).
- The form uses the standard text-input and primary button Component contracts (components library); required-field and email-format validation follow `foundations/accessibility.md` §18.6, with the status message rendered in the status slot under `aria-live="polite"`.
- The validation and status behavior is shape-level: the fragment carries its own scoped `<style>` and IIFE `<script>` scoped to its own instance, so multiple copies on one page never collide.
