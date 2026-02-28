import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.woocommerce_connector import WooCommerceConnector

def check_stock_status():
    woo = WooCommerceConnector()
    print("Fetching all products...")
    result = woo.get_all_products(save=False)
    
    if not result.get("success"):
        print("Failed to fetch products:", result.get("error"))
        return
        
    products = result["data"]["products"]
    total = len(products)
    
    # We need to fetch full product details because get_all_products might not include `manage_stock` explicitly in its summary, 
    # but let's check what it returns first. Wait, get_all_products in woocommerce_connector currently returns:
    # "id", "name", "stock_status", "stock_quantity". 
    # Let's fetch the raw API to check `manage_stock` explicitly.
    
    print("Fetching raw products data to check manage_stock...")
    all_raw = []
    page = 1
    while True:
        res = woo._make_request("products", {"page": page, "per_page": 100, "status": "any"})
        if not res.get("success"):
            break
        batch = res.get("data", [])
        if not batch:
            break
        all_raw.extend(batch)
        page += 1
        if len(batch) < 100:
            break
            
    managed = 0
    unmanaged = 0
    in_stock = 0
    out_of_stock = 0
    
    for p in all_raw:
        if p.get("manage_stock"):
            managed += 1
        else:
            unmanaged += 1
            
        if p.get("stock_status") == "instock":
            in_stock += 1
        else:
            out_of_stock += 1
            
    print(f"Total Products: {len(all_raw)}")
    print(f"Manage Stock = True: {managed}")
    print(f"Manage Stock = False: {unmanaged}")
    print(f"In Stock: {in_stock}")
    print(f"Out of Stock: {out_of_stock}")

if __name__ == "__main__":
    check_stock_status()
