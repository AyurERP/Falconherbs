"""Profit Tracker — Revenue, Costs, and Real Profit Tracking"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

class ProfitTracker:
    """Track real revenue, costs, and profit"""
    
    def __init__(self):
        self.revenue_file = os.path.join(DATA_DIR, 'revenue.json')
        self.costs_file = os.path.join(DATA_DIR, 'costs.json')
        self._ensure_files()
    
    def _ensure_files(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for filepath in [self.revenue_file, self.costs_file]:
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump({"entries": []}, f)
    
    def _load_json(self, filepath: str) -> dict:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"entries": []}
    
    def _save_json(self, filepath: str, data: dict):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    
    def log_revenue(self, amount: float, source: str, order_id: str = None, product: str = None, site: str = "falconherbs.com") -> bool:
        """Log revenue entry"""
        data = self._load_json(self.revenue_file)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().date().isoformat(),
            "amount": amount,
            "source": source,
            "order_id": order_id,
            "product": product,
            "site": site
        }
        data["entries"].append(entry)
        self._save_json(self.revenue_file, data)
        return True
    
    def log_cost(self, amount: float, category: str, description: str = "", site: str = "all") -> bool:
        """Log cost entry"""
        data = self._load_json(self.costs_file)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().date().isoformat(),
            "amount": amount,
            "category": category,
            "description": description,
            "site": site
        }
        data["entries"].append(entry)
        self._save_json(self.costs_file, data)
        return True
    
    def get_summary(self, days: int = 30, site: str = None) -> Dict:
        """Get profit summary for last N days"""
        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
        
        revenue_data = self._load_json(self.revenue_file)
        costs_data = self._load_json(self.costs_file)
        
        # Filter by date and optionally by site
        def filter_entries(entries, site_filter=None):
            filtered = [e for e in entries if e.get('date', '') >= cutoff]
            if site_filter:
                filtered = [e for e in filtered if e.get('site') == site_filter or e.get('site') == 'all']
            return filtered
        
        revenue_entries = filter_entries(revenue_data.get('entries', []), site)
        cost_entries = filter_entries(costs_data.get('entries', []), site)
        
        total_revenue = sum(e['amount'] for e in revenue_entries)
        total_costs = sum(e['amount'] for e in cost_entries)
        
        # Revenue by source
        revenue_by_source = {}
        for e in revenue_entries:
            src = e.get('source', 'other')
            revenue_by_source[src] = revenue_by_source.get(src, 0) + e['amount']
        
        # Costs by category
        costs_by_category = {}
        for e in cost_entries:
            cat = e.get('category', 'other')
            costs_by_category[cat] = costs_by_category.get(cat, 0) + e['amount']
        
        return {
            "period_days": days,
            "site": site or "all",
            "total_revenue": total_revenue,
            "total_costs": total_costs,
            "net_profit": total_revenue - total_costs,
            "roi_percentage": round(((total_revenue - total_costs) / total_costs * 100), 1) if total_costs > 0 else 0,
            "revenue_breakdown": revenue_by_source,
            "costs_breakdown": costs_by_category,
            "order_count": len([e for e in revenue_entries if e.get('order_id')])
        }
    
    def get_today_summary(self, site: str = None) -> Dict:
        """Get today's summary"""
        today = datetime.now().date().isoformat()
        
        revenue_data = self._load_json(self.revenue_file)
        costs_data = self._load_json(self.costs_file)
        
        def filter_today(entries, site_filter=None):
            filtered = [e for e in entries if e.get('date') == today]
            if site_filter:
                filtered = [e for e in filtered if e.get('site') == site_filter or e.get('site') == 'all']
            return filtered
        
        revenue_entries = filter_today(revenue_data.get('entries', []), site)
        cost_entries = filter_today(costs_data.get('entries', []), site)
        
        today_revenue = sum(e['amount'] for e in revenue_entries)
        today_costs = sum(e['amount'] for e in cost_entries)
        
        return {
            "date": today,
            "site": site or "all",
            "revenue": today_revenue,
            "costs": today_costs,
            "profit": today_revenue - today_costs,
            "orders": len([e for e in revenue_entries if e.get('order_id')])
        }
    
    def generate_profit_report(self, days: int = 30) -> str:
        """Generate WhatsApp-friendly profit report"""
        summary = self.get_summary(days)
        today = self.get_today_summary()
        
        profit_emoji = "📈" if summary['net_profit'] > 0 else "📉"
        
        report = f"""{profit_emoji} PROFIT REPORT — Last {days} Days

💰 REVENUE: ₹{summary['total_revenue']:,.0f}
💸 COSTS: ₹{summary['total_costs']:,.0f}
✨ NET PROFIT: ₹{summary['net_profit']:,.0f}
📊 ROI: {summary['roi_percentage']}%

📦 Total Orders: {summary['order_count']}

TODAY:
├── Revenue: ₹{today['revenue']:,.0f}
├── Costs: ₹{today['costs']:,.0f}
└── Profit: ₹{today['profit']:,.0f}"""
        return report.strip()

# Global instance
profit_tracker = ProfitTracker()
