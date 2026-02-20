"""
FALCON AGENCY — Safety Rules
This file defines what agents CAN and CANNOT do autonomously.
Think of it as the agency's constitution.
"""

from config.settings import settings, IS_PRODUCTION
from core.logger import log


class SafetyGuard:
    """
    Every agent checks with SafetyGuard before executing any action.
    It either approves autonomously or escalates to the human.
    """

    def requires_human_approval(self, action: str) -> bool:
        """Returns True if this action needs your Telegram approval."""
        needs_approval = action in settings.require_approval_for
        if needs_approval:
            log.warning(f"[SAFETY] Action '{action}' flagged — human approval required.")
        return needs_approval

    def is_safe_to_run(self, action: str, context: dict = None) -> bool:
        """
        Quick pre-flight check before any agent starts a task.
        Returns False if something looks wrong.
        """
        context = context or {}

        # Never run destructive actions in production without approval
        if IS_PRODUCTION and self.requires_human_approval(action):
            log.critical(
                f"[SAFETY BLOCK] '{action}' attempted in PRODUCTION without approval. BLOCKED."
            )
            return False

        # Log every action attempt regardless
        log.info(f"[SAFETY] Pre-flight OK for action: '{action}' | Context: {context}")
        return True

    def validate_file_path(self, path: str) -> bool:
        """Prevent path traversal attacks from agent-generated paths."""
        dangerous = ["..", "//", "/etc", "/root", "~", "passwd", "shadow"]
        for pattern in dangerous:
            if pattern in path:
                log.critical(f"[SAFETY] Dangerous path blocked: '{path}'")
                return False
        return True

    def validate_url(self, url: str) -> bool:
        """Basic URL safety check before any agent makes external requests."""
        allowed_protocols = ["https://"]
        if not any(url.startswith(p) for p in allowed_protocols):
            log.warning(f"[SAFETY] Non-HTTPS URL blocked: '{url}'")
            return False
        return True


# Singleton
guard = SafetyGuard()