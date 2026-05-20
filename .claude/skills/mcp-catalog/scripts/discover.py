#!/usr/bin/env python3
"""
Discover all MCP server configurations across Claude Code config locations.

Scans:
  - .mcp.json (project root)
  - .claude/settings.json (project scope)
  - .claude/settings.local.json (project local scope)
  - ~/.claude.json (legacy user config)
  - ~/.claude/settings.json (user scope)
  - ~/.claude/settings.local.json (user local scope)
  - ~/.claude/claude_desktop_config.json (Claude Desktop)
  - Installed plugins (.claude/plugins/*/plugin.json and .mcp.json)
  - Plugin cache (~/.claude/plugins/cache/*/*/<version>/.mcp.json)

Outputs discovered_servers.json with risk classification.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone


def expand_path(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def load_json_safe(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [warn] Failed to parse {path}: {e}", file=sys.stderr)
        return None


def extract_mcp_servers(data: dict) -> dict:
    """Extract mcpServers from a config dict, handling different nesting patterns."""
    if not data:
        return {}
    # Direct mcpServers key (used by .mcp.json, .claude.json)
    if "mcpServers" in data:
        return data["mcpServers"]
    # Nested under projects or other keys in settings.json
    if "mcpServers" in data.get("settings", {}):
        return data["settings"]["mcpServers"]
    return {}


_LOG_LEVEL_VALUES = {"DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL", "TRACE"}


def classify_risk(name: str, server_config: dict) -> str:
    """Classify a server's risk level for introspection."""
    transport = detect_transport(server_config)

    if transport in ("http", "sse"):
        headers = server_config.get("headers", {})
        if any("auth" in k.lower() or "token" in k.lower() or "key" in k.lower()
               for k in headers):
            return "safe"  # Has static auth headers
        return "needs-auth"

    if transport == "stdio":
        env = server_config.get("env", {})
        if not env:
            return "safe"

        missing = []
        for var, val in env.items():
            # Skip known log-level values — they're config, not credentials
            if isinstance(val, str) and val.upper() in _LOG_LEVEL_VALUES:
                continue
            # Flag empty values or explicit placeholders, then check the real env
            if not val or val.startswith("${") or "YOUR_" in val:
                if not os.environ.get(var):
                    missing.append(var)
        if missing:
            return "needs-env"
        return "safe"

    return "unknown"


def detect_transport(server_config: dict) -> str:
    """Detect transport type from server config."""
    if "type" in server_config:
        return server_config["type"]
    if "url" in server_config:
        return "http"
    if "command" in server_config:
        return "stdio"
    return "unknown"


def build_server_entry(name: str, config: dict, source: str, scope: str) -> dict:
    transport = detect_transport(config)
    entry = {
        "name": name,
        "source": source,
        "scope": scope,
        "transport": transport,
        "risk": classify_risk(name, config),
        "config": config,
    }
    if transport == "stdio":
        entry["command"] = config.get("command", "")
        entry["args"] = config.get("args", [])
    elif transport in ("http", "sse"):
        entry["url"] = config.get("url", "")
    return entry


def scan_plugin_cache() -> list[dict]:
    """Scan ~/.claude/plugins/cache/ for MCP servers installed by plugins."""
    servers = []
    cache_dir = Path.home() / ".claude" / "plugins" / "cache"
    if not cache_dir.is_dir():
        return servers

    # Layout: cache/<namespace>/<plugin-name>/<version>/.mcp.json
    for namespace_dir in cache_dir.iterdir():
        if not namespace_dir.is_dir():
            continue
        for plugin_dir in namespace_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            for version_dir in plugin_dir.iterdir():
                if not version_dir.is_dir():
                    continue
                mcp_json = load_json_safe(version_dir / ".mcp.json")
                if not mcp_json:
                    continue
                source_label = f"~/.claude/plugins/cache/{namespace_dir.name}/{plugin_dir.name}/{version_dir.name}/.mcp.json"
                for name, config in extract_mcp_servers(mcp_json).items():
                    if config.get("disabled"):
                        continue
                    servers.append(build_server_entry(name, config, source_label, "plugin-cache"))

    return servers


