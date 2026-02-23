"""
Tests for PriceTrackerAgent — all offline, no HTTP calls.
Run: python tests/test_price_tracker.py
"""
import sys, os, json, tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
))
from agents.price_tracker import PriceTrackerAgent


def make_agent(tmp_dir: Path) -> PriceTrackerAgent:
    agent = PriceTrackerAgent(bridge=None)
    agent.data_dir = tmp_dir
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return agent


passed = 0
failed = 0

def t(name, fn):
    global passed, failed
    try:
        fn()
        print(f"[PASS] {name}")
        passed += 1
    except AssertionError as e:
        print(f"[FAIL] {name}: {e}")
        failed += 1
    except Exception as e:
        print(f"[ERROR] {name}: {e}")
        failed += 1


# ── Gap strategy ─────────────────────────────────────────

def test_gap_budget():
    a = PriceTrackerAgent()
    assert a.get_gap(149) == 5

def test_gap_standard():
    a = PriceTrackerAgent()
    assert a.get_gap(299) == 10

def test_gap_premium():
    a = PriceTrackerAgent()
    assert a.get_gap(599) == 20

def test_gap_boundary_200():
    a = PriceTrackerAgent()
    # ₹200 is standard
    assert a.get_gap(200) == 10

def test_gap_boundary_500():
    a = PriceTrackerAgent()
    # ₹500 is premium
    assert a.get_gap(500) == 20


# ── Recommendation engine ─────────────────────────────────

def test_recommend_lower():
    """When our price is well above competitors → action=lower"""
    a = PriceTrackerAgent()
    product = {"name": "Test", "our_price": 399}
    comp    = {"himalaya": 299, "patanjali": 279, "dabur": 319}
    rec = a.compute_recommendation(product, comp)
    assert rec["action"] == "lower"
    assert rec["competitor_min"] == 279
    assert rec["recommended"] == 279 - 10   # standard tier

def test_recommend_ok():
    """Already competitive → action=ok"""
    a = PriceTrackerAgent()
    product = {"name": "Test", "our_price": 269}
    comp    = {"himalaya": 299, "patanjali": 289}
    rec = a.compute_recommendation(product, comp)
    assert rec["action"] == "ok"

def test_recommend_raise():
    """Much cheaper than market → action=raise"""
    a = PriceTrackerAgent()
    product = {"name": "Test", "our_price": 149}
    comp    = {"himalaya": 399, "patanjali": 350}
    rec = a.compute_recommendation(product, comp)
    assert rec["action"] == "raise"

def test_recommend_no_data():
    """No competitor prices → action=no_data"""
    a = PriceTrackerAgent()
    product = {"name": "Test", "our_price": 299}
    rec = a.compute_recommendation(product, {})
    assert rec["action"] == "no_data"

def test_recommend_partial_data():
    """Some None prices — only valid ones counted"""
    a = PriceTrackerAgent()
    product = {"name": "Test", "our_price": 399}
    comp    = {"himalaya": None, "patanjali": 299, "dabur": None}
    rec = a.compute_recommendation(product, comp)
    assert rec["competitor_min"] == 299
    assert rec["action"] == "lower"


# ── Manual price update ───────────────────────────────────

def test_manual_price_save():
    with tempfile.TemporaryDirectory() as tmp:
        a = make_agent(Path(tmp))
        result = a.update_manual_price("Ashwagandha", "himalaya", 399.0)
        assert result["success"] is True

        manual = a._load_manual_prices()
        assert "ashwagandha" in manual
        assert manual["ashwagandha"]["himalaya"]["price"] == 399.0

def test_manual_price_overwrite():
    """Updating same product+brand overwrites, not duplicates"""
    with tempfile.TemporaryDirectory() as tmp:
        a = make_agent(Path(tmp))
        a.update_manual_price("Triphala", "patanjali", 149.0)
        a.update_manual_price("Triphala", "patanjali", 159.0)

        manual = a._load_manual_prices()
        assert manual["triphala"]["patanjali"]["price"] == 159.0


# ── Product map ───────────────────────────────────────────

def test_product_map_loads():
    """config/product_map.yaml must load with >= 5 products"""
    a = PriceTrackerAgent()
    products = a.load_product_map()
    assert len(products) >= 5, \
        f"Expected ≥5 products, got {len(products)}"

