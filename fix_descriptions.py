import sys
sys.path.append('.')
from core.integration_bridge import IntegrationBridge
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

bridge = IntegrationBridge()
woo = bridge.tools.get('woocommerce')

def sync_product(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if data.get('status') == 'applied' and data.get('product_id'):
        pid = data.get('product_id')
        new_desc = data.get('rewritten_description')
        if pid and new_desc:
            print(f'Syncing {pid}...')
            res = woo.update_product(pid, {'description': new_desc})
            return 1 if res.get('success') else 0
    return 0

paths = [p for p in Path('data/content/product_rewrites').glob('*.json') 
         if p.name not in ['last_scan.json', 'page_scan.json', 'blog_scan.json']]

with ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(sync_product, paths)
    applied_count = sum(results)

print(f'\nSuccessfully re-synced {applied_count} products.')
