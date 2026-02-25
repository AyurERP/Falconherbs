"""
core/webhook.py — FastAPI Webhook Server for Falcon Agency
============================================================

Receives incoming WhatsApp messages from the Meta Cloud API,
validates the sender, and routes messages to the appropriate handler.

Runs in a daemon thread alongside the Director's main loop.

Flow:
    Meta Cloud API ──POST──▶ /webhook ──▶ parse payload
                                              │
                                    ┌─────────┼─────────┐
                                    ▼                   ▼
                              YES/NO reply      Free-text message
                                    │                   │
                                    ▼                   ▼
                         whatsapp.receive_reply   commander.handle_message
                         (blocks approval gate)   (background thread)

Security:
    • Webhook verification via hub.verify_token
    • Sender validation — only WHATSAPP_RECIPIENT is processed
    • All other senders are silently ignored and logged
"""

from __future__ import annotations

import os
import re
import threading
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

from core.logger import log
from core.whatsapp import WhatsAppNotifier

if TYPE_CHECKING:
    from core.commander import FalconCommander

UPLOADS_DIR = Path("data/uploads")
META_API_BASE = "https://graph.facebook.com/v18.0"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  QUICK YES/NO DETECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_QUICK_REPLIES: frozenset[str] = frozenset({
    "YES", "Y", "APPROVE", "APPROVED", "OK", "OKAY",
    "NO", "N", "DENY", "DENIED", "REJECT", "REJECTED",
    "HAA", "HAAN", "HA", "THEEK", "BILKUL",
    "NAHI", "CANCEL", "STOP", "RUKO",
    "👍", "✅", "👎", "❌",
})


