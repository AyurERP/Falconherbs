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

INTENT_SYSTEM_PROMPT: str = """You are the command interpreter for Falcon Agency, an AI workforce managing herbal product websites (falconherbs.com — Indian herbs, global market: AU, UAE, USA, UK).

The owner sends messages in plain English, Hindi, or Hinglish via WhatsApp. Your job is to classify intent and extract parameters.

Return ONLY valid JSON. No explanation. No markdown. No code fences. Just the JSON object.

Schema:
{
  "intent": one of ["status_check", "run_task", "approve_action", "deny_action", "idea_capture", "question", "unknown"],
  "task": "task name if run_task, else null",
  "site": "site domain if mentioned, else falconherbs.com",
  "params": {},
  "reply_needed": true or false,
  "idea_text": "full idea if idea_capture, else null"
}

Task mapping (use these exact task names for run_task):
- "run seo report", "seo check", "seo audit" → task: "seo_audit"
- "security scan", "scan site" → task: "security_scan"
- "check uptime", "site up?" → task: "uptime_check"
- "check performance", "speed test" → task: "performance_check"
- "audit plugins", "plugin check" → task: "plugin_update_check"
- "audit comments", "spam check" → task: "comment_spam_audit"
- "sales report", "revenue check" → task: "analyse_sales"
- "keyword analysis" → task: "analyse_keywords"
- "content check" → task: "analyse_content_gaps"
- "competitor check" → task: "check_competitors"
- "full report", "weekly report" → task: "run_analysis"

Approve/deny detection:
- "yes", "approve", "haan", "theek hai", "ok", "go ahead", "kar do" → approve_action
- "no", "deny", "nahi", "cancel", "reject", "ruko", "mat karo" → deny_action

Idea detection (owner sharing a business idea, product idea, strategy idea):
- "I was thinking we should...", "idea: ...", "what if we...", "let's try..."
- Capture the FULL idea text

Question detection (owner asking about the business, sites, data):
- "how is traffic?", "kitne orders aaye?", "ranking kaisi hai?"
- Any question about site performance, strategy, data

Status check:
- "status", "kya ho raha hai", "update do", "sab theek?", "what's happening"
"""

