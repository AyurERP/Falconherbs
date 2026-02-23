"""
Email System — SMTP direct email sending for campaigns,
notifications, and customer communication.

Uses Gmail SMTP or any SMTP for sending.
B3: Email Marketing Foundation.
"""

import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from dotenv import load_dotenv

load_dotenv()

# SMTP Configuration (add to .env)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
FROM_NAME = os.getenv("FROM_NAME", "Falcon Herbs")

# Email logs
EMAIL_LOG = Path(__file__).parent.parent / "data" / "email_log.json"
TEMPLATES_DIR = Path(__file__).parent.parent / "data" / "email_templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


class EmailSystem:
    """Send emails via SMTP with templates and logging."""
    
    def __init__(self):
        self.host = SMTP_HOST
        self.port = SMTP_PORT
        self.user = SMTP_USER
        self.password = SMTP_PASSWORD
        self.from_email = FROM_EMAIL
        self.from_name = FROM_NAME
        self._ensure_templates()
    
    def is_configured(self) -> bool:
        """Check if SMTP credentials are set."""
        return bool(self.user and self.password)
    
    def send_email(self, to: str, subject: str, 
                   html_body: str, text_body: str = None) -> dict:
        """
        Send a single email.
        
        Args:
            to: Recipient email
            subject: Email subject
            html_body: HTML content
            text_body: Plain text fallback
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "SMTP not configured. Add SMTP_USER and SMTP_PASSWORD to .env"
            }
        
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg["Reply-To"] = self.from_email
            
            # Add text version
            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            
            # Add HTML version
            msg.attach(MIMEText(html_body, "html"))
            
            # Send
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
            
            # Log
            self._log_email(to, subject, "sent")
            
            return {
                "success": True,
                "message": f"✅ Email sent to {to}\n📧 Subject: {subject}"
            }
            
        except Exception as e:
            self._log_email(to, subject, f"failed: {e}")
            return {"success": False, "error": str(e)}
    
    def send_welcome_email(self, customer_email: str, 
                           customer_name: str = "") -> dict:
        """Send welcome email to new customer."""
        subject = f"Welcome to Falcon Herbs, {customer_name or 'Friend'}! 🌿"
        html = self._load_template("welcome", {
            "name": customer_name or "Friend",
            "shop_url": "https://falconherbs.com/shop/",
            "year": datetime.now().year
        })
        return self.send_email(customer_email, subject, html)
    
    def send_order_confirmation(self, customer_email: str,
                                order_data: dict) -> dict:
        """Send order confirmation email."""
        subject = f"Order Confirmed #{order_data.get('id', '')} — Falcon Herbs"
        html = self._load_template("order_confirmation", {
            "order_id": order_data.get("id", ""),
            "total": order_data.get("total", "0"),
            "items": order_data.get("items", []),
            "name": order_data.get("name", "Customer")
        })
        return self.send_email(customer_email, subject, html)
    
    def send_campaign(self, recipients: List[str], subject: str,
                      html_body: str) -> dict:
        """Send campaign to multiple recipients."""
        results = {"sent": 0, "failed": 0, "errors": []}
        
        for email in recipients:
            result = self.send_email(email, subject, html_body)
            if result["success"]:
                results["sent"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{email}: {result['error']}")
        
        return {
            "success": results["sent"] > 0,
            "message": f"""📧 *CAMPAIGN SENT*
✅ Sent: {results['sent']}
❌ Failed: {results['failed']}
📨 Total: {len(recipients)}"""
        }
    
    def get_status(self) -> str:
        """Get email system status for WhatsApp."""
        configured = self.is_configured()
        logs = self._load_log()
        total_sent = len([l for l in logs if l.get("status") == "sent"])
        
        return f"""📧 *EMAIL SYSTEM STATUS*
{'─' * 25}
🔌 SMTP: {'✅ Configured' if configured else '❌ Not configured'}
📤 Host: {self.host}:{self.port}
📊 Total Sent: {total_sent}

{'Add SMTP_USER + SMTP_PASSWORD to .env' if not configured else '✅ Ready to send'}"""
    
    def _load_template(self, name: str, data: dict) -> str:
        """Load and fill email template."""
        template_file = TEMPLATES_DIR / f"{name}.html"
        if template_file.exists():
            html = template_file.read_text(encoding="utf-8")
            for key, value in data.items():
                html = html.replace(f"{{{{{key}}}}}", str(value))
            return html
        
        # Fallback: simple template
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2d5016;">🌿 Falcon Herbs</h2>
            <p>Thank you for choosing Falcon Herbs — authentic Ayurvedic wellness.</p>
            <p>{json.dumps(data, indent=2)}</p>
            <hr>
            <small style="color: #888;">Falcon Herbs | falconherbs.com</small>
        </div>
        """
    
    def _ensure_templates(self):
        """Create default email templates if missing."""
        welcome = TEMPLATES_DIR / "welcome.html"
        if not welcome.exists():
            welcome.write_text("""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #2d5016, #4a7c1f); border-radius: 10px;">
        <h1 style="color: white; margin: 0;">🌿 Welcome to Falcon Herbs</h1>
    </div>
    <div style="padding: 20px;">
        <p>Dear {{name}},</p>
        <p>Thank you for joining the Falcon Herbs family! We're committed to bringing you the finest authentic Ayurvedic herbal products.</p>
        <p>Explore our collection:</p>
        <div style="text-align: center; margin: 20px 0;">
            <a href="{{shop_url}}" style="background: #2d5016; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-size: 16px;">Visit Our Shop →</a>
        </div>
        <p>🌱 100% Natural Ingredients<br>📦 Free Shipping on Orders Over $50<br>🏥 Traditional Ayurvedic Formulations</p>
    </div>
    <hr style="border: 1px solid #eee;">
    <small style="color: #888;">© {{year}} Falcon Herbs | <a href="https://falconherbs.com">falconherbs.com</a></small>
</body>
</html>""", encoding="utf-8")
    
    def _log_email(self, to: str, subject: str, status: str):
        """Log email activity."""
        logs = self._load_log()
        logs.append({
            "to": to,
            "subject": subject,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
        # Keep last 500
        logs = logs[-500:]
        try:
            EMAIL_LOG.write_text(
                json.dumps(logs, indent=2), encoding="utf-8"
            )
        except:
            pass
    
    def _load_log(self) -> list:
        """Load email log."""
        try:
            return json.loads(EMAIL_LOG.read_text(encoding="utf-8"))
        except:
            return []


# Global instance
email_system = EmailSystem()
