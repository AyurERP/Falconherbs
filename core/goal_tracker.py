"""Goal Tracker — 30-day targets and progress tracking"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

class GoalTracker:
    """Track 30-day goals and daily progress"""
    
    def __init__(self):
        self.goals_file = os.path.join(DATA_DIR, 'monthly_goals.json')
        self.progress_file = os.path.join(DATA_DIR, 'daily_progress.json')
        self._ensure_files()
    
    def _ensure_files(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for filepath, default in [
            (self.goals_file, {"goals": {}, "created": None}),
            (self.progress_file, {"entries": []})
        ]:
            if not os.path.exists(filepath):
                self._save_json(filepath, default)
    
    def _load_json(self, filepath: str) -> dict:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_json(self, filepath: str, data: dict):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    
    def set_monthly_goals(self, goals: Dict) -> bool:
        """Set 30-day goals"""
        data = {
            "period_start": datetime.now().isoformat(),
            "period_end": (datetime.now() + timedelta(days=30)).isoformat(),
            "goals": goals,
            "status": "active"
        }
        self._save_json(self.goals_file, data)
        return True
    
    def get_current_goals(self) -> Dict:
        """Get current 30-day goals"""
        return self._load_json(self.goals_file)
    
    def log_daily_progress(self, metrics: Dict) -> bool:
        """Log daily progress"""
        data = self._load_json(self.progress_file)
        today = datetime.now().date().isoformat()
        
        # Check if today already has entry
        for entry in data.get("entries", []):
            if entry.get("date") == today:
                entry["metrics"].update(metrics)
                entry["updated"] = datetime.now().isoformat()
                self._save_json(self.progress_file, data)
                return True
        
        # New entry
        entry = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        }
        data.setdefault("entries", []).append(entry)
        self._save_json(self.progress_file, data)
        return True
    
    def get_progress_summary(self) -> Dict:
        """Get progress vs goals"""
        goals_data = self.get_current_goals()
        progress_data = self._load_json(self.progress_file)
        goals = goals_data.get('goals', {})
        entries = progress_data.get('entries', [])
        
        # Calculate totals
        total_revenue = sum(e.get('metrics', {}).get('revenue', 0) for e in entries)
        total_orders = sum(e.get('metrics', {}).get('orders', 0) for e in entries)
        total_tasks = sum(e.get('metrics', {}).get('tasks_completed', 0) for e in entries)
        total_blogs = sum(e.get('metrics', {}).get('blog_posts', 0) for e in entries)
        total_social = sum(e.get('metrics', {}).get('social_posts', 0) for e in entries)
        
        # Target values
        target_revenue = goals.get('revenue_target', 0)
        target_blogs = goals.get('blog_posts_target', 0)
        target_social = goals.get('social_posts_target', 0)
        
        days_elapsed = len(set(e.get('date') for e in entries))
        
        return {
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
    
    def generate_daily_report(self) -> str:
        """Generate WhatsApp-friendly daily report"""
        summary = self.get_progress_summary()
        goals = self.get_current_goals().get('goals', {})
        today = datetime.now().strftime('%d %b %Y')
        
        status_emoji = "🟢 ON TRACK" if summary.get('on_track') else "🔴 BEHIND"
        
        report = f"""📊 DAILY REPORT — {today}

💰 REVENUE:
├── Target: ₹{goals.get('revenue_target', 0):,}
├── Achieved: ₹{summary['revenue']['achieved']:,}
└── Progress: {summary['revenue']['percentage']}%

📝 CONTENT:
├── Blogs: {summary['content']['blogs_done']}/{summary['content']['blogs_target']}
└── Social: {summary['content']['social_done']}/{summary['content']['social_target']}

📦 Orders: {summary['orders']}
✅ Tasks: {summary['tasks_completed']}
📅 Day: {summary['period']['days_elapsed']}/30

{status_emoji}"""
        return report.strip()

# Global instance
goal_tracker = GoalTracker()
