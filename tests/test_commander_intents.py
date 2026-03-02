"""
Tests for ExtendedIntentClassifier + IntentResponseHandler.
Run: python -X utf8 tests/test_commander_intents.py
"""
import sys
import os
import io

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


# ── Test 1: Health-scan intent recognition ──────────────────
def test_health_scan_intents():
    sep("TEST 1: health_scan intent patterns")
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()

    phrases = [
        "health claims scan karo",
        "scan karo site",
        "compliance check karo",
        "fssai scan",          # fssai added to patterns
        "violation check karo",
    ]
    for phrase in phrases:
        r = clf.classify(phrase)
        intent = r["intent"] if r else None
        check(f'"{phrase}"', intent == "health_scan", f"got={intent}")


# ── Test 2: Store-audit intent recognition ──────────────────
def test_store_audit_intents():
    sep("TEST 2: store_audit intent patterns")
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()

    phrases = [
        "store audit karo",
        "dukaan check karo",
        "full store audit",
    ]
    for phrase in phrases:
        r = clf.classify(phrase)
        intent = r["intent"] if r else None
        check(f'"{phrase}"', intent == "store_audit", f"got={intent}")


# ── Test 3: Rewrite-status intent ───────────────────────────
def test_rewrite_status_intent():
    sep("TEST 3: rewrite_status intent patterns")
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()

    phrases = [
        ("rewrite status", "rewrite_status"),
        ("show pending rewrites", "rewrite_status"),
    ]
    for phrase, expected_intent in phrases:
        r = clf.classify(phrase)
        intent = r["intent"] if r else None
        check(f'"{phrase}"', intent == expected_intent, f"got={intent}")


# ── Test 4: Approve-rewrites intent ─────────────────────────
def test_approve_rewrites_intent():
    sep("TEST 4: approve_all_rewrites intent patterns")
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()

    phrases = [
        "approve all rewrites",
        "approve all",
        "apply all rewrites",
    ]
    for phrase in phrases:
        r = clf.classify(phrase)
        intent = r["intent"] if r else None
        check(f'"{phrase}"', intent == "approve_all_rewrites", f"got={intent}")


# ── Test 5: handle_health_scan returns valid dict ────────────
def test_health_scan_handler_structure():
    sep("TEST 5: handle_health_scan() returns correct structure")
    from core.commander_intents import IntentResponseHandler

    class _MockBridge:
        def run_health_scan(self, max_pages=100):
            return {"success": True, "summary": "Mock scan complete. 0 violations."}

    handler = IntentResponseHandler(integration_bridge=_MockBridge())
    result = handler.handle_health_scan({"intent": "health_scan", "extracted_data": {}})

    check("Returns dict", isinstance(result, dict))
    check("Has 'response' key", "response" in result)
    check("Has 'success' key", "success" in result)
    check("Success is True", result.get("success") is True)
    check("Response is non-empty string",
          isinstance(result.get("response"), str) and len(result["response"]) > 0)


# ── Test 6: handle_store_audit returns valid dict ────────────
def test_store_audit_handler_structure():
    sep("TEST 6: handle_store_audit() returns correct structure")
    from core.commander_intents import IntentResponseHandler

    class _MockBridge:
        def run_store_audit(self):
            return {"success": True, "summary": "87 products, 3 categories checked."}

    handler = IntentResponseHandler(integration_bridge=_MockBridge())
    result = handler.handle_store_audit({"intent": "store_audit", "extracted_data": {}})

    check("Returns dict", isinstance(result, dict))
    check("Has 'response' key", "response" in result)
    check("Success is True", result.get("success") is True)


# ── Test 7: handle_health_scan with bridge failure ───────────
def test_health_scan_handler_failure():
    sep("TEST 7: handle_health_scan() handles bridge failure gracefully")
    from core.commander_intents import IntentResponseHandler

    class _FailBridge:
        def run_health_scan(self, max_pages=100):
            return {"success": False, "error": "Site unreachable"}

    handler = IntentResponseHandler(integration_bridge=_FailBridge())
    result = handler.handle_health_scan({"intent": "health_scan", "extracted_data": {}})

    check("Returns dict on failure", isinstance(result, dict))
    check("success=False on failure", result.get("success") is False)
    check("Has error info in response",
          "unreachable" in result.get("response", "").lower()
          or "failed" in result.get("response", "").lower())


# ── Test 8: IntentResponseHandler.handle() routing ──────────
def test_handler_routing():
    sep("TEST 8: IntentResponseHandler.handle() routes correctly")
    from core.commander_intents import IntentResponseHandler

    class _MockBridge:
        def run_store_audit(self):
            return {"success": True, "summary": "All good."}
        def run_health_scan(self, max_pages=100):
            return {"success": True, "summary": "Clean."}

    handler = IntentResponseHandler(integration_bridge=_MockBridge())

    for intent_name, handler_name in [
        ("store_audit", "handle_store_audit"),
        ("health_scan", "handle_health_scan"),
    ]:
        result = handler.handle({"intent": intent_name, "handler": handler_name,
                                 "extracted_data": {}})
        check(f'handle("{intent_name}") -> dict', isinstance(result, dict))
        check(f'handle("{intent_name}") -> success', result.get("success") is True)


# ── Test 9: No false-positive on unrelated messages ──────────
def test_no_false_positive():
    sep("TEST 9: No false-positive on unrelated messages")
    from core.commander_intents import ExtendedIntentClassifier
    clf = ExtendedIntentClassifier()

    unrelated = [
        "hello bhai",
        "weather kaisa hai",
        "mujhe neend aa rahi hai",
    ]
    for phrase in unrelated:
        r = clf.classify(phrase)
        check(f'"{phrase}" -> no health/audit match',
              r is None or r.get("intent") not in ("health_scan", "store_audit"),
              f"got={r['intent'] if r else None}")


# ── Summary ──────────────────────────────────────────────────
if __name__ == "__main__":
    test_health_scan_intents()
    test_store_audit_intents()
    test_rewrite_status_intent()
    test_approve_rewrites_intent()
    test_health_scan_handler_structure()
    test_store_audit_handler_structure()
    test_health_scan_handler_failure()
    test_handler_routing()
    test_no_false_positive()

    sep("SUMMARY")
    total = PASSED + FAILED
    print(f"  Result: {PASSED}/{total} passed")
    if FAILED:
        print(f"  FAILED: {FAILED} tests need attention.")
        sys.exit(1)
    else:
        print("  All tests passed!")
        sys.exit(0)
