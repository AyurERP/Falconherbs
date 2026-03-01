"""Conversation Memory — SQLite-backed persistent memory across restarts"""

import json
import sqlite3
import threading
from core.logger import log
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_PATH = Path(__file__).parent.parent / "data" / "falcon.db"


class ConversationMemory:
    """
    Remembers conversation context per user.
    
    Persists to SQLite so conversations survive service restarts.
    Thread-safe for use from webhook + director threads.
    """
    
    def __init__(self, max_messages: int = 200, db_path: Path = DB_PATH):
        self._max_messages = max_messages
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist and run simple migrations."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            # Basic table creation
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            
            # Migration: Add message_id column if missing (Task 3)
            try:
                cursor = conn.execute("PRAGMA table_info(messages)")
                cols = [row[1] for row in cursor.fetchall()]
                if "message_id" not in cols:
                    log.info("Migration: Adding 'message_id' column to messages table")
                    conn.execute("ALTER TABLE messages ADD COLUMN message_id TEXT")
            except Exception as e:
                log.warning("Migration failed: %s", e)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS context (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    PRIMARY KEY (user_id, key)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_user 
                ON messages(user_id, timestamp DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    last_mentioned TEXT,
                    related_intents TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_topics_user 
                ON topics(user_id, frequency DESC)
            """)
            conn.commit()
            conn.close()
    
    def _conn(self) -> sqlite3.Connection:
        """Get a thread-local connection."""
        return sqlite3.connect(str(self._db_path))
    
    def add_message(self, user_id: str, role: str, content: str, message_id: Optional[str] = None) -> None:
        """Add message to conversation history (persisted)."""
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO messages (user_id, role, content, timestamp, message_id) VALUES (?, ?, ?, ?, ?)",
                    (user_id, role, content, datetime.now().isoformat(), message_id)
                )
                # Keep only last N messages per user
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
        self, user_id: str, limit: int = 8
    ) -> List[Dict]:
        """Get recent messages for AI context. Alias for get_history."""
        return self.get_history(user_id, last_n=limit)

    def get_history(self, user_id: str, last_n: int = 10) -> List[Dict]:
        """Get recent conversation history (max N MSGs, 24h expiry)."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    """SELECT role, content, timestamp, message_id FROM messages 
                       WHERE user_id = ? AND timestamp > ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (user_id, cutoff, last_n)
                ).fetchall()
                return [
                    {"role": r[0], "content": r[1], "timestamp": r[2], "message_id": r[3]}
                    for r in reversed(rows)
                ]
            finally:
                conn.close()
    
    def get_message_by_id(self, user_id: str, message_id: str) -> Optional[Dict]:
        """Find a specific message by its WhatsApp message_id"""
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT role, content, timestamp, message_id FROM messages WHERE user_id = ? AND message_id = ?",
                    (user_id, message_id)
                ).fetchone()
                if row:
                    return {"role": row[0], "content": row[1], "timestamp": row[2], "message_id": row[3]}
                return None
            finally:
                conn.close()
    
    def get_history_text(self, user_id: str, last_n: int = 5) -> str:
        """Get conversation history as readable text."""
        history = self.get_history(user_id, last_n)
        if not history:
            return "No previous conversation."
        
        text = ""
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            c = msg["content"]
            text += f"{role}: {c[:150]}...\n" if len(c) > 150 else f"{role}: {c}\n"
        return text.strip()
    
    def set_context(self, user_id: str, key: str, value: Any) -> None:
        """Store context variable (persisted)."""
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO context (user_id, key, value, timestamp) VALUES (?, ?, ?, ?)",
                    (user_id, key, json.dumps(value), datetime.now().isoformat())
                )
                conn.commit()
            finally:
                conn.close()
    
    def get_context(self, user_id: str, key: str) -> Optional[Any]:
        """Retrieve context variable."""
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
        """Get all context for user."""
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT key, value FROM context WHERE user_id = ?",
                    (user_id,)
                ).fetchall()
                return {r[0]: json.loads(r[1]) for r in rows}
            finally:
                conn.close()
    
    def clear_context(self, user_id: str) -> None:
        """Clear user context."""
        with self._lock:
            conn = self._conn()
            try:
                conn.execute("DELETE FROM context WHERE user_id = ?", (user_id,))
                conn.commit()
            finally:
                conn.close()
    
    def get_conversation_summary(self, user_id: str) -> str:
        """AI-friendly summary of recent conversation."""
        history = self.get_history_text(user_id, 5)
        context = self.get_all_context(user_id)
        
        summary = f"RECENT CONVERSATION:\n{history}\n"
        
        if context:
            summary += f"\nACTIVE CONTEXT:\n{json.dumps(context, indent=2)}\n"
        
        return summary
    
    def get_message_count(self, user_id: str) -> int:
        """Total messages stored for user."""
        with self._lock:
            conn = self._conn()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    # ── Topic Tracking (Phase 3) ──────────────────────

    _STOPWORDS = {
        "the", "is", "in", "at", "to", "a", "an",
        "and", "or", "of", "for", "on", "it", "by",
        "ka", "ke", "ki", "hai", "ho", "se", "me",
        "ko", "ye", "wo", "kya", "karo", "karo",
        "do", "de", "le", "na", "hi", "bhi",
        "aur", "ya", "toh", "sir", "please",
        "can", "you", "how", "what", "this", "that",
        "with", "from", "about", "are", "was", "but",
    }

    def track_topic(
        self, user_id: str, message: str,
        intent: Optional[str] = None
    ) -> None:
        """Extract keywords from message and track
        in topics table."""
        words = message.lower().split()
        keywords = [
            w for w in words
            if len(w) >= 3 and w not in self._STOPWORDS
        ]
        if not keywords:
            return

        now = datetime.now().isoformat()
        with self._lock:
            conn = self._conn()
            try:
                for kw in keywords:
                    row = conn.execute(
                        "SELECT id, frequency, "
                        "related_intents FROM topics "
                        "WHERE user_id = ? AND topic = ?",
                        (user_id, kw)
                    ).fetchone()
                    if row:
                        freq = row[1] + 1
                        intents = row[2] or ""
                        if intent and intent not in intents:
                            intents = (
                                f"{intents},{intent}"
                                if intents else intent
                            )
                        conn.execute(
                            "UPDATE topics SET "
                            "frequency = ?, "
                            "last_mentioned = ?, "
                            "related_intents = ? "
                            "WHERE id = ?",
                            (freq, now, intents, row[0])
                        )
                    else:
                        conn.execute(
                            "INSERT INTO topics "
                            "(user_id, topic, frequency, "
                            "last_mentioned, "
                            "related_intents) "
                            "VALUES (?, ?, 1, ?, ?)",
                            (user_id, kw, now,
                             intent or "")
                        )
                conn.commit()
            finally:
                conn.close()

    def get_user_preferences(
        self, user_id: str
    ) -> List[Dict]:
        """Top 10 topics by frequency."""
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT topic, frequency, "
                    "last_mentioned FROM topics "
                    "WHERE user_id = ? "
                    "ORDER BY frequency DESC LIMIT 10",
                    (user_id,)
                ).fetchall()
                return [
                    {
                        "topic": r[0],
                        "frequency": r[1],
                        "last_mentioned": r[2],
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def build_rich_context(
        self, user_id: str, recent_messages: int = 5
    ) -> str:
        """Build rich context string for AI prompts."""
        prefs = self.get_user_preferences(user_id)
        history = self.get_history_text(
            user_id, recent_messages
        )

        parts = []
        if prefs:
            topics = ", ".join(
                p["topic"] for p in prefs[:5]
            )
            parts.append(
                f"User frequently asks about: {topics}."
            )
        parts.append(
            f"Recent conversation:\n{history}"
        )
        return "\n".join(parts)


# Global instance
memory = ConversationMemory()
