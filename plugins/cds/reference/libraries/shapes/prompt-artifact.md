---
kind: shape
name: prompt-artifact
family: landing
aliases: [prompt and response demo, input/output panel, AI demo panel]
status: stable
slots:
  - { name: prompt-column, required: true, accepts: [prompt-example] }
  - { name: artifact-column, required: true, accepts: [text, code, image] }
variants: [text-artifact, code-artifact, image-artifact]
self_contained: false
content_defaults:
  prompt: "a mock user prompt to an AI assistant"
  artifact: "the mock AI-generated artifact the prompt produces"
---

# prompt-artifact — Two-column prompt/artifact panel

A horizontal two-column split with fixed roles: an input example on the left, the artifact it produces on the right.

## Determinations

- The prompt/artifact roles are fixed: prompt always left, artifact always right — the left-to-right order mirrors the cause-then-effect reading. Columns are 50/50 on the 12-column grid (each spans 6); the grid gutter (`foundations/layout.md` §11.6) separates them.
- Exactly one prompt/artifact pair per Shape instance; several examples repeat the shape as separate Sections, never stacked pairs within one instance.
- The artifact renders per its type: text in body type, code in the code-block Component (components library), image in a contained tile. Below the tablet breakpoint (`foundations/responsive.md` §17.1) the columns stack with prompt above artifact.
- The AI prompt-and-response pairing is content: the declared defaults in `content_defaults` are the drafted-mode scaffold; supplied content overrides them.
