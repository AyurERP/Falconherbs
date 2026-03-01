import requests
from requests.auth import HTTPBasicAuth
import json

WC_KEY = 'ck_88a99d5545e72992b39549aa579ed12b9c248353'
WC_SEC = 'cs_3c804057f2b3dcbb9da0d9332fcfef3444f78a8a'
BASE_URL = 'https://www.falconherbs.com/wp-json'

def run():
    auth_wc = HTTPBasicAuth(WC_KEY, WC_SEC)
    
    for page in range(1, 4):
        cats_res = requests.get(f"{BASE_URL}/wc/v3/products/categories?per_page=100&page={page}", auth=auth_wc)
        if cats_res.status_code == 200:
            wc_cats = cats_res.json()
            if not wc_cats: break
            
            for c in wc_cats:
                name = c.get('name', '').lower()
                if ('zaarah' in name or 'khoob' in name or 'zarah' in name or 
                    'sugset' in name or 'diabetic' in name or 
                    'chilli' in name or 'chili' in name or 'ginger' in name or 'garlic' in name):
                    print(f"Found match: {c['name']} (ID: {c['id']}, Slug: {c['slug']})")
        else:
            print("Failed to fetch WC categories.")

if __name__ == '__main__':
    run()
