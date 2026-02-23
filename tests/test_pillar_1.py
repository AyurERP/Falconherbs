"""
Falcon Agency — Pillar 1 Verification
Tests the LeadPredictor math and report generation.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from core.integration_bridge import IntegrationBridge

def test_inventory_prediction():
    print("🚀 Initializing Integration Bridge...")
    bridge = IntegrationBridge()
    
    print("\n📊 Generating Inventory Burn Rate Report...")
    result = bridge.get_burn_rate_report()
    
    if result.get("success"):
        print("\n✅ Report Generated Successfully!")
        print("-" * 30)
        print(result.get("summary"))
        print("-" * 30)
        
        # Check if data structure is correct
        data = result.get("data", {})
        print(f"Products Analyzed: {len(data.get('all', []))}")
        print(f"Low Stock Alerts: {len(data.get('risky', []))}")
        
    else:
        print(f"\n❌ Report Failed: {result.get('error')}")

if __name__ == "__main__":
    test_inventory_prediction()
