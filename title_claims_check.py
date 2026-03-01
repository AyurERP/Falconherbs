import sys
sys.path.append('.')
from core.integration_bridge import IntegrationBridge

bridge = IntegrationBridge()
woo = bridge.tools.get('woocommerce')

result = woo.get_all_products(save=False)
if result.get('success'):
    products = result['data']['products']
    bad_words = ['support', 'growth', 'cure', 'treat', 'heal', 'prevent', 'get rid', 'rid of', 'relief', 'control', 'manage', 'reduce', 'improve', 'boost', 'protect']
    
    violators = []
    for p in products:
        name = p.get('name', '').lower()
        if not name: continue
        
        found = [w for w in bad_words if w in name]
        if found:
            violators.append((p['id'], p['name'], found))
    
    with open('claims_output.txt', 'w', encoding='utf-8') as f:
        f.write('Products with possible health claims in title:\n')
        for v in violators:
            f.write(f'ID {v[0]}: {v[1]} (Claims: {", ".join(v[2])})\n')
    print(f"Checkout claims_output.txt - found {len(violators)}")
