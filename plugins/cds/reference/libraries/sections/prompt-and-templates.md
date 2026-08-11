---
kind: section
name: prompt-and-templates
aliases: [quickstart body, prompt and template picker, create-or-browse body]
status: stable
shape: prompt-templates-split
content_contract:
  templates: "list of {title, description, starter_text} (content-driven)"
  prompt_placeholder: "placeholder text for the prompt strip"
theme: default
composition_notes:
  - "Selecting a template card populates the prompt strip with that template's starter text and advances the step-breadcrumb step breadcrumb to the next step."
---

# Prompt and templates

The body of a creation flow, offering two entry points with equal standing: a prompt for starting blank, and a templates gallery for starting from a template. Its layout is the `prompt-templates-split` Shape (`libraries/shapes/prompt-templates-split.md`), which carries the full slot and dimension contract.

The prompt strip belongs to this Section's prompt column — it is never a strip pinned to the viewport floor by the Shell.
