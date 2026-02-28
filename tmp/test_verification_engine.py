import os
import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.woocommerce_connector import WooCommerceConnector

def test_verify():
    woo = WooCommerceConnector()
    print("Testing VerifyEngine with harmless update...")
    
    # Try updating a product description slightly
    # Re-using the same ID we messed with earlier: 7510
    product_id = 7510
    data = {"name": "Turmeric Powder 100g - Traditional Ayurvedic Herb"} # Same name as before to test if it passes (since we fixed the unchanged bug, wait it should pass if we send the same data cause `c_expect != c_before` will be FALSE, hence it won't be flagged)

    # Actually let's test a real change
    print(f"\n--- TEST 1: Identical Data Update ---")
    res1 = woo.update_product(product_id, data)
    print("Result:", res1)
    
    # Test a minor space addition
    print(f"\n--- TEST 2: Minor Text Change Update ---")
    data2 = {"name": "Turmeric Powder 100g - Traditional Ayurvedic Herb "}
    res2 = woo.update_product(product_id, data2)
    print("Result:", res2)

    # Test an impossible meta update if we want to test failure (though WC might just accept it and add it?)
    # Let's see the log
    log_file = "data/woocommerce/verification_log.json"
    if os.path.exists(log_file):
        print(f"\nLog file contents ({log_file}):")
        with open(log_file, "r", encoding="utf-8") as f:
            print(f.read())
            
if __name__ == "__main__":
    test_verify()
