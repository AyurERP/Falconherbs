# Falcon Agency — Full Continuation Summary (March 2, 2026)

**Purpose:** Copy this document when switching IDEs or continuing work elsewhere.

---

## QUICK REFERENCE

| Item | Value |
|------|-------|
| **Project** | Falcon Agency — AI-powered digital marketing for falconherbs.com |
| **Tech** | Python 3.11+, FastAPI, SQLite, NVIDIA NIM / OpenRouter, WhatsApp Cloud API |
| **Root** | `F:\FALCON AGENCY` (Windows) / `/home/ubuntu/falcon-agency` (VPS) |
| **Git** | https://github.com/AyurERP/Falconherbs.git, branch `main` |

---

## WHAT WAS DONE TONIGHT (March 2, 2026)

### 1. Pushed 16 Pending Product Descriptions to WooCommerce

All 16 products with `pending_approval` status → pushed to WooCommerce, now `applied`:
- 7068 (Ashwagandha Root Whole), 7309 (Dry Amla), 7324 (Haritaki Dried Whole)
- 7339 (Kaali Jeeri), 7444 (Moringa Seeds), 7527 (Rose Petals)
- 7625 (Turmeric Face Pack), 7690 (Lemon Peel Face Pack), 7742 (Brahmi Powder)
- 7745 (Dashmool Powder), 7769 (Jatamansi Powder), 7772 (Karela Powder)
- 7778 (Neem Powder), 7788 (Rasayan Churan), 7791 (Safed Musli), 7800 (Triphala)

**Note on 7068:** VerifyEngine gave false-negative (tight string comparison); confirmed via direct GET — description IS updated.

**Script:** `push_pending_rewrites.py` (run with `python -X utf8 push_pending_rewrites.py`)

### 2. Fixed Staging Index

- **Before:** 7800 in pending + approved + rejected (conflict)
- **After:** pending=[7739], approved=[7803, 7807], rejected=[7800]
- **File:** `data/staging/rewrites/index.json`

### 3. Title Claims Scan + Fixed 37 Titles

- Ran `title_claims_check.py` → found 37 products with health claims in title
- Ran `fix_titles.py` → AI rewrote all 37 to clean "Herb Name + Weight" format
- All 37 verified by VerifyEngine ✅
- **Exception fix:** Product 7610 — AI incorrectly renamed "Orange Peel" to "Nimbu Powder". Manually corrected to "Orange Peel Herbal 100gm Face Pack" via direct API call.

### 4. New Script Created

- `push_pending_rewrites.py` — pushes all `pending_approval` product descriptions to WooCommerce, marks them `applied`

---

## CURRENT STATE (After Tonight)

| Category | Count | Status |
|----------|-------|--------|
| Product descriptions | **98** | ✅ Applied to WooCommerce |
| Product descriptions | 0 | ⏳ pending_approval |
| Blog posts | 11 | ✅ Applied |
| Staging index | — | ✅ Clean |
| Product titles | 37 | ✅ Fixed tonight |

**Total product rewrites pushed across all sessions: ~98 products**

---

## KNOWN ISSUES / NOTES

### VerifyEngine False Negatives
The VerifyEngine in `woocommerce_connector.update_product()` uses strict string equality for verification. If there are minor formatting differences (trailing whitespace, HTML entity differences), it may report failure even when the update succeeded. Always do a GET check before assuming failure.

### Windows UTF-8 Issue
Always run scripts with `python -X utf8 script.py` on Windows to avoid charmap encoding errors from emoji characters in the connector output.

### Product 7739 (Bhringraj)
Still in staging `pending` — needs staging approval flow run if needed.

---

## REMAINING GAPS (Carry Forward from March 1)

### Immediate
1. Add NVIDIA_API_KEY, SERPER_API_KEY to `.env.example`
2. Time-based messaging — "⏳ Health scan ~40s, wait karo" for long tasks
3. North-star goal — "world #1 ayurvedic site" in `goals.json`

### Short-Term
4. Agent failure → Director report / WhatsApp digest
5. Direct @aeo, @content tags in Commander
6. "Director complaint" intent
7. Health scan vs rewrite pipeline — unify or document

### Medium-Term
8. Test coverage — Commander intents, IntegrationBridge
9. ARCHITECTURE.md — update Flask → FastAPI
10. VerifyEngine — loosen string comparison (strip whitespace, normalize HTML entities)

---

## KEY SCRIPTS

| Script | Purpose | Run |
|--------|---------|-----|
| `push_pending_rewrites.py` | Push pending_approval products to WooCommerce | `python -X utf8 push_pending_rewrites.py` |
| `fix_titles.py` | AI-fix titles from claims_output.txt | `python -X utf8 fix_titles.py` |
| `fix_descriptions.py` | Re-sync applied products | `python -X utf8 fix_descriptions.py` |
| `title_claims_check.py` | Scan all product titles for health claims | `python -X utf8 title_claims_check.py` |

---

## KEY FILES

| File | Purpose |
|------|---------|
| `main.py` | Entry point |
| `core/director.py` | 60s loop, schedule, agents |
| `core/webhook.py` | FastAPI POST /webhook |
| `core/commander.py` | handle_message, intent routing |
| `core/integration_bridge.py` | Central hub |
| `core/health_scanner.py` | Health claims regex + risk |
| `core/health_rewriter.py` | AI rewriter, saves for approval |
| `core/woocommerce_connector.py` | WooCommerce REST |
| `config/profiles/falconherbs.json` | Site profile, credentials |

---

## VPS INFO

- **IP:** ubuntu@140.245.246.190
- **SSH:** `ssh -i "ssh-key-2026-02-21.key" ubuntu@140.245.246.190`
- **Service:** `sudo systemctl restart falcon.service`
- **Webhook:** `https://falconagency.duckdns.org/webhook`

---

## GIT STATUS (Tonight)

- `push_pending_rewrites.py` — new script (uncommitted)
- `data/content/product_rewrites/*.json` — 16 files status changed to 'applied'
- `data/staging/rewrites/index.json` — cleaned up

**Recommend:** Commit all changes, push to main, pull on VPS.

---

## IMPORTANT RULES

- **Never invent data** — DirectorBrain: "NEVER invent, assume, or fabricate"
- **Approval for sensitive actions** — Publish, plugin install → ApprovalSystem
- **Hinglish support** — Owner speaks Hinglish; mirror in replies
- **Compliance** — No "cures"/"treats"; use "traditionally used", "may support"
- **Windows Python** — Always `python -X utf8` to avoid charmap errors

---

*Generated: March 2, 2026 night session*
