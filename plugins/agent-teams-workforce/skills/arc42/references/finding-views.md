# Finding the documents that describe an element

The TRD, the specs, the Tasks, a write of decided facts and a review each read the architecture
documents that describe the elements they work on. Ask the matrix which documents those are. Then
read the documents and headings it names in full.

## Ask the matrix

The matrix records how elements, features, design facts and architecture documents relate. Read it
with `atw-matrix`; each command prints one JSON object.

- `atw-matrix find --text "<words>"` returns the rows that match the words: elements, features,
  facts, shared capabilities and documents. `--kinds <kind>,<kind>` limits the rows to those kinds,
  and `--limit <n>` limits how many are printed.
- `atw-matrix find --provides "<behaviour>"` returns the shared capabilities that provide a
  behaviour.
- `atw-matrix node <id>` returns one row with its links and the links that point to it. For an
  element these name the documents that describe it. For a fact they name its one home: the
  document and the heading. For a document they name its headings and the rows that link to it.
- `atw-matrix prd <bead>` returns what the matrix holds for one PRD.
- `atw-matrix disagreements --document <path>` returns the recorded disagreements that quote a
  document, each with its settlement when it has one.

Name an element as the glossary and the stack names name it. `atw-matrix node` also answers to a
name only one row has.

## What the matrix says about a document

Each document row carries the document's `lifecycle_state` and whether each of its headings is
approved. An `effective` document has been reviewed and approved. An `in-review` document is input
to check: read it, and do not assume it is complete or correct. The version a document belongs to
is the folder it lives in: `arc42/` is effective and `built/<element>/` is built.

The matrix reads each document's catalog front matter (`view_type`, `scope`, `subject`, `shows`,
`lifecycle_state`) and its headings when `atw-matrix sync-documents` runs. A document written or
changed since the last sync is in the matrix after the next one.

## What each reader reads

| Reader | Reads |
|---|---|
| A design | The constraints in section 2, the strategy in section 4, and the documents and headings the matrix names for each element and fact the design touches |
| TRD, specs, Tasks | The documents the matrix names for the elements they concern, and the home heading of each fact they cite |
| A write of decided facts | The home document of each fact in the write request, and each document the matrix lists as describing the same element |
| A correction from built | The built documents in `built/<element>/`, and the documents the matrix names for each element they differ on |

## When the matrix has no answer

A row that names no document, and a document with missing or invalid catalog front matter, are
reported to the caller by element or by path. The reader does not guess which documents matter.

Packaged design support files (for example the build specs, HTML, stylesheets and assets of a
design package) are not architecture documents. They have no row, and a reader follows them only
as design references from the documents that cite them.
