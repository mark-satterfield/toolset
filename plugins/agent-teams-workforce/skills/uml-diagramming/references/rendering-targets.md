# Rendering targets — GitHub, Docusaurus, and the PlantUML tradeoff

Mermaid is the default for this skill because it renders directly from Markdown source in the two targets that matter most: GitHub and Docusaurus. The source diffs cleanly in pull requests and needs no image-build step. This reference covers how rendering works in each target and the narrow cases where PlantUML genuinely does more.

## GitHub

GitHub renders Mermaid natively in any Markdown it displays — README files, issues, pull request descriptions, comments, and wiki pages. No configuration, plugin, or action is required.

- Put the diagram in a fenced block tagged `mermaid`. GitHub detects the tag and renders the SVG inline.
- Diagrams render in the file view, in diffs (as the rendered block, not raw text, in the rich view), and in the PR conversation.
- GitHub pins a specific Mermaid version, which can trail the latest release. If a newer Mermaid feature does not render on GitHub, it is usually a version-lag issue, not a syntax error — confirm against the Mermaid live editor.
- There is no theming control from the Markdown side; GitHub applies its own light/dark theme to the diagram.

This native support is the main reason to stay Mermaid-first: a Mermaid diagram in a README is readable the moment it is committed, by anyone, with zero tooling.

## Docusaurus

Docusaurus supports Mermaid through an official theme. It is not on by default — it must be enabled.

1. Install the theme: `npm install @docusaurus/theme-mermaid`.
2. In `docusaurus.config.js`, enable Markdown Mermaid and add the theme:

   ```js
   export default {
     markdown: { mermaid: true },
     themes: ['@docusaurus/theme-mermaid'],
   };
   ```

3. Write diagrams as ordinary ` ```mermaid ` fenced blocks in your `.md` / `.mdx` docs. They render client-side.

Notes:
- Mermaid theming (light/dark, colors) can be configured under `themeConfig.mermaid` so diagrams match the site theme.
- Because rendering is client-side, very large diagrams can be slow to paint; prefer several focused diagrams over one enormous one.
- MDX is stricter than plain Markdown about curly braces and angle brackets in prose, but content *inside* a `mermaid` code fence is treated as code and is not parsed as MDX — so the diagram body is safe.

For exact, current configuration keys, verify against the live Docusaurus docs rather than relying on memory, since theme options evolve between major versions.

## Where Mermaid is weak (and PlantUML is stronger)

Stay Mermaid-first. Reach for PlantUML only when a diagram genuinely exceeds Mermaid's reach, and when you do, say so explicitly and explain the tradeoff rather than switching silently.

| Need | Mermaid | PlantUML |
|---|---|---|
| Native component diagram (lollipop/socket interfaces) | No native grammar — approximate with `flowchart` | First-class `component` grammar with provided/required interfaces |
| Native deployment diagram (nodes, artifacts, stereotypes) | No native grammar — approximate with `flowchart` | First-class `node`, `artifact`, `database` stereotypes |
| Precise UML stereotypes and notation fidelity | Partial | High — closest to the UML spec |
| Large, dense diagrams with fine layout control | Limited layout tuning | More layout control (e.g., `skinparam`, explicit direction, packages) |
| Renders inline on GitHub with zero setup | Yes | No — needs an external renderer or pre-rendered image |
| Renders in Docusaurus from Markdown source | Yes (with the theme) | Needs a plugin or pre-rendered SVG/PNG |
| Diffs as text in PRs | Yes | Yes (but rarely rendered inline where reviewers read) |

**The tradeoff:** PlantUML wins on UML fidelity — it has true component and deployment grammars and tighter notation. Mermaid wins on *reach*: it renders where your readers already are (GitHub, Docusaurus) without a build pipeline or committed image artifacts. For architecture docs that live in a repo and a doc site, that reach usually beats the notation gap. The component and deployment `flowchart` approximations in `mermaid-uml-syntax.md` close most of that gap.

**Decision rule:** Use Mermaid unless the diagram demands strict UML component/deployment notation that the `flowchart` approximation cannot convey honestly. If you switch to PlantUML, note in the doc that this one diagram is PlantUML and why — never mix silently, and never make the reader wonder which tool drew which picture.
