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

# NVIDIA Multi-Model Setup
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Model assignments
AI_MODELS = {
    "commander": "meta/llama-3.1-8b-instruct",
    "director": "deepseek-ai/deepseek-v3.1",
    "developer": "meta/llama-3.3-70b-instruct",
    "media": "qwen/qwq-32b",
    "content": "qwen/qwen3-next-80b-a3b-instruct",
    "content_fallback": "meta/llama-3.3-70b-instruct",
    "fallback": "meta/llama-3.1-8b-instruct"
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