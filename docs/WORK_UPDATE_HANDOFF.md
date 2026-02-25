# Falcon Agency — Work Update Handoff

**Date:** 2026-02-25  
**Purpose:** Resume work in another IDE/session

---

## 1. Project Overview

**Falcon Agency** — AI agency for FalconHerbs.com (WooCommerce/WordPress), controlled via WhatsApp.

- **Path:** `F:\FALCON AGENCY\`
- **VPS:** `ubuntu@140.245.246.190` (Oracle Cloud)
- **VPS Path:** `/home/ubuntu/falcon-agency`
- **Git:** `https://github.com/AyurERP/Falconherbs.git`
- **Webhook URL:** `https://falconagency.duckdns.org/webhook`

---

## 2. Completed This Session

### 2.1 VPS Deployment
- Created venv (was missing), installed `requirements.txt`
- Restarted `falcon.service` — Falcon Agency running
- Health: `https://falconagency.duckdns.org/health` → 200 OK

### 2.2 Site Unreachable Alerts Fix
- **Problem:** VPS → falconherbs.com SSL handshake timeout; WhatsApp spam alerts
- **Changes:**
  - `core/director.py`: `UPTIME_CHECK_TIMEOUT` 5→20 sec; added 30-min cooldown for unreachable alerts
  - `core/sentinel.py`: `_HTTP_TIMEOUT` 10→25 sec; cooldown for "Site Unreachable" scan alerts
- **Files:** `core/director.py`, `core/sentinel.py`

### 2.3 Server Check Script
- **New:** `scripts/server_check.py` — tests site, cPanel API, WHM API
- **New:** `.env.example` — added WHM vars (`WHM_URL`, `WHM_USER`, `WHM_PASSWORD`)
- **Usage:** `python scripts/server_check.py`
- **Pending:** User to add WHM credentials to `.env` and run check

### 2.4 Health Claim Rewrite Cheat Codes (documented)
- `sab fix karo` / `fix all` / `125 fix` — apply ALL (products+blogs+pages+categories)
- `rewrite products` / `rewrite blogs` / `rewrite pages` — generate AI rewrites
- `push karo` — apply product rewrites only
- `rewrite status` — pending rewrites

---

## 3. Key Paths & Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point |
| `core/webhook.py` | WhatsApp webhook (port 8000) |
| `core/commander.py` | Intent routing |
| `core/commander_intents.py` | All WhatsApp commands |
| `core/director.py` | Main loop, uptime check |
| `core/sentinel.py` | Security scan |
| `core/integration_bridge.py` | WooCommerce, rewriter, etc. |
| `core/health_rewriter.py` | Health claim rewrites |
| `agents/backup.py` | cPanel/WHM backup |
| `scripts/server_check.py` | Server diagnostics |
| `scripts/whatsapp_check.py` | WhatsApp troubleshooting |

---

## 4. Environment Variables (.env)

```
# WhatsApp
WHATSAPP_PHONE_ID, WHATSAPP_ACCESS_TOKEN, WHATSAPP_RECIPIENT, WHATSAPP_VERIFY_TOKEN

# cPanel
CPANEL_USERNAME, CPANEL_API_TOKEN, CPANEL_DOMAIN, CPANEL_PORT

# WHM (optional, for server check)
WHM_URL, WHM_USER, WHM_PASSWORD

# WooCommerce
WOO_SITE_URL, WC_API_KEY, WC_API_SECRET

# WordPress
FALCONHERBS_WP_USER, FALCONHERBS_WP_PASSWORD, WP_DB_NAME
```

---

## 5. VPS Commands

```bash
# SSH
ssh -i "ssh-key-2026-02-21.key" ubuntu@140.245.246.190

# Service
sudo systemctl status falcon.service
sudo systemctl restart falcon.service

# Logs
journalctl -u falcon.service -f

# Pull & restart
cd /home/ubuntu/falcon-agency && git pull && sudo systemctl restart falcon.service
```

---

## 6. Pending / TODO

1. **Server check** — User to add WHM credentials to `.env`, run `python scripts/server_check.py`
2. **falconherbs.com unreachable from VPS** — SSL handshake timeout; may need hosting provider to allow VPS IP or check firewall
3. **cPanel API** — Ensure `CPANEL_DOMAIN` is correct (server hostname if different from falconherbs.com)

---

## 7. Quick Reference

| Action | Command |
|--------|---------|
| Start work | WhatsApp: `Bismillah sab batao` |
| Health claim fix | WhatsApp: `sab fix karo` |
| Server check | `python scripts/server_check.py` |
| WhatsApp check | `python scripts/whatsapp_check.py` |

---

## 8. Git Status

- Latest commit includes: director/sentinel timeout+cooldown, server_check.py, .env.example WHM vars
- Push to `main` done; VPS pulled and restarted

---

*End of handoff*
