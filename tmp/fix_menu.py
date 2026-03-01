import requests
from requests.auth import HTTPBasicAuth
import json

WP_USER = 'herbsad'
WP_PASS = 'BMlW 3TOt RLuB zz98 J1r7 0U0E'
WC_KEY = 'ck_88a99d5545e72992b39549aa579ed12b9c248353'
WC_SEC = 'cs_3c804057f2b3dcbb9da0d9332fcfef3444f78a8a'
BASE_URL = 'https://www.falconherbs.com/wp-json'

MENU_ID = 102

TARGET_CATEGORIES = [
    "Zaarah Herbals",
    "Khoobsurat Herbals",
    "Herbal Powders",
    "Ayurvedic Roots",
    "Personal Care",
    "Diabetic",
    "Mouth",
    "Chilli"
]

def run():
    print(f"--- FIFI OMEGA: Fixing Menu {MENU_ID} ---")
    auth_wp = HTTPBasicAuth(WP_USER, WP_PASS)
    auth_wc = HTTPBasicAuth(WC_KEY, WC_SEC)

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
            print(f"  Deleted: {item['title']['rendered']} (ID: {item['id']})")
        else:
            print(f"  Failed to delete ID {item['id']}: HTTP {del_res.status_code}")
            return

    # 3. Get WC Categories
    print("\nStep 3: Fetching WooCommerce Categories...")
    cats_res = requests.get(f"{BASE_URL}/wc/v3/products/categories?per_page=100", auth=auth_wc)
    if cats_res.status_code != 200:
        print(f"Failed to fetch WC categories. HTTP {cats_res.status_code}")
        return
    
    wc_cats = cats_res.json()
    
    # Map target categories to IDs
    menu_items_to_add = []
    
    # Custom titles mapping
    titles = {
        "Zaarah Herbals": "Zaarah Herbals",
        "Khoobsurat Herbals": "Khoobsurat Herbals",
        "Herbal Powders": "Herbal Powders",
        "Ayurvedic Roots": "Ayurvedic Roots",
        "Personal Care": "Personal Care",
        "Diabetic": "Diabetic (Sugset)",
        "Mouth": "Mouth Freshners",
        "Chilli": "Chilli, Ginger & Garlic"
    }
    
    for target in TARGET_CATEGORIES:
        found = False
        for c in wc_cats:
            if target.lower() in c['name'].lower():
                menu_items_to_add.append({
                    "title": titles[target],
                    "url": f"https://www.falconherbs.com/product-category/{c['slug']}/",
                    "status": "publish",
                    "menus": MENU_ID,
                    "type": "taxonomy", # Fallback custom supported by changing this
                    "object": "product_cat",
                    "object_id": c['id']
                })
                found = True
                print(f"  Found WC Cat: {c['name']} (ID: {c['id']}) mapped to '{titles[target]}'")
                break
        if not found:
            print(f"  WARNING: Could not find WC category matching '{target}'")

    # Get Post Category for News & Blogs
    print("\nStep 3b: Fetching WP Post Categories...")
    post_cats_res = requests.get(f"{BASE_URL}/wp/v2/categories?per_page=100", auth=auth_wp)
    if post_cats_res.status_code == 200:
        post_cats = post_cats_res.json()
        for c in post_cats:
            if "news" in c['name'].lower() or "blog" in c['name'].lower():
                menu_items_to_add.append({
                    "title": "News & Blogs",
                    "url": f"https://www.falconherbs.com/category/{c['slug']}/",
                    "status": "publish",
                    "menus": MENU_ID,
                    "type": "taxonomy",
                    "object": "category",
                    "object_id": c['id']
                })
                print(f"  Found Post Cat: {c['name']} (ID: {c['id']})")
                break
    else:
        print("  Failed to fetch WP categories.")

    # 4. Add new items
    print("\nStep 4: Adding new menu items...")
    for idx, item in enumerate(menu_items_to_add, start=1):
        item["menu_order"] = idx
        add_res = requests.post(f"{BASE_URL}/wp/v2/menu-items", auth=auth_wp, json=item)
        if add_res.status_code == 201:
            print(f"  Added: {item['title']} (Order: {idx})")
        else:
            print(f"  Failed add. Try custom link fallback for {item['title']}...")
            # Fallback
            fb_item = {
                "title": item['title'],
                "url": item['url'],
                "status": "publish",
                "menus": MENU_ID,
                "menu_order": idx,
                "type": "custom"
            }
            fb_res = requests.post(f"{BASE_URL}/wp/v2/menu-items", auth=auth_wp, json=fb_item)
            if fb_res.status_code == 201:
                print(f"    Fallback Added successfully: {item['title']}")
            else:
                print(f"    Fallback Failed: HTTP {fb_res.status_code}: {fb_res.text}")

    # 5. Verify
    print("\nStep 5: Verifying final menu state...")
    verify_res = requests.get(f"{BASE_URL}/wp/v2/menu-items?menus={MENU_ID}&per_page=100", auth=auth_wp)
    if verify_res.status_code == 200:
        final_items = verify_res.json()
        print(f"Total items in Menu {MENU_ID}: {len(final_items)}")
        for i in sorted(final_items, key=lambda x: x['menu_order']):
            print(f"  {i['menu_order']}. {i['title']['rendered']}")
    else:
        print("Verification failed.")

if __name__ == '__main__':
    run()
