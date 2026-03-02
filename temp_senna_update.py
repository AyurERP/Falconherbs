import sys
sys.path.append('.')
from core.integration_bridge import IntegrationBridge

bridge = IntegrationBridge()
woo = bridge.tools.get('woocommerce')

# Update Senna Leaves
pid = 7493
new_name = 'Senna Leaves 70gm | Pure Ayurvedic Herb'
new_slug = 'senna-leaves-70gm-pure-ayurvedic-herb'

res = woo.update_product(pid, {
    'name': new_name,
    'slug': new_slug
})
print("Update Senna:", res.get('success'), res.get('error', ''))
