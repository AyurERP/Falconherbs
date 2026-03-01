import requests
from requests.auth import HTTPBasicAuth
import json

WP_USER = 'herbsad'
WP_PASS = 'BMlW 3TOt RLuB zz98 J1r7 0U0E'
BASE_URL = 'https://www.falconherbs.com/wp-json'

MENU_ID = 102

TARGETS = [
    {"name": "Zaarah Herbals", "url": "https://www.falconherbs.com/product-category/zaarah-herbals/"},
    {"name": "Khoobsurat Herbals", "url": "https://www.falconherbs.com/product-category/khoobsurat-herbals/"},
    {"name": "Herbal Powders", "url": "https://www.falconherbs.com/product-category/herbal-powders/"},
    {"name": "Ayurvedic Roots", "url": "https://www.falconherbs.com/product-category/ayurvedic-roots/"},
    {"name": "Personal Care", "url": "https://www.falconherbs.com/product-category/personal-care/"},
    {"name": "Diabetic (Sugset)", "url": "https://www.falconherbs.com/product-category/diabetic-sugset/"},
    {"name": "Mouth Freshners", "url": "https://www.falconherbs.com/product-category/mouth-freshners/"},
    {"name": "Chilli, Ginger & Garlic", "url": "https://www.falconherbs.com/product-category/chilli-ginger-garlic/"},
    {"name": "News & Blogs", "url": "https://www.falconherbs.com/category/news-and-blogs/"} # WP post category
]

def run():
    print(f"--- FIFI OMEGA: Forcing Menu {MENU_ID} via Custom Links ---")
    auth_wp = HTTPBasicAuth(WP_USER, WP_PASS)

    # 1. Get current menu items
    print("Step 1: Fetching current menu items...")
    res = requests.get(f"{BASE_URL}/wp/v2/menu-items?menus={MENU_ID}&per_page=100", auth=auth_wp)
    if res.status_code != 200:
        print(f"Failed to fetch menu items. HTTP {res.status_code}: {res.text}")
        return
    
    current_items = res.json()
    print(f"Found {len(current_items)} existing items.")

    # 2. Delete existing items
    print("\nStep 2: Deleting existing items...")
    for item in current_items:
        del_res = requests.delete(f"{BASE_URL}/wp/v2/menu-items/{item['id']}?force=true", auth=auth_wp)
        if del_res.status_code == 200:
            print(f"  Deleted ID: {item['id']}")
        else:
            print(f"  Failed to delete ID {item['id']}")

    # 3. Add Custom Links
    print("\nStep 3: Adding custom links...")
    for idx, t in enumerate(TARGETS, start=1):
        item = {
            "title": t["name"],
            "url": t["url"],
            "status": "publish",
            "menus": MENU_ID,
            "menu_order": idx,
            "type": "custom"
        }
        add_res = requests.post(f"{BASE_URL}/wp/v2/menu-items", auth=auth_wp, json=item)
        if add_res.status_code == 201:
            print(f"  Added: {t['name']} (Order: {idx})")
        else:
            print(f"  Failed: HTTP {add_res.status_code}: {add_res.text}")

    # 4. Verify
    print("\nStep 4: Verify...")
    res_v = requests.get(f"{BASE_URL}/wp/v2/menu-items?menus={MENU_ID}&per_page=100", auth=auth_wp)
    if res_v.status_code == 200:
        for i in sorted(res_v.json(), key=lambda x: x['menu_order']):
            print(f"  {i['menu_order']}. {i['title']['rendered']} -> {i['url']}")

if __name__ == '__main__':
    run()
