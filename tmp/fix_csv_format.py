import pandas as pd
import json

with open("tmp/slug_fix_preview.json", "r", encoding="utf-8") as f:
    flagged = json.load(f)

redirects = []
for item in flagged:
    old_slug = item['old_slug']
    new_slug = item['new_slug']
    if old_slug != new_slug:
        redirects.append({
            "source": f"/{old_slug}",
            "destination": f"/{new_slug}",
            "type": 301,
            "matching": "exact",
            "status": "active"
        })

df = pd.DataFrame(redirects)
df.to_csv("tmp/rank_math_redirects_correct.csv", index=False)
print("Saved correct format to tmp/rank_math_redirects_correct.csv")
