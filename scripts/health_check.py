import os
import sys
import importlib
from pathlib import Path
import requests
from dotenv import load_dotenv

# Add root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

load_dotenv(ROOT / ".env")

def check_env():
    print("--- 1. Checking Environment Variables ---")
    required = [
        "FALCONHERBS_WC_API_KEY", "FALCONHERBS_WC_API_SECRET",
        "NVIDIA_API_KEY",
        "WHATSAPP_PHONE_ID", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_VERIFY_TOKEN",
        "ANTHROPIC_API_KEY",
    ]
    missing = []
    for var in required:
        val = os.getenv(var)
        if not val or val.startswith("your_") or "HERE" in val:
            print(f"  [FAIL] {var} is missing or placeholder")
            missing.append(var)
        else:
            print(f"  [PASS] {var} is set")
    return len(missing) == 0

def check_imports():
    print("\n--- 2. Checking Module Imports ---")
    modules = []
    
    # Core modules
    core_path = ROOT / "core"
    for f in core_path.glob("*.py"):
        if f.name != "__init__.py":
            modules.append(f"core.{f.stem}")
            
    # Agents
    agents_path = ROOT / "agents"
    for f in agents_path.glob("*.py"):
        if f.name != "__init__.py":
            modules.append(f"agents.{f.stem}")
            
    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
            print(f"  [PASS] {mod}")
        except Exception as e:
            print(f"  [FAIL] {mod}: {e}")
            failed.append(mod)
    return len(failed) == 0

def check_woo():
    print("\n--- 3. Testing WooCommerce Connectivity ---")
    url = os.getenv("WOO_SITE_URL") or "https://falconherbs.com"
    key = os.getenv("WOO_KEY") or os.getenv("FALCONHERBS_WC_API_KEY")
    secret = os.getenv("WOO_SECRET") or os.getenv("FALCONHERBS_WC_API_SECRET")
    
    if not (url and key and secret):
        print("  [SKIP] WooCommerce credentials missing")
        return False
        
    try:
        # Simple health check endpoint for WooCommerce
        api_url = f"{url.rstrip('/')}/wp-json/wc/v3/products/categories"
        response = requests.get(api_url, auth=(key, secret), timeout=10)
        if response.status_code == 200:
            print(f"  [PASS] WooCommerce connected (Status {response.status_code})")
            return True
        else:
            print(f"  [FAIL] WooCommerce error: {response.status_code} - {response.text[:100]}")
            return False
    except Exception as e:
        print(f"  [FAIL] WooCommerce exception: {e}")
        return False

def main():
    print("🦅 FALCON AGENCY — SYSTEM HEALTH CHECK")
    print("========================================")
    
    env_ok = check_env()
    import_ok = check_imports()
    woo_ok = check_woo()
    
    print("\n========================================")
    if env_ok and import_ok and woo_ok:
        print("✅ ALL SYSTEMS GO")
        sys.exit(0)
    else:
        print("❌ HEALTH CHECK FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
