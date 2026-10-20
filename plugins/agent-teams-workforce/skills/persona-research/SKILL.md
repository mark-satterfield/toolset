---
name: persona-research
description: How to write a persona and its jobs-to-be-done that are grounded in evidence - research-based personas and, when the only source is a request, proto-personas whose every element is marked stated, inferred or assumed; behavior over demographics; job stories with functional, emotional and social dimensions; goals, frustrations and context; and the checks a persona passes. Use when writing, revising or reviewing a persona for a feature or a product.
user-invocable: false
---

# Persona research

A persona is a model of one group of people who share a goal and a way of behaving toward it.
It exists so that requirements are written for someone real rather than for an elastic "user"
who stretches to justify any feature. A persona is only as good as the evidence under it.

## Two kinds, and which one you are writing

| Kind | Source | What it may claim |
|---|---|---|
| Research persona | Interviews, observation, support tickets, analytics, surveys | Behaviors, goals and pains the research shows, each traceable to it |
| Proto-persona (assumption persona) | A request, an intake brief, what the team believes | Only what the source states or plainly implies; everything else is an assumption, marked as one |

When you are given no research, you are writing a proto-persona. Say so, and never present an
assumption with the confidence of evidence. A proto-persona is a hypothesis to test later, not a
finding.

## Grounding: every element has a source

Classify each element you write before you write it:

- **Stated**: the source says it. Keep the source's meaning; do not sharpen it.
- **Inferred**: it follows directly from what the source says (a request about applying to jobs
  implies a person who is applying to jobs). Say what it follows from.
- **Assumed**: the source does not say it and it does not follow. Keep it only when the persona
  cannot be written without it, and mark it as an assumption.

Where the output contract has no field for the classification, carry it in the text: name the
assumptions in the summary, and word an assumed goal or frustration as one.

## Behavior over demographics

Segment by what people do and are trying to achieve, not by who they are. Age, gender, a stock
photo name or a hobby add nothing a requirement can use and invite stereotype; include a
demographic or situational fact only when the source states it and it changes behavior (for
example, "applies from a phone between shifts").

## Jobs-to-be-done

A job is the progress a person is trying to make in a situation, independent of any product.

- **Job story:** "When <situation>, I want to <motivation>, so I can <expected outcome>." The
  situation is the trigger; the outcome is what success looks like to the person.
- **Three dimensions:** functional (the task to get done), emotional (how they want to feel or
  avoid feeling), social (how they want to be seen). Name each that the source supports.
- **Solution-free:** a job that names a feature ("I want a dashboard") is a solution, not a job.
  Restate it as the progress the feature would serve.

## Goals, frustrations, context

- **Goals** are the outcomes the person seeks: the "so I can" of their jobs. Few and distinct; a
  persona with more than a handful of goals is several personas or no persona.
- **Frustrations** are the pains of how they get the job done today: obstacles, workarounds,
  risks, wasted effort. Each one is a pain the feature could relieve, stated from the person's
  side, never as the absence of the feature.
- **Context** is the situation that shapes behavior: when and where the job arises, what
  constrains them (time, device, money, knowledge), and what triggers them to act.

## Checks a persona passes

- [ ] It says whether it is a research persona or a proto-persona.
- [ ] Every element is stated, inferred or marked as an assumption; nothing is invented for color.
- [ ] It describes one group with one shared goal and behavior; distinct behaviors are separate
      personas, not a composite.
- [ ] Goals and frustrations are the person's, in their terms, and name no feature.
- [ ] Each frustration is something a requirement could relieve; each goal is something a key
      result could measure.
- [ ] It was not shaped to justify a feature already chosen.

## Anti-patterns

- **The elastic user:** a persona so broad that every feature serves them.
- **Fabricated vividness:** names, ages, quotes and back-stories no source supports.
- **The composite:** two behaviors blended into one person who exists nowhere.
- **The demographic stereotype:** segments by who people are instead of what they do.
- **Assumption as evidence:** an assumed goal stated with the confidence of a finding.
