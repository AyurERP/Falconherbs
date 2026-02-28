import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import re
from core.woocommerce_connector import WooCommerceConnector

def md_to_html(text: str) -> str:
    if not text: return ""
    # Bold
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)
    # Paragraphs
    if "<p>" not in text.lower():
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        text = "\n".join([f"<p>{p.replace('\n', '<br />')}</p>" for p in paragraphs])
    return text.strip()

def clean_desc(text: str):
    if not text: return "", ""
    
    # Extract keywords
    keywords = ""
    kw_match = re.search(r"(?i)(?:\*\*|###|#)?\s*SEO Keywords\s*(?:Naturally Integrated)?\s*[:：]?(.*?)(?:\n\n|\n---|\n\*\*\*|$)", text, flags=re.DOTALL)
    if kw_match:
        keywords = kw_match.group(1).strip().replace("\n", " ")
        keywords = keywords.replace("**", "").replace("__", "").replace("*", "").strip()
        keywords = re.sub(r"^[*,:\s-]+", "", keywords).strip()
        text = re.sub(r"(?i)(?:\n)?(?:\*\*|###|#)?\s*SEO Keywords.*?(?:\n\n|\n---|\n\*\*\*|$)", "", text, flags=re.DOTALL)

    # Remove AI filler from start
    filler_patterns = ["certainly", "here is", "here's", "i have", "rewritten", "optimized", "compliant", "version below"]
    lines = text.split("\n")
    start_idx = 0
    for i, line in enumerate(lines[:12]):
        l_line = line.lower().strip()
        if not l_line: continue
        if any(p in l_line for p in filler_patterns) or "---" in line or line.strip() == "###":
            continue
        start_idx = i
        break
    text = "\n".join(lines[start_idx:]).strip()

    # Remove trailing commentary
    commentary_keywords = ["this version", "this rewrite", "this description", "let me know", "hope this", "it invites", "matched packaging"]
    lines = text.split("\n")
    if len(lines) > 3:
        for i in range(len(lines)-1, max(0, len(lines)-5), -1):
            l_line = lines[i].lower()
            if any(k in l_line for k in commentary_keywords):
                lines = lines[:i]
                break
    text = "\n".join(lines).strip()

    # MD to HTML
    text = md_to_html(text)
    
    # Strip any remaining artifacts
    text = text.strip().strip('"').strip("'")
    if text.startswith("---"): text = text[3:].strip()
    if text.endswith("---"): text = text[:-3].strip()
    
    return text.strip(), keywords

def global_live_fix():
    woo = WooCommerceConnector()
    print("🚀 STARTING GLOBAL LIVE SCAN & FIX...")
    
    res = woo.get_all_products(save=False)
    if not res.get("success"):
        print(f"❌ Error: {res.get('error')}")
        return

    products = res["data"].get("products", [])
    fixed_count = 0
    
    for p in products:
        pid = p.get("id")
        name = p.get("name")
        desc = p.get("description", "")
        
        # Check if needs fix
        needs_fix = False
        if "**" in desc or "*" in desc or "Certainly" in desc or "SEO Keywords" in desc:
            needs_fix = True
            
        if needs_fix:
            print(f"  🛠️ Fixing product {name} (ID: {pid})...")
            new_desc, kw = clean_desc(desc)
            
            update_data = {"description": new_desc}
            if kw:
                update_data["meta_data"] = [
                    {"key": "_rank_math_focus_keyword", "value": kw}
                ]
            
            ures = woo.update_product(pid, update_data)
            if ures.get("success"):
                print(f"    ✅ Fixed!")
                fixed_count += 1
            else:
                print(f"    ❌ Failed: {ures.get('error')}")

    print(f"\n✨ GLOBAL CLEANUP COMPLETE! Fixed {fixed_count} products.")

if __name__ == "__main__":
    global_live_fix()
