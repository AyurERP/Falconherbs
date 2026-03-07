"""
core/whatsapp.py — WhatsApp Business Cloud API Integration for Falcon Agency
===============================================================================

The owner's primary communication channel. All approvals, alerts, reports,
and conversations flow through here via the Meta WhatsApp Business API.

Architecture:
    Owner ←──WhatsApp──→ Meta Cloud API ←──HTTPS──→ WhatsAppNotifier
                                                         │
                                              ┌──────────┼──────────┐
                                              ▼          ▼          ▼
                                          Approvals   Alerts    Reports

Thread Safety:
    The reply polling mechanism uses threading.Event for efficient blocking
    and threading.Lock for state protection. Safe for concurrent access
    from the webhook thread and the Director's main loop.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from core.logger import log


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

META_API_BASE: str = "https://graph.facebook.com/v18.0"
HTTP_TIMEOUT: int = 10
MAX_MSG_LEN: int = 4000         # WhatsApp limit is 4096; leave buffer
POLL_INTERVAL: float = 5.0      # seconds between reply checks

# Normalisation maps for YES/NO detection
_YES_TOKENS: frozenset[str] = frozenset({
    "YES", "Y", "APPROVE", "APPROVED", "OK", "OKAY",
    "HAA", "HAAN", "HA", "THEEK", "THEEK HAI", "BILKUL",
    "CHALO", "KAR DO", "KARO", "GO AHEAD",
    "👍", "✅",
})
_NO_TOKENS: frozenset[str] = frozenset({
    "NO", "N", "DENY", "DENIED", "REJECT", "REJECTED",
    "NAHI", "NAHI CHAHIYE", "CANCEL", "STOP", "RUKO", "MAT KARO",
    "👎", "❌",
})

# Alert type → emoji mapping
_ALERT_EMOJIS: Dict[str, str] = {
    "security":       "🚨",
    "uptime":         "📡",
    "backup_failed":  "💾",
    "revenue_spike":  "📈",
    "revenue_drop":   "📉",
    "content_ready":  "📝",
    "error":          "⚠️",
    "info":           "ℹ️",
    "approval":       "🔐",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_display() -> str:
    return datetime.now(timezone.utc).strftime("%d %b %Y")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WHATSAPP NOTIFIER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class WhatsAppNotifier:
    """
    Production WhatsApp Business Cloud API client for Falcon Agency.

    Handles:
        • Outbound messages (alerts, reports, approval requests)
        • Reply polling for the approval gate (thread-safe)
        • Message chunking for long reports (4000-char limit)

    All credentials come from environment variables — never hardcoded.

    Usage::

        wa = WhatsAppNotifier()
        wa.send_message("Hello from Falcon Agency!")
        wa.send_alert("security", {"threat": "brute force", "ip": "1.2.3.4"})
    """

    def __init__(self) -> None:
        """
        Initialise the WhatsApp notifier.

        Reads credentials from environment. If any are missing,
        all send methods will log a warning and return False
        instead of crashing.
        """
        self._phone_id: str = os.environ.get("WHATSAPP_PHONE_ID", "")
        self._access_token: str = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        self._recipient: str = os.environ.get("WHATSAPP_RECIPIENT", "")

        # ── Reply polling infrastructure (thread-safe) ──
        self._lock: threading.Lock = threading.Lock()
        self._reply_store: Dict[str, str] = {}                 # request_id → normalised reply
        self._reply_events: Dict[str, threading.Event] = {}    # request_id → wake-up event
        self._latest_pending_id: Optional[str] = None          # most recent unanswered request

        # ── Validate credentials ──
        self._configured: bool = all([self._phone_id, self._access_token, self._recipient])

        if self._configured:
            log.info(
                "WhatsAppNotifier ready  |  phone_id=%s  |  recipient=%s…%s",
                self._phone_id[:6] + "…",
                self._recipient[:4],
                self._recipient[-4:],
            )
        else:
            missing = []
            if not self._phone_id:
                missing.append("WHATSAPP_PHONE_ID")
            if not self._access_token:
                missing.append("WHATSAPP_ACCESS_TOKEN")
            if not self._recipient:
                missing.append("WHATSAPP_RECIPIENT")
            log.warning(
                "WhatsAppNotifier: credentials incomplete — missing: %s. "
                "All send methods will return False.",
                ", ".join(missing),
            )

    @property
    def latest_pending_id(self) -> Optional[str]:
        """Get the ID of the most recent unanswered approval request."""
        return self._latest_pending_id

    # ══════════════════════════════════════════════════════════════════
    #  CORE: send_message
    # ══════════════════════════════════════════════════════════════════

    def send_message(self, text: str, reply_to: Optional[str] = None) -> Optional[str]:
        """
        Send a text message to the owner via WhatsApp Business API.
        Returns the message ID of the last chunk if successful, else None.
        """
        if not self._configured:
            log.warning("WhatsApp not configured — message not sent")
            return None

        if not text or not text.strip():
            log.warning("WhatsApp: empty message — skipping")
            return None

        chunks = self._chunk_message(text)
        last_id = None

        for i, chunk in enumerate(chunks):
            msg_id = self._send_single(chunk, reply_to=reply_to)
            if not msg_id:
                log.warning(
                    "WhatsApp chunk %d/%d failed  |  preview=%s",
                    i + 1, len(chunks), chunk[:60],
                )
            else:
                last_id = msg_id
                log.info(
                    "WhatsApp sent  |  chunk %d/%d  |  id=%s",
                    i + 1, len(chunks), msg_id,
                )

            # Small delay between chunks to maintain ordering
            if i < len(chunks) - 1:
                time.sleep(0.5)

        return last_id

    def _send_single(self, text: str, reply_to: Optional[str] = None) -> Optional[str]:
        """Send a single message chunk. Returns message ID on success."""
        try:
            url = f"{META_API_BASE}/{self._phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": self._recipient,
                "type": "text",
                "text": {"body": text},
            }

            if reply_to:
                payload["context"] = {"message_id": reply_to}

            resp = requests.post(
                url, headers=headers, json=payload, timeout=HTTP_TIMEOUT,
            )

            if resp.status_code == 200:
                data = resp.json()
                msg_id = data.get("messages", [{}])[0].get("id")
                log.log_action(
                    action="whatsapp_send",
                    agent="whatsapp",
                    status="success",
                    details={"chars": len(text), "id": msg_id},
                )
                return msg_id

            # ── 401 = Access Token Expired — CRITICAL alert ─────────────────
            if resp.status_code == 401:
                log.error(
                    "🚨 WHATSAPP TOKEN EXPIRED (401)! "
                    "Meta access token needs refresh. "
                    "Go to: developers.facebook.com → System Users → Generate Token. "
                    "Response: %s",
                    resp.text[:300],
                )
                log.log_action(
                    action="whatsapp_token_expired",
                    agent="whatsapp",
                    status="CRITICAL",
                    details={"status_code": 401, "response": resp.text[:200]},
                )
                # Write flag file so monitoring scripts can detect this
                try:
                    import json as _json
                    from pathlib import Path
                    _flag = Path(__file__).resolve().parent.parent / "tmp" / "token_expired.flag"
                    _flag.parent.mkdir(exist_ok=True)
                    _flag.write_text(_json.dumps({
                        "error": "WHATSAPP_TOKEN_EXPIRED",
                        "time": _utcnow_iso(),
                        "fix": "developers.facebook.com → System Users → Generate Permanent Token",
                        "env_var": "WHATSAPP_ACCESS_TOKEN",
                    }, indent=2))
                    log.warning("Token expiry flag written to tmp/token_expired.flag")
                except Exception as _fe:
                    log.warning("Could not write token_expired.flag: %s", _fe)
                # Try email alert as fallback notification
                try:
                    from core.email_system import EmailSystem
                    _em = EmailSystem()
                    _em.send_email(
                        to=os.environ.get("SMTP_USER", ""),
                        subject="🚨 FALCON AGENCY: WhatsApp Token Expired!",
                        body=(
                            "WhatsApp Access Token (WHATSAPP_ACCESS_TOKEN) has expired.\n\n"
                            "Fix: Go to developers.facebook.com → System Users → Generate Permanent Token\n"
                            "Then update WHATSAPP_ACCESS_TOKEN in .env and restart the service.\n\n"
                            f"Time: {_utcnow_iso()}"
                        ),
                    )
                except Exception as _ee:
                    log.warning("Email fallback alert also failed: %s", _ee)
                return None

            log.warning(
                "WhatsApp API returned %d: %s",
                resp.status_code,
                resp.text[:300],
            )
            log.log_action(
                action="whatsapp_send",
                agent="whatsapp",
                status="failed",
                details={
                    "status_code": resp.status_code,
                    "response": resp.text[:300],
                },
            )
            return None

        except requests.exceptions.Timeout:
            log.warning("WhatsApp API timed out after %ds", HTTP_TIMEOUT)
            return None
        except requests.RequestException as exc:
            log.warning("WhatsApp API request error: %s", exc)
            return None
        except Exception as exc:
            log.error("WhatsApp _send_single failed: %s", exc)
            return None

    def send_document(
        self,
        file_path: str | Path,
        caption: str = "",
        filename: str | None = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """
        Upload a file and send it as a WhatsApp document to the owner.

        Parameters
        ----------
        file_path : str | Path
            Local path to the file (TXT, PDF, etc.).
        caption : str
            Optional caption text.
        filename : str | None
            Display filename. Defaults to the file's basename.

        Returns
        -------
        bool
            True if sent successfully.
        """
        if not self._configured:
            log.warning("WhatsApp not configured — document not sent")
            return False

        path = Path(file_path)
        if not path.exists():
            log.warning("WhatsApp send_document: file not found: %s", path)
            return False

        display_name = filename or path.name
        mime_map = {
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        mime_type = mime_map.get(path.suffix.lower(), "application/octet-stream")

        try:
            # 1. Upload media to Meta
            upload_url = f"{META_API_BASE}/{self._phone_id}/media"
            with open(path, "rb") as f:
                files = {"file": (path.name, f, mime_type)}
                data = {"messaging_product": "whatsapp", "type": mime_type}
                resp = requests.post(
                    upload_url,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    files=files,
                    data=data,
                    timeout=60,
                )

            if resp.status_code != 200:
                log.warning(
                    "WhatsApp media upload failed: %d %s",
                    resp.status_code,
                    resp.text[:500],
                )
                return False

            media_id = resp.json().get("id")
            if not media_id:
                log.warning("WhatsApp media upload: no id in response")
                return False

            # 2. Send document message
            msg_url = f"{META_API_BASE}/{self._phone_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": self._recipient,
                "type": "document",
                "document": {
                    "id": media_id,
                    "filename": display_name,
                },
            }
            if reply_to:
                payload["context"] = {"message_id": reply_to}
            if caption:
                payload["document"]["caption"] = caption[:1024]

            resp2 = requests.post(
                msg_url,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=HTTP_TIMEOUT,
            )

            if resp2.status_code == 200:
                log.info("WhatsApp document sent: %s", display_name)
                return True

            log.warning(
                "WhatsApp document send failed: %d %s",
                resp2.status_code,
                resp2.text[:300],
            )
            return False

        except requests.RequestException as exc:
            log.warning("WhatsApp send_document request error: %s", exc)
            return False
        except Exception as exc:
            log.critical("WhatsApp send_document crashed: %s", exc, exc_info=True)
            return False

    # ══════════════════════════════════════════════════════════════════
    #  APPROVAL SYSTEM
    # ══════════════════════════════════════════════════════════════════

    def send_approval_request(
        self,
        action: str,
        details: dict,
        request_id: str,
    ) -> bool:
        """
        Send a structured approval request to the owner.

        Registers the request_id as the latest pending approval so
        that a simple YES/NO reply gets routed correctly.

        Parameters
        ----------
        action : str
            The action requiring approval (e.g. ``"deploy_code"``).
        details : dict
            Human-readable context.
        request_id : str
            Unique identifier for this approval request.

        Returns
        -------
        bool
            ``True`` if the message was sent successfully.
        """
        # Register as latest pending
        with self._lock:
            self._latest_pending_id = request_id
            # Pre-create the event so poll_for_reply can start waiting
            if request_id not in self._reply_events:
                self._reply_events[request_id] = threading.Event()

        # Format details
        detail_lines = []
        for key, value in details.items():
            clean_key = key.replace("_", " ").title()
            detail_lines.append(f"  {clean_key}: {value}")
        details_text = "\n".join(detail_lines) if detail_lines else "  (no details)"

        message = (
            "🦅 FALCON APPROVAL REQUIRED\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Action: {action}\n"
            f"Details:\n{details_text}\n"
            f"ID: {request_id}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Reply YES to approve or NO to reject.\n"
            "⏱ Timeout: 5 minutes — no reply = auto rejected."
        )

        ok = self.send_message(message)

        log.log_action(
            action="approval_request_sent",
            agent="whatsapp",
            status="success" if ok else "failed",
            details={"request_id": request_id, "action": action},
        )

        return ok

    def poll_for_reply(
        self,
        request_id: str,
        timeout: int = 300,
    ) -> str | None:
        """
        Block until the owner replies YES/NO or *timeout* expires.

        Uses ``threading.Event`` for efficient blocking — no CPU-burning
        busy-wait. The event is signalled by ``receive_reply()`` when the
        webhook delivers the owner's response.

        Parameters
        ----------
        request_id : str
            The approval request to wait for.
        timeout : int
            Maximum seconds to wait (default: 300 = 5 minutes).

        Returns
        -------
        str or None
            ``"YES"`` or ``"NO"`` if owner replied.
            ``None`` on timeout.
        """
        log.info(
            "Polling for reply  |  request_id=%s  |  timeout=%ds",
            request_id, timeout,
        )

        # Ensure event exists
        with self._lock:
            if request_id not in self._reply_events:
                self._reply_events[request_id] = threading.Event()
            event = self._reply_events[request_id]

            # Check if reply already arrived (race condition guard)
            if request_id in self._reply_store:
                reply = self._reply_store.pop(request_id)
                self._reply_events.pop(request_id, None)
                if self._latest_pending_id == request_id:
                    self._latest_pending_id = None
                log.info("Reply already available: %s", reply)
                return reply

        # Poll loop with Event-based efficient waiting
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            # Wait efficiently — blocks until event.set() or timeout
            event.wait(timeout=min(POLL_INTERVAL, remaining))

            # Check for reply
            with self._lock:
                if request_id in self._reply_store:
                    reply = self._reply_store.pop(request_id)
                    self._reply_events.pop(request_id, None)
                    if self._latest_pending_id == request_id:
                        self._latest_pending_id = None
                    log.info("Reply received: %s  |  request_id=%s", reply, request_id)
                    return reply

        # Timeout — clean up
        with self._lock:
            self._reply_store.pop(request_id, None)
            self._reply_events.pop(request_id, None)
            if self._latest_pending_id == request_id:
                self._latest_pending_id = None

        log.warning("Reply timeout  |  request_id=%s  |  after %ds", request_id, timeout)
        return None

    def receive_reply(self, request_id: str, reply: str) -> None:
        """
        Store a reply from the owner (called by the webhook or commander).

        Resolves the magic value ``"latest"`` to the most recent pending
        approval request ID.

        Parameters
        ----------
        request_id : str
            The request to reply to. Use ``"latest"`` for the most
            recent pending request.
        reply : str
            The owner's reply text (will be normalised to YES/NO).
        """
        # Resolve "latest"
        actual_id = request_id
        if request_id == "latest":
            with self._lock:
                if self._latest_pending_id:
                    actual_id = self._latest_pending_id
                    log.info(
                        "Resolved 'latest' to request_id=%s", actual_id,
                    )
                else:
                    log.warning("receive_reply('latest') but no pending request")
                    return

        # Normalise
        normalised = self._normalise_reply(reply)

        log.info(
            "Reply stored  |  request_id=%s  |  raw='%s'  |  normalised=%s",
            actual_id, reply[:40], normalised,
        )

        with self._lock:
            self._reply_store[actual_id] = normalised
            event = self._reply_events.get(actual_id)
            if event:
                event.set()  # Wake up poll_for_reply

        log.log_action(
            action="approval_reply_received",
            agent="whatsapp",
            status="success",
            details={
                "request_id": actual_id,
                "reply": normalised,
            },
        )

    @staticmethod
    def _normalise_reply(text: str) -> str:
        """Normalise owner reply to YES, NO, or the raw text."""
        cleaned = text.strip().upper()

        if cleaned in _YES_TOKENS:
            return "YES"
        if cleaned in _NO_TOKENS:
            return "NO"

        # Check for partial matches (e.g., "yes please", "haan bhai")
        words = cleaned.split()
        for word in words:
            if word in _YES_TOKENS:
                return "YES"
            if word in _NO_TOKENS:
                return "NO"

        return cleaned  # Return as-is for the commander to interpret

    # ══════════════════════════════════════════════════════════════════
    #  DAILY SUMMARY
    # ══════════════════════════════════════════════════════════════════

    def send_daily_summary(self, report: dict) -> bool:
        """
        Send a formatted daily summary report to the owner.

        Parameters
        ----------
        report : dict
            Expected keys: ``sites_checked``, ``security_alerts``,
            ``content_created``, ``api_spend``, ``spend_limit``,
            ``goals_done``, ``goals_failed``, ``actions_needed`` (list).

        Returns
        -------
        bool
            ``True`` if sent successfully.
        """
        date = _today_display()
        sites = report.get("sites_checked", 0)
        sec_alerts = report.get("security_alerts", 0)
        content = report.get("content_created", 0)
        spend = report.get("api_spend", 0.0)
        limit = report.get("spend_limit", 10.0)
        done = report.get("goals_done", 0)
        failed = report.get("goals_failed", 0)
        actions = report.get("actions_needed", [])

        actions_text = "\n".join(f"  • {a}" for a in actions) if actions else "  None — sab theek hai 👍"

        message = (
            f"🦅 FALCON DAILY REPORT — {date}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 Sites checked: {sites}\n"
            f"🛡 Security alerts: {sec_alerts}\n"
            f"📝 Content created: {content}\n"
            f"💰 API spend: ${spend:.2f} / ${limit:.2f}\n"
            f"🎯 Goals: {done} done, {failed} failed\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ Actions needed:\n{actions_text}"
        )

        ok = self.send_message(message)

        log.log_action(
            action="daily_summary_sent",
            agent="whatsapp",
            status="success" if ok else "failed",
            details={"date": date, "sites": sites, "spend": spend},
        )

        return ok

    # ══════════════════════════════════════════════════════════════════
    #  ALERTS
    # ══════════════════════════════════════════════════════════════════

    def send_alert(self, alert_type: str, details: dict) -> bool:
        """
        Send a typed alert to the owner.

        Parameters
        ----------
        alert_type : str
            One of: ``"security"``, ``"uptime"``, ``"backup_failed"``,
            ``"revenue_spike"``, ``"revenue_drop"``, ``"content_ready"``,
            ``"error"``.
        details : dict
            Alert-specific data to display.

        Returns
        -------
        bool
            ``True`` if sent successfully.
        """
        emoji = _ALERT_EMOJIS.get(alert_type, "🔔")
        type_label = alert_type.replace("_", " ").upper()

        detail_lines = []
        for key, value in details.items():
            clean_key = key.replace("_", " ").title()
            detail_lines.append(f"  {clean_key}: {value}")
        details_text = "\n".join(detail_lines) if detail_lines else "  (no details)"

        message = (
            f"{emoji} FALCON ALERT — {type_label}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{details_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 {_utcnow_iso()}"
        )

        ok = self.send_message(message)

        log.log_action(
            action="alert_sent",
            agent="whatsapp",
            status="success" if ok else "failed",
            details={"alert_type": alert_type, **details},
        )

        return ok

    # ══════════════════════════════════════════════════════════════════
    #  WEEKLY REPORT
    # ══════════════════════════════════════════════════════════════════

    def send_weekly_report(self, report: dict) -> bool:
        """
        Send a comprehensive weekly strategy report to the owner.

        Parameters
        ----------
        report : dict
            Expected keys: ``revenue_inr``, ``revenue_usd``,
            ``orders``, ``countries``, ``top_products`` (list),
            ``content_published``, ``keywords_improved``,
            ``security_events``, ``recommendations`` (list),
            ``approvals_pending``.

        Returns
        -------
        bool
            ``True`` if sent successfully.
        """
        date = _today_display()
        rev_inr = report.get("revenue_inr", 0)
        rev_usd = report.get("revenue_usd", 0)
        orders = report.get("orders", 0)
        countries = report.get("countries", 0)
        top_products = report.get("top_products", [])
        content = report.get("content_published", 0)
        kw_improved = report.get("keywords_improved", 0)
        sec_events = report.get("security_events", 0)
        recs = report.get("recommendations", [])
        approvals = report.get("approvals_pending", 0)

        # Format top products
        if top_products:
            products_text = ", ".join(str(p) for p in top_products[:3])
        else:
            products_text = "No data"

        # Format recommendations
        if recs:
            recs_text = "\n".join(f"  {i}. {r}" for i, r in enumerate(recs[:3], 1))
        else:
            recs_text = "  No new recommendations"

        message = (
            f"🦅 FALCON WEEKLY REPORT — Week of {date}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Revenue this week: ₹{rev_inr:,.0f} / ${rev_usd:,.2f}\n"
            f"📦 Orders: {orders} ({countries} countries)\n"
            f"🏆 Top products: {products_text}\n"
            f"📝 Content published: {content} posts\n"
            f"📈 SEO: {kw_improved} keywords improved\n"
            f"🛡 Security events: {sec_events}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Top 3 recommendations:\n{recs_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔐 Actions awaiting approval: {approvals}"
        )

        ok = self.send_message(message)

        log.log_action(
            action="weekly_report_sent",
            agent="whatsapp",
            status="success" if ok else "failed",
            details={"date": date, "orders": orders, "revenue_usd": rev_usd},
        )

        return ok

    # ══════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _chunk_message(text: str, limit: int = MAX_MSG_LEN) -> List[str]:
        """
        Split *text* into chunks that fit WhatsApp's character limit.

        Prefers splitting on newline boundaries for readability.
        """
        if len(text) <= limit:
            return [text]

        chunks: List[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break

            # Find the last newline within the limit
            split_at = remaining.rfind("\n", 0, limit)
            if split_at <= 0:
                # No newline — try space
                split_at = remaining.rfind(" ", 0, limit)
            if split_at <= 0:
                # No space — hard cut
                split_at = limit

            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")

        return chunks

    def _resolve_credential(self, value: str) -> str:
        """Resolve ``{{ENV:VAR}}`` placeholders from environment."""
        if isinstance(value, str) and value.startswith("{{ENV:"):
            var_name = value[6:-2]
            return os.environ.get(var_name, "")
        return value

    @property
    def is_configured(self) -> bool:
        """``True`` if all WhatsApp credentials are present."""
        return self._configured

    @property
    def latest_pending_id(self) -> Optional[str]:
        """The most recent unanswered approval request ID."""
        with self._lock:
            return self._latest_pending_id

    def __repr__(self) -> str:
        return (
            f"<WhatsAppNotifier  "
            f"configured={'✅' if self._configured else '❌'}  "
            f"pending={self._latest_pending_id or 'none'}>"
        )
