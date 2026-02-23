"""
Phase 3: Local Mock Testing
Tests ALL Commander intents + handlers without WhatsApp.
Run: python tests/test_phase3_mock.py
"""
import sys
import os
import io
import time

# Fix Windows emoji encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure project root is in path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)


def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_result(label, passed, detail=""):
    icon = "PASS" if passed else "FAIL"
    detail_str = f" | {detail}" if detail else ""
    print(f"  [{icon}] {label}{detail_str}")
    return passed


# ══════════════════════════════════════════════════════════
#  TEST 1: Intent Classification (all 22 intents)
# ══════════════════════════════════════════════════════════
def test_intent_classification():
    separator("TEST 1: Intent Classification (22 intents)")
    from core.commander_intents import ExtendedIntentClassifier
    
    classifier = ExtendedIntentClassifier()
    
    tests = [
        # (message, expected_intent)
        ("hello", None),  # No match expected
        ("store audit karo", "store_audit"),
        ("store check karo", "store_audit"),
        ("kitne order aaye last month?", "order_check"),
        ("payment gateway chal raha hai?", "payment_check"),
        ("health claims scan karo", "health_scan"),
        ("is this safe: our herb cures diabetes", "safety_check"),
        ("kitna kamaya is month?", "revenue_check"),
        ("blog likh about ashwagandha benefits", "create_blog"),
        ("social post banao green tea", "create_social"),
        ("content status dikhao", "content_status"),
        ("sab generate karo pura week", "generate_weekly"),
        ("morning report do", "morning_report"),
        ("sham ka report bhejo", "evening_report"),
        ("purane customer dhundho", "customer_recovery"),
        # NEW intents (Phase 2)
        ("goal set karo revenue 12500 blogs 8", "goal_set"),
        ("progress dikhao", "progress_check"),
        ("profit report bhejo", "profit_report"),
        ("kitna munafa hua", "profit_report"),
        ("full seo audit karo", "full_seo_audit"),
        ("seo check karo", "full_seo_audit"),
        ("content calendar banao", "content_calendar"),
        ("competitor analysis karo https://herbsforever.com", "competitor_analysis"),
        ("competition check karo naturalherbs.com", "competitor_analysis"),
        ("backup banao", "backup_create"),
        ("backups dikhao", "backup_list"),
        ("data verify karo", "backup_verify"),
    ]
    
    passed = 0
    failed = 0
    
    for msg, expected in tests:
        result = classifier.classify(msg)
        actual = result["intent"] if result else None
        
        if actual == expected:
            passed += 1
            data = result.get("extracted_data", {}) if result else {}
            test_result(f'"{msg[:42]}"', True, f"{actual}" + (f" data={data}" if data else ""))
        else:
            failed += 1
            test_result(f'"{msg[:42]}"', False, f"got={actual}, want={expected}")
    
    print(f"\n  Score: {passed}/{passed+failed}")
    return failed == 0


# ══════════════════════════════════════════════════════════
#  TEST 2: Data Extraction
# ══════════════════════════════════════════════════════════
def test_data_extraction():
    separator("TEST 2: Data Extraction")
    from core.commander_intents import ExtendedIntentClassifier
    
    classifier = ExtendedIntentClassifier()
    passed = 0
    failed = 0
    
    # Test blog topic extraction
    r = classifier.classify("blog likh about ashwagandha benefits")
    data = r.get("extracted_data", {}) if r else {}
    ok = "topic" in data and "ashwagandha" in data.get("topic", "").lower()
    if test_result("Blog topic extraction", ok, f"topic={data.get('topic')}"):
        passed += 1
    else:
        failed += 1
    
    # Test goal revenue extraction
    r = classifier.classify("goal set karo revenue 12500 blogs 8 social 30")
    data = r.get("extracted_data", {}) if r else {}
    ok = data.get("revenue_target") == 12500
    if test_result("Goal revenue extraction", ok, f"revenue={data.get('revenue_target')}"):
        passed += 1
    else:
        failed += 1
    
    ok = data.get("blog_posts_target") == 8
    if test_result("Goal blog count extraction", ok, f"blogs={data.get('blog_posts_target')}"):
        passed += 1
    else:
        failed += 1
    
    ok = data.get("social_posts_target") == 30
    if test_result("Goal social count extraction", ok, f"social={data.get('social_posts_target')}"):
        passed += 1
    else:
        failed += 1
    
    # Test competitor URL extraction
    r = classifier.classify("competitor analysis karo https://herbsforever.com")
    data = r.get("extracted_data", {}) if r else {}
    ok = data.get("competitor_url") == "https://herbsforever.com"
    if test_result("Competitor URL extraction", ok, f"url={data.get('competitor_url')}"):
        passed += 1
    else:
        failed += 1
    
    # Test bare domain extraction
    r = classifier.classify("competition check karo naturalherbs.com")
    data = r.get("extracted_data", {}) if r else {}
    ok = "naturalherbs.com" in data.get("competitor_url", "")
    if test_result("Competitor bare domain extraction", ok, f"url={data.get('competitor_url')}"):
        passed += 1
    else:
        failed += 1
    
    print(f"\n  Score: {passed}/{passed+failed}")
    return failed == 0