def scan_plugins(project_dir: Path) -> list[dict]:
    """Scan installed plugins for MCP server definitions."""
    servers = []
    plugins_dir = project_dir / ".claude" / "plugins"
    if not plugins_dir.is_dir():
        return servers

    for plugin_path in plugins_dir.iterdir():
        if not plugin_path.is_dir():
            continue

        # Check plugin.json for inline mcpServers
        plugin_json = load_json_safe(plugin_path / "plugin.json")
        if plugin_json and "mcpServers" in plugin_json:
            for name, config in plugin_json["mcpServers"].items():
                servers.append(build_server_entry(
                    name, config,
                    source=f".claude/plugins/{plugin_path.name}/plugin.json",
                    scope="plugin"
                ))

        # Check .mcp.json at plugin root
        mcp_json = load_json_safe(plugin_path / ".mcp.json")
        if mcp_json:
            for name, config in extract_mcp_servers(mcp_json).items():
                servers.append(build_server_entry(
                    name, config,
                    source=f".claude/plugins/{plugin_path.name}/.mcp.json",
                    scope="plugin"
                ))

    return servers


def discover(project_dir: str) -> dict:
    project = Path(project_dir).resolve()
    home = Path.home()
    servers = []
    seen = set()  # Dedupe by (name, command/url)

    config_locations = [
        (project / ".mcp.json",                        "project", ".mcp.json"),
        (project / ".claude" / "settings.json",        "project", ".claude/settings.json"),
        (project / ".claude" / "settings.local.json",  "local",   ".claude/settings.local.json"),
        (home / ".claude.json",                        "user",    "~/.claude.json"),
        (home / ".claude" / "settings.json",           "user",    "~/.claude/settings.json"),
        (home / ".claude" / "settings.local.json",     "user",    "~/.claude/settings.local.json"),
        (home / ".claude" / "claude_desktop_config.json", "desktop", "~/.claude/claude_desktop_config.json"),
    ]

    for path, scope, source_label in config_locations:
        data = load_json_safe(path)
        if not data:
            continue
        mcp_servers = extract_mcp_servers(data)
        if not mcp_servers:
            continue

        print(f"  [found] {source_label}: {len(mcp_servers)} server(s)", file=sys.stderr)
        for name, config in mcp_servers.items():
            dedup_key = (name, config.get("command", config.get("url", "")))
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            servers.append(build_server_entry(name, config, source_label, scope))

    # Scan project-local plugins
    plugin_servers = scan_plugins(project)
    for s in plugin_servers:
        dedup_key = (s["name"], s.get("command", s.get("url", "")))
        if dedup_key not in seen:
            seen.add(dedup_key)
            servers.append(s)
    if plugin_servers:
        print(f"  [found] plugins: {len(plugin_servers)} server(s)", file=sys.stderr)

    # Scan user plugin cache (~/.claude/plugins/cache/)
    cache_servers = scan_plugin_cache()
    for s in cache_servers:
        dedup_key = (s["name"], s.get("command", s.get("url", "")))
        if dedup_key not in seen:
            seen.add(dedup_key)
            servers.append(s)
    if cache_servers:
        print(f"  [found] plugin cache: {len(cache_servers)} server(s)", file=sys.stderr)

    result = {
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "project_dir": str(project),
        "config_locations_scanned": [str(p) for p, _, _ in config_locations],
        "servers": servers,
        "summary": {
            "total": len(servers),
            "safe": sum(1 for s in servers if s["risk"] == "safe"),
            "needs_env": sum(1 for s in servers if s["risk"] == "needs-env"),
            "needs_auth": sum(1 for s in servers if s["risk"] == "needs-auth"),
            "unknown": sum(1 for s in servers if s["risk"] == "unknown"),
        }
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Discover MCP server configurations")
    parser.add_argument("--project-dir", default=os.getcwd(),
                        help="Project root directory (default: cwd)")
    parser.add_argument("--output", default="discovered_servers.json",
                        help="Output file path (default: discovered_servers.json)")
    args = parser.parse_args()

    print("Scanning for MCP server configurations...", file=sys.stderr)
    result = discover(args.project_dir)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nDiscovered {result['summary']['total']} server(s):", file=sys.stderr)
    print(f"  safe:       {result['summary']['safe']}", file=sys.stderr)
    print(f"  needs-env:  {result['summary']['needs_env']}", file=sys.stderr)
    print(f"  needs-auth: {result['summary']['needs_auth']}", file=sys.stderr)
    print(f"  unknown:    {result['summary']['unknown']}", file=sys.stderr)
    print(f"\nWrote: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
