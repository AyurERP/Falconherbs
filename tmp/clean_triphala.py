import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from core.woocommerce_connector import WooCommerceConnector

def clean_triphala():
    woo = WooCommerceConnector()
    product_id = 7800
    
    # Read the JSON draft we generated
    json_path = Path("data/content/product_rewrites/7800.json")
    if not json_path.exists():
        print("JSON file not found.")
        return
        
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    raw_desc = data.get("rewritten_description", "")
    
    cleaned = raw_desc
    parts = cleaned.split("\n\n")
    if len(parts) > 1:
        # Check if the first part is a short AI filler sentence (conversational)
        first_part = parts[0].strip()
        if any(w in first_part for w in ["Certainly", "Here", "refined", "rewrite", "compliant"]):
            # If the next part is "---", skip it too
            start_idx = 1
            if len(parts) > 2 and "---" in parts[1]:
                start_idx = 2
            cleaned = "\n\n".join(parts[start_idx:])

    # Final trim
    cleaned = cleaned.strip()
    # Strip leading/trailing --- if any
    if cleaned.startswith("---"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("---"):
        cleaned = cleaned[:-3].strip()
    cleaned = cleaned.strip()
    
    # Also strip any trailing "This version..." or "SEO Keywords..." if they are outside the main body
    # (Optional, but let's keep it safe)
    
    print("Cleaned Description Preview:")
    print(cleaned[:200] + "...")
    
    # Push to WooCommerce
    print(f"Updating Product {product_id} with cleaned description...")
    res = woo.update_product(product_id, {"description": cleaned})
    
    if res.get("success"):
        print("✅ Live site cleaned!")
        # Update local JSON too
        data["rewritten_description"] = cleaned
        data["applied_at"] = "2026-03-01T01:20:00"
        data["status"] = "applied"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        print(f"❌ Failed: {res.get('error')}")

if __name__ == "__main__":
    clean_triphala()
