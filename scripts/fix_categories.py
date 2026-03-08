"""
Falcon Agency — Create Brand Categories & Clean Up
====================================================
1. Creates missing brand categories: Zaarah, Khoobsurat, Sugset, Mast, Unbranded
2. Assigns matching products to each brand
3. Deletes the fake 'Chilli, Ginger & Garlic' category

Brand Structure:
  Zaarah Herbals    → ~26 herbal powder products
  Khoobsurat Herbals → 10-11 face packs + hair packs (Personal Care)
  Diabetic (Sugset)  → Sugset brand diabetic wellness products
  Mast               → 19-20 mouth fresheners, mukhwas, confectionery
  Unbranded          → placeholder for future local Indian products

Usage:
    python scripts/fix_categories.py           # dry-run
    python scripts/fix_categories.py --apply   # create + assign + delete
"""

import sys, os, json, time, re, requests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv; load_dotenv()
from core.woocommerce_connector import WooCommerceConnector


CATEGORIES_TO_CREATE = [
    {
        "name": "Zaarah Herbals",
        "slug": "zaarah-herbals",
        "description": "Premium Ayurvedic herbal powders by Zaarah Herbals. Pure, traditionally sourced herb powders for daily wellness — from Ashwagandha to Triphala.",
        "parent": 0,
        "match_cat_names": ["Herbal Powders", "Digestion", "Immunity",
                            "Hair Care", "Skin Care", "Cardiovascular Wellness",
                            "Calm & Balance", "Digestive Wellness",
                            "Joint & Muscle Wellness", "Liver Care", "Respiratory Care",
                            "Weight Management"],
        "exclude_cat_names": ["Ayurvedic Roots", "Mouth Freshners", "Freshners", "Mukhwas",
                              "Personal Care", "Face Packs", "Hair Packs"],
    },
    {
        "name": "Khoobsurat Herbals",
        "slug": "khoobsurat-herbals",
        "description": "Natural personal care products by Khoobsurat Herbals. Premium face packs, hair packs, and herbal skincare essentials for radiant beauty.",
        "parent": 0,
        "match_cat_names": ["Personal Care", "Face Packs", "Hair Packs"],
    },
    {
        "name": "Diabetic (Sugset)",
        "slug": "diabetic-sugset",
        "description": "Sugset brand Ayurvedic products for blood sugar wellness. Traditional herbs that support healthy glucose levels naturally.",
        "parent": 0,
        "match_cat_names": ["Wellness"],
        "match_names": ["sugset"],
    },
    {
        "name": "Mast",
        "slug": "mast",
        "description": "Mast brand mouth fresheners, mukhwas, and confectionery. Premium blends of traditional Indian flavors — from Banarasi Paan to Kesari Saunf.",
        "parent": 0,
        "match_cat_names": ["Mouth Freshners", "Freshners", "Mukhwas"],
    },
    {
        "name": "Unbranded",
        "slug": "unbranded",
        "description": "Local Indian products — traditional herbs, spices, and wellness essentials. Sourced directly from farms across India.",
        "parent": 0,
        # No auto-matching — this is a placeholder for future products
    },
]

# Categories to DELETE (fake/wrong categories)
CATEGORIES_TO_DELETE = ["chilli-ginger-garlic"]


def find_matching_products(products, cat_def):
    """Find products matching by category names, with exclusion support."""
    matched = []
    match_cat_names = set(cat_def.get("match_cat_names", []))
    exclude_cat_names = set(cat_def.get("exclude_cat_names", []))
    match_names = cat_def.get("match_names", [])

    for p in products:
        name_lower = p.get("name", "").lower()
        raw_cats = p.get("categories", [])
        prod_cat_names = set()
        for c in raw_cats:
            if isinstance(c, dict):
                prod_cat_names.add(c.get("name", ""))
            elif isinstance(c, str):
                prod_cat_names.add(c)

        # Skip if product belongs to an excluded brand/category
        if exclude_cat_names and exclude_cat_names & prod_cat_names:
            continue

        # Match by category name
        if match_cat_names and match_cat_names & prod_cat_names:
            matched.append(p)
            continue

        # Match by product name keywords
        for kw in match_names:
            if kw in name_lower:
                matched.append(p)
                break

    return matched


