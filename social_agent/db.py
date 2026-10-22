"""Fidirana amin'ny base SQLite.

Base roa no ampiasaina:
- `DB_PATH`: ny base an'ny logiciel (stock, vokatra, kaomandy). Vakiana fotsiny, tsy soratana mihitsy.
- `HISTORY_DB_PATH`: base manokan'ny agent (tantaran'ny resaka, fanaraha-maso ny hafatra efa voaray).
"""

import os
import re
import sqlite3
import time

DB_PATH = os.environ.get("DB_PATH", "shop.sqlite")
HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "agent_history.sqlite")

HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    platform     TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    display_name TEXT,
    needs_human  INTEGER NOT NULL DEFAULT 0,
    handoff_note TEXT,
    updated_at   REAL NOT NULL,
    PRIMARY KEY (platform, user_id)
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    platform   TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'staff')),
    text       TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages (platform, user_id, id);
CREATE TABLE IF NOT EXISTS processed_events (
    event_id   TEXT PRIMARY KEY,
    created_at REAL NOT NULL
);
"""


def _allowed_tables() -> set[str]:
    raw = os.environ.get("SQL_ALLOWED_TABLES", "products,categories,faq,shipping_zones")
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


def readonly_connection(restrict_tables: bool = False) -> sqlite3.Connection:
    """Connexion amin'ny base an'ny logiciel, tsy afaka manova na inona na inona.

    Raha `restrict_tables` dia ireo tables ao amin'ny SQL_ALLOWED_TABLES ihany no azo vakiana,
    mba tsy hahitan'ny SQL malalaka ny mombamomba ny mpanjifa hafa.
    """
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
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
    conn = sqlite3.connect(HISTORY_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(HISTORY_SCHEMA)
    return conn


def mark_event_processed(event_id: str) -> bool:
    """Mamerina `False` raha efa voaray io hafatra io (mamerina mandefa indraindray i Meta)."""
    with history_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO processed_events (event_id, created_at) VALUES (?, ?)",
            (event_id, time.time()),
        )
        return cur.rowcount == 1


def load_history(platform: str, user_id: str, limit: int = 30) -> list[dict]:
    """Ireo hafatra farany, voalamina ho `messages` an'ny Claude API (user/assistant mifandimby).

    Ny valin'ny mpiasa (`staff`) dia raisina ho valin'ny mpivarotra mba hahafantaran'ny agent azy.
    """
    with history_connection() as conn:
        rows = conn.execute(
            "SELECT role, text FROM chat_messages WHERE platform = ? AND user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (platform, user_id, limit),
        ).fetchall()
    messages: list[dict] = []
    for row in reversed(rows):
        role = "assistant" if row["role"] in ("assistant", "staff") else "user"
        text = f"[Mpiasa] {row['text']}" if row["role"] == "staff" else row["text"]
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + text
        else:
            messages.append({"role": role, "content": text})
    # Tsy maintsy manomboka amin'ny `user` ny resaka
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def save_message(platform: str, user_id: str, role: str, text: str, display_name: str | None = None) -> None:
    now = time.time()
    with history_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (platform, user_id, role, text, created_at) VALUES (?, ?, ?, ?, ?)",
            (platform, user_id, role, text, now),
        )
        conn.execute(
            "INSERT INTO conversations (platform, user_id, display_name, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (platform, user_id) DO UPDATE SET updated_at = excluded.updated_at, "
            "display_name = coalesce(excluded.display_name, conversations.display_name)",
            (platform, user_id, display_name, now),
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


def list_conversations(only_handoff: bool = False, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM conversations"
    if only_handoff:
        sql += " WHERE needs_human = 1"
    with history_connection() as conn:
        rows = conn.execute(sql + " ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_transcript(platform: str, user_id: str, limit: int = 200) -> list[dict]:
    with history_connection() as conn:
        rows = conn.execute(
            "SELECT role, text, created_at FROM chat_messages WHERE platform = ? AND user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (platform, user_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def describe_schema() -> str:
    """Ny schéma an'ireo tables azon'ny SQL malalaka vakiana."""
    allowed = _allowed_tables()
    with readonly_connection() as conn:
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name"
        ).fetchall()
    return "\n\n".join(r["sql"] for r in rows if r["name"].lower() in allowed) or "(tsy misy table)"


def phone_variants(user_id: str) -> dict:
    """Endrika samihafa amin'ny laharana WhatsApp (261341234567 → 0341234567, +261341234567)."""
    digits = re.sub(r"\D", "", user_id)
    local = "0" + digits[3:] if digits.startswith("261") else digits
    return {"phone_intl": digits, "phone_plus": "+" + digits, "phone_local": local}
