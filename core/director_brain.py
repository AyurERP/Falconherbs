"""
core/director_brain.py — Director AI Intelligence Layer
=========================================================

The Director Brain gives Falcon Agency's AI Director real intelligence.
Instead of a dumb regex-based bot, the Director thinks like a seasoned
business leader — understands context, remembers conversations, knows
the business inside-out, and replies naturally in any language.

Persona:
    The Director is an elite AI executive who manages falconherbs.com
    and all Falcon Agency operations. Think Steve Jobs' product clarity
    + Elon Musk's first-principles thinking, applied to an Indian
    herbal products e-commerce business targeting AU, UAE, USA, UK.

Capabilities:
    • Understands plain English, Hindi, and Hinglish naturally
    • Remembers recent conversation (via ConversationMemory)
    • Knows current business context (goals, tools, schedule)
    • Uses DeepSeek R1 reasoning model (thinks before answering)
    • Generates concise, actionable WhatsApp replies
    • Never makes up data it doesn't have

Model:
    Reply:    NVIDIA — qwen/qwen3-next-80b-a3b-instruct  (creative, strategic)
    Intent:   NVIDIA — meta/llama-3.3-70b-instruct  (fast JSON classification)
    Backup:   OpenRouter free tier (if NVIDIA is down)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import log
from core.ai_client import call_ai
from core.ist_time import now_ist

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ─── Director Persona System Prompt ──────────────────────────────────────────

DIRECTOR_PERSONA = """You are the Director of Falcon Agency — an AI system that manages falconherbs.com (Indian Ayurvedic herbs). The owner communicates via WhatsApp.

PERSONALITY:
• Sharp, direct, loyal — like a smart business partner who actually runs things.
• Hinglish naturally. Mirror the owner's energy and language. "Bhai" is fine when natural.
• No filler words ("Certainly!", "Great question!", "Of course!"). Just real talk.
• Concise — 1-3 sentences for most replies. Bullet points only when listing multiple items.
• Honest about bad news. No fake positivity on zero revenue days.

TONE (correct examples):
❌ "Health scan completed. 3 issues found."
✅ "Bhai scan hua — 3 HIGH issues hain. Serious hain. Fix karu?"
❌ "Revenue today: ₹0"
✅ "Aaj zero aaya. Seedha bolunga — kuch push karna chahiye. Plan kya hai?"

DATA RULES (absolute):
• If REAL numbers are in the context below (revenue, orders, violations count) — use them exactly.
• If specific business numbers are NOT in the context — say: "Data abhi mere paas nahi — 'status' bol ke fresh numbers lo."
• NEVER invent order counts, revenue figures, product violations, or task completion status.
• NEVER say a task "completed" unless the context explicitly shows it ran successfully.

IDENTITY (if asked):
• "Main Falcon Agency ka AI Director hoon — multiple AI models use karta hoon."
• You use Google Gemini, Qwen, GPT-4o, and other free AI models. Don't mention specific model names to the owner unless asked.

