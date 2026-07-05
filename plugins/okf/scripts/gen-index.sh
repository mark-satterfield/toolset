#!/usr/bin/env bash
# OKF index.md generator
# Usage: gen-index.sh [dir]
#
# Generates a conformant index.md for a single directory by listing its
# child concept files and subdirectories, pulling the `title` and
# `description` from each child concept's frontmatter. Prints to stdout;
# redirect to write:
#
#   gen-index.sh ./tables > ./tables/index.md
#
# Rules honored (see spec §6):
#   - No frontmatter (this generator never emits any).
#   - Subdirectories linked with a trailing slash.
#   - Reserved files (index.md, log.md) are excluded from the listing.
#   - Entry text uses the child's `description` when present.

set -euo pipefail

DIR="${1:-.}"
if [ ! -d "$DIR" ]; then
  echo "Error: '$DIR' is not a directory" >&2
  exit 2
fi

# Read a frontmatter field from a file (first match). Empty if absent.
fm_field() {
  local file="$1" key="$2"
  sed -n '2,/^---[[:space:]]*$/p' "$file" | sed '$d' \
    | grep -E "^${key}:" | head -1 \
    | sed "s/^${key}:[[:space:]]*//" | tr -d "\"'" | sed 's/[[:space:]]*$//'
}

# Title cased from a filename slug when no title field exists.
title_from_name() {
  basename "$1" .md | tr '_-' '  '
}

dir_title=$(basename "$DIR")
printf '# %s\n\n' "$dir_title"

# --- Concept files (direct children only) ------------------------------
had_concepts=0
while IFS= read -r file; do
  base=$(basename "$file")
  [[ "$base" == "index.md" || "$base" == "log.md" ]] && continue
  had_concepts=1
  title=$(fm_field "$file" title)
  [ -z "$title" ] && title=$(title_from_name "$file")
  desc=$(fm_field "$file" description)
  if [ -n "$desc" ]; then
    printf '* [%s](%s) - %s\n' "$title" "$base" "$desc"
  else
    printf '* [%s](%s)\n' "$title" "$base"
  fi
done < <(find "$DIR" -maxdepth 1 -name "*.md" -type f | sort)

# --- Subdirectories ----------------------------------------------------
first_sub=1
while IFS= read -r sub; do
  [ "$sub" = "$DIR" ] && continue
  name=$(basename "$sub")
  if [ "$first_sub" -eq 1 ]; then
    [ "$had_concepts" -eq 1 ] && printf '\n'
    printf '# Subdirectories\n\n'
    first_sub=0
  fi
  printf '* [%s](%s/)\n' "$name" "$name"
done < <(find "$DIR" -mindepth 1 -maxdepth 1 -type d | sort)
