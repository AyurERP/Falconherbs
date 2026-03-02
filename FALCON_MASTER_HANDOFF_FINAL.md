# 🦅 FALCON AGENCY — MASTER PROJECT CONTEXT (FINAL)
## For Claude IDE / Gemini AI Continuation Session
**Last Updated:** March 1, 2026 (Night)  
**Project Location:** `F:\FALCON AGENCY\`  
**VPS:** `ubuntu@140.245.246.190` (SSH key: `F:\FALCON AGENCY\ssh-key-2026-02-21.key`)

---

## 👤 PROJECT SUMMARY
An **AI Autonomous Digital Marketing Agency** for `falconherbs.com`.
**Director (Sheru):** Orchestrates agents (Chanakya/Strategist, Content, Dev) via WhatsApp/Telegram.
**Core Stack:** Python, SQLite, WooCommerce/WordPress REST API, NVIDIA NIM (Qwen/Llama).

---

## 🛠️ TECH STACK & ARCHITECTURE

- **Memory:** `core/memory.py` (SQLite-backed) — *Recently Fixed*
- **Scanner:** `core/health_scanner.py` — *Aligned with FSSAI Mar 1*
- **Pipeline:** `core/content_pipeline.py` — *Drafts → Staging → WC/WP*
- **Bridge:** `core/integration_bridge.py` — *Unified API caller*
- **Testing:** `local_test.py` + `whatsapp_mock.py`

---

## ✅ COMPLETED WORK (LATE SESSION — MARCH 1)

### 1. ⚖️ FSSAI/Global Compliance Realignment
We shifted from a "nuclear" banning approach to a **Precision Compliance** model based on the `FALCON_GLOBAL_COMPLIANCE_GUIDE.md`.
- **Allowed:** *"Supports immunity"*, *"Healthy digestion"*, *"Traditionally used for"*, *"Wellness"*, *"Energy boost"*.
- **Banned (Strict):** *"Cures"*, *"Treats"*, *"Prevents disease"*, *"Heals"*, *"Clinically proven"*, *"Guaranteed result"*.
- **Hindi Specifics:** Banned terms like *"rog door karta hai"*, *"bimari theek karta hai"*.

### 2. 🧠 core/memory.py Fixes
I fixed the critical bugs that were blocking Sheru's long-term memory:
- **Import Fix:** Resolved `NameError: name 'log' is not defined` by adding proper imports.
- **Migration Fix:** Added sub-step in `_init_db` to check for and add the `message_id` column automatically.
- **Code Snippet:**
```python
# core/memory.py:44
try:
    cursor = conn.execute("PRAGMA table_info(messages)")
    cols = [row[1] for row in cursor.fetchall()]
    if "message_id" not in cols:
        log.info("Migration: Adding 'message_id' column to messages table")
        conn.execute("ALTER TABLE messages ADD COLUMN message_id TEXT")
except Exception as e:
    log.warning("Migration failed: %s", e)
```

### 3. 📄 Source Synchronization
Updated the following core files to reflect the new "Wellness-First" rules:
- **`config/brand_guidelines.json`:** Updated `banned_words`.
- **`config/smart_word_swap.json`:** Cleaned up replacements to prevent "Supportsnatural" type bugs.
- **`core/health_scanner.py` & `core/website_tools.py`:** Removed Low-Risk/Borderline flags for allowed wellness terms.
- **`core/content_pipeline.py`:** Updated AI instructions to separate "Body Function" claims (allowed) from "Disease Claims" (banned).

### 4. 🗃️ Git / Repo Cleanup
- Pushed all core logic changes.
- Committed `fix_titles.py`, `fix_descriptions.py`, and `title_claims_check.py` tools.
- Deleted `data/content/product_rewrites/last_scan.json` to force a fresh scan under new rules.

---

## 🔴 UNFINISHED / ADHOORA KAAM (Next Priority)

### 1. Fresh Health Audit (Priority 1)
Because we deleted the `last_scan.json`, a full `health scan` is needed via WhatsApp. This will confirm that "Supports Immunity" is no longer flagged.

### 2. Restoring 37 Product Titles (Priority 2)
**Status:** Partly done, but needs verification.
**Action:** Compare current live titles with `claims_output.txt`. If you find titles that are too simple (e.g., "Bhringraj Powder 100g"), restore the "Support/Wellness" phrases from the original text in `claims_output.txt`.

### 3. Verify 10 Blog Titles (Priority 3)
A previous "approve all" changed 10 blog titles. They might be overly simplified.
**Action:** Fetch latest blog titles via `IntegrationBridge` and check if they need manual correction for better SEO.

### 4. Batch Progress Updates (Priority 4)
The `approve all` command currently sends one message and then goes silent for 20 minutes while processing.
**Improvement Needed:** Modify the loop to send a WhatsApp update every 10 items (e.g., "✅ 10/97 processed...").

### 5. Memory Integration in Director
While `memory.py` is fixed, `agents/director.py` needs to consistently pull `get_history_text()` for every user input to ensure it doesn't "forget" what was being discussed 2 minutes ago.

---

## 🐞 KNOWN BUGS & ISSUES

1.  **Duplicate "Wellness":** A previous bug caused some categories to be renamed "Wellness Wellness". Most fixed, but scan `Shop by Category` again.
2.  **Stock Management:** 57 products are marked `manage_stock=false` in WooCommerce. The Strategist (Chanakya) cannot track inventory velocity for these.
3.  **Webhook Timeout:** If an AI generation takes >10 seconds, WhatsApp might retry the webhook. Threading is implemented, but progress pings are needed for long tasks.

---

## 📂 DIRECTORY REFERENCE (Critical Paths)
- `C:\Users\Falcon\Downloads\FALCON_GLOBAL_COMPLIANCE_GUIDE.md` (Reference for current rules)
- `f:\FALCON AGENCY\data\reports\` (Latest audit results)
- `f:\FALCON AGENCY\claims_output.txt` (Backup of original product titles)

---
*Created: March 1, 2026 | Prepared for Claude IDE / Gemini AI*
