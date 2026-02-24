"""
Phase 3 — Offline tests.
Covers: HealthClaimsRewriter logic, memory topics,
commander intent routing for new Phase 3 intents.

Run: python tests/test_phase3.py
"""
import sys, os, json, tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
))

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


# ── Memory / Topics ───────────────────────────────────────

def test_track_topic_stores():
    """track_topic saves keywords for user"""
    from core.memory import ConversationMemory
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = Path(f.name)
    try:
        m = ConversationMemory(db_path=db)
        m.track_topic("user1", "ashwagandha benefits kya hai", "question")
        prefs = m.get_user_preferences("user1")
        topics = [p["topic"] for p in prefs]
        assert "ashwagandha" in topics, f"expected ashwagandha in {topics}"
        assert "benefits" in topics
    finally:
        db.unlink(missing_ok=True)


def test_track_topic_frequency():
    """Repeated messages increase frequency"""
    from core.memory import ConversationMemory
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = Path(f.name)
    try:
        m = ConversationMemory(db_path=db)
        for _ in range(3):
            m.track_topic("user1", "ashwagandha acha hai")
        prefs = m.get_user_preferences("user1")
        ashwa = next(
            (p for p in prefs if p["topic"] == "ashwagandha"), None
        )
        assert ashwa is not None
        assert ashwa["frequency"] == 3, \
            f"Expected 3, got {ashwa['frequency']}"
    finally:
        db.unlink(missing_ok=True)


def test_build_rich_context_includes_topics():
    """build_rich_context includes frequently asked topics"""
    from core.memory import ConversationMemory
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = Path(f.name)
    try:
        m = ConversationMemory(db_path=db)
        m.track_topic("user1", "triphala digestion ke liye")
        m.add_message("user1", "user", "triphala ke baare mein batao")
        ctx = m.build_rich_context("user1")
        assert "triphala" in ctx.lower(), \
            f"Context: {ctx}"
    finally:
        db.unlink(missing_ok=True)


def test_stopwords_excluded():
    """Common stopwords are not tracked as topics"""
    from core.memory import ConversationMemory
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = Path(f.name)
    try:
        m = ConversationMemory(db_path=db)
        m.track_topic("user1", "the is in at to a an")
        prefs = m.get_user_preferences("user1")
        assert len(prefs) == 0, \
            f"Expected no topics, got {prefs}"
    finally:
        db.unlink(missing_ok=True)


# ── HealthClaimsRewriter — offline ────────────────────────

class MockPipeline:
    """Mock ContentPipeline for offline tests"""
    def safety_check(self, text):
        # Flag text that contains "cures" or "cancer"
        has_issue = any(
            w in text.lower() for w in ["cures", "cancer"]
        )
        changes = []
        if has_issue:
            changes.append({
                "severity": "HIGH",
                "found": "cures/cancer",
                "action": "Replace with safe language",
            })
        return {
            "is_safe": not has_issue,
            "cleaned_content": text,
            "changes": changes,
        }


class MockWoo:
    """Mock WooCommerce connector for offline tests"""
    PRODUCTS = [
        {"id": 1, "name": "Ashwagandha Capsules"},
        {"id": 2, "name": "Triphala Churna"},
    ]
    RAW = {
        1: {"description": "This product cures stress.",
            "short_description": "Natural stress cure."},
        2: {"description": "Good for digestion.",
            "short_description": "Daily supplement."},
    }

    def get_all_products(self, save=False):
        return {"success": True,
                "data": {"products": self.PRODUCTS}}

    def _make_request(self, endpoint):
        pid = int(endpoint.split("/")[-1])
        data = self.RAW.get(pid, {})
        return {"success": True, "data": data}

    def update_product(self, product_id, data):
        return {"success": True, "product_id": product_id}


class MockBridge:
    def __init__(self, tmp_dir):
        self.tools = {
            "woocommerce": MockWoo(),
            "content": MockPipeline(),
        }
        self._tmp_dir = tmp_dir

    def get(self, key):
        return self.tools.get(key)


def make_rewriter(tmp_dir):
    from core.health_rewriter import HealthClaimsRewriter
    bridge = MockBridge(tmp_dir)
    r = HealthClaimsRewriter(bridge=bridge)
    r.rewrites_dir = Path(tmp_dir)
    r.rewrites_dir.mkdir(parents=True, exist_ok=True)
    return r


def test_scan_flags_violations():
    """scan_all_products flags products with health claims"""
    with tempfile.TemporaryDirectory() as tmp:
        r = make_rewriter(tmp)
        result = r.scan_all_products()
        assert result["success"] is True
        assert result["total"] == 2
        assert result["flagged"] == 1, \
            f"Expected 1 flagged, got {result['flagged']}"
        assert result["products"][0]["name"] == "Ashwagandha Capsules"


def test_scan_saves_last_scan():
    """scan_all_products saves last_scan.json"""
    with tempfile.TemporaryDirectory() as tmp:
        r = make_rewriter(tmp)
        r.scan_all_products()
        scan_file = Path(tmp) / "last_scan.json"
        assert scan_file.exists(), "last_scan.json not created"
        with open(scan_file) as f:
            data = json.load(f)
        assert data["flagged"] == 1


