# Search Recipes

Cross-repo search is one of the steward's most-used capabilities. The
human asks "where is X" or "what uses Y" and expects a fast, accurate
answer that spans every relevant repo. This file documents the
patterns the steward uses, both to *follow* recipes that have been
captured in the manifest and to *create* new ones when it learns a
useful search pattern.

## The recipe shape

Every search recipe captured in the manifest's `search_recipes`
section has:

- **Intent** — what the human is trying to find, in their own words.
- **Command** — the actual command or query (`rg`, `grep -r`,
  `gh search code`, Sourcegraph URL, IDE shortcut, etc.).
- **Scope** — which repos to run it across, if relevant.
- **Notes** — caveats, common pitfalls, or expected runtime.

A recipe earns its keep when it captures something non-obvious — the
flag that filters out test files, the directory exclusion that skips
the vendored code, the regex that handles both old and new naming.
Trivial commands ("just run `grep`") do not need recipes.

## Default search tools

When no recipe exists, fall back to these defaults. Walk down the
list and use the first one that's available and appropriate for the
question.

1. **Ripgrep (`rg`)** — fast, respects `.gitignore` by default,
   works on any directory tree. Default for filesystem-scope search.
   ```bash
   rg --type ts "createUser" <parent-dir>
   ```

2. **`git grep`** — repository-scope search that respects the index.
   Useful when you want to scope to one repo and avoid build output.
   ```bash
   git grep -n "createUser"
   ```

3. **`gh search code`** — GitHub-wide code search across an org or
   user. Useful when local clones are missing.
   ```bash
   gh search code --owner <org> "createUser"
   ```

4. **`gh api`** with the search endpoint — when `gh search code` is
   too coarse and you need filters (path, language, repo).

5. **The IDE / Sourcegraph / internal code-search tool** — only if
   the manifest records that the project uses one. Capture the URL
   pattern in a recipe.

## Common patterns

### Finding consumers of a symbol

When the user asks "what uses X" — typically before a rename or
deprecation:

```bash
# parent-folder topology
rg -t ts -t tsx "\\bX\\b" <parent-dir> --files-with-matches
```

For better signal:
- Anchor with `\b` to avoid partial matches.
- Filter by language (`-t ts -t tsx -t py …`) to skip vendored or
  generated files.
- Use `--files-with-matches` for a quick repo-level summary, then
  drill in.

If the symbol is exported via a shared types or contract repo,
prefer searching for the *import path* rather than the symbol name.

### Finding API route definitions

When the user asks "where is the X endpoint defined":

```bash
rg -e "/api/X|@route.*X|router\\.(get|post|put|delete).*X"
```

The exact pattern depends on the framework. Capture per-framework
patterns as recipes the first time you derive them.

### Finding cross-repo type or contract references

When the user asks "where is the User type defined / used":

```bash
# definition site
rg -e "(type|interface|class)\\s+User\\b"

# import sites — the import path is more discriminating than the type
# name, which may collide with locals
rg -e "from\\s+['\"].*types-shared.*User"
```

### Finding the repo that owns a feature

When the user asks "which repo owns X" and the manifest does not
already say:

```bash
# search across all repos; sort hits by repo
rg "<feature-keyword>" <parent-dir> --files-with-matches \
  | xargs -I{} dirname {} | sort -u
```

Then propose the repo with the highest hit density as the owner, and
confirm with the human before recording it.

## Capturing new recipes

Every time you derive a non-obvious search command — one that
required tweaking, scoping, or an excludes flag — capture it as a
recipe. The next steward (or the next agent invocation, or the next
human) should not have to re-derive it.

Capture format in the manifest:

```yaml
search_recipes:
  - intent: Find every consumer of a shared type
    command: >
      rg -e "from\\s+['\"].*types-shared.*<TYPE>" <parent-dir>
    scope: [auth-svc, billing-svc, web-app, mobile-app]
    notes: Replace <TYPE> with the type name. Anchored on the import
      path because type names can collide with local definitions.
```

Recipes that are obvious (`grep -r foo .`) should not be captured —
they add noise. Recipes that involve specific paths, exclusions, or
patterns should always be captured.

## When search is the wrong tool

Some questions look like search but are not:

- **"What does X depend on?"** — answer from the manifest's
  dependency graph, not by grepping for imports.
- **"Who owns X?"** — answer from the manifest's owners or
  `CODEOWNERS`, not by guessing from commit history.
- **"What are the rules about X?"** — answer from the manifest's
  rules section, not by searching docs.

If the manifest can answer a question authoritatively, prefer the
manifest. Search is for things the manifest does not yet know.
