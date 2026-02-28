# Falcon Agency — Continue Fixing 28 Gaps (Copy This Prompt)

**File:** `docs/PROMPT_CONTINUE_28_GAPS.md` — Copy everything below the line.

---

## QUICK COPY (Paste this into new chat)

```
Continue fixing Falcon Agency 28-gap list. Project: F:\FALCON AGENCY\

REMAINING GAPS:
- #8: Add VPS CPU/memory/disk monitoring + WhatsApp alert when thresholds exceeded
- #11: Verify Sentinel monitoring auto-starts (sentry_daily_scan in director_schedule)
- #13: Idle alert should repeat every 60 min, not once total
- #22: Task retry queue when Director busy at scheduled time
- #23: Add Hinglish patterns ("traffic dekho", "ads check karo", "backup theek hai?")
- #25: When intent classifier crashes, send WhatsApp notification to owner
- #27: Add URL validation before crawl_all_pages in _do_deep_competitor_analysis

ALREADY FIXED (don't redo): #5, #6, #7, #9, #15, #17, #24

Read docs/GAP_ASSESSMENT_28.md and docs/FINAL_STATUS_28_GAPS.md. Fix in order #8, #11, #13, #22, #23, #25, #27. Give final status.
```

---

## CONTEXT

I'm continuing work on **Falcon Agency** — an AI agency that manages FalconHerbs.com (WooCommerce/WordPress) via WhatsApp. Project path: `F:\FALCON AGENCY\`.

A previous session assessed all 28 gaps and fixed 6. **Your job: fix the remaining gaps** that are still NOT DONE or DEFERRED.

---

## REMAINING GAPS TO FIX

### CRITICAL
- **#8** — No CPU/memory/disk monitoring on VPS → add basic resource check (psutil or /proc) and WhatsApp alert when thresholds exceeded

### DANGEROUS
- **#11** — Sentinel monitoring thread never auto-starts → verify director_schedule runs sentry_daily_scan; if not, wire it
- **#13** — Idle alert fires only once total → should repeat every 60 min; check _last_idle_alert_time logic in director.py

### HIGH
- **#22** — No task retry queue → if Director busy at scheduled time, task is skipped; add retry or queue for next cycle

### MEDIUM
- **#23** — 10+ intents missing Hinglish variants → add patterns like "traffic dekho", "ads check karo", "backup theek hai?", "visitors kitne"
- **#25** — Intent classifier crash silently falls back → add WhatsApp notification to owner when extended classifier fails
- **#27** — _do_deep_competitor_analysis() calls crawl_all_pages() with no URL validation → add validation before crawl

---

## WHAT WAS ALREADY FIXED (Don't redo)
- #5 backup _do_backup → calls run_daily_backup
- #6 GSC → honest "not configured"
- #7 _task_sentry_scan → checks META_ACCESS_TOKEN
- #15 ads_status → real config status
- #17 handle_analyse_keywords → added
- #9 confirmation flow → memory pending_action + "haan karo"
- #24 _reply_unknown → Hinglish suggestions

---

## KEY FILES
- `core/director.py` — main loop, uptime check, idle alert, heartbeat
- `core/director_schedule.py` — scheduled tasks (sentry_daily_scan, aeo_scan)
- `core/commander_intents.py` — intent patterns, handlers
- `core/commander.py` — message routing, _reply_unknown
- `agents/strategist.py` — _do_deep_competitor_analysis, crawl
- `core/integration_bridge.py` — bridge to tools

---

## RULES
1. **No fake returns** — if feature can't work, return "Not configured" with instructions
2. **Dangerous actions need confirmation** — already done for push/sab fix
3. **Use existing WhatsApp notifier** — `core/whatsapp.py` or ApprovalSystem
4. **Don't break working features** — test imports, avoid circular deps
5. **Hinglish support** — commands work in Hindi-English mix

---

## APPROACH
1. Read the relevant files for each remaining gap
2. Fix one gap at a time
3. For #8 (VPS monitoring): add optional psutil check or read /proc/meminfo, /proc/loadavg; alert if CPU > 90% or memory > 95%
4. For #11: check director_schedule and director.py — when does sentry_daily_scan run? Is it wired?
5. For #13: idle alert — ensure it can fire again after cooldown (e.g. 60 min)
6. For #22: consider storing "missed" task and retrying next cycle
7. For #23: add Hinglish patterns to existing intents in commander_intents.py
8. For #25: in commander.py, when extended intent fails (except block), send WhatsApp "System: intent classifier had an issue, falling back."
9. For #27: validate URL (scheme, hostname) before crawl_all_pages

---

## START
Read `docs/GAP_ASSESSMENT_28.md` and `docs/FINAL_STATUS_28_GAPS.md` for full context. Then fix gaps #8, #11, #13, #22, #23, #25, #27 in that order. Give a final status when done.
