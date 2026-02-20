"""
FALCON AGENCY — Structured Logger
Every agent action is recorded here.
SQLite for persistence. Console for visibility.
"""

import logging
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# Ensure directories exist
Path("logs").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)

DB_PATH = "data/falcon.db"


def _init_db():
    """Create the action log table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS action_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            agent       TEXT NOT NULL,
            action      TEXT NOT NULL,
            status      TEXT NOT NULL,
            details     TEXT,
            approved_by TEXT DEFAULT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spend_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            model     TEXT NOT NULL,
            tokens    INTEGER,
            cost_usd  REAL,
            task      TEXT
        )
    """)
    conn.commit()
    conn.close()


_init_db()


class FalconLogger:
    """
    Unified logger for all agents.
    Writes to: console, file, and SQLite database.
    """

    def __init__(self):
        self._setup_console_logger()

    def _setup_console_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("logs/falcon.log", encoding="utf-8"),
            ]
        )
        self._logger = logging.getLogger("FalconAgency")

    # === STANDARD LOG LEVELS ===
    def info(self, msg: str, *args, **kwargs):     self._logger.info(msg, *args, **kwargs)
    def warning(self, msg: str, *args, **kwargs):  self._logger.warning(msg, *args, **kwargs)
    def critical(self, msg: str, *args, **kwargs): self._logger.critical(msg, *args, **kwargs)
    def error(self, msg: str, *args, **kwargs):    self._logger.error(msg, *args, **kwargs)

    # === STRUCTURED ACTION LOGGING (goes to SQLite) ===
    def log_action(
        self,
        action: str,
        agent: str = "system",
        status: str = "success",
        details: dict = None,
        approved_by: str = None,
        approved: str = None,
        reason: str = None,
        **kwargs
    ):
        """
        Record every meaningful agent action to the database.
        This is your audit trail.
        """
        # Handle alternate parameter names from different agents
        if approved_by is None and approved is not None:
            approved_by = str(approved)
        if details is None:
            details = {}
        if reason is not None:
            details["reason"] = reason
        # Absorb any extra kwargs silently so future callers never crash
        details.update({k: str(v) for k, v in kwargs.items()})
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO action_log (timestamp, agent, action, status, details, approved_by) VALUES (?,?,?,?,?,?)",
            (
                datetime.utcnow().isoformat(),
                agent,
                action,
                status,
                json.dumps(details or {}),
                approved_by,
            )
        )
        conn.commit()
        conn.close()
        self._logger.info(f"[{agent.upper()}] {action} → {status.upper()}")

    def log_spend(self, model: str, tokens: int, cost_usd: float, task: str):
        """Track API spending against your daily/monthly limits."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO spend_log (timestamp, model, tokens, cost_usd, task) VALUES (?,?,?,?,?)",
            (datetime.utcnow().isoformat(), model, tokens, cost_usd, task)
        )
        conn.commit()
        conn.close()
        self._logger.info(f"[SPEND] {model} | {tokens} tokens | ${cost_usd:.4f} | {task}")

    def get_today_spend(self) -> float:
        """Returns total USD spent today across all models."""
        today = datetime.utcnow().date().isoformat()
        conn = sqlite3.connect(DB_PATH)
        result = conn.execute(
            "SELECT SUM(cost_usd) FROM spend_log WHERE timestamp LIKE ?",
            (f"{today}%",)
        ).fetchone()
        conn.close()
        return result[0] or 0.0

    def get_recent_actions(self, limit: int = 20) -> list:
        """Fetch the most recent agent actions for review."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT timestamp, agent, action, status, details FROM action_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return rows


# Singleton — every agent imports this
log = FalconLogger()