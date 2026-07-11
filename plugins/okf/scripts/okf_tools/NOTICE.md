# Attribution & third-party notices

## Adapted source code

`document.py`, `paths.py`, `index.py`, and `viewer.py` are adapted from the
**OKF reference agent** in Google Cloud's Knowledge Catalog project, © the
Knowledge Catalog authors (Google LLC), licensed under the **Apache License
2.0**. These files remain under Apache 2.0 (they carry an
`SPDX-License-Identifier: Apache-2.0` header); the rest of the plugin is MIT.

- Source: <https://github.com/GoogleCloudPlatform/knowledge-catalog>
- License text (bundled copy): [`LICENSE.apache-2.0`](LICENSE.apache-2.0)

Modifications made for the `okf` Claude Code plugin:

- `document.py` — split validation into a spec floor (`type` only) and a
  stricter reference profile (`type`, `title`, `description`, `timestamp`).
- `paths.py` — allow spaces in concept-id path segments.
- `index.py` — deterministic directory summaries (no LLM/network); `phrase`
  title fallback; runnable as a CLI that reindexes the whole bundle in one pass.
- `viewer.py` — generic per-type color palette (not BigQuery-specific);
  link extraction resolves bundle-relative (`/path.md`) links; the third-party
  browser libraries are inlined from vendored copies so the output HTML is
  fully self-contained (no CDN); rendered markdown is sanitized with DOMPurify.

## Vendored browser libraries (`vendor/`)

Inlined verbatim into generated `viz.html` output:

| File | Library | Version | License |
|------|---------|---------|---------|
| `cytoscape.min.js` | Cytoscape.js | 3.28.1 | MIT |
| `marked.min.js` | marked | 12.0.0 | MIT |
| `purify.min.js` | DOMPurify | 3.1.6 | Apache-2.0 / MPL-2.0 |

Each minified file retains its own license header inline, satisfying the
attribution these licenses require.
