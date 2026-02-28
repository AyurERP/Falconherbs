#!/usr/bin/env python3
"""
FALCON AGENCY — Server & Site Diagnostic
========================================

Site down? Plugin update crash? Run this to diagnose.
Uses: HTTP check, WHM API (if configured), common fixes.

Usage:
  python scripts/server_diagnose.py

.env needs:
  - WOO_SITE_URL or falconherbs.com
  - WHM_URL, WHM_USER, WHM_PASSWORD (for WHM actions)
  - CPANEL_* (optional, for cPanel check)
"""

import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

SITE = os.getenv("WOO_SITE_URL", "https://falconherbs.com")
if not SITE.startswith("http"):
    SITE = f"https://{SITE}"


def http_check(url: str, timeout: int = 15) -> dict:
    """Check URL — returns status, code, error."""
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "FalconDiagnose/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "code": r.status, "url": url}
    except urllib.error.HTTPError as e:
        return {"ok": False, "code": e.code, "error": str(e), "url": url}
    except urllib.error.URLError as e:
        return {"ok": False, "error": str(e.reason)[:150], "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150], "url": url}


def whm_api(cmd: str, params: dict = None) -> dict:
    """Call WHM JSON API. Returns {ok, data, error}."""
    url = os.getenv("WHM_URL", "").rstrip("/")
    user = os.getenv("WHM_USER", "")
    passwd = os.getenv("WHM_PASSWORD", "")

    if not all([url, user, passwd]):
        return {"ok": False, "error": "WHM_URL, WHM_USER, WHM_PASSWORD not set in .env"}

    try:
        import requests
        import urllib.parse
        full_url = f"{url}/json-api/{cmd}"
        if params:
            qs = urllib.parse.urlencode(params)
            full_url += "?" + qs

        r = requests.get(
            full_url,
            auth=(user, passwd),
            timeout=20,
            verify=False,
        )
        if r.status_code == 200:
            data = r.json() if "json" in r.headers.get("content-type", "") else {}
            return {"ok": True, "data": data}
        return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}


def main():
    print("=" * 60)
    print("  FALCON AGENCY — Server & Site Diagnostic")
    print("  (Plugin update crash? Site unreachable?)")
    print("=" * 60)

    # 1. Site reachability
    print("\n--- 1. SITE REACHABILITY ---")
    for path in ["/", "/wp-admin/", "/wp-json/"]:
        r = http_check(SITE.rstrip("/") + path)
        status = "OK" if r.get("ok") else "FAIL"
        code = r.get("code", "?")
        err = r.get("error", "")
        print(f"   {path or '/'}: {status} (HTTP {code})" + (f" — {err}" if err else ""))

    # 2. WHM status
    print("\n--- 2. WHM SERVER ---")
    v = whm_api("version")
    if v.get("ok"):
        ver = v.get("data", {}).get("version", "?")
        print(f"   WHM: OK (version {ver})")
    else:
        print(f"   WHM: {v.get('error', '?')}")
        print("   Add WHM_URL, WHM_USER, WHM_PASSWORD to .env for server actions")

    # 3. WHM — list accounts (confirm site account exists)
    if v.get("ok"):
        accts = whm_api("listaccts")
        if accts.get("ok"):
            data = accts.get("data", {})
            acct_list = data.get("acct", []) if isinstance(data.get("acct"), list) else []
            domain = SITE.split("//")[-1].split("/")[0].split(":")[0]
            found = [a for a in acct_list if domain in str(a.get("domain", ""))]
            if found:
                print(f"   Account: {found[0].get('user', '?')} ({found[0].get('domain', '')})")
            else:
                print(f"   Account: {domain} not in listaccts (may be addon/subdomain)")

    # 4. Common plugin-update crash causes
    print("\n--- 3. COMMON FIXES (plugin update crash) ---")
    print("""
   Plugin update ke baad site down ho jana — common causes:

   A) PHP Fatal Error / Memory
      - WHM: Restart Services > Apache (or PHP-FPM)
      - Ya SSH: /usr/local/cpanel/scripts/restartsrv apache
      - PHP memory_limit badhao (wp-config.php ya .htaccess)

   B) Corrupted .htaccess
      - cPanel File Manager: public_html/.htaccess rename karo .htaccess.bak
      - Site check karo — agar up ho jaye to .htaccess restore karke fix karo

   C) Plugin conflict
      - wp-content/plugins/ folder rename karo (e.g. plugins_off)
      - Site check — agar up ho jaye to plugins one-by-one wapas karo

   D) MySQL down
      - WHM: Restart Services > MySQL
      - Ya SSH: /usr/local/cpanel/scripts/restartsrv mysql

   E) Disk full
      - WHM: Check disk usage
      - cPanel: Backup > Download — purane backups delete karo
""")

    # 5. Restart Apache via WHM (if user wants)
    print("\n--- 4. RESTART APACHE (optional) ---")
    if v.get("ok"):
        print("   WHM connected. Run: python scripts/server_diagnose.py --restart-apache")
        print("   (Ya manually: WHM > Restart Services > Apache)")
    else:
        print("   WHM not configured. Add credentials to .env for restart.")

    # 6. Director alert cooldown
    print("\n--- 5. DIRECTOR ALERT SPAM ---")
    print("""
   Site bar unreachable ho rahi hai to Director har 10 min alert bhejta hai.
   Maintenance ke time pe reduce karne ke liye .env mein add karo:

   MUTE_SITE_ALERTS=1
   (Director site-down alerts temporarily band karega)

   Ya cooldown badhao: SITE_ALERT_COOLDOWN_MIN=30
""")

    # 7. --restart-apache flag
    if "--restart-apache" in sys.argv and v.get("ok"):
        print("\n--- RESTARTING APACHE ---")
        restart = whm_api("restartservice", {"service": "httpd"})
        if not restart.get("ok"):
            restart = whm_api("restartservice", {"service": "apache"})
        if restart.get("ok"):
            out = restart.get("data", {}).get("output", "")
            print("   Apache restart sent. Wait 30-60 sec, then check site.")
            if out:
                print(f"   Output: {out[:200]}...")
        else:
            print(f"   Restart failed: {restart.get('error')}")
            print("   Manual: WHM > Restart Services > Apache")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
