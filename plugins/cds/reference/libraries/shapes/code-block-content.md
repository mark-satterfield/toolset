---
kind: shape
name: code-block-content
page_family: app
aliases: [code block as content, API template empty state, snippet-first screen]
status: stable
slots:
  - { name: page-header, required: true, accepts: [heading] }
  - { name: subhead, required: true, accepts: [usage-instruction] }
  - { name: code-panel, required: true, accepts: [language-picker, copy-action, docs-action, code-listing] }
variants: []
self_contained: false
content_defaults:
  page_title: "Batches"
  subhead: "No batches have been created in the Default workspace. Copy the template below to set up your first batch."
  language: "Python"
---

# code-block-content — Code block as primary content + actions

A developer-facing screen whose primary content is a single full-width code block: a page heading, a one-line subhead carrying a usage instruction, then the code panel. The panel's top bar carries a language picker on the left and Copy Code + View Docs actions (glyph + label each) on the right; the body holds a monospaced code listing with line numbers and syntax highlighting.

The code itself is the call-to-action — the user copies the template and runs it elsewhere.

## HTML skeleton

```html
<header class="page-header"><h1>Batches</h1></header>
<p class="page-subhead">No batches have been created in the <strong>Default</strong> workspace. Copy the template below to set up your first batch.</p>
<section class="code-panel">
  <header class="code-panel__bar">
    <button class="code-panel__lang-picker">Python ▾</button>
    <div class="code-panel__actions">
      <button>⧉ Copy Code</button>
      <button>📄 View Docs</button>
    </div>
  </header>
  <pre class="code-panel__body"><code>
import vendor_sdk  # placeholder — host project's chosen SDK

client = vendor_sdk.Client(…)
batch_job = client.batch_jobs.create(
  requests=[…]
)
print(batch_job)
  </code></pre>
</section>
```

## Determinations

- Language picker: a dropdown trigger (`aria-haspopup="menu"`, `aria-expanded`) offering the host project's supported SDK languages; switching swaps the code body to the equivalent snippet for that language and persists the choice for the session.
- Syntax-highlight token mapping: highlight colors bind to the host project's code-surface role tokens — keywords, strings, comments, and numerics each map to a dedicated `--code-*` role token resolved by the active theme, never hard-coded hex.
- Populated state: once items exist the code block is replaced by the populated table (the empty state and the populated state are mutually exclusive renders of the same route); the "Copy template" affordance moves into a secondary action so the snippet stays reachable.
