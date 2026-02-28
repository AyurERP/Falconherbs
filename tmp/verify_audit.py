import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import random
import json
import re
from core.woocommerce_connector import WooCommerceConnector

def run_audit():
    woo = WooCommerceConnector()
    print("Connecting to live WooCommerce API for Verification Audit...")
    
    # Get all products (to pick random 5)
    res = woo.get_all_products(save=False)
    if not res.get("success"):
        print(f"❌ API Error: {res.get('error')}")
        return

    products = res["data"].get("products", [])
    if not products:
        print("❌ No products found.")
        return

    # Pick 5 random products
    audit_batch = random.sample(products, min(5, len(products)))
    
    audit_results = []
    
    ai_filler = ["certainly", "here is", "here's", "i have", "rewritten", "optimized", "compliant"]
    
    print(f"\n🚀 AUDITING {len(audit_batch)} RANDOM LIVE PRODUCTS\n" + "="*50)
    
    for p in audit_batch:
        pid = p.get("id")
        name = p.get("name")
        desc = p.get("description", "")
        
        # 1. Check for Markdown
        has_markdown = "**" in desc or (re.search(r"[^\w]\*[^\w]", desc) is not None)
        
        # 2. Check for AI Filler
        has_filler = any(f in desc.lower() for f in ai_filler)
        
        # 3. Check for HTML
        has_html = desc.strip().startswith("<p>") or "<strong>" in desc or "<em>" in desc
        
        # 4. Check for SEO Keyword Section
        has_keywords = "SEO Keywords" in desc or "keywords integrated" in desc.lower()
        
        status = "✅ PASS"
        issues = []
        if has_markdown: issues.append("Markdown symbols found")
        if has_filler: issues.append("AI conversational filler found")
        if not has_html: issues.append("Missing proper HTML formatting")
        if has_keywords: issues.append("SEO Keywords visible in text")
        
        if issues:
            status = "❌ FAIL: " + ", ".join(issues)
            
        print(f"\n📦 PRODUCT: {name} (ID: {pid})")
        print(f"Status: {status}")
        print("-"*30)
        # Show first 200 chars of live desc
        print(f"Live Description Preview:\n{desc[:400].strip()}...")
        print("-"*30)
        
        audit_results.append({
            "id": pid,
            "name": name,
            "status": status,
            "issues": issues
        })

    print("\n" + "="*50)
    print("AUDIT COMPLETE.")

if __name__ == "__main__":
    run_audit()
