#!/usr/bin/env bash
# Render every Mermaid diagram in the given files to PNG, for visual inspection.
#
# Usage: render-check.sh <out-dir> <file.md|file.mmd> [more files ...]
#
# A Markdown file has each ```mermaid block rendered to <out-dir>/<name>-<n>.png (n counts the
# blocks from 1); a .mmd file is rendered to <out-dir>/<name>.png. Every PNG path is printed.
# Exits non-zero when any file fails to render. The PNGs are verification evidence: look at each
# one; a clean exit proves the source parses, not that the image is readable.
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: render-check.sh <out-dir> <file.md|file.mmd> [more files ...]" >&2
  exit 2
fi

out_dir="$1"
shift
mkdir -p "$out_dir"

mmdc=(npx -y @mermaid-js/mermaid-cli)
failed=0
index=0

for src in "$@"; do
  index=$((index + 1))
  if [ ! -f "$src" ]; then
    echo "FAIL $src: no such file" >&2
    failed=1
    continue
  fi
  name="$(basename "$src")"
  name="${name%.*}"
  if [ -e "$out_dir/$name.md" ] || [ -e "$out_dir/$name.png" ] || [ -e "$out_dir/$name-1.png" ]; then
    name="$name-$index"
  fi
  case "$src" in
    *.mmd)
      if "${mmdc[@]}" -i "$src" -o "$out_dir/$name.png" -s 2 -b white >&2; then
        echo "$out_dir/$name.png"
      else
        echo "FAIL $src" >&2
        failed=1
      fi
      ;;
    *)
      if ! grep -q '^[[:space:]]*```mermaid' "$src"; then
        echo "SKIP $src: no mermaid block" >&2
        continue
      fi
      if "${mmdc[@]}" -i "$src" -o "$out_dir/$name.md" -e png -s 2 -b white >&2; then
        rm -f "$out_dir/$name.md"
        n=1
        while [ -e "$out_dir/$name-$n.png" ]; do
          echo "$out_dir/$name-$n.png"
          n=$((n + 1))
        done
      else
        echo "FAIL $src" >&2
        failed=1
      fi
      ;;
  esac
done

exit "$failed"
