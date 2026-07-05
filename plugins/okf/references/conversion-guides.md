# Converting sources to OKF

Format-specific rules for turning existing material into a conformant
OKF bundle. The universal move is always the same: **one source item →
one concept file with a `type`**, then group into directories, generate
indexes, and weave cross-links.

Golden rules for every source:

- **Never invent data.** Missing schema/URI/type → leave it out or ask.
- **Preserve unknown metadata** as extension frontmatter keys.
- **One concept per file.** Split multi-entity documents.
- **Add `type` to every file** — this is what makes output conformant.

---

## Plain markdown directory

The most common case: a folder of `.md` files that is *almost* OKF.

1. For each file, ensure a frontmatter block exists; add `type` (infer
   from folder name or content — `Reference`, `Playbook`, `Doc`).
2. Lift an H1 or the filename into `title`; write a one-line
   `description`.
3. Convert intra-repo links to bundle-relative (`/path/to.md`) form.
4. Generate `index.md` per directory (`scripts/gen-index.sh`).
5. Validate (`scripts/validate-okf.sh`).

## Obsidian vault

- Convert `[[wikilinks]]` → `[title](./file.md)` (bundle-relative
  preferred). Resolve aliases (`[[file|alias]]`) to the alias as link text.
- Ensure every note has a `type`. Obsidian notes often already have
  frontmatter — keep it, add `type` if absent.
- Move inline `#tags` into the `tags:` frontmatter list.
- Embeds (`![[file]]`) → normal links unless the target is an asset.
- Drop `.obsidian/` config; it is not part of the bundle.

## Notion export (markdown)

- Notion **properties** → frontmatter fields. Map the "Type"/"Category"
  property to `type` when present; otherwise infer.
- **Strip the UUID suffix** Notion appends to filenames and directories
  (`Page abc123def….md` → `page.md`); update links accordingly.
- Convert Notion relative links to bundle-relative markdown links.
- Notion callouts/toggles → standard markdown; keep the content.

## CSV / spreadsheet

- **Each row = one concept.** Choose a key column (first column, an ID,
  or a name) → becomes the filename (slugified).
- Map columns to frontmatter fields: a `type`/`category` column → `type`;
  `name`/`title` → `title`; `summary`/`desc` → `description`; a URL
  column → `resource`.
- Remaining columns → a `# Schema`-style table in the body, or extension
  frontmatter keys if they are metadata rather than content.
- If no column implies a type, ask the user for one `type` to apply to
  all rows.

## Database / warehouse metadata (e.g. BigQuery)

The reference enrichment agent's pattern, applied manually:

1. **One concept per table/view.** `type: BigQuery Table` (or `View`).
   `resource:` = the console/asset URI. `title`/`description` from the
   table's own metadata/description.
2. **Datasets** get a concept too (`type: BigQuery Dataset`) under
   `datasets/`, linking to their tables.
3. Put the column list under a `# Schema` heading as a table
   (Column / Type / Description). Link FK columns to their target
   table's concept.
4. **Do not query data.** OKF captures metadata and curated insight, not
   rows.
5. For automated ingestion at scale, point the user at `kcmd` and the
   reference enrichment agent — see [serving-and-tooling.md](serving-and-tooling.md).

## OpenAPI / GraphQL / event schemas

- One concept per endpoint/operation/event (`type: API Endpoint`,
  `Event`, `Schema`).
- `resource:` = the canonical spec URL or operationId anchor.
- Request/response shapes → `# Schema`; sample calls → `# Examples`.
- **Reference, don't subsume** the source schema — link to the `.yaml`
  or SDL rather than reproducing it wholesale.

---

## After any conversion

1. Generate `index.md` files (`scripts/gen-index.sh <dir>`).
2. Optionally add a bundle-root `index.md` with `okf_version: "0.1"`.
3. Add a `log.md` recording the conversion.
4. Validate (`scripts/validate-okf.sh <bundle>`), then report the tree,
   the file count, and the conformance result.
