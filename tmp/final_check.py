import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from core.woocommerce_connector import WooCommerceConnector

def final_check():
    woo = WooCommerceConnector()
    # IDs to check
    ids = [7800, 7803, 7676, 7527] # Triphala, Tulsi, Paan Masala, etc.
    
    print("FINAL RAW CONTENT CHECK (LIVE SITE)")
    print("="*60)
    
    for pid in ids:
        try:
            res = woo._make_request(f"products/{pid}")
            if res.get("success"):
                item = res["data"]
                name = item.get("name")
                desc = item.get("description", "")
                print(f"\n[ID: {pid}] NAME: {name}")
                print("-" * 20)
                print(desc)
                print("-" * 20)
                
                # Verify
                errors = []
                if "**" in desc: errors.append("Raw Markdown Bold (**) found")
                if "Certainly!" in desc: errors.append("AI Filler found")
                if "SEO Keywords" in desc: errors.append("SEO Keyword block found")
                if "<p>" not in desc: errors.append("Missing HTML Paragraphs")
                
                if not errors:
                    print("✅ CLEAN & FORMATTED")
                else:
                    print(f"❌ ISSUES: {', '.join(errors)}")
        except Exception as e:
            print(f"Error checking {pid}: {e}")

if __name__ == "__main__":
    final_check()
