#!/usr/bin/env python3
"""Run health scan and print report (for VPS or local)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.integration_bridge import IntegrationBridge

def main():
    b = IntegrationBridge()
    r = b.run_health_scan(max_pages=100)
    if not r.get("success"):
        print("FAILED:", r.get("error", ""))
        return 1

    rep = r.get("full_report", {})
    pf = len(rep.get("products_fixable", []))
    tf = len(rep.get("titles_fixable", []))
    ba = len(rep.get("blogs_advisory", []))
    pa = len(rep.get("pages_advisory", []))
    ca = len(rep.get("categories_advisory", []))

    print("=" * 60)
    print("HEALTH CLAIMS AUDIT: falconherbs.com")
    print("=" * 60)
    vb = r.get("violations_breakdown", {})
    tv = r.get("total_violations", 0)
    print("TOTAL VIOLATIONS:", tv, "(HIGH:", vb.get("high",0), "| MED:", vb.get("medium",0), "| LOW:", vb.get("low",0), ")")
    print("PRODUCTS:", r.get("total", 0), "total |", pf, "desc violations |", tf, "title violations |", r.get("clean", 0), "clean")
    print("BLOGS:", ba, "flagged")
    print("PAGES:", pa, "flagged")
    print("CATEGORIES:", ca, "flagged")
    print()
    print("TOP PRODUCT VIOLATIONS (by risk score):")
    for v in sorted(rep.get("products_fixable", []), key=lambda x: x.get("risk_score", 0), reverse=True)[:15]:
        print("  -", v.get("name", "")[:65])
        if v.get("high"):
            print("    HIGH:", v["high"][0][:70])
    print()
    print("PRODUCT TITLE VIOLATIONS:")
    for t in rep.get("titles_fixable", [])[:10]:
        print("  -", t.get("name", "")[:65])
    print()
    print("BLOG VIOLATIONS:")
    for b in rep.get("blogs_advisory", [])[:10]:
        print("  -", b.get("title", "")[:65])
    print()
    print("PAGE VIOLATIONS:")
    for p in rep.get("pages_advisory", [])[:5]:
        print("  -", p.get("title", "")[:65])
    print()
    print("CATEGORY RENAMES NEEDED:")
    for c in rep.get("categories_advisory", []):
        print("  -", c.get("name", ""), "->", c.get("suggestion", ""))
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
