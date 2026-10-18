---
name: shell-coding
description: How to write bash and sh scripts and hooks that are shellcheck-clean and safe the first time — a known interpreter, strict mode and where it does not protect, quoting every expansion, arrays for argument lists, [[ ]] and $( ), reading files and command output without word splitting, never parsing ls, traps and temporary-file cleanup, errors to stderr and never discarded, explicit exit codes, and flags that work on both BSD (macOS) and GNU (Linux). Use whenever writing, editing, refactoring or reviewing a shell script, a hook script or a Taskfile or CI step that holds more than one command.
user-invocable: true
---

# Shell: quoted, strict and portable by construction

A shell script runs with the full authority of whoever runs it, and the shell's defaults are unsafe: unquoted
variables split and expand as globs, a failing command does not stop the script, and an error message can vanish.
Write every script so that a filename with a space, an empty variable or a failing command produces a clear error,
never a wrong action. ShellCheck then confirms the script and never corrects it.

These rules apply to every shell script an agent writes, changes or reviews: standalone scripts, hook scripts, and
multi-line steps in a Taskfile or CI workflow. A reviewer judges the script against them.

When a script grows past about 100 lines, needs data structures beyond a flat array, or parses JSON or YAML beyond a
single `jq` filter, write it in Python instead (load `python-coding`). The reason: shell has no types, no real error
handling and no data structures, so complex logic in shell is fragile however carefully it is written.

## How to read this skill

- Every rule has one form: the instruction, then the reason, then at most one example.
- An example is two labelled code blocks, "Instead of" and "Write". The "Instead of" block shows the habit the rule
  bans. An example illustrates its rule; the rule covers every case its text describes, not only the case shown.
- A code in parentheses, such as (SC2086), names the ShellCheck check that reports the same thing.

## Habits to replace on sight

| Do not | Do instead | Section |
|---|---|---|
| `rm $file`, `cp $src $dest` | `rm -- "$file"`, `cp -- "$src" "$dest"` | Quoting |
| `args="--flag $value"; cmd $args` | `args=(--flag "$value"); cmd "${args[@]}"` | Arrays |
| `for f in $(ls *.txt)` | `for f in ./*.txt` | Files and output |
| `cmd 2>/dev/null` | Let stderr through, or capture it and report it | Errors and output |
| `local result=$(cmd)` | `local result` then `result=$(cmd)` | Strict mode |
| `cd "$dir"` followed by more commands | `cd "$dir" \|\| exit 1`, or `git -C`, or a subshell | Strict mode |
| `` `cmd` `` | `$(cmd)` | Syntax |

## Interpreter

- Start every script with a shebang that names its interpreter: `#!/usr/bin/env bash` for bash, `#!/bin/sh` for
  POSIX sh. Write only the syntax that interpreter supports: in an `sh` script, no `[[ ]]`, arrays, `local -r`,
  `$'...'`, `<( )` or `{a,b}` brace expansion (ShellCheck reports bashisms in `sh` scripts).
- Know which bash runs the script. macOS ships bash 3.2 at `/bin/bash`; `#!/usr/bin/env bash` runs the first `bash`
  on `PATH`, which may be 3.2 or a newer one. Use bash 4 features (`mapfile`/`readarray`, associative arrays,
  `${var,,}`, `&>>`) only where the script's documented runtime guarantees bash 4 or later; otherwise write the
  3.2-compatible form (a `while IFS= read -r` loop instead of `mapfile`).
- Make a script that is meant to be run executable and run it directly; make a file that is meant to be sourced
  (`. lib.sh`) not executable, without strict mode of its own (Strict mode), and declare its interpreter for
  ShellCheck with `# shellcheck shell=bash` on the first line.

## Strict mode

- Start every bash script that is run (not sourced) with `set -euo pipefail`:
  - `-e` stops the script when a command fails, instead of carrying on with a wrong state.
  - `-u` makes an unset variable an error, instead of an empty string that turns `rm -rf "$dir/"` into `rm -rf /`.
  - `-o pipefail` makes a pipeline fail when any command in it fails, not only the last.
  In POSIX `sh`, write `set -eu` (`pipefail` is not available in every `sh`).
- Do not set strict mode in a file that is sourced into an interactive shell or into another script: it changes the
  options of the shell that sourced it.
