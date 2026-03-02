import sys
sys.path.append('.')
from core.integration_bridge import IntegrationBridge

bridge = IntegrationBridge()
woo = bridge.tools.get('woocommerce')
pipeline = bridge.tools.get('content')

result = woo.get_all_products(save=False)
count = 0
violators = []
if result.get('success'):
    products = result['data']['products']
    for p in products:
        name = p.get('name', '')
        if not name: continue
        
        # Quick check for obvious claims, or use pipeline
        check = pipeline.safety_check(name)
        if not check.get('is_safe', True):
            violators.append((p['id'], name))
            count += 1
            print(f"- ID {p['id']}: {name}")

print(f"Total product titles with health claims: {count}")
