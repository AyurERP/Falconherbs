"""
core/approval.py — Human-in-the-Loop Approval System for Falcon Agency
=======================================================================

Safety valve between autonomous AI agents and real-world actions.

Design Principles:
    1. DENY BY DEFAULT  — any failure, timeout, or ambiguity → auto-reject.
    2. NEVER CRASH      — every code path is wrapped; errors are logged, not raised.
    3. SERIALIZE        — only one approval dialog at a time.
    4. LOG EVERYTHING   — every request, decision, and failure is recorded.

Owner communicates exclusively via WhatsApp Business API.
Approval timeout defaults to 900 seconds (15 minutes).
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.settings import settings
from core.logger import log

_MAX_MSG_LEN: int = 4000


class ApprovalSystem:
    """
    Gatekeeper that ensures no sensitive action fires without explicit
    human approval from the Falcon Agency owner via WhatsApp.

    Typical lifecycle::

        approval = ApprovalSystem()
        ok = approval.request_approval(
            action="deploy_code",
            details={"site": "falconherbs.com", "risk_level": "low"},
        )
        if ok:
            perform_deploy()
    """

    def __init__(self) -> None:
        # Import here to avoid circular imports at module load
        from core.whatsapp import WhatsAppNotifier
        self._whatsapp: WhatsAppNotifier = WhatsAppNotifier()

        self._timeout: int = int(
            getattr(settings, "approval_timeout_seconds", 900)
        )

        # Serialise approvals — one at a time
        self._approval_lock: threading.Lock = threading.Lock()

        log.info(
            "ApprovalSystem created  |  chat_id=%s  |  timeout=%ds",
            "WhatsApp",
            self._timeout,
        )

    # ================================================================== #
    #  PUBLIC API                                                          #
    # ================================================================== #

    def test_connection(self) -> bool:
        """
        Verify WhatsApp is reachable by sending a startup ping.
        Returns True if message sent, False on failure.
        """
        try:
            ok = self._whatsapp.send_message(
                "🦅 Falcon Agency — ApprovalSystem online.\n"
                "WhatsApp approval channel ready."
            )
            if ok:
                log.info("✅ WhatsApp approval channel: connected")
            else:
                log.warning("⚠️ WhatsApp approval channel: send failed")
            return ok
        except Exception as exc:
            log.critical("WhatsApp connection test FAILED: %s", exc, exc_info=True)
            return False

    def request_approval(self, action: str, details: dict) -> bool:
        """
        Request explicit human approval for *action* via WhatsApp.

        Sends a formatted message, polls for YES/NO reply.
        Returns True ONLY on explicit YES. Everything else → False.

        Thread-safe (serialised via internal lock).
        """
        with self._approval_lock:
            try:
                if not self._whatsapp._configured:
                    log.critical(
                        "WhatsApp not configured — DENYING '%s' for safety", action
                    )
                    log.log_action(
                        action=action,
                        details=details,
                        approved=False,
                        reason="whatsapp_not_configured",
                    )
                    return False

                request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"

                sent = self._whatsapp.send_approval_request(
                    action=action,
                    details=details,
                    request_id=request_id,
                )
                if not sent:
                    log.critical(
                        "Failed to send approval request — DENYING '%s'", action
                    )
                    return False

                reply = self._whatsapp.poll_for_reply(
                    request_id=request_id,
                    timeout=self._timeout,
                )

                approved = reply == "YES"

                log.log_action(
                    action=action,
                    details=details,
                    approved=approved,
                    reason=reply or "timeout",
                )

                ack = "✅ Approved" if approved else "❌ Denied"
                self._whatsapp.send_message(
                    f"{ack}: {action}\n🆔 {request_id}"
                )

                return approved

            except Exception as exc:
                log.critical(
                    "Approval system hard-failure for '%s': %s",
                    action, exc, exc_info=True,
                )
                log.log_action(
                    action=action,
                    details=details,
                    approved=False,
                    reason=f"system_hard_failure: {type(exc).__name__}",
                )
                return False

    def send_alert(self, message: str) -> None:
        """Send alert via WhatsApp. Failures logged, never raised."""
        try:
            self._whatsapp.send_message(message)
        except Exception as exc:
            log.warning("Failed to send WhatsApp alert: %s", exc)

    def send_status_report(self, report: dict) -> None:
        """Send a status report dict via WhatsApp daily summary."""
        try:
            self._whatsapp.send_daily_summary(report)
        except Exception as exc:
            log.warning("Failed to send status report: %s", exc)

    # ── Repr ──

    def __repr__(self) -> str:
        configured = "✅" if self._whatsapp._configured else "❌"
        return (
            f"<ApprovalSystem  whatsapp={configured}  "
            f"timeout={self._timeout}s>"
        )
