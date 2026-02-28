import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.woocommerce_connector import WooCommerceConnector

def get_product(pid):
    woo = WooCommerceConnector()
    res = woo._make_request(f'products/{pid}')
    data = res.get('data', {})
    
    print(f"ID: {data.get('id')}")
    print(f"NAME: {data.get('name')}")
    print(f"SLUG: {data.get('slug')}")
    print(f"\nDESCRIPTION:\n{data.get('description')}")
    
get_product(7510)
