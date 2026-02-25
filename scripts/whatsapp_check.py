#!/usr/bin/env python3
"""
WhatsApp Webhook Troubleshooter — Run on VPS to diagnose "msgs nahi aa rahe".

Usage: python scripts/whatsapp_check.py
"""
import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    print("=" * 50)
    print("FALCON AGENCY — WhatsApp Check")
    print("=" * 50)

    # 1. .env
    from dotenv import load_dotenv
    load_dotenv()
    phone_id = os.getenv("WHATSAPP_PHONE_ID", "")
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    recipient = os.getenv("WHATSAPP_RECIPIENT", "")
    verify = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    print("\n1. ENV VARS")
    print("   WHATSAPP_PHONE_ID:", "OK" if phone_id else "MISSING")
    print("   WHATSAPP_ACCESS_TOKEN:", "OK" if token else "MISSING")
    print("   WHATSAPP_RECIPIENT:", recipient or "MISSING")
    print("   WHATSAPP_VERIFY_TOKEN:", "OK" if verify else "MISSING")

    # 2. Webhook reachable
    print("\n2. WEBHOOK REACHABLE (local)")
    try:
        import requests
        r = requests.get("http://127.0.0.1:8000/health", timeout=3)
        print("   /health:", r.status_code, r.json().get("status", "?") if r.ok else "FAIL")
    except Exception as e:
        print("   /health: NOT REACHABLE —", str(e)[:60])
        print("   -> Is main.py running? Start: python main.py")

    # 3. Verify endpoint
    try:
        r = requests.get(
            f"http://127.0.0.1:8000/webhook?hub.mode=subscribe&hub.verify_token={verify}&hub.challenge=123",
            timeout=3
        )
        if r.text == "123":
            print("   /webhook verify: OK")
        else:
            print("   /webhook verify: FAIL (expected 123, got)", r.text[:50])
    except Exception as e:
        print("   /webhook verify: NOT REACHABLE")

    # 4. Meta config reminder
    print("\n3. META DASHBOARD CHECK")
    print("   - Webhook URL: https://YOUR-DOMAIN/webhook")
    print("   - Verify Token must match WHATSAPP_VERIFY_TOKEN")
    print("   - Subscribe: messages")
    print("   - If VPS IP: ensure nginx proxies :80 -> :8000")

    # 5. Phone format
    print("\n4. PHONE FORMAT")
    digits = "".join(c for c in str(recipient) if c.isdigit())
    print("   Recipient (digits):", digits)
    if len(digits) == 12 and digits.startswith("91"):
        print("   Format: OK (91 + 10 digits)")
    elif len(digits) == 10:
        print("   Format: Add 91 prefix -> 91" + digits)
    else:
        print("   Format: Use 91XXXXXXXXXX (no +)")

    print("\n" + "=" * 50)
    print("If msgs still nahi aa rahe: check VPS logs when you send a msg")
    print("  tail -f logs/*.log  OR  journalctl -u falcon_agency -f")
    print("=" * 50)

if __name__ == "__main__":
    main()
