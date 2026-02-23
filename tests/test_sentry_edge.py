# tests/test_sentry_edge.py

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.social_sentry import SocialSentry

def mock_llm(prompt, model):
    return f"[MOCK REPLY - Model: {model}]"

# Initialize with explicit config path
sentry = SocialSentry(llm_caller=mock_llm, config_path="config/clients/falconherbs.yaml")

edge_cases = [
    # Edge 1: Should be DANGER - indirect claim
    "I don't need my blood pressure medicine anymore after using this",
    
    # Edge 2: Should be CAUTION not DANGER - positive but vague  
    "My energy levels improved so much",
    
    # Edge 3: Should be DANGER - Hindi script
    "Ye dawai ne mera diabetes theek kar diya",
    
    # Edge 4: Should be SAFE - question not a claim
    "Can this help with diabetes?",
    
    # Edge 5: Should be CAUTION - implied medical benefit
    "Doctor was surprised by my blood test results after using this",
    
    # Edge 6: Should be DANGER - Hinglish mix
    "Bhai ye sach mein cure karta hai thyroid ko 100%",
    
    # Edge 7: Should be SAFE - general praise
    "Been using for 3 months, feel great overall",
    
    # Edge 8: Empty string
    "",
    
    # Edge 9: Just punctuation
    "!!!",
    
    # Edge 10: Very long comment with danger buried inside
    "Great product, love the taste, easy to consume, " * 5 + "completely cured my cancer",
]

print("=" * 70)
print("SOCIAL SENTRY — EDGE CASE TEST SUITE")
print("=" * 70)

passed = 0
failed = 0

expected = [
    "DANGER",   # Edge 1
    "CAUTION",  # Edge 2
    "DANGER",   # Edge 3
    "SAFE",     # Edge 4
    "CAUTION",  # Edge 5
    "DANGER",   # Edge 6
    "SAFE",     # Edge 7
    "SAFE",     # Edge 8 - empty should not crash
    "SAFE",     # Edge 9 - punctuation only
    "DANGER",   # Edge 10 - buried claim
]

for i, (comment, expect) in enumerate(zip(edge_cases, expected), 1):
    try:
        result = sentry.analyze(comment)
        actual = result["risk"]
        status = "✅ PASS" if actual == expect else "❌ FAIL"
        if actual == expect:
            passed += 1
        else:
            failed += 1
        matched = f"'{result['matched_phrase']}'" if result["matched_phrase"] else "None"
        print(f"{status} | Edge {i:02d} | Expected: {expect:7s} | Got: {actual:7s} | Matched: {matched}")
        if comment == "":
            print(f"         | Comment: [EMPTY STRING]")
        else:
            print(f"         | Comment: {comment[:60]}{'...' if len(comment) > 60 else ''}")
    except Exception as e:
        failed += 1
        print(f"💥 CRASH | Edge {i:02d} | Expected: {expect:7s} | Error: {str(e)}")
    print()

print("=" * 70)
print(f"RESULTS: {passed} passed, {failed} failed out of {len(edge_cases)} tests")
print("=" * 70)
