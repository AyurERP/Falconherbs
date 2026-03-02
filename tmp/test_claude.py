"""Test Claude API integration live."""
import sys, os
sys.path.insert(0, 'F:/FALCON AGENCY')
os.chdir('F:/FALCON AGENCY')

print("=== TEST 1: Keys loaded ===")
from config.keys import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, AI_MODELS
assert ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.startswith("sk-ant"), \
    f"Key missing or wrong format: {ANTHROPIC_API_KEY[:10]}..."
print(f"  Key: {ANTHROPIC_API_KEY[:12]}...{ANTHROPIC_API_KEY[-4:]}")
print(f"  URL: {ANTHROPIC_BASE_URL}")
print("  PASS")

print()
print("=== TEST 2: Model assignments ===")
claude_roles = ['strategist','media','content','health_rewriter','aeo']
for role in claude_roles:
    m = AI_MODELS.get(role,'')
    assert m.startswith('cl::'), f"{role} not Claude: {m}"
    print(f"  {role:20s} → {m}")
print("  PASS")

print()
print("=== TEST 3: _call_anthropic() function exists ===")
from core.ai_client import _call_anthropic
print(f"  _call_anthropic: {_call_anthropic}")
print("  PASS")

print()
print("=== TEST 4: Live API call — Claude 3.5 Haiku ===")
from core.ai_client import call_ai
result = call_ai(
    "media",
    [{"role": "user", "content": "Say exactly: 'Falcon Agency Claude integration successful!' — nothing else."}],
    max_tokens=50,
    timeout=30,
)
print(f"  Response: {result}")
assert "AI_ERROR" not in result, f"API call failed: {result}"
assert len(result) > 5
print("  PASS — Claude 3.5 Haiku responding!")

print()
print("=== TEST 5: Live API call — Claude 3.5 Sonnet (strategist) ===")
result2 = call_ai(
    "strategist",
    [{"role": "user", "content": "In one sentence, what is falconherbs.com?"}],
    max_tokens=80,
    timeout=30,
)
print(f"  Response: {result2}")
assert "AI_ERROR" not in result2
print("  PASS — Claude 3.5 Sonnet responding!")

print()
print("=== ALL 5 TESTS PASSED ===")
print("Claude fully integrated into Falcon Agency!")
