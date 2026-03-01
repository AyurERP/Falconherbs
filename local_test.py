import os
import sys
import time
import json
import asyncio
from datetime import datetime

# Setup paths
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Force local mode environment
os.environ["FALCON_LOCAL_MODE"] = "1"
os.environ["PYTHONUTF8"] = "1"

# Import mock first to ensure it patches before anything else
import core.whatsapp_mock as mock_wa
sys.modules['core.whatsapp'] = mock_wa

from core.commander import FalconCommander
from core.director_brain import DirectorBrain
from core.whatsapp import WhatsAppNotifier

# Initialize prerequisites
director = DirectorBrain()
whatsapp = WhatsAppNotifier()

# Initialize commander
commander = FalconCommander(director=director, whatsapp=whatsapp)

# Color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

def simulate_message(text, msg_id=None, context_id=None):
    if not msg_id:
        msg_id = f"test_{int(time.time() * 1000)}"
        
    print(f"\n{GREEN}{'#'*60}")
    print(f"🚀 SIMULATING INCOMING: {text}")
    print(f"{'#'*60}{RESET}")
    
    # Clear previous mock messages
    mock_wa.clear_mock_log()
    
    start_timestamp = time.time()
    start_time_iso = datetime.now().isoformat()
    
    try:
        # Process message
        commander.handle_message(text, message_id=msg_id, sender="919916322917", context_message_id=context_id)
            
        # Wait logic for background processing
        wait_for = 15 
        responses = []
        
        for _ in range(wait_for // 3):
            time.sleep(3)
            responses = mock_wa.get_logs_since(start_time_iso)
            # If we got a real response (not just the timeout warning), we can stop early
            if any("analyze kar raha hoon" not in r["text"].lower() and "working on it" not in r["text"].lower() for r in responses):
                break
                
        end_time = time.time()
        elapsed = end_time - start_timestamp
        
        msg_count = len(responses)
        msg_texts = [r["text"] for r in responses]
        
        print(f"\n{YELLOW}⏱️  Response time: {elapsed:.2f}s")
        print(f"📤 Messages sent: {msg_count}")
        
        if msg_count > 0:
            for i, msg in enumerate(msg_texts, 1):
                print(f"  {i}. {msg[:80]}...")
            
            return {
                "input": text,
                "msg_id": msg_id,
                "response_time": elapsed,
                "messages_sent": msg_count,
                "messages": msg_texts,
                "status": "PASSED"
            }
        else:
            print(f"{RED}⚠️  NO RESPONSE SENT — potential hang or crash!{RESET}")
            return {
                "input": text,
                "msg_id": msg_id,
                "response_time": elapsed,
                "messages_sent": 0,
                "messages": [],
                "status": "FAILED"
            }
    except Exception as e:
        print(f"{RED}❌ CRASHED: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return {
            "input": text,
            "error": str(e),
            "status": "CRASHED"
        }

def run_all_tests():
    # Regular tests
    tests = [
        ("Test 1: Status Check", "status"),
        ("Test 6: Fix Violations Batch", "fix violations batch 3"),
        ("Test 7: Rewrite Status", "rewrite status"),
    ]
    
    results = []
    for name, text in tests:
        print(f"\n{CYAN}RUNNING: {name}{RESET}")
        res = simulate_message(text)
        res["test"] = name
        results.append(res)
    
    # Test 8: Context Memory (Sequential)
    print(f"\n{CYAN}RUNNING: Test 8: Context Memory (Sequential){RESET}")
    # Part A: Ask about violations
    res_a = simulate_message("fix violations batch 1")
    time.sleep(2)
    # Part B: Approve via context
    res_b = simulate_message("approve all")
    res_b["test"] = "Test 8: Context Memory"
    results.append(res_b)
    
    # Test 9: Quote Reply (Simulated)
    print(f"\n{CYAN}RUNNING: Test 9: Quote Reply Simulation{RESET}")
    # Get last bot msg id from previous test
    mock_log = mock_wa.get_mock_log()
    last_bot_id = None
    for msg in reversed(mock_log):
        if msg.get("id"):
            last_bot_id = msg["id"]
            break
            
    # For now, we'll just simulate a reply-to the last bot message
    res_d = simulate_message("Apply this one", context_id=last_bot_id)
    res_d["test"] = "Test 9: Quote Reply"
    results.append(res_d)
        
    with open("data/test_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\n{GREEN}{'='*60}")
    print(f"✅ ALL TESTS COMPLETE")
    print(f"Results saved to data/test_results.json")
    print(f"{'='*60}{RESET}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        simulate_message(sys.argv[1])
    else:
        run_all_tests()
