# Obsidian CLI — Troubleshooting

Common failure modes and fixes. Read this when an `obsidian` command returns an unexpected error, hangs, or produces no output.

> Adapted from the third-party Obsidian-CLI-skill project. See `platforms.md` for setup-time gotchas.

## Quick reference

| Problem | Likely cause | Fix |
|---|---|---|
| Empty output / hangs | Obsidian not running, or admin terminal on Windows | Start Obsidian; use a normal-privilege terminal |
| `command not found: obsidian` | CLI not registered in `PATH` | Re-enable CLI in Settings → Command line interface; restart terminal |
| Unicode / encoding errors | Bug in Obsidian < 1.12.2 | Update Obsidian |
| Wrong vault targeted | Multi-vault ambiguity | Pass vault name as first arg: `obsidian "My Vault" <cmd>` |
| IPC socket not found (Linux) | `PrivateTmp=true` in systemd | Set `PrivateTmp=false` in the service unit |
| Snap confinement issues | Snap restricts IPC | Use the `.deb` package instead of snap |
| `obsidian "Name" command` returns `Error: Command "Name" not found` | Vault-name matching glitch in some setups | Omit the vault name (CLI targets the most recently active vault) and switch vaults manually in the UI |
| `property:set name=tags value="a, b"` writes a literal comma-separated string, not a YAML array | The CLI stores `value` as-is; it does not parse list syntax | For real YAML arrays: edit frontmatter directly (`read` → modify → `create overwrite`) or use `obsidian eval` to call the Obsidian API |
| Colon subcommand returns exit 127, no error message (Windows) | `Obsidian.com` redirector missing — outdated installer | Reinstall from [obsidian.md/download](https://obsidian.md/download) |
| Colon subcommand returns exit 127 (Git Bash / MSYS2) | Bash resolves `obsidian` to `.exe` instead of `.com` | Create a `~/bin/obsidian` wrapper — see `platforms.md` |
| `template:insert` returns `Error: No active editor. Open a file first.` | `template:insert` operates on the currently active editor in the UI; it has no `path=` parameter | To create a file from a template via CLI, use `obsidian create path="..." template="..."` instead |
| `obsidian eval code="..."` fails with a token error on multiline JS | `eval` requires single-line JavaScript | Write the script to a temp file and inline it: `obsidian eval code="$(cat /tmp/script.js)"` |

## Filtering noise

GPU and Electron warnings on headless Linux are harmless. Filter them out:

```bash
obsidian search query="x" 2>/dev/null
```

## When in doubt

```bash
obsidian help              # always-current command list
obsidian version           # confirm you're on v1.12+
obsidian vaults            # confirm IPC works at all
```

If `vaults` works but a specific command fails, the problem is in your command syntax — re-check parameter quoting and `key=value` form. If `vaults` itself fails, the problem is environmental — see `platforms.md`.
