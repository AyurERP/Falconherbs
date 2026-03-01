import requests
from requests.auth import HTTPBasicAuth

url = 'https://falconherbs.com/wp-json/wc/v3/products/categories/156'
auth = HTTPBasicAuth('ck_88a99d5545e72992b39549aa579ed12b9c248353', 'cs_3c804057f2b3dcbb9da0d9332fcfef3444f78a8a')

data = {
    'name': 'Cardiovascular Wellness',
    'slug': 'cardiovascular-wellness'
}

res = requests.post(url, auth=auth, json=data)
if res.status_code == 200:
    print('Category 156 updated successfully!')
else:
    print('Failed:', res.status_code, res.text)
