"""
core/commander.py — AI Command Interpreter for Falcon Agency
==============================================================

The Commander is the AI brain that understands the owner's plain
English (or Hinglish) WhatsApp messages and routes them to the
correct system action.

Flow:
    Owner message → Claude classifies intent → route to handler
                                                    │
                        ┌───────────────────────────┼───────────────┐
                        ▼           ▼               ▼               ▼
                   status_check  run_task      idea_capture     question
                        │           │               │               │
                        ▼           ▼               ▼               ▼
                   get status   dispatch agent  save to JSON   Claude answers
                        │           │               │               │
                        └───────────┴───────────────┴───────────────┘
                                            │
                                            ▼
                                Claude formats Hinglish reply
                                            │
                                            ▼
                                   WhatsApp → Owner

Personality:
    Director speaks like a trusted, hardworking colleague. Mostly Hinglish.
    Matches the owner's language automatically. Never says "I am an AI."
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.logger import log
from core.whatsapp import WhatsAppNotifier
from core.ai_client import call_ai
from config.keys import AI_MODELS
from core.data_reader import RealDataReader
from core.integration_bridge import IntegrationBridge
from core.commander_intents import ExtendedIntentClassifier, IntentResponseHandler
from core.memory import memory
from core.website_tools import website_tools
from core.goal_tracker import goal_tracker
from core.profit_tracker import profit_tracker
from core.content_generator import content_generator
from core.director_brain import director_brain
from core.state_aggregator import get_client_state_summary, format_for_director_context

if TYPE_CHECKING:
    from core.director import Director


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PATHS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
IDEAS_FILE: Path = PROJECT_ROOT / "data" / "ideas.json"
HTTP_TIMEOUT: int = 30    # Claude can take longer than a web request

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SYSTEM PROMPTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INTENT_SYSTEM_PROMPT: str = """You are the command interpreter for Falcon Agency, an elite AI workforce managing herbal product websites.

The owner sends messages in plain English, Hindi, or Hinglish via WhatsApp. Your job is to classify intent and extract parameters.

Return ONLY valid JSON. No explanation. No markdown. No code fences. Just the JSON object.

Schema:
{
  "intent": one of ["status_check", "run_task", "plan_task", "approve_action", "deny_action", "idea_capture", "question", "unclear", "unknown"],
  "task": "task name if run_task or plan_task, else null",
  "site": "site domain if mentioned, else falconherbs.com",
  "params": {},
  "plan_summary": "only if intent is plan_task - brief plan summary",
  "clarifying_question": "only if intent is unclear - question to ask owner",
  "reply_needed": true or false,
  "idea_text": "full idea if idea_capture, else null"
}

Task mapping (use these exact task names):
Simple tasks (use "run_task"):
- "check uptime", "site up?" → task: "uptime_check"
- "check performance", "speed test" → task: "performance_check"

Complex tasks (use "plan_task" so the AI can discuss and plan first):
- "run seo report", "seo check", "seo audit" → task: "seo_audit"
- "security scan", "scan site" → task: "security_scan"
- "audit plugins", "plugin check" → task: "plugin_update_check"
- "audit comments", "spam check" → task: "comment_spam_audit"
- "sales report", "revenue check" → task: "analyse_sales"
- "keyword analysis" → task: "analyse_keywords"
- "content check" → task: "analyse_content_gaps"
- "competitor check" → task: "check_competitors"
- "full report", "weekly report" → task: "run_analysis"
- "health claim check", "compliance" → task: "health_claim_audit"

Approve/deny detection:
- "yes", "approve", "haan", "theek hai", "ok", "go ahead", "kar do" → approve_action
- "no", "deny", "nahi", "cancel", "reject", "ruko", "mat karo" → deny_action

Idea detection (owner sharing a business idea):
- "I was thinking we should...", "idea: ...", "let's try..."

Question detection (asking about business/data):
- "how is traffic?", "kitne orders aaye?", "ranking kaisi hai?"

