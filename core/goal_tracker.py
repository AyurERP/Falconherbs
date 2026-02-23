"""Goal Tracker — Multi-site 30-day targets and progress tracking"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Default sites
DEFAULT_SITE = "falconherbs.com"


class GoalTracker:
    """Track 30-day goals and daily progress per site."""
    
    def __init__(self):
        self.goals_dir = os.path.join(DATA_DIR, 'goals')
        self.progress_dir = os.path.join(DATA_DIR, 'goals')
        os.makedirs(self.goals_dir, exist_ok=True)
        
        # Migrate old single-file format if exists
        self._migrate_old_format()
    
    def _migrate_old_format(self):
        """Migrate from old single-file to multi-site format."""
        old_goals = os.path.join(DATA_DIR, 'monthly_goals.json')
        old_progress = os.path.join(DATA_DIR, 'daily_progress.json')
        
        if os.path.exists(old_goals):
            try:
                data = self._load_json(old_goals)
                site = data.get('goals', {}).get('site', DEFAULT_SITE)
                new_path = self._goals_path(site)
                if not os.path.exists(new_path):
                    self._save_json(new_path, data)
            except:
                pass
        
        if os.path.exists(old_progress):
            try:
                data = self._load_json(old_progress)
                new_path = self._progress_path(DEFAULT_SITE)
                if not os.path.exists(new_path):
                    self._save_json(new_path, data)
            except:
                pass
    
    def _goals_path(self, site: str) -> str:
        safe = site.replace('.', '_').replace('/', '_')
        return os.path.join(self.goals_dir, f"goals_{safe}.json")
    
    def _progress_path(self, site: str) -> str:
        safe = site.replace('.', '_').replace('/', '_')
        return os.path.join(self.goals_dir, f"progress_{safe}.json")
    
    def _load_json(self, filepath: str) -> dict:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_json(self, filepath: str, data: dict):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    
    def set_monthly_goals(self, goals: Dict, site: str = DEFAULT_SITE) -> bool:
        """Set 30-day goals for a specific site."""
        # Also accept site from goals dict for backward compat
        site = goals.pop('site', site)
        data = {
            "site": site,
            "period_start": datetime.now().isoformat(),
            "period_end": (datetime.now() + timedelta(days=30)).isoformat(),
            "goals": goals,
            "status": "active"
        }
        self._save_json(self._goals_path(site), data)
        return True
    
    def get_current_goals(self, site: str = DEFAULT_SITE) -> Dict:
        """Get current 30-day goals for a site."""
        return self._load_json(self._goals_path(site))
    
    def get_all_sites(self) -> list:
        """Get all sites with active goals."""
        sites = []
        for f in os.listdir(self.goals_dir):
            if f.startswith("goals_") and f.endswith(".json"):
                site_key = f[6:-5].replace('_', '.')
                sites.append(site_key)
        return sites
    
    def log_daily_progress(self, metrics: Dict, site: str = DEFAULT_SITE) -> bool:
        """Log daily progress for a site."""
        site = metrics.pop('site', site)
        filepath = self._progress_path(site)
        data = self._load_json(filepath)
        today = datetime.now().date().isoformat()
        
        for entry in data.get("entries", []):
            if entry.get("date") == today:
                entry["metrics"].update(metrics)
                entry["updated"] = datetime.now().isoformat()
                self._save_json(filepath, data)
                return True
        
        entry = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        }
        data.setdefault("entries", []).append(entry)
        self._save_json(filepath, data)
        return True
    
    def get_progress_summary(self, site: str = DEFAULT_SITE) -> Dict:
        """Get progress vs goals for a site."""
        goals_data = self.get_current_goals(site)
        progress_data = self._load_json(self._progress_path(site))
        goals = goals_data.get('goals', {})
        entries = progress_data.get('entries', [])
        
        total_revenue = sum(e.get('metrics', {}).get('revenue', 0) for e in entries)
        total_orders = sum(e.get('metrics', {}).get('orders', 0) for e in entries)
        total_tasks = sum(e.get('metrics', {}).get('tasks_completed', 0) for e in entries)
        total_blogs = sum(e.get('metrics', {}).get('blog_posts', 0) for e in entries)
        total_social = sum(e.get('metrics', {}).get('social_posts', 0) for e in entries)
        
        target_revenue = goals.get('revenue_target', 0)
        target_blogs = goals.get('blog_posts_target', 0)
        target_social = goals.get('social_posts_target', 0)
        
        days_elapsed = len(set(e.get('date') for e in entries))
        
        return {
            "site": site,
            "period": {
                "start": goals_data.get('period_start'),
                "end": goals_data.get('period_end'),
                "days_elapsed": days_elapsed,
                "days_remaining": 30 - days_elapsed
            },
            "revenue": {
                "target": target_revenue,
                "achieved": total_revenue,
                "percentage": round((total_revenue / target_revenue * 100), 1) if target_revenue else 0
            },
            "content": {
                "blogs_target": target_blogs,
                "blogs_done": total_blogs,
                "social_target": target_social,
                "social_done": total_social
            },
            "orders": total_orders,
            "tasks_completed": total_tasks,
            "on_track": (total_revenue / target_revenue * 100) >= (days_elapsed / 30 * 100) if target_revenue and days_elapsed else True
        }
    
    def generate_daily_report(self, site: str = None) -> str:
        """Generate WhatsApp-friendly daily report (all sites or specific)."""
        sites = [site] if site else self.get_all_sites()
        if not sites:
            sites = [DEFAULT_SITE]
        
        today = datetime.now().strftime('%d %b %Y')
        reports = []
        
        for s in sites:
            summary = self.get_progress_summary(s)
            goals = self.get_current_goals(s).get('goals', {})
            currency = goals.get('currency', 'INR')
            symbol = '$' if currency == 'USD' else '₹'
            
            status_emoji = "🟢 ON TRACK" if summary.get('on_track') else "🔴 BEHIND"
            
            report = f"""🌐 *{s.upper()}*

💰 REVENUE:
├── Target: {symbol}{goals.get('revenue_target', 0):,}
├── Achieved: {symbol}{summary['revenue']['achieved']:,}
└── Progress: {summary['revenue']['percentage']}%

📝 CONTENT:
├── Blogs: {summary['content']['blogs_done']}/{summary['content']['blogs_target']}
└── Social: {summary['content']['social_done']}/{summary['content']['social_target']}

📦 Orders: {summary['orders']}
📅 Day: {summary['period']['days_elapsed']}/30
{status_emoji}"""
            reports.append(report.strip())
        
        header = f"📊 DAILY REPORT — {today}\n{'─' * 25}"
        return header + "\n\n" + "\n\n".join(reports)


# Global instance
goal_tracker = GoalTracker()
