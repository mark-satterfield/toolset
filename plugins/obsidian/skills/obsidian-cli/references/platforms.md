# Obsidian CLI — Platform-specific setup

The Obsidian CLI communicates with a running Obsidian desktop instance via IPC. Each platform has setup quirks. Read this file when the CLI is failing to start, hanging, or returning exit code 127.

> Adapted from the third-party Obsidian-CLI-skill project. Used here for the platform-specific gotchas that kepano's upstream skill does not currently cover.

## Prerequisites

| Requirement | Details |
|---|---|
| Obsidian Desktop | **v1.12.0+** (released February 2026; available to all users — no Early Access or Catalyst license required) |
| CLI enabled | Settings → Command line interface → Toggle ON |
| Obsidian running | The desktop app **must be running** for the CLI to work (it uses IPC) |

## macOS / Linux

The `obsidian` binary is registered in `PATH` automatically when you enable CLI in Settings. No further setup required.

If `obsidian` is not on `PATH` after enabling, restart your terminal so it picks up the new `PATH`.

## Windows

Requires an `Obsidian.com` redirector file placed alongside `Obsidian.exe`. The CLI **must run with normal user privileges** — admin terminals produce silent failures.

### Common Windows failure modes

- **Colon subcommands return exit 127 (e.g. `property:set`, `daily:append`)** — check that `Obsidian.com` exists next to `Obsidian.exe`. If missing, you have an outdated installer. Reinstall from [obsidian.md/download](https://obsidian.md/download).
- **Git Bash / MSYS2 users**: Bash resolves `obsidian` to `Obsidian.exe` (the GUI launcher) instead of `Obsidian.com` (the CLI), causing colon subcommands with parameters to fail with exit 127 even when `Obsidian.com` is present.

  Workaround — create a wrapper script:

  ```bash
  # ~/bin/obsidian
  #!/bin/bash
  /c/path/to/Obsidian.com "$@"
  ```

  Then add `export PATH="$HOME/bin:$PATH"` to `~/.bashrc`.

## Headless Linux (servers, CI, containers)

Use the `.deb` package (not the snap — snap confinement restricts IPC). Run under `xvfb`:

```bash
xvfb-run -a obsidian search query="..."
# or, with a persistent display:
DISPLAY=:5 obsidian read path="note.md"
```

If running as a systemd service: ensure `PrivateTmp=false`. Obsidian's IPC socket lives in `/tmp`, and `PrivateTmp=true` will hide it from other processes.

## Verifying the install

```bash
obsidian version       # prints CLI + Obsidian version
obsidian vaults        # lists all vaults — confirms IPC is working
```

If `vaults` hangs or returns nothing, Obsidian is not running or the IPC socket is not reachable.
