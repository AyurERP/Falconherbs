"""
Falcon Agency — Lead & Inventory Predictor
Analyzes sales velocity to predict stock-outs (Burn Rate).
Helps optimize ad spend and prevents out-of-stock losses.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

class LeadPredictor:
    """Predicts stock exhaustion and sales trends."""

    def __init__(self, bridge):
        self.bridge = bridge
        self.data_dir = Path("data/predictions")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_burn_rate_report(self, days_back=30):
        """Analyze last 30 days of sales to predict stock-out dates.
        Returns a WhatsApp-friendly report."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, "error": "WooCommerce tool missing"}

            # 1. Get current products/stock
            p_result = woo.get_all_products(save=False)
            if not p_result.get("success"):
                return p_result
            products = p_result["data"].get("products", [])

            # 2. Get past orders for velocity
            o_result = woo.get_orders(days_back=days_back, save=False)
            if not o_result.get("success"):
                return o_result
            orders = o_result["data"].get("orders", [])

            # 3. Calculate Velocity (Units sold per product)
            velocity = {} # {product_id: units_sold}
            for order in orders:
                if order.get("status") not in ("completed", "processing"):
                    continue
                for item in order.get("items", []):
                    # Item names are more reliable than IDs if variants are used
                    name = item.get("name")
                    qty = item.get("quantity", 0)
                    velocity[name] = velocity.get(name, 0) + qty

            report_items = []
            low_stock_alerts = []

            for p in products:
                name = p.get("name")
                qty = p.get("stock_quantity")
                
                # Default to 0 if stock is managed but quantity is missing
                if qty is None:
                    continue 

                units_sold = velocity.get(name, 0)
                daily_velocity = units_sold / days_back
                
                if daily_velocity > 0:
                    days_left = round(qty / daily_velocity)
                    prediction_date = (datetime.now() + timedelta(days=days_left)).strftime("%d %b")
                else:
                    days_left = 999
                    prediction_date = "N/A"

                item_data = {
                    "name": name,
                    "stock": qty,
                    "daily_velocity": round(daily_velocity, 2),
                    "days_left": days_left,
                    "prediction": prediction_date
                }
                
                if days_left <= 14:
                    low_stock_alerts.append(item_data)
                
                if days_left < 60 or units_sold > 0: # Only show active/risky items
                    report_items.append(item_data)

            # Sort by urgency
            report_items.sort(key=lambda x: x["days_left"])

            return {
                "success": True,
                "data": {
                    "all": report_items,
                    "risky": low_stock_alerts
                },
                "summary": self._format_whatsapp_report(report_items, low_stock_alerts)
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _format_whatsapp_report(self, items, alerts):
        """Format the report for WhatsApp"""
        lines = [
            "📉 *INVENTORY BURN RATE*",
            "────────────────",
        ]

        if alerts:
            lines.append("⚠️ *CRITICAL LOW STOCK*")
            for a in alerts[:5]:
                lines.append(f"• *{a['name']}*: {a['stock']} units ({a['days_left']} days left)")
            lines.append("────────────────")

        lines.append("📊 *Velocity Report (Top Items)*")
        for i in items[:8]:
            status = "🔴" if i['days_left'] <= 7 else ("🟡" if i['days_left'] <= 14 else "🟢")
            lines.append(f"{status} *{i['name']}*")
            lines.append(f"   Stock: {i['stock']} | Velocity: {i['daily_velocity']}/day")
            if i['days_left'] < 100:
                lines.append(f"   Est. Stockout: *{i['prediction']}*")
            lines.append("")

        lines.append("🤖 _Falcon Agency Prediction_")
        return "\n".join(lines)
