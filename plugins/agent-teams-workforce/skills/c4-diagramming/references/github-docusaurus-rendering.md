# Rendering Mermaid C4 in GitHub and Docusaurus

The whole point of authoring C4 in Mermaid (rather than a desktop tool) is that the source
is plain text that renders in the two places architecture docs usually live: GitHub and a
Docusaurus site. The two targets render the *same* fenced block but reach it differently.

---

## GitHub — native, zero config

GitHub renders Mermaid automatically inside Markdown anywhere it renders Markdown:
`README.md` and other `.md`/`.markdown` files, issues, pull request descriptions and
comments, discussions, and gists. You write a fenced code block tagged `mermaid` and GitHub
turns it into an SVG when the page is viewed.

- **How:** a triple-backtick fence with the `mermaid` info string, containing a valid
  diagram whose first line is the C4 kind (`C4Context`, `C4Container`, `C4Component`,
  `C4Deployment`). See `mermaid-c4-syntax.md` for the blocks themselves.
- **No build step, no plugin, no theme config.** It just works on github.com.
- **Versioning:** because the diagram is text, it diffs cleanly in PRs — reviewers see what
  changed in the architecture, line by line.

### GitHub gotchas

- **Mermaid version lag.** GitHub pins a specific Mermaid version and upgrades on its own
  schedule. The C4 diagram kinds are flagged *experimental* in Mermaid, so a syntax feature
  that works in the latest Mermaid playground may not yet be live on github.com. If a block
  fails to render, simplify to the documented element set in `mermaid-c4-syntax.md`.
- **Silent failure on syntax errors.** A malformed block renders as a red error box (or as
  the raw code) rather than failing the page. Preview in the Mermaid Live Editor
  (mermaid.live) before committing.
- **Size limits.** Very large diagrams may be truncated or refused. This is another reason
  to keep one diagram to one C4 level with a modest element count.
- **No custom theme injection.** You cannot load a custom Mermaid theme or config file on
  GitHub; only in-diagram directives (e.g. `UpdateElementStyle`, `UpdateLayoutConfig`,
  `%%{init: ...}%%`) take effect.

---

## Docusaurus — enable the theme, then it's automatic

Docusaurus does **not** render Mermaid out of the box. You opt in with the official theme.

### 1. Install the theme

```bash
npm install --save @docusaurus/theme-mermaid
```

### 2. Enable it in `docusaurus.config.js`

```js
export default {
  // ...
  markdown: {
    mermaid: true,
  },
  themes: ['@docusaurus/theme-mermaid'],
};
```

`markdown.mermaid: true` tells the Markdown loader to treat ```` ```mermaid ```` fences as
diagrams; the theme provides the runtime component that renders them. Both are required.

### 3. Author the diagram

Once enabled, the same fenced `mermaid` block you would put in a GitHub README renders in
your `.md`/`.mdx` docs. You can also render a diagram imperatively with the `<Mermaid>`
component from `@theme/Mermaid` by passing a `value` prop, which is handy when generating a
diagram from data.

### Optional theme configuration

You can set light/dark Mermaid themes so diagrams follow the Docusaurus color mode:

```js
export default {
  themeConfig: {
    mermaid: {
      theme: { light: 'neutral', dark: 'dark' },
    },
  },
  markdown: { mermaid: true },
  themes: ['@docusaurus/theme-mermaid'],
};
```

### Docusaurus gotchas

- **MDX parsing.** In `.mdx` files, the Markdown is parsed as MDX, so stray `<`, `{`, or
  `>` characters *outside* the fenced block can break compilation. Keep diagram text inside
  the fence; keep angle brackets out of surrounding prose or escape them.
- **Mermaid version is pinned by the theme.** The rendered Mermaid version tracks the
  `@docusaurus/theme-mermaid` release, not the latest Mermaid. As with GitHub, the
  experimental C4 kinds may trail the newest Mermaid features — stick to the documented C4
  element set.
- **Color mode contrast.** The default Mermaid theme can be low-contrast in dark mode.
  Configure `theme.dark` (e.g. `'dark'`) so C4 boxes stay legible when users flip to dark.
- **SSR/hydration.** Diagrams render client-side after hydration; a momentary flash of the
  raw block before the SVG appears is expected and not an error.

---

## One source, two targets — practical advice

- Write the diagram **once** to the documented C4 element set so it renders identically on
  GitHub and in Docusaurus. Avoid bleeding-edge Mermaid features that only the newest
  version supports.
- Steer layout only with in-diagram directives (`UpdateLayoutConfig`, `Rel_U/D/L/R`,
  `UpdateElementStyle`) — those are the only knobs both targets honor.
- Validate in mermaid.live before committing; both GitHub and Docusaurus fail visually
  rather than loudly, so the live editor is your fastest feedback loop.
