# Falcon Agency — Full Context Report (For Second Opinion)

**Date:** 28 Feb 2026  
**Purpose:** Comprehensive project overview for external review / second opinion

---

## 1. WHAT IS FALCON AGENCY?

**Falcon Agency** is an AI-powered digital marketing automation system for **falconherbs.com** — an Indian Ayurvedic herbal products e-commerce site (WooCommerce + WordPress).

**Primary user:** Business owner who controls everything via **WhatsApp**.

**Core value proposition:**
- Owner sends natural-language commands via WhatsApp (e.g. "health scan", "sab fix karo", "status")
- Director (AI brain) interprets, routes to agents, executes tasks
- Human-in-the-loop: sensitive actions (publish, plugin install, etc.) require explicit approval
- Scheduled automation: security scans, revenue sync, content, backups

**Business context:** Site was hacked once. Owner is security-conscious. All write operations go through approval. Content must avoid FDA/FTC health-claim violations (no "cures", "treats" — use "traditionally used", "may support").

---

## 2. ARCHITECTURE

### Entry Points
| Component | Role |
|-----------|------|
| `main.py` | Starts Director loop + webhook |
| `core/webhook.py` | FastAPI — receives WhatsApp messages from Meta Cloud API |
| `core/director.py` | 60-second main loop — schedule, budget gate, agent dispatch |

### Brain Layer
| Component | Role |
|-----------|------|
| `core/commander.py` | Message interpreter — intent classification, routing, reply |
| `core/commander_intents.py` | 80+ extended intents (regex + handlers) |
| `core/director_brain.py` | AI reply generation (Qwen3 80B), persona, anti-hallucination |
| `core/ai_client.py` | Multi-model client (NVIDIA NIM, OpenRouter fallback) |
| `core/memory.py` | SQLite conversation memory, pending_action |

### Agents (Specialists)
| Agent | Role |
|-------|------|
| Sentinel | Security scan, uptime, site-down alerts |
| Developer | Uptime, performance, security, code fixes |
| Strategist | SEO, keyword analysis, competitor analysis |
| Media | Image generation, content creation |
| Backup | cPanel DB + files backup |
| AEO | Brand visibility in AI answers (Serper + analysis) |
| Content Producer | Weekly packages, reels, email campaigns |
| Price Tracker | Competitor pricing |

### Integrations
| Integration | Purpose |
|-------------|---------|
| **WhatsApp** (Meta Cloud API) | Owner communication, approval gate |
| **WooCommerce** | Products, orders, categories |
| **WordPress** | Blog/page publishing, plugin management |
| **NVIDIA NIM** | Primary AI (Qwen3 80B, Llama 3.3 70B) |
| **OpenRouter** | Fallback AI |
| **Gemini** | Media agent (images) |
| **cPanel/WHM** | Backup, server diagnostics |
| **GSC** | Google Search Console (when configured) |
| **GA4** | Analytics (when configured) |
| **Serper** | Search for AEO agent |

---

## 3. WHAT WORKS TODAY

### ✅ Fully Working
- **WhatsApp command flow** — status, health scan, store audit, revenue, agent performance
- **Health claims flow** — Scan → Rewrite → Preview → Approve → Publish (fixed Feb 28)
- **Confirmation flow** — "haan karo" / "ok" routes to pending_action
- **Scheduled tasks** — Sentinel, revenue sync, health scan, VPS monitoring
- **WooCommerce** — products, orders, categories, product rewrites
- **WordPress** — blog/page publishing (with app password)
- **Backup** — cPanel DB + files (when configured)
- **Approval gate** — Plugin install, pause campaign, live publish
- **VPS health** — CPU/memory/disk alerts via WhatsApp
- **Director loop** — 60s cycle, budget gate ($10/day, $150/month)

### ⚠️ Partially Working / Config-Dependent
- **WhatsApp delivery** — Requires webhook reachable, correct WHATSAPP_RECIPIENT
- **GSC** — Returns "not configured" when no key (honest, no fake data)
- **GA4** — Same
- **Ads Monitor** — Placeholder until Meta/Google Ads keys added
- **Backup** — cPanel/FTP must be configured; falls back to placeholder if not

### ❌ Stubbed / Placeholder
- **GSC Search Analytics** — `TODO: Call Search Analytics API when implemented`
- **Meta Graph API (comments)** — `TODO: Meta Graph API — fetch comments, run SocialSentry.analyze`
- **Ads Monitor** — "Google Ads API connected (placeholder — implement when keys added)"

---

## 4. GAPS & MISSING (Prioritized)

### Critical / High
| Gap | Description | Impact |
|-----|-------------|--------|
| **Time-based messaging** | Long tasks (health scan ~40s) — no "X min wait" + done notification | UX — owner doesn't know when to expect result |
| **Agent failure → Director report** | Agent error → log only; no WhatsApp summary to owner | Transparency gap |
| **North-star goal** | goals.json generic; "world #1" not explicit | Strategy clarity |
| **Direct @aeo, @content** | Only @developer, @strategist, @media, @backup have direct tags | Incomplete agent access |
| **"Director complaint" intent** | "Director, X agent problem" — no explicit route | Escalation gap |

