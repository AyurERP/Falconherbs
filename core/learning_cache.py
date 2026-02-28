import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

LEARNING_FILE = Path("data/lessons_learned.json")

class LearningCache:
    """
    Falcon Agency Self-Learning Repository.
    Records failures, successes, and patterns to avoid repeating mistakes.
    """
    
    def __init__(self):
        self._load()

    def _load(self):
        if LEARNING_FILE.exists():
            try:
                with open(LEARNING_FILE, "r") as f:
                    self.data = json.load(f)
            except:
                self.data = {"failures": {}, "success_patterns": {}, "last_updated": ""}
        else:
            self.data = {"failures": {}, "success_patterns": {}, "last_updated": ""}

    def _save(self):
        self.data["last_updated"] = datetime.now().isoformat()
        with open(LEARNING_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def record_failure(self, task_name: str, error_msg: str, agent: str):
        """Record a failure pattern to warn the boss next time."""
        key = f"{task_name}_{agent}".lower()
        if key not in self.data["failures"]:
            self.data["failures"][key] = {"count": 0, "last_error": "", "occurrences": []}
        
        entry = self.data["failures"][key]
        entry["count"] += 1
        entry["last_error"] = error_msg
        entry["occurrences"].append({
            "timestamp": datetime.now().isoformat(),
            "error": error_msg
        })
        
        # Keep only last 5 occurrences
        entry["occurrences"] = entry["occurrences"][-5:]
        self._save()

    def get_lesson(self, task_name: str, agent: str) -> Optional[str]:
        """Check if we have a lesson for this task."""
        key = f"{task_name}_{agent}".lower()
        fail_data = self.data["failures"].get(key)
        
        if fail_data and fail_data["count"] >= 2:
            return (
                f"⚠️ *SELF-LEARNING WARNING*: This task (`{task_name}`) has failed {fail_data['count']} times recently. "
                f"Last error: `{fail_data['last_error']}`. Please check environment/config."
            )
        return None

    def record_success(self, task_name: str, agent: str):
        """Clear failures on success."""
        key = f"{task_name}_{agent}".lower()
        if key in self.data["failures"]:
            del self.data["failures"][key]
            self._save()

# Global singleton
learning = LearningCache()
