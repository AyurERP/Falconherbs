import subprocess
import base64
import sys

remote_code = """
import sqlite3
import json
import sys
conn = sqlite3.connect('/home/ubuntu/falcon-agency/data/falcon.db')
cursor = conn.cursor()
cursor.execute("SELECT id, action, details FROM action_log WHERE action IN ('whatsapp_send', 'approval_request_sent') ORDER BY id DESC LIMIT 20")
rows = cursor.fetchall()
output = []
for row in rows:
    output.append({"id": row[0], "action": row[1], "details": json.loads(row[2])})
sys.stdout.buffer.write(json.dumps(output, ensure_ascii=False).encode('utf-8'))
"""
b64_code = base64.b64encode(remote_code.encode()).decode()

ssh_cmd = [
    'ssh', '-i', 'ssh-key-2026-02-21.key', '-o', 'StrictHostKeyChecking=no', 'ubuntu@140.245.246.190',
    f"python3 -c \"exec(__import__('base64').b64decode('{b64_code}'))\""
]

res = subprocess.run(ssh_cmd, capture_output=True)
with open("tmp/db_out.json", "wb") as f:
    f.write(res.stdout)
print("Saved to tmp/db_out.json")
