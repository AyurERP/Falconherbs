"""
Section 5 test: _is_likely_brand() logic validation
Run: python tests/test_brand_filter.py
"""
import sys, os, types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock external deps so no real API keys needed
yaml_mod = types.ModuleType('yaml')
yaml_mod.safe_load = lambda f: {}
sys.modules.setdefault('yaml', yaml_mod)

gapi = types.ModuleType('googleapiclient')
gapi_disc = types.ModuleType('googleapiclient.discovery')
gapi_disc.build = lambda *a, **k: None
gapi_errors = types.ModuleType('googleapiclient.errors')
class HttpError(Exception): pass
gapi_errors.HttpError = HttpError
sys.modules.setdefault('googleapiclient', gapi)
sys.modules.setdefault('googleapiclient.discovery', gapi_disc)
sys.modules.setdefault('googleapiclient.errors', gapi_errors)

from agents.pr_outreach import PROutreach

# Bare instance — no real config needed
agent = PROutreach.__new__(PROutreach)
agent.api_key = ''
agent.min_subs = 5000
agent.max_results = 8
agent.youtube = None
agent.config = {}


def get_reason(name, desc, subs):
    """Trace which signal fired — for test output."""
    name_l = name.lower()
    desc_l = desc.lower()

    corporate_keywords = [
        "pvt ltd", "pvt. ltd", "private limited",
        "inc.", " inc ", "corporation", "corp.",
        "enterprise", "enterprises", "official channel",
        "official page", " company", " co."
    ]
    for kw in corporate_keywords:
        if kw in name_l:
            return 'corporate_keywords ("{}")'.format(kw)

    known_brands = [
        "patanjali", "himalaya", "dabur", "baidyanath",
        "zandu", "hamdard", "charak", "kerala ayurveda",
        "kama ayurveda", "forest essentials", "biotique"
    ]
    for brand in known_brands:
        if brand in name_l:
            return 'known_brands ("{}")'.format(brand)

    business_signals = [
        "our company", "our brand", "we manufacture",
        "buy now", "shop now",
        "established in 19", "established in 20",
        "gst no", "cin no", "iso certified"
    ]
    for sig in business_signals:
        if sig in desc_l:
            return 'business_signals ("{}")'.format(sig)

    personal_pronouns = [
        "i am", "i'm", "my journey", "my story",
        "main hoon", "mera naam", "myself"
    ]
    if subs > 500000:
        if not any(p in desc_l for p in personal_pronouns):
            return "large_impersonal (subs={})".format(subs)

    return "no signal fired"


# ---- Section 5 test cases ----
test_cases = [
    ("Patanjali Ayurved",        "", 0),   # FILTERED - known_brands
    ("Himalaya Wellness",         "", 0),   # FILTERED - known_brands
    ("Dr. Priya Sharma Ayurveda", "", 0),   # KEPT
    ("The Ayurveda Company",      "", 0),   # FILTERED - corporate_keywords
    ("Ayurveda With Nidhi",       "", 0),   # KEPT
    ("Wellness With Kavita",      "", 0),   # KEPT
    ("Ayurveda Inc.",             "", 0),   # FILTERED - corporate_keywords
    ("My Wellness Journey",       "", 0),   # KEPT
]

expected = [True, True, False, True, False, False, True, False]

print("--- _is_likely_brand() test results ---\n")

all_pass = True
for i, (name, desc, subs) in enumerate(test_cases):
    cd = {"title": name, "description": desc, "subscriberCount": subs}
    result = agent._is_likely_brand(cd)
    label = "FILTERED" if result else "KEPT"
    reason = get_reason(name, desc, subs) if result else "-"
    exp = expected[i]
    status = "PASS" if result == exp else "FAIL"
    if result != exp:
        all_pass = False
    print('  [{}] "{}" -> {} | Reason: {}'.format(
        status, name, label, reason
    ))

print()
print("OVERALL:", "ALL 8 PASS" if all_pass else "SOME TESTS FAILED")
sys.exit(0 if all_pass else 1)
