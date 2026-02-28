#!/usr/bin/env python3
"""
Server Check — falconherbs.com hosting diagnostics.
Tests: site reachability, cPanel API, WHM API.

Usage:
  python scripts/server_check.py

Requires in .env:
  - Site: WOO_SITE_URL or falconherbs.com
  - cPanel: CPANEL_USERNAME, CPANEL_API_TOKEN, CPANEL_DOMAIN (or FALCONHERBS_CPANEL_*)
  - WHM (optional): WHM_URL, WHM_USER, WHM_PASSWORD
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main():
    from dotenv import load_dotenv
    load_dotenv()

    site = os.getenv("WOO_SITE_URL", "https://falconherbs.com")
    if not site.startswith("http"):
        site = f"https://{site}"

    print("=" * 55)
    print("FALCONHERBS — SERVER CHECK")
    print("=" * 55)

    # 1. Site reachability
    print("\n1. SITE REACHABILITY")
    try:
        import urllib.request
        req = urllib.request.Request(site, headers={"User-Agent": "FalconServerCheck/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            code = r.status
            print(f"   {site}")
            print(f"   HTTP {code} — {'OK' if code < 500 else 'ERROR'}")
    except Exception as e:
        print(f"   FAIL: {e}")

    # 2. cPanel API
    print("\n2. CPANEL API")
    from core.cpanel_connector import cpanel
    if not cpanel._configured:
        print("   SKIP: FALCONHERBS_CPANEL_* not set in .env")
    else:
        # Just check connectivity via a simple call (optional, cpanel class doesn't have a check_conn yet)
        res = cpanel._execute("Fileman", "list_files", {"dir": "public_html", "limit": 1})
        if res.get("status"):
            print(f"   {cpanel.url} — OK")
        else:
            print(f"   {cpanel.url} — FAILED: {res.get('errors')}")

    # 3. WHM API
    print("\n3. WHM API")
    whm_url = os.getenv("WHM_URL", "")  # e.g. https://server-ip:2087
    whm_user = os.getenv("WHM_USER", "")
    whm_pass = os.getenv("WHM_PASSWORD", "")

    if not whm_url or not whm_user or not whm_pass:
        print("   SKIP: WHM_URL, WHM_USER, WHM_PASSWORD not set in .env")
        print("   Add for WHM check:")
        print("     WHM_URL=https://your-server-ip:2087")
        print("     WHM_USER=root")
        print("     WHM_PASSWORD=your_whm_password")
    else:
        try:
            import requests
            # WHM uses remote_user in query
            r = requests.get(
                f"{whm_url.rstrip('/')}/json-api/version",
                auth=(whm_user, whm_pass),
                timeout=15,
                verify=False,  # WHM often has self-signed cert
            )
            if r.status_code == 200:
                data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                version = data.get("version", "?")
                print(f"   {whm_url} — OK")
                print(f"   WHM version: {version}")
            else:
                print(f"   HTTP {r.status_code} — {r.text[:100] if r.text else 'no body'}")
        except requests.exceptions.SSLError as e:
            print(f"   SSL Error (try verify=False): {str(e)[:80]}")
        except requests.exceptions.ConnectTimeout:
            print(f"   Timeout — check WHM port 2087, firewall")
        except Exception as e:
            print(f"   FAIL: {e}")

    print("\n" + "=" * 55)
    print("If cPanel/WHM fails: check firewall allows 2083, 2087")
    print("=" * 55)

if __name__ == "__main__":
    main()
