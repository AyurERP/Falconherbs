"""
FALCON AGENCY — Secure Key Vault
Rule: No hardcoded credentials. Ever.
Every key comes from environment variables only.
"""

import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

class KeyVault:
    """
    Central secure access point for all API keys and credentials.
    Agents request keys through here — they never see raw env vars.
    """

    def __init__(self):
        self._encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self._encryption_key:
            raise EnvironmentError(
                "ENCRYPTION_KEY not found in .env — "
                "run: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                " and paste the result into your .env"
            )
        self._fernet = Fernet(self._encryption_key.encode())

    # === AI MODELS ===
    @property
    def anthropic(self) -> str:
        return self._get("ANTHROPIC_API_KEY")

    @property
    def openai(self) -> str:
        return self._get("OPENAI_API_KEY")

    @property
    def gemini(self) -> str:
        return self._get("GEMINI_API_KEY")

    @property
    def elevenlabs(self) -> str:
        return self._get("ELEVENLABS_API_KEY")

    # === COMMUNICATION ===
    @property
    def telegram_token(self) -> str:
        return self._get("TELEGRAM_BOT_TOKEN")

    @property
    def telegram_chat_id(self) -> str:
        return self._get("TELEGRAM_CHAT_ID")

    # === UTILITIES ===
    def _get(self, key_name: str) -> str:
        value = os.getenv(key_name)
        if not value:
            raise EnvironmentError(
                f"Missing required key: '{key_name}' — add it to your .env file"
            )
        return value

    def encrypt(self, plain_text: str) -> str:
        """Encrypt a string (for storing sensitive site passwords)."""
        return self._fernet.encrypt(plain_text.encode()).decode()

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt a stored encrypted string."""
        return self._fernet.decrypt(encrypted_text.encode()).decode()


# Singleton — import this everywhere
vault = KeyVault()