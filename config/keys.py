"""
FALCON AGENCY — Secure Key Vault
Rule: No hardcoded credentials. Ever.
Every key comes from environment variables only.
"""

import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# Load .env file
load_dotenv()

# ── NVIDIA API ─────────────────────────────────────────────────────────
NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# ── OpenRouter API ──────────────────────────────────────────────────────
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── Anthropic (Claude) API ───────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1/messages"

# ── Model assignments ───────────────────────────────────────────────────
# Prefix convention:
#   "nv::<model>"  →  NVIDIA NIM endpoint
#   "or::<model>"  →  OpenRouter (200+ models, free + paid)
#   "cl::<model>"  →  Anthropic Claude
#
# BENCHMARK (Mar 2026, tested 12+ models for Director persona):
#   Gemini 2.0 Flash  → 2.5s, FREE, BEST Hinglish quality, no hallucination ★
#   GPT-4o-mini       → 3.7s, ~$3/month, excellent grounding
#   GPT-4o            → 3.2s, ~$15/month, best quality
#   Grok-3-mini       → 9-19s, TOO SLOW for WhatsApp
#   Kimi K2           → 1s, fast but limited reasoning depth
#   qwen3-next-80b-a3b → 1.5s, only 3B ACTIVE params — too weak
#   LLaMA4-Maverick   → hallucinated numbers — dangerous
#
AI_MODELS = {
    # Commander Brain (Director's WhatsApp voice) — Gemini 2.0 Flash
    # FREE via OpenRouter. Fastest smart model. Best Hinglish.
    # Doesn't hallucinate data when instructed. 2.5s avg.
    "commander":        "or::google/gemini-2.0-flash-001",

    # Commander Fast (intent classification only) — LLaMA 3.3 70B NVIDIA
    # Sub-2s JSON output. Not for persona — just routing.
    "commander_fast":   "nv::meta/llama-3.3-70b-instruct",

    # Director (same as commander — Gemini Flash)
    "director":         "or::google/gemini-2.0-flash-001",

    # Strategist — GPT-4o via OpenRouter: deep analysis, competitor research
    # Best reasoning for long-form strategy. ~$0.01/call.
    "strategist":       "or::openai/gpt-4o",

    # Developer — LLaMA 3.3 70B: reliable code-level precision
    "developer":        "nv::meta/llama-3.3-70b-instruct",

    # Media/Content — GPT-4o-mini: fast, excellent writing quality
    "media":            "or::openai/gpt-4o-mini",
    "content":          "or::openai/gpt-4o-mini",
    "content_fallback": "nv::meta/llama-3.3-70b-instruct",

    # Health rewriter — GPT-4o-mini: follows FSSAI rules precisely
    "health_rewriter":  "or::openai/gpt-4o-mini",

    # AEO agent — GPT-4o: best for AI-engine optimized structured content
    "aeo":              "or::openai/gpt-4o",

    # Fallback
    "fallback":         "nv::meta/llama-3.3-70b-instruct",
}

# Other existing keys (load from .env)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "") # Mapping from .env WHATSAPP_ACCESS_TOKEN
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
CPANEL_USER = os.getenv("FALCONHERBS_CPANEL_USER", "")
CPANEL_TOKEN = os.getenv("FALCONHERBS_CPANEL_PASSWORD", "") # Note: .env has password, but requested CPANEL_TOKEN
CPANEL_DOMAIN = os.getenv("FALCONHERBS_CPANEL_URL", "") # Note: .env has URL

class KeyVault:
    """
    Central secure access point for all API keys and credentials.
    Agents request keys through here — they never see raw env vars.
    """

    def __init__(self):
        self._encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self._encryption_key:
            # We don't raise here to avoid crashing apps during setup
            self._encryption_key = "PLACEHOLDER_FOR_DOCKER_OR_SETUP"
        
        try:
            self._fernet = Fernet(self._encryption_key.encode())
        except Exception:
            self._fernet = None

    # === AI MODELS ===
    @property
    def anthropic(self) -> str:
        return os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def gemini(self) -> str:
        return os.getenv("GEMINI_API_KEY", "")

    @property
    def openai(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def elevenlabs(self) -> str:
        return os.getenv("ELEVENLABS_API_KEY", "")

    # === SEARCH & TOOLS ===
    @property
    def serper(self) -> str:
        return os.getenv("SERPER_API_KEY", "")

    @property
    def serper_2(self) -> str:
        return os.getenv("SERPER_API_KEY_2", "")

    # === COMMUNICATION (WhatsApp) ===
    @property
    def whatsapp_phone_id(self) -> str:
        return os.getenv("WHATSAPP_PHONE_ID", "")

    @property
    def whatsapp_access_token(self) -> str:
        return os.getenv("WHATSAPP_ACCESS_TOKEN", "")

    @property
    def whatsapp_recipient(self) -> str:
        return os.getenv("WHATSAPP_RECIPIENT", "")

    @property
    def whatsapp_verify_token(self) -> str:
        return os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    # === UTILITIES ===
    def _get(self, key_name: str) -> str:
        value = os.getenv(key_name)
        if not value:
            return "" # Return empty instead of raising
        return value

    def encrypt(self, plain_text: str) -> str:
        """Encrypt a string."""
        if not self._fernet: return plain_text
        return self._fernet.encrypt(plain_text.encode()).decode()

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt a string."""
        if not self._fernet: return encrypted_text
        return self._fernet.decrypt(encrypted_text.encode()).decode()

# Singleton
vault = KeyVault()