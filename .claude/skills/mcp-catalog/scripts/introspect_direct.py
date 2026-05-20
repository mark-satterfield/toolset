#!/usr/bin/env python3
"""
introspect_direct.py — Introspect MCP servers directly via JSON-RPC over stdio.

Usage:
    python3 introspect_direct.py <approved_servers.json> <output_dir>

For each stdio server, starts the process, performs the MCP handshake, calls
tools/list, and writes the result to <output_dir>/<server_name>.json.

HTTP/SSE servers are skipped with a 'skipped' status (require live auth).
"""

import json
import os
import subprocess
import sys
import time
import threading
from pathlib import Path

TIMEOUT = int(os.environ.get("INTROSPECT_TIMEOUT", "30"))


def send_message(proc, msg: dict) -> None:
    line = json.dumps(msg) + "\n"
    proc.stdin.write(line.encode())
    proc.stdin.flush()


def read_response(proc, timeout: float = 30.0) -> dict | None:
    """Read lines until we get a valid JSON-RPC response (has 'result' or 'error')."""
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        proc.stdout.flush()
        try:
            proc.stdout.timeout = 1.0  # type: ignore[attr-defined]
        except Exception:
            pass

        # Non-blocking read attempt
        line = _read_line_with_timeout(proc.stdout, remaining=deadline - time.monotonic())
        if line is None:
            continue
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Accept any message that has 'result', 'error', or is a 'tools/list' result
        if "result" in msg or "error" in msg:
            return msg
    return None


def _read_line_with_timeout(stream, remaining: float) -> bytes | None:
    result = [None]
    exc = [None]

    def _read():
        try:
            result[0] = stream.readline()
        except Exception as e:
            exc[0] = e

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout=max(0.1, remaining))
    if t.is_alive():
        return None
    if exc[0]:
        return None
    return result[0]


def introspect_stdio(name: str, config: dict) -> dict:
    command = config.get("command", "")
    args = config.get("args", [])
    env_overrides = config.get("env", {})

    env = dict(os.environ)
    for k, v in env_overrides.items():
        if v:
            env[k] = v

    full_cmd = [command] + args
    try:
        proc = subprocess.Popen(
            full_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
    except (FileNotFoundError, PermissionError) as e:
        return {"server_name": name, "tools": [], "status": "failed", "error": str(e)}

    try:
        # 1. initialize
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "mcp-catalog", "version": "1.0"},
            },
        })

        init_resp = read_response(proc, timeout=TIMEOUT)
        if init_resp is None:
            return {"server_name": name, "tools": [], "status": "failed",
                    "error": "timeout waiting for initialize response"}
        if "error" in init_resp:
            return {"server_name": name, "tools": [], "status": "failed",
                    "error": f"initialize error: {init_resp['error']}"}

        # 2. initialized notification (no response expected)
        send_message(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })

        # 3. tools/list
        send_message(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })

        tools_resp = read_response(proc, timeout=TIMEOUT)
        if tools_resp is None:
            return {"server_name": name, "tools": [], "status": "failed",
                    "error": "timeout waiting for tools/list response"}
        if "error" in tools_resp:
            return {"server_name": name, "tools": [], "status": "failed",
                    "error": f"tools/list error: {tools_resp['error']}"}

        raw_tools = tools_resp.get("result", {}).get("tools", [])
        tools = [
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "input_schema": t.get("inputSchema", {}),
            }
            for t in raw_tools
        ]
        return {"server_name": name, "tools": tools, "status": "cataloged", "error": None}

    finally:
        try:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def main():
    if len(sys.argv) < 3:
        print("Usage: introspect_direct.py <approved_servers.json> <output_dir>", file=sys.stderr)
        sys.exit(1)

    approved_file = sys.argv[1]
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(approved_file) as f:
        data = json.load(f)

    servers = data.get("servers", [])
    total = len(servers)
    print(f"Introspecting {total} MCP server(s) via direct JSON-RPC...", file=sys.stderr)
    print(f"  Timeout per server: {TIMEOUT}s", file=sys.stderr)
    print(f"  Output: {output_dir}/", file=sys.stderr)
    print("", file=sys.stderr)

    for i, srv in enumerate(servers):
        name = srv["name"]
        transport = srv.get("transport", "unknown")
        config = srv.get("config", {})
        result_file = output_dir / f"{name}.json"

        print(f"[{i+1}/{total}] Introspecting: {name}", file=sys.stderr)

        if transport in ("http", "sse"):
            result = {
                "server_name": name,
                "tools": [],
                "status": "skipped",
                "error": f"HTTP transport requires live auth — cannot introspect via stdio",
            }
        else:
            result = introspect_stdio(name, config)

        tool_count = len(result.get("tools", []))
        status = result.get("status", "unknown")
        print(f"  {status} — {tool_count} tool(s)", file=sys.stderr)

        with open(result_file, "w") as f:
            json.dump(result, f, indent=2)

    print("", file=sys.stderr)
    print(f"Introspection complete. Results in: {output_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
