# Director Audit — ACTUAL Current State (Code as of 2026-02-25)

Audit of what EXISTS in code RIGHT NOW. Not planned — actual.

---

## KNOWLEDGE LAYER

### 1. Where does the Director store what it knows about the client's current website state?

**EXISTS** — Scattered across multiple files; no single "website state" store:
- `config/profiles/falconherbs.json` — site identity, plugins, goals (static config)
- `data/health_audit/health_audit_report.json` — health scan results (products, blogs, pages, categories)
- `data/reports/strategy_*.json` — SEO/keyword reports
- `data/content/product_rewrites/last_scan.json` — product rewrite status
- `data/woocommerce/` — WooCommerce sync data (orders, products)
- Director does NOT aggregate these into a single "current website state" — each tool reads its own data when needed

### 2. Where does it store task history — done, failed, pending?

**EXISTS** in multiple places:
- **Goals:** `core/director.py:load_goals()` / `save_goals()` — `data/goals.json` with status: `pending`, `in_progress`, `complete`, `failed`
- **Schedule (legacy):** `core/director.py:check_schedule()` — `data/schedule.json` with `last_run` per task per site
- **Extended schedule:** `core/director_schedule.py` — `data/extended_schedule.json` with `last_run` per task
- **Task results:** `core/director_schedule.py:_record_task_result()` — records success/fail + elapsed; stored in schedule or internal state
- **SQLite:** `core/logger.py` — `log_action()` writes to `falcon.db` (action, details, agent, status)
- No single "task history" table — status is in goals.json; last_run in schedule; logs in SQLite

### 3. Where does it store the owner's goals/preferences?

**EXISTS:**
- **Goals:** `core/director.py:load_goals()` — `data/goals.json` (id, site, description, priority, status, created_at)
- **Preferences (topics):** `core/memory.py:get_user_preferences()` — SQLite `topics` table (user_id, topic, frequency, last_mentioned)
- **Ideas:** `core/commander.py` — `data/ideas.json` (idea capture)
- No explicit "owner preferences" like language, notification frequency — inferred from conversation topics

### 4. Where does it track what each agent is currently doing?

**EXISTS:**
- `core/director.py:_current_task` (instance var) — string like "security_scan" or "Completed: health_claims_scan"
- `core/director.py:_current_site` (instance var) — site being worked on
- Set in `dispatch_agent()` (line 1266), cleared in `finally` (line 1331)
- `core/commander.py:_get_director_status()` reads `self._director._current_task` for status reply
- Only ONE task at a time — no per-agent queue; single `_current_task` for "what's running now"

### 5. Where does it track budget spent?

**EXISTS:**
- `core/director.py:_load_spend()` — reads `data/spend.json` (daily_total, monthly_total, date)
- `core/director.py:log_spend()` — adds to spend.json + inserts into SQLite `spend_log` table
- `core/director.py:check_budget()` — compares against DAILY_LIMIT ($10), MONTHLY_LIMIT ($150)
- `core/logger.py` — `spend_log` table for API cost tracking (model, tokens, cost_usd, task)

---

## DECISION LAYER

### 6. What logic decides WHAT to do next in the 60s loop?

**EXISTS** in `core/director.py:process_cycle()` (lines 1671–1835):

```
1. run_heartbeat()
2. due_tasks = check_schedule()  — legacy schedule (data/schedule.json)
3. Prepend _retry_queue (tasks deferred when busy)
4. For each due task:
   - Time budget guard (CYCLE_TIME_BUDGET 25s) → defer to retry_queue
   - Max tasks guard (MAX_TASKS_PER_CYCLE 10) → defer to retry_queue
   - Budget check → halt if exhausted
   - _is_sensitive() → _gate_approval() if needed
   - dispatch_agent()
   - log_spend()
   - _update_schedule_last_run()
5. If time remains: goal = get_next_goal() → _process_goal(goal)
6. _extended_schedule.check_and_execute() — ExtendedSchedule (data/extended_schedule.json)
7. If nothing ran: _run_idle_monitoring()
```

