"""Conversation Memory — SQLite-backed persistent memory across restarts"""

import json
import sqlite3
import threading
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
    
    def __init__(self, max_messages: int = 50, db_path: Path = DB_PATH):
        self._max_messages = max_messages
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with self._lock:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
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
            conn.commit()
            conn.close()
    
    def _conn(self) -> sqlite3.Connection:
        """Get a thread-local connection."""
        return sqlite3.connect(str(self._db_path))
    
    def add_message(self, user_id: str, role: str, content: str) -> None:
        """Add message to conversation history (persisted)."""
        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    "INSERT INTO messages (user_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                    (user_id, role, content, datetime.now().isoformat())
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
    
    def get_history(self, user_id: str, last_n: int = 10) -> List[Dict]:
        """Get recent conversation history."""
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT role, content, timestamp FROM messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, last_n)
                ).fetchall()
                return [
                    {"role": r[0], "content": r[1], "timestamp": r[2]}
                    for r in reversed(rows)
                ]
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


# Global instance
memory = ConversationMemory()
