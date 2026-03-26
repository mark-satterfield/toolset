#!/usr/bin/env python3
"""
Back-fill ~/.claude/chat_history.db from existing Claude Code session history.
Captures both user and assistant sides of the conversation.

Covers:
  ~/.claude/projects/-Users-msat1971-git-SkillSpoke/
  ~/.claude/projects/-Users-msat1971-git-SkillSpoke--*/

Run:
  python3 backfill_chat_history.py
  python3 backfill_chat_history.py --dry-run
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".claude" / "chat_history.db"
PROJECTS_ROOT = Path.home() / ".claude" / "projects"

GLOB_PATTERNS = [
    "-Users-msat1971-git-SkillSpoke",
    "-Users-msat1971-git-SkillSpoke--*",
]

CONTENT_FILTERS = re.compile(
    r"^(?:Caveat:|<command|<local-command|This session is being continued|"
    r"<user-prompt-submit-hook>|Analysis:|Base directory for this skill:)"
)


def decode_path(encoded: str) -> str:
    placeholder = "\x00"
    s = encoded.lstrip("-").replace("--", placeholder)
    return "/" + s.replace("-", "/").replace(placeholder, "-")


def extract_user_content(message: dict) -> str | None:
    """
    Extract text content from a user message.
    message.content may be a plain string or a list of blocks.
    Skips tool_result blocks (plumbing, not conversation).
    """
    content = message.get("content", "")
    if isinstance(content, str):
        text = content.strip()
        return text if text and not CONTENT_FILTERS.match(text) else None
    if isinstance(content, list):
        parts = []
        for block in content:
            if block.get("type") == "text":
                t = block.get("text", "").strip()
                if t and not CONTENT_FILTERS.match(t):
                    parts.append(t)
        return "\n\n".join(parts) if parts else None
    return None


def extract_assistant_content(message: dict) -> str | None:
    """
    Extract text content from an assistant message.
    Concatenates text blocks; skips thinking and tool_use blocks.
    """
    parts = []
    for block in message.get("content", []):
        if block.get("type") == "text":
            t = block.get("text", "").strip()
            if t:
                parts.append(t)
    return "\n\n".join(parts) if parts else None


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id           INTEGER PRIMARY KEY,
            encoded_path TEXT UNIQUE NOT NULL,
            decoded_path TEXT NOT NULL,
            name         TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id           INTEGER PRIMARY KEY,
            session_id   TEXT UNIQUE NOT NULL,
            project_id   INTEGER REFERENCES projects(id),
            session_file TEXT NOT NULL,
            git_branch   TEXT,
            slug         TEXT,
            version      TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id           INTEGER PRIMARY KEY,
            uuid         TEXT UNIQUE NOT NULL,
            parent_uuid  TEXT,
            session_id   TEXT NOT NULL,
            project_id   INTEGER REFERENCES projects(id),
            timestamp    TEXT NOT NULL,
            date         TEXT NOT NULL,
            role         TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            prompt_id    TEXT,
            content      TEXT NOT NULL,
            model        TEXT,
            cwd          TEXT,
            git_branch   TEXT,
            is_sidechain INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_messages_date    ON messages(date);
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_messages_project ON messages(project_id);
        CREATE INDEX IF NOT EXISTS idx_messages_prompt  ON messages(prompt_id);
        CREATE INDEX IF NOT EXISTS idx_messages_role    ON messages(role);
        CREATE INDEX IF NOT EXISTS idx_messages_parent  ON messages(parent_uuid);
    """)
    conn.commit()


def upsert_project(conn: sqlite3.Connection, encoded: str) -> int:
    decoded = decode_path(encoded)
    name = Path(decoded).name
    conn.execute(
        "INSERT OR IGNORE INTO projects (encoded_path, decoded_path, name) VALUES (?, ?, ?)",
        (encoded, decoded, name),
    )
    return conn.execute(
        "SELECT id FROM projects WHERE encoded_path = ?", (encoded,)
    ).fetchone()[0]


def upsert_session(
    conn: sqlite3.Connection,
    session_id: str,
    project_id: int,
    session_file: str,
    record: dict,
) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO sessions
           (session_id, project_id, session_file, git_branch, slug, version)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            project_id,
            session_file,
            record.get("gitBranch"),
            record.get("slug"),
            record.get("version"),
        ),
    )


