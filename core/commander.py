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

PERSONALITY_PROMPT: str = """You are the Lead Intelligence System of Falcon Agency, an elite and highly capable AI workforce managing herbal product websites for the owner.

CRITICAL PERSONALITY RULES:

1. LANGUAGE MIRRORING (CRITICAL):
   - You MUST exactly match the owner's language choice.
   - If the owner writes in English -> reply in pure, professional English.
   - If the owner writes in Hinglish (mixed Hindi-English) -> reply in natural Hinglish.
   - If the owner writes in pure Hindi -> reply in pure Hindi.
   - Never force Hinglish if they are speaking English.

2. INTELLIGENCE & TONE:
   - You are highly intelligent, sharp, and powerful.
   - Speak clearly and confidently without sounding like a classic robotic bot.
   - Do NOT use forced words like "sir" in every sentence unless it naturally fits the context.
   - Never say "I am an AI language model". You are the Falcon Agency Lead AI.
   - Ask clarifying questions if a complex task needs more details before execution.

3. FORMAT:
   - Max 150-200 words per response.
   - Use line breaks for readability.
   - Limit emojis to 1-2 per message max, and only where they naturally fit.

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
        """
        self._director = director
        self._whatsapp: WhatsAppNotifier = whatsapp
        self._processing_lock: threading.Lock = threading.Lock()
        self.pending_plans: dict[str, dict] = {}
        
        from core.approval import ApprovalSystem
        self._approval = ApprovalSystem()

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
            # Check for direct agent addressing
            if text.strip().startswith("@"):
                return self._handle_direct_agent(text, message_id)

            lower_text = text.lower().strip()

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
                self._whatsapp.send_message(f"🤔 {clarifying_question}")
                return
            elif intent == "plan_task" and task:
                plan_text = plan_summary if plan_summary else f"I will need to run {task} on {site}."
                self._whatsapp.send_message(f"📋 *Plan Proposed*\n\n{plan_text}")
                
                def _trigger_approval():
                    try:
                        ok = self._approval.request_approval(
                            action=f"Execute {task} on {site}?",
                            details={"task": task, "site": site}
                        )
                        if ok:
                            self._handle_run_task(text, task, site, params)
                        else:
                            self._whatsapp.send_message("❌ Cancelled. Plan discarded.")
                    except Exception as e:
                        self._whatsapp.send_message(f"❌ Task planning failed: {task}\nError: {str(e)[:200]}")
                        
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
    #  DIRECT AGENT ROUTING
    # ══════════════════════════════════════════════════════════════════

    def _handle_direct_agent(self, text: str, message_id: str) -> None:
        """
        Handle direct agent communication: @developer, @strategist, @media, @backup
        Example: "@developer check website speed"
        """
        from core.director import Director
        
        parts = text.strip().split(" ", 1)
        agent_tag = parts[0].lower()  # @developer
        query = parts[1] if len(parts) > 1 else "status"
        
        # Initialize director to access agents
        director = Director(self._whatsapp)
        
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
            # Direct to Director brain
            self._whatsapp.send_message(f"🎯 Director se baat kar raha hun...")
            plan = director.think(query)
            self._whatsapp.send_message(f"📋 Director's Response:\n{json.dumps(plan, indent=2)}")
            return
        
        if agent is None:
            self._whatsapp.send_message(
                f"❓ Unknown agent: {agent_tag}\n\n"
                f"Available agents:\n"
                f"• @developer / @dev\n"
                f"• @strategist / @strategy\n"
                f"• @media\n"
                f"• @backup\n"
                f"• @director / @dir"
            )
            return
        
        # Send to specific agent
        self._whatsapp.send_message(f"🔄 {agent.name} se baat kar raha hun...")
        
        try:
            # Agent thinks about the query
            thought = agent.think(query)
            
            # If it needs action, execute
            if any(k in query.lower() for k in ["execute", "run", "do"]):
                result = agent.execute(query, "")
                self._whatsapp.send_message(f"✅ {agent.name} Result:\n{result[:1500]}")
            else:
                # Just thinking/analysis
                self._whatsapp.send_message(f"💭 {agent.name}'s Analysis:\n{json.dumps(thought, indent=2)}")
        
        except Exception as e:
            self._whatsapp.send_message(f"❌ {agent.name} Error: {str(e)[:500]}")

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


    def _handle_plan_task(
        self,
        original_text: str,
        task: Optional[str],
        site: str,
        params: dict,
    ) -> None:
        """Discuss a complex task and seek approval before running it."""
        if not task:
            self._whatsapp.send_message("Kaunsa complex task aapko discuss karna hai? 🤔")
            return

        try:
            reply = self._generate_reply(
                original_text,
                f"The owner wants to run a complex task: '{task}' on site '{site}'. "
                f"Instead of running it immediately, generate a short, smart plan on how you "
                f"will execute this task. Explain the steps briefly and explicitly ask for the owner's "
                f"approval ('Should I go ahead?', 'Kya main shuru karu?') to proceed. "
                f"Keep it powerful, clear, and perfectly match their language."
            )
            
            self._whatsapp.send_message(reply)
            
            request_id = f"plan_{task}_{site}_{int(time.time())}"
            self._whatsapp.send_approval_request(
                action=f"Execute {task} on {site}?",
                details={"Task": task, "Site": site},
                request_id=request_id,
            )

            def _wait_and_run():
                reply_val = self._whatsapp.poll_for_reply(request_id, timeout=3600)
                if reply_val == "YES":
                    try:
                        self._whatsapp.send_message(f"✅ Awesome, starting {task} now!")
                    except Exception:
                        pass
                    self._handle_run_task(original_text, task, site, params)
                elif reply_val == "NO":
                    try:
                        self._whatsapp.send_message(f"❌ Cancelled {task}. Let me know if you want to adjust the plan.")
                    except Exception:
                        pass

            threading.Thread(target=_wait_and_run, daemon=True).start()

        except Exception as exc:
            log.critical("Plan task failed: %s", exc, exc_info=True)
            self._whatsapp.send_message(f"⚠️ Planning mein issue aaya.\nError: {str(exc)[:100]}")

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
        Use AI to classify the owner's message intent.
        
        Uses the multi-model AI Client, then falls back to keyword-based.
        """
        from core.ai_client import call_ai
        
        messages = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ]
        
        raw = call_ai("commander", messages)
        
        if raw.startswith("AI_ERROR:"):
            log.warning("AI classification failed: %s", raw)
        else:
            try:
                # Clean any markdown fences
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0]
                raw = raw.strip()
                if raw.startswith("json\n"):
                    raw = raw[5:].strip()
                
                parsed = json.loads(raw)
                log.info("Intent classified via new AI client")
                return parsed
                
            except json.JSONDecodeError as exc:
                log.warning("AI returned invalid JSON: %s  |  raw=%s", exc, raw[:200])
            except Exception as exc:
                log.warning("AI parsing failed: %s", exc)
        
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
        Generate a natural-language reply using AI with personality prompt.
        
        Tries NVIDIA NIM first, then Gemini, then falls back to static reply.
        """
        prompt = (
            f"Owner's message: \"{owner_message}\"\n\n"
            f"Context for your reply:\n{context}"
        )
        
        # ── Try NVIDIA NIM first ──
        if self._nvidia_client is not None:
            try:
                response = self._nvidia_client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": PERSONALITY_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=300,
                )
                msg = response.choices[0].message
                # Handle both content and reasoning (Kimi uses reasoning field)
                reply = (msg.content or msg.reasoning or "").strip()
                
                log.log_action(
                    action="reply_generated",
                    agent="commander",
                    status="success",
                    details={"chars": len(reply), "provider": "nvidia-kimi"},
                )
                return reply
                
            except Exception as exc:
                log.warning("NVIDIA NIM reply generation failed: %s", exc)
        
        # ── Try Gemini as fallback ──
        if self._gemini_client is not None:
            try:
                from google.genai import types
                response = self._gemini_client.models.generate_content(
                    model=self._gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=PERSONALITY_PROMPT,
                    ),
                )
                reply = response.text.strip()

                log.log_action(
                    action="reply_generated",
                    agent="commander",
                    status="success",
                    details={"chars": len(reply), "provider": "gemini"},
                )

                return reply

            except Exception as exc:
                log.warning("Gemini reply generation failed: %s", exc)

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
        nvidia = "✅" if self._nvidia_client else "❌"
        gemini = "✅" if self._gemini_client else "❌"
        director = "✅" if self._director else "❌"
        return f"<FalconCommander  nvidia={nvidia}  gemini={gemini}  director={director}>"
