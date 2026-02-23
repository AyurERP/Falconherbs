import sys
import os

# Ensure we can import from core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.woocommerce_connector import WooCommerceConnector
from core.revenue_tracker import RevenueTracker

def sync_orders():
    print("🔄 Connecting to WooCommerce...")
    woo = WooCommerceConnector()
    
    # We don't want to save the raw orders dump, just fetch them for the tracker
    orders_data = woo.get_orders(days_back=30, save=False)
    
    if not orders_data["success"]:
        print(f"❌ Failed to fetch orders: {orders_data.get('error')}")
        return
        
    print(f"✅ Fetched {orders_data['data']['total_orders']} orders. Syncing to Revenue Tracker...")
    
    tracker = RevenueTracker()
    result = tracker.sync_from_woocommerce(orders_data)
    
    if "error" in result:
        print(f"❌ Sync failed: {result['error']}")
    else:
        print(f"✅ Sync complete! Imported {result['imported']} new orders.")
        print(tracker.generate_whatsapp_report())

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    sync_orders()
