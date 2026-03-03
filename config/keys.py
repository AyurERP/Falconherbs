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

# ── DeepSeek Direct API ──────────────────────────────────────────────────
# Cheapest: $0.14/1M tokens input. Best coding model.
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ── Google Gemini Direct API ─────────────────────────────────────────────
# FREE: 1M tokens/day, 15 RPM. OpenAI-compatible endpoint.
# Much higher limits than OpenRouter shared tier (no 429s).
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

# ── HuggingFace Inference API ────────────────────────────────────────────
# Free serverless inference. Good for open-source models.
HUGGINGFACE_API_KEY  = os.getenv("HUGGINGFACE_API_KEY", "")
HUGGINGFACE_BASE_URL = "https://api-inference.huggingface.co/models"

# ── Perplexity Sonar (live web search) ───────────────────────────────────
# OpenAI-compatible. sonar-pro = real-time Google search in LLM.
PERPLEXITY_API_KEY  = os.getenv("PERPLEXITY_API_KEY", "")
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"

# ── GitHub Models (Azure AI — 100% FREE, 10 RPM) ─────────────────────────
# PATs are model-specific. Managed per-call in ai_client.py.
GITHUB_BASE_URL = "https://models.inference.ai.azure.com"

# ── Model assignments ───────────────────────────────────────────────────
# Prefix convention:
#   "gm::<model>"  →  Google Gemini DIRECT (FREE 1M TPD, 15 RPM, OpenAI-compat)
#   "or::<model>"  →  OpenRouter (200+ models, Gemini free tier, GPT-4o, etc.)
#   "gh::<model>"  →  GitHub Models (100% FREE Azure-hosted, GPT-4o, DeepSeek-V3)
#   "nv::<model>"  →  NVIDIA NIM (reliable paid fallback)
#   "ds::<model>"  →  DeepSeek Direct (best coder, needs paid balance)
#   "px::<model>"  →  Perplexity Sonar (live web search, AEO)
#   "cl::<model>"  →  Anthropic Claude (premium)
#
# VERIFIED WORKING (2026-03-03, tested from VPS):
#   or::google/gemini-2.0-flash-001  → 2.5s, FREE via OR, best Hinglish ★★★
#   gh::gpt-4o                       → 3.2s, 100% FREE Azure, excellent quality ★★★
#   gh::DeepSeek-V3                  → fast, FREE, best for coding ★★★
#   nv::meta/llama-3.3-70b-instruct  → reliable, ~$0.27/1M, NVIDIA ★★
#   gm::gemini-2.0-flash             → native FREE (resets daily, use as backup)
#   ds::deepseek-coder               → NO BALANCE (top up needed)
#   px::sonar-pro                    → no key configured (skip)
#
AI_MODELS = {
    # ── Commander / Director (WhatsApp voice) ───────────────────────────────
    # Gemini 2.0 Flash via OpenRouter: verified fastest, best Hinglish, FREE.
    # or:: uses OpenRouter's own Gemini access (separate from direct API quota).
    "commander":        "or::google/gemini-2.0-flash-001",
    "commander_fast":   "or::google/gemini-2.0-flash-001",
    "director":         "or::google/gemini-2.0-flash-001",

    # ── Strategist ──────────────────────────────────────────────────────────
    # GPT-4o via GitHub Models: 100% FREE, deep reasoning, no cost.
    "strategist":       "gh::gpt-4o",

    # ── Developer ───────────────────────────────────────────────────────────
    # DeepSeek-V3 via GitHub Models: 100% FREE, best for coding.
    # (Direct DeepSeek API has no balance — using GitHub Free tier instead)
    "developer":        "gh::DeepSeek-V3",
    "developer_fast":   "gh::gpt-4o",             # FREE GitHub fallback

    # ── Content / Media ─────────────────────────────────────────────────────
    # GPT-4o-mini via OpenRouter: fast writing, FSSAI-aware, cheap.
    # Falls back to gm:: (native Gemini) when OR is rate-limited.
    "media":            "or::openai/gpt-4o-mini",
    "content":          "or::openai/gpt-4o-mini",
    "content_fallback": "nv::meta/llama-3.3-70b-instruct",
    "health_rewriter":  "or::openai/gpt-4o-mini",

    # ── AEO Agent ────────────────────────────────────────────────────────────
    # Perplexity Sonar Pro: LIVE web search. Falls back to GPT-4o if no key.
    "aeo":              "px::sonar-pro",
    "aeo_fallback":     "or::openai/gpt-4o",

    # ── GitHub Models (FREE budget tier) ────────────────────────────────────
    "free_gpt4o":       "gh::gpt-4o",
    "free_phi4":        "gh::Phi-4",
    "free_deepseek":    "gh::DeepSeek-V3",
    "free_jamba":       "gh::jamba-1.5-large",

    # ── Fallback (NVIDIA NIM — always reliable) ──────────────────────────────
    "fallback":         "nv::meta/llama-3.3-70b-instruct",
}

# Other existing keys (load from .env)
# Note: GEMINI_API_KEY is now defined above in the provider section.
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