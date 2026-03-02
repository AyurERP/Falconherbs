"""
Bulk-add FSSAI disclaimer to all 87 live products that lack one.
Appends to existing description HTML — does NOT replace content.
"""
import sys, os, re, time
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from core.woocommerce_connector import WooCommerceConnector
from bs4 import BeautifulSoup

woo = WooCommerceConnector()

DISCLAIMER_HTML = (
    '\n<p><em>This product is not intended to diagnose, treat, cure, or prevent '
    'any condition. It is offered as a traditional herbal product for general '
    'wellness purposes. Consult a qualified healthcare professional before use.</em></p>'
)

DISC_CHECK = ['not intended to diagnose', 'these statements have not been evaluated']

def has_disclaimer(html_text):
    text = BeautifulSoup(html_text or '', 'html.parser').get_text(' ', strip=True).lower()
    return any(ph in text for ph in DISC_CHECK)

# Fetch all products
print("Fetching all products...")
products = []
page = 1
while True:
    r = woo._make_request('products', {'per_page': 100, 'page': page})
    batch = r.get('data', []) if r.get('success') else []
    if not batch:
        break
    products.extend(batch)
    if len(batch) < 100:
        break
    page += 1

print(f"Total: {len(products)} products\n")

ok = 0
skip = 0
fail = 0

for i, p in enumerate(products):
    pid = p['id']
    name = p['name'][:45]
    desc = p.get('description') or ''

    if has_disclaimer(desc):
        print(f"  SKIP P{pid} {name} (already has disclaimer)")
        skip += 1
        continue

    # Append disclaimer to existing description
    new_desc = desc.rstrip() + DISCLAIMER_HTML

    upd = woo.update_product(pid, {'description': new_desc})
    if upd.get('success'):
        print(f"  OK   P{pid} {name}")
        ok += 1
    else:
        print(f"  FAIL P{pid} {name}: {upd.get('error','?')}")
        fail += 1

    # Throttle to avoid hammering the API
    time.sleep(1.5)

    # Progress every 10
    if (i + 1) % 10 == 0:
        print(f"\n  --- Progress: {i+1}/{len(products)} | ok={ok} skip={skip} fail={fail} ---\n")

print(f"\n{'='*50}")
print(f"DONE: {ok} updated | {skip} already had disclaimer | {fail} failed")
print(f"{'='*50}")
