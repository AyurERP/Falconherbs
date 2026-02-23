# tests/test_sentry.py

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.social_sentry import SocialSentry

def mock_llm(prompt, model):
    """Mock LLM response for testing"""
    return (
        "Thank you for sharing your experience! Individual experiences may vary. "
        "Our products are traditional Ayurvedic formulations. "
        "For serious concerns, please consult a healthcare professional."
    )

def run_tests():
    # Initialize with mock LLM and explicit config path
    sentry = SocialSentry(llm_caller=mock_llm, config_path="config/clients/falconherbs.yaml")

    test_comments = [
        # DANGER (English)
        "This product cured my diabetes completely",
        "I stopped my insulin after using this",
        "No more thyroid medicine needed!!",
        "100% cure for cancer",
        "This treat my diabetes instantly",
        
        # DANGER (Hindi/Hinglish)
        "Ye dawai lene ke baad diabetes theek ho gaya",
        "Mera cancer theek ho gaya",
        "Ab doctor ki jarurat nahi hai",
        "Diabetes theek karne ka pakka ilaj",
        
        # CAUTION
        "Really helped my digestion issues",
        "My joint pain disappeared after 2 weeks",
        "Works better than allopathy medicines",
        "Miracle product for immunity",
        
        # SAFE
        "Love the packaging!",
        "Fast delivery, thank you",
        "Which flavor is best?",
        "Price is very reasonable",
        "Can you ship to Dubai?",
    ]

    print("=" * 70)
    print(f"{'RISK':8s} | {'PHRASE':20s} | {'COMMENT'}")
    print("-" * 70)

    stats = {"DANGER": 0, "CAUTION": 0, "SAFE": 0}

    for comment in test_comments:
        result = sentry.analyze(comment)
        risk = result["risk"]
        matched = result["matched_phrase"] or "-"
        
        stats[risk] += 1
        
        emoji = {"DANGER": "🔴", "CAUTION": "🟡", "SAFE": "✅"}[risk]
        print(f"{emoji} {risk:7s} | {matched[:20]:20s} | {comment[:40]}...")

    print("=" * 70)
    print("SUMMARY")
    print(f"Total: {len(test_comments)}")
    for r, count in stats.items():
        print(f"{r:8s}: {count}")
    print("=" * 70)

    # Verification checks
    assert stats["DANGER"] >= 9, "DANGER cases missed"
    assert stats["CAUTION"] >= 4, "CAUTION cases missed"
    assert stats["SAFE"] >= 5, "SAFE cases incorrectly flagged"
    
    print("\n✅ ALL TEST CASES PASSED!")

if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
