"""Fidirana amin'ny base SQLite.

Connexion roa no ampiasaina:
- `readonly_connection()`: vakiana fotsiny (mode=ro + authorizer), ho an'ny tools an'ny agent.
- `history_connection()`: manoratra ny tantaran'ny resaka (table `conversations` / `chat_messages`).
"""

import os
import sqlite3
import time

DB_PATH = os.environ.get("DB_PATH", "shop.sqlite")

HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    platform     TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    needs_human  INTEGER NOT NULL DEFAULT 0,
    handoff_note TEXT,
    updated_at   REAL NOT NULL,
    PRIMARY KEY (platform, user_id)
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    platform   TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text       TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages (platform, user_id, id);
"""


def _allowed_tables() -> set[str]:
    raw = os.environ.get("SQL_ALLOWED_TABLES", "products,categories,faq,shipping_zones")
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


def readonly_connection(restrict_tables: bool = False) -> sqlite3.Connection:
    """Connexion tsy afaka manova na inona na inona.

    Raha `restrict_tables` dia ireo tables ao amin'ny SQL_ALLOWED_TABLES ihany no azo vakiana,
    mba tsy hahitan'ny SQL malalaka ny mombamomba ny mpanjifa hafa.
    """
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    allowed = _allowed_tables()

    def authorizer(action, arg1, arg2, _db, _trigger):
        if action == sqlite3.SQLITE_SELECT or action == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            if restrict_tables and (arg1 or "").lower() not in allowed:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    conn.set_authorizer(authorizer)
    return conn


def history_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(HISTORY_SCHEMA)
    return conn


def load_history(platform: str, user_id: str, limit: int = 20) -> list[dict]:
    """Ireo hafatra farany, voalamina ho `messages` an'ny Claude API (user/assistant mifandimby)."""
    with history_connection() as conn:
        rows = conn.execute(
            "SELECT role, text FROM chat_messages WHERE platform = ? AND user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (platform, user_id, limit),
        ).fetchall()
    messages: list[dict] = []
    for row in reversed(rows):
        if messages and messages[-1]["role"] == row["role"]:
            messages[-1]["content"] += "\n\n" + row["text"]
        else:
            messages.append({"role": row["role"], "content": row["text"]})
    # Tsy maintsy manomboka amin'ny `user` ny resaka
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def save_message(platform: str, user_id: str, role: str, text: str) -> None:
    now = time.time()
    with history_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (platform, user_id, role, text, created_at) VALUES (?, ?, ?, ?, ?)",
            (platform, user_id, role, text, now),
        )
        conn.execute(
            "INSERT INTO conversations (platform, user_id, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT (platform, user_id) DO UPDATE SET updated_at = excluded.updated_at",
            (platform, user_id, now),
        )


def needs_human(platform: str, user_id: str) -> bool:
    with history_connection() as conn:
        row = conn.execute(
            "SELECT needs_human FROM conversations WHERE platform = ? AND user_id = ?",
            (platform, user_id),
        ).fetchone()
    return bool(row and row["needs_human"])


def set_needs_human(platform: str, user_id: str, note: str, value: bool = True) -> None:
    with history_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (platform, user_id, needs_human, handoff_note, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT (platform, user_id) DO UPDATE SET "
            "needs_human = excluded.needs_human, handoff_note = excluded.handoff_note, "
            "updated_at = excluded.updated_at",
            (platform, user_id, int(value), note, time.time()),
        )


def describe_schema() -> str:
    """Ny schéma an'ireo tables azon'ny SQL malalaka vakiana."""
    allowed = _allowed_tables()
    with readonly_connection() as conn:
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    return "\n\n".join(r["sql"] for r in rows if r["name"].lower() in allowed) or "(tsy misy table)"
