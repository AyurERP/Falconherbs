"""Quick verification: content_pipeline safety_check fixes."""
import sys, os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
))
from core.content_pipeline import ContentPipeline

p = ContentPipeline()

def check(name, text, fn):
    r = p.safety_check(text)
    ok = fn(r)
    print(("[PASS] " if ok else "[FAIL] ") + name)
    return ok

passed = 0
total  = 0

def t(name, text, fn):
    global passed, total
    total += 1
    if check(name, text, fn):
        passed += 1

# 1. 'cure' inside 'secure' must NOT be corrupted
t("cure inside 'secure' not replaced",
  "Secure packaging with natural ingredients.",
  lambda r: "supporte" not in r["cleaned_content"]
            and "secure" in r["cleaned_content"].lower())

# 2. 'cures diabetes' → specific safe replacement
t("'cures diabetes' replaced correctly",
  "This herb cures diabetes completely.",
  lambda r: "supports healthy blood sugar" in r["cleaned_content"])

# 3. Disease keyword flagged HIGH severity but text preserved
t("'diabetes' flagged HIGH but text preserved",
  "Good for people managing diabetes.",
  lambda r: (
      any(c.get("severity") == "HIGH" for c in r["changes"])
      and "diabetes" in r["cleaned_content"]
  ))

# 4. 'Ayurvedic treatment' must NOT be corrupted
t("'Ayurvedic treatment' not corrupted",
  "Traditional Ayurvedic treatment for joint support.",
  lambda r: "Ayurvedic treatment" in r["cleaned_content"])

# 5. 'boosts immunity' replaced (no duplicate issue)
t("'boosts immunity' replaced",
  "This product boosts immunity naturally.",
  lambda r: "supports healthy immune function" in r["cleaned_content"])

# 6. 'anti-cancer' replaced with antioxidant language
t("'anti-cancer' replaced",
  "Contains anti-cancer compounds.",
  lambda r: "antioxidants" in r["cleaned_content"])

# 7. 'theek ho gaya' replaced with safe Hindi
t("'theek ho gaya' replaced",
  "Customer said: sar dard theek ho gaya.",
  lambda r: "madad" in r["cleaned_content"])

# 8. 'anti-tumor' replaced before 'anti' or 'tumor'
t("'anti-tumor' replaced (longer phrase first)",
  "This compound has anti-tumor properties.",
  lambda r: "cellular function" in r["cleaned_content"])

# 9. 'miracle' replaced (standalone word)
t("'miracle' replaced",
  "This is a miracle product.",
  lambda r: "time-honored" in r["cleaned_content"])

# 10. is_safe False when HIGH severity issue present
t("is_safe=False when disease keyword present",
  "Cures cancer and diabetes permanently.",
  lambda r: r["is_safe"] is False)

print()
print(f"RESULT: {passed}/{total} passed")
if passed == total:
    print("ALL PASS")
else:
    print(f"{total - passed} FAILED")