def insert_message(
    conn: sqlite3.Connection,
    record: dict,
    role: str,
    content: str,
    project_id: int,
    session_id: str,
    model: str | None = None,
) -> bool:
    ts = record.get("timestamp", "")
    date = ts[:10] if len(ts) >= 10 else ""
    try:
        conn.execute(
            """INSERT OR IGNORE INTO messages
               (uuid, parent_uuid, session_id, project_id, timestamp, date,
                role, prompt_id, content, model, cwd, git_branch, is_sidechain)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.get("uuid", ""),
                record.get("parentUuid"),
                session_id,
                project_id,
                ts,
                date,
                role,
                record.get("promptId"),
                content,
                model,
                record.get("cwd"),
                record.get("gitBranch"),
                1 if record.get("isSidechain") else 0,
            ),
        )
        return conn.execute("SELECT changes()").fetchone()[0] == 1
    except sqlite3.Error as e:
        print(f"    DB error on {record.get('uuid')}: {e}", file=sys.stderr)
        return False


def process_file(
    conn: sqlite3.Connection,
    jsonl_path: Path,
    project_id: int,
    dry_run: bool,
) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    session_id = None

    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if session_id is None and "sessionId" in record:
                    session_id = record["sessionId"]
                    if not dry_run:
                        upsert_session(conn, session_id, project_id, str(jsonl_path), record)

                cur_session = record.get("sessionId") or session_id or ""
                rtype = record.get("type")

                # ── User messages ──────────────────────────────────────────
                if rtype == "user":
                    if record.get("userType") != "external":
                        continue
                    if record.get("isMeta"):
                        continue
                    content = extract_user_content(record.get("message", {}))
                    if not content:
                        continue
                    if dry_run:
                        inserted += 1
                    elif insert_message(conn, record, "user", content, project_id, cur_session):
                        inserted += 1
                    else:
                        skipped += 1

                # ── Assistant messages ─────────────────────────────────────
                elif rtype == "assistant":
                    msg = record.get("message", {})
                    # Skip streaming partials — only the terminal record has stop_reason
                    if msg.get("stop_reason") is None:
                        continue
                    content = extract_assistant_content(msg)
                    if not content:
                        continue
                    model = msg.get("model")
                    if dry_run:
                        inserted += 1
                    elif insert_message(conn, record, "assistant", content, project_id, cur_session, model):
                        inserted += 1
                    else:
                        skipped += 1

    except OSError as e:
        print(f"  ERROR: {e}", file=sys.stderr)

    return inserted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Back-fill Claude chat history into SQLite.")
    parser.add_argument("--dry-run", action="store_true", help="Count records without writing")
    parser.add_argument("--db", default=str(DB_PATH), help=f"DB path (default: {DB_PATH})")
    args = parser.parse_args()

    db_path = Path(args.db)
    dry_run: bool = args.dry_run

    if dry_run:
        print("DRY RUN — no writes")
        conn = sqlite3.connect(":memory:")
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")

    create_schema(conn)

    total_inserted = 0
    total_skipped = 0
    total_files = 0

    for pattern in GLOB_PATTERNS:
        matches = sorted(PROJECTS_ROOT.glob(pattern))
        for project_dir in matches:
            if not project_dir.is_dir():
                continue

            encoded = project_dir.name
            project_id = upsert_project(conn, encoded)
            if not dry_run:
                conn.commit()

            jsonl_files = sorted(
                f for f in project_dir.glob("*.jsonl")
                if not f.name.startswith("agent-")
            )
            if not jsonl_files:
                continue

            decoded = decode_path(encoded)
            print(f"\n{decoded}  ({len(jsonl_files)} session files)")

            for jf in jsonl_files:
                ins, skp = process_file(conn, jf, project_id, dry_run)
                if not dry_run:
                    conn.commit()
                total_files += 1
                total_inserted += ins
                total_skipped += skp
                if ins or skp:
                    print(f"  {jf.name}: +{ins} new, {skp} already present")

    conn.close()

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Done.")
    print(f"  Files processed  : {total_files}")
    print(f"  Messages inserted: {total_inserted}")
    print(f"  Already present  : {total_skipped}")
    if not dry_run:
        print(f"  DB               : {db_path}")


if __name__ == "__main__":
    main()
