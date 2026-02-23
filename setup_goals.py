"""
Phase 5: 30-Day Goal Setup
Sets goals for falconherbs.com and zaarahherbals.com
Run: python3 setup_goals.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.goal_tracker import goal_tracker
from core.profit_tracker import profit_tracker

print("=" * 50)
print("  PHASE 5: 30-DAY GOAL SETUP")
print("=" * 50)

# ── FALCONHERBS.COM Goals ──
print("\n1. Setting FALCONHERBS.COM goals...")
goal_tracker.set_monthly_goals({
    "site": "falconherbs.com",
    "revenue_target": 12500,
    "blog_posts_target": 8,
    "social_posts_target": 30,
    "seo_score_target": 75,
    "health_claims_fixed": True,
    "currency": "INR"
})
print("   Revenue: Rs.12,500")
print("   Blog Posts: 8")
print("   Social Posts: 30")
print("   SEO Score: 75+")
print("   Health Claims: 100% Fixed")

# ── ZAARAHHERBALS.COM Goals ──
print("\n2. Setting ZAARAHHERBALS.COM goals...")
goal_tracker.set_monthly_goals({
    "site": "zaarahherbals.com",
    "revenue_target": 500,
    "blog_posts_target": 6,
    "social_posts_target": 25,
    "seo_score_target": 75,
    "currency": "USD"
})
print("   Revenue: $500")
print("   Blog Posts: 6")
print("   Social Posts: 25")
print("   SEO Score: 75+")

# ── Initial Progress Entry ──
print("\n3. Logging Day 1 progress (baseline)...")
goal_tracker.log_daily_progress({
    "site": "falconherbs.com",
    "revenue": 0,
    "blog_posts": 0,
    "social_posts": 0,
    "seo_score": 0,
    "day": 1
})
print("   Day 1 baseline logged")

# ── Initial Profit Entry ──
print("\n4. Initializing profit tracker...")
profit_tracker.log_revenue(0, "Day 1 baseline - falconherbs.com")
profit_tracker.log_cost(0, "Day 1 baseline - no costs yet")
print("   Profit tracker initialized")

# ── Generate First Report ──
print("\n5. Generating Day 1 report...")
report = goal_tracker.generate_daily_report()
print("\n" + report[:800])

print("\n" + "=" * 50)
print("  GOALS SET! Phase 5 Complete!")
print("=" * 50)
print("\nWhatsApp pe test karo:")
print('  "progress dikhao"')
print('  "profit report bhejo"')
print('  "goal set karo revenue 12500"')
