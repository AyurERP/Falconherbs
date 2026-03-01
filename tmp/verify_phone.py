import requests
from bs4 import BeautifulSoup

url = 'https://www.falconherbs.com/'
res = requests.get(url)
if res.status_code == 200:
    soup = BeautifulSoup(res.text, 'html.parser')
    # The subagent mentioned <span>6364590007 | 9916322917, 9844072345</span>
    # Let's search for these numbers
    text = res.text
    if '9844072345.9916322917' in text:
        print("OLD NUMBER DETECTED.")
    if '6364590007 | 9916322917, 9844072345' in text:
        print("NEW NUMBER CONFIRMED.")
    else:
        # Search for fragments
        import re
        matches = re.findall(r'[0-9]{10}', text)
        print("Found numbers:", set(matches))
else:
    print("Failed to fetch page:", res.status_code)