**Decision code:** `core/director.py:check_schedule()` (lines 933–990) — interval_minutes elapsed since last_run; `core/director_schedule.py:get_pending_tasks()` + `should_run_task()` — time-of-day, frequency (daily/weekly/monthly/interval)

### 7. What logic decides task priority?

**EXISTS:**
- **Goals:** `core/director.py:get_next_goal()` — sorts by `(priority, created_at)`; lower priority number = higher urgency
- **Schedule (legacy):** `core/director.py:check_schedule()` — returns list; comment says "uptime_check first, then security_scan, then seo_audit" but actual sort not clearly in code (order from schedule iteration)
- **Extended schedule:** `core/director_schedule.py:get_pending_tasks()` — no explicit priority; iterates tasks, returns those where `should_run_task()` is True
- **Retry queue:** FIFO — first deferred, first retried

### 8. What logic checks if owner approval is needed before acting?

**EXISTS:**
- `core/director.py:_is_sensitive()` — static check: `task in SENSITIVE_TASKS` (frozenset: code_deploy, file_write, file_delete, content_update, database_modify, config_change, security_action, ip_block)
- `core/director.py:_gate_approval()` — calls `ApprovalSystem.request_approval()` (WhatsApp); blocks until YES/NO or timeout
- **Note:** Extended schedule tasks (health_scan, backup, etc.) do NOT go through `_is_sensitive` — they use `check_and_execute()` which has no approval gate. Only legacy schedule + goals use it.
- **Commander intents:** Some handlers return `needs_confirmation` + `pending_action`; Commander stores in memory, re-runs on "haan karo"

### 9. What logic checks if a task is in scope or out of scope?

**DOES NOT EXIST**

- No `in_scope()` or `out_of_scope()` function
- No scope check before dispatch
- DirectorBrain persona lists "YOUR TOOLS" but no programmatic scope validation
- Unknown tasks → `dispatch_agent` returns `{"status": "error", "message": "Unknown agent"}` or agent returns error — reactive, not proactive scope check

---

## EXECUTION LAYER

### 10. List every REAL tool/API the agents can actually call

**Actual function calls (not prompt text):**

| Tool | Module | Key methods |
|------|--------|-------------|
| WooCommerce | `core/woocommerce_connector.py` | `get_orders()`, `_make_request()`, `update_product()`, `get_products()` |
| Health Scanner | `core/health_scanner.py` | `scan_page()`, `full_scan()` |
| Integration Bridge | `core/integration_bridge.py` | `run_health_scan()`, `run_push_all_rewrites()`, `run_push_all_blog_fixes()`, `run_push_all_page_fixes()`, `get_revenue_report()`, `generate_daily_digest()`, `generate_morning_report()`, `generate_evening_report()`, `run_backup()`, `run_aeo_scan()`, `get_orders()`, etc. |
| Sentinel | `core/sentinel.py` | `run_scan()`, `monitor_failed_logins()` |
| Revenue Tracker | `core/revenue_tracker.py` | `sync_from_woocommerce()`, `generate_whatsapp_report()`, `get_monthly_summary()` |
| Content Pipeline | `core/content_pipeline.py` | `generate_this_weeks_content()`, `generate_content_status_report()` |
| Health Rewriter | `core/health_rewriter.py` | `rewrite_product()`, `rewrite_blog()`, `rewrite_page()`, `get_rewrite_status()` |
| WordPress Publisher | `core/wordpress_publisher.py` | Publish to WP REST API |
| Backup | `agents/backup.py` | `run_daily_backup()`, `verify_backup()`, `quick_snapshot()` |
| Strategist | `agents/strategist.py` | `execute()` → `_do_seo_audit()`, `_do_keyword_analysis()`, `_do_deep_competitor_analysis()` |
| Developer | `agents/developer.py` | `execute()` → `_do_uptime()`, `_do_security()`, `_do_performance()`, plugin updates |
| Media | `agents/media.py` | `execute()` → content queue |
| AEO Agent | `agents/aeo_agent.py` | `run_monthly_scan()`, `_search_serper()` |
| GSC | `core/gsc_connector.py` | `run_health_check()` |
| Lead Predictor | `core/lead_predictor.py` | `get_burn_rate_report()` |
| Customer Winback | `core/customer_winback.py` | `generate_winback_emails()`, `get_winback_status()` |
| Profit Tracker | `core/profit_tracker.py` | `run_weekly_scan()`, `get_latest_report()` |

