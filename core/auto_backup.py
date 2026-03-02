"""
Auto Backup Scheduler — Automatic daily backups with 
WhatsApp confirmation. Integrates with Director schedule.

B5: Ensures data safety without manual intervention.
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Files to backup
CRITICAL_FILES = [
    "falcon.db",
    "monthly_goals.json",
    "daily_progress.json",
    "revenue.json",
    "costs.json",
    "goals.json",
    "schedule.json",
    "extended_schedule.json",
    "content_index.json"
]

# Max backups to keep (auto-prune old ones)
MAX_BACKUPS = 14  # 2 weeks


class AutoBackup:
    """Automatic backup system with rotation."""
    
    def __init__(self):
        self.data_dir = DATA_DIR
        self.backup_dir = BACKUP_DIR
    
    def create_daily_backup(self) -> dict:
        """
        Create a daily backup of all critical data files.
        Called by Director schedule at configured time.
        """
        today = datetime.now().strftime("%Y%m%d")
        backup_folder = self.backup_dir / f"auto_{today}"
        
        # Skip if already backed up today
        if backup_folder.exists():
            return {
                "success": True,
                "message": f"Backup already exists for {today}",
                "skipped": True
            }
        
        try:
            backup_folder.mkdir(parents=True, exist_ok=True)
            backed_up = []
            failed = []
            total_size = 0
            
            for filename in CRITICAL_FILES:
                src = self.data_dir / filename
                if src.exists():
                    dst = backup_folder / filename
                    shutil.copy2(str(src), str(dst))
                    size = src.stat().st_size
                    total_size += size
                    backed_up.append(filename)
                else:
                    failed.append(f"{filename} (not found)")
            
            # Also backup goals directory
            goals_dir = self.data_dir / "goals"
            if goals_dir.exists():
                goals_backup = backup_folder / "goals"
                shutil.copytree(str(goals_dir), str(goals_backup), 
                               dirs_exist_ok=True)
                backed_up.append("goals/")
            
            # Also backup content drafts
            drafts_dir = self.data_dir / "content" / "drafts"
            if drafts_dir.exists():
                drafts_backup = backup_folder / "drafts"
                shutil.copytree(str(drafts_dir), str(drafts_backup),
                               dirs_exist_ok=True)
                backed_up.append("drafts/")
            
            # Auto-prune old backups
            self._prune_old_backups()
            
            # Save backup manifest
            manifest = {
                "date": today,
                "timestamp": datetime.now().isoformat(),
                "files": backed_up,
                "failed": failed,
                "total_size_kb": total_size // 1024,
                "type": "auto_daily"
            }
            (backup_folder / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            
            return {
                "success": True,
                "send_whatsapp": True,
                "message": f"""💾 *AUTO BACKUP COMPLETE*
{'─' * 25}
📅 Date: {today}
📁 Files: {len(backed_up)}
💾 Size: {total_size // 1024}KB
{'⚠️ Missed: ' + ', '.join(failed) if failed else '✅ All files backed up'}

🗂️ Location: backups/auto_{today}/"""
            }
        
        except Exception as e:
            return {
                "success": False,
                "send_whatsapp": True,
                "message": f"🚨 *BACKUP FAILED!*\nError: {str(e)[:200]}"
            }
    
    def _prune_old_backups(self):
        """Remove backups older than MAX_BACKUPS."""
        auto_backups = sorted([
            d for d in self.backup_dir.iterdir() 
            if d.is_dir() and d.name.startswith("auto_")
        ], key=lambda d: d.name, reverse=True)
        
        for old in auto_backups[MAX_BACKUPS:]:
            try:
                shutil.rmtree(str(old))
            except OSError:
                pass
    
    def list_backups(self) -> str:
        """List all available backups."""
        backups = sorted([
            d for d in self.backup_dir.iterdir() if d.is_dir()
        ], key=lambda d: d.name, reverse=True)
        
        if not backups:
            return "💾 No backups found."
        
        lines = [f"💾 *BACKUPS ({len(backups)})*", "─" * 25]
        
        for b in backups[:10]:
            manifest = b / "manifest.json"
            if manifest.exists():
                try:
                    m = json.loads(manifest.read_text(encoding="utf-8"))
                    lines.append(
                        f"📁 {b.name} — {m.get('total_size_kb', '?')}KB "
                        f"({len(m.get('files', []))} files)"
                    )
                    continue
                except (OSError, json.JSONDecodeError, ValueError):
                    pass
            # Fallback: count files
            files = list(b.iterdir())
            lines.append(f"📁 {b.name} — {len(files)} items")
        
        if len(backups) > 10:
            lines.append(f"\n... and {len(backups) - 10} more")
        
        return "\n".join(lines)
    
    def get_status(self) -> dict:
        """Get backup system status."""
        auto_backups = [
            d for d in self.backup_dir.iterdir() 
            if d.is_dir() and d.name.startswith("auto_")
        ]
        latest = max(auto_backups, key=lambda d: d.name) if auto_backups else None
        
        return {
            "total_backups": len(list(self.backup_dir.iterdir())),
            "auto_backups": len(auto_backups),
            "latest": latest.name if latest else "None",
            "max_kept": MAX_BACKUPS
        }


# Global instance
auto_backup = AutoBackup()
