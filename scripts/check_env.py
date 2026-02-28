#!/usr/bin/env python3
"""
Check which .env keys Falcon Agency needs and which are set.
Does NOT print values — only key names and status.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv()

# All keys Falcon Agency uses (from codebase scan)
REQUIRED_FOR_CORE = [
    "WHATSAPP_PHONE_ID",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_RECIPIENT",
    "NVIDIA_API_KEY",  # or OPENROUTER for AI
    "FALCONHERBS_WC_API_KEY",
    "FALCONHERBS_WC_API_SECRET",
]

REQUIRED_FOR_BLOG_FIXES = [
    "FALCONHERBS_WP_USER",
    "FALCONHERBS_WP_APP_PASSWORD",  # WP Application Password (Users → Profile → App Passwords)
]

OPTIONAL = [
    "FALCONHERBS_WP_PASSWORD",      # Fallback if WP_APP_PASSWORD not set
    "GSC_SERVICE_ACCOUNT_JSON",    # Google Search Console — for SEO reports
    "GA4_PROPERTY_ID",             # Google Analytics 4
    "SERPER_API_KEY",              # AEO scan, search
    "GEMINI_API_KEY",              # Content/Media agent
    "CPANEL_USERNAME",
    "CPANEL_API_TOKEN",
    "FTP_HOST", "FTP_USER", "FTP_PASS",
    "META_ACCESS_TOKEN",
]

def check(key: str) -> bool:
    val = os.getenv(key, "")
    if isinstance(val, str):
        return bool(val.strip())
    return bool(val)

def main():
    print("=" * 55)
    print("  FALCON AGENCY — .env Key Check")
    print("  (Values NOT shown — security)")
    print("=" * 55)

    print("\n--- CORE (WhatsApp + WooCommerce + AI) ---")
    for k in REQUIRED_FOR_CORE:
        ok = check(k)
        print(f"  {'OK' if ok else 'MISSING':8} {k}")

    print("\n--- BLOG FIXES (sab fix karo -> blogs) ---")
    for k in REQUIRED_FOR_BLOG_FIXES:
        ok = check(k)
        print(f"  {'OK' if ok else 'MISSING':8} {k}")

    wp_ok = check("FALCONHERBS_WP_APP_PASSWORD") or check("FALCONHERBS_WP_PASSWORD")
    wp_val = os.getenv("FALCONHERBS_WP_APP_PASSWORD", "") or os.getenv("FALCONHERBS_WP_PASSWORD", "")
    if not wp_ok:
        print("  --> Add FALCONHERBS_WP_APP_PASSWORD (WP Users > Profile > Application Passwords)")
    elif len(wp_val) < 16:
        print("  --> App password may be truncated! In .env use quotes: FALCONHERBS_WP_APP_PASSWORD=\"xxxx xxxx xxxx xxxx\"")

    print("\n--- OPTIONAL (SEO, GSC, Backup, etc.) ---")
    for k in OPTIONAL:
        ok = check(k)
        print(f"  {'OK' if ok else '-':8} {k}")

    print("\n--- SEO REPORTS ---")
    gsc = check("GSC_SERVICE_ACCOUNT_JSON")
    print(f"  {'OK' if gsc else 'MISSING':8} GSC_SERVICE_ACCOUNT_JSON -> monthly SEO data")
    print("  --> Weekly SEO digest runs Mondays (content + product health)")
    print("  --> Say 'seo audit' or 'full seo' for on-demand report")

    print("\n" + "=" * 55)


if __name__ == "__main__":
    main()