### Medium
| Gap | Description |
|-----|-------------|
| **Health scan vs rewrite data** | `run_health_scan` saves to health_audit; rewrite uses last_scan — different pipelines |
| **Intent fallthrough** | Some phrases → "unknown"; more patterns needed |
| **NVIDIA_API_KEY** | .env.example doesn't list it; primary AI needs it |
| **Serper API** | AEO agent needs SERPER_API_KEY; not in .env.example |

### Low / Deferred
| Gap | Description |
|-----|-------------|
| **Jarvis** | Separate Node/TS project in repo; relationship to Falcon unclear |
| **generate_daily_digest** | Placeholder comment in integration_bridge |
| **ENCRYPTION_KEY** | Placeholder if not set; KeyVault still works |

---

## 5. TECHNICAL DEBT

| Item | Location | Notes |
|------|----------|-------|
| **Duplicate structure** | VPS had root-level copies of core/agents files | Cleaned in fresh deploy |
| **Bare except** | None found (was a prior gap) | OK |
| **Test coverage** | Minimal — `tests/` exists but sparse | Risk for regressions |
| **Documentation drift** | ARCHITECTURE says "Flask" but webhook is FastAPI | Minor |
| **main.py vs director.py** | main.py starts Director; director.py is the module | Confusing naming |

---

## 6. DEPLOYMENT

### VPS (Current)
- **Host:** Oracle Cloud (or similar) — 2 CPU, 956 MB RAM, 45 GB disk
- **Swap:** 2 GB added (recommended)
- **Service:** `falcon.service` — `venv/bin/python3 main.py`
- **Webhook:** Port 8000 (Caddy reverse proxy to Meta)
- **Path:** `/home/ubuntu/falcon-agency`

### Required .env (Key Subset)
```
WHATSAPP_PHONE_ID, WHATSAPP_ACCESS_TOKEN, WHATSAPP_RECIPIENT, WHATSAPP_VERIFY_TOKEN
NVIDIA_API_KEY          # Primary AI — not in .env.example!
FALCONHERBS_WC_API_KEY, FALCONHERBS_WC_API_SECRET
FALCONHERBS_WP_USER, FALCONHERBS_WP_APP_PASSWORD
WOO_SITE_URL
OPENROUTER_API_KEY      # Fallback AI
GEMINI_API_KEY          # Media agent
```

### Optional (Feature-Specific)
```
WHM_URL, WHM_USER, WHM_PASSWORD    # Server diagnose, Apache restart
CPANEL_*                            # Backup
SERPER_API_KEY                     # AEO agent
GOOGLE_*                            # GSC, GA4
META_ACCESS_TOKEN                  # Sentry/social scan
```

---

## 7. RECOMMENDATIONS (For Second Opinion)

### Immediate (High Impact, Low Effort)
1. **Add NVIDIA_API_KEY to .env.example** — Primary AI won't work without it
2. **Time-based msg for long tasks** — "Health scan ~40s, wait karo" + done notification
3. **North-star goal** — Add "world #1 ayurvedic site" to goals.json / config

### Short-Term (Medium Effort)
4. **Agent failure → digest** — Include failures in daily/status report
5. **Direct @aeo, @content** — Extend agent_map for Commander
6. **"Director complaint" intent** — Route "Director, X problem" explicitly
7. **Health scan → rewrite pipeline** — Unify or document why two pipelines

### Medium-Term
8. **Test coverage** — At least for Commander intents, IntegrationBridge
9. **Documentation** — Update ARCHITECTURE (Flask→FastAPI), add runbook
10. **Jarvis** — Clarify role or move to separate repo

### Lower Priority
11. **GSC Search Analytics** — Implement when key available
12. **Meta Graph comments** — For SocialSentry
13. **Ads Monitor** — When Meta/Google Ads keys added

---

## 8. SUMMARY FOR REVIEWER

**Strengths:**
- Clear architecture: Director → Commander → Agents → Integrations
- Human-in-the-loop for sensitive actions
- Strong AI models (70B–80B via NVIDIA)
- Health compliance flow (scan → rewrite → approve → publish) is correct
- Honest "not configured" instead of fake data
- VPS monitoring, retry queue, idle alerts

**Weaknesses:**
- Some features config-dependent (WhatsApp, GSC, GA4, Backup)
- Placeholder/stub for Ads, GSC Analytics, Meta comments
- Vision gaps: time-based msg, agent failure report, north-star goal
- Test coverage minimal

**Overall:** Production-capable for core use case (WhatsApp-driven e-commerce automation). Gaps are incremental improvements, not blockers. A second pair of eyes should focus on: (1) env var completeness, (2) vision alignment (AGENCY_VISION_VS_CURRENT.md), (3) security review of approval flow.

---

*End of report*
