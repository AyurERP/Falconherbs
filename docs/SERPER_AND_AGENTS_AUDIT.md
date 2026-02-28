# Serper & Agents Audit — Falcon Agency

**Date:** 2025-02  
**Purpose:** Serper usage, agent wiring, quota utilization, quality before Monday launch.

---

## 1. Serper API

| Item | Value |
|------|-------|
| **Limit** | 2,500 searches/month (free tier) |
| **Reset** | Monthly |
| **Cost after** | ~$1/1000 queries |

### Who Uses Serper

| Caller | When | Est./month |
|--------|------|------------|
| **Commander** | User asks with "trending", "kya chal raha", "abhi kya", "google", "search" | 5–50 |
| **AEOAgent** | Monthly scan (25 questions) | 25 |
| **weekly_trending_scan** | Friday 12:00 — 5 ayurveda/herbal queries | 20 |
| **Total** | | ~50–95 |

### Changes Made

1. **`core/serper_client.py`** — Central client with usage tracking
2. **Commander** — Uses `search_text()` from serper_client
3. **AEOAgent** — Uses `search()` from serper_client
4. **weekly_trending_scan** — New Friday task, 5 Serper calls
5. **Usage file** — `data/serper_usage.json` (month, count, last 100 calls)
6. **State** — Serper usage in Director context (`X/2500 this month`)

### Quota Strategy

- AEO: 25/month
- Weekly trending: 20/month
- Commander (on-demand): rest of quota
- "Month end waste" — weekly trending + Commander use remaining quota

---

## 2. Agent Wiring

| Agent | Serper | Notes |
|-------|--------|-------|
| Commander | ✅ | Question handler, trigger words |
| AEOAgent | ✅ | Monthly scan |
| Strategist | ❌ | Uses direct Google scrape (no Serper) |
| Content Producer | ❌ | No search |
| Media/Designer | ❌ | No search |

**Strategist:** Uses `requests.get("google.com/search")` — can hit rate limits. Future: switch to Serper for keyword/SERP checks.

---

## 3. AI Break / Cooldown

**Idea:** After heavy tasks, system can "rest" before next heavy work.

**Heavy tasks:** AEO scan (~30s), health scan (~40s), full store audit.

**Current:** Schedule already spaces tasks (AEO monthly, others daily/weekly). No extra cooldown.

**Optional:** Add `data/cooldown.json` and skip next heavy task if last heavy was &lt; 10 min ago. Not implemented — can add if needed.

---

## 4. Quality Checklist (Monday)

- [ ] Director responds to prompts
- [ ] Health scan runs
- [ ] AEO scan runs (needs SERPER + NVIDIA keys)
- [ ] Weekly trending runs Friday 12:00
- [ ] Serper usage visible in state ("meri website ka kya haal")
- [ ] No duplicate Serper calls (single client)
- [ ] `data/serper_usage.json` updates correctly

---

## 5. Prompts for Serper

- "abhi ayurveda mein kya trending hai"
- "kya chal raha market mein"
- "google pe search karo [query]"
- "trending keywords"

These trigger Commander → Serper → live results in reply.
