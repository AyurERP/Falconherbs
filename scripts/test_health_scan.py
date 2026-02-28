#!/usr/bin/env python3
"""Quick test: run health scan and print totals for verification."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.integration_bridge import IntegrationBridge

def main():
    bridge = IntegrationBridge()
    print("Running health scan (this may take 30-60s)...")
    result = bridge.run_health_scan(max_pages=100)
    if not result.get("success"):
        print("ERROR:", result.get("error", "Unknown"))
        return 1

    r = result.get("full_report", {})
    total_products = result.get("total", 0)
    clean = result.get("clean", 0)
    pf = len(r.get("products_fixable", []))
    tf = len(r.get("titles_fixable", []))
    ba = len(r.get("blogs_advisory", []))
    pa = len(r.get("pages_advisory", []))
    ca = len(r.get("categories_advisory", []))

    # Total items scanned (products + blogs + pages + categories)
    # Products: each product counted once
    # Blogs/pages: we only have flagged in report; need total from API
    # For now: total_items = products + len(blogs we fetched) + len(pages) + len(cats)
    # The report only stores FLAGGED items for blogs/pages/cats
    # So we can't get "total blogs" from report - we'd need to change the scan
    total_items = total_products + ba + pa + ca  # This undercounts - we don't store total blogs/pages
    total_flagged = pf + tf + ba + pa + ca  # Overcounts if product has both desc+title violation

    print("\n" + "="*50)
    print("HEALTH SCAN RESULTS (for 204/53 verification)")
    print("="*50)
    print(f"Products:  total={total_products}  |  desc violations={pf}  |  title violations={tf}  |  clean={clean}")
    print(f"Blogs:     flagged={ba}")
    print(f"Pages:     flagged={pa}")
    print(f"Categories: flagged={ca}")
    print("---")
    print(f"TOTAL items (products only in scan): {total_products}")
    print(f"TOTAL flagged: products_desc={pf}, titles={tf}, blogs={ba}, pages={pa}, cats={ca}")
    print(f"  Sum of flagged: {pf}+{tf}+{ba}+{pa}+{ca} = {pf+tf+ba+pa+ca}")
    print("="*50)
    print(result.get("summary", "")[:800])
    return 0

if __name__ == "__main__":
    sys.exit(main())
