import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.woocommerce_connector import WooCommerceConnector
import re
import json

def get_weight(name, slug):
    weight_match = re.search(r'(\d+\s*(?:gm|g|kg|ml|l)\b)', name, re.I)
    if not weight_match:
        weight_match = re.search(r'(\d+(?:gm|g|kg|ml|l)\b)', slug, re.I)
        
    if weight_match:
        w = weight_match.group(1).lower().replace(" ", "")
        if w.endswith("gm"):
            w = w[:-2] + "g"
        return w
    
    return ""

def transform_slug(name, old_slug):
    # 1. Base name
    base_name = re.split(r'[|\-–—]', name)[0].strip()
    
    # 2. Extract weight
    weight = get_weight(name, old_slug)
    
    # Strip weight and units from base name to avoid duplication
    base_name = re.sub(r'\b(?:\d+\s*(?:g|gm|gms|kg|ml|l))\b', '', base_name, flags=re.I)
    base_name = re.sub(r'\b(?:gm|g|gms)\b', '', base_name, flags=re.I).strip()
    
    base_slug_part = re.sub(r'[^a-z0-9\s]', '', base_name.lower())
    base_slug_part = "-".join(base_slug_part.split())
    
    # 3. Determine Use Case from old slug or name
    full_text = f"{old_slug} {name.lower()}"
    
    use_case = ""
    
    # Category Mappings based on user input
    if any(k in full_text for k in ["immunity", "immune"]):
        use_case = "immunity-support"
    elif any(k in full_text for k in ["digest", "stomach", "appetite", "constipation"]):
        use_case = "digestive-wellness"
    elif any(k in full_text for k in ["stress", "memory", "nervous"]):
        use_case = "stress-support"
    elif any(k in full_text for k in ["respiratory", "cough"]):
        use_case = "respiratory-support"
    elif any(k in full_text for k in ["heart", "cardio", "lipid", "cholesterol", "blood sugar"]):
        use_case = "cardio-support"
    elif any(k in full_text for k in ["skin", "acne", "blemish", "wound"]):
        use_case = "skin-care"
    elif any(k in full_text for k in ["hair", "scalp"]):
        use_case = "hair-care"
    elif any(k in full_text for k in ["men's", "mens"]):
        use_case = "mens-wellness"
    elif any(k in full_text for k in ["liver", "kidney", "bladder"]):
        use_case = "liver-support"
    elif any(k in full_text for k in ["energy", "weakness"]):
        use_case = "traditional-energy"
    elif any(k in full_text for k in ["weight", "fat"]):
        use_case = "weight-management"
    elif any(k in full_text for k in ["bone", "joint"]):
        use_case = "bone-health"
    elif any(k in full_text for k in ["hormon", "women"]):
        use_case = "womens-wellness"
    elif any(k in full_text for k in ["detox", "cleanse"]):
        use_case = "traditional-wellness"
    else:
        use_case = "daily-wellness"
        
    # Construct new slug
    parts = [base_slug_part]
    if weight:
        parts.append(weight)
    parts.append(use_case)
    
    new_slug = "-".join(parts)
    new_slug = re.sub(r"-+", "-", new_slug).strip("-")
    
    return new_slug

def scan_slugs():
    woo = WooCommerceConnector()
    print("Fetching products to generate SEO-friendly slugs...")
    res = woo.get_all_products(save=False)
    
    if not res.get("success"):
        print(f"Error: {res.get('error')}")
        return

    products = res['data']['products']
    danger_keywords = ["detoxify", "cure", "treat", "heal", "remedy", "relief", "boost", "rejuvenate", "cleanse", "detox", "cancer", "disease"]
    
    flagged = []
    
    for p in products:
        slug = p.get('slug', '')
        pid = p.get('id')
        name = p.get('name')
        
        found = [kw for kw in danger_keywords if kw in slug.lower()]
        
        # Additionally flag slugs with 'booster' or missing weight but having claims
        if found or "booster" in slug.lower() or "medicine" in slug.lower():
            new_slug = transform_slug(name, slug)
            
            flagged.append({
                "id": pid,
                "name": name,
                "old_slug": slug,
                "new_slug": new_slug,
                "reason": found if found else ["booster/non-compliant format"]
            })

    print(f"\nAUDIT PREVIEW: {len(flagged)} products flagged for URL fix\n" + "-"*60)
    for item in flagged:
        print(f"📦 ID: {item['id']} | {item['name']}")
        print(f"   🔴 OLD: /{item['old_slug']}")
        print(f"   🟢 NEW: /{item['new_slug']}")
        print("-" * 60)

    with open("tmp/slug_fix_preview.json", "w", encoding="utf-8") as f:
        json.dump(flagged, f, indent=2)

if __name__ == "__main__":
    scan_slugs()