def test_rewrite_flagged_saves_file():
    """rewrite_flagged creates {id}.json file"""
    with tempfile.TemporaryDirectory() as tmp:
        r = make_rewriter(tmp)
        r.scan_all_products()
        result = r.rewrite_flagged()
        assert result["success"] is True
        assert result["rewrites"] == 1
        rewrite_file = Path(tmp) / "1.json"
        assert rewrite_file.exists(), f"{rewrite_file} not created"


def test_rewrite_status_pending():
    """get_rewrite_status shows pending count"""
    with tempfile.TemporaryDirectory() as tmp:
        r = make_rewriter(tmp)
        r.scan_all_products()
        r.rewrite_flagged()
        status = r.get_rewrite_status()
        assert "Pending" in status or "pending" in status, \
            f"Status: {status}"
        assert "1" in status  # 1 pending


def test_apply_rewrite_calls_woo():
    """apply_rewrite calls woo.update_product successfully"""
    with tempfile.TemporaryDirectory() as tmp:
        r = make_rewriter(tmp)
        r.scan_all_products()
        r.rewrite_flagged()
        result = r.apply_rewrite(1)
        assert result["success"] is True


def test_apply_rewrite_marks_applied():
    """apply_rewrite marks rewrite as applied"""
    with tempfile.TemporaryDirectory() as tmp:
        r = make_rewriter(tmp)
        r.scan_all_products()
        r.rewrite_flagged()
        r.apply_rewrite(1)
        with open(Path(tmp) / "1.json") as f:
            data = json.load(f)
        assert data["status"] == "applied"
        assert data["applied_at"] is not None


def test_apply_rewrite_no_double_apply():
    """Cannot apply same rewrite twice"""
    with tempfile.TemporaryDirectory() as tmp:
        r = make_rewriter(tmp)
        r.scan_all_products()
        r.rewrite_flagged()
        r.apply_rewrite(1)
        result = r.apply_rewrite(1)
        assert result["success"] is False
        assert "already" in result["error"]


def test_apply_rewrite_missing_id():
    """apply_rewrite returns error for unknown product_id"""
    with tempfile.TemporaryDirectory() as tmp:
        r = make_rewriter(tmp)
        result = r.apply_rewrite(9999)
        assert result["success"] is False


# ── Commander intents — Phase 3 ───────────────────────────

def test_intent_scan_products():
    """'scan products' routes to scan_products intent"""
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()
    # "products scan" uniquely matches scan_products (no overlap)
    result = clf.classify("products scan karo")
    assert result is not None, "No match"
    assert result["intent"] == "scan_products", \
        f"Got: {result['intent']}"


def test_intent_rewrite_products():
    """'rewrite products' routes to rewrite_products"""
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()
    result = clf.classify("rewrite flagged products")
    assert result is not None
    assert result["intent"] == "rewrite_products", \
        f"Got: {result['intent']}"


def test_intent_apply_rewrite():
    """'apply rewrite 42' routes to apply_rewrite"""
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()
    result = clf.classify("apply rewrite 42")
    assert result is not None
    assert result["intent"] == "apply_rewrite", \
        f"Got: {result['intent']}"


def test_intent_rewrite_status():
    """'rewrite status' routes to rewrite_status"""
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()
    result = clf.classify("pending rewrites dikhao")
    assert result is not None
    assert result["intent"] == "rewrite_status", \
        f"Got: {result['intent']}"


# ── RUN ALL ───────────────────────────────────────────────

print("=" * 55)
print("PHASE 3 — TEST SUITE")
print("=" * 55)

t("memory: track_topic stores keywords",
  test_track_topic_stores)
t("memory: repeated topics raise frequency",
  test_track_topic_frequency)
t("memory: build_rich_context includes topics",
  test_build_rich_context_includes_topics)
t("memory: stopwords not tracked",
  test_stopwords_excluded)
t("rewriter: scan flags violations",
  test_scan_flags_violations)
t("rewriter: scan saves last_scan.json",
  test_scan_saves_last_scan)
t("rewriter: rewrite_flagged saves file",
  test_rewrite_flagged_saves_file)
t("rewriter: get_rewrite_status shows pending",
  test_rewrite_status_pending)
t("rewriter: apply_rewrite calls woo",
  test_apply_rewrite_calls_woo)
t("rewriter: apply marks status=applied",
  test_apply_rewrite_marks_applied)
t("rewriter: no double apply",
  test_apply_rewrite_no_double_apply)
t("rewriter: apply with missing id fails",
  test_apply_rewrite_missing_id)
t("intent: scan_products",
  test_intent_scan_products)
t("intent: rewrite_products",
  test_intent_rewrite_products)
t("intent: apply_rewrite",
  test_intent_apply_rewrite)
t("intent: rewrite_status",
  test_intent_rewrite_status)

print("=" * 55)
print(f"RESULT: {passed}/{passed+failed} passed")
if failed == 0:
    print("ALL PASS")
else:
    print(f"{failed} FAILED")
print("=" * 55)
