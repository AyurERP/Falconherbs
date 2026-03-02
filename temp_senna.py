import sys
sys.path.append('.')
from core.integration_bridge import IntegrationBridge

bridge = IntegrationBridge()
woo = bridge.tools.get('woocommerce')

result = woo.get_all_products(save=False)
if result.get('success'):
    products = result['data']['products']
    for p in products:
        if 'senna' in p.get('name', '').lower() or 'senna' in p.get('slug', '').lower():
            print(f"ID: {p['id']}, Name: {p['name']}, Slug: {p['slug']}")
