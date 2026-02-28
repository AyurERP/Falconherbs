# Health Claims Audit — falconherbs.com

**Date:** 25 Feb 2026  
**Scope:** Products, blogs, pages, categories  
**Tool:** Falcon Agency Health Scanner (FDA/FTC risk flagging — not legal advice)

---

## Executive Summary

| Area | Total | Flagged | Status |
|------|-------|---------|--------|
| **Products** | 87 | 46 desc + 15 title | Needs rewrite |
| **Blogs** | 46 | 44 | Needs rewrite |
| **Pages** | 36 | 5 | Needs rewrite |
| **Categories** | 35 | 10 | Needs rename |
| **TOTAL** | ~204 | ~120 violations | Action required |

*Note: Live scan returned 0 (API/connectivity issue). Numbers above from last successful scan.*

---

## 1. What the Scanner Checks

### HIGH RISK (FDA: unapproved drug claims)

- **Disease cure claims:** cures, treats, prevents, heals + disease names
- **Drug claims:** clinically proven, FDA approved, doctor recommended, guaranteed results
- **Specific disease mentions:** cancer, diabetes, anxiety, arthritis, asthma, depression, hypertension, insomnia, eczema, psoriasis, etc.

**Fix:** Remove disease names. Use structure/function claims: "traditionally used to support…", "may help with…"

### MEDIUM RISK (Implied treatment / FTC)

- **Implied treatment:** boosts immunity, fights infection, anti-viral, detoxify, cleanses blood, lowers cholesterol
- **Absolute claims:** 100% natural, no side effects, miracle, instant relief, permanent cure

**Fix:** Rephrase: "supports healthy immune function" instead of "boosts immunity"

### LOW RISK

- **Missing disclaimers:** "These statements have not been evaluated by the FDA"

---

## 2. Top Product Violations (from last scan)

| Product | Issue |
|---------|-------|
| Tulsi Powder – Support Immune System | anxiety |
| Kamarkas Raw Herb | treat mouth ulcers and infection |
| Banafsha viola odorata | — |
| Arnica Flower for Immunity | Boost Your Defenses |
| Terminalia Arjuna | Top 6 Benefits |
| Soap Nut | Top 4 Benefits |
| Flaxseed / Flax Seeds | Top 7 Health Benefits |
| Vasaka Powder | asthma |
| Triphala Powder | prevents viral and bacterial infection |
| Safed Musli | arthritis, physical weakness |
| Ashwagandha Root | anxiety, boost immunity |
| Sugset Paneer Dodi | diabetes |
| Kaali Jeeri | asthma, prevent urinary track infections |
| Rose Petals | reduces anxiety |

---

## 3. Category Renames Needed

| Current Name | Suggested |
|--------------|-----------|
| Cardiovascular | Heart Wellness |
| Diabetic | Wellness Teas |
| Immunity | Immune Support |
| Inflammation, Swelling & Body Pain | Comfort & Mobility |
| Liver Care | Liver Wellness |
| Respiratory Care | Respiratory Wellness |
| Stress, Anxiety & Depression | Calm & Balance |

---

## 4. Safe Alternatives (from scanner)

| Avoid | Use Instead |
|-------|--------------|
| cures | traditionally used to support |
| treats | may help with |
| prevents | traditionally associated with |
| boosts immunity | supports healthy immune function |
| fights infection | supports the body's natural defenses |
| anti-cancer | rich in antioxidants |
| lowers blood sugar | may support healthy blood sugar levels already within normal range |
| anxiety | calm & balance, stress response |
| diabetes | metabolic wellness, glucose support |
| arthritis | joint comfort, mobility |

---

## 5. How to Fix

### Via Falcon Agency (WhatsApp)

1. **"health scan"** — Run fresh audit
2. **"sab fix karo"** — Generate rewrites + apply all (products, blogs, pages, categories)
3. **"rewrite products"** / **"rewrite blogs"** / **"rewrite pages"** — Generate only
4. **"push karo"** — Apply product rewrites via WooCommerce API

### Manual

- **Products:** WooCommerce Admin → Products → Edit → Description / Short Description
- **Blogs/Pages:** WordPress Admin → Posts / Pages → Edit
- **Categories:** WooCommerce → Products → Categories → Rename

---

## 6. Connectivity Note

The live scan returned 0 items from this environment (timeout / API). To get a fresh audit:

- Send **"health scan"** via WhatsApp — the Director runs it on the VPS with API access
- Or run `python scripts/run_health_on_vps.py` on the VPS where `.env` has WooCommerce credentials

---

*This is AI-generated risk flagging, not legal advice. Review with judgment.*
