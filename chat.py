#!/usr/bin/env python3
"""
FALCON AGENCY — CLI Chat Mode
=============================

Chat with Director via console (no WhatsApp). Same flow as WhatsApp:
you type, Director responds. Use for testing.

Usage:
    python chat.py

Examples:
    health scan
    sab fix karo
    haan karo
    status
"""

import sys

# Windows: ensure UTF-8 for Director's Hinglish/Unicode output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
import uuid
from pathlib import Path

# Ensure project root
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Create required dirs (same as main.py)
for d in ["data", "data/goals", "data/content", "data/health_audit", "config/profiles"]:
    (ROOT / d).mkdir(parents=True, exist_ok=True)

from core.console_whatsapp import ConsoleWhatsApp
from core.director import Director
from core.logger import log


def main():
    print("\n" + "=" * 55)
    print("  🦅 FALCON AGENCY — CLI Chat Mode")
    print("  Director ke saath baat karo (WhatsApp jaisa)")
    print("  Type 'quit' or 'exit' to stop.")
    print("=" * 55 + "\n")

    # Boot Director with console output
    wa = ConsoleWhatsApp()
    director = Director(whatsapp_client=wa)

    if not director._commander:
        log.critical("Commander init failed. Cannot chat.")
        sys.exit(1)

    commander = director._commander
    msg_counter = 0

    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye! 🦅")
            break

        if not text:
            continue
        if text.lower() in ("quit", "exit", "bye"):
            print("Bye! 🦅")
            break

        msg_counter += 1
        msg_id = f"chat_{msg_counter}_{uuid.uuid4().hex[:8]}"
        commander.handle_message(text, msg_id, user_id="owner")


if __name__ == "__main__":
    main()
