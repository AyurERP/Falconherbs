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

    # 2. cPanel API (port 2083)
    print("\n2. CPANEL API (port 2083)")
    cpanel_user = os.getenv("CPANEL_USERNAME") or os.getenv("FALCONHERBS_CPANEL_USER", "")
    cpanel_token = os.getenv("CPANEL_API_TOKEN") or os.getenv("FALCONHERBS_CPANEL_PASSWORD", "")
    cpanel_domain = os.getenv("CPANEL_DOMAIN") or os.getenv("FALCONHERBS_CPANEL_URL", "falconherbs.com")
    cpanel_domain = cpanel_domain.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    cpanel_port = os.getenv("CPANEL_PORT", "2083")

    if not cpanel_user or not cpanel_token:
        print("   SKIP: CPANEL_USERNAME + CPANEL_API_TOKEN (or FALCONHERBS_CPANEL_*) not set")
    else:
        try:
            import requests
            base = f"https://{cpanel_domain}:{cpanel_port}"
            headers = {"Authorization": f"cpanel {cpanel_user}:{cpanel_token}"}
            # Simple API call — list accounts or version
            r = requests.get(
                f"{base}/execute/VersionControl/get_version",
                headers=headers,
                timeout=15,
                verify=True,
            )
            if r.status_code == 200:
                print(f"   {base} — OK (200)")
            else:
                # Try alternate — listaccts
                r2 = requests.get(
                    f"{base}/json-api/listaccts",
                    headers=headers,
                    timeout=15,
                    verify=True,
                )
                if r2.status_code == 200:
                    print(f"   {base} — OK (200)")
                else:
                    print(f"   {base} — HTTP {r.status_code} (may need API token from cPanel)")
        except requests.exceptions.SSLError as e:
            print(f"   SSL Error: {str(e)[:80]}")
        except requests.exceptions.ConnectTimeout:
            print(f"   Timeout — check firewall/port {cpanel_port}")
        except Exception as e:
            print(f"   FAIL: {e}")

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
