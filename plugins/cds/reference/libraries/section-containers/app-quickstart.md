---
kind: section-container
name: app-quickstart
family: app
aliases: [quickstart, new project flow, project creation screen, creation wizard, onboarding flow]
status: stable
default_shell: A1
sections:
  - { id: AS7, required: true }
  - { id: AS8, required: true }
constraints: []
register:
  motion_register: application-shell
---

# App quickstart

A multi-step creation flow that presents two entry paths side by side: a "start blank" prompt column and a "start from a template" gallery, beneath a persistent step indicator. Fills the main pane of an app Shell (default A1).

The prompt affordance lives **inside** the body Section's left column (see `shapes/prompt-templates-split.md`) — it is not Shell A3's full-width bottom strip. The two are distinct: the Shell strip pins to the viewport floor of the main column; this container's prompt strip pins near the bottom of its own column within the body Section.

Suits multi-step creation and onboarding flows where the blank path and the template path deserve equal visual weight, with the step indicator persisting at the top.