Status check:
- "status", "kya ho raha hai", "update do"
"""

def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FALCON COMMANDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FalconCommander:
    """
    AI brain that interprets the owner's WhatsApp messages.

    Uses Claude Haiku for fast intent classification, then routes
    to the appropriate handler. Generates natural Hinglish responses
    using the personality prompt.

    Parameters
    ----------
    director : Director
        The Director orchestrator (for dispatching tasks and getting status).
    whatsapp : WhatsAppNotifier
        The WhatsApp client for sending replies.
    """

    def __init__(
        self,
        director: Any,
        whatsapp: WhatsAppNotifier,
    ) -> None:
        """
        Initialise the Commander.
        """
        self._director = director
        self._whatsapp: WhatsAppNotifier = whatsapp
        self._processing_lock: threading.Lock = threading.Lock()
        self.pending_plans: dict[str, dict] = {}
        
        from core.approval import ApprovalSystem
        self._approval = ApprovalSystem()

        # ── Extended tools (safe — if fails, old system continues) ──
        try:
            self._bridge = IntegrationBridge()
            self._extended_classifier = ExtendedIntentClassifier(self._bridge)
            self._extended_handler = IntentResponseHandler(self._bridge)
            log.info("Extended intents loaded (bridge OK)")
        except Exception as e:
            self._bridge = None
            self._extended_classifier = None
            self._extended_handler = None
            log.warning("Extended intents unavailable: %s", e)

        # Ensure data directory exists
        try:
            IDEAS_FILE.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        log.info("FalconCommander initialised")




    # ══════════════════════════════════════════════════════════════════
    #  MAIN HANDLER
    # ══════════════════════════════════════════════════════════════════

    def handle_message(self, text: str, message_id: str, user_id: str = "owner") -> None:
        """
        Process an incoming WhatsApp message from the owner.

        This is the main entry point called by the webhook. It:
            1. Stores message in conversation memory
            2. Classifies intent using Claude
            3. Routes to the appropriate handler
            4. Generates a natural-language reply
            5. Sends the reply via WhatsApp

        Never raises — all errors are caught, logged, and an error
        message is sent to the owner.

        Parameters
        ----------
        text : str
            The owner's message text.
        message_id : str
            WhatsApp message ID (for logging/dedup).
        user_id : str
            User identifier for memory tracking.
        """
        # Store user message in memory
        memory.add_message(user_id, "user", text)
        memory.track_topic(user_id, text)

        log.info(
            "Commander processing  |  msg_id=%s  |  text='%s'",
            message_id[:16], text[:80],
        )

        try:
            # Check for direct agent addressing
            if text.strip().startswith("@"):
                return self._handle_direct_agent(text, message_id)

            lower_text = text.lower().strip()

            # ── Step 0.5: Scope check (GAP 1) — honest "not in scope" before routing ──
            try:
                from config.capabilities import check_scope
                scope_result = check_scope(text)
                if scope_result:
                    ctx = (
                        f"Owner asked for something OUT OF SCOPE.\n"
                        f"Request matched: {scope_result.get('out_of_scope', '')}\n"
                        f"Reason: {scope_result.get('reason', '')}\n"
                        f"Alternatives you CAN do:\n"
                        + "\n".join(f"  • {a}" for a in scope_result.get("alternatives", []))
                        + "\n\n"
                        "Generate an honest WhatsApp reply. Say 'mere scope mein nahi hai' + reason. "
                        "Then offer the alternatives. Match owner's language (Hinglish/English). "
                        "Be direct — a real director, not a yes-man."
                    )
                    reply = self._generate_reply(text, ctx)
                    self._whatsapp.send_message(reply)
                    memory.add_message(user_id, "assistant", reply)
                    return
            except Exception as exc:
                log.warning("Scope check failed (continuing): %s", exc)

            # ── Step 0: Try new extended intents first ──
            if self._extended_classifier:
                try:
                    # Check for confirmation of pending action (haan karo, yes do it)
                    confirm_words = ["haan", "yes", "karo", "confirm", "do it", "theek", "apply"]
                    if any(w in lower_text for w in confirm_words) and len(lower_text) < 30:
                        pending = memory.get_context(user_id, "pending_action")
                        if pending:
                            handler_name = pending if pending.startswith("handle_") else f"handle_{pending.replace('-', '_')}"
                            ext_result = {
                                "intent": pending,
                                "handler": handler_name,
                                "message_text": text,
                                "confirmed": True,
                            }
                            response = self._extended_handler.handle(ext_result)
                            if response.get("success"):
                                memory.set_context(user_id, "pending_action", None)  # clear
                            raw_reply = response.get("response", "")
                            if raw_reply:
                                try:
                                    recent_msgs = memory.get_recent_messages(user_id, limit=8)
                                except Exception:
                                    recent_msgs = []
                                reply_text = director_brain.wrap_raw_response(
                                    text, raw_reply, "confirm",
                                    recent_messages=recent_msgs,
                                )
                                self._whatsapp.send_message(reply_text)
                                memory.add_message(user_id, "assistant", reply_text)
                                return
                    ext_result = self._extended_classifier.classify(text)
                    if ext_result:
                        ext_result["message_text"] = text
                        response = self._extended_handler.handle(ext_result)
                        # Store pending_action for confirmation flow
                        if response.get("needs_confirmation") and response.get("pending_action"):
                            memory.set_context(user_id, "pending_action", response["pending_action"])
                        # ALWAYS send if intent was classified — even on errors.
                        # Previously fell through on success=False which caused
                        # old keyword classifier to misroute (e.g. "price scan"
                        # → "security_scan").
                        raw_reply = response.get("response", "")
                        if raw_reply:
                            # FIX 2: Every extended intent response passes through
                            # DirectorBrain for personality wrapping before WhatsApp.
                            # Flow: Handler → RAW DATA → DirectorBrain → Send
                            try:
                                recent_msgs = memory.get_recent_messages(user_id, limit=8)
                            except Exception:
                                recent_msgs = []
                            reply_text = director_brain.wrap_raw_response(
                                owner_message=text,
                                raw_response=raw_reply,
                                intent=ext_result.get("intent", ""),
                                recent_messages=recent_msgs,
                            )
                            self._whatsapp.send_message(reply_text)
                            memory.add_message(
                                user_id, "assistant", reply_text
                            )
                            # If handler returned a document (e.g. changelog report), send it
                            doc_path = response.get("document_path")
                            if doc_path and Path(doc_path).exists():
                                self._whatsapp.send_document(
                                    doc_path,
                                    caption="Full before/after report",
                                )
                            log.info(
                                "Extended intent: %s (success=%s)",
                                ext_result["intent"],
                                response.get("success"),
                            )
                            return
                except Exception as e:
                    log.warning("Extended intent failed (falling through): %s", e)
                    # Gap #25: Notify owner when intent classifier crashes
                    try:
                        self._whatsapp.send_message(
                            "⚠️ *Falcon Agency Alert*\n\n"
                            "Intent classifier crashed. Error: {}\n\n"
                            "Falling back to basic classifier. "
                            "Check logs if this repeats.".format(str(e)[:150])
                        )
                    except Exception:
                        pass

            # Step 3: no pending plan → normal intent classification
            # ── Step 1: Classify intent ──
            intent_data = self._classify_intent(text)

            if intent_data is None:
                self._reply_unknown(text)
                return

            intent = intent_data.get("intent", "unknown")
            task = intent_data.get("task")
            site = intent_data.get("site", "falconherbs.com")
            params = intent_data.get("params", {})
            idea_text = intent_data.get("idea_text")
            plan_summary = intent_data.get("plan_summary")
            clarifying_question = intent_data.get("clarifying_question")

            log.info(
                "Intent classified  |  intent=%s  |  task=%s  |  site=%s",
                intent, task, site
            )

            log.log_action(
                action="intent_classified",
                agent="commander",
                status="success",
                details={
                    "intent": intent,
                    "task": task,
                    "site": site,
                    "original_text": text[:200],
                },
            )

            if intent == "unclear" and clarifying_question:
                reply = director_brain.wrap_raw_response(
                    text, clarifying_question, "clarify",
                    recent_messages=self._get_recent_for_wrap(),
                )
                self._whatsapp.send_message(reply)
                return
            elif intent == "plan_task" and task:
                plan_text = plan_summary if plan_summary else f"I will need to run {task} on {site}."
                reply = director_brain.wrap_raw_response(
                    text, f"Plan proposed: {plan_text}", "plan_proposed",
                    recent_messages=self._get_recent_for_wrap(),
                )
                self._whatsapp.send_message(reply)
                
                def _trigger_approval():
                    try:
                        ok = self._approval.request_approval(
                            action=f"Execute {task} on {site}?",
                            details={"task": task, "site": site}
                        )
                        if ok:
                            self._handle_run_task(text, task, site, params)
                        else:
                            raw = "Cancelled. Plan discarded."
                            r = director_brain.wrap_raw_response(
                                text, raw, "plan_cancelled",
                                recent_messages=self._get_recent_for_wrap(),
                            )
                            self._whatsapp.send_message(r)
                    except Exception as e:
                        raw = f"Task planning failed: {task}. Error: {str(e)[:200]}"
                        r = director_brain.wrap_raw_response(
                            text, raw, "plan_error",
                            recent_messages=self._get_recent_for_wrap(),
                        )
                        self._whatsapp.send_message(r)
                        
                # request_approval is blocking (poll_for_reply loops with timeout),
                # so we run it in a daemon thread (async wrapper behaviour) to prevent blocking webhook responses.
                threading.Thread(target=_trigger_approval, daemon=True).start()
                return

            # ── Step 2: Route based on intent ──
            if intent == "status_check":
                self._handle_status_check(text)

            elif intent in ["run_task", "plan_task"]:
                # If plan_task slipped through as simple somehow, just run it
                self._handle_run_task(text, task, site, params)

            elif intent == "approve_action":
                self._handle_approve(text)

            elif intent == "deny_action":
                self._handle_deny(text)

            elif intent == "idea_capture":
                self._handle_idea_capture(text, idea_text)

            elif intent == "question":
                self._handle_question(text, site)

            elif intent == "unknown":
                self._reply_unknown(text)

            else:
                self._reply_unknown(text)

        except Exception as exc:
            log.critical(
                "Commander.handle_message crashed: %s", exc, exc_info=True,
            )
            try:
                raw = "Hit a snag on my end. Logged and investigating. Please try again in a moment."
                reply = director_brain.wrap_raw_response(
                    text, raw, "crash_fallback",
                    recent_messages=self._get_recent_for_wrap(),
                )
                self._whatsapp.send_message(reply)
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════
    #  DIRECT AGENT ROUTING
    # ══════════════════════════════════════════════════════════════════

    def _handle_direct_agent(self, text: str, message_id: str) -> None:
        """
        Handle direct agent communication: @developer, @strategist, @media, @backup
        Example: "@developer check website speed"
        """
        # Use existing Director instance — never create a new one
        director = self._director
        if director is None:
            raw = "Director not connected. System may still be starting."
            reply = director_brain.wrap_raw_response(
                text, raw, "director_offline",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)
            return

        parts = text.strip().split(" ", 1)
        agent_tag = parts[0].lower()  # @developer
        query = parts[1] if len(parts) > 1 else "status"
        
        agent_map = {
            "@developer": director._developer,
            "@dev": director._developer,
            "@strategist": director._strategist,
            "@strategy": director._strategist,
            "@media": director._media,
            "@backup": director._backup,
            "@director": None,
            "@dir": None
        }
        
        agent = agent_map.get(agent_tag)
        
        if agent_tag in ["@director", "@dir"]:
            raw = "Talking to Director..."
            reply = director_brain.wrap_raw_response(
                text, raw, "direct_agent_start",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)
            plan = director.think(query)
            plan_str = json.dumps(plan, indent=2)[:2000]
            reply2 = director_brain.wrap_raw_response(
                text, f"Director's response: {plan_str}", "director_response",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply2)
            return
        
        if agent is None:
            raw = (
                f"Unknown agent: {agent_tag}. "
                "Available: @developer, @strategist, @media, @backup, @director"
            )
            reply = director_brain.wrap_raw_response(
                text, raw, "unknown_agent",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)
            return
        
        # Send to specific agent
        raw_start = f"Talking to {agent.name}..."
        reply = director_brain.wrap_raw_response(
            text, raw_start, "direct_agent_start",
            recent_messages=self._get_recent_for_wrap(),
        )
        self._whatsapp.send_message(reply)
        
        try:
            thought = agent.think(query)
            if any(k in query.lower() for k in ["execute", "run", "do"]):
                result = agent.execute(query, "")
                raw_result = f"{agent.name} result: {result[:1500]}"
                reply = director_brain.wrap_raw_response(
                    text, raw_result, "agent_result",
                    recent_messages=self._get_recent_for_wrap(),
                )
                self._whatsapp.send_message(reply)
            else:
                thought_str = json.dumps(thought, indent=2)[:1500]
                raw_analysis = f"{agent.name} analysis: {thought_str}"
                reply = director_brain.wrap_raw_response(
                    text, raw_analysis, "agent_analysis",
                    recent_messages=self._get_recent_for_wrap(),
                )
                self._whatsapp.send_message(reply)
        except Exception as e:
            raw_err = f"{agent.name} error: {str(e)[:500]}"
            reply = director_brain.wrap_raw_response(
                text, raw_err, "agent_error",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)

    # ══════════════════════════════════════════════════════════════════
    #  INTENT HANDLERS
    # ══════════════════════════════════════════════════════════════════

    def _handle_status_check(self, original_text: str) -> None:
        """Gather system status via get_client_state_summary — ONE function, real data."""
        try:
            # GAP 2: Single source of truth — state_aggregator knows everything
            state = get_client_state_summary(
                site_id="falconherbs.com",
                director=self._director,
                bridge=self._bridge,
            )
            status_text = format_for_director_context(state)

            reply = self._generate_reply(
                original_text,
                "The owner asked for status / 'website ka kya haal hai'.\n"
                "Use this REAL data to answer. Keep it conversational, Hinglish.\n\n"
                f"{status_text}\n\n"
                "Generate a short WhatsApp reply with key numbers.",
            )
            self._whatsapp.send_message(reply)

        except Exception as exc:
            log.warning("Status check failed: %s", exc)
            raw = "Status check hit an issue. System is running. Retrying shortly."
            reply = director_brain.wrap_raw_response(
                original_text, raw, "status_error",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)

    def _handle_run_task(
        self,
        original_text: str,
        task: Optional[str],
        site: str,
        params: dict,
    ) -> None:
        """Dispatch a task to the Director and report results."""
        if not task:
            raw = (
                "Which task to run? Try: 'seo report', 'security scan', "
                "'performance check'"
            )
            reply = director_brain.wrap_raw_response(
                original_text, raw, "task_clarify",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)
            return

        # Notify owner that task is starting — via DirectorBrain for tone matching
        raw_start = f"Task {task.replace('_', ' ').title()} starting on {site}."
        start_msg = director_brain.wrap_raw_response(
            original_text, raw_start, "task_start",
            recent_messages=self._get_recent_for_wrap(),
        )
        self._whatsapp.send_message(start_msg)

        try:
            # Map task to agent
            agent = self._task_to_agent(task)

            # Dispatch via director
            result = {}
            if self._director is not None:
                if hasattr(self._director, "dispatch_agent"):
                    result = self._director.dispatch_agent(
                        agent=agent,
                        task=task,
                        site=site,
                        params=params,
                    )
                else:
                    result = {"status": "skipped", "message": "Director dispatch not available"}
            else:
                result = {"status": "skipped", "message": "Director not connected"}

            # Format result as a natural reply
            result_json = json.dumps(result, default=str, ensure_ascii=False)[:1500]

            reply = self._generate_reply(
                original_text,
                f"The owner asked to run task '{task}' on '{site}'. "
                f"Here are the results:\n{result_json}\n\n"
                "Summarise the key findings in a short WhatsApp reply. "
                "Highlight what's good, what needs attention, and any numbers.",
            )

            self._whatsapp.send_message(reply)

        except Exception as exc:
            log.critical("Task dispatch failed: %s", exc, exc_info=True)
            raw_err = f"Task {task} failed. Error: {str(exc)[:100]}"
            err_msg = director_brain.wrap_raw_response(
                original_text, raw_err, "task_error",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(err_msg)


    def _handle_approve(self, original_text: str = "") -> None:
        """Route an approval to the pending request."""
        pending = self._whatsapp.latest_pending_id
        if pending:
            self._whatsapp.receive_reply("latest", "YES")
            raw = "Approved. Starting the action."
            reply = director_brain.wrap_raw_response(
                original_text or "yes", raw, "approve",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)
        else:
            raw = "No pending approval. When an action needs approval, I'll ask."
            reply = director_brain.wrap_raw_response(
                original_text or "approve", raw, "approve_none",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)

    def _handle_deny(self, original_text: str = "") -> None:
        """Route a denial to the pending request."""
        pending = self._whatsapp.latest_pending_id
        if pending:
            self._whatsapp.receive_reply("latest", "NO")
            raw = "Rejected. Action cancelled."
            reply = director_brain.wrap_raw_response(
                original_text or "no", raw, "deny",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)
        else:
            raw = "No pending approval."
            reply = director_brain.wrap_raw_response(
                original_text or "deny", raw, "deny_none",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)

    def _handle_idea_capture(
        self,
        original_text: str,
        idea_text: Optional[str],
    ) -> None:
        """Save an idea to the ideas log."""
        idea = idea_text or original_text

        self._save_idea(idea)

        preview = idea[:50] + "…" if len(idea) > 50 else idea
        raw = f"Idea noted: {preview}\nSaved to ideas log. Will review later."
        reply = director_brain.wrap_raw_response(
            original_text, raw, "idea_capture",
            recent_messages=self._get_recent_for_wrap(),
        )
        self._whatsapp.send_message(reply)

    def _search_serper(self, query: str) -> str:
        """Live Google search via Serper.dev. Returns formatted text or empty."""
        api_key = os.getenv("SERPER_API_KEY", "")
        if not api_key:
            return ""
        try:
            import requests as _req
            r = _req.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "gl": "in", "hl": "en"},
                timeout=12,
            )
            if r.status_code != 200:
                return ""
            data = r.json()
            parts = []
            for i, o in enumerate(data.get("organic", [])[:8], 1):
                parts.append(f"{i}. {o.get('title','')}\n   {o.get('snippet','')}")
            for p in data.get("peopleAlsoAsk", [])[:3]:
                parts.append(f"PAA: {p.get('question','')}\n   {p.get('snippet','')}")
            ab = data.get("answerBox", {})
            if ab:
                parts.append(f"Featured: {ab.get('title','')}\n   {ab.get('snippet','')}")
            return "\n\n".join(parts) if parts else ""
        except Exception:
            return ""

    def _handle_question(self, original_text: str, site: str) -> None:
        """Answer a question using Claude with business context."""
        try:
            # GAP 2: Full client state — one function, real data for any question
            state = get_client_state_summary(
                site_id=site or "falconherbs.com",
                director=self._director,
                bridge=self._bridge,
            )
            status_text = format_for_director_context(state)

            # Inject health audit data if user asks about claims/numbers
            extra_context = ""
            lower = original_text.lower()
            if any(w in lower for w in ["claims", "violations", "numbers", "kitne", "how many", "count"]):
                audit_path = PROJECT_ROOT / "data" / "health_audit" / "health_audit_report.json"
                if audit_path.exists():
                    try:
                        import json as _json
                        data = _json.loads(audit_path.read_text(encoding="utf-8"))
                        report = data.get("report", {})
                        extra_context = (
                            "\n\n=== LATEST HEALTH AUDIT (use this for numbers) ===\n"
                            f"Products scanned: {data.get('total_products', 0)}\n"
                            f"Clean: {data.get('clean', 0)} | With issues: {len(report.get('products_fixable', []))}\n"
                            f"Product description violations: {len(report.get('products_fixable', []))}\n"
                            f"Product title violations: {len(report.get('titles_fixable', []))}\n"
                            f"Blog violations: {len(report.get('blogs_advisory', []))}\n"
                            f"Page violations: {len(report.get('pages_advisory', []))}\n"
                            f"Category renames needed: {len(report.get('categories_advisory', []))}\n"
                            "========================================\n"
                        )
                    except Exception:
                        pass

            # Live Google search via Serper when question needs current data
            serper_trigger = any(w in lower for w in [
                "trending", "latest", "current", "market", "competitor",
                "google", "search", "what's hot", "kya chal raha", "abhi kya",
                "competition", "prices", "demand", "ayurveda trend",
                "herbal trend", "real time", "realtime", "dhoondo",
                "search karo", "google pe", "kya chal raha"
            ])
            if serper_trigger:
                search_text = self._search_serper(original_text)
                if search_text:
                    extra_context += (
                        "\n\n=== LIVE GOOGLE SEARCH (Serper.dev) ===\n"
                        "Use this real-time data to answer. Cite sources if relevant.\n\n"
                        f"{search_text[:2500]}\n"
                        "========================================\n"
                    )

            reply = self._generate_reply(
                original_text,
                f"The owner is asking a question about their business/sites.\n"
                f"Current system status:\n{status_text}\n\n"
                f"Site in question: {site}\n"
                f"Business: Indian herbal products (falconherbs.com), "
                f"markets: Australia, UAE, USA, UK.\n\n"
                f"{extra_context}"
                "Answer the question based on available data. "
                "If you don't have the specific data, say so honestly and "
                "suggest running a relevant task. Keep it short — WhatsApp reply.",
            )

            self._whatsapp.send_message(reply)

        except Exception as exc:
            log.warning("Question handling failed: %s", exc)
            raw = (
                "Need more data to answer. "
                "Should I run a report? Try 'seo report' or 'sales report'."
            )
            reply = director_brain.wrap_raw_response(
                original_text, raw, "question_error",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)

    def _reply_unknown(self, original_text: str) -> None:
        """Reply when the message intent cannot be determined."""
        # Try Claude for a friendly response first
        try:
            reply = self._generate_reply(
                original_text,
                "The owner sent a message that doesn't clearly match any command. "
                "Generate a friendly reply that:\n"
                "1. Acknowledges their message\n"
                "2. Gently suggests what they can ask (status, run tasks, questions)\n"
                "3. Keep it short and friendly in Hinglish",
            )
            self._whatsapp.send_message(reply)
        except Exception:
            raw = (
                "Samajh nahi aaya. Try karo:\n"
                "• \"status\" / \"kya ho raha hai\" — update\n"
                "• \"order check\" / \"revenue\" — sales\n"
                "• \"health scan\" — compliance\n"
                "• \"keyword analysis\" — SEO\n"
                "• \"help\" — sab commands"
            )
            reply = director_brain.wrap_raw_response(
                original_text, raw, "unknown_fallback",
                recent_messages=self._get_recent_for_wrap(),
            )
            self._whatsapp.send_message(reply)

    # ══════════════════════════════════════════════════════════════════
    #  AI ENGINE
    # ══════════════════════════════════════════════════════════════════

    def _classify_intent(self, text: str) -> Optional[dict]:
        """
        Use AI to classify the owner's message intent.

        Uses DirectorBrain (DeepSeek R1 via OpenRouter) → falls back to
        keyword-based classifier if AI is unavailable.
        """
        # Build rich context for better classification
        try:
            context = memory.build_rich_context("owner")
        except Exception:
            context = ""

        # Try DirectorBrain first (reasoning model = better JSON output)
        result = director_brain.classify_intent(text, context=context)
        if result:
            log.info("Intent classified via DirectorBrain (DeepSeek R1)")
            return result

        # ── Fallback: keyword-based classification ──
        log.info("Falling back to keyword classifier")
        return self._keyword_classify(text)

    def _keyword_classify(self, text: str) -> dict:
        """
        Fallback intent classification using simple keyword matching.

        Used when Claude API is unavailable.
        """
        lower = text.lower().strip()

        # Status
        if any(w in lower for w in ["status", "update", "kya ho raha", "sab theek", "what's happening", "how's"]):
            return {"intent": "status_check", "task": None, "site": "falconherbs.com",
                    "params": {}, "reply_needed": True, "idea_text": None}

        # Approve
        if any(w in lower for w in ["yes", "approve", "haan", "ok", "go ahead", "kar do", "theek"]):
            return {"intent": "approve_action", "task": None, "site": "falconherbs.com",
                    "params": {}, "reply_needed": False, "idea_text": None}

        # Deny
        if any(w in lower for w in ["no", "deny", "nahi", "cancel", "reject", "ruko", "mat"]):
            return {"intent": "deny_action", "task": None, "site": "falconherbs.com",
                    "params": {}, "reply_needed": False, "idea_text": None}

        # Tasks
        task_map = {
            "uptime": "uptime_check",
            "performance": "performance_check",
            "speed": "performance_check",
        }
        complex_task_map = {
            "seo": "seo_audit",
            "security": "security_scan",
            "scan": "security_scan",
            "plugin": "plugin_update_check",
            "spam": "comment_spam_audit",
            "comment": "comment_spam_audit",
            "sales": "analyse_sales",
            "revenue": "analyse_sales",
            "keyword": "analyse_keywords",
            "content": "analyse_content_gaps",
            "competitor": "check_competitors",
            "report": "run_analysis",
            "health claim": "health_claim_audit",
            "wrong claim": "health_claim_audit",
            "compliance": "health_claim_audit",
            "govt": "health_claim_audit",
            "legal": "health_claim_audit",
        }
        
        for keyword, task in task_map.items():
            if keyword in lower:
                return {"intent": "run_task", "task": task, "site": "falconherbs.com",
                        "params": {}, "reply_needed": True, "idea_text": None}
                        
        for keyword, task in complex_task_map.items():
            if keyword in lower:
                return {"intent": "plan_task", "task": task, "site": "falconherbs.com",
                        "params": {}, "reply_needed": True, "idea_text": None}

        # Idea
        if any(w in lower for w in ["idea", "thinking", "what if", "let's try", "socha"]):
            return {"intent": "idea_capture", "task": None, "site": "falconherbs.com",
                    "params": {}, "reply_needed": True, "idea_text": text}

        # Question (if ends with ?)
        if "?" in text or any(w in lower for w in ["kitne", "kaisa", "kaise", "how", "what", "why", "when"]):
            return {"intent": "question", "task": None, "site": "falconherbs.com",
                    "params": {}, "reply_needed": True, "idea_text": None}

        return {"intent": "unknown", "task": None, "site": "falconherbs.com",
                "params": {}, "reply_needed": True, "idea_text": None}

    def _generate_reply(self, owner_message: str, context: str) -> str:
        """
        Generate a natural-language reply using DirectorBrain.

        DirectorBrain uses DeepSeek R1 (reasoning model) with the full
        Director persona — understands Hinglish, knows the business,
        gives intelligent contextual responses.
        """
        # GET REAL DATA — inject into context
        try:
            real_status = RealDataReader.get_real_system_status()
            real_data_block = (
                f"REAL SYSTEM DATA:\n"
                f"Tasks completed: {real_status['completed_count']} | "
                f"Failed: {real_status['failed_count']} | "
                f"Today's spend: ${real_status['spending'].get('today_usd', 0):.3f}\n"
                f"Recent tasks: {json.dumps(real_status['completed_tasks'][-3:], default=str)}"
            )
            full_context = f"{real_data_block}\n\n{context}" if context else real_data_block
        except Exception:
            full_context = context

        # Get recent conversation history
        try:
            recent_msgs = memory.get_recent_messages("owner", limit=8)
        except Exception:
            recent_msgs = []

        # Get live system status for context injection
        try:
            system_status = self._get_director_status()
        except Exception:
            system_status = None

        try:
            reply = director_brain.generate_reply(
                owner_message=owner_message,
                context=full_context,
                recent_messages=recent_msgs,
                system_status=system_status,
                director=getattr(self, "_director", None),
                bridge=getattr(self, "_bridge", None),
            )
            log.log_action(
                action="reply_generated",
                agent="commander",
                status="success",
                details={"chars": len(reply), "provider": "director_brain"},
            )
            return reply
        except Exception as exc:
            log.warning("DirectorBrain reply failed: %s", exc)
            return (
                "System is processing. Give me a moment.\n"
                "Try: 'status', 'sales report', or 'seo check'"
            )

    # ══════════════════════════════════════════════════════════════════
    #  STATUS HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _get_recent_for_wrap(self, user_id: str = "owner") -> Optional[List]:
        """Get recent messages for DirectorBrain wrap. Returns None on error."""
        try:
            return memory.get_recent_messages(user_id, limit=6)
        except Exception:
            return None

    def _get_director_status(self) -> dict:
        """
        Gather current status from the Director.

        Assembles data from multiple Director methods/properties.
        Returns a status dict even if the Director is unavailable.
        """
        status: Dict[str, Any] = {
            "running": False,
            "cycle_count": 0,
            "current_task": None,
            "current_site": None,
            "daily_spend": 0.0,
            "monthly_spend": 0.0,
            "pending_goals": 0,
            "complete_goals": 0,
            "failed_goals": 0,
            "timestamp": _utcnow_iso(),
        }

        if self._director is None:
            status["error"] = "Director not connected"
            return status

        try:
            status["running"] = getattr(self._director, "_running", False)
            status["cycle_count"] = getattr(self._director, "_cycle_count", 0)
            status["current_task"] = getattr(self._director, "_current_task", None)
            status["current_site"] = getattr(self._director, "_current_site", None)

            # Spend data
            if hasattr(self._director, "_load_spend"):
                spend = self._director._load_spend()
                status["daily_spend"] = spend.get("daily_total", 0.0)
                status["monthly_spend"] = spend.get("monthly_total", 0.0)

            # Goals
            if hasattr(self._director, "load_goals"):
                goals = self._director.load_goals()
                status["pending_goals"] = sum(1 for g in goals if g.get("status") == "pending")
                status["complete_goals"] = sum(1 for g in goals if g.get("status") == "complete")
                status["failed_goals"] = sum(1 for g in goals if g.get("status") == "failed")
                status["total_goals"] = len(goals)

        except Exception as exc:
            log.warning("Error gathering director status: %s", exc)
            status["error"] = str(exc)[:100]

        return status

    def _get_status_message(self, status: dict) -> str:
        """
        Format director status into a structured text summary.

        Parameters
        ----------
        status : dict
            Status data from ``_get_director_status()``.

        Returns
        -------
        str
            Multi-line plain text summary.
        """
        running = "🟢 Running" if status.get("running") else "⚫ Idle"
        task = status.get("current_task") or "none"
        site = status.get("current_site") or "idle"
        cycle = status.get("cycle_count", 0)
        daily = status.get("daily_spend", 0.0)
        monthly = status.get("monthly_spend", 0.0)
        pending = status.get("pending_goals", 0)
        done = status.get("complete_goals", 0)
        failed = status.get("failed_goals", 0)

        lines = [
            f"System: {running}",
            f"Cycle: #{cycle}",
            f"Current: {task} on {site}",
            f"Spend: ${daily:.2f} today / ${monthly:.2f} this month",
            f"Goals: {pending} pending, {done} done, {failed} failed",
        ]

        if status.get("error"):
            lines.append(f"⚠️ Issue: {status['error']}")

        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════
    #  IDEA STORAGE
    # ══════════════════════════════════════════════════════════════════

    def _save_idea(self, idea_text: str) -> None:
        """
        Append an idea to ``data/ideas.json``.

        Creates the file if it doesn't exist.

        Parameters
        ----------
        idea_text : str
            The full idea text from the owner.
        """
        try:
            IDEAS_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Load existing ideas
            ideas: List[Dict[str, Any]] = []
            if IDEAS_FILE.exists():
                try:
                    text = IDEAS_FILE.read_text(encoding="utf-8")
                    if text.strip():
                        ideas = json.loads(text)
                except (json.JSONDecodeError, OSError):
                    ideas = []

            # Append new idea
            ideas.append({
                "timestamp": _utcnow_iso(),
                "idea": idea_text,
                "status": "pending",
            })

            # Save atomically
            tmp = IDEAS_FILE.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(ideas, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            tmp.replace(IDEAS_FILE)

            log.info("Idea saved  |  total=%d  |  preview=%s", len(ideas), idea_text[:60])

            log.log_action(
                action="idea_captured",
                agent="commander",
                status="success",
                details={"idea_preview": idea_text[:100], "total_ideas": len(ideas)},
            )

        except Exception as exc:
            log.critical("Failed to save idea: %s", exc, exc_info=True)

    # ══════════════════════════════════════════════════════════════════
    #  UTILITY
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _task_to_agent(task: str) -> str:
        """Map a task name to the responsible agent."""
        agent_map = {
            "security_scan": "sentinel",
            "uptime_check": "sentinel",
            "performance_check": "developer",
            "plugin_update_check": "developer",
            "comment_spam_audit": "developer",
            "seo_audit": "strategist",
            "run_analysis": "strategist",
            "analyse_keywords": "strategist",
            "analyse_sales": "strategist",
            "analyse_traffic": "strategist",
            "analyse_content_gaps": "strategist",
            "check_competitors": "strategist",
        }
        return agent_map.get(task, "developer")

    def _resolve_credential(self, value: str) -> str:
        """Resolve ``{{ENV:VAR}}`` placeholders from environment."""
        if isinstance(value, str) and value.startswith("{{ENV:"):
            var_name = value[6:-2]
            return os.environ.get(var_name, "")
        return value

    def __repr__(self) -> str:
        director = "✅" if self._director else "❌"
        return f"<FalconCommander  unified_ai=✅  director={director}>"