def main():
    apply_mode = "--apply" in sys.argv

    woo = WooCommerceConnector()
    site = woo.site_url.rstrip("/")
    ck = woo.consumer_key
    cs = woo.consumer_secret

    print("=" * 65)
    print("FALCON AGENCY - Brand Category Fix")
    print("=" * 65)
    print(f"  Mode: {'APPLY (LIVE)' if apply_mode else 'DRY RUN'}")

    # Fetch products
    result = woo.get_all_products(save=False)
    products = result["data"]["products"] if result.get("success") else []
    print(f"  Products loaded: {len(products)}")

    # Fetch existing categories
    cats_result = woo.get_wc_categories()
    existing = {}
    if cats_result.get("success"):
        existing = {c["slug"]: c for c in cats_result["data"]}
    print(f"  Existing categories: {len(existing)}")

    results = {"created": 0, "assigned": 0, "skipped": 0, "failed": 0, "deleted": 0}

    # ═══ PART 1: CREATE BRAND CATEGORIES ═══
    print("\n" + "=" * 65)
    print("PART 1: Create Brand Categories")
    print("=" * 65)

    for cat_def in CATEGORIES_TO_CREATE:
        slug = cat_def["slug"]
        name = cat_def["name"]

        print(f"\n  [{name}] (/{slug}/)")

        if slug in existing:
            print(f"    Already exists (ID: {existing[slug]['id']}) - skipping")
            results["skipped"] += 1
            continue

        # Find matching products
        matched = find_matching_products(products, cat_def)
        print(f"    Products to assign: {len(matched)}")
        for p in matched[:5]:
            print(f"      - {p['name'][:55]}")
        if len(matched) > 5:
            print(f"      ... and {len(matched) - 5} more")

        if apply_mode:
            try:
                api_url = f"{site}/wp-json/wc/v3/products/categories"
                r = requests.post(
                    api_url,
                    json={"name": name, "slug": slug, "description": cat_def["description"]},
                    auth=(ck, cs), timeout=30,
                )
                if r.ok:
                    new_id = r.json().get("id")
                    print(f"    Created: ID {new_id}")
                    results["created"] += 1

                    # Assign products
                    for p in matched:
                        pid = p["id"]
                        current_cats = [c["id"] for c in p.get("categories", []) if isinstance(c, dict)]
                        if new_id not in current_cats:
                            current_cats.append(new_id)
                            try:
                                res = woo.update_product(pid, {"categories": [{"id": cid} for cid in current_cats]}, verify=False)
                                if res.get("success"):
                                    results["assigned"] += 1
                                else:
                                    results["failed"] += 1
                            except:
                                results["failed"] += 1
                            time.sleep(1)
                else:
                    print(f"    FAILED: {r.status_code} - {r.text[:80]}")
                    results["failed"] += 1
            except Exception as e:
                print(f"    ERROR: {e}")
                results["failed"] += 1
        else:
            print(f"    [DRY RUN] Would create + assign {len(matched)} products")

    # ═══ PART 2: DELETE FAKE CATEGORIES ═══
    print("\n" + "=" * 65)
    print("PART 2: Delete Fake Categories")
    print("=" * 65)

    for slug in CATEGORIES_TO_DELETE:
        if slug in existing:
            cat_id = existing[slug]["id"]
            cat_name = existing[slug]["name"]
            print(f"\n  Deleting: {cat_name} (/{slug}/) ID:{cat_id}")
            if apply_mode:
                try:
                    r = requests.delete(
                        f"{site}/wp-json/wc/v3/products/categories/{cat_id}",
                        params={"force": True},
                        auth=(ck, cs), timeout=30,
                    )
                    if r.ok:
                        print(f"    Deleted OK")
                        results["deleted"] += 1
                    else:
                        print(f"    FAILED: {r.status_code}")
                        results["failed"] += 1
                except Exception as e:
                    print(f"    ERROR: {e}")
            else:
                print(f"    [DRY RUN] Would delete")
        else:
            print(f"\n  {slug}: not found - already deleted or never existed")

    # ═══ SUMMARY ═══
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"  Categories created: {results['created']}")
    print(f"  Products assigned:  {results['assigned']}")
    print(f"  Categories deleted: {results['deleted']}")
    print(f"  Skipped:           {results['skipped']}")
    print(f"  Failed:            {results['failed']}")
    if not apply_mode:
        print(f"\n  To apply: python scripts/fix_categories.py --apply")
    print("=" * 65)


if __name__ == "__main__":
    main()
