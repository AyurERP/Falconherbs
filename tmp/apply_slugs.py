import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.woocommerce_connector import WooCommerceConnector
import json

def apply_fixes():
    woo = WooCommerceConnector()
    print("Applying Slug Fixes & Generating Redirects...")
    
    with open("tmp/slug_fix_preview.json", "r", encoding="utf-8") as f:
        flagged = json.load(f)
        
    redirects = []
    
    # Process Name issue first
    print("\nFixing Name for ID 7510...")
    res = woo.update_product(7510, {
        "name": "Turmeric Powder 100g - Traditional Ayurvedic Herb"
    })
    if res.get("success"):
        print("✅ ID 7510 Name Updated!")
    else:
        print(f"❌ Failed to update ID 7510 Name: {res.get('error')}")

    # Process Slugs
    print("\nUpdating Slugs...")
    for item in flagged:
        pid = item['id']
        new_slug = item['new_slug']
        old_slug = item['old_slug']
        
        # Don't try to update if old and new are the same
        if new_slug == old_slug:
            continue
            
        print(f"  🔄 Updating ID {pid}: /{old_slug} -> /{new_slug}")
        ures = woo.update_product(pid, {"slug": new_slug})
        if ures.get("success"):
            print("    ✅ Success!")
            redirects.append({
                "source": f"/{old_slug}",
                "target": f"/{new_slug}",
                "type": 301
            })
        else:
            print(f"    ❌ Failed: {ures.get('error')}")
            
    # Write redirects file
    with open("tmp/301_redirects.csv", "w", encoding="utf-8") as f:
        f.write("source,url\n")
        f.write("~^old_slug/?$,new_slug\n")
        f.write("# Import this format into Rank Math > Redirections\n")
        for r in redirects:
            f.write(f"{r['source']},{r['target']}\n")
            
    print("\n" + "="*50)
    print(f"✅ APPLIED {len(redirects)} SLUGS.")
    print("📁 301 Redirects saved to tmp/301_redirects.csv")
    print("   Upload this file to Rank Math Redirections importer in WordPress.")
    
if __name__ == "__main__":
    apply_fixes()
