# local_mode.py
"""
Run this BEFORE starting the local server.
Patches WhatsApp module to use mock sender.

Usage:
    python local_mode.py          → Start local server with mock WhatsApp
    python local_mode.py test     → Run all 7 tests automatically
"""

import sys
import os

# Set local mode flag
os.environ["FALCON_LOCAL_MODE"] = "true"

# Monkey-patch whatsapp module BEFORE any other imports
import core.whatsapp_mock as mock_wa
sys.modules['core.whatsapp'] = mock_wa

# Now we can import the rest
print("🏠 Local mode active — WhatsApp messages will be printed to console")
print(f"📁 Working directory: {os.getcwd()}")
print(f"📝 Mock log: data/mock_whatsapp_log.json")
print()
