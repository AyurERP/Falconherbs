import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import os
from datetime import datetime
from core.woocommerce_connector import WooCommerceConnector

def clean_ai_markup(text: str) -> str:
    """Helper to strip AI conversational junk."""
    if not text:
        return ""
    
    # 1. Strip common conversational prefixes until first --- or **
    lines = text.split("\n")
    cleaned_lines = []
    skip_header = True
    
    # We strip until we find a header or rule, BUT only if the first few lines are filler
    filler_patterns = [
        "certainly", "here is", "here's", "i have", "rewritten", 
        "optimized", "compliant", "this version", "version below",
        "refined", "seo-optimized"
    ]
    
    found_content = False
    for i, line in enumerate(lines[:12]):
        l_line = line.lower().strip()
        if not l_line: continue
        
        # If we hit a Horizontal Rule or a bold header at the start of a line
        if ("---" in line or (line.strip().startswith("**") and "Powder" in line or "100" in line)):
            # If it's just "---", skip it and everything above it
            if line.strip() == "---" or line.strip() == "---":
                cleaned_lines = lines[i+1:]
            else:
                cleaned_lines = lines[i:]
            found_content = True
            break
            
        if any(p in l_line for p in filler_patterns):
            continue
            
        # If no rule found but we have a non-filler line
        cleaned_lines = lines[i:]
        found_content = True
        break
        
    if not found_content:
        cleaned_lines = lines

    cleaned = "\n".join(cleaned_lines).strip()
    
    # 2. Strip trailing filler (e.g. "Let me know if you need anything else")
    # Search from bottom
    final_lines = cleaned.split("\n")
    for i in range(len(final_lines)-1, max(0, len(final_lines)-5), -1):
        l_line = final_lines[i].lower()
        if any(p in l_line for p in ["let me know", "this version", "seo keywords integrated", "compliant language"]):
            # If it's a trailing meta-commentary, strip it
            if "keywords" in l_line or "compliant" in l_line:
                # Keep keywords if they are part of the description? 
                # User usually wants them in WP, but let's be safe.
                # Actually, let's just strip conversational meta-talk.
                pass
            if "let me know" in l_line or "hope this" in l_line:
                final_lines = final_lines[:i]
    
    cleaned = "\n".join(final_lines).strip()
    cleaned = cleaned.strip('"').strip("'").strip("`").strip()
    
    if cleaned.startswith("---"): cleaned = cleaned[3:].strip()
    if cleaned.endswith("---"): cleaned = cleaned[:-3].strip()
    
    return cleaned.strip()

def bulk_cleanup():
    woo = WooCommerceConnector()
    rewrites_dir = Path("data/content/product_rewrites")
    
    print(f"Starting Bulk Cleanup in {rewrites_dir}...")
    
    files = list(rewrites_dir.glob("*.json"))
    for f_path in files:
        if f_path.name == "last_scan.json" or f_path.name == "blog_scan.json" or f_path.name == "page_scan.json":
            continue
            
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            changed = False
            
            # 1. Clean description
            if "rewritten_description" in data and data["rewritten_description"]:
                old = data["rewritten_description"]
                new = clean_ai_markup(old)
                if new != old:
                    print(f"  ✨ Cleaned description for {f_path.name}")
                    data["rewritten_description"] = new
                    changed = True
            
            # 2. Clean title
            if "rewritten_title" in data and data["rewritten_title"]:
                old = data["rewritten_title"]
                new = clean_ai_markup(old)
                if new != old:
                    print(f"  ✨ Cleaned title for {f_path.name}")
                    data["rewritten_title"] = new
                    changed = True

            # 3. Clean name (for products)
            if "rewritten_name" in data and data["rewritten_name"]:
                old = data["rewritten_name"]
                new = clean_ai_markup(old)
                if new != old:
                    print(f"  ✨ Cleaned name for {f_path.name}")
                    data["rewritten_name"] = new
                    changed = True
            
            if changed:
                # Save locally
                with open(f_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # If already applied, push fix to live site
                if data.get("status") == "applied":
                    item_id = data.get("product_id") or data.get("post_id") or data.get("page_id")
                    if item_id:
                        print(f"  🚀 Pushing live fix for ID {item_id}...")
                        update_fields = {}
                        if data.get("rewritten_description"):
                            update_fields["description"] = data["rewritten_description"]
                        if data.get("rewritten_title"):
                            update_fields["title"] = data["rewritten_title"]
                        if data.get("rewritten_name"):
                            update_fields["name"] = data["rewritten_name"]
                            
                        # Determine if product or post
                        if "product_id" in data:
                            woo.update_product(item_id, update_fields)
                        else:
                            woo.update_post(item_id, update_fields)

        except Exception as e:
            print(f"  ❌ Error processing {f_path.name}: {e}")

    print("Bulk Cleanup Complete.")

if __name__ == "__main__":
    bulk_cleanup()
