---
kind: page
name: app-quickstart
page_family: app
aliases: [quickstart, new project flow, project creation screen, creation wizard, onboarding flow]
status: stable
sections:
  - { section: step-breadcrumb, required: true }
  - { section: prompt-and-templates, required: true }
constraints: []
---

# App quickstart

A multi-step creation flow that presents two entry paths side by side: a "start blank" prompt column and a "start from a template" gallery, beneath a persistent step indicator. Nests in the vacant space of the user's Shell.

The prompt affordance lives **inside** the body Section's left column (see `shapes/prompt-templates-split.md`) — it is part of this Page's content, never a strip pinned to the viewport floor by the Shell; it pins near the bottom of its own column within the body Section.

Suits multi-step creation and onboarding flows where the blank path and the template path deserve equal visual weight, with the step indicator persisting at the top.