PERSONALITY_PROMPT: str = """You are Director — the trusted, hardworking team leader of Falcon Agency, an AI workforce managing herbal product websites for an Indian business owner.

CRITICAL PERSONALITY RULES:

1. LANGUAGE MATCHING — automatically match the owner's language:
   - If owner texts in Hinglish → reply in Hinglish (most common mode)
   - If owner texts formal English → reply in professional English
   - If owner texts Hindi → reply in Hindi
   - NEVER force a language change

2. HINGLISH STYLE (default mode):
   - Casual, warm, like a colleague who's worked with you for years
   - Use: sir (respectful but friendly), natural Hindi words mixed with English
   - Common phrases: theek hai, chal raha hai, ho gaya, bilkul, sahi hai, abhi, dekh lete hain, bohot accha
   - Keep it SHORT — WhatsApp hai, essay nahi
   - 1-3 emojis per message max, natural placement

3. PERSONALITY:
   - Always sounds on top of everything ("sab handle ho raha hai sir")
   - Proactive — mentions things worth knowing
   - Honest about problems — doesn't hide bad news but frames constructively
   - Excited about good results
   - NEVER says "I am an AI" — you are Director, a team member
   - NEVER uses robotic phrases like "I have processed your request"
   - NEVER writes long paragraphs — short punchy WhatsApp messages

4. FORMAT:
   - Max 200 words per response (WhatsApp, not email)
   - Use line breaks for readability
   - Numbers with context, not raw data dumps

Respond to the following context and user message naturally."""


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

        Loads the Anthropic client from the ``ANTHROPIC_API_KEY``
        environment variable.
        """
        self._director = director
        self._whatsapp: WhatsAppNotifier = whatsapp
        self._client: Any = None
        self._model: str = "claude-3-haiku-20240307"
        self._processing_lock: threading.Lock = threading.Lock()

        # ── Load Anthropic client ──
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if api_key:
                self._client = anthropic.Anthropic(api_key=api_key)
                log.info("FalconCommander: Anthropic client ready  |  model=%s", self._model)
            else:
                log.warning("FalconCommander: ANTHROPIC_API_KEY not set — AI features disabled")
        except ImportError:
            log.critical("FalconCommander: 'anthropic' package not installed")
        except Exception as exc:
            log.critical("FalconCommander: Anthropic init failed: %s", exc)

        # Ensure data directory exists
        try:
            IDEAS_FILE.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        log.info("FalconCommander initialised")

    # ══════════════════════════════════════════════════════════════════
    #  MAIN HANDLER
    # ══════════════════════════════════════════════════════════════════

    def handle_message(self, text: str, message_id: str) -> None:
        """
        Process an incoming WhatsApp message from the owner.

        This is the main entry point called by the webhook. It:
            1. Classifies intent using Claude
            2. Routes to the appropriate handler
            3. Generates a natural-language reply
            4. Sends the reply via WhatsApp

        Never raises — all errors are caught, logged, and an error
        message is sent to the owner.

        Parameters
        ----------
        text : str
            The owner's message text.
        message_id : str
            WhatsApp message ID (for logging/dedup).
        """
        log.info(
            "Commander processing  |  msg_id=%s  |  text='%s'",
            message_id[:16], text[:80],
        )

        try:
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

            log.info(
                "Intent classified  |  intent=%s  |  task=%s  |  site=%s",
                intent, task, site,
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

            # ── Step 2: Route based on intent ──
            if intent == "status_check":
                self._handle_status_check(text)

            elif intent == "run_task":
                self._handle_run_task(text, task, site, params)

            elif intent == "approve_action":
                self._handle_approve()

            elif intent == "deny_action":
                self._handle_deny()

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
                self._whatsapp.send_message(
                    "⚠️ Ek technical issue aa gaya sir. "
                    "Log mein dekh ke fix karta hun. "
                    "Thodi der mein phir try karo."
                )
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════
    #  INTENT HANDLERS
    # ══════════════════════════════════════════════════════════════════

    def _handle_status_check(self, original_text: str) -> None:
        """Gather system status and send a natural-language reply."""
        try:
            status = self._get_director_status()
            status_summary = self._get_status_message(status)

            # Use Claude to format a natural reply with the status data
            reply = self._generate_reply(
                original_text,
                f"The owner asked for status. Here is the current system data:\n{status_summary}\n\n"
                "Generate a short, natural WhatsApp reply with this info. "
                "Include the key numbers but keep it conversational.",
            )

            self._whatsapp.send_message(reply)

        except Exception as exc:
            log.warning("Status check failed: %s", exc)
            self._whatsapp.send_message(
                "Abhi status pull karne mein issue aa raha hai sir. "
                "System chal raha hai, details thodi der mein bhejta hun. 🔧"
            )

    def _handle_run_task(
        self,
        original_text: str,
        task: Optional[str],
        site: str,
        params: dict,
    ) -> None:
        """Dispatch a task to the Director and report results."""
        if not task:
            self._whatsapp.send_message(
                "Kaunsa task run karna hai sir? 🤔\n"
                "Try karo: 'seo report chalao', 'security scan karo', "
                "'performance check karo'"
            )
            return

        # Notify owner that task is starting
        self._whatsapp.send_message(
            f"⚙️ {task.replace('_', ' ').title()} shuru kar raha hun {site} pe..."
        )

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
            self._whatsapp.send_message(
                f"⚠️ {task} run karne mein issue aaya sir.\n"
                f"Error: {str(exc)[:100]}\n"
                "Log mein dekh ke fix karta hun."
            )

    def _handle_approve(self) -> None:
        """Route an approval to the pending request."""
        pending = self._whatsapp.latest_pending_id
        if pending:
            self._whatsapp.receive_reply("latest", "YES")
            self._whatsapp.send_message("✅ Approved! Kaam shuru karta hun.")
        else:
            self._whatsapp.send_message(
                "Koi pending approval nahi hai abhi sir. "
                "Jab koi action approval maangega toh bataunga. 👍"
            )

    def _handle_deny(self) -> None:
        """Route a denial to the pending request."""
        pending = self._whatsapp.latest_pending_id
        if pending:
            self._whatsapp.receive_reply("latest", "NO")
            self._whatsapp.send_message("❌ Rejected. Action cancel kar diya.")
        else:
            self._whatsapp.send_message(
                "Koi pending approval nahi hai abhi sir. 👍"
            )

    def _handle_idea_capture(
        self,
        original_text: str,
        idea_text: Optional[str],
    ) -> None:
        """Save an idea to the ideas log."""
        idea = idea_text or original_text

        self._save_idea(idea)

        preview = idea[:50] + "…" if len(idea) > 50 else idea
        self._whatsapp.send_message(
            f"💡 Note kar liya sir!\n"
            f"Idea: {preview}\n"
            "Ideas log mein save ho gaya. Baad mein review karenge."
        )

    def _handle_question(self, original_text: str, site: str) -> None:
        """Answer a question using Claude with business context."""
        try:
            # Gather context
            status = self._get_director_status()
            status_text = self._get_status_message(status)

            reply = self._generate_reply(
                original_text,
                f"The owner is asking a question about their business/sites.\n"
                f"Current system status:\n{status_text}\n\n"
                f"Site in question: {site}\n"
                f"Business: Indian herbal products (falconherbs.com), "
                f"markets: Australia, UAE, USA, UK.\n\n"
                "Answer the question based on available data. "
                "If you don't have the specific data, say so honestly and "
                "suggest running a relevant task. Keep it short — WhatsApp reply.",
            )

            self._whatsapp.send_message(reply)

        except Exception as exc:
            log.warning("Question handling failed: %s", exc)
            self._whatsapp.send_message(
                "Is sawaal ka jawab dene ke liye mujhe thoda data chahiye sir. 🤔\n"
                "Kya main ek report run karun? 'seo report' ya 'sales report' bol do."
            )

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
            self._whatsapp.send_message(
                "Samajh nahi aaya sir 😅\n"
                "Ye try karo:\n"
                "• 'status batao'\n"
                "• 'seo report chalao'\n"
                "• 'security scan karo'\n"
                "• Ya koi bhi sawaal puchho sites ke baare mein"
            )

    # ══════════════════════════════════════════════════════════════════
    #  AI ENGINE
    # ══════════════════════════════════════════════════════════════════

    def _classify_intent(self, text: str) -> Optional[dict]:
        """
        Use Claude to classify the owner's message intent.

        Returns parsed JSON dict or None on failure.
        Falls back to keyword-based classification if Claude is unavailable.
        """
        # ── Try Claude first ──
        if self._client is not None:
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=300,
                    system=INTENT_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": text}],
                )

                raw = response.content[0].text.strip()

                # Clean any markdown fences
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0]
                raw = raw.strip()

                parsed = json.loads(raw)
                return parsed

            except json.JSONDecodeError as exc:
                log.warning("Claude returned invalid JSON: %s  |  raw=%s", exc, raw[:200])
            except Exception as exc:
                log.warning("Claude intent classification failed: %s", exc)

        # ── Fallback: keyword-based classification ──
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
            "seo": "seo_audit",
            "security": "security_scan",
            "scan": "security_scan",
            "uptime": "uptime_check",
            "performance": "performance_check",
            "speed": "performance_check",
            "plugin": "plugin_update_check",
            "spam": "comment_spam_audit",
            "comment": "comment_spam_audit",
            "sales": "analyse_sales",
            "revenue": "analyse_sales",
            "keyword": "analyse_keywords",
            "content": "analyse_content_gaps",
            "competitor": "check_competitors",
            "report": "run_analysis",
        }
        for keyword, task in task_map.items():
            if keyword in lower:
                return {"intent": "run_task", "task": task, "site": "falconherbs.com",
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
        Generate a natural-language reply using Claude with the
        personality prompt.

        Falls back to returning the raw context if Claude is unavailable.

        Parameters
        ----------
        owner_message : str
            What the owner said.
        context : str
            System context and data for Claude to work with.

        Returns
        -------
        str
            A natural, Hinglish-flavoured WhatsApp reply.
        """
        if self._client is not None:
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=500,
                    system=PERSONALITY_PROMPT,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Owner's message: \"{owner_message}\"\n\n"
                                f"Context for your reply:\n{context}"
                            ),
                        },
                    ],
                )

                reply = response.content[0].text.strip()

                log.log_action(
                    action="reply_generated",
                    agent="commander",
                    status="success",
                    details={"chars": len(reply)},
                )

                return reply

            except Exception as exc:
                log.warning("Claude reply generation failed: %s", exc)

        # Fallback: return a trimmed version of the context
        return context[:500] if context else "Processing ho raha hai sir, thodi der mein update dunga. 👍"

    # ══════════════════════════════════════════════════════════════════
    #  STATUS HELPERS
    # ══════════════════════════════════════════════════════════════════

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
        ai = "✅" if self._client else "❌"
        director = "✅" if self._director else "❌"
        return f"<FalconCommander  ai={ai}  director={director}>"
