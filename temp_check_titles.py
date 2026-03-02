import json

with open('data/content/product_rewrites/last_scan.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Products with title violations:")
count = 0
for p in data.get('products', []):
    title_check = p.get('title_safety_check', {})
    if not title_check.get('is_safe', True):
        print(f"- ID {p['id']}: {p['name']}")
        count += 1
print(f"Total: {count}")
