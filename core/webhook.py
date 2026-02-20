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
import threading
from typing import Any, Dict, Optional, TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

from core.logger import log
from core.whatsapp import WhatsAppNotifier

if TYPE_CHECKING:
    from core.commander import FalconCommander


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

            # ── Deduplication ──
            if message_id:
                with self._id_lock:
                    if message_id in self._processed_ids:
                        log.info("Webhook: duplicate message %s — skipping", message_id[:20])
                        return
                    self._processed_ids.add(message_id)
                    # Keep set bounded
                    if len(self._processed_ids) > 1000:
                        # Remove oldest (set doesn't preserve order, but this prevents unbounded growth)
                        self._processed_ids = set(list(self._processed_ids)[-500:])

            # ── Security: validate sender ──
            if not self._is_allowed_sender(sender):
                log.warning(
                    "Webhook: message from UNKNOWN sender %s — IGNORED",
                    sender[:6] + "…" if sender else "empty",
                )
                return

            # ── Only process text messages ──
            if msg_type != "text":
                log.info("Webhook: non-text message (type=%s) — ignoring", msg_type)
                return

            text_body = msg.get("text", {}).get("body", "").strip()
            if not text_body:
                return

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
                },
            )

            # ── Route: quick YES/NO → approval system ──
            if _is_quick_reply(text_body) and self._whatsapp.latest_pending_id:
                log.info("Quick reply detected: '%s' → routing to approval", text_body[:20])
                self._whatsapp.receive_reply("latest", text_body)
                return

            # ── Route: everything else → commander ──
            try:
                self._commander.handle_message(text_body, message_id)
            except Exception as exc:
                log.critical(
                    "Commander.handle_message crashed: %s", exc, exc_info=True,
                )
                # Best-effort error reply
                self._whatsapp.send_message(
                    "⚠️ Sorry sir, internal error aa gaya. "
                    "Team dekh rahi hai, thodi der mein try karo."
                )

        except Exception as exc:
            log.critical(
                "Webhook: _handle_incoming_message crashed: %s",
                exc, exc_info=True,
            )

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
