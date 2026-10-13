# Finding the documents that describe an entry

The TRD, the specs, the Tasks, a write of decided facts and a review each read the architecture
documents that describe the things they work on. Ask the matrix which documents those are. Then
read the documents and headings it names in full.

## Ask the matrix

The matrix is the one record of how Epics, PRD requirements, features, constraints, architecture
documents, services, components, infrastructure, events, stacks, packages and layers relate. Each
of them is an entry with an id: its kind, a colon and the rest (`feature:<slug>`,
`component:<slug>`, `stack:<stack name>`, `document:<path under the architecture root>`). Read
the matrix with `atw-matrix`; each command prints one JSON object, and a command takes ids, never
names.

- `atw-matrix find --text "<words>"` returns the entries that match the words, ranked. `--kinds
  <kind>,<kind>` limits the result to those kinds, and `--limit <n>` limits how many are printed.
  It is how a name becomes an id. An empty result means the matrix holds no such entry.
- `atw-matrix find --kinds feature --text "<behaviour>"` returns the features that match a
  behaviour, each with the Epics it serves. A shared capability is a feature whose `provides`
  lists the behaviours consumers take from it.
- `atw-matrix node <id>` returns one entry with its relationships: those that start at it under
  each kind's name and those that end at it under the reverse name. For a service, a component, a
  piece of infrastructure, an event, a stack, a layer, a feature or a constraint, `describedBy`
  names the documents that describe it, each with the heading and the document's `lifecycle`. For
  a document, the entry holds its `headings` and `lifecycle`, `describes` names the entries it
  describes, and `disputedBy` names each recorded disagreement that quotes it, which
  `atw-matrix node disagreement:<id>` returns with its ruling once it has one.
- `atw-matrix epic <epic id>` returns what the matrix holds for one Epic and its PRD: each
  requirement, the features that serve it, and the documents and headings that cover it.
  `--constraints` adds the constraints that apply, each with the document and heading it is
  stated in.
- `atw-matrix story-scope --stack <stack id> --ids <entry ids>` returns, for the entries a Story
  builds, the stack and its repository, the documents and headings that describe each entry, the
  constraints that apply and the shared capabilities the work must use.

Every entry and relationship carries `side`. `architecture` means beads, a PRD or an arc42
document states the fact, or the architect designed it: this side is the authority. `repository`
means it was read from what is in a repository today: a hint. The documents that describe
something are found from its architecture-side entry.

## What the matrix says about a document

Each document entry carries the document's `lifecycle`, mirrored from its `lifecycle_state`, and
its `headings`. An `effective` document has been reviewed and approved. An `in-review` or `draft`
document is input to check: read it, and do not assume it is complete or correct. The version a
document belongs to is the folder it lives in: `arc42/` is effective and `built/<element>/` is
built.

A design fact has no entry. Its content stays under its arc42 heading, and the matrix holds the
heading: the `describedBy` relationship from the entry the fact is about names the home document
and heading.

The matrix reads each document's catalog front matter (`view_type`, `scope`, `subject`, `shows`,
`lifecycle_state`) and its headings when `atw-matrix sync-documents` runs, and records
`describedBy` to the entry each name in `shows` and `subject` names. A document written or
changed since the last sync is in the matrix after the next one.

## What each reader reads

| Reader | Reads |
|---|---|
| A design | The constraints the matrix returns for the Epic, the strategy in section 4, and the documents and headings the matrix names for each entry the design touches |
| TRD, specs, Tasks | The documents and headings the matrix names for the entries they concern, and the heading each constraint they cite is stated in |
| A write of decided facts | The home document of each fact in the write request, and each document the matrix lists as describing the same entry |
| A correction from built | The built documents in `built/<element>/`, and the documents the matrix names for each entry they differ on |

## When the matrix has no answer

An entry that no document describes, and a document with missing or invalid catalog front matter,
are reported to the caller by id or by path. The reader does not guess which documents matter, and
does not search the catalog front matter of the architecture root to find them.

Packaged design support files (for example the build specs, HTML, stylesheets and assets of a
design package) are not architecture documents. They have no entry, and a reader follows them only
as design references from the documents that cite them.
