#!/usr/bin/env bash
# Render every Mermaid diagram in the given files to PNG, for visual inspection.
#
# Usage: render-check.sh <out-dir> <file.md|file.mmd> [more files ...]
#
# A Markdown file has each ```mermaid block rendered to <out-dir>/<name>-<n>.png (n counts the
# blocks from 1); a .mmd file is rendered to <out-dir>/<name>.png. Every PNG path is printed.
# Exits non-zero when any file fails to render, after printing `FAIL <file>` for each one. The
# PNGs are verification evidence: look at each one; a clean exit proves the source parses, not
# that the image is readable.
#
# The .mmd files are batched so they share one browser start (render_batch). A failed batch falls
# back to rendering each file on its own, so every failure still names its file.
set -euo pipefail

readonly MERMAID_CLI_VERSION="12.2.0"
mmdc=(npx -y "@mermaid-js/mermaid-cli@${MERMAID_CLI_VERSION}")
render_options=(-s 2 -b white)

failed=0
taken=$'\n'
batch_sources=()
batch_names=()
work_dir=""

# Pick the output name of a source: its base name, or <base name>-<position> when that name is
# already used by an earlier source of this run or by a file in the output folder.
output_name() {
  local src="$1" position="$2" out_dir="$3" name
  name="$(basename -- "$src")"
  name="${name%.*}"
  if [[ "$taken" == *$'\n'"$name"$'\n'* || -e "$out_dir/$name.md" || -e "$out_dir/$name.png" || -e "$out_dir/$name-1.png" ]]; then
    name="$name-$position"
  fi
  printf '%s\n' "$name"
}

# Whether a .mmd source can be written as one fenced block: no line of it opens or closes a fence.
batchable() {
  ! grep -Eq '^[[:space:]]*(```|:::)' -- "$1"
}

render_mmd() {
  local src="$1" png="$2"
  if "${mmdc[@]}" -i "$src" -o "$png" "${render_options[@]}" >&2; then
    printf '%s\n' "$png"
  else
    printf 'FAIL %s\n' "$src" >&2
    failed=1
  fi
}

render_markdown() {
  local src="$1" out_dir="$2" name="$3" n
  if ! grep -q '^[[:space:]]*```mermaid' -- "$src"; then
    printf 'SKIP %s: no mermaid block\n' "$src" >&2
    return
  fi
  if "${mmdc[@]}" -i "$src" -o "$out_dir/$name.md" -e png "${render_options[@]}" >&2; then
    rm -f -- "$out_dir/$name.md"
    n=1
    while [[ -e "$out_dir/$name-$n.png" ]]; do
      printf '%s\n' "$out_dir/$name-$n.png"
      n=$((n + 1))
    done
  else
    printf 'FAIL %s\n' "$src" >&2
    failed=1
  fi
}

# Render every batched .mmd source in one CLI run; on success move each block's PNG to its name.
# Returns non-zero, leaving nothing in the output folder, when the run fails or a PNG is missing.
render_batch() {
  local out_dir="$1" work_dir="$2" k
  local input="$work_dir/batch-input.md" output="$work_dir/batch.md"
  : >"$input"
  for k in "${!batch_sources[@]}"; do
    {
      printf '```mermaid\n'
      cat -- "${batch_sources[$k]}"
      printf '\n```\n\n'
    } >>"$input"
  done
  if ! "${mmdc[@]}" -i "$input" -o "$output" -e png "${render_options[@]}" >&2; then
    printf 'the batched render of %s diagrams failed; rendering each on its own\n' "${#batch_sources[@]}" >&2
    return 1
  fi
  for k in "${!batch_sources[@]}"; do
    if [[ ! -f "$work_dir/batch-$((k + 1)).png" ]]; then
      printf 'the batched render left no image for %s; rendering each on its own\n' "${batch_sources[$k]}" >&2
      return 1
    fi
  done
  for k in "${!batch_sources[@]}"; do
    mv -- "$work_dir/batch-$((k + 1)).png" "$out_dir/${batch_names[$k]}.png"
    printf '%s\n' "$out_dir/${batch_names[$k]}.png"
  done
}

main() {
  if [[ "$#" -lt 2 ]]; then
    printf 'usage: render-check.sh <out-dir> <file.md|file.mmd> [more files ...]\n' >&2
    exit 2
  fi
  local out_dir="$1" src name index=0 k
  shift
  mkdir -p -- "$out_dir"
  work_dir="$(mktemp -d)"
  trap 'rm -rf -- "$work_dir"' EXIT

  for src in "$@"; do
    index=$((index + 1))
    if [[ ! -f "$src" ]]; then
      printf 'FAIL %s: no such file\n' "$src" >&2
      failed=1
      continue
    fi
    name="$(output_name "$src" "$index" "$out_dir")"
    taken+="$name"$'\n'
    case "$src" in
      *.mmd)
        if batchable "$src"; then
          batch_sources+=("$src")
          batch_names+=("$name")
        else
          render_mmd "$src" "$out_dir/$name.png"
        fi
        ;;
      *)
        render_markdown "$src" "$out_dir" "$name"
        ;;
    esac
  done

  if [[ "${#batch_sources[@]}" -gt 0 ]] && ! render_batch "$out_dir" "$work_dir"; then
    for k in "${!batch_sources[@]}"; do
      render_mmd "${batch_sources[$k]}" "$out_dir/${batch_names[$k]}.png"
    done
  fi

  exit "$failed"
}

main "$@"
