import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.woocommerce_connector import WooCommerceConnector

def get_product(pid):
    woo = WooCommerceConnector()
    res = woo._make_request(f'products/{pid}')
    data = res.get('data', {})
    
    with open("tmp/output_7510_utf8.txt", "w", encoding="utf-8") as f:
        f.write(f"ID: {data.get('id')}\n")
        f.write(f"NAME: {data.get('name')}\n")
        f.write(f"SLUG: {data.get('slug')}\n")
        f.write(f"\nDESCRIPTION:\n{data.get('description')}\n")
    
get_product(7510)
