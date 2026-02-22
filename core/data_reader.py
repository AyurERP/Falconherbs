import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')

def get_recent_tasks(limit: int = 10) -> list:
    """Get recent tasks from goals.json"""
    try:
        goals_file = os.path.join(DATA_DIR, 'goals.json')
        if os.path.exists(goals_file):
            with open(goals_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data[-limit:]
                elif isinstance(data, dict) and 'goals' in data:
                    return data['goals'][-limit:]
        return []
    except Exception as e:
        return [{"error": str(e)}]

def get_failed_tasks() -> list:
    """Get all failed tasks"""
    tasks = get_recent_tasks(100)
    return [t for t in tasks if t.get('status', '').lower() in ['failed', 'fail', 'error']]

def get_spend_summary() -> dict:
    """Get spending summary"""
    try:
        spend_file = os.path.join(DATA_DIR, 'spend.json')
        if os.path.exists(spend_file):
            with open(spend_file, 'r') as f:
                return json.load(f)
        return {"today": 0, "month": 0}
    except:
        return {"today": 0, "month": 0}

def get_recent_logs(lines: int = 20) -> str:
    """Get recent log entries"""
    try:
        log_file = os.path.join(LOGS_DIR, 'falcon.log')
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        return "No logs found"
    except Exception as e:
        return f"Error reading logs: {e}"

def get_system_summary() -> dict:
    """Get complete system summary for AI context"""
    tasks = get_recent_tasks(20)
    failed = get_failed_tasks()
    spend = get_spend_summary()
    
    return {
        "total_tasks": len(tasks),
        "completed": len([t for t in tasks if t.get('status', '').lower() in ['complete', 'completed', 'success']]),
        "failed": len(failed),
        "failed_tasks": failed[:5],  # Last 5 failures with details
        "recent_tasks": tasks[-5:],  # Last 5 tasks
        "spend": spend
    }
