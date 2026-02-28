"""
core/console_whatsapp.py — Console output for CLI chat mode
============================================================

Replaces WhatsApp with print-to-console for testing Director
via command line. Same interface as WhatsAppNotifier.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, Optional


class ConsoleWhatsApp:
    """
    Drop-in replacement for WhatsAppNotifier that prints to console.
    Used for CLI chat mode: python chat.py
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reply_store: Dict[str, str] = {}
        self._reply_events: Dict[str, threading.Event] = {}
        self._latest_pending_id: Optional[str] = None
        self._configured = True  # Always "ready" for console

    def send_message(self, text: str) -> bool:
        """Print message to console instead of sending."""
        if not text or not text.strip():
            return False
        sep = "-" * 50
        print("\n" + sep)
        print("DIRECTOR:")
        for line in text.strip().split("\n"):
            print(f"   {line}")
        print(sep + "\n")
        return True

    def send_document(
        self,
        file_path: str | Path,
        caption: str = "",
        filename: str | None = None,
    ) -> bool:
        """Print document info to console."""
        path = Path(file_path)
        display = filename or path.name
        msg = f"📎 Document: {display}"
        if caption:
            msg += f"\n   Caption: {caption[:100]}"
        self.send_message(msg)
        return True

    def send_approval_request(
        self,
        action: str,
        details: dict,
        request_id: str,
    ) -> bool:
        """Print approval request — in chat mode, next message = reply."""
        with self._lock:
            self._latest_pending_id = request_id
            if request_id not in self._reply_events:
                self._reply_events[request_id] = threading.Event()
        lines = [f"Action: {action}"]
        for k, v in details.items():
            lines.append(f"  {k}: {v}")
        msg = "🦅 APPROVAL REQUIRED\n" + "\n".join(lines) + "\nReply YES/NO or haan karo/nahi"
        return self.send_message(msg)

    def poll_for_reply(self, request_id: str, timeout: int = 300) -> str | None:
        """In CLI mode, we don't block — user types next message. Return None."""
        return None

    def receive_reply(self, request_id: str, reply: str) -> None:
        """Store reply for pending approval."""
        with self._lock:
            if request_id == "latest" and self._latest_pending_id:
                request_id = self._latest_pending_id
            self._reply_store[request_id] = reply.upper()
            if request_id in self._reply_events:
                self._reply_events[request_id].set()
            if self._latest_pending_id == request_id:
                self._latest_pending_id = None

    @property
    def latest_pending_id(self) -> Optional[str]:
        return self._latest_pending_id

    @property
    def _recipient(self) -> str:
        return "console"
