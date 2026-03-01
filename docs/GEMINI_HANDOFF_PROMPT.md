# Falcon Agency — Project Handoff / Continuation Prompt for Gemini AI

**Copy the entire prompt below and paste it into Gemini to continue development with full context.**

---

## PROMPT START (copy everything below this line)

---

You are continuing development on **Falcon Agency**, an AI-powered digital marketing automation system for falconherbs.com (Indian Ayurvedic herbal e-commerce, WooCommerce + WordPress). The owner controls everything via WhatsApp. Your job is to understand the project completely and continue development without losing context.

---

## PROJECT IDENTITY

**What it is:** Falcon Agency = Director (AI brain) + specialized agents (Developer, Strategist, Media, Backup, Sentinel, AEO, Content Producer, Price Tracker) that automate e-commerce operations. Owner sends natural-language commands via WhatsApp; Director interprets, routes, executes. Human-in-the-loop for sensitive actions (publish, plugin install, etc.).

**Business context:** Site was hacked once. Owner is security-conscious. All write operations require explicit approval. Content must avoid FDA/FTC health-claim violations — no "cures"/"treats"; use "traditionally used", "may support".

**Tech stack:** Python 3.11+, FastAPI (webhook), SQLite (memory, logs), NVIDIA NIM (primary AI: Qwen3 80B, Llama 3.3 70B), OpenRouter (fallback), Meta WhatsApp Cloud API.

---

## ARCHITECTURE OVERVIEW

```
WhatsApp Message → Meta Webhook → core/webhook.py (FastAPI)
       ↓
core/commander.py (FalconCommander.handle_message)
       ↓
[1] core/memory.py — add message, track topic
[2] core/commander_intents.py — 80+ regex patterns → handlers
[3] core/director_brain.py — AI intent classification (if regex misses)
[4] core/ai_client.py — call_ai(role, messages)
       ↓
IntentResponseHandler.handle(intent) → IntegrationBridge methods
       ↓
core/whatsapp.py — send_message() to owner
```

**Director loop (separate thread):** `core/director.py` runs every 60 seconds — checks schedule, budget gate ($10/day, $150/month), dispatches scheduled tasks (Sentinel, revenue sync, health scan, VPS monitoring).

---

## KEY FILES AND ROLES

| File | Role |
|------|------|
| `main.py` | Entry point — pre-flight checks, starts Director.run() |
| `core/director.py` | 60s loop, schedule, budget, agent dispatch, webhook startup |
| `core/webhook.py` | FastAPI — POST /webhook receives WhatsApp from Meta |
| `core/commander.py` | handle_message(), intent routing, approve/deny, DirectorBrain wrap |
| `core/commander_intents.py` | 80+ intents (regex + handler), EXTENDED_INTENTS dict |
| `core/director_brain.py` | AI reply generation, persona, anti-hallucination rules |
| `core/integration_bridge.py` | Central hub — run_health_scan, run_push_all, run_store_audit, etc. |
| `core/director_schedule.py` | ExtendedSchedule, task definitions, _task_* methods |
| `core/health_scanner.py` | Health claims scanner (regex + risk scoring) |
| `core/health_rewriter.py` | AI product/blog/page rewriter, saves for approval |
| `core/woocommerce_connector.py` | WooCommerce REST API |
| `core/wordpress_publisher.py` | WordPress REST API publishing |
| `core/whatsapp.py` | WhatsAppNotifier — send_message, send_approval_request, poll_for_reply |
| `core/approval.py` | ApprovalSystem — request_approval for sensitive actions |
| `core/memory.py` | SQLite conversation memory, set_context("pending_action") |
| `core/ai_client.py` | call_ai(role, messages) — config/keys.py AI_MODELS |
| `config/keys.py` | AI_MODELS dict, NVIDIA/OpenRouter, KeyVault |
| `config/profiles/falconherbs.json` | Site profile, credentials, {{ENV:VAR}} placeholders |
| `data/extended_schedule.json` | Scheduled tasks (enabled, time, frequency) |
| `data/goals.json` | 30-day goals |

**Agents:** `agents/developer.py`, `agents/strategist.py`, `agents/media.py`, `agents/backup.py`, `agents/aeo_agent.py`, `agents/content_producer.py`, `agents/price_tracker.py` — each has `execute()` or similar entry point.

---

## CURRENT STATE — WORKING FEATURES

| Feature | Status |
|---------|--------|
| WhatsApp command flow | ✅ status, health scan, store audit, revenue, agent performance |
| Health claims flow | ✅ Scan → Rewrite → Preview → Approve → Publish (fixed Feb 28) |
| Confirmation flow | ✅ "haan karo" / "ok" routes to pending_action, re-runs handler with confirmed=True |
| _is_confirmation | ✅ Excludes "sab fix karo" — only explicit yes phrases count |
| Scheduled tasks | ✅ Sentinel, revenue sync, health scan, VPS monitoring |
| WooCommerce | ✅ Products, orders, categories, product rewrites |
| WordPress | ✅ Blog/page publish (FALCONHERBS_WP_APP_PASSWORD) |
| Backup | ✅ cPanel DB + files (when configured) |
| Approval gate | ✅ Plugin install, pause campaign, live publish |
| VPS health | ✅ psutil + /proc, WhatsApp alert when CPU/mem/disk > 85% |
| Director loop | ✅ 60s cycle, budget gate, retry queue |

---

## PENDING GAPS (Prioritized)