# ══════════════════════════════════════════════════════════
#  TEST 3: Handler Execution (safe handlers only)
# ══════════════════════════════════════════════════════════
def test_handler_execution():
    separator("TEST 3: Handler Execution (safe handlers)")
    
    passed = 0
    failed = 0
    
    # Test goal_set handler
    try:
        from core.commander_intents import IntentResponseHandler
        
        # Create a minimal bridge mock
        class MockBridge:
            def __init__(self):
                self.tools = {}
        
        handler = IntentResponseHandler(MockBridge())
        
        # Test goal_set - no data (should ask for format)
        result = handler.handle_goal_set({
            "intent": "goal_set",
            "extracted_data": {}
        })
        ok = result.get("success") and "Format" in result.get("response", "")
        if test_result("goal_set (no data) -> asks format", ok):
            passed += 1
        else:
            failed += 1
        
        # Test goal_set - with data
        result = handler.handle_goal_set({
            "intent": "goal_set",
            "extracted_data": {"revenue_target": 12500, "blog_posts_target": 8}
        })
        ok = result.get("success") and "12,500" in result.get("response", "")
        if test_result("goal_set (with data) -> sets goals", ok, result.get("response", "")[:60]):
            passed += 1
        else:
            failed += 1
        
        # Test progress_check handler
        result = handler.handle_progress_check({"intent": "progress_check", "extracted_data": {}})
        ok = result.get("response") is not None  # Whether success or fail, should have response
        if test_result("progress_check -> generates report", ok):
            passed += 1
        else:
            failed += 1
        
        # Test profit_report handler
        result = handler.handle_profit_report({"intent": "profit_report", "extracted_data": {}})
        ok = result.get("response") is not None
        if test_result("profit_report -> generates report", ok):
            passed += 1
        else:
            failed += 1
        
        # Test competitor_analysis - no URL (should ask)
        result = handler.handle_competitor_analysis({
            "intent": "competitor_analysis",
            "extracted_data": {}
        })
        ok = result.get("success") and "Kiska" in result.get("response", "")
        if test_result("competitor_analysis (no url) -> asks", ok):
            passed += 1
        else:
            failed += 1
        
        # Test backup handlers
        for method_name, label in [
            ("handle_backup_create", "backup_create"),
            ("handle_backup_list", "backup_list"),
            ("handle_backup_verify", "backup_verify"),
        ]:
            try:
                method = getattr(handler, method_name)
                result = method({"intent": label, "extracted_data": {}})
                ok = result.get("response") is not None
                if test_result(f"{label} -> has response", ok):
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                if test_result(f"{label} -> handler executes", False, str(e)[:60]):
                    passed += 1
                else:
                    failed += 1
        
    except Exception as e:
        test_result("Handler import/init", False, str(e))
        failed += 1
    
    print(f"\n  Score: {passed}/{passed+failed}")
    return failed == 0


# ══════════════════════════════════════════════════════════
#  TEST 4: Core Module Imports
# ══════════════════════════════════════════════════════════
def test_core_modules():
    separator("TEST 4: Core Module Imports")
    
    modules = [
        ("core.memory", "memory"),
        ("core.website_tools", "website_tools"),
        ("core.goal_tracker", "goal_tracker"),
        ("core.profit_tracker", "profit_tracker"),
        ("core.content_generator", "content_generator"),
    ]
    
    passed = 0
    failed = 0
    
    for module_path, instance_name in modules:
        try:
            mod = __import__(module_path, fromlist=[instance_name])
            obj = getattr(mod, instance_name)
            ok = obj is not None
            if test_result(f"{module_path}.{instance_name}", ok, type(obj).__name__):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            test_result(f"{module_path}.{instance_name}", False, str(e)[:60])
            failed += 1
    
    print(f"\n  Score: {passed}/{passed+failed}")
    return failed == 0


