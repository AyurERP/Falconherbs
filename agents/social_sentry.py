import re
import logging
import yaml
from datetime import datetime
from pathlib import Path
from core.logger import log

# Set up logger
logger = logging.getLogger("SocialSentry")

class SocialSentry:
    """
    Compliance scanner for social media comments.
    Phase 1: Manual paste via WhatsApp
    Phase 2: Meta Graph API auto-scan (future)
    """

    def __init__(self, llm_caller=None, config_path="config/clients/falconherbs.yaml"):
        """
        Args:
            llm_caller: Function that takes (prompt, model) and returns string.
                        Matches your existing LLM call pattern.
            config_path: Path to the client YAML config.
        """
        self.llm_caller = llm_caller
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._compile_patterns()

    def _load_config(self):
        """Load compliance rules from YAML"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            else:
                log.warning(f"Config for SocialSentry not found at {self.config_path}")
                return {}
        except Exception as e:
            log.error(f"Error loading SocialSentry config: {e}")
            return {}

    def _compile_patterns(self):
        """Compile regex patterns from config"""
        comp = self.config.get("compliance", {})
        prohibited = comp.get("prohibited_terms", {})
        
        danger_patterns = prohibited.get("danger", [])
        caution_patterns = prohibited.get("caution", [])
        
        self._danger = [re.compile(p, re.IGNORECASE) for p in danger_patterns]
        self._caution = [re.compile(p, re.IGNORECASE) for p in caution_patterns]

    def analyze(self, comment_text: str) -> dict:
        """
        Main entry point. Matches your agent pattern:
        Commander extracts data -> calls agent method -> returns result dict.

        Args:
            comment_text: Raw comment string (EN/HI/Hinglish)

        Returns:
            dict with: risk, comment, matched_phrase, suggested_reply, timestamp
        """
        risk, matched = self._classify(comment_text)
        
        suggested_reply = None
        if risk in ("DANGER", "CAUTION") and self.llm_caller:
            suggested_reply = self._generate_reply(comment_text, risk)

        return {
            "risk": risk,
            "comment": comment_text,
            "matched_phrase": matched,
            "suggested_reply": suggested_reply,
            "timestamp": datetime.now().isoformat(),
            "action_needed": risk in ("DANGER", "CAUTION")
        }

    def _classify(self, text: str) -> tuple:
        """Returns (risk_level, matched_phrase)"""
        for pattern in self._danger:
            match = pattern.search(text)
            if match:
                logger.warning(f"DANGER detected: '{match.group()}' in comment")
                return ("DANGER", match.group())

        for pattern in self._caution:
            match = pattern.search(text)
            if match:
                logger.info(f"CAUTION detected: '{match.group()}' in comment")
                return ("CAUTION", match.group())

        return ("SAFE", None)

    def _generate_reply(self, comment: str, risk_level: str) -> str:
        """Uses Qwen model for natural response generation"""
        urgency = "CRITICAL" if risk_level == "DANGER" else "moderate"
        
        voice = self.config.get("brand_voice", {})
        tone = voice.get("tone", "warm, professional")
        role = voice.get("role", "Social Media Manager")
        disclaimer = self.config.get("compliance", {}).get("mandatory_disclaimer", "Individual experiences may vary.")

        prompt = f"""You are a {role}.
A customer left this comment that contains a {urgency} compliance risk.

Comment: "{comment}"

Write a warm reply that:
1. Thanks them genuinely for sharing their experience
2. Does NOT confirm or repeat any medical/health claim they made
3. Includes the phrase "{disclaimer}"
4. Mentions the products are "traditional Ayurvedic formulations"
5. If CRITICAL: Gently suggests consulting a healthcare professional
6. Sounds like a real person, not a legal department
7. Maximum 3 sentences
8. Works in the same language as the comment (Hindi reply for Hindi comment)"""

        # Model mapping: "qwen" corresponds to Qwen-Next 80B in our stack
        return self.llm_caller(prompt, "qwen")

    def format_whatsapp_alert(self, result: dict, source: str = "Manual Check") -> str:
        """Formats result for WhatsApp notification"""
        if result["risk"] == "SAFE":
            return f"✅ *SAFE* — No compliance risk detected.\n\n_{result['comment']}_"

        emoji = "🔴" if result["risk"] == "DANGER" else "🟡"
        
        alert = f"""{emoji} *COMPLIANCE {result['risk']}*
📍 Source: {source}

💬 *Comment:*
_{result['comment']}_

⚠️ *Flagged phrase:* `{result['matched_phrase']}`

✍️ *Suggested reply:*
{result['suggested_reply']}

*Actions:*
Reply *APPROVE* — Post this reply
Reply *EDIT* — Modify before posting  
Reply *IGNORE* — Skip this comment"""

        return alert
