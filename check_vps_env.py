import os
from dotenv import load_dotenv

load_dotenv()

vps_keys = [
    "VPS_IP",
    "VPS_HOST", 
    "VPS_USER",
    "VPS_USERNAME",
    "ORACLE_IP",
    "SERVER_IP",
    "SSH_USER",
    "SSH_HOST"
]

print("=== VPS CONFIG IN .ENV ===")
for key in vps_keys:
    val = os.getenv(key, "")
    if val:
        print(f"✅ {key}: {val}")
    
# Also check if any key contains "oracle" or "vps"
print("\n=== ALL POTENTIAL VPS KEYS ===")
with open(".env", "r") as f:
    for line in f:
        if "=" in line:
            if any(x in line.lower() for x in ["vps", "oracle", "ssh", "server", "host", "ip"]):
                # Print key name only, not value (security)
                key_name = line.split("=")[0].strip()
                print(f"Found: {key_name}")
