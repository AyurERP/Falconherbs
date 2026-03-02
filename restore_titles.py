"""
Restore product titles: wellness terms back, banned terms removed.
FSSAI Rules:
  ALLOWED: supports, healthy, wellness, growth, traditional, may support, boosts immunity
  BANNED:  cures, treats, treatment, heals, prevents (disease), clinically proven, FDA approved,
           lower blood sugar, reduces cholesterol, control cholesterol, reduces blood pressure
Run: python -X utf8 restore_titles.py
"""
import sys, io, requests, os
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

load_dotenv()
WOO_URL = os.getenv('WOO_SITE_URL', 'https://falconherbs.com')
KEY = os.getenv('FALCONHERBS_WC_API_KEY')
SECRET = os.getenv('FALCONHERBS_WC_API_SECRET')

# FSSAI-compliant restored titles
# Original -> Cleaned wellness title
RESTORED = {
    7803: "Tulsi Powder 100gm – Supports Immune Wellness",
    7797: "Sitopaladi Powder 100gm – Supports Healthy Respiratory Function",
    7791: "Safed Musli Powder 100gm – Supports Men's Wellness Naturally",
    7778: "Neem Powder 100gm – Supports Healthy Blood Sugar Levels",
    7775: "Licorice Powder 100gm – Promotes Gastric Wellness",
    7758: "Haritaki Powder 100gm – Supports Healthy Immunity",
    7755: "Gurmar Powder 100gm – Supports Healthy Blood Sugar",
    7751: "Giloy Powder 100gm – Supports Immunity & Natural Detox",
    7745: "Dashmool Powder 100gm – Supports Muscle and Joint Wellness",
    7742: "Brahmi Powder 100gm – Supports Healthy Memory & Focus",
    7739: "Bhringraj Powder 100gm – Supports Healthy Hair Growth",
    7735: "Avipattikar Powder 100gm – Supports Digestive Comfort",
    7731: "Ashwagandha Powder 100gm – Supports Stress Relief & Wellness",
    7728: "Arjuna Powder 100gm – Supports Healthy Lipid Levels",
    7725: "Amla Powder 100gm – Supports Hair Growth & Wellness",
    7534: "Valerian Root 100gm | Supports Restful Sleep & Relaxation",
    7512: "Tulsi Leaves 70gm – Organic Herbal Immunity Wellness",
    7506: "Shikakai Pods 100gm | Supports Healthy Hair & Reduces Hair Fall",
    7486: "Naagkesar 100gm | Traditional Ayurvedic Herb for Wellness",
    7479: "Mulethi Sticks 100gm | Traditional Throat & Respiratory Wellness Herb",
    7478: "Neem Leaves 70gm | Rich in Natural Anti-bacterial Properties",
    7448: "Methi Dana 200gm | Supports Digestive Wellness & Appetite",
    7444: "Moringa Seeds 100gm | Supports Liver Wellness & Healthy Digestion",
    7435: "Long Pepper Whole 100gm | Supports Digestive Comfort & Wellness",
    7433: "Kamarkas Raw Herb 200gm | Traditional Ayurvedic Wellness Herb",
    7341: "Kalonji 200gm | Traditional Seed for Immunity & Wellness",
    7323: "Guduchi (Tinospora Cordifolia) 100gm | Organic Immunity Wellness Herb",
    7312: "Ginger Whole 100gm | Traditional Digestive & Wellness Herb",
    7309: "Dry Amla 100gm | Supports Hair & Digestive Wellness",
    7292: "Organic Dry Dates 200gm | Supports Bone Health & Skin Wellness",
    7285: "Black Harde (Haritaki) 100gm | Supports Immunity & Scalp Wellness",
    7204: "Arnica Flowers Whole 70gm | Traditional Topical Wellness Herb",
    7176: "Arjuna Bark 100gm | Traditional Heart Wellness Herb",
    7141: "Aritha Soap Nut 100gm | Natural Hair Wellness & Anti-Dandruff Herb",
    7134: "Alsi Flax Seeds 200gm | High Fiber Seed for Digestive Wellness",
    7068: "Ashwagandha Root Whole 100gm | Traditional Ayurvedic Wellness Herb",
}

import time

print(f"\nRestoring {len(RESTORED)} product titles with FSSAI-compliant wellness terms\n")

success = 0
failed = []

def put_with_retry(pid, new_title, retries=3, timeout=45):
    for attempt in range(retries):
        try:
            return requests.put(
                f'{WOO_URL}/wp-json/wc/v3/products/{pid}',
                auth=(KEY, SECRET),
                json={'name': new_title},
                timeout=timeout
            )
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                print(f'    Timeout, retry {attempt+2}/{retries}...')
                time.sleep(4)
            else:
                raise

for pid, new_title in RESTORED.items():
    try:
        r = put_with_retry(pid, new_title)
        if r.ok:
            print(f'  OK  {pid}: {new_title}')
            success += 1
        else:
            err = f'HTTP {r.status_code}'
            print(f'  FAIL {pid}: {err}')
            failed.append((pid, new_title, err))
    except Exception as e:
        err = str(e)[:80]
        print(f'  FAIL {pid}: {err}')
        failed.append((pid, new_title, err))

print(f'\n========================================')
print(f'Done: {success}/{len(RESTORED)} titles restored')
if failed:
    print(f'Failed ({len(failed)}):')
    for pid, t, e in failed:
        print(f'  {pid}: {e}')
print(f'========================================\n')
