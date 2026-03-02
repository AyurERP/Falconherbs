"""Quick WHM API check — fetch all accounts and disk usage."""
import os, sys, requests, json
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

WHM_URL  = os.getenv("WHM_URL", "").rstrip("/")
WHM_USER = os.getenv("WHM_USER", "")
WHM_PASS = os.getenv("WHM_PASSWORD", "")

def whm(func, **params):
    url = f"{WHM_URL}/json-api/{func}"
    params["api.version"] = 1
    try:
        r = requests.get(url, params=params,
                         auth=(WHM_USER, WHM_PASS),
                         verify=False, timeout=20)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

print(f"Connecting to {WHM_URL} as {WHM_USER}...\n")

# 1. Server version
v = whm("version")
ver = v.get("version", v.get("error","?"))
print(f"WHM Version: {ver}")

# 2. List all accounts
print("\n--- ALL ACCOUNTS ---")
accts = whm("listaccts", searchtype="domain", search="")
data = accts.get("data", {})
accounts = data.get("acct", [])
print(f"Total accounts: {len(accounts)}")
print()

# Sort by disk used
accounts_sorted = sorted(
    accounts,
    key=lambda a: float(a.get("diskused","0").replace("M","").replace("G","000").replace("k","0.001") or 0),
    reverse=True
)

for i, a in enumerate(accounts_sorted, 1):
    user     = a.get("user","?")
    domain   = a.get("domain","?")
    plan     = a.get("plan","?")
    disk     = a.get("diskused","?")
    quota    = a.get("disklimit","unlimited")
    suspended = a.get("suspended", False)
    status   = "🔴 SUSPENDED" if suspended else "🟢 active"
    print(f"{i:2}. {status}  {domain} ({user})")
    print(f"    Disk: {disk} / {quota}  |  Plan: {plan}")

# Summary
suspended_count = sum(1 for a in accounts if a.get("suspended"))
empty_domains = [a for a in accounts if float((a.get("diskused","0").replace("M","").replace("G","000").replace("k","0") or "0").split()[0] if " " not in a.get("diskused","0") else "0") < 5]
print(f"\nTotal: {len(accounts)} | Active: {len(accounts)-suspended_count} | Suspended: {suspended_count}")
print(f"Very small (<5M used, possibly empty): {len(empty_domains)}")
for a in empty_domains:
    print(f"  → {a.get('domain')} — disk: {a.get('diskused','?')}")

# Save full data
out = Path("tmp/whm_accounts.json")
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(accounts, indent=2, default=str))
print(f"\nFull data saved: {out}")
