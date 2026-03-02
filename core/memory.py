"""
core/memory.py — Falcon Agency Persistent Memory
=================================================

UPGRADE v2: Long-term memory that never forgets.

4 layers of memory:
  1. Short-term  — last N messages for conversation context (no time cutoff)
  2. Long-term   — important events/decisions stored permanently with tags
  3. Business facts — key facts about the business stored as named facts
  4. Smart context — builds rich Director context from all 3 layers

Tables:
  messages      — conversation history (max 500 per user)
  long_term     — tagged permanent events (never auto-deleted)
  business_facts— named business facts (e.g. "peak_sale_day" = "Tuesday")
  context       — session context key-value
  topics        — keyword frequency tracking
"""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import log
from core.ist_time import now_ist_str, today_ist

DB_PATH = Path(__file__).parent.parent / "data" / "falcon.db"


class ConversationMemory:
    """
    Long-term persistent memory for Falcon Agency Director.

    Remembers:
    - Full conversation history (no 24h cutoff, max 500 msgs)
    - Important events forever (revenue highs, decisions, issues)
    - Business facts that don't change often
    - Keyword topics the owner frequently asks about
    """

    def __init__(self, max_messages: int = 500, db_path: Path = DB_PATH):
        self._max_messages = max_messages
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    # ── DB Setup ────────────────────────────────────────────────────────────

    def _init_db(self):
        """Create all tables with migrations for existing DBs."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            try:
                # ── 1. Messages (conversation history) ──
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id     TEXT    NOT NULL,
                        role        TEXT    NOT NULL,
                        content     TEXT    NOT NULL,
                        timestamp   TEXT    NOT NULL,
                        message_id  TEXT
                    )
                """)
                # migration: add message_id if missing
                cols = [r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()]
                if "message_id" not in cols:
                    conn.execute("ALTER TABLE messages ADD COLUMN message_id TEXT")

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_messages_user
                    ON messages(user_id, timestamp DESC)
                """)

                # ── 2. Long-term event log ──────────────────────────────────
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS long_term (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        category    TEXT    NOT NULL,
                        title       TEXT    NOT NULL,
                        detail      TEXT,
                        tags        TEXT,
                        timestamp   TEXT    NOT NULL,
                        importance  INTEGER DEFAULT 1
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_lt_cat
                    ON long_term(category, timestamp DESC)
                """)

                # ── 3. Business facts store ──────────────────────────────────
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS business_facts (
                        key         TEXT    PRIMARY KEY,
                        value       TEXT    NOT NULL,
                        updated_at  TEXT    NOT NULL,
                        source      TEXT
                    )
                """)

                # ── 4. Context (session key-value) ──────────────────────────
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS context (
                        user_id     TEXT    NOT NULL,
                        key         TEXT    NOT NULL,
                        value       TEXT    NOT NULL,
                        timestamp   TEXT    NOT NULL,
                        PRIMARY KEY (user_id, key)
                    )
                """)

                # ── 5. Topics ───────────────────────────────────────────────
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS topics (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id         TEXT    NOT NULL,
                        topic           TEXT    NOT NULL,
                        frequency       INTEGER DEFAULT 1,
                        last_mentioned  TEXT,
                        related_intents TEXT
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_topics_user
                    ON topics(user_id, frequency DESC)
                """)

                conn.commit()
                log.info("MemoryDB initialised (%s)", self._db_path.name)
            finally:
                conn.close()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    # ── Short-term: conversation messages ───────────────────────────────────

    def add_message(
        self, user_id: str, role: str, content: str,
        message_id: Optional[str] = None
    ) -> None:
        """Add message. Keeps last max_messages per user — NO time cutoff."""
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO messages (user_id, role, content, timestamp, message_id)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (user_id, role, content, now_ist_str(), message_id)
                )
                # Trim to max_messages
                conn.execute("""
                    DELETE FROM messages WHERE id IN (
                        SELECT id FROM messages WHERE user_id = ?
                        ORDER BY timestamp DESC
                        LIMIT -1 OFFSET ?
                    )
                """, (user_id, self._max_messages))
                conn.commit()
            finally:
                conn.close()

    def get_recent_messages(
        self, user_id: str, limit: int = 12
    ) -> List[Dict]:
        """Get last N messages for AI context. No time cutoff — pure count."""
        return self.get_history(user_id, last_n=limit)

    def get_history(self, user_id: str, last_n: int = 12) -> List[Dict]:
        """Get last N messages. No 24h cutoff — Director remembers always."""
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    """SELECT role, content, timestamp, message_id FROM messages
                       WHERE user_id = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (user_id, last_n)
                ).fetchall()
                return [
                    {"role": r[0], "content": r[1],
                     "timestamp": r[2], "message_id": r[3]}
                    for r in reversed(rows)
                ]
            finally:
                conn.close()

    def get_history_text(self, user_id: str, last_n: int = 5) -> str:
        """Readable conversation history for prompts."""
        history = self.get_history(user_id, last_n)
        if not history:
            return "No previous conversation."
        lines = []
        for msg in history:
            role = "You" if msg["role"] == "user" else "Director"
            c = msg["content"]
            ts = msg.get("timestamp", "")[:16]  # YYYY-MM-DDTHH:MM
            snippet = c[:200] + "..." if len(c) > 200 else c
            lines.append(f"[{ts}] {role}: {snippet}")
        return "\n".join(lines)

    def get_message_by_id(self, user_id: str, message_id: str) -> Optional[Dict]:
        """Find message by WhatsApp message_id."""
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT role, content, timestamp, message_id FROM messages"
                    " WHERE user_id = ? AND message_id = ?",
                    (user_id, message_id)
                ).fetchone()
                return {"role": row[0], "content": row[1],
                        "timestamp": row[2], "message_id": row[3]} if row else None
            finally:
                conn.close()

    def get_message_count(self, user_id: str) -> int:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE user_id = ?", (user_id,)
                ).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    # ── Long-term: permanent event log ──────────────────────────────────────

    def remember(
        self,
        category: str,
        title: str,
        detail: str = "",
        tags: Optional[List[str]] = None,
        importance: int = 1,
    ) -> int:
        """
        Store an important event permanently (never auto-deleted).

        Categories: 'revenue', 'order', 'error', 'decision', 'milestone',
                    'content', 'seo', 'security', 'product', 'customer'

        importance: 1=normal, 2=important, 3=critical

        Returns the event ID.

        Example:
            memory.remember('revenue', 'Best sale day',
                            detail='₹12,400 on Diwali 2025',
                            tags=['diwali','revenue'], importance=3)
        """
        tags_str = json.dumps(tags or [])
        with self._lock:
            conn = self._conn()
            try:
                cur = conn.execute(
                    "INSERT INTO long_term (category, title, detail, tags, timestamp, importance)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (category, title, detail, tags_str, now_ist_str(), importance)
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def recall(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        min_importance: int = 1,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Recall long-term memories filtered by category/tag/importance.

        Example:
            memory.recall(category='revenue', min_importance=2)
            memory.recall(tag='diwali')
        """
        with self._lock:
            conn = self._conn()
            try:
                if category and tag:
                    rows = conn.execute(
                        """SELECT id, category, title, detail, tags, timestamp, importance
                           FROM long_term
                           WHERE category = ? AND tags LIKE ? AND importance >= ?
                           ORDER BY timestamp DESC LIMIT ?""",
                        (category, f"%{tag}%", min_importance, limit)
                    ).fetchall()
                elif category:
                    rows = conn.execute(
                        """SELECT id, category, title, detail, tags, timestamp, importance
                           FROM long_term
                           WHERE category = ? AND importance >= ?
                           ORDER BY timestamp DESC LIMIT ?""",
                        (category, min_importance, limit)
                    ).fetchall()
                elif tag:
                    rows = conn.execute(
                        """SELECT id, category, title, detail, tags, timestamp, importance
                           FROM long_term
                           WHERE tags LIKE ? AND importance >= ?
                           ORDER BY timestamp DESC LIMIT ?""",
                        (f"%{tag}%", min_importance, limit)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT id, category, title, detail, tags, timestamp, importance
                           FROM long_term
                           WHERE importance >= ?
                           ORDER BY importance DESC, timestamp DESC LIMIT ?""",
                        (min_importance, limit)
                    ).fetchall()

                return [
                    {
                        "id": r[0], "category": r[1], "title": r[2],
                        "detail": r[3], "tags": json.loads(r[4] or "[]"),
                        "timestamp": r[5], "importance": r[6],
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def recall_recent(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """Recall long-term events from last N days."""
        from datetime import timedelta
        from datetime import datetime
        since = (datetime.fromisoformat(now_ist_str()) - timedelta(days=days)).isoformat()
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    """SELECT id, category, title, detail, tags, timestamp, importance
                       FROM long_term WHERE timestamp > ?
                       ORDER BY importance DESC, timestamp DESC LIMIT ?""",
                    (since, limit)
                ).fetchall()
                return [
                    {"id": r[0], "category": r[1], "title": r[2],
                     "detail": r[3], "tags": json.loads(r[4] or "[]"),
                     "timestamp": r[5], "importance": r[6]}
                    for r in rows
                ]
            finally:
                conn.close()

    def recall_summary(self, days: int = 7) -> str:
        """Human-readable summary of recent long-term events for Director prompt."""
        events = self.recall_recent(days=days, limit=15)
        if not events:
            return "No significant events in the last week."
        lines = [f"📌 Last {days} days — key events:"]
        for e in events:
            imp = "🔴" if e["importance"] == 3 else ("🟡" if e["importance"] == 2 else "⚪")
            ts = e["timestamp"][:10]
            lines.append(f"  {imp} [{ts}] {e['category'].upper()}: {e['title']}")
            if e["detail"]:
                lines.append(f"     → {e['detail'][:120]}")
        return "\n".join(lines)

    # ── Business facts store ─────────────────────────────────────────────────

    def set_fact(self, key: str, value: Any, source: str = "system") -> None:
        """
        Store a persistent business fact.

        Example:
            memory.set_fact('best_selling_product', 'Senna Leaves 200g')
            memory.set_fact('avg_daily_revenue_30d', '₹4,200')
            memory.set_fact('peak_order_day', 'Tuesday')
            memory.set_fact('falconherbs_products_count', 87)
        """
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO business_facts (key, value, updated_at, source)"
                    " VALUES (?, ?, ?, ?)",
                    (key, json.dumps(value), now_ist_str(), source)
                )
                conn.commit()
            finally:
                conn.close()

    def get_fact(self, key: str, default: Any = None) -> Any:
        """Retrieve a business fact by key."""
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT value FROM business_facts WHERE key = ?", (key,)
                ).fetchone()
                return json.loads(row[0]) if row else default
            finally:
                conn.close()

    def get_all_facts(self) -> Dict:
        """Get all stored business facts."""
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT key, value, updated_at, source FROM business_facts"
                    " ORDER BY updated_at DESC"
                ).fetchall()
                return {
                    r[0]: {
                        "value": json.loads(r[1]),
                        "updated_at": r[2],
                        "source": r[3],
                    }
                    for r in rows
                }
            finally:
                conn.close()

    def facts_summary(self) -> str:
        """Compact business facts for Director prompt injection."""
        facts = self.get_all_facts()
        if not facts:
            return ""
        lines = ["📊 Business Facts:"]
        for key, meta in facts.items():
            lines.append(f"  {key}: {meta['value']}")
        return "\n".join(lines)

    # ── Context (session key-value) ──────────────────────────────────────────

    def set_context(self, user_id: str, key: str, value: Any) -> None:
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO context (user_id, key, value, timestamp)"
                    " VALUES (?, ?, ?, ?)",
                    (user_id, key, json.dumps(value), now_ist_str())
                )
                conn.commit()
            finally:
                conn.close()

    def get_context(self, user_id: str, key: str) -> Optional[Any]:
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT value FROM context WHERE user_id = ? AND key = ?",
                    (user_id, key)
                ).fetchone()
                return json.loads(row[0]) if row else None
            finally:
                conn.close()

    def get_all_context(self, user_id: str) -> Dict:
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT key, value FROM context WHERE user_id = ?", (user_id,)
                ).fetchall()
                return {r[0]: json.loads(r[1]) for r in rows}
            finally:
                conn.close()

    def clear_context(self, user_id: str) -> None:
        with self._lock:
            conn = self._conn()
            try:
                conn.execute("DELETE FROM context WHERE user_id = ?", (user_id,))
                conn.commit()
            finally:
                conn.close()

    # ── Topics ───────────────────────────────────────────────────────────────

    _STOPWORDS = {
        "the", "is", "in", "at", "to", "a", "an",
        "and", "or", "of", "for", "on", "it", "by",
        "ka", "ke", "ki", "hai", "ho", "se", "me",
        "ko", "ye", "wo", "kya", "karo", "do",
        "de", "le", "na", "hi", "bhi", "aur", "ya",
        "toh", "sir", "please", "can", "you", "how",
        "what", "this", "that", "with", "from",
        "about", "are", "was", "but",
    }

    def track_topic(
        self, user_id: str, message: str,
        intent: Optional[str] = None
    ) -> None:
        words = message.lower().split()
        keywords = [
            w for w in words
            if len(w) >= 3 and w not in self._STOPWORDS
        ]
        if not keywords:
            return
        now = now_ist_str()
        with self._lock:
            conn = self._conn()
            try:
                for kw in keywords:
                    row = conn.execute(
                        "SELECT id, frequency, related_intents FROM topics"
                        " WHERE user_id = ? AND topic = ?",
                        (user_id, kw)
                    ).fetchone()
                    if row:
                        freq = row[1] + 1
                        intents = row[2] or ""
                        if intent and intent not in intents:
                            intents = f"{intents},{intent}" if intents else intent
                        conn.execute(
                            "UPDATE topics SET frequency=?, last_mentioned=?,"
                            " related_intents=? WHERE id=?",
                            (freq, now, intents, row[0])
                        )
                    else:
                        conn.execute(
                            "INSERT INTO topics (user_id, topic, frequency,"
                            " last_mentioned, related_intents) VALUES (?,?,1,?,?)",
                            (user_id, kw, now, intent or "")
                        )
                conn.commit()
            finally:
                conn.close()

    def get_user_preferences(self, user_id: str) -> List[Dict]:
        """Top 10 topics by frequency."""
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT topic, frequency, last_mentioned FROM topics"
                    " WHERE user_id = ? ORDER BY frequency DESC LIMIT 10",
                    (user_id,)
                ).fetchall()
                return [{"topic": r[0], "frequency": r[1], "last_mentioned": r[2]}
                        for r in rows]
            finally:
                conn.close()

    # ── Smart context builder (main upgrade) ─────────────────────────────────

    def build_director_context(
        self, user_id: str,
        recent_messages: int = 12,
        include_long_term_days: int = 7,
    ) -> str:
        """
        Build the richest possible context for Director's AI prompt.

        Combines:
        - Recent conversation (no time cutoff)
        - Long-term event summary (last 7 days)
        - Business facts
        - Top topics owner asks about

        Usage in DirectorBrain._build_system_prompt():
            context = memory.build_director_context(user_id)
        """
        parts = []

        # 1. Business facts
        facts = self.facts_summary()
        if facts:
            parts.append(facts)

        # 2. Long-term events
        lt_summary = self.recall_summary(days=include_long_term_days)
        if lt_summary:
            parts.append(lt_summary)

        # 3. User topics
        prefs = self.get_user_preferences(user_id)
        if prefs:
            top_topics = ", ".join(p["topic"] for p in prefs[:6])
            parts.append(f"🔁 Frequently asked about: {top_topics}")

        # 4. Recent conversation
        hist = self.get_history_text(user_id, last_n=recent_messages)
        if hist and hist != "No previous conversation.":
            parts.append(f"💬 Recent conversation:\n{hist}")

        return "\n\n".join(parts) if parts else ""

    # Legacy alias kept for backward compatibility
    def build_rich_context(self, user_id: str, recent_messages: int = 5) -> str:
        return self.build_director_context(user_id, recent_messages)

    def get_conversation_summary(self, user_id: str) -> str:
        history = self.get_history_text(user_id, 5)
        context = self.get_all_context(user_id)
        summary = f"RECENT CONVERSATION:\n{history}\n"
        if context:
            summary += f"\nACTIVE CONTEXT:\n{json.dumps(context, indent=2)}\n"
        return summary

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """DB stats for monitoring."""
        with self._lock:
            conn = self._conn()
            try:
                msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
                lt_count  = conn.execute("SELECT COUNT(*) FROM long_term").fetchone()[0]
                fact_count= conn.execute("SELECT COUNT(*) FROM business_facts").fetchone()[0]
                ctx_count = conn.execute("SELECT COUNT(*) FROM context").fetchone()[0]
                db_size   = round(self._db_path.stat().st_size / 1024, 1) if self._db_path.exists() else 0
                return {
                    "messages": msg_count,
                    "long_term_events": lt_count,
                    "business_facts": fact_count,
                    "context_vars": ctx_count,
                    "db_size_kb": db_size,
                    "db_path": str(self._db_path),
                    "max_messages": self._max_messages,
                }
            finally:
                conn.close()


# ── Global singleton ───────────────────────────────────────────────────────────
memory = ConversationMemory()
