import json
import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

class RealDataReader:
    """Reads ACTUAL data from files - no fake data allowed"""
    
    @staticmethod
    def read_json_file(filename: str) -> dict | list | None:
        """Safely read a JSON file"""
        filepath = os.path.join(DATA_DIR, filename)
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            return {"error": f"Cannot read {filename}: {str(e)}"}
        return None
    
    @staticmethod
    def get_all_tasks() -> list:
        """Get ALL tasks from goals.json"""
        data = RealDataReader.read_json_file('goals.json')
        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get('goals', data.get('tasks', []))
        return []
    
    @staticmethod
    def get_failed_tasks() -> list:
        """Get tasks that actually failed with real reasons"""
        tasks = RealDataReader.get_all_tasks()
        failed = []
        for task in tasks:
            status = str(task.get('status', '')).lower()
            if status in ['failed', 'fail', 'error', 'timeout']:
                failed.append({
                    "task": task.get('task', task.get('name', 'unknown')),
                    "site": task.get('site', 'unknown'),
                    "status": status,
                    "reason": task.get('reason', task.get('error', task.get('result_summary', 'No reason recorded'))),
                    "timestamp": task.get('timestamp', task.get('date', 'unknown'))
                })
        return failed
    
    @staticmethod
    def get_completed_tasks() -> list:
        """Get tasks that actually completed"""
        tasks = RealDataReader.get_all_tasks()
        completed = []
        for task in tasks:
            status = str(task.get('status', '')).lower()
            if status in ['complete', 'completed', 'success', 'done']:
                completed.append({
                    "task": task.get('task', task.get('name', 'unknown')),
                    "site": task.get('site', 'unknown'),
                    "result": task.get('result_summary', 'Completed'),
                    "timestamp": task.get('timestamp', task.get('date', 'unknown'))
                })
        return completed
    
    @staticmethod
    def get_spend() -> dict:
        """Get REAL spending data"""
        data = RealDataReader.read_json_file('spend.json')
        if data is None:
            return {"today": "$0.00", "month": "$0.00", "note": "No spend data found"}
        return data
    
    @staticmethod
    def get_recent_logs(lines: int = 30) -> str:
        """Get REAL recent log entries"""
        log_file = os.path.join(LOGS_DIR, 'falcon.log')
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    return ''.join(all_lines[-lines:])
            return "Log file not found"
        except Exception as e:
            return f"Cannot read logs: {str(e)}"
    
    @staticmethod
    def get_real_system_status() -> dict:
        """Get COMPLETE real system status - this is THE source of truth"""
        all_tasks = RealDataReader.get_all_tasks()
        failed = RealDataReader.get_failed_tasks()
        completed = RealDataReader.get_completed_tasks()
        spend = RealDataReader.get_spend()
        
        return {
            "data_source": "REAL - from goals.json, spend.json, falcon.log",
            "total_tasks_ever": len(all_tasks),
            "completed_count": len(completed),
            "failed_count": len(failed),
            "completed_tasks": completed[-5:] if completed else [],
            "failed_tasks": failed if failed else [],
            "spending": spend,
            "last_updated": datetime.now().isoformat()
        }
