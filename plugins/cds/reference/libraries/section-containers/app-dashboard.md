---
kind: section-container
name: app-dashboard
family: app
aliases: [dashboard, workspace home, home screen, app home page]
status: stable
default_shell: A1
sections:
  - { id: AS1, required: true, notes: "greeting variant; right cluster carries the workspace's new/create actions" }
  - { id: AS2, required: true, notes: "card size variant; typical content: 3 stat cards" }
  - { id: AS3, required: false }
  - { id: AS4, required: true, notes: "renders its empty state until the workspace has activity" }
constraints: []
register:
  motion_register: application-shell
---

# App dashboard

The opening screen of an application workspace: a personalized greeting header, an at-a-glance stat row, a full-width activity card, and a recent-items card that carries the next-action affordance when the workspace is new. Fills the main pane of an app Shell (default A1).

## Determinations

- Stat cards sit in a single row with a `--sp-1-5` gap; the row stacks to the next full-width Section with a `--sp-2-5` vertical gap. Card inner padding is `--sp-2`.
- The greeting form (AS1's greeting variant) personalizes the screen; the recent-items card (AS4) gives the next-action affordance.
