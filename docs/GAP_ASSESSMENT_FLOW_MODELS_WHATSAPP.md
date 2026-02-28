# Falcon Agency — Flow, Models & WhatsApp Gap Assessment

**Date:** 28 Feb 2026  
**Scope:** Health scan flow, AI models, natural language, WhatsApp delivery

---

## 1. FLOW FIXES (DONE)

### Before (Wrong)
- "sab fix karo" → applied immediately (no preview, no permission)
- `_is_confirmation` treated "karo" as yes → "sab fix karo" bypassed confirmation
- No separate generate → preview → approve → publish steps

### After (Correct)
1. **Scan** — "health scan" / "scan karo" → full site audit
2. **Generate** — "sab fix karo" → rewrites generated, saved as drafts (no publish)
3. **Preview** — Director shows changelog / pending count
4. **Permission** — "haan karo" / "ok" / "agree" → user approves
5. **Publish** — Director applies to live site

### Code Changes
- `_is_confirmation`: Excluded "fix karo", "sab fix" — only explicit yes phrases count
- `run_generate_all_fixes()`: New method — scan + rewrite only, no apply
- `run_push_all(apply_immediately=False)`: Generate-only mode
- `handle_push_all_fixes`: First call = generate + preview; second call (on approve) = apply

---

## 2. AI MODELS USED

| Component | Model | Provider | Speed | Purpose |
|-----------|-------|----------|-------|---------|
| **Director reply** | qwen/qwen3-next-80b-a3b-instruct | NVIDIA | ~2s | Creative, strategic, Hinglish |
| **Intent classification** | meta/llama-3.3-70b-instruct | NVIDIA | ~1.8s | Fast JSON, routing |
| **DirectorBrain reasoning** | DeepSeek R1 | (via config) | ~35s | Thinks before answering |
| **Content/Media** | qwen3-80b | NVIDIA | ~2s | Creative writing |
| **Strategist/Developer** | llama-3.3-70b | NVIDIA | ~1.8s | Analysis, code |
| **Fallback** | llama-3.3-70b | NVIDIA | — | When primary fails |

**Config:** `config/keys.py` → `AI_MODELS` dict

**Assessment:** Models are strong (70B–80B). Speed is good for WhatsApp. DirectorBrain uses Qwen3 80B for replies, Llama 70B for intent — both via NVIDIA NIM.

---

## 3. NATURAL LANGUAGE (Intent Matching)

### Extended Intents (Regex Patterns)
- **health_scan:** "health scan", "scan karo", "site scan", "compliance", "violation", etc.
- **push_all_fixes:** "sab fix karo", "fix karo", "fix all", "compliance fix", "rewrite sab", etc.

### Fallback (Commander)
- "status", "kya ho raha" → status_check
- "haan", "ok", "agree", "publish karo" → approve_action
- "nahi", "cancel" → deny_action

### DirectorBrain (AI Classification)
- Uses Llama 70B for intent when regex doesn’t match
- Understands Hinglish, English, Hindi
- Persona prompt in `core/director_brain.py`

**Gap:** Some phrases may still fall through to "unknown". Adding more patterns over time helps.

---

## 4. WHATSAPP — Real vs Console

### Console Mode (chat_test.py, chat.py)
- Uses `ConsoleWhatsApp` — prints to terminal
- Same logic as real WhatsApp
- No webhook, no Meta API

### Real WhatsApp
- Uses `WhatsAppNotifier` — sends via Meta Cloud API
- Webhook (`FalconWebhook`) receives incoming messages
- Director must be running with webhook enabled

### Why You Might Not See Responses on Real WhatsApp

| Cause | Check |
|-------|--------|
| **Director not running** | `python director.py` or `python chat.py` with real WA |
| **Webhook not reachable** | Meta needs public URL (ngrok, etc.) |
| **WHATSAPP_RECIPIENT mismatch** | Sender phone must match `.env` |
| **WHATSAPP_VERIFY_TOKEN** | Must match Meta App config |
| **WHATSAPP_ACCESS_TOKEN** | Valid token from Meta |
| **WHATSAPP_PHONE_ID** | Your business phone number ID |

### Quick Check
```bash
# Console (always works)
python scripts/chat_test.py

# Real WhatsApp — Director + webhook
python director.py
# Or: python chat.py  (uses ConsoleWhatsApp by default — change to WhatsAppNotifier for real)
```

### chat.py vs director.py
- `chat.py` — interactive, typically ConsoleWhatsApp
- `director.py` — full Director loop + webhook + real WhatsApp

---

## 5. REMAINING GAPS

| Gap | Status | Notes |
|-----|--------|-------|
| Flow: Scan → Rewrite → Preview → Approve → Publish | ✅ Fixed | |
| _is_confirmation bug | ✅ Fixed | |
| Natural language patterns | ✅ Improved | More can be added |
| WhatsApp delivery | ⚠️ Config-dependent | Verify webhook + env |
| DirectorBrain vs regex priority | — | Extended intents run first |
| Health scan vs rewrite data | — | health_scan uses health_audit; rewrite uses last_scan |

---

## 6. RECOMMENDED FLOW (User)

1. **"health scan"** or **"scan karo"** → Full audit, ~40 sec
2. **"sab fix karo"** → Generate rewrites, preview shown
3. Review preview on WhatsApp
4. **"haan karo"** or **"ok"** or **"publish karo"** → Apply to live site
5. **"changelog"** → Full before/after report

---

## 7. FILES CHANGED

- `core/commander_intents.py` — _is_confirmation, handle_push_all_fixes, patterns
- `core/integration_bridge.py` — run_generate_all_fixes, run_push_all(apply_immediately)
- `core/commander.py` — approve fallback patterns