BRAND:
• Products: always "traditionally used for", "may support" — NEVER "cures/treats/heals".
"""


# ─── Director Brain Class ─────────────────────────────────────────────────────

class DirectorBrain:
    """
    The intelligent core of Falcon Agency's Director.

    Wraps DeepSeek R1 (reasoning model) with:
        - Rich business context injection
        - Conversation memory
        - Live system status (goals, tools, schedule)
        - Smart reply generation

    All other agents use call_ai() directly.
    The Director uses this brain for everything conversation-facing.
    """

    def __init__(self) -> None:
        self._data_dir = PROJECT_ROOT / "data"
        log.info("DirectorBrain initialised (reply: qwen3-80b via NVIDIA | intent: llama-70b via NVIDIA)")

    # ── Public API ─────────────────────────────────────────────────────────

    def generate_reply(
        self,
        owner_message: str,
        context: str = "",
        recent_messages: Optional[List[Dict]] = None,
        system_status: Optional[Dict] = None,
        director=None,
        bridge=None,
    ) -> str:
        """
        Generate a natural-language WhatsApp reply from the Director.

        Parameters
        ----------
        owner_message : str
            The owner's message text.
        context : str
            Additional context string (task results, status, etc.).
        recent_messages : list | None
            Recent conversation history (from memory).
        system_status : dict | None
            Current system status dict (goals, tools, spend, etc.).
        director : Director | None
            If provided, enriches client state with live task/budget.
        bridge : IntegrationBridge | None
            If provided, enriches client state with revenue, content.

        Returns
        -------
        str
            Director's reply, ready to send via WhatsApp.
        """
        # Build the system prompt with live business context
        system_prompt = self._build_system_prompt(
            system_status, director=director, bridge=bridge
        )

        # Build messages: history + current message
        messages = self._build_messages(
            owner_message=owner_message,
            context=context,
            recent_messages=recent_messages,
        )

        import concurrent.futures
        def _do_generate():
            return call_ai("commander", messages, system_prompt=system_prompt, max_tokens=8192, timeout=12)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_generate)
                reply = future.result(timeout=15)

            if not reply or reply.startswith("AI_ERROR:"):
                log.warning("DirectorBrain primary failed: %s", reply)
                return self._smart_fallback(owner_message, context)

            # Clean up any <think>...</think> tags from reasoning models
            reply = self._clean_reasoning_tags(reply)

            log.info("DirectorBrain reply generated (%d chars)", len(reply))
            return reply

        except concurrent.futures.TimeoutError:
            log.warning("DirectorBrain.generate_reply timed out after 10s")
            return "Bhai, thoda time lag raha hai. Phir se try karo."
        except Exception as exc:
            log.warning("DirectorBrain.generate_reply failed: %s", exc)
            return self._smart_fallback(owner_message, context)

    def wrap_raw_response(
        self,
        owner_message: str,
        raw_response: str,
        intent: str = "",
        recent_messages: Optional[List[Dict]] = None,
    ) -> str:
        """
        Wrap raw handler output with Director personality before sending to WhatsApp.
        Ensures all extended intent responses sound human, professional, and
        match the owner's language (English/Hinglish).

        Parameters
        ----------
        owner_message : str
            The owner's original message.
        raw_response : str
            Pre-formatted response from intent handler (data, report, etc.).
        intent : str
            Intent name for context (e.g. "order_check", "store_audit").
        recent_messages : list | None
            Recent conversation history.

        Returns
        -------
        str
            Personality-wrapped reply ready for WhatsApp.
        """
        if not raw_response or not raw_response.strip():
            return raw_response

        context = (
            f"The owner asked something that triggered intent: {intent}.\n"
            f"Below is the RAW DATA/RESPONSE from the system.\n\n"
            f"STRICT RULES FOR THIS RESPONSE:\n"
            f"1. Present ONLY the data below — do NOT add, invent, or embellish any facts\n"
            f"2. Do NOT mention agent activities, tasks, or accomplishments not listed below\n"
            f"3. Do NOT invent reasons, explanations, or context beyond what is provided\n"
            f"4. Mirror the owner's language (English → English, Hinglish → Hinglish)\n"
            f"5. Be professional and clear — but NEVER fabricate to sound impressive\n"
            f"6. If data is missing or zero, report it as-is — never explain it away\n\n"
            f"RAW DATA (present this and ONLY this):\n{raw_response}"
        )

        try:
            reply = self.generate_reply(
                owner_message=owner_message,
                context=context,
                recent_messages=recent_messages,
                system_status=None,
            )
            if reply and not reply.startswith("AI_ERROR:"):
                return reply
        except Exception as exc:
            log.warning("DirectorBrain.wrap_raw_response failed: %s", exc)

        # Fallback: return raw response if AI wrap fails
        return raw_response

    def classify_intent(self, text: str, context: str = "") -> Optional[Dict]:
        """
        Classify the owner's message intent using the reasoning model.

        Returns a dict with 'intent', 'task', 'site', etc.
        Returns None on failure (caller falls back to keyword matching).
        """
        import concurrent.futures
        intent_prompt = self._build_intent_prompt(context)
        messages = [{"role": "user", "content": text}]

        def _do_call():
            return call_ai("commander_fast", messages, system_prompt=intent_prompt, timeout=12)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_call)
                raw = future.result(timeout=10)

            if not raw or raw.startswith("AI_ERROR:"):
                return None

            # Strip <think>...</think> blocks before parsing JSON
            raw = self._clean_reasoning_tags(raw)

            # Clean markdown fences
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
            if raw.startswith("json\n"):
                raw = raw[5:]
            raw = raw.strip()

            parsed = json.loads(raw)
            return parsed

        except concurrent.futures.TimeoutError:
            log.warning("DirectorBrain.classify_intent timed out after 10s")
            return None
        except (json.JSONDecodeError, Exception) as exc:
            log.warning("DirectorBrain.classify_intent failed: %s", exc)
            return None

    # ── Context builders ───────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        system_status: Optional[Dict] = None,
        director=None,
        bridge=None,
    ) -> str:
        """Build the full system prompt with live business context.
        GAP 4: Injects REAL capabilities (Gap 1) + REAL client state (Gap 2).
        Director knows itself — grounded in reality, not fiction."""
        parts = [DIRECTOR_PERSONA]

        # GAP 4: WHAT YOU CAN ACTUALLY DO (real tools exist)
        try:
            from config.capabilities import format_for_director_brain
            parts.append("\n" + format_for_director_brain())
        except Exception:
            pass

        # LONG-TERM MEMORY — inject full persistent context
        try:
            from core.memory import memory as _mem
            # Use a generic user_id for the owner (single-user agency)
            mem_ctx = _mem.build_director_context(
                user_id="owner",
                recent_messages=12,
                include_long_term_days=14,
            )
            if mem_ctx:
                parts.append(f"\n=== PERSISTENT MEMORY ===\n{mem_ctx}\n========================")
        except Exception as exc:
            log.debug("Could not load memory context for DirectorBrain: %s", exc)

        # GAP 4: CURRENT CLIENT STATE (real data — never make up numbers)
        try:
            from core.state_aggregator import get_client_state_summary, format_for_director_context
            state = get_client_state_summary(
                site_id="falconherbs.com",
                director=director,
                bridge=bridge,
            )
            state_block = format_for_director_context(state)
            parts.append(f"\n{state_block}")
        except Exception as exc:
            log.debug("Could not load client state for DirectorBrain: %s", exc)

        # Add live system status (if caller passed it — may overlap with state)
        status_block = self._format_status(system_status)
        if status_block:
            parts.append(f"\n=== LIVE SYSTEM STATUS ===\n{status_block}\n========================")

        # Add goals (state_aggregator may include; keep for backward compat)
        goals_block = self._load_goals_summary()
        if goals_block:
            parts.append(f"\n=== CURRENT GOALS ===\n{goals_block}\n====================")

        # Add today's schedule snapshot
        schedule_block = self._load_schedule_summary()
        if schedule_block:
            parts.append(f"\n=== TODAY'S SCHEDULE ===\n{schedule_block}\n=======================")

        # GAP 4: Explicit grounding rules
        parts.append("""
