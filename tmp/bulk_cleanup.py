import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import re
from datetime import datetime
from core.woocommerce_connector import WooCommerceConnector

def extract_and_clean(text: str):
    """
    1. Extract SEO Keywords
    2. Remove Keywords section
    3. Remove trailing AI commentary
    4. Strip conversational filler
    """
    if not text:
        return "", ""
    
    # Extract keywords
    keywords = ""
    kw_match = re.search(r"(?i)(?:\*\*|###|#)?\s*SEO Keywords\s*(?:Naturally Integrated)?\s*[:：]?(.*?)(?:\n\n|\n---|\n\*\*\*|$)", text, flags=re.DOTALL)
    if kw_match:
        keywords = kw_match.group(1).strip().replace("\n", " ")
        # Remove keywords section from text
        text = re.sub(r"(?i)(?:\n)?(?:\*\*|###|#)?\s*SEO Keywords.*?(?:\n\n|\n---|\n\*\*\*|$)", "", text, flags=re.DOTALL)

    # Remove trailing commentary
    commentary_keywords = ["this version", "this rewrite", "this description", "let me know", "hope this", "it invites", "matched packaging"]
    lines = text.split("\n")
    if len(lines) > 3:
        # Check last 4 lines for commentary
        for i in range(len(lines)-1, max(0, len(lines)-5), -1):
            l_line = lines[i].lower()
            if any(k in l_line for k in commentary_keywords):
                lines = lines[:i]
                break
    text = "\n".join(lines).strip()

    # Strip conversational filler from START
    filler_patterns = ["certainly", "here is", "here's", "i have", "rewritten", "optimized", "compliant", "version below"]
    lines = text.split("\n")
    start_idx = 0
    for i, line in enumerate(lines[:10]):
        l_line = line.lower().strip()
        if not l_line: continue
        if any(p in l_line for p in filler_patterns) or "---" in line:
            continue
        start_idx = i
        break
    text = "\n".join(lines[start_idx:]).strip()

    # Clean surrounding markup
    text = text.strip().strip('"').strip("'").strip("`").strip()
    if text.startswith("---"): text = text[3:].strip()
    if text.endswith("---"): text = text[:-3].strip()
    
    return text.strip(), keywords

def bulk_cleanup():
    woo = WooCommerceConnector()
    rewrites_dir = Path("data/content/product_rewrites")
    
    print(f"Starting Robust Bulk Cleanup in {rewrites_dir}...")
    
    files = list(rewrites_dir.glob("*.json"))
    for f_path in files:
        if f_path.name in ["last_scan.json", "blog_scan.json", "page_scan.json"]:
            continue
            
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            changed = False
            extracted_kw = ""
            
            if "rewritten_description" in data and data["rewritten_description"]:
                old_desc = data["rewritten_description"]
                new_desc, kw = extract_and_clean(old_desc)
                if new_desc != old_desc or kw:
                    data["rewritten_description"] = new_desc
                    if kw:
                        data["rewritten_keywords"] = kw
                        extracted_kw = kw
                    changed = True
                    print(f"  ✨ Cleaned {f_path.name}")

            if changed:
                with open(f_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Push live if status is applied
                if data.get("status") == "applied":
                    pid = data.get("product_id")
                    if pid:
                        print(f"  🚀 Pushing live fix for Product {pid}...")
                        update_fields = {
                            "description": data["rewritten_description"]
                        }
                        if extracted_kw:
                            update_fields["meta_data"] = [
                                {
                                    "key": "_rank_math_focus_keyword",
                                    "value": extracted_kw
                                }
                            ]
                        woo.update_product(pid, update_fields)

        except Exception as e:
            print(f"  ❌ Error processing {f_path.name}: {e}")

    print("Cleanup Complete.")

if __name__ == "__main__":
    bulk_cleanup()
