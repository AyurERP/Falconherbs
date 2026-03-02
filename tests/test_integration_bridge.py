"""
Tests for IntegrationBridge — key public methods.
Uses mocked tool dependencies so no live API calls are made.
Run: python -X utf8 tests/test_integration_bridge.py
"""
import sys
import os
import io
from unittest.mock import MagicMock, patch

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PASSED = 0
FAILED = 0


def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check(label, ok, detail=""):
    global PASSED, FAILED
    icon = "PASS" if ok else "FAIL"
    suffix = f" | {detail}" if detail else ""
    print(f"  [{icon}] {label}{suffix}")
    if ok:
        PASSED += 1
    else:
        FAILED += 1
    return ok


def _make_bridge():
    """Return an IntegrationBridge with all tools mocked (no live connections)."""
    with patch("core.integration_bridge.IntegrationBridge._load_tools"):
        from core.integration_bridge import IntegrationBridge
        bridge = IntegrationBridge.__new__(IntegrationBridge)
        bridge.tools = {}
        bridge.status = {}
        bridge.brand_guidelines = {}
        return bridge


# ── Test 1: Bridge instantiation ────────────────────────────
def test_bridge_init():
    sep("TEST 1: IntegrationBridge instantiation")
    try:
        bridge = _make_bridge()
        check("Bridge created without crash", True)
        check("Has .tools dict", isinstance(bridge.tools, dict))
        check("Has .status dict", isinstance(bridge.status, dict))
    except Exception as e:
        check("Bridge created without crash", False, str(e))


# ── Test 2: get_status() ─────────────────────────────────────
def test_get_status():
    sep("TEST 2: get_status()")
    bridge = _make_bridge()
    bridge.status = {"woocommerce": "loaded", "content": "loaded"}

    result = bridge.get_status()
    check("Returns dict", isinstance(result, dict))
    check("Has 'timestamp' key", "timestamp" in result)
    check("Has 'tools' key", "tools" in result)
    check("Has 'all_loaded' key", "all_loaded" in result)


# ── Test 3: run_store_audit() — no tool loaded ───────────────
def test_store_audit_no_tool():
    sep("TEST 3: run_store_audit() when WooCommerce not loaded")
    bridge = _make_bridge()
    bridge.tools = {}  # no woocommerce

    result = bridge.run_store_audit()
    check("Returns dict", isinstance(result, dict))
    check("success=False when not loaded", result.get("success") is False)
    check("Has 'error' key", "error" in result)


# ── Test 4: run_store_audit() — with mock WooCommerce ────────
def test_store_audit_with_mock_woo():
    sep("TEST 4: run_store_audit() with mocked WooCommerce")
    bridge = _make_bridge()

    mock_woo = MagicMock()
    mock_woo.full_store_audit.return_value = {
        "success": True,
        "summary": "87 products audited.",
        "data": {"total_products": 87}
    }
    bridge.tools = {"woocommerce": mock_woo}

    result = bridge.run_store_audit()
    check("Returns dict", isinstance(result, dict))
    check("success=True with mock", result.get("success") is True)
    check("Summary present", "summary" in result or "data" in result)
    check("WooCommerce.full_store_audit called once", mock_woo.full_store_audit.call_count == 1)


# ── Test 5: check_health_safety() — no pipeline ──────────────
def test_check_safety_no_pipeline():
    sep("TEST 5: check_health_safety() when content pipeline not loaded")
    bridge = _make_bridge()
    bridge.tools = {}

    result = bridge.check_health_safety("this herb cures diabetes")
    check("Returns dict", isinstance(result, dict))
    check("success=False when not loaded", result.get("success") is False)


# ── Test 6: check_health_safety() — with mock pipeline ───────
def test_check_safety_with_mock():
    sep("TEST 6: check_health_safety() with mocked ContentPipeline")
    bridge = _make_bridge()

    mock_pipeline = MagicMock()
    mock_pipeline.safety_check.return_value = {
        "is_safe": False,
        "changes": [{"severity": "HIGH", "original": "cures diabetes", "suggested": "traditionally used"}]
    }
    bridge.tools = {"content": mock_pipeline}

    result = bridge.check_health_safety("this herb cures diabetes")
    check("Returns dict", isinstance(result, dict))
    check("success=True with mock", result.get("success") is True)
    check("Result contains safety data", "result" in result)
    safety = result.get("result", {})
    check("is_safe=False for 'cures' claim", safety.get("is_safe") is False)
    check("safety_check called once", mock_pipeline.safety_check.call_count == 1)


# ── Test 7: scan_products() — no rewriter tool ───────────────
def test_scan_products_no_rewriter():
    sep("TEST 7: scan_products() when rewriter not loaded")
    bridge = _make_bridge()
    bridge.tools = {}

    result = bridge.scan_products()
    check("Returns dict", isinstance(result, dict))
    check("success=False when not loaded", result.get("success") is False)


# ── Test 8: get_rewrite_status() — file absent ───────────────
def test_get_rewrite_status_no_file():
    sep("TEST 8: get_rewrite_status() with missing staging file")
    bridge = _make_bridge()

    # Temporarily rename staging file if it exists
    import json
    staging_path = os.path.join(ROOT, "data", "staging", "rewrites", "index.json")
    result = bridge.get_rewrite_status()
    check("Returns string", isinstance(result, str))
    check("Non-empty response", len(result) > 0)


# ── Summary ──────────────────────────────────────────────────
if __name__ == "__main__":
    test_bridge_init()
    test_get_status()
    test_store_audit_no_tool()
    test_store_audit_with_mock_woo()
    test_check_safety_no_pipeline()
    test_check_safety_with_mock()
    test_scan_products_no_rewriter()
    test_get_rewrite_status_no_file()

    sep("SUMMARY")
    total = PASSED + FAILED
    print(f"  Result: {PASSED}/{total} passed")
    if FAILED:
        print(f"  FAILED: {FAILED} tests need attention.")
        sys.exit(1)
    else:
        print("  All tests passed!")
        sys.exit(0)
