#!/usr/bin/env python3
"""
Parse the JSON output from `claude -p --output-format json` and extract
the tool listing response.

Usage: python3 parse_response.py <raw_output_file> <server_name> <result_file>
"""

import json
import sys


def parse(raw_path: str, server_name: str, result_path: str):
    try:
        with open(raw_path) as f:
            raw = f.read()
    except OSError as e:
        write_error(result_path, server_name, f"Cannot read raw output: {e}")
        return

    if not raw.strip():
        write_error(result_path, server_name, "Empty response from claude -p")
        return

    # Try to parse as JSON (claude --output-format json wrapper)
    try:
        wrapper = json.loads(raw)
    except json.JSONDecodeError:
        # Not JSON at all — treat as plain text
        write_error(result_path, server_name, "Response is not valid JSON", raw[:500])
        return

    # Extract the text content from the wrapper
    text = extract_text(wrapper)
    if not text:
        write_error(result_path, server_name, "No text content found in response")
        return

    # Strip markdown fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # skip opening fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    # Parse the inner JSON (the actual tool listing)
    try:
        result = json.loads(cleaned)
        result["status"] = "cataloged"
    except json.JSONDecodeError:
        write_error(result_path, server_name, "Claude response text is not valid JSON", cleaned[:500])
        return

    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)


def extract_text(data: dict) -> str:
    """Navigate various claude output wrapper shapes to find the text."""
    # Shape 1: { "result": { "content": [{"type":"text","text":"..."}] } }
    if "result" in data:
        for block in data.get("result", {}).get("content", []):
            if block.get("type") == "text":
                return block.get("text", "")

    # Shape 2: { "content": [{"type":"text","text":"..."}] }
    if "content" in data and isinstance(data["content"], list):
        for block in data["content"]:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")

    # Shape 3: { "messages": [...], "result": ... } — try messages last item
    if "messages" in data and isinstance(data["messages"], list):
        for msg in reversed(data["messages"]):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            return block.get("text", "")

    return ""


def write_error(result_path: str, server_name: str, error: str, raw_text: str = ""):
    result = {
        "server_name": server_name,
        "tools": [],
        "status": "failed",
        "error": error,
    }
    if raw_text:
        result["raw_text"] = raw_text
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <raw_output_file> <server_name> <result_file>",
              file=sys.stderr)
        sys.exit(1)
    parse(sys.argv[1], sys.argv[2], sys.argv[3])
