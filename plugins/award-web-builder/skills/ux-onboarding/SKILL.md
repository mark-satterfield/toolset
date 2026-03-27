---
Name: ux-onboarding
name: ux-onboarding
description: Design onboarding flows that get users to value fast. Use when building sign-up flows, welcome screens, product tours, feature introductions, or any first-run experience. Also use when designing AI feature onboarding, contextual guidance, or progressive disclosure patterns.
Category: UX Design
Tier: STANDARD
Dependencies: None
Author: mark-satterfield
Version: 1.0.0
---

# UX Onboarding Design

## Name

ux-onboarding

## Description

Design onboarding experiences that get users to value fast without overwhelming them. This skill covers the full spectrum — from sign-up to first meaningful action — with specific guidance for AI-powered products.

## Features

- Five core UX onboarding principles
- Anti-pattern catalog for common onboarding mistakes
- AI-enhanced onboarding patterns (adaptive flows, copilot onboarding, progressive AI disclosure)
- Onboarding flow element reference (welcome screen, profile wizard, guided tour, etc.)
- Design checklist for validation
- SaaS-specific onboarding guidance

## Five Principles

### 1. Keep it simple
Focus on essentials only. Highlight 1-2 key actions that enable initial productivity. Do not attempt to explain every feature upfront.

### 2. Fast-track to value
Enable users to experience core product benefits immediately. Allow profile completion in phases — minimal fields first, full profile later. Never delay value discovery behind setup requirements.

### 3. Personalize without overloading
Ask setup questions to gauge user priorities, then surface the 1-2 most relevant features — not all available options. Balance customization with simplicity.

### 4. Progressive disclosure
Introduce features, actions, and steps gradually as they become relevant. Spread information over time. Surface contextual guidance when users interact with specific features, not before.

### 5. Contextual guidance
Provide tips and prompts within the interface itself. Use supportive microcopy adjacent to confusing elements. Embed explanations in dropdowns, form fields, and inline hints — not external help pages.

---

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Information overload | Users overwhelmed/bored by excessive features shown at once | Focus only on essentials; use progressive disclosure |
| Feature-centric design | Shows product capabilities instead of addressing user goals | Center the flow around what users want to achieve |
| Mandatory long tours | Users lose control and interest | Make walkthroughs skippable; allow fast-forwarding |
| Neglected iteration | Stale onboarding diverges from evolving user needs | Establish continuous testing and refinement |
| One-size-fits-all | Same flow for every user regardless of role or intent | Segment by role, goal, or experience level |

---

## AI-Enhanced Onboarding

For SkillSpoke specifically — an AI-powered product:

### Adaptive flows
Respond to user behavior in real-time. If a user skips a step, don't force it — adapt the remaining flow. If they're exploring confidently, reduce guidance. If they're hesitating, offer more.

### AI feature introduction
When introducing AI features for the first time:
- Set expectations about what the AI can and cannot do
- Show a quick example of the AI in action before asking users to try it
- Make it clear the user is always in control (edit, reject, override)
- Don't oversell capabilities — trust is built through honesty

### Copilot onboarding
SkillSpoke's AI chat is a copilot. Introduce it contextually:
- Show the copilot when the user encounters a task it can help with
- Demonstrate with a real example from their data, not generic placeholder content
- Allow dismissal without penalty — the copilot should reappear when relevant, not nag

### Progressive AI disclosure
Don't explain the entire AI system at once. Reveal capabilities as users encounter situations where they're useful:
- First session: basic chat assistance
- After first project: suggest automations based on observed patterns
- After sustained use: surface advanced features like bulk actions, predictions, analytics

---

## Onboarding Flow Elements

Use these as building blocks — not all are required for every flow:

- **Welcome screen** — establish the product's personality and set expectations. One screen, one message, one CTA.
- **Setup questions** — 2-3 questions maximum to personalize the experience. Role, primary goal, experience level.
- **First action prompt** — guide the user to complete one meaningful action that delivers immediate value.
- **Contextual tooltips** — appear when the user first encounters a feature, not before. Dismiss on interaction.
- **Progress indicator** — only if the flow has 3+ steps. Show where they are and how much remains.
- **Empty states** — when a screen has no data yet, use the empty state as onboarding: explain what will appear here and how to populate it.
- **Celebration moments** — mark the completion of meaningful milestones. Use the celebratory spring profile (more bounce, slightly slower).

---

## Design Checklist

- Clear onboarding goal defined (what does "done" look like for this user?)
- Value shown prominently — not just features listed
- Lean content — only essentials, nothing "nice to know"
- Interactive — learn by doing, not by reading
- Progressive — information revealed as needed, not all at once
- Friction minimized at every step (simplified sign-up, sensible defaults)
- Personalized based on role or stated goal
- Skippable — users can exit at any point and return later
- AI features introduced honestly with clear capabilities and limitations
- Tested and iterated — onboarding is never "done"

---

## Metrics to Design For

- **Time to first value** — how quickly does the user experience the core benefit?
- **Completion rate** — what percentage of users finish the onboarding flow?
- **Drop-off points** — where do users abandon the flow?
- **Feature adoption** — do users actually use the features introduced during onboarding?
- **Return rate** — do users come back after their first session?

---

## Psychology

- Users form snap judgments about products within seconds
- Cognitive overload from excessive information causes abandonment
- Sense of control and autonomy increases engagement
- Immediate value experience drives retention
- Personality and tone humanize the experience and build trust
- Users now expect individualized guidance, not one-size-fits-all tours

---

## SkillSpoke-Specific Guidance

SkillSpoke is a career intelligence platform for a 54-year-old career engineer building it solo. The target users are professionals navigating career transitions.

### Emotional context
Users arriving at SkillSpoke may be stressed, uncertain, or overwhelmed. The onboarding should feel:
- **Empathetic** — acknowledge the emotional weight of career decisions
- **Warm** — Amber accents, conversational microcopy, spring animations with personality
- **Confident** — the interface should signal "we've got this" without being dismissive

### First-run priorities
1. Establish what the user is looking for (role type, industry, career stage)
2. Show one meaningful insight immediately — a matching opportunity, a skill gap analysis, or a market trend relevant to their profile
3. Introduce the AI copilot by having it do something useful, not by explaining what it can do

### What NOT to do
- Don't show an empty dashboard and say "get started by adding your profile"
- Don't explain every feature in the sidebar
- Don't require a complete profile before showing value
- Don't use corporate onboarding language ("Let's set up your workspace!")

---

## Usage

Use this skill when designing sign-up flows, welcome screens, product tours,
feature introductions, or any first-run experience. Apply the five principles
and anti-pattern checklist to evaluate existing onboarding or design new flows.

## Examples

- "Design an onboarding flow for our SaaS app" — apply the five principles with progressive disclosure
- "Review this sign-up flow" — check against anti-patterns and the design checklist
- "Add AI copilot onboarding" — use the AI-enhanced onboarding patterns section
