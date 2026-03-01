import subprocess
import time

SSH_CMD = [
    "ssh",
    "-i", "ssh-key-2026-02-21.key",
    "-o", "StrictHostKeyChecking=no",
    "ubuntu@140.245.246.190"
]

def run_test_and_get_logs(test_name, payload):
    print(f"\n======================================")
    print(f"RUNNING TEST: {test_name}")
    print(f"======================================")
    
    # Send curl
    curl_cmd = f"curl -s -X POST http://localhost:8000/webhook -H 'Content-Type: application/json' -d '{payload}'"
    subprocess.run(SSH_CMD + [curl_cmd])
    
    print(f"Waiting for response processing...")
    # Wait appropriate time based on test
    if 'health scan' in payload or 'draft blog' in payload:
        time.sleep(120)
    elif 'run chanakya' in payload:
        time.sleep(60)
    else:
        time.sleep(30)
        
    print(f"Fetching logs...")
    log_cmd = "journalctl -u falcon.service --since '5 minutes ago' --no-pager"
    result = subprocess.run(SSH_CMD + [log_cmd], capture_output=True, text=True)
    
    # Clean output slightly
    lines = result.stdout.split('\n')
    filtered = []
    for line in lines:
        if "complete  |  scheduled" in line: continue
        filtered.append(line)
        
    print("\nLOGS (Last 50 lines):")
    for line in filtered[-50:]:
        print(line)

import time as t
now = int(t.time())

tests = [
    {
        "name": "Test 1: status",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_001", "timestamp": "{now}", "text": {{"body": "status"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    },
    {
        "name": "Test 2: health scan",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_002", "timestamp": "{now+10}", "text": {{"body": "health scan"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    },
    {
        "name": "Test 3: chanakya triggers",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_003", "timestamp": "{now+20}", "text": {{"body": "run chanakya triggers"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    },
    {
        "name": "Test 4: sab fix karo",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_004", "timestamp": "{now+30}", "text": {{"body": "sab fix karo"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    },
    {
        "name": "Test 5: draft blog on tulsi benefits",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_005", "timestamp": "{now+40}", "text": {{"body": "draft blog on tulsi benefits"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    }
]

# Run just the FIRST one for now to verify.
run_test_and_get_logs(tests[0]['name'], tests[0]['payload'])