def test_product_map_has_required_keys():
    """Each product must have name, our_price, competitors"""
    a = PriceTrackerAgent()
    for p in a.load_product_map():
        assert "name"        in p, f"Missing 'name': {p}"
        assert "our_price"   in p, f"Missing 'our_price': {p}"
        assert "competitors" in p, f"Missing 'competitors': {p}"
        assert p["our_price"] > 0, f"Invalid our_price in {p['name']}"

def test_product_map_competitors_have_urls():
    """Each competitor should have amazon_url"""
    a = PriceTrackerAgent()
    for p in a.load_product_map():
        for brand, info in p["competitors"].items():
            assert "amazon_url" in info, \
                f"{p['name']}/{brand} missing amazon_url"


# ── Report formatting ──────────────────────────────────────

def test_report_no_scan():
    with tempfile.TemporaryDirectory() as tmp:
        a = make_agent(Path(tmp))
        report = a.get_latest_report()
        assert "No scans" in report or "price scan" in report.lower()

def test_report_with_alerts():
    agent = PriceTrackerAgent()
    mock_results = [
        {
            "product":   "Ashwagandha",
            "our_price": 399,
            "recommendation": {
                "action":         "lower",
                "competitor_min": 279,
                "competitor_avg": 299,
                "recommended":    269,
                "note":           "Lower by ₹130",
            },
        },
        {
            "product":   "Triphala",
            "our_price": 199,
            "recommendation": {
                "action":         "ok",
                "competitor_min": 210,
                "competitor_avg": 225,
                "recommended":    205,
                "note":           "Price competitive",
            },
        },
    ]
    alerts = [mock_results[0]]
    report = agent._format_whatsapp_report(mock_results, alerts, "2026-02-24")
    assert "ACTION NEEDED" in report
    assert "Ashwagandha"   in report
    assert "269"           in report   # recommended price
    assert "Triphala"      in report


# ── Price extraction (offline regex) ─────────────────────

def test_price_pattern_json():
    """Extracts price from JSON pattern in mock HTML"""
    import re
    html  = '..."priceAmount": 299.00,'  # comma stops [\d.]+ match
    match = re.search(r'"priceAmount":\s*([\d.]+)', html)
    assert match and float(match.group(1)) == 299.0

def test_price_pattern_offscreen():
    """Extracts price from a-offscreen pattern"""
    import re
    html  = '<span class="a-offscreen">₹ 349.00</span>'
    match = re.search(
        r'class="a-offscreen"[^>]*>[₹\s]*([\d,]+\.?\d*)', html
    )
    assert match and float(match.group(1).replace(",", "")) == 349.0


# ── RUN ALL ────────────────────────────────────────────────

print("=" * 55)
print("PRICE TRACKER — TEST SUITE")
print("=" * 55)

t("gap: budget (Rs149 -> Rs5)",      test_gap_budget)
t("gap: standard (Rs299 -> Rs10)",   test_gap_standard)
t("gap: premium (Rs599 -> Rs20)",    test_gap_premium)
t("gap: boundary Rs200 -> standard", test_gap_boundary_200)
t("gap: boundary Rs500 -> premium",  test_gap_boundary_500)
t("recommend: lower",             test_recommend_lower)
t("recommend: ok",                test_recommend_ok)
t("recommend: raise",             test_recommend_raise)
t("recommend: no data",           test_recommend_no_data)
t("recommend: partial None data", test_recommend_partial_data)
t("manual price save",            test_manual_price_save)
t("manual price overwrite",       test_manual_price_overwrite)
t("product map loads (>=5)",      test_product_map_loads)
t("product map required keys",    test_product_map_has_required_keys)
t("product map competitor URLs",  test_product_map_competitors_have_urls)
t("report: no scan message",      test_report_no_scan)
t("report: with alerts",          test_report_with_alerts)
t("price regex: JSON pattern",    test_price_pattern_json)
t("price regex: offscreen",       test_price_pattern_offscreen)

print("=" * 55)
print(f"RESULT: {passed}/{passed+failed} passed")
if failed == 0:
    print("ALL PASS")
else:
    print(f"{failed} FAILED")
print("=" * 55)
