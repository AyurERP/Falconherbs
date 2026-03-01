# core/whatsapp_mock.py
"""
Mock WhatsApp sender for local testing.
Instead of sending real WhatsApp messages, prints to console with formatting.
"""

import json
from datetime import datetime

# Color codes for terminal
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Log file for all mock messages
MOCK_LOG = "data/mock_whatsapp_log.json"

_mock_messages = []

def get_mock_log():
    return _mock_messages

def get_logs_since(timestamp_iso):
    """Returns mock messages that occurred after the given ISO timestamp"""
    return [m for m in _mock_messages if m["timestamp"] >= timestamp_iso]

def clear_mock_log():
    global _mock_messages
    _mock_messages = []

class WhatsAppNotifier:
    def __init__(self, phone_id=None, token=None, recipient=None):
        self.recipient_phone = recipient or "owner"

    def send_message(self, text: str, recipient: str = None):
        """Mock WhatsApp send — prints to console and logs to file"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n{GREEN}{'='*60}")
        print(f"📱 WhatsApp Message @ {timestamp}")
        print(f"{'='*60}{RESET}")
        print(f"{CYAN}{text}{RESET}")
        print(f"{GREEN}{'='*60}{RESET}\n")
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "recipient": recipient or self.recipient_phone,
            "text": text,
            "length": len(text)
        }
        _mock_messages.append(entry)
        
        # Append to log file
        try:
            import os
            os.makedirs("data", exist_ok=True)
            existing = []
            if os.path.exists(MOCK_LOG):
                with open(MOCK_LOG, 'r') as f:
                    try:
                        existing = json.load(f)
                    except json.JSONDecodeError:
                        existing = []
            existing.append(entry)
            with open(MOCK_LOG, 'w') as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{YELLOW}⚠️ Log save failed: {e}{RESET}")
        
        return {"status": "mocked", "length": len(text)}

    def send_document(self, filepath: str, caption: str = "", recipient: str = None):
        """Mock WhatsApp document send"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n{YELLOW}{'='*60}")
        print(f"📎 WhatsApp Document @ {timestamp}")
        print(f"{'='*60}{RESET}")
        print(f"File: {filepath}")
        print(f"Caption: {caption}")
        print(f"{YELLOW}{'='*60}{RESET}\n")
        
        return {"status": "mocked", "filepath": filepath}