- Know where `-e` does not stop the script, and handle those places yourself:
  - A command that is tested (`if cmd`, `cmd && other`, `cmd || other`, `while cmd`) does not stop the script, and
    neither does any command inside a function called in such a test.
  - `local var=$(cmd)` and `export var=$(cmd)` hide the failure of `cmd` behind the success of `local` (SC2155).
    Declare and assign separately.

    Instead of:

    ```bash
    local commit_id=$(git rev-parse HEAD)
    ```

    Write:

    ```bash
    local commit_id
    commit_id=$(git rev-parse HEAD)
    ```

  - A command substitution inside another command's arguments hides its failure: `cd "$(find_root)"` runs
    `cd ""` when `find_root` fails (SC2312). Assign the substitution to a variable first, then use the variable.
  - `((count++))` returns a failure status when `count` was 0. Write `count=$((count + 1))`.
- Handle a command whose non-zero exit is an expected answer explicitly. `grep` exits 1 when nothing matches; write
  `if grep -q "$pattern" "$file"; then ...`, or `matches=$(grep -- "$pattern" "$file") || matches=""` when no match is
  a normal outcome. Never append `|| true` to a command whose failure would mean something is wrong.
- Follow every `cd` with `|| exit 1` (or `|| return 1` in a function) (SC2164), or avoid `cd` with a tool's
  directory flag (`git -C "$repo"`, `make -C`) or a subshell `( cd "$dir" || exit 1; ... )` that leaves the script's
  directory unchanged.

## Quoting

- Quote every expansion: `"$var"`, `"${var}"`, `"$(cmd)"`, `"$@"`, `"${array[@]}"` (SC2086, SC2046). The reason: an
  unquoted expansion is split on whitespace and each word is expanded as a glob, so a path with a space becomes two
  arguments and a value containing `*` becomes a list of files. The only unquoted expansions are inside `[[ ]]` on the
  left side and in arithmetic `$(( ))`, where no splitting happens.
- Write `--` before a list of paths given to a command that accepts options (`rm -- "$file"`, `grep -- "$pattern"
  "$file"`), so a value starting with `-` is not read as an option.
- Use `"$@"` to pass a script's or function's arguments on; never `$*` or unquoted `$@` (SC2068), which split and
  rejoin them.
- Use single quotes for a literal string, double quotes when it contains an expansion, and `printf '%s\n' "$value"`
  to print a value: `echo` interprets backslashes and leading `-n` or `-e` differently between shells.

## Arrays for argument lists

- Build a list of arguments in a bash array and expand it quoted, never in a string (SC2089, SC2090). The reason: a
  string loses the boundaries between arguments, so an argument containing a space or a quote cannot be passed
  correctly.

  Instead of:

  ```bash
  curl_options="--silent --header 'Authorization: Bearer $token'"
  curl $curl_options "$url"
  ```

  Write:

  ```bash
  curl_options=(--silent --header "Authorization: Bearer ${token}")
  curl "${curl_options[@]}" "$url"
  ```

- In POSIX `sh`, which has no arrays, use the positional parameters (`set -- "$@" --flag "$value"`) as the list.

## Syntax

- Use `$(cmd)` for command substitution, never backticks (SC2006): it nests and quotes predictably.
- In bash, test with `[[ ... ]]` (no word splitting, `&&`/`||` inside, pattern and regex matching); in `sh`, use
  `[ ... ]` with every operand quoted. Compare numbers with `-eq`, `-lt` (or `(( ))` in bash), strings with `=` and
  `!=`.
- Use `$(( ))` for arithmetic, never `expr` or `let`.
- Use `command -v tool` to check that a tool exists, never `which` (not POSIX, output differs between systems).
- Use `case` for matching one value against several patterns instead of a chain of `if`/`elif`.

## Files and command output

- Never parse the output of `ls` (SC2045, SC2012). Iterate with a glob (`for path in "$dir"/*.json`), checking that
  the glob matched (`[[ -e "$path" ]] || continue`, or `shopt -s nullglob` in bash), or with `find`.
- Read lines with `while IFS= read -r line; do ...; done < "$file"` (SC2162): `-r` keeps backslashes and `IFS=` keeps
  leading and trailing spaces. Read command output the same way from `< <(cmd)` in bash, not by piping into `while`,
  which runs the loop in a subshell so its variable changes are lost.
- Process `find` results null-delimited, so any filename works: `find "$dir" -name '*.log' -print0 | while IFS= read
  -r -d '' path; do ...; done`, or `find ... -exec cmd {} +`.
