---
kind: section
name: prompt-and-templates
id: AS8
family: app
aliases: [quickstart body, prompt and template picker, create-or-browse body]
status: stable
mode: deterministic
content_contract:
  templates: "list of {title, description, starter_text} (content-driven)"
  prompt_placeholder: "placeholder text for the prompt strip"
theme: default
composition_notes:
  - "Selecting a template card populates the prompt strip with that template's starter text and advances the AS7 step breadcrumb to the next step."
---

# AS8 — Prompt and templates

The two-column body of a creation flow: a left prompt column ("start blank") and a right templates panel ("start from a template"), presented side by side with equal standing. Layout is fixed at definition to the `prompt-templates-split` Shape (`libraries/shapes/prompt-templates-split.md`), which carries the full slot and dimension contract.

The prompt strip belongs to this Section's left column — it is not Shell A3's viewport-bottom strip.
