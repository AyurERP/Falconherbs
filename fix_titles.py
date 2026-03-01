import sys
sys.path.append('.')
from core.integration_bridge import IntegrationBridge
import re
import json
from concurrent.futures import ThreadPoolExecutor

bridge = IntegrationBridge()
woo = bridge.tools.get('woocommerce')
ai = bridge.tools.get('ai_client')

violators = []
with open('claims_output.txt', 'r', encoding='utf-8') as f:
    for line in f:
        m = re.match(r'ID (\d+): (.*?) \(Claims:', line)
        if m:
            violators.append((int(m.group(1)), m.group(2).strip()))

print(f'Fixing {len(violators)} titles via AI...')

def fix_title(item):
    pid, old_name = item
    prompt = (
        f"Rewrite this Ayurvedic shop product title. "
        f"1. Remove ALL health claims, body parts, cures, or benefits (e.g. immunity, hair growth, digestion, sugar control). "
        f"2. Keep it simple: Just the Plant/Herb Name + Weight (e.g., '100gm') + 'Powder' or 'Whole' or 'Raw Herb'. "
        f"3. Return ONLY the new title. No conversational text.\n"
        f"Original: {old_name}"
    )
    
    clean_name = ai.generate(prompt)
    if clean_name:
        clean_name = clean_name.strip().replace('**', '').replace('"', '').replace('---', '').strip()
        print(f'{pid}: {old_name} -> {clean_name}')
        res = woo.update_product(pid, {'name': clean_name})
        return 1 if res.get('success') else 0
    return 0

with ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(fix_title, violators)
    total_fixed = sum(results)
    
print(f'Successfully updated {total_fixed} titles.')
