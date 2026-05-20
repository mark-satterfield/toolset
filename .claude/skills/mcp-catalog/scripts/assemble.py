#!/usr/bin/env python3
"""
Assemble the final MCP catalog from discovery + introspection results.

Reads:
  - discovered_servers.json (from discover.py)
  - approved_servers.json (user-filtered subset)
  - introspect_results/<name>.json (from introspect.sh)

Produces a single consolidated JSON catalog.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Assemble MCP tool catalog")
    parser.add_argument("--discovered", default="discovered_servers.json",
                        help="Discovery results file")
    parser.add_argument("--approved", default="approved_servers.json",
                        help="Approved servers file (after user filtering)")
    parser.add_argument("--results-dir", default="introspect_results",
                        help="Directory with introspection results")
    parser.add_argument("--output", default="mcp-catalog.json",
                        help="Output catalog file")
    args = parser.parse_args()

    # Load discovery data
    with open(args.discovered) as f:
        discovered = json.load(f)

    # Load approved list
    approved_names = set()
    if os.path.exists(args.approved):
        with open(args.approved) as f:
            approved = json.load(f)
            approved_names = {s["name"] for s in approved.get("servers", [])}

    results_dir = Path(args.results_dir)
    catalog_servers = []
    total_tools = 0
    cataloged = 0
    skipped = 0
    failed = 0

    for server in discovered["servers"]:
        name = server["name"]
        entry = {
            "name": name,
            "source": server["source"],
            "scope": server["scope"],
            "transport": server["transport"],
            "risk": server["risk"],
        }

        if server["transport"] == "stdio":
            entry["command"] = server.get("command", "")
            entry["args"] = server.get("args", [])
        elif server["transport"] in ("http", "sse"):
            entry["url"] = server.get("url", "")

        if name not in approved_names:
            entry["status"] = "skipped"
            entry["tools"] = []
            reason = "User opted out"
            if server["risk"] == "needs-auth":
                reason += " (requires interactive OAuth)"
            elif server["risk"] == "needs-env":
                reason += " (missing environment variables)"
            entry["error"] = reason
            skipped += 1
            catalog_servers.append(entry)
            continue

        # Look for introspection result
        result_file = results_dir / f"{name}.json"
        if not result_file.is_file():
            entry["status"] = "failed"
            entry["tools"] = []
            entry["error"] = "No introspection result file found"
            failed += 1
            catalog_servers.append(entry)
            continue

        try:
            with open(result_file) as f:
                result = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            entry["status"] = "failed"
            entry["tools"] = []
            entry["error"] = f"Failed to read result: {e}"
            failed += 1
            catalog_servers.append(entry)
            continue

        status = result.get("status", "unknown")
        tools = result.get("tools", [])

        entry["status"] = status
        entry["tools"] = tools
        entry["error"] = result.get("error")

        if status == "cataloged":
            cataloged += 1
            total_tools += len(tools)
        else:
            failed += 1

        catalog_servers.append(entry)

    catalog = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_dir": discovered["project_dir"],
        "servers": catalog_servers,
        "summary": {
            "total_servers": len(catalog_servers),
            "cataloged": cataloged,
            "skipped": skipped,
            "failed": failed,
            "total_tools": total_tools,
        }
    }

    with open(args.output, "w") as f:
        json.dump(catalog, f, indent=2)

    print(f"Catalog written to: {args.output}", file=sys.stderr)
    print(f"  Servers: {len(catalog_servers)}", file=sys.stderr)
    print(f"  Cataloged: {cataloged} ({total_tools} tools)", file=sys.stderr)
    print(f"  Skipped: {skipped}", file=sys.stderr)
    print(f"  Failed: {failed}", file=sys.stderr)


if __name__ == "__main__":
    main()
