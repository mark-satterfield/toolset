---
kind: section-container
name: app-dashboard
family: app
aliases: [dashboard, workspace home, home screen, app home page]
status: stable
default_shell: rail-main
sections:
  - { section: page-header, required: true, notes: "greeting variant; right cluster carries the workspace's new/create actions" }
  - { section: kpi-summary, required: true, notes: "card size variant; typical content: 3 stat cards" }
  - { section: activity-card, required: false }
  - { section: recent-list, required: true, notes: "renders its empty state until the workspace has activity" }
constraints: []
register:
  motion_register: application-shell
---

# App dashboard

The opening screen of an application workspace: a personalized greeting header, an at-a-glance stat row, a full-width activity card, and a recent-items card that carries the next-action affordance when the workspace is new. Fills the main pane of an app Shell (default rail-main).

## Determinations

- Stat cards sit in a single row with a `--sp-1-5` gap; the row stacks to the next full-width Section with a `--sp-2-5` vertical gap. Card inner padding is `--sp-2`.
- The greeting form (page-header's greeting variant) personalizes the screen; the recent-items card (recent-list) gives the next-action affordance.
