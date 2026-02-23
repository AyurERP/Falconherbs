"""Test: Generate a REAL AI-powered blog post"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.integration_bridge import IntegrationBridge

bridge = IntegrationBridge()

# Check status
status = bridge.get_status()
for tool, state in status["tools"].items():
    icon = "✅" if "loaded" in state else "❌"
    print(f"  {icon} {tool}: {state}")

# Generate a REAL blog post!
print("\n🚀 Generating REAL AI blog post...")
result = bridge.create_blog(
    topic="Complete Guide to Ashwagandha Benefits",
    keyword="ashwagandha benefits",
    product="Falcon Herbs Ashwagandha Capsules"
)

if result.get("success"):
    draft = result["draft"]
    status_val = draft["status"]
    print(f"✅ Status: {status_val}")
    print(f"📂 File: {result['file']}")
    if draft.get("content"):
        print(f"📝 Content length: {len(draft['content'])} chars")
        safety = draft.get("safety_check", {})
        print(f"🛡️ Safety: {safety.get('is_safe', 'N/A')}")
        print(f"🔧 Changes: {safety.get('changes_made', 0)}")
        print(f"\n--- FIRST 800 CHARS ---")
        print(draft["content"][:800])
    else:
        print("⚠️ No content generated (prompt_only)")
else:
    print(f"❌ Error: {result.get('error')}")
