import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.woocommerce_connector import WooCommerceConnector
import re

def verify_all():
    woo = WooCommerceConnector()
    res = woo.get_all_products(save=False)
    products = res['data']['products']
    
    markdown_count = 0
    filler_count = 0
    keywords_count = 0
    commentary_count = 0
    
    for p in products:
        desc = p.get('description', '')
        pid = p['id']
        name = p['name']
        
        if "**" in desc:
            print(f"❌ Markdown in {pid}: {name}")
            markdown_count += 1
            
        if any(f in desc.lower() for f in ["certainly!", "here is", "here's a", "rewritten version"]):
            print(f"❌ AI Filler in {pid}: {name}")
            filler_count += 1
            
        if "SEO Keywords" in desc:
            print(f"❌ Keywords block in {pid}: {name}")
            keywords_count += 1

        if "This version enhances" in desc or "emotional resonance" in desc:
            print(f"❌ Commentary in {pid}: {name}")
            commentary_count += 1

    print("\n" + "="*30)
    print(f"AUDIT SUMMARY (All {len(products)} products)")
    print(f"Markdown Leaks: {markdown_count}")
    print(f"AI Filler Leaks: {filler_count}")
    print(f"SEO Keyword Leaks: {keywords_count}")
    print(f"AI Commentary Leaks: {commentary_count}")
    print("="*30)

if __name__ == "__main__":
    verify_all()
