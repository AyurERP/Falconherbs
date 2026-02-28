import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.integration_bridge import IntegrationBridge
from core.content_ai_client import ContentAIClient
from core.content_pipeline import ContentPipeline
from core.woocommerce_connector import WooCommerceConnector
from core.health_rewriter import HealthClaimsRewriter

def debug_scan_triphala():
    # Setup tools
    ai = ContentAIClient()
    content = ContentPipeline(ai_client=ai)
    woo = WooCommerceConnector()
    
    bridge = IntegrationBridge()
    bridge.tools = {
        "ai_client": ai,
        "content": content,
        "woocommerce": woo
    }
    
    rewriter = HealthClaimsRewriter(bridge)
    bridge.tools["rewriter"] = rewriter
    
    # Fetch Triphala specifically
    print("Fetching Product 7800...")
    res = woo._make_request("products/7800")
    if not res.get("success"):
        print(f"Failed to fetch: {res.get('error')}")
        return
    
    product = res["data"]
    name = product.get("name")
    desc = product.get("description")
    print(f"Product: {name}")
    print(f"Description: {desc[:100]}...")
    
    # Run safety check
    print("\nRunning Safety Check...")
    check = content.safety_check(f"{name} {desc}")
    print(f"Result: Is Safe? {check['is_safe']}")
    print(f"Changes: {check['changes']}")
    
    if not check['is_safe'] or check['changes_made'] > 0:
        print("\nRewriting...")
        # rewriter.scan_all_products() # To ensure last_scan updated
        rewriter.rewrite_flagged(product_id=7800)
        print("Done. Check for 7800.json")

if __name__ == "__main__":
    debug_scan_triphala()