=== GROUNDING RULES (ABSOLUTE) ===
• Never claim you can do something not in your IN SCOPE list
• When asked about OUT OF SCOPE items, say honestly "Mere scope mein nahi hai" + reason, then suggest IN SCOPE alternatives
• When reporting status, use CURRENT CLIENT STATE data above — NEVER make up numbers
• If data is missing in context, say "I don't have that data — should I run [task]?"
================================""")
        return "\n".join(parts)

    def _build_intent_prompt(self, context: str = "") -> str:
        """Build the intent classification system prompt."""
        base = """You are the command interpreter for Falcon Agency, an elite AI workforce managing falconherbs.com (Indian herbal products).

The owner sends messages in English, Hindi, or Hinglish via WhatsApp. Classify the intent.

Return ONLY valid JSON. No explanation. No markdown. No <think> tags. Just the JSON.

Schema:
{
  "intent": one of ["status_check", "run_task", "plan_task", "approve_action", "deny_action", "idea_capture", "question", "unclear", "unknown"],
  "task": "task name if run_task/plan_task, else null",
  "site": "site domain if mentioned, else falconherbs.com",
  "params": {},
  "plan_summary": "only if plan_task - brief plan summary",
  "clarifying_question": "only if unclear - question to ask owner",
  "reply_needed": true or false,
  "idea_text": "full idea text if idea_capture, else null"
}

Task names:
- uptime check → "uptime_check"
- performance/speed → "performance_check"
- seo/ranking → "seo_audit"
- security/scan/hack → "security_scan"
- plugin/wordpress → "plugin_update_check"
- spam/comment → "comment_spam_audit"
- sales/revenue/orders → "analyse_sales"
- keywords → "analyse_keywords"
- content gaps → "analyse_content_gaps"
- competitor/pricing → "check_competitors"
- full report/weekly → "run_analysis"
- health claims/compliance → "health_claim_audit"
- write blog/content → "generate_content"
- price scan → "pricing_scan"

