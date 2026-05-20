# External integrations

All free, all public, none requiring credentials. Use Claude Code's `WebFetch` and `WebSearch` tools to access them. Document each query in `prior-art.md`.

## PatentsView API

- **Base URL**: https://search.patentsview.org/api/v1/
- **Auth**: Free API key recommended for higher rate limits. Without key, lower throughput but still functional. Register at https://patentsview.org/apis/keyrequest if needed; otherwise unauthenticated requests work for typical use.
- **Endpoints used**:
  - `POST /patent/` — query US patents by claim text, abstract, CPC code, inventor, assignee
  - `POST /publication/` — query published applications
- **Example query body**:
  ```json
  {
    "q": {
      "_and": [
        {"_text_phrase": {"patent_abstract": "bloom filter"}},
        {"_gte": {"patent_date": "2020-01-01"}}
      ]
    },
    "f": ["patent_id", "patent_title", "patent_date", "assignees"],
    "o": {"size": 25}
  }
  ```
- **Rate limit**: 45 requests/min unauthenticated. Cache aggressively in `patents/prior-art-cache/`.

## Google Patents

- **Base URL**: https://patents.google.com
- **Auth**: None. Public web access.
- **Strategy**: Use `WebSearch` with `site:patents.google.com` and the search terms, or `WebFetch` direct URLs of the form `https://patents.google.com/?q={url-encoded-query}`.
- **Coverage**: Global. Includes US, EP, JP, CN, KR, WO publications with full text where licensed.
- **Limitation**: No structured API for free tier. Treat as a discovery layer; verify hits against the patent office of origin (USPTO PAIR, EPO Espacenet) for citation.

### Google Patents Public Data on BigQuery

- **URL**: https://console.cloud.google.com/marketplace/details/google_patents_public_datasets/google-patents-public-data
- **Auth**: Google Cloud account, free tier covers 1 TB query/month
- **Strategy**: For large-scale landscape queries. Beyond this skill's typical scope; flag to user as advanced option.

## EPO Open Patent Services (OPS)

- **Base URL**: https://ops.epo.org/3.2/
- **Auth**: Free OAuth client credentials. Register at https://developers.epo.org. Anonymous access also available for limited queries.
- **Endpoints used**:
  - `GET /rest-services/published-data/search/biblio` — bibliographic search
  - `GET /rest-services/published-data/publication/epodoc/{number}` — fetch a specific publication
- **Rate limit**: 1,000 queries/week anonymous; higher with free OAuth.
- **Example unauthenticated query**:
  ```
  https://ops.epo.org/3.2/rest-services/published-data/search/biblio?q=ti=(bloom AND filter) AND pd>=20200101
  ```

## arXiv API

- **Base URL**: http://export.arxiv.org/api/query
- **Auth**: None
- **Format**: Atom XML response
- **Example**:
  ```
  http://export.arxiv.org/api/query?search_query=all:%22differential+privacy%22+AND+cat:cs.CR&start=0&max_results=20&sortBy=submittedDate&sortOrder=descending
  ```
- **Categories relevant to software/ML patents**: cs.AI, cs.CR (security), cs.DB, cs.DC (distributed), cs.DS (data structures), cs.LG, cs.OS, cs.PL, cs.SY (systems)

## GitHub code search

- **Base URL**: https://api.github.com/search/code
- **Auth**: GitHub personal access token improves rate limits but isn't required for low-volume search.
- **Strategy**: Search for specific algorithmic patterns or library usage that might constitute prior art.
- **Limitation**: Code search is limited to indexed default branches. Old prior art may be in non-default branches or deleted repos. Use as a supplement, not a primary source.

## Web search

- Use Claude Code's `WebSearch` for general engineering-blog and technical-content prior art.
- Verify hits in higher-tier sources (Tier 1–3) before citing as gating prior art.

## Graceful degradation protocol

If a source is unavailable (rate-limited, network error, API down):

1. Log the failure in `prior-art.md` with the timestamp and source name
2. Proceed with remaining sources
3. State explicitly in the search summary that coverage is partial:

> "PatentsView returned a 429 (rate limit) on 2026-05-19 at 14:23 UTC. Three other sources (Google Patents, arXiv, GitHub) completed. Patent-corpus coverage may be incomplete."

NEVER imply a clean search when a source was skipped.

## Caching

Every successful response is written to `patents/prior-art-cache/{sha256-of-canonical-query}.json`. Before issuing a query, check the cache. Use cached results if less than 30 days old.

Canonical query format: lowercase, whitespace-collapsed, JSON-keys-sorted for API requests.
