"""Fix the real HIGH violation products from health scan."""
import os, sys, re
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from core.woocommerce_connector import WooCommerceConnector

woo = WooCommerceConnector()

# --- FIX 1: P7651 Shikakai Powder - "hair treatment" → "hair care"
print("Fixing P7651 Shikakai Powder...")
r = woo._make_request('products/7651')
if r.get('success'):
    desc = r['data'].get('description', '')
    new_desc = re.sub(r'\bhair treatment\b', 'hair care', desc, flags=re.IGNORECASE)
    if new_desc != desc:
        upd = woo.update_product(7651, {'description': new_desc})
        print('  OK' if upd.get('success') else f'  FAIL: {upd.get("error")}')
    else:
        print('  No change needed')

# --- FIX 2: P7506 Shikakai Pods - "hair treatment" → "hair care"
print("Fixing P7506 Shikakai Pods...")
r = woo._make_request('products/7506')
if r.get('success'):
    desc = r['data'].get('description', '')
    new_desc = re.sub(r'\bhair treatment\b', 'hair care', desc, flags=re.IGNORECASE)
    if new_desc != desc:
        upd = woo.update_product(7506, {'description': new_desc})
        print('  OK' if upd.get('success') else f'  FAIL: {upd.get("error")}')
    else:
        print('  No change needed')

# --- FIX 3: P7211 Banafsha - fix "treatment" in desc + fix the disease-claim title
print("Fixing P7211 Banafsha (title + description)...")
r = woo._make_request('products/7211')
if r.get('success'):
    p = r['data']
    desc = p.get('description', '')
    # Replace "treatment" with "ritual" or "care" contextually
    new_desc = re.sub(r'\brejuvenating treatment\b', 'rejuvenating ritual', desc, flags=re.IGNORECASE)
    new_desc = re.sub(r'\btreatment\b', 'care ritual', new_desc, flags=re.IGNORECASE)

    # Fix the title - remove disease claims
    # OLD: "Banafsha - 30gms. Helpful for acne, pimple and respiratory problem"
    new_name = "Banafsha Leaves 30gm | Traditional Ayurvedic Herb for Wellness"

    upd = woo.update_product(7211, {
        'description': new_desc,
        'name': new_name
    })
    print('  Title + Desc OK' if upd.get('success') else f'  FAIL: {upd.get("error")}')

print("\nNote: Mouth fresheners (7709/7700/7659/7656) - 'treat' = 'a delightful treat for the senses'")
print("      These are FALSE POSITIVES. No fix needed.")
print("\nAll done.")
