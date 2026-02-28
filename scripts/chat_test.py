#!/usr/bin/env python3
"""One-shot chat test: send 'health scan' to Director and print response."""

import sys
# Windows: UTF-8 for Hinglish/Unicode
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for d in ["data", "data/goals", "data/content", "data/health_audit", "config/profiles"]:
    (ROOT / d).mkdir(parents=True, exist_ok=True)

from core.console_whatsapp import ConsoleWhatsApp
from core.director import Director


def main():
    print("Booting Director (console mode)...")
    wa = ConsoleWhatsApp()
    director = Director(whatsapp_client=wa)
    if not director._commander:
        print("ERROR: Commander init failed")
        sys.exit(1)

    # Full flow: scan -> fix -> results
    msgs = ["health scan", "sab fix karo", "haan karo", "changelog"]
    for i, msg in enumerate(msgs):
        print(f"\n>>> Sending: {msg}\n")
        director._commander.handle_message(msg, f"test_{i+1}", "owner")

    print("\n>>> Done.\n")


if __name__ == "__main__":
    main()
