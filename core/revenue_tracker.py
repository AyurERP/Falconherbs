"""
Falcon Agency — Revenue Tracker
Tracks revenue, costs, profit, and goals
Integrates with WooCommerce data
"""

import json
from datetime import datetime, timedelta
from pathlib import Path


class RevenueTracker:
    
    def __init__(self):
        self.data_dir = Path("data/revenue")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.revenue_file = self.data_dir / "revenue_log.json"
        self.costs_file = self.data_dir / "costs_log.json"
        self.goals_file = self.data_dir / "goals.json"
        self._init_files()
    
    def _init_files(self):
        for filepath, default in [
            (self.revenue_file, {"entries": [], "total": 0}),
            (self.costs_file, {"entries": [], "total": 0}),
            (self.goals_file, {
                "monthly_revenue_target": 12500,
                "monthly_targets": {},
                "daily_content_target": 1,
                "weekly_blog_target": 2
            }),
        ]:
            if not filepath.exists():
                with open(filepath, "w") as f:
                    json.dump(default, f, indent=2)
    
    def log_revenue(self, amount, source, description="",
                    currency="INR", order_id=None):
        """Log a revenue entry with dedup by order_id"""
        data = self._load(self.revenue_file)

        # Dedup: skip if order_id already exists
        if order_id:
            existing_ids = {
                e.get("order_id") for e in data["entries"]
                if e.get("order_id")
            }
            if order_id in existing_ids:
                return {"skipped": True, "reason": "duplicate",
                        "order_id": order_id}

        entry = {
            "date": datetime.now().isoformat(),
            "amount": float(amount),
            "source": source,
            "description": description,
            "currency": currency,
            "month": datetime.now().strftime("%Y-%m"),
            "order_id": order_id
        }
        data["entries"].append(entry)
        data["total"] = sum(e["amount"] for e in data["entries"])
        self._save(self.revenue_file, data)
        return entry
    
    def log_cost(self, amount, category, description="",
                 currency="INR", dedup_key=None):
        """Log a cost entry with dedup by key"""
        data = self._load(self.costs_file)

        # Auto-generate dedup key if not provided
        if not dedup_key:
            dedup_key = (f"cost_{category}_{amount}_"
                        f"{datetime.now().strftime('%Y-%m-%d')}")

        # Dedup: skip if same key already logged today
        existing_keys = {
            e.get("dedup_key") for e in data["entries"]
            if e.get("dedup_key")
        }
        if dedup_key in existing_keys:
            return {"skipped": True, "reason": "duplicate",
                    "dedup_key": dedup_key}

        entry = {
            "date": datetime.now().isoformat(),
            "amount": float(amount),
            "category": category,
            "description": description,
            "currency": currency,
            "month": datetime.now().strftime("%Y-%m"),
            "dedup_key": dedup_key
        }
        data["entries"].append(entry)
        data["total"] = sum(e["amount"] for e in data["entries"])
        self._save(self.costs_file, data)
        return entry
    
    def get_monthly_summary(self, month=None):
        """Get revenue/cost/profit for a month"""
        if not month:
            month = datetime.now().strftime("%Y-%m")
        
        revenue_data = self._load(self.revenue_file)
        costs_data = self._load(self.costs_file)
        goals_data = self._load(self.goals_file)
        
        month_revenue = sum(
            e["amount"] for e in revenue_data["entries"]
            if e.get("month") == month
        )
        month_costs = sum(
            e["amount"] for e in costs_data["entries"]
            if e.get("month") == month
        )
        
        target = goals_data.get("monthly_revenue_target", 12500)
        
        return {
            "month": month,
            "revenue": month_revenue,
            "costs": month_costs,
            "profit": month_revenue - month_costs,
            "target": target,
            "progress_pct": round(
                (month_revenue / target * 100) if target else 0, 1
            ),
            "remaining": max(0, target - month_revenue),
            "on_track": month_revenue >= (
                target * datetime.now().day / 30
            )
        }
    
    def sync_from_woocommerce(self, woo_orders_data):
        """Import orders from WooCommerce data"""
        if not woo_orders_data.get("success"):
            return {"error": "Invalid WooCommerce data"}
        
        orders = woo_orders_data["data"].get("orders", [])
        imported = 0
        
        revenue_data = self._load(self.revenue_file)
        existing_ids = {
            e.get("order_id") 
            for e in revenue_data["entries"]
        }
        
        for order in orders:
            order_id = f"woo_{order.get('id')}"
            if order_id in existing_ids:
                continue
            
            if order.get("status") in (
                "completed", "processing"
            ):
                entry = {
                    "date": order.get("date", 
                                      datetime.now().isoformat()),
                    "amount": float(order.get("total", 0)),
                    "source": "woocommerce",
                    "description": f"Order #{order.get('id')} — "
                                   f"{order.get('country', 'Unknown')}",
                    "currency": order.get("currency", "INR"),
                    "month": order.get("date", "")[:7],
                    "order_id": order_id,
                    "country": order.get("country")
                }
                revenue_data["entries"].append(entry)
                imported += 1
        
        revenue_data["total"] = sum(
            e["amount"] for e in revenue_data["entries"]
        )
        self._save(self.revenue_file, revenue_data)
        
        return {"imported": imported, "total_entries": len(
            revenue_data["entries"]
        )}
    
    def generate_whatsapp_report(self):
        """Daily revenue report for WhatsApp"""
        summary = self.get_monthly_summary()
        
        lines = [
            "💰 *DAILY REVENUE REPORT*",
            f"📅 {datetime.now().strftime('%d %b %Y')}",
            "─" * 25,
            f"📊 This Month: ₹{summary['revenue']:,.0f}",
            f"💸 Costs: ₹{summary['costs']:,.0f}",
            f"📈 Profit: ₹{summary['profit']:,.0f}",
            f"🎯 Target: ₹{summary['target']:,.0f}",
            f"📉 Remaining: ₹{summary['remaining']:,.0f}",
            f"{'✅' if summary['on_track'] else '⚠️'} "
            f"Progress: {summary['progress_pct']}%",
            "─" * 25,
            "🤖 _Falcon Agency_"
        ]
        
        return "\n".join(lines)
    
    def _load(self, filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    
    def _save(self, filepath, data):
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    tracker = RevenueTracker()
    print(tracker.generate_whatsapp_report())
