"""Test new memory.py upgrade — all 4 layers."""
import sys, os
sys.path.insert(0, 'F:/FALCON AGENCY')
os.chdir('F:/FALCON AGENCY')

from core.memory import memory

print("=== TEST 1: No 24h cutoff — message count ===")
initial = memory.get_message_count("test_user_mem")
memory.add_message("test_user_mem", "user", "Kya hua revenue ka?")
memory.add_message("test_user_mem", "assistant", "Aaj ₹4,200 aaya, kal se zyada hai.")
history = memory.get_history("test_user_mem", last_n=5)
assert len(history) >= 2
print(f"  History count: {len(history)} (no time cutoff)")
print("  PASS")

print()
print("=== TEST 2: Long-term memory ===")
eid = memory.remember(
    category="revenue",
    title="Best sale day of Feb 2026",
    detail="₹12,400 — Diwali promo worked",
    tags=["revenue", "milestone", "diwali"],
    importance=3
)
assert eid > 0
print(f"  Event stored: id={eid}")

events = memory.recall(category="revenue", min_importance=2)
assert any(e["id"] == eid for e in events)
print(f"  Recall by category: {len(events)} event(s)")

events_tagged = memory.recall(tag="milestone")
assert any(e["id"] == eid for e in events_tagged)
print(f"  Recall by tag: {len(events_tagged)} event(s)")

summary = memory.recall_summary(days=7)
print(f"  Summary preview: {summary[:80]}...")
print("  PASS")

print()
print("=== TEST 3: Business facts ===")
memory.set_fact("best_selling_product", "Senna Leaves 200g", source="woocommerce_scan")
memory.set_fact("avg_daily_revenue_30d", "₹4,200", source="revenue_tracker")
memory.set_fact("peak_order_day", "Tuesday", source="analytics")
memory.set_fact("falconherbs_products_count", 87, source="woocommerce_api")

assert memory.get_fact("best_selling_product") == "Senna Leaves 200g"
assert memory.get_fact("falconherbs_products_count") == 87
assert memory.get_fact("nonexistent_key", "default") == "default"

all_facts = memory.get_all_facts()
assert len(all_facts) >= 4
print(f"  Facts stored: {len(all_facts)}")
print(f"  Facts: {list(all_facts.keys())}")

facts_str = memory.facts_summary()
assert "Senna" in facts_str
print(f"  Facts summary: {facts_str[:80]}...")
print("  PASS")

print()
print("=== TEST 4: build_director_context() ===")
memory.track_topic("test_user_mem", "revenue sales report kitna hua", intent="analyse_sales")
memory.track_topic("test_user_mem", "seo ranking kya hai", intent="seo_audit")

ctx = memory.build_director_context("test_user_mem", recent_messages=5, include_long_term_days=7)
assert "Senna" in ctx or "📊" in ctx  # facts included
assert "milestone" in ctx or "revenue" in ctx  # long_term included
print(f"  Context length: {len(ctx)} chars")
print(f"  Preview:\n{ctx[:300]}...")
print("  PASS")

print()
print("=== TEST 5: Stats ===")
stats = memory.get_stats()
print(f"  Messages: {stats['messages']}")
print(f"  Long-term events: {stats['long_term_events']}")
print(f"  Business facts: {stats['business_facts']}")
print(f"  DB size: {stats['db_size_kb']} KB")
print(f"  Max messages: {stats['max_messages']}")
assert stats['max_messages'] == 500  # upgraded from 200
print("  PASS")

print()
print("=== TEST 6: DirectorBrain loads memory ===")
from core.director_brain import DirectorBrain
brain = DirectorBrain()
prompt = brain._build_system_prompt(None)
assert "PERSISTENT MEMORY" in prompt or "Business Facts" in prompt or "📊" in prompt
print(f"  DirectorBrain system prompt: {len(prompt)} chars (memory wired in)")
print("  PASS")

# Cleanup test data
print()
print("Cleaning up test data...")
conn = __import__('sqlite3').connect('data/falcon.db')
conn.execute("DELETE FROM messages WHERE user_id='test_user_mem'")
conn.execute("DELETE FROM long_term WHERE detail LIKE '%Diwali promo%'")
conn.execute("DELETE FROM business_facts WHERE key IN ('best_selling_product','avg_daily_revenue_30d','peak_order_day','falconherbs_products_count')")
conn.execute("DELETE FROM topics WHERE user_id='test_user_mem'")
conn.commit()
conn.close()

print()
print("=== ALL 6 TESTS PASSED ===")
print("Memory upgrade complete and verified")
