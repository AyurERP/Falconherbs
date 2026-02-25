# 🦅 FALCON AGENCY — QUICK REFERENCE CARD
*Print this or keep it open on your phone*

---

## 📱 AGENCY CONTACT
**WhatsApp:** +91 99163 22917 (send commands here)
**Health:** https://falconagency.duckdns.org/health

---

## 🔥 TOP 10 COMMANDS

```
sab batao              → Full status update
scan products          → Check 87 products for violations
rewrite products       → AI-fix flagged descriptions
sab fix karo           → Apply ALL fixes to live site ✅
blog likh [topic]      → Write a blog post
drafts dikhao          → See pending content
publish karo           → Publish latest draft to WordPress
kitne order aaye       → Today's orders
revenue report         → Sales/revenue numbers
backup banao           → Create site backup
```

---

## ⚠️ APPROVAL WORDS

```
YES  → haan / kar do / theek hai / approve / go ahead
NO   → nahi / ruko / cancel / mat karo / reject
```

---

## 🔄 HEALTH FIX WORKFLOW

```
1. scan products      2. rewrite products    3. push karo
1. scan blogs         2. rewrite blogs       3. blogs fix karo

           OR just:   sab fix karo  (does everything at once)
```

---

## 📂 IMPORTANT DATA PATHS

```
data/reports/                    ← Change reports (before/after)
data/content/drafts/             ← Blog/social drafts waiting review
data/content/product_rewrites/   ← Product rewrites pending push
data/pricing/                    ← Competitor price scans
data/uploads/                    ← Files you sent to agency via WhatsApp
data/revenue/                    ← Revenue logs
```

---

## 🖥️ VPS COMMANDS

```bash
# SSH into VPS
ssh -i "ssh-key-2026-02-21.key" ubuntu@140.245.246.190

# Restart service
sudo systemctl restart falcon.service

# View live logs
journalctl -u falcon.service -f

# Update code + restart
cd /home/ubuntu/falcon-agency && git pull && sudo systemctl restart falcon.service
```

---

## 📋 ALL 17 TOOLS (quick reference)

| Tool | Trigger Command |
|---|---|
| woocommerce | store audit |
| health_scanner | health scan |
| health_rewriter | rewrite products |
| content | blog likh |
| revenue | revenue report |
| goal_tracker | progress dikhao |
| profit | profit report |
| seo | seo audit |
| competitor | competitor check |
| backup | backup banao |
| designer | image bana |
| analytics (GA4) | analytics traffic |
| ads | ads status |
| sentry | sentry check |
| aeo | aeo scan |
| pricing | price scan |
| website | site up? |

---

## 🗓️ AUTO SCHEDULE (No Action Needed)

```
06:00  → Morning report sent to WhatsApp
10:00  → WooCommerce orders sync
14:00  → Content generation
20:00  → Evening summary to WhatsApp
Mon    → Weekly SEO digest
Weekly → Competitor price scan
```

---

## 🚨 TROUBLESHOOTING

| Problem | Fix |
|---|---|
| Tool not loaded | VPS: `pip install -r requirements.txt` + restart |
| Service down | `sudo systemctl restart falcon.service` |
| 401 on blog edits | WP Admin → Users → App Passwords → Create one |
| No WhatsApp reply | Check: `https://falconagency.duckdns.org/health` |

---

## 📁 KEY CODE FILES

```
core/commander_intents.py   ← All command handlers
core/health_rewriter.py     ← Product/blog/page fixer
core/integration_bridge.py  ← Tool manager
core/changelog_manager.py   ← Change tracking
.env                        ← All credentials
requirements.txt            ← Python packages
```

---
*Falcon Agency v3.0 | 2026-02-25*
