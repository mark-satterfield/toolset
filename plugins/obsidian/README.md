# obsidian

A Claude Code plugin bundling five Agent Skills for working with [Obsidian](https://obsidian.md) — vaults, Markdown, Bases, Canvas, and web capture.

## Credits & lineage

**This plugin is a fork of [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills).**

Heartfelt thanks to **[Steph Ango (@kepano)](https://stephango.com/)** — Obsidian's CEO and the original author of these skills — and to every contributor to the upstream project. The Markdown, Bases, Canvas, Defuddle, and CLI skills below are theirs; this fork wraps them into a Claude Code plugin under the `mark-satterfield` marketplace and packages them alongside small additions to the `obsidian-cli` skill.

The original work is licensed MIT — see `LICENSE`. This repackaging preserves that license verbatim.

## What's in this plugin

| Skill | Purpose |
|---|---|
| `defuddle` | Convert web pages to clean Markdown using the [Defuddle](https://github.com/kepano/defuddle) library — strips ads, navigation, and boilerplate. |
| `json-canvas` | Author `.canvas` files in the [JSON Canvas](https://jsoncanvas.org/) format — nodes, edges, embeds. |
| `obsidian-bases` | Author and edit Obsidian Bases (`.base`) files — the v1.12+ database feature with filters, formulas, and views. Includes a full functions reference. |
| `obsidian-cli` | Automate a running Obsidian vault from the terminal — read/create/edit notes, search, manage tasks, properties, tags, daily notes, plugins, themes, sync, and run JavaScript via `eval`. **Also supports plugin and theme development**: reload plugins, capture errors, take screenshots, inspect the DOM. |
| `obsidian-markdown` | Write Obsidian-flavored Markdown — callouts, embeds, properties (frontmatter), wiki-links. Includes per-feature references. |

All five skills auto-activate via their `description` frontmatter when you ask Claude to do something that matches them (e.g. *"add a task to my daily note"*, *"convert this URL to markdown"*, *"create a base for my book list"*).

## What's different from upstream

This fork is intentionally close to upstream. The only intentional addition lives inside `obsidian-cli/`:

- `obsidian-cli/references/platforms.md` — platform-specific setup (Windows `Obsidian.com` redirector, Git Bash / MSYS2 wrapper, headless Linux / xvfb, snap confinement)
- `obsidian-cli/references/troubleshooting.md` — common-error lookup table (exit 127, IPC socket issues, multi-vault ambiguity, `property:set` list-value behavior, `template:insert` no-active-editor, etc.)

These two files were cherry-picked from the third-party [Obsidian-CLI-skill](https://github.com/) project. They cover deployment gotchas the upstream skill doesn't currently document. The third-party project's 21KB inline command reference and non-standard `triggers:` frontmatter were **not** imported — kepano's "trust `obsidian help`" design is forward-compatible, and the standard `name` + `description` frontmatter is what Claude Code actually matches against.

## Installation

After this plugin is registered in the `mark-satterfield` marketplace:

```
/plugin install obsidian@mark-satterfield
```

Or install just the upstream skills directly from kepano:

```
/plugin marketplace add kepano/obsidian-skills
/plugin install obsidian@obsidian-skills
```

## Prerequisites

- **Obsidian Desktop v1.12.0+** for `obsidian-cli`, `obsidian-bases`, and most `obsidian-markdown` features. v1.12 is available to all users — no Early Access build or Catalyst license required.
- For `obsidian-cli`: enable Settings → Command line interface, and have Obsidian running when invoking commands.

See `skills/obsidian-cli/references/platforms.md` for platform-specific setup.

## License

MIT — see `LICENSE`. Copyright belongs to Steph Ango (@kepano) for the upstream skills; modifications and additions in this fork are released under the same license.