- Fill an array from command output with `mapfile -t lines < <(cmd)` where bash 4 is guaranteed, otherwise with a
  `while IFS= read -r` loop; never `lines=( $(cmd) )` (SC2207), which splits on spaces and expands globs.
- Parse JSON with `jq` and YAML with `yq`, never with `grep`, `sed` or `awk`. Pass values into `jq` with `--arg`
  (`jq --arg name "$name" '.[$name]'`), never by splicing them into the filter.

## Temporary files and cleanup

- Create temporary files and folders with `mktemp` (`tmp_dir=$(mktemp -d)`), never with a fixed name such as
  `/tmp/output.txt`, which collides between runs and can be pre-created by another user.
- Remove them in an `EXIT` trap set immediately after creating them, so they are removed however the script ends:

  ```bash
  tmp_dir=$(mktemp -d)
  trap 'rm -rf -- "$tmp_dir"' EXIT
  ```

- Never run a destructive command on a path that could be empty or computed wrongly. Check the variable first
  (`[[ -n "$target_dir" ]] || exit 1`), or use `${target_dir:?}` to stop the script when it is empty.

## Errors and output

- Never discard stderr (`2>/dev/null`, `&>/dev/null`, `>/dev/null 2>&1`). The reason: the discarded message is the
  only explanation of a failure, and the next person to debug the script has nothing to go on. When a command's
  error output is expected and not useful, capture it (`error_output=$(cmd 2>&1)`) and report it if the command
  fails. Discarding stdout of a command whose output is not needed (`>/dev/null`) is fine.
- Write diagnostics and errors to stderr (`printf 'error: %s\n' "$message" >&2`) and only the script's real output
  to stdout, so the script can be used in a pipeline.
- Give every failure a message that names what failed and with which input, then exit non-zero. Define one function
  for it:

  ```bash
  die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
  }
  ```

- Document the meaning of the script's exit codes where a caller depends on them (a hook whose exit code is its
  contract), and exit with exactly those codes.

## Structure and naming

- Put the logic in functions and call a `main` function at the end with the script's arguments (`main "$@"`), so the
  whole file is read before anything runs and each step has a name.
- Declare every variable a function uses with `local`. Use `readonly` for constants.
- Name local variables in `lower_snake_case`; reserve `UPPER_SNAKE_CASE` for exported environment variables and
  constants that configure the script. The reason: a lower-case name never collides with an environment variable the
  shell or a tool uses (`PATH`, `HOME`, `IFS`).
- Use environment variables or arguments for paths and settings; never hard-code a user's home folder or a
  machine-specific path.
- Validate arguments at the top of `main`: the count, that required values are non-empty, that paths exist. Print a
  usage line and exit 2 on a usage error.

## Portability between macOS (BSD) and Linux (GNU)

Scripts run on macOS for developers and on Linux in CI and containers; write the form that works on both.

- `sed -i` takes a required suffix argument on BSD (`sed -i ''`) and an optional attached one on GNU. Do not use
  `sed -i`: write to a temporary file and move it over the original, or use a tool with a portable in-place mode.
- Use `sed -E` and `grep -E` for extended regular expressions; `grep -P` (Perl syntax) does not exist on BSD.
- `date -d` (GNU) and `date -j -f` (BSD) differ. Do date arithmetic in a language with a date library, or use only
  `date +FORMAT` and `date -u`.
- `readlink -f` and `realpath` are missing on older macOS. Resolve a script's own folder with `cd -- "$(dirname --
  "${BASH_SOURCE[0]}")" && pwd -P` assigned to a variable.
- `xargs -r`, `find -printf`, `stat -c` and `base64 -w` are GNU-only; `stat -f` is BSD-only. Use `find -exec`,
  `wc -c < file` for a size, and `base64 | tr -d '\n'`.
- `mktemp` needs no template on either system when called as `mktemp` or `mktemp -d`.

## ShellCheck directives

- Fix the script rather than disabling a check. A directive is written only for a verified false positive: `#
  shellcheck disable=SC2016` on the line before the command, naming one check, with a comment saying why the check
  does not apply.
- Tell ShellCheck where a sourced file is (`# shellcheck source=lib/common.sh`) instead of disabling SC1091.

## The safety net

Where the repository's hooks run ShellCheck on each edited script and at commit, fix every finding they report and do
not run it yourself; where no hook runs it, run `shellcheck` on the changed scripts before finishing. Then run the
script once with realistic input, including a path that contains a space, as the probe that the checks cannot be.
