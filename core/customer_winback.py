"""
Falcon Agency -- Customer Win-Back System
Finds inactive customers (no orders in 90+ days),
generates reactivation emails, queues for approval.
NEVER auto-sends emails.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path


class CustomerWinback:
    """Find inactive customers, generate reactivation
    email drafts, queue for owner approval."""

    def __init__(self, bridge):
        self.bridge = bridge
        self.data_dir = Path("data/customer_winback")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.inactive_file = (
            self.data_dir / "inactive_customers.json"
        )
        self.emails_dir = self.data_dir / "email_drafts"
        self.emails_dir.mkdir(parents=True, exist_ok=True)

    # ── Find Inactive ──────────────────────────────────

    def find_inactive_customers(self, days=90):
        """Find customers with no orders in last N days.
        Returns {total_customers, inactive, customers}"""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {
                    "success": False,
                    "error": "WooCommerce not loaded",
                }

            # Get all customers
            cust_result = woo.get_customers(save=False)
            if not cust_result.get("success"):
                return {
                    "success": False,
                    "error": cust_result.get(
                        "error", "Cannot fetch customers"
                    ),
                }

            customers = cust_result["data"].get(
                "customers", []
            )

            # Get recent orders to identify active ones
            cutoff = datetime.now() - timedelta(days=days)
            orders_result = woo.get_orders(
                days_back=days, save=False
            )
            active_emails = set()
            if orders_result.get("success"):
                for o in orders_result["data"].get(
                    "orders", []
                ):
                    email = o.get("customer_email", "")
                    if email:
                        active_emails.add(email.lower())

            # Find inactive
            inactive = []
            for c in customers:
                email = c.get("email", "").lower()
                if not email:
                    continue
                if email not in active_emails:
                    inactive.append({
                        "id": c.get("id"),
                        "email": c.get("email"),
                        "first_name": c.get(
                            "first_name", ""
                        ),
                        "last_name": c.get(
                            "last_name", ""
                        ),
                        "country": c.get("country", ""),
                        "orders_count": c.get(
                            "orders_count", 0
                        ),
                        "total_spent": c.get(
                            "total_spent", "0"
                        ),
                    })

            # Save results
            data = {
                "scanned_at": datetime.now().isoformat(),
                "days_threshold": days,
                "total_customers": len(customers),
                "inactive_count": len(inactive),
                "customers": inactive,
            }
            with open(self.inactive_file, "w",
                      encoding="utf-8") as f:
                json.dump(data, f, indent=2,
                          ensure_ascii=False)

            return {
                "success": True,
                "total_customers": len(customers),
                "inactive": len(inactive),
                "customers": [
                    {
                        "name": "{} {}".format(
                            c["first_name"],
                            c["last_name"]
                        ).strip(),
                        "email": c["email"],
                        "orders": c["orders_count"],
                    }
                    for c in inactive[:20]
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Generate Emails ────────────────────────────────

    def generate_winback_emails(self, count=10):
        """Generate reactivation email drafts for top N
        inactive customers. NEVER sends automatically."""
        try:
            if not self.inactive_file.exists():
                return {
                    "success": False,
                    "error": "No inactive data. Run "
                             "find_inactive_customers() first.",
                }

            with open(self.inactive_file,
                      encoding="utf-8") as f:
                data = json.load(f)

            inactive = data.get("customers", [])[:count]
            if not inactive:
                return {
                    "success": True,
                    "generated": 0,
                    "message": "No inactive customers found.",
                }

            generated = 0
            for cust in inactive:
                cid = cust.get("id", "unknown")
                name = "{} {}".format(
                    cust.get("first_name", ""),
                    cust.get("last_name", "")
                ).strip() or "Valued Customer"

                # Try AI rewrite if available
                email_body = ""
                ai = self.bridge.tools.get("ai_client")
                if ai:
                    try:
                        prompt = (
                            "Write a short, warm "
                            "reactivation email for '{}' "
                            "who hasn't ordered from "
                            "Falcon Herbs (Ayurvedic "
                            "products) in 90+ days. "
                            "Include a special welcome-back "
                            "offer. Max 150 words. "
                            "Professional but warm tone."
                        ).format(name)
                        response = ai.generate(prompt)
                        if response:
                            email_body = response
                    except Exception:
                        pass

                # Fallback template
                if not email_body:
                    email_body = (
                        "Dear {},\n\n"
                        "We noticed you haven't visited "
                        "Falcon Herbs in a while and we "
                        "miss you!\n\n"
                        "As a welcome-back gesture, enjoy "
                        "15% OFF your next order with "
                        "code: WELCOME15\n\n"
                        "Our latest Ayurvedic wellness "
                        "products are waiting for you.\n\n"
                        "Warm regards,\n"
                        "Team Falcon Herbs"
                    ).format(name)

                draft = {
                    "customer_id": cid,
                    "customer_name": name,
                    "customer_email": cust.get(
                        "email", ""
                    ),
                    "subject": "We miss you, {}! "
                               "Special offer inside "
                               "\U0001F331".format(
                                   name.split()[0]
                                   if name != "Valued Customer"
                                   else "Friend"
                               ),
                    "body": email_body,
                    "status": "pending",
                    "created_at": (
                        datetime.now().isoformat()
                    ),
                    "sent_at": None,
                }

                out = self.emails_dir / f"{cid}.json"
                with open(out, "w",
                          encoding="utf-8") as f:
                    json.dump(draft, f, indent=2,
                              ensure_ascii=False)
                generated += 1

            return {
                "success": True,
                "generated": generated,
                "message": "{} email drafts created in "
                           "data/customer_winback/"
                           "email_drafts/".format(generated),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Status ─────────────────────────────────────────

    def get_winback_status(self):
        """WhatsApp-friendly summary"""
        try:
            # Inactive count
            inactive_count = 0
            if self.inactive_file.exists():
                try:
                    with open(self.inactive_file,
                              encoding="utf-8") as f:
                        data = json.load(f)
                    inactive_count = data.get(
                        "inactive_count", 0
                    )
                except Exception:
                    pass

            # Email drafts
            drafts = list(self.emails_dir.glob("*.json"))
            pending = 0
            sent = 0
            for d in drafts:
                try:
                    with open(d, encoding="utf-8") as f:
                        info = json.load(f)
                    if info.get("status") == "sent":
                        sent += 1
                    else:
                        pending += 1
                except Exception:
                    continue

            return (
                "\U0001F465 *CUSTOMER WIN-BACK*\n"
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
                "\U0001F6AB Inactive customers: {}\n"
                "\u2709\uFE0F Email drafts: {}\n"
                "   \u23F3 Pending: {}\n"
                "   \u2705 Sent: {}\n\n"
                "\U0001F4C2 data/customer_winback/"
            ).format(
                inactive_count, len(drafts),
                pending, sent
            )
        except Exception as e:
            return f"\u274c Win-back status error: {e}"

    # ── Mark Sent ──────────────────────────────────────

    def mark_email_sent(self, customer_id):
        """Mark an email draft as sent (after manual
        send by owner)"""
        try:
            draft_file = (
                self.emails_dir / f"{customer_id}.json"
            )
            if not draft_file.exists():
                return {
                    "success": False,
                    "error": "No draft for customer "
                             "{}".format(customer_id),
                }

            with open(draft_file,
                      encoding="utf-8") as f:
                data = json.load(f)

            data["status"] = "sent"
            data["sent_at"] = datetime.now().isoformat()

            with open(draft_file, "w",
                      encoding="utf-8") as f:
                json.dump(data, f, indent=2,
                          ensure_ascii=False)

            return {
                "success": True,
                "message": "Email for {} marked as "
                           "sent.".format(
                               data.get("customer_name",
                                        customer_id)
                           ),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
