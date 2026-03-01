import subprocess
import time
import sys

SSH_CMD = [
    "ssh",
    "-i", "ssh-key-2026-02-21.key",
    "-o", "StrictHostKeyChecking=no",
    "ubuntu@140.245.246.190"
]

def run_test_and_get_logs(test_name, payload, idx):
    print(f"\n======================================")
    print(f"RUNNING TEST: {test_name}")
    print(f"======================================")
    
    curl_cmd = f"curl -s -X POST http://localhost:8000/webhook -H 'Content-Type: application/json' -d '{payload}'"
    subprocess.run(SSH_CMD + [curl_cmd])
    
    print(f"Waiting for response processing...")
    if 'health scan' in payload or 'draft blog' in payload:
        time.sleep(120)
    elif 'run chanakya' in payload:
        time.sleep(60)
    else:
        time.sleep(30)
        
    print(f"Fetching logs...")
    log_cmd = "journalctl -u falcon.service --since '2 minutes ago' --no-pager"
    result = subprocess.run(SSH_CMD + [log_cmd], capture_output=True, text=True, errors='ignore')
    
    with open(f"tmp/logs{idx}.txt", "w", encoding="utf-8") as f:
        f.write(result.stdout.replace('\r', ''))
    print(f"Logs saved to tmp/logs{idx}.txt")

import time as t
now = int(t.time())

tests = [
    {
        "name": "Test 1: status",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_001_{now}", "timestamp": "{now}", "text": {{"body": "status"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    },
    {
        "name": "Test 2: health scan",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_002_{now}", "timestamp": "{now+10}", "text": {{"body": "health scan"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    },
    {
        "name": "Test 3: chanakya triggers",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_003_{now}", "timestamp": "{now+20}", "text": {{"body": "run chanakya triggers"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    },
    {
        "name": "Test 4: sab fix karo",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_004_{now}", "timestamp": "{now+30}", "text": {{"body": "sab fix karo"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    },
    {
        "name": "Test 5: draft blog on tulsi benefits",
        "payload": f'{{"object": "whatsapp_business_account", "entry": [{{"id": "BID", "changes": [{{"value": {{"messaging_product": "whatsapp", "metadata": {{"display_phone_number": "0000", "phone_number_id": "PID"}}, "messages": [{{"from": "919916322917", "id": "test_005_{now}", "timestamp": "{now+40}", "text": {{"body": "draft blog on tulsi benefits"}}, "type": "text"}}]}}, "field": "messages"}}]}}]}}'
    }
]

idx = int(sys.argv[1])
run_test_and_get_logs(tests[idx]['name'], tests[idx]['payload'], idx)