### Immediate (High Impact, Low Effort)
1. **Add NVIDIA_API_KEY to .env.example** — Primary AI requires it; not documented
2. **Add SERPER_API_KEY to .env.example** — AEO agent needs it
3. **Time-based messaging** — Long tasks (health scan ~40s) should send "X min wait" + done notification
4. **North-star goal** — Add "world #1 ayurvedic site" to goals.json / config/north_star.json

### Short-Term (Medium Effort)
5. **Agent failure → Director report** — Agent error → log + include in WhatsApp digest/status
6. **Direct @aeo, @content** — Extend agent_map in Commander for @aeo, @content tags
7. **"Director complaint" intent** — Route "Director, X agent problem" explicitly
8. **Health scan vs rewrite pipeline** — run_health_scan saves to health_audit; rewrite uses last_scan — unify or document

### Medium-Term
9. **Test coverage** — Commander intents, IntegrationBridge
10. **Documentation** — ARCHITECTURE.md says Flask; webhook is FastAPI
11. **Jarvis** — Clarify role (separate Node/TS project in repo) or move out

### Stubbed / TODO in Code
- `core/gsc_connector.py`: `TODO: Call Search Analytics API when implemented`
- `core/director_schedule.py`: `TODO: Meta Graph API — fetch comments, run SocialSentry.analyze`
- `core/ads_monitor.py`: Placeholder until Meta/Google Ads keys added

---

## WHAT WAS LAST WORKED ON

### March 1, 2026
1. **Product & blog compliance rewrites** — 32 changes: 27 product descriptions + 5 blog titles. All in `data/reports/changelog_2026-03-01.json`. Pattern: remove health claims, use "traditionally used", "may support".
2. **Staging flow** — `data/staging/rewrites/index.json`: approved [7803, 7807, 7800], pending []. New rewrites: products 7758–7807, blogs 7853–8148.
3. **Full summary** — `docs/CONTINUATION_SUMMARY_2026-03-01.md` for IDE handoff.

### Feb 28, 2026
1. **Health flow fix** — `core/commander_intents.py` handle_push_all_fixes: first call = generate rewrites only (no publish), show preview, ask permission; second call (on "haan karo") = apply.
2. **_is_confirmation fix** — Excluded "fix karo", "sab fix" — was treating "sab fix karo" as confirmation. Now only explicit yes phrases.
3. **run_generate_all_fixes** — New method in `core/integration_bridge.py`; run_push_all(apply_immediately=False) for generate-only.
4. **Natural language patterns** — Added "scan karo", "fix karo", "agree", "publish karo" to intents.
5. **VPS** — 2GB swap added; fresh git clone + restore .env + data; falcon.service running.
6. **Local commit + push** — commit 519d41d to GitHub (AyurERP/Falconherbs).

---

## DEPLOYMENT

- **VPS:** Oracle Cloud, 2 CPU, 956 MB RAM, 45 GB disk, 2 GB swap
- **Service:** `falcon.service` — `venv/bin/python3 main.py`
- **Webhook:** Port 8000, Caddy reverse proxy
- **Path:** `/home/ubuntu/falcon-agency` (GitHub clone)

**Required .env:** WHATSAPP_*, NVIDIA_API_KEY, FALCONHERBS_WC_*, FALCONHERBS_WP_*, WOO_SITE_URL, OPENROUTER_API_KEY, GEMINI_API_KEY

---

## RECOMMENDED NEXT STEPS

1. **Add NVIDIA_API_KEY and SERPER_API_KEY to .env.example** (5 min)
2. **Time-based msg for long tasks** — In `handle_health_scan` and similar: send "⏳ Health scan ~40s, wait karo" immediately; then send full result when done (15 min)
3. **North-star goal** — Add to config/north_star.json or data/goals.json (5 min)
4. **Agent failure in digest** — In `generate_daily_digest` or status: include agent failure summary from `core/agent_performance.py` (30 min)

---

## IMPORTANT RULES

- **Never invent data** — DirectorBrain persona: "NEVER invent, assume, or fabricate"
- **Honest "not configured"** — When API key missing, return "not configured" not fake zeros
- **Approval for sensitive actions** — Plugin install, live publish, pause campaign → ApprovalSystem
- **Hinglish support** — Owner speaks Hinglish; mirror language in replies
- **config/profiles** — Use `{{ENV:VAR}}` for credentials; PluginManager resolves via _resolve_env

---

## REFERENCE DOCS

- `docs/CONTINUATION_SUMMARY_2026-03-01.md` — Full summary for IDE handoff (March 1)
- `docs/FULL_CONTEXT_REPORT_OPINION.md` — Full gap assessment
- `docs/AGENCY_VISION_VS_CURRENT.md` — Vision vs current state
- `docs/DIRECTOR_PROMPTS_GUIDE.md` — User commands for WhatsApp
- `docs/ARCHITECTURE.md` — Technical architecture (note: says Flask, webhook is FastAPI)
- `docs/GAP_ASSESSMENT_FLOW_MODELS_WHATSAPP.md` — Flow fix, models, WhatsApp

---

## PROJECT ROOT

`F:\FALCON AGENCY` (Windows) or `/home/ubuntu/falcon-agency` (VPS)

**Git:** https://github.com/AyurERP/Falconherbs.git, branch main

---

You now have full context. Continue development from the recommended next steps or address any gap the user specifies. Ask clarifying questions if anything is ambiguous.

---

## PROMPT END (copy everything above this line)