# ══════════════════════════════════════════════════════════
#  TEST 5: Agent New Methods
# ══════════════════════════════════════════════════════════
def test_agent_methods():
    separator("TEST 5: Agent New Methods (hasattr)")
    
    checks = [
        ("agents.developer", "DeveloperAgent", ["_full_seo_audit", "_health_claims_audit"]),
        ("agents.strategist", "StrategistAgent", ["_content_calendar", "_deep_competitor_analysis"]),
        ("agents.media", "MediaAgent", ["quick_blog", "quick_social", "quick_product_desc"]),
        ("agents.backup", "BackupAgent", ["quick_snapshot", "quick_list", "quick_verify"]),
    ]
    
    passed = 0
    failed = 0
    
    for module_path, class_name, methods in checks:
        try:
            mod = __import__(module_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            agent = cls()
            for method in methods:
                ok = hasattr(agent, method) and callable(getattr(agent, method))
                if test_result(f"{class_name}.{method}", ok):
                    passed += 1
                else:
                    failed += 1
        except Exception as e:
            test_result(f"{class_name} import", False, str(e)[:60])
            failed += len(methods)
    
    print(f"\n  Score: {passed}/{passed+failed}")
    return failed == 0


# ══════════════════════════════════════════════════════════
#  TEST 6: Memory System
# ══════════════════════════════════════════════════════════
def test_memory():
    separator("TEST 6: Memory System")
    from core.memory import memory
    
    passed = 0
    failed = 0
    
    # Add test messages
    memory.add_message("test_user", "user", "Hello bot!")
    memory.add_message("test_user", "assistant", "Hi there!")
    memory.add_message("test_user", "user", "How are you?")
    
    # Get history
    history = memory.get_history("test_user")
    ok = len(history) >= 3
    if test_result("add_message + get_history", ok, f"history_len={len(history)}"):
        passed += 1
    else:
        failed += 1
    
    # Get context
    memory.set_context("test_user", "last_topic", "herbal tea")
    context = memory.get_context("test_user", "last_topic")
    ok = context == "herbal tea"
    if test_result("get_context", ok, f"value={context}"):
        passed += 1
    else:
        failed += 1
    
    # Get summary
    summary = memory.get_conversation_summary("test_user")
    ok = isinstance(summary, str) and len(summary) > 0
    if test_result("get_conversation_summary", ok):
        passed += 1
    else:
        failed += 1
    
    print(f"\n  Score: {passed}/{passed+failed}")
    return failed == 0


# ══════════════════════════════════════════════════════════
#  TEST 7: Goal Tracker
# ══════════════════════════════════════════════════════════
def test_goal_tracker():
    separator("TEST 7: Goal Tracker")
    from core.goal_tracker import goal_tracker
    
    passed = 0
    failed = 0
    
    # Set goals
    goal_tracker.set_monthly_goals({
        "revenue_target": 12500,
        "blog_posts_target": 8,
        "social_posts_target": 30
    })
    ok = True
    if test_result("set_monthly_goals", ok):
        passed += 1
    else:
        failed += 1
    
    # Log progress
    goal_tracker.log_daily_progress({
        "revenue": 500,
        "blog_posts": 1,
        "social_posts": 3
    })
    ok = True
    if test_result("log_daily_progress", ok):
        passed += 1
    else:
        failed += 1
    
    # Generate report
    report = goal_tracker.generate_daily_report()
    ok = isinstance(report, str) and len(report) > 10
    if test_result("generate_daily_report", ok, f"report_len={len(report)}"):
        passed += 1
    else:
        failed += 1
    
    print(f"\n  Score: {passed}/{passed+failed}")
    return failed == 0


# ══════════════════════════════════════════════════════════
#  TEST 8: Profit Tracker
# ══════════════════════════════════════════════════════════
def test_profit_tracker():
    separator("TEST 8: Profit Tracker")
    from core.profit_tracker import profit_tracker
    
    passed = 0
    failed = 0
    
    # Log revenue
    profit_tracker.log_revenue(1500, "WooCommerce order #1234")
    ok = True
    if test_result("log_revenue", ok):
        passed += 1
    else:
        failed += 1
    
    # Log cost
    profit_tracker.log_cost(200, "Hosting fees")
    ok = True
    if test_result("log_cost", ok):
        passed += 1
    else:
        failed += 1
    
    # Generate report
    report = profit_tracker.generate_profit_report(days=30)
    ok = isinstance(report, str) and len(report) > 10
    if test_result("generate_profit_report", ok, f"report_len={len(report)}"):
        passed += 1
    else:
        failed += 1
    
    print(f"\n  Score: {passed}/{passed+failed}")
    return failed == 0


# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "#"*60)
    print("  PHASE 3: LOCAL MOCK TESTING")
    print("  Falcon Agency — All Systems Check")
    print("#"*60)
    
    start = time.time()
    
    results = {}
    results["1_intents"] = test_intent_classification()
    results["2_extraction"] = test_data_extraction()
    results["3_handlers"] = test_handler_execution()
    results["4_modules"] = test_core_modules()
    results["5_agents"] = test_agent_methods()
    results["6_memory"] = test_memory()
    results["7_goals"] = test_goal_tracker()
    results["8_profit"] = test_profit_tracker()
    
    elapsed = time.time() - start
    
    separator("FINAL RESULTS")
    
    total_pass = 0
    total_fail = 0
    for name, ok in results.items():
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {name}")
        if ok:
            total_pass += 1
        else:
            total_fail += 1
    
    print(f"\n  Total: {total_pass}/{total_pass+total_fail} test groups passed")
    print(f"  Time: {elapsed:.1f}s")
    
    if total_fail == 0:
        print("\n  ALL SYSTEMS GO!")
    else:
        print(f"\n  {total_fail} test group(s) need attention")
    
    print()
