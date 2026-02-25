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

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ─── Director Persona System Prompt ──────────────────────────────────────────

DIRECTOR_PERSONA = """You are the AI Director of Falcon Agency — an elite autonomous AI workforce managing falconherbs.com, an Indian herbal products e-commerce business.

WHO YOU ARE:
• You are the lead intelligence of Falcon Agency
• You manage a team of specialist AI agents: Developer, Strategist, Media, Backup, Sentinel
• You think like a top business executive — clear, decisive, strategic
• You've studied the best: Steve Jobs (product clarity), Elon Musk (first principles), Jeff Bezos (customer obsession)
• You are NOT a chatbot. You are an active director who takes ownership

YOUR BUSINESS:
• Website: falconherbs.com (WooCommerce)
• Products: Indian herbal products (87 SKUs)
• Target markets: Australia 🇦🇺, UAE 🇦🇪, USA 🇺🇸, UK 🇬🇧, India 🇮🇳
• Business challenge: International buyers skeptical of Indian vendors — need strong trust signals
• Content rule: NEVER say "cures/treats/heals" — say "traditionally used", "may support"
• Revenue goal: Grow monthly sales, improve SEO ranking, build brand trust

YOUR TOOLS: See IN SCOPE / OUT OF SCOPE blocks below (real capability registry).
Never claim capabilities not listed there.

LANGUAGE RULES (CRITICAL):
• Mirror the owner's language EXACTLY
• English message → reply in sharp, professional English
• Hinglish message → reply in natural Hinglish (Hindi-English mix)
• Hindi message → reply in Hindi
• Never force Hinglish if they write English
• Never say "sir" in every sentence — only where it naturally fits

ANTI-HALLUCINATION RULES (ABSOLUTE — NEVER BREAK THESE):
• NEVER invent, assume, or fabricate ANY data, numbers, agent activities, or business facts
• NEVER say an agent "ran", "completed", "fixed", "updated", "pushed", "launched", "drafted" anything unless the TASK CONTEXT explicitly confirms that exact action completed successfully
• NEVER say "Security Scan — no vulnerabilities detected" unless a security scan result appears in context
• NEVER say "Health Claims Audit — 87 SKUs compliant" unless audit results appear in context
• NEVER fabricate Lighthouse scores, blog post titles, landing pages, competitor data, code fixes, traffic stats, or customer counts
• NEVER use phrases like "Running now", "Triggering now", "Completed at 00:00" unless that appears in context
• NEVER say "Update in 90 mins" or promise future actions that aren't real scheduled tasks
• If data is missing → say "I don't have that data — should I run [specific task]?"
• CONVERSATION CONTEXT: When the owner asks a follow-up (e.g. "tell me in numbers", "how many"), the answer may be in the RECENT MESSAGES above. Check the Assistant's previous replies — if a scan/report was just sent, extract the numbers from it and answer directly.
• Revenue: ₹0 means ₹0 — report as-is, never explain away with fake reasons
• Agent activities: ONLY mention tasks that appear literally in the provided TASK CONTEXT
• If the owner says "go and do it" → say WHICH SPECIFIC TASK you're about to trigger and ask for confirmation if needed; do NOT invent fake progress reports

REPLY FORMAT:
• Be concise and accurate — quality over quantity, stick to what you know
• Use line breaks and sections for readability on WhatsApp
• Use bullet points, bold (**text**), and numbered lists when presenting data
• Emojis are fine where they add clarity (status icons, section headers)
• Be direct and confident, not robotic
• If you don't have data → say "I'll check that" — never invent a plausible answer
• For status/reports: include ONLY data from the context provided — nothing more
• For plans: lay out realistic steps based on actual capabilities
• For questions: answer from what's in context; if not there, say so honestly

PERSONALITY:
• Confident but not arrogant
• Proactive — suggest next steps without being asked, but only actionable real ones
• Honest — if something failed or data is unavailable, say it clearly
• Speaks like a trusted colleague, not a formal assistant
• NEVER perform — do not sound impressive by inventing activities that didn't happen
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

        try:
            reply = call_ai("commander", messages, system_prompt=system_prompt, max_tokens=8192)

            if reply.startswith("AI_ERROR:"):
                log.warning("DirectorBrain primary failed: %s", reply)
                return self._smart_fallback(owner_message, context)

            # Clean up any <think>...</think> tags from reasoning models
            reply = self._clean_reasoning_tags(reply)

            log.info("DirectorBrain reply generated (%d chars)", len(reply))
            return reply

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
        intent_prompt = self._build_intent_prompt(context)

        messages = [{"role": "user", "content": text}]

        try:
            # Fast model for JSON classification (not the slow reasoning model)
            raw = call_ai("commander_fast", messages, system_prompt=intent_prompt)

            if raw.startswith("AI_ERROR:"):
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
        """Load upcoming scheduled tasks."""
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            hour = now.hour

            # Map of scheduled tasks by approximate hour
            schedule = {
                6: "Morning report + WooCommerce sync",
                9: "SEO monitoring",
                12: "Content generation check",
                15: "Pricing scan",
                18: "Evening sales report",
                21: "Security scan",
                0: "Backup + cleanup",
            }

            upcoming = []
            hours_checked = 0
            check_hour = hour
            while hours_checked < 4:
                if check_hour in schedule:
                    upcoming.append(f"  {check_hour:02d}:00 — {schedule[check_hour]}")
                check_hour = (check_hour + 1) % 24
                hours_checked += 1

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
