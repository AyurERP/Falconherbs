# Falcon Agency — VPS Deploy & WhatsApp Fix

## Quick Deploy

```bash
# On your local machine — push code
git push origin main

# SSH to VPS
ssh -i ssh-key-2026-02-21.key user@your-vps-ip

# On VPS
cd /opt/falcon-agency
git pull
pip install -r requirements.txt
sudo systemctl restart falcon_agency
```

---

## WhatsApp Messages Not Coming — Checklist

### 1. Service Running?
```bash
sudo systemctl status falcon_agency
# Should show: active (running)
```

### 2. Webhook Reachable?
Meta must POST to your webhook. Test:
```bash
curl -X GET "https://YOUR-DOMAIN/webhook?hub.mode=subscribe&hub.verify_token=YOUR_VERIFY_TOKEN&hub.challenge=123"
# Should return: 123
```

### 3. .env Variables (on VPS)
```
WHATSAPP_PHONE_ID=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_RECIPIENT=91XXXXXXXXXX   # Your phone (with country code, no +)
WHATSAPP_VERIFY_TOKEN=...          # Same as Meta Dashboard
```

### 4. Meta Dashboard
- **Webhook URL:** `https://your-domain.com/webhook`
- **Verify Token:** Must match WHATSAPP_VERIFY_TOKEN
- **Subscribe:** messages, message_deliveries (if needed)

### 5. Nginx Reverse Proxy (if using)
```nginx
location /webhook {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### 6. Firewall
```bash
# Allow 80, 443 (nginx) — webhook comes via HTTPS
sudo ufw allow 80
sudo ufw allow 443
sudo ufw reload
```

### 7. Logs
```bash
tail -f /var/log/falcon-agency.log
# Look for: "WhatsApp webhook listening on port 8000"
# Look for: "Webhook: incoming message" when you send a msg
```

---

## Clean Unwanted Files (Before Deploy)

```bash
# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete

# Remove local dev files (if any)
rm -f backup.txt commander.txt webhook.txt 2>/dev/null
```

---

## Service File Location

Copy to systemd:
```bash
sudo cp scripts/falcon_agency.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable falcon_agency
```

**Note:** Service runs `main.py` (not director.py) — main.py does pre-flight checks first.
