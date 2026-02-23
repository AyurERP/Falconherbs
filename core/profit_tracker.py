"""
Profit Tracker — Facade over RevenueTracker
=============================================
CONSOLIDATED: All revenue/cost data now flows through
RevenueTracker (data/revenue/). This class provides
backward compatibility for any code that still calls
ProfitTracker methods.

Old files (data/revenue.json, data/costs.json) are
no longer written to. Use scripts/migrate_revenue.py
to import old data.
"""

import re
from datetime import datetime
from typing import Dict


class ProfitTracker:
    """
    Unified revenue/cost tracker.
    Delegates to RevenueTracker for all operations.
    """

    def __init__(self):
        from core.revenue_tracker import RevenueTracker
        self._tracker = RevenueTracker()

    def log_revenue(self, amount: float, source: str,
                    order_id: str = None, product: str = None,
                    site: str = "falconherbs.com") -> bool:
        """Log revenue entry with dedup"""
        # Extract order_id from source string if not provided
        if not order_id:
            order_id = self._extract_order_id(source)

        desc = f"{product or ''} | site={site}".strip(" |")
        result = self._tracker.log_revenue(
            amount=amount,
            source=source,
            description=desc,
            order_id=order_id
        )
        return not result.get("skipped", False)

    def log_cost(self, amount: float, category: str,
                 description: str = "",
                 site: str = "all") -> bool:
        """Log cost entry with dedup"""
        dedup_key = (f"cost_{category}_{amount}_"
                     f"{datetime.now().strftime('%Y-%m-%d')}_{site}")
        result = self._tracker.log_cost(
            amount=amount,
            category=category,
            description=f"{description} | site={site}".strip(" |"),
            dedup_key=dedup_key
        )
        return not result.get("skipped", False)

    def get_summary(self, days: int = 30,
                    site: str = None) -> Dict:
        """Get profit summary — delegates to RevenueTracker"""
        summary = self._tracker.get_monthly_summary()
        return {
            "period_days": days,
            "site": site or "all",
            "total_revenue": summary["revenue"],
            "total_costs": summary["costs"],
            "net_profit": summary["profit"],
            "roi_percentage": round(
                ((summary["profit"]) / summary["costs"] * 100), 1
            ) if summary["costs"] > 0 else 0,
            "revenue_breakdown": {},
            "costs_breakdown": {},
            "order_count": 0
        }

    def get_today_summary(self, site: str = None) -> Dict:
        """Get today's summary"""
        summary = self._tracker.get_monthly_summary()
        today = datetime.now().date().isoformat()
        return {
            "date": today,
            "site": site or "all",
            "revenue": summary["revenue"],
            "costs": summary["costs"],
            "profit": summary["profit"],
            "orders": 0
        }

    def generate_profit_report(self, days: int = 30) -> str:
        """WhatsApp-friendly profit report"""
        return self._tracker.generate_whatsapp_report()

    @staticmethod
    def _extract_order_id(source: str) -> str:
        """Extract order_id from source strings like
        'WooCommerce order #1234'"""
        match = re.search(r'#(\d+)', source)
        return f"manual_{match.group(1)}" if match else None


# Global instance
profit_tracker = ProfitTracker()
