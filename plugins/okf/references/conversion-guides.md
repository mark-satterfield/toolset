# Converting sources to OKF

Format-specific rules for turning existing material into a conformant OKF
bundle. The universal move is always the same: **one source item → one
concept file with a `type`**, then group into directories, generate indexes,
and weave cross-links.

Process a source as a nested loop, not a flat pass:

1. **Directory setup.** Identify the directory (or source) type and run its
   one-time setup.
2. **Per file.** Convert each file, assuming the directory type but not
   trusting it.
3. **Finalize.** Index, log, and validate the directory.

The directory type tells you the *likely* `type` of the files inside. It is a
strong prior, not a guarantee. Any file can sit in any directory.

---

## Golden rules

Apply to every source and every file:

- **Never invent data.** Missing schema/URI/type → leave it out or ask.
- **Preserve unknown metadata** as extension frontmatter keys.
- **One concept per file.** Split multi-entity documents.
- **Ensure a frontmatter block exists.** Add one if the file has none.
- **Add `type` to every file.** This is what makes output conformant.
- **Don't trust file extensions.** Any file parsable as text could be a
  recognized type. Recognize by content, not by name or suffix.
- **Binary and non-text sources still convert.** A PDF, DOCX, XLSX, PPTX,
  image, or audio file is a source item too. Extract it to Markdown first with
  the `to-markdown-util` skill, then treat the result like any other file.
- **Deterministic first, obvious-fill second.** Each type's explicit mapping
  rules are mandatory. For non-deterministic fields the rules don't populate,
  fill from an obvious source when one exists (see *Per-file conversion*,
  step 3).

---

## Directory setup

Identify the directory type and run its setup once, before touching individual
files.

### Obsidian vault

- Drop `.obsidian/` config; it is not part of the bundle.

### Notion export (markdown)

- **Strip the UUID suffix** Notion appends to directory names
  (`Section abc123def…/` → `section/`) and update links accordingly.
  Per-file filename stripping happens in the file pass.

### Plain markdown directory

- No special setup. Go straight to the per-file pass.

### Structured sources (CSV, database, API specs)

Not folder scans. One source expands into many concepts, so their rules live
in the per-file pass under their own type. A structured file can also turn up
*inside* a folder scan (a stray `.csv` in an Obsidian vault); the per-file
recognizer handles that case.

---

## Per-file conversion

Run this for **every file** in the directory, including files the native app
ignores — a `.csv` or `.pdf` is not a native Obsidian type, but the file still
exists and still needs converting.

**Step 1: assume the directory type.**
Apply that type's file rules (below) as the default path.

**Step 2: verify, and re-dispatch if wrong.**
If the content does not match the assumed type, recognize the actual type and
apply *its* rules instead. Example: a Notion export dropped into an Obsidian
vault. The extension may be `.md` either way, so check the content — Notion
property blocks and UUID-suffixed names signal a Notion page, not an Obsidian
note. A non-text file (PDF, DOCX, image…) is extracted to Markdown first with
the `to-markdown-util` skill, then dispatched on the extracted content.

**Step 3: fill obvious gaps.**
After the deterministic mapping, inspect the target for conformance fields the
rules did not populate, and fill each from the most obvious available source.
Best-effort only: fill when the value is obvious, otherwise leave it (golden
rule: never invent data).

These are only examples:
- `title` missing → a title-like field in the source frontmatter, else an H1,
  else the filename.
- `description` missing → a `description`/`summary` field in the source
  frontmatter, else the body, else write a one-line description.

### File rules by type

#### Plain markdown

- Add `type` (infer from folder name or content: `Reference`, `Playbook`,
  `Doc`).
- Convert intra-repo links to bundle-relative (`/path/to.md`) form.

#### Obsidian note

- Convert `[[wikilinks]]` → `[title](./file.md)` (bundle-relative preferred).
  Resolve aliases (`[[file|alias]]`) to the alias as link text.
- Ensure the note has a `type`. Obsidian notes often already carry
  frontmatter; keep it, add `type` if absent.
- Move inline `#tags` into the `tags:` frontmatter list.
- Embeds (`![[file]]`) → normal links unless the target is an asset.

#### Notion page (markdown)

- Notion **properties** → frontmatter fields. Map the "Type"/"Category"
  property to `type` when present; otherwise infer.
- **Strip the UUID suffix** from the filename (`Page abc123def….md` →
  `page.md`) and update links accordingly.
- Convert Notion relative links to bundle-relative markdown links.
- Notion callouts/toggles → standard markdown; keep the content.

#### Binary / non-text documents (PDF, DOCX, XLSX, PPTX, images, audio)

- **Extract to Markdown first** with the `to-markdown-util` skill (it wraps
  MarkItDown). Then dispatch the extracted Markdown on its recognized type and
  run steps 1–3 on the result.
- **Keep the original asset** in the bundle and set `resource:` to its
  bundle-relative path, so the concept links back to the source of record.
- If extraction yields little or nothing (e.g. a scanned, text-less PDF), fall
  back to a stub concept — `type: Reference`, a `title`/`description`, and the
  `resource:` link. Never fabricate body content.

#### CSV / spreadsheet

One file expands into many concepts.

- **Each row = one concept.** Choose a key column (first column, an ID, or a
  name) → becomes the filename (slugified).
- Map columns to frontmatter fields: a `type`/`category` column → `type`;
  `name`/`title` → `title`; `summary`/`desc` → `description`; a URL column →
  `resource`.
- Remaining columns → a `# Schema`-style table in the body, or extension
  frontmatter keys if they are metadata rather than content.
- If no column implies a type, ask the user for one `type` to apply to all
  rows.

#### Database / warehouse metadata (e.g. BigQuery)

The reference enrichment agent's pattern, applied manually. One source expands
into many concepts.

1. **One concept per table/view.** `type: BigQuery Table` (or `View`).
   `resource:` = the console/asset URI. `title`/`description` from the table's
   own metadata/description.
2. **Datasets** get a concept too (`type: BigQuery Dataset`) under
   `datasets/`, linking to their tables.
3. Put the column list under a `# Schema` heading as a table (Column / Type /
   Description). Link FK columns to their target table's concept.
4. **Do not query data.** OKF captures metadata and curated insight, not rows.
5. For automated ingestion at scale, point the user at `kcmd` and the
   reference enrichment agent; see
   [serving-and-tooling.md](serving-and-tooling.md).

#### OpenAPI / GraphQL / event schemas

One source expands into many concepts.

- One concept per endpoint/operation/event (`type: API Endpoint`, `Event`,
  `Schema`).
- `resource:` = the canonical spec URL or operationId anchor.
- Request/response shapes → `# Schema`; sample calls → `# Examples`.
- **Reference, don't subsume** the source schema: link to the `.yaml` or SDL
  rather than reproducing it wholesale.

---

## Finalize

Per directory, then once per bundle:

1. Generate `index.md` files — `python3 scripts/okf_tools/index.py <bundle>`
   reindexes every directory in one pass and writes the bundle-root `index.md`
   with `okf_version: "0.1"`.
2. Add a `log.md` recording the conversion.
3. Validate (`scripts/validate-okf.sh <bundle>`), then report the tree, the
   file count, and the conformance result.
