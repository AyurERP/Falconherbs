import requests
from requests.auth import HTTPBasicAuth

url = 'https://falconherbs.com/wp-json/wc/v3/products/categories'
auth = HTTPBasicAuth('ck_88a99d5545e72992b39549aa579ed12b9c248353', 'cs_3c804057f2b3dcbb9da0d9332fcfef3444f78a8a')

for page in range(1, 4):
    params = {'per_page': 100, 'page': page}
    res = requests.get(url, auth=auth, params=params)
    if res.status_code == 200:
        cats = res.json()
        if not cats: break
        for c in cats:
            if 'cardio' in c['name'].lower() or 'wellness' in c['name'].lower() or 'well' in c['name'].lower():
                print(f"ID {c['id']}: {c['name']} (Parent: {c['parent']})")
    else:
        print('Failed:', res.status_code, res.text)
        break