def _is_quick_reply(text: str) -> bool:
    """Return True if *text* looks like a YES/NO approval reply."""
    words = text.strip().upper().split()
    # If the message is 1-3 words and contains a known reply token
    if len(words) > 4:
        return False
    return any(w in _QUICK_REPLIES for w in words)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FALCON WEBHOOK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FalconWebhook:
    """
    FastAPI webhook server that receives incoming WhatsApp messages.

    Meta's WhatsApp Cloud API requires:
        1. A GET endpoint for verification handshake
        2. A POST endpoint for incoming message delivery
        3. Response within 5 seconds (we process in background threads)

    Parameters
    ----------
    whatsapp : WhatsAppNotifier
        The outbound notifier instance (for storing replies).
    commander : FalconCommander
        The AI brain that interprets free-text messages.
    """

    def __init__(
        self,
        whatsapp: WhatsAppNotifier,
        commander: "FalconCommander",
    ) -> None:
        """
        Initialise the webhook server.

        Creates the FastAPI app, registers routes, and loads the
        verification token from the environment.
        """
        self._whatsapp: WhatsAppNotifier = whatsapp
        self._commander: "FalconCommander" = commander
        self._verify_token: str = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
        self._allowed_sender: str = os.environ.get("WHATSAPP_RECIPIENT", "")
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._processed_ids: set = set()  # dedup: track last 1000 message IDs
        self._id_lock: threading.Lock = threading.Lock()

        # ── Build FastAPI app ──
        self._app: FastAPI = FastAPI(
            title="Falcon Agency Webhook",
            docs_url=None,       # disable Swagger in production
            redoc_url=None,      # disable ReDoc in production
        )

        self._register_routes()

        log.info(
            "FalconWebhook initialised  |  verify_token=%s  |  allowed_sender=%s",
            "set" if self._verify_token else "NOT SET",
            self._allowed_sender[:4] + "…" if self._allowed_sender else "NOT SET",
        )

    # ══════════════════════════════════════════════════════════════════
    #  ROUTE REGISTRATION
    # ══════════════════════════════════════════════════════════════════

    def _register_routes(self) -> None:
        """Register the GET and POST webhook endpoints."""

        @self._app.get("/webhook")
        async def verify_webhook(request: Request) -> Any:
            """
            Meta verification handshake.

            Meta sends a GET request with:
                hub.mode=subscribe
                hub.verify_token=<your token>
                hub.challenge=<random string>

            We verify the token and echo back the challenge.
            """
            params = request.query_params
            mode = params.get("hub.mode", "")
            token = params.get("hub.verify_token", "")
            challenge = params.get("hub.challenge", "")

            if mode == "subscribe" and token == self._verify_token and self._verify_token:
                log.info("Webhook verification successful")
                return PlainTextResponse(content=challenge, status_code=200)

            log.warning(
                "Webhook verification FAILED  |  mode=%s  |  token_match=%s",
                mode, token == self._verify_token,
            )
            return PlainTextResponse(content="Forbidden", status_code=403)

        @self._app.post("/webhook")
        async def receive_webhook(request: Request) -> JSONResponse:
            """
            Receive incoming WhatsApp messages from Meta.

            MUST return 200 within 5 seconds or Meta will retry.
            All processing happens in background threads.
            """
            try:
                body = await request.json()
            except Exception as exc:
                log.warning("Webhook: invalid JSON body: %s", exc)
                return JSONResponse({"status": "ok"}, status_code=200)

            # Process in background — Meta needs a fast response
            thread = threading.Thread(
                target=self._process_webhook_payload,
                args=(body,),
                daemon=True,
                name="webhook-processor",
            )
            thread.start()

            return JSONResponse({"status": "ok"}, status_code=200)

        @self._app.get("/health")
        async def health_check() -> JSONResponse:
            """Simple health check endpoint."""
            return JSONResponse({
                "status": "healthy",
                "service": "falcon-agency-webhook",
            })

    # ══════════════════════════════════════════════════════════════════
    #  PAYLOAD PROCESSING
    # ══════════════════════════════════════════════════════════════════

    def _process_webhook_payload(self, body: dict) -> None:
        """
        Parse the Meta webhook payload and route the message.

        Meta payload structure (deeply nested):
        ```
        {
          "object": "whatsapp_business_account",
          "entry": [{
            "changes": [{
              "value": {
                "messages": [{
                  "from": "91XXXXXXXXXX",
                  "id": "wamid.xxx",
                  "text": {"body": "Hello"},
                  "type": "text"
                }]
              }
            }]
          }]
        }
        ```
        """
        try:
            if body.get("object") != "whatsapp_business_account":
                log.info("Webhook: not a WhatsApp event — ignoring")
                return

            entries = body.get("entry", [])
            if not entries:
                return

            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})

                    # Skip status updates (delivered, read, etc.)
                    if "statuses" in value:
                        continue

                    messages = value.get("messages", [])
                    for msg in messages:
                        self._handle_incoming_message(msg)

        except Exception as exc:
            log.critical(
                "Webhook payload processing crashed: %s", exc, exc_info=True,
            )

    def _handle_incoming_message(self, msg: dict) -> None:
        """
        Handle a single incoming WhatsApp message.

        Validates sender, deduplicates, and routes to the appropriate
        handler (approval reply or commander).
        """
        try:
            sender = msg.get("from", "")
            message_id = msg.get("id", "")
            msg_type = msg.get("type", "")

            # ── Deduplication: message ID ──
            if message_id:
                with self._id_lock:
                    if message_id in self._processed_ids:
                        log.info("Webhook: duplicate message %s — skipping", message_id[:20])
                        return
                    self._processed_ids.add(message_id)
                    # Keep set bounded
                    if len(self._processed_ids) > 1000:
                        self._processed_ids = set(list(self._processed_ids)[-500:])

            # ── Deduplication: same text within 60s (A5 enhancement) ──
            import hashlib, time as _time
            text_body_peek = msg.get("text", {}).get("body", "").strip()
            if text_body_peek and sender:
                dedup_key = f"{sender}:{hashlib.md5(text_body_peek.encode()).hexdigest()}"
                now_ts = _time.time()
                if not hasattr(self, '_text_dedup'):
                    self._text_dedup = {}
                last_seen = self._text_dedup.get(dedup_key, 0)
                if now_ts - last_seen < 60:
                    log.info("Webhook: same text within 60s — skipping")
                    return
                self._text_dedup[dedup_key] = now_ts
                # Prune old entries
                if len(self._text_dedup) > 200:
                    cutoff = now_ts - 120
                    self._text_dedup = {k: v for k, v in self._text_dedup.items() if v > cutoff}

            # ── Security: validate sender ──
            if not self._is_allowed_sender(sender):
                log.warning(
                    "Webhook: message from UNKNOWN sender %s — IGNORED",
                    sender[:6] + "…" if sender else "empty",
                )
                return

            # ── Handle media/document messages (Task 3) ──
            if msg_type in ("image", "document", "audio", "video"):
                saved_path = self._download_whatsapp_media(msg, msg_type)
                if saved_path:
                    media_obj = msg.get(msg_type, {}) or msg.get("document", {})
                    caption = media_obj.get("caption", "") or media_obj.get("filename", "")
                    text_for_commander = (
                        f"[File received: {saved_path.name}]\n"
                        f"Saved to: data/uploads/\n"
                        f"{caption}".strip()
                    )
                    try:
                        self._commander.handle_message(
                            text_for_commander, message_id
                        )
                    except Exception as exc:
                        log.warning("Commander handle (file) failed: %s", exc)
                return

            # ── Only process text messages ──
            if msg_type != "text":
                log.info("Webhook: non-text message (type=%s) — ignoring", msg_type)
                return

            text_body = msg.get("text", {}).get("body", "").strip()
            if not text_body:
                return

            # ── Extract quote-reply context ──
            # When user swipe-replies to a message in WhatsApp, Meta sends
            # a "context" object with the quoted message ID.
            quoted_text = ""
            reply_context = msg.get("context", {})
            if reply_context:
                quoted_msg_id = reply_context.get("id", "")
                log.info(
                    "Webhook: quote-reply detected  |  replying_to=%s",
                    quoted_msg_id[:20] if quoted_msg_id else "none",
                )
                # If we stored the director's outbound messages, we could
                # look up the quoted text here.  For now, pass the ID so
                # the commander knows this is a reply to a specific message.
                quoted_text = f"[Replying to message {quoted_msg_id[:20]}]"

            log.info(
                "Webhook: incoming message  |  from=%s…  |  id=%s  |  text='%s'",
                sender[:6], message_id[:16], text_body[:60],
            )

            log.log_action(
                action="whatsapp_received",
                agent="webhook",
                status="success",
                details={
                    "sender": sender[-4:],
                    "message_id": message_id[:20],
                    "text_preview": text_body[:80],
                    "type": msg_type,
                    "is_reply": bool(reply_context),
                },
            )

            # ── Route: quick YES/NO → approval system ──
            if _is_quick_reply(text_body) and self._whatsapp.latest_pending_id:
                log.info("Quick reply detected: '%s' → routing to approval", text_body[:20])
                self._whatsapp.receive_reply("latest", text_body)
                return

            # ── Route: everything else → commander ──
            # If this is a quote-reply, prepend the context so the
            # Director knows what message the owner is referring to.
            full_text = text_body
            if quoted_text:
                full_text = f"{quoted_text}\n{text_body}"

            try:
                self._commander.handle_message(full_text, message_id)
            except Exception as exc:
                log.critical(
                    "Commander.handle_message crashed: %s", exc, exc_info=True,
                )
                try:
                    from core.director_brain import director_brain
                    from core.memory import memory
                    raw = "Hit an internal error. Logged and investigating. Please try again in a moment."
                    recent = None
                    try:
                        recent = memory.get_recent_messages("owner", limit=4)
                    except Exception:
                        pass
                    reply = director_brain.wrap_raw_response(
                        full_text, raw, "webhook_crash",
                        recent_messages=recent,
                    )
                    self._whatsapp.send_message(reply)
                except Exception:
                    self._whatsapp.send_message(
                        "Hit an internal error. Please try again in a moment."
                    )

        except Exception as exc:
            log.critical(
                "Webhook: _handle_incoming_message crashed: %s",
                exc, exc_info=True,
            )

    def _download_whatsapp_media(
        self, msg: dict, msg_type: str
    ) -> Optional[Path]:
        """
        Download media from WhatsApp Cloud API, save to data/uploads/.
        Returns Path to saved file or None on failure.
        """
        media_obj = msg.get(msg_type) or msg.get("document") or msg.get("image")
        if not media_obj:
            return None

        media_id = media_obj.get("id")
        if not media_id:
            return None

        token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
        if not token:
            log.warning("WHATSAPP_ACCESS_TOKEN not set — cannot download media")
            return None

        try:
            # 1. Get download URL from Meta
            url = f"{META_API_BASE}/{media_id}"
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code != 200:
                log.warning("WhatsApp media URL fetch failed: %d", resp.status_code)
                return None

            data = resp.json()
            download_url = data.get("url")
            if not download_url:
                return None

            # 2. Download file
            r2 = requests.get(
                download_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
                stream=True,
            )
            r2.raise_for_status()

            # 3. Determine filename and save
            UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            filename = media_obj.get("filename") or media_obj.get("sha256", "")[:12]
            if not filename or filename == "":
                ext = {"image": "jpg", "document": "pdf", "audio": "ogg", "video": "mp4"}.get(msg_type, "bin")
                filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            else:
                filename = re.sub(r'[^\w\-\.]', '_', filename)

            saved = UPLOADS_DIR / filename
            with open(saved, "wb") as f:
                for chunk in r2.iter_content(chunk_size=8192):
                    f.write(chunk)

            log.info("WhatsApp media saved: %s", saved)
            return saved

        except Exception as exc:
            log.warning("WhatsApp media download failed: %s", exc)
            return None

    def _is_allowed_sender(self, sender: str) -> bool:
        """Check if *sender* matches the configured owner phone number."""
        if not self._allowed_sender:
            log.warning("WHATSAPP_RECIPIENT not set — rejecting all messages")
            return False
        # Meta may send with or without country code prefix
        return (
            sender == self._allowed_sender
            or sender.endswith(self._allowed_sender[-10:])
        )

    # ══════════════════════════════════════════════════════════════════
    #  SERVER LIFECYCLE
    # ══════════════════════════════════════════════════════════════════

    def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """
        Start the webhook server in a background daemon thread.

        Parameters
        ----------
        host : str
            Bind address (default: all interfaces).
        port : int
            Listen port (default: 8000).
        """
        if self._thread and self._thread.is_alive():
            log.warning("Webhook server already running")
            return

        config = uvicorn.Config(
            app=self._app,
            host=host,
            port=port,
            log_level="warning",    # reduce uvicorn noise
            access_log=False,       # we log ourselves
        )
        self._server = uvicorn.Server(config)

        self._thread = threading.Thread(
            target=self._server.run,
            daemon=True,
            name="Falcon-Webhook-Server",
        )
        self._thread.start()

        log.info("Webhook server started  |  http://%s:%d/webhook", host, port)

    def stop(self) -> None:
        """Gracefully shut down the webhook server."""
        if self._server:
            log.info("Stopping webhook server…")
            self._server.should_exit = True

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=10)
                if self._thread.is_alive():
                    log.warning("Webhook server thread did not exit cleanly")
                else:
                    log.info("Webhook server stopped")
        else:
            log.info("Webhook server was not running")

    @property
    def app(self) -> FastAPI:
        """The underlying FastAPI application (for testing)."""
        return self._app

    def __repr__(self) -> str:
        running = self._thread is not None and self._thread.is_alive()
        return f"<FalconWebhook  running={'🟢' if running else '⚫'}>"
