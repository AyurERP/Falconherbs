"""
Falcon Agency — WHM Write Scheduler
=====================================

Queues product update operations (PUT requests to WHM server) and
executes them during the low-traffic window: 2:00–4:00 AM IST.

Why? WHM shared server has limited resources. Write operations
(update_product) should only happen at night.

Queue file: data/cache/write_queue.json

Usage:
    from core.write_scheduler import write_scheduler
    
    # Queue a product update (daytime — safe, non-blocking)
    write_scheduler.queue(
        site_key="falconherbs",
        product_id=123,
        data={"description": "...new text..."},
        reason="health_rewrite"
    )
    
    # Execute all pending writes (called by Director at 2 AM IST)
    result = write_scheduler.run_pending(woo_connector, dry_run=False)
    print(result["summary"])
    
    # Check queue status (for WhatsApp report)
    status = write_scheduler.get_status()
"""

import json
import time
from datetime import datetime
from pathlib import Path
from core.ist_time import now_ist, now_ist_str, is_write_window, minutes_until_write_window

QUEUE_FILE = Path("data/cache/write_queue.json")
MAX_QUEUE_SIZE = 500    # safety cap — prevent runaway queuing


class WriteScheduler:
    """
    Disk-backed queue for product write operations.
    Writes execute during 2–4 AM IST window only.
    """

    def __init__(self):
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_queue_file()

    def _ensure_queue_file(self):
        if not QUEUE_FILE.exists():
            self._save([])

    def _load(self) -> list:
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, queue: list) -> None:
        tmp = QUEUE_FILE.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2, ensure_ascii=False, default=str)
            tmp.replace(QUEUE_FILE)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            print(f"⚠️ [WriteScheduler] Failed to save queue: {e}")

    # ── Queue operations ────────────────────────────────────────────────

    def queue(
        self,
        site_key: str,
        product_id: int,
        data: dict,
        reason: str = "manual",
        priority: int = 5,   # 1=urgent, 10=low
    ) -> dict:
        """
        Add a product write operation to the queue.
        
        Returns {"queued": True, "position": N, "will_run_at": "2:00 AM IST"}
        or {"queued": False, "reason": "..."} on failure.
        """
        queue = self._load()
        
        if len(queue) >= MAX_QUEUE_SIZE:
            return {"queued": False, "reason": f"Queue full ({MAX_QUEUE_SIZE} items)"}

        # Deduplication — if same product already queued, merge data
        for item in queue:
            if (item["site_key"] == site_key
                    and item["product_id"] == product_id
                    and item["status"] == "pending"):
                item["data"].update(data)
                item["updated_at"] = now_ist_str()
                item["reason"] = reason
                self._save(queue)
                return {"queued": True, "merged": True, "position": queue.index(item) + 1}

        entry = {
            "id": f"wq_{int(time.monotonic() * 1000)}",
            "site_key": site_key,
            "product_id": product_id,
            "data": data,
            "reason": reason,
            "priority": priority,
            "status": "pending",    # pending | executing | done | failed | skipped
            "queued_at": now_ist_str(),
            "updated_at": now_ist_str(),
            "result": None,
            "attempts": 0,
        }
        queue.append(entry)
        self._save(queue)
        
        mins = minutes_until_write_window()
        if mins == 0:
            when = "now (in write window)"
        else:
            when = f"~{mins // 60}h {mins % 60}m (at 2:00 AM IST)"

        return {
            "queued": True,
            "position": len(queue),
            "will_run_at": when,
            "entry_id": entry["id"],
        }

    def get_pending(self, site_key: str = None) -> list:
        """Return pending items, optionally filtered by site."""
        queue = self._load()
        pending = [q for q in queue if q["status"] == "pending"]
        if site_key:
            pending = [q for q in pending if q["site_key"] == site_key]
        # Sort by priority then queued_at
        pending.sort(key=lambda x: (x.get("priority", 5), x.get("queued_at", "")))
        return pending

    def get_status(self) -> dict:
        """Summary of queue state — for WhatsApp reports."""
        queue = self._load()
        pending  = [q for q in queue if q["status"] == "pending"]
        done     = [q for q in queue if q["status"] == "done"]
        failed   = [q for q in queue if q["status"] == "failed"]
        in_win   = is_write_window()
        mins     = minutes_until_write_window()
        
        lines = [
            "📝 *WRITE QUEUE STATUS*",
            f"  ⏳ Pending:  {len(pending)}",
            f"  ✅ Done:     {len(done)}",
            f"  ❌ Failed:   {len(failed)}",
            f"  🕐 Window:   {'OPEN (2–4 AM IST)' if in_win else f'Opens in {mins//60}h {mins%60}m'}",
        ]
        if pending:
            sites = {}
            for p in pending:
                sites[p["site_key"]] = sites.get(p["site_key"], 0) + 1
            for sk, cnt in sites.items():
                lines.append(f"    {sk}: {cnt} items")
        
        return {
            "pending": len(pending),
            "done": len(done),
            "failed": len(failed),
            "in_write_window": in_win,
            "summary": "\n".join(lines),
        }

    # ── Execution ───────────────────────────────────────────────────────

    def run_pending(self, woo_connector, site_key: str = None, dry_run: bool = False) -> dict:
        """
        Execute all pending write operations.
        
        Should be called by Director at 2 AM IST via ExtendedSchedule.
        
        Args:
            woo_connector: WooCommerceConnector instance
            site_key: If set, only run for this site
            dry_run: If True, simulate without actual writes
        
        Returns:
            {"success": True, "executed": N, "failed": N, "summary": "..."}
        """
        if not is_write_window() and not dry_run:
            mins = minutes_until_write_window()
            return {
                "success": False,
                "error": f"Not in write window. Opens in {mins//60}h {mins%60}m (2 AM IST)",
                "pending": len(self.get_pending(site_key)),
            }

        pending = self.get_pending(site_key)
        if not pending:
            return {"success": True, "executed": 0, "failed": 0,
                    "summary": "✅ Write queue empty — nothing to do"}

        print(f"🌙 [WriteScheduler] Executing {len(pending)} queued writes "
              f"({'DRY RUN' if dry_run else 'LIVE'})...")

        queue    = self._load()
        executed = 0
        failed   = 0
        errors   = []

        for item in pending:
            # Find item in full queue by id
            queue_item = next((q for q in queue if q["id"] == item["id"]), None)
            if not queue_item:
                continue

            queue_item["status"] = "executing"
            queue_item["updated_at"] = now_ist_str()
            queue_item["attempts"] = queue_item.get("attempts", 0) + 1
            self._save(queue)

            if dry_run:
                queue_item["status"] = "done"
                queue_item["result"] = "DRY RUN — not applied"
                queue_item["updated_at"] = now_ist_str()
                executed += 1
                self._save(queue)
                continue

            try:
                result = woo_connector.update_product(
                    item["product_id"],
                    item["data"],
                    verify=True,
                )
                if result.get("success"):
                    queue_item["status"] = "done"
                    queue_item["result"] = "OK"
                    executed += 1
                    print(f"  ✅ Product {item['product_id']} ({item['site_key']}) updated")
                else:
                    err = result.get("error", "Unknown")
                    queue_item["status"] = "failed"
                    queue_item["result"] = err[:200]
                    failed += 1
                    errors.append(f"Product {item['product_id']}: {err[:60]}")
                    print(f"  ❌ Product {item['product_id']} failed: {err[:60]}")
            except Exception as e:
                queue_item["status"] = "failed"
                queue_item["result"] = str(e)[:200]
                failed += 1
                errors.append(f"Product {item['product_id']}: {str(e)[:60]}")

            queue_item["updated_at"] = now_ist_str()
            self._save(queue)

        summary_lines = [
            "🌙 *NIGHT WRITE QUEUE — COMPLETE*",
            f"  ✅ Applied: {executed}",
            f"  ❌ Failed:  {failed}",
        ]
        if errors:
            summary_lines.append("  Errors:")
            for e in errors[:5]:
                summary_lines.append(f"    • {e}")

        return {
            "success": failed == 0,
            "executed": executed,
            "failed": failed,
            "summary": "\n".join(summary_lines),
            "errors": errors,
        }

    def clear_done(self, keep_days: int = 7) -> int:
        """
        Remove old done/failed items older than keep_days.
        Returns count removed.
        """
        from datetime import timedelta
        cutoff = (now_ist() - timedelta(days=keep_days)).isoformat()
        queue = self._load()
        before = len(queue)
        queue = [
            q for q in queue
            if not (q["status"] in ("done", "failed")
                    and q.get("updated_at", "9999") < cutoff)
        ]
        self._save(queue)
        return before - len(queue)


# Module-level singleton
write_scheduler = WriteScheduler()