External APIs: WooCommerce REST, WordPress REST, Meta WhatsApp, Serper.dev, NVIDIA AI, Anthropic/OpenAI/Gemini (via ai_client), cPanel (backup), requests (HTTP)

### 11. After an agent finishes a task, what verifies the work was done correctly?

**EXISTS** — Partial, task-specific:
- **Backup:** `core/director_schedule.py:_task_daily_backup()` — checks backup_dir for recent files, file size > 100 bytes
- **Backup verify:** `agents/backup.py:verify_backup()` → `_verify_components()` — checksum, file existence
- **Developer (plugin update):** `agents/developer.py` — documents "git commit before, rollback if fails" but no automated post-verify
- **Health rewriter:** Saves to JSON; "push" applies — no automatic verification that live site matches
- **General:** No universal "verify task result" step. Most tasks: `result.get("status") == "success"` is trusted. No re-check of live state.

### 12. If something goes wrong, what handles rollback/recovery?

**EXISTS** — Partial:
- **Developer:** `agents/developer.py` — git commit before file mod; documents "git rollback" on failure; `rollback_available: True` in result
- **Director process_cycle:** `try/except` logs "process_cycle crashed (recovering)" — loop continues next cycle
- **dispatch_agent:** `try/except` returns `{"status": "error", "error": "..."}` — no rollback
- **Backup restore:** `agents/backup.py` — restore flow exists (verify backup → restore DB → restore files → verify site)
- **Schedule corruption:** `core/director_schedule.py:_load_schedule()` — backs up corrupted file, resets to default
- **Goals:** On shutdown, in-progress goals reverted to pending
- No automatic rollback for: health rewrite push, content publish, WooCommerce update — manual recovery only

### 13. How are reports/updates sent to the owner automatically?

**EXISTS:**
- `core/director.py:_send_alert()` — delegates to `ApprovalSystem.send_alert()` → `WhatsAppNotifier.send_message()`
- **Scheduled reports:** `core/director_schedule.py:check_and_execute()` — when task returns `send_whatsapp: True`, calls `whatsapp_sender(result["message"])` (Director passes `self._whatsapp.send_message`)
- **Tasks that send WhatsApp:** morning_report, evening_report, daily_digest, order_check (on new orders), daily_backup (on failure), site_health_check (on failure), vps_health_check (on threshold), critical task failures
- **Alerts:** Site down, budget exceeded, idle alert, recovery — all via `_send_alert()`
- **Reactive:** Commander sends reply on every WhatsApp message (status, task result, question answer)

---

## Summary Table

| # | Item | Status |
|---|------|--------|
| 1 | Website state storage | EXISTS (scattered: profiles, health_audit, reports, woocommerce) |
| 2 | Task history (done/failed/pending) | EXISTS (goals.json, schedule last_run, SQLite logs) |
| 3 | Owner goals/preferences | EXISTS (goals.json, memory topics, ideas.json) |
| 4 | Agent current activity tracking | EXISTS (Director._current_task, _current_site) |
| 5 | Budget tracking | EXISTS (director._load_spend, log_spend, spend.json) |
| 6 | What-to-do-next logic | EXISTS (director.process_cycle, check_schedule, get_next_goal, extended_schedule) |
| 7 | Task priority logic | EXISTS (get_next_goal priority sort; schedule order) |
| 8 | Approval check | EXISTS (director._is_sensitive, _gate_approval) |
| 9 | Scope check | DOES NOT EXIST |
| 10 | Real tools/APIs | EXISTS (see table above) |
| 11 | Post-task verification | EXISTS (backup only; partial) |
| 12 | Rollback/recovery | EXISTS (developer git; backup restore; schedule corruption; no general rollback) |
| 13 | Automatic reports to owner | EXISTS (_send_alert, check_and_execute send_whatsapp) |
