import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.woocommerce_connector import WooCommerceConnector
import os
from dotenv import load_dotenv

load_dotenv()

def test_api_write():
    woo = WooCommerceConnector()
    # Test updating a product's status to 'publish' (non-destructive test if already published)
    # We'll try to update Triphala Powder (7800) but with its SAME name to see if API works
    product_id = 7800
    test_data = {"name": "Triphala Powder"} 
    
    print(f"Testing API Write for Product {product_id}...")
    result = woo.update_product(product_id, test_data)
    
    if result.get("success"):
        print("✅ API Write Success!")
    else:
        print(f"❌ API Write Failed: {result.get('error')}")
        if "401" in str(result.get("error")) or "403" in str(result.get("error")):
            print("   Hint: API keys might be READ ONLY.")

if __name__ == "__main__":
    test_api_write()