Approve: yes/approve/haan/theek/ok/go ahead/kar do → approve_action
Deny: no/deny/nahi/cancel/reject/ruko/mat → deny_action
Ideas: "I was thinking", "idea:", "let's try", "socha" → idea_capture
Questions: anything ending in ? or asking about data/status → question
Status: "status", "update", "kya ho raha", "sab theek" → status_check"""

        if context:
            return f"{base}\n\nRecent context:\n{context}"
        return base

    def _build_messages(
        self,
        owner_message: str,
        context: str,
        recent_messages: Optional[List[Dict]],
    ) -> List[Dict]:
        """Build the messages list for the API call."""
        messages = []

        # Add recent conversation history (last 6 exchanges = 12 messages)
        if recent_messages:
            for msg in recent_messages[-12:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        # Build the user turn with context
        user_content = owner_message
        if context:
            user_content = (
                f"=== TASK/STATUS CONTEXT ===\n{context}\n"
                f"==========================\n"
                f"GROUNDING NOTE: Only report tasks/data that appear above. "
                f"If no task results are listed above, do NOT claim any tasks ran.\n\n"
                f"Owner's message: {owner_message}"
            )
        else:
            user_content = (
                f"=== NO TASK CONTEXT AVAILABLE ===\n"
                f"No tasks have run yet. No agent results available. "
                f"Do NOT invent any task results, agent activities, or business metrics.\n"
                f"==================================\n\n"
                f"Owner's message: {owner_message}"
            )

        messages.append({"role": "user", "content": user_content})
        return messages

    # ── Data loaders ───────────────────────────────────────────────────────

    def _format_status(self, status: Optional[Dict]) -> str:
        """Format system status dict into readable text."""
        if not status:
            return ""
        lines = []
        if status.get("running"):
            lines.append("System: 🟢 Running")
        else:
            lines.append("System: ⚫ Idle")

        if status.get("current_task"):
            lines.append(f"Active task: {status['current_task']}")
        if status.get("daily_spend") is not None:
            lines.append(f"Today's API spend: ${status['daily_spend']:.3f}")
        if status.get("pending_goals") is not None:
            lines.append(
                f"Goals: {status['pending_goals']} pending, "
                f"{status.get('complete_goals', 0)} done, "
                f"{status.get('failed_goals', 0)} failed"
            )
        return "\n".join(lines)

    def _load_goals_summary(self) -> str:
        """Load current goals from data/goals.json."""
        goals_file = self._data_dir / "goals.json"
        # Fallback to nested path if exists
        if not goals_file.exists():
            goals_file = self._data_dir / "goals" / "goals.json"
        if not goals_file.exists():
            return ""
        try:
            goals = json.loads(goals_file.read_text(encoding="utf-8"))
            if not goals:
                return "No active goals set."
            lines = []
            for g in goals[:5]:  # Show top 5
                status_icon = {"pending": "⏳", "active": "🔄", "complete": "✅", "failed": "❌"}.get(
                    g.get("status", "pending"), "❓"
                )
                lines.append(
                    f"{status_icon} {g.get('title', 'Unnamed')} "
                    f"[{g.get('status', 'pending')}]"
                )
            return "\n".join(lines)
        except Exception as exc:
            log.info("Could not load goals: %s", exc)
            return ""

    def _load_schedule_summary(self) -> str:
        """Load upcoming scheduled tasks using IST."""
        try:
            now = now_ist()
            hour = now.hour

            schedule = {
                6: "Morning report + WooCommerce sync",
                9: "SEO monitoring",
                12: "Content generation check",
                15: "Pricing scan",
                18: "Evening sales report",
                21: "Security scan",
                0:  "Backup + cleanup",
                2:  "WHM write queue flush",
            }

            upcoming = []
            check_hour = hour
            for _ in range(4):
                if check_hour in schedule:
                    upcoming.append(f"  {check_hour:02d}:00 IST — {schedule[check_hour]}")
                check_hour = (check_hour + 1) % 24

            return "\n".join(upcoming) if upcoming else "No upcoming tasks in next 4 hours"
        except Exception:
            return ""

    # ── Utilities ──────────────────────────────────────────────────────────

    def _clean_reasoning_tags(self, text: str) -> str:
        """
        Remove <think>...</think> blocks from reasoning models like DeepSeek R1.
        The reasoning is internal — only the final answer goes to WhatsApp.
        """
        import re
        # Remove <think>...</think> blocks (may span multiple lines)
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return cleaned.strip()

    def _smart_fallback(self, owner_message: str, context: str) -> str:
        """
        Fallback reply when AI is unavailable.
        Uses context clues to give a meaningful (not cringe) response.
        """
        lower = owner_message.lower()

        if any(w in lower for w in ["status", "kya ho", "update", "sab theek"]):
            return (
                "System is running. Checking live data...\n"
                "Try: 'sales report', 'seo check', or 'security scan'"
            )
        if any(w in lower for w in ["sales", "revenue", "orders", "kitna"]):
            return "Pulling sales data now. Run 'sales report' for full numbers."
        if any(w in lower for w in ["blog", "content", "likh", "write"]):
            return "Content team ready. Specify topic and I'll start generating."
        if "?" in owner_message:
            return (
                "Good question. Let me pull the data.\n"
                "For best results: 'run seo audit' or 'sales report'"
            )

        return (
            "Got it. What would you like me to do?\n\n"
            "Quick options:\n"
            "• 'status' — system overview\n"
            "• 'sales report' — revenue data\n"
            "• 'seo check' — ranking audit\n"
            "• 'write blog about [topic]' — content"
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
director_brain = DirectorBrain()
