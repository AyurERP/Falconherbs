"""
Falcon Agency — Director Schedule Extensions
Adds new scheduled tasks for content, health scans,
revenue tracking, and store monitoring.

This EXTENDS the Director's existing schedule.
Import in director.py to add new capabilities.
"""

import json
import os
from datetime import datetime, time
from pathlib import Path


class ExtendedSchedule:
    """
    New scheduled tasks for the Director's 60-second loop.
    Each task has a schedule, last_run tracking, and
    safe execution wrapper.
    """
    
    def __init__(self, integration_bridge=None):
        self.bridge = integration_bridge
        self.schedule_file = Path("data/extended_schedule.json")
        self.schedule = self._load_schedule()
    
    def _load_schedule(self):
        """Load schedule state with corruption recovery."""
        if self.schedule_file.exists():
            try:
                with open(self.schedule_file) as f:
                    data = json.load(f)
                # Validate structure
                if isinstance(data, dict) and "tasks" in data:
                    # Gap #11: Ensure sentry_daily_scan auto-starts (migration)
                    tasks = data.get("tasks", {})
                    modified = False
                    if "sentry_daily_scan" not in tasks:
                        tasks["sentry_daily_scan"] = {
                            "time": "11:00", "frequency": "daily",
                            "enabled": True, "last_run": None,
                            "description": "Scan recent FB/IG comments for compliance risks",
                        }
                        modified = True
                    elif not tasks["sentry_daily_scan"].get("enabled", True):
                        tasks["sentry_daily_scan"]["enabled"] = True
                        modified = True
                    if "vps_health_check" not in tasks:
                        tasks["vps_health_check"] = {
                            "time": "00:00", "frequency": "interval",
                            "interval_minutes": 30, "enabled": True,
                            "last_run": None,
                            "description": "VPS CPU/memory/disk monitoring",
                        }
                        modified = True
                    if "content_package_weekly" not in tasks:
                        tasks["content_package_weekly"] = {
                            "time": "06:00", "day": "monday", "frequency": "weekly",
                            "enabled": True, "last_run": None,
                            "description": "Generate weekly content package for HeroPost",
                        }
                        modified = True
                    if modified:
                        self._save_schedule(data)
                    return data
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    "Schedule file corrupted, resetting: %s", e
                )
                # Back up corrupted file
                try:
                    self.schedule_file.rename(
                        self.schedule_file.with_suffix(".json.bak")
                    )
                except Exception:
                    pass
        return self._default_schedule()

    def _default_schedule(self) -> dict:
        """Return the default schedule structure."""
        return self._build_default_tasks()

    def _build_default_tasks(self) -> dict:
        """Build default task schedule (extracted to avoid duplication)."""
        default = {
            "tasks": {
                "morning_report": {
                    "time": "06:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Send morning WhatsApp report"
                },
                "evening_report": {
                    "time": "22:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Send evening WhatsApp report"
                },
                "site_health_check": {
                    "time": "06:30",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Quick site uptime + "
                                   "response check"
                },
                "order_check": {
                    "time": "08:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Check for new orders"
                },
                "content_generation": {
                    "time": "09:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Generate daily content drafts"
                },
                "revenue_update": {
                    "time": "20:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Update revenue tracking"
                },
                "full_store_audit": {
                    "time": "07:00",
                    "day": "monday",
                    "frequency": "weekly",
                    "enabled": True,
                    "last_run": None,
                    "description": "Full WooCommerce store audit"
                },
                "health_claims_scan": {
                    "time": "07:00",
                    "day": "wednesday",
                    "frequency": "weekly",
                    "enabled": True,
                    "last_run": None,
                    "description": "Full health claims re-scan"
                },
                "weekly_content_batch": {
                    "time": "08:00",
                    "day": "monday",
                    "frequency": "weekly",
                    "enabled": True,
                    "last_run": None,
                    "description": "Generate full week's "
                                   "content batch"
                },
                "content_package_weekly": {
                    "time": "06:00",
                    "day": "monday",
                    "frequency": "weekly",
                    "enabled": True,
                    "last_run": None,
                    "description": "Generate weekly content package (images, captions, video, UPLOAD_GUIDE) for HeroPost"
                },
                "customer_analysis": {
                    "time": "09:00",
                    "day": "friday",
                    "frequency": "weekly",
                    "enabled": True,
                    "last_run": None,
                    "description": "Analyze customer data and "
                                   "suggest recovery actions"
                },
                "daily_backup": {
                    "time": "03:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Automatic daily data backup"
                },
                "weekly_seo_digest": {
                    "time": "09:30",
                    "day": "monday",
                    "frequency": "weekly",
                    "enabled": True,
                    "last_run": None,
                    "description": "Weekly SEO + content "
                                   "+ revenue digest"
                },
                "inventory_screening": {
                    "time": "10:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Scan inventory for low stock alerts"
                },
                "sentry_daily_scan": {
                    "time": "11:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Scan recent FB/IG comments for compliance risks"
                },
                "weekly_influencer_scan": {
                    "time": "09:00",
                    "day": "monday",
                    "frequency": "weekly",
                    "enabled": False,
                    "last_run": None,
                    "description": "Weekly YouTube influencer discovery and outreach"
                },
                "monthly_aeo_scan": {
                    "time": "10:00",
                    "day": "monday",
                    "frequency": "monthly",
                    "enabled": True,
                    "last_run": None,
                    "description": "Monthly AEO scan — Falcon Herbs visibility in AI search"
                },
                "weekly_price_scan": {
                    "time": "08:30",
                    "day": "wednesday",
                    "frequency": "weekly",
                    "enabled": True,
                    "last_run": None,
                    "description": "Weekly competitor price scan — Amazon India"
                },
                "daily_digest": {
                    "time": "07:00",
                    "frequency": "daily",
                    "enabled": True,
                    "last_run": None,
                    "description": "Unified daily digest — orders, content, pricing, goals"
                },
                "vps_health_check": {
                    "time": "00:00",
                    "frequency": "interval",
                    "interval_minutes": 30,
                    "enabled": True,
                    "last_run": None,
                    "description": "VPS CPU/memory/disk monitoring"
                },
            },
            "created_at": datetime.now().isoformat()
        }
        
        self._save_schedule(default)
        return default

    def _save_schedule(self, data=None):
        """Save schedule state atomically to prevent corruption."""
        if data is None:
            data = self.schedule
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.schedule_file.with_suffix(".json.tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2, default=str)
            tmp.replace(self.schedule_file)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                "Failed to save schedule: %s", e
            )
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
    
    def should_run_task(self, task_name):
        """
        Check if a task should run right now.
        Called every 60 seconds by Director's main loop.
        """
        task = self.schedule["tasks"].get(task_name)
        if not task or not task.get("enabled"):
            return False
        
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%A").lower()
        today_date = now.strftime("%Y-%m-%d")
        
        task_time = task.get("time", "00:00")
        frequency = task.get("frequency", "daily")
        last_run = task.get("last_run")
        
        # Interval tasks: run every N minutes regardless of day/time slots
        if frequency == "interval":
            interval_min = task.get("interval_minutes", 30)
            if last_run:
                try:
                    from datetime import datetime as _dt
                    last_dt = _dt.fromisoformat(last_run)
                    elapsed_min = (now - last_dt).total_seconds() / 60
                    return elapsed_min >= interval_min
                except Exception:
                    pass
            return True  # Never run before

        # Already ran today?
        if last_run and last_run.startswith(today_date):
            return False
        
        # Check time (within 5-minute window)
        task_hour, task_min = map(int, task_time.split(":"))
        now_minutes = now.hour * 60 + now.minute
        task_minutes = task_hour * 60 + task_min
        
        if abs(now_minutes - task_minutes) > 5:
            return False
        
        # Check day for weekly tasks
        if frequency == "weekly":
            task_day = task.get("day", "monday")
            if current_day != task_day:
                return False

        # Monthly tasks: run on 1st Monday of the month
        if frequency == "monthly":
            task_day = task.get("day", "monday")
            if current_day != task_day:
                return False
            # Only run if we haven't run this calendar month
            if last_run:
                last_month = last_run[:7]   # "YYYY-MM"
                this_month = now.strftime("%Y-%m")
                if last_month == this_month:
                    return False

        return True
    
    def mark_completed(self, task_name):
        """Mark a task as completed"""
        if task_name in self.schedule["tasks"]:
            self.schedule["tasks"][task_name]["last_run"] = \
                datetime.now().isoformat()
            self._save_schedule()
    
    def get_pending_tasks(self):
        """Get all tasks that should run now"""
        pending = []
        for name, task in self.schedule["tasks"].items():
            if self.should_run_task(name):
                pending.append({
                    "name": name,
                    "description": task["description"],
                    "time": task["time"],
                    "frequency": task["frequency"]
                })
        return pending
    
    def execute_task(self, task_name):
        """
        Execute a scheduled task safely.
        Returns result for WhatsApp notification.
        """
        if not self.bridge:
            return {
                "success": False,
                "error": "IntegrationBridge not connected"
            }
        
        handlers = {
            "daily_digest": self._task_daily_digest,
            "morning_report": self._task_morning_report,
            "evening_report": self._task_evening_report,
            "site_health_check": self._task_site_health,
            "order_check": self._task_order_check,
            "content_generation": self._task_daily_content,
            "revenue_update": self._task_revenue_update,
            "full_store_audit": self._task_store_audit,
            "health_claims_scan": self._task_health_scan,
            "weekly_content_batch": self._task_weekly_content,
            "content_package_weekly": self._task_content_package_weekly,
            "customer_analysis": self._task_customer_analysis,
            "daily_backup": self._task_daily_backup,
            "weekly_seo_digest": self._task_weekly_seo_digest,
            "inventory_screening": self._task_inventory_screening,
            "sentry_daily_scan": self._task_sentry_scan,
            "weekly_influencer_scan": self._task_influencer_scan,
            "monthly_aeo_scan":   self._task_aeo_scan,
            "weekly_price_scan":  self._task_price_scan,
            "vps_health_check":    self._task_vps_health_check,
        }
        
        handler = handlers.get(task_name)
        if not handler:
            return {
                "success": False,
                "error": f"No handler for task: {task_name}"
            }
        
        import time as _time
        start = _time.time()
        try:
            result = handler()
            elapsed = int((_time.time() - start) * 1000)
            success = result.get("success", True)
            self._record_task_result(
                task_name, success, elapsed
            )
            self.mark_completed(task_name)
            return result
        except Exception as e:
            elapsed = int((_time.time() - start) * 1000)
            self._record_task_result(
                task_name, False, elapsed
            )
            return {
                "success": False,
                "error": f"Task {task_name} failed: {e}",
                "task": task_name
            }
    
    # ========= TASK HANDLERS =========
    
    def _task_daily_digest(self):
        """Unified daily digest at 07:00 — replaces separate
        morning/evening reports with one richer message."""
        try:
            digest = self.bridge.generate_daily_digest()
            return {
                "success": True,
                "send_whatsapp": True,
                "message": digest,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _task_morning_report(self):
        """Generate and return morning report"""
        report = self.bridge.generate_morning_report()
        return {
            "success": True,
            "send_whatsapp": True,
            "message": report
        }
    
    def _task_daily_backup(self) -> dict:
        """Execute daily backup and verify it actually succeeded."""
        try:
            result = self.bridge.run_backup()
            if not result.get("success"):
                return {
                    "success": False,
                    "send_whatsapp": True,
                    "message": (
                        "❌ *BACKUP FAILED*\n"
                        "Error: {}\n"
                        "Check backup tool!".format(
                            result.get("error", "unknown")
                        )
                    )
                }

            # Verify backup file exists and has content
            from pathlib import Path
            import time as _btime
            backup_dir = Path("data/backups")
            if backup_dir.exists():
                now_ts = _btime.time()
                recent = [
                    f for f in backup_dir.glob("**/*")
                    if f.is_file() and (now_ts - f.stat().st_mtime) < 600
                ]
                if not recent:
                    return {
                        "success": False,
                        "send_whatsapp": True,
                        "message": (
                            "❌ *BACKUP WARNING*\n"
                            "Backup ran but no recent files found. "
                            "Verify manually!"
                        )
                    }
                largest = max(
                    recent, key=lambda f: f.stat().st_size, default=None
                )
                if largest and largest.stat().st_size < 100:
                    return {
                        "success": False,
                        "send_whatsapp": True,
                        "message": (
                            "❌ *BACKUP WARNING*\n"
                            "Backup file suspiciously small ({} bytes). "
                            "Verify!".format(largest.stat().st_size)
                        )
                    }

            return {
                "success": True,
                "send_whatsapp": False,
                "message": result.get("message", "Backup completed")
            }
        except Exception as e:
            return {
                "success": False,
                "send_whatsapp": True,
                "message": "❌ *BACKUP EXCEPTION*\n{}".format(str(e)[:100])
            }
    
    def _task_evening_report(self):
        """Generate and return evening report"""
        report = self.bridge.generate_evening_report()
        return {
            "success": True,
            "send_whatsapp": True,
            "message": report
        }
    
    def _task_site_health(self):
        """Quick site health check"""
        import requests
        try:
            import os
            site_url = os.getenv(
                "WOO_SITE_URL", "https://falconherbs.com"
            )
            r = requests.get(site_url, timeout=15)
            
            response_time = round(
                r.elapsed.total_seconds() * 1000
            )
            
            if r.status_code == 200 and response_time < 5000:
                return {
                    "success": True,
                    "send_whatsapp": False,
                    "message": f"Site OK: {response_time}ms"
                }
            else:
                return {
                    "success": True,
                    "send_whatsapp": True,
                    "message": (
                        f"⚠️ *SITE ALERT*\n"
                        f"Status: {r.status_code}\n"
                        f"Response: {response_time}ms\n"
                        f"{'🐌 SLOW!' if response_time > 5000 else ''}"
                    )
                }
        except Exception as e:
            return {
                "success": True,
                "send_whatsapp": True,
                "message": (
                    f"🚨 *SITE DOWN!*\n"
                    f"Error: {str(e)[:100]}\n"
                    f"Check immediately!"
                )
            }
    
    def _task_order_check(self):
        """Check for new orders"""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False, 
                       "error": "WooCommerce not loaded"}
            
            result = woo.get_orders(days_back=1)
            if result["success"]:
                total = result["data"]["total_orders"]
                revenue = result["data"]["revenue"]["total"]

                if total > 0 and revenue > 0:
                    return {
                        "success": True,
                        "send_whatsapp": True,
                        "message": (
                            f"🎉 *NEW ORDERS!*\n"
                            f"📦 Orders today: {total}\n"
                            f"💰 Revenue: ₹{revenue:,.0f}\n"
                            f"Check WooCommerce for details!"
                        )
                    }
                else:
                    return {
                        "success": True,
                        "send_whatsapp": False,
                        "message": "No new orders today"
                    }
            
            return {"success": False, 
                   "error": result.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _task_daily_content(self):
        """Generate daily content via ContentWorkflow.
        Picks next topic, generates AI content, queues
        for approval."""
        try:
            from core.content_workflow import ContentWorkflow
            workflow = self.bridge.tools.get("workflow")
            if not workflow:
                workflow = ContentWorkflow(self.bridge)

            # Pick next unused topic
            topic, keyword, product = workflow.pick_next_topic()

            # Generate and queue via full pipeline
            result = workflow.generate_and_queue(
                topic=topic,
                keyword=keyword,
                product=product
            )

            if result.get("success"):
                return {
                    "success": True,
                    "send_whatsapp": True,
                    "message": result.get("message",
                        "Content generated: {}".format(topic))
                }
            else:
                return {
                    "success": True,
                    "send_whatsapp": False,
                    "message": "Content generation skipped: "
                               "{}".format(
                                   result.get("error", "unknown")
                               )
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _task_revenue_update(self):
        """Update revenue from LIVE WooCommerce + auto-sync
        daily progress"""
        try:
            woo = self.bridge.tools.get("woocommerce")
            tracker = self.bridge.tools.get("revenue")

            # Sync live orders into revenue tracker
            imported = 0
            if woo and tracker:
                orders = woo.get_orders(days_back=7, save=False)
                if orders.get("success"):
                    sync = tracker.sync_from_woocommerce(orders)
                    imported = sync.get("imported", 0)

            # Auto-sync daily progress from real data
            try:
                from core.goal_tracker import goal_tracker
                goal_tracker.auto_sync_progress()
            except Exception:
                pass

            return {
                "success": True,
                "send_whatsapp": imported > 0,
                "message": (
                    "\U0001F4B0 Revenue synced: "
                    "{} new entries".format(imported)
                    if imported > 0
                    else "Revenue up to date"
                )
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _task_store_audit(self):
        """Weekly full store audit"""
        result = self.bridge.run_store_audit()
        return {
            "success": result.get("success", False),
            "send_whatsapp": True,
            "message": result.get("summary", 
                "Store audit complete. Check report.")
        }
    
    def _task_health_scan(self):
        """Weekly health claims scan"""
        result = self.bridge.run_health_scan(max_pages=100)
        
        if result.get("success"):
            return {
                "success": True,
                "send_whatsapp": True,
                "message": result.get("summary",
                    "Health scan complete.")
            }
        return {
            "success": False,
            "send_whatsapp": True,
            "message": f"❌ Health scan failed: "
                      f"{result.get('error')}"
        }
    
    def _task_weekly_content(self):
        """Weekly content batch generation"""
        result = self.bridge.generate_weekly_content()

        if result.get("success"):
            return {
                "success": True,
                "send_whatsapp": True,
                "message": (
                    "📝 *WEEKLY CONTENT GENERATED*\n"
                    "Check data/content/drafts/ for:\n"
                    "• Blog drafts\n"
                    "• Social media batch\n"
                    "• Email sequences\n\n"
                    "Review → Approve → Publish"
                )
            }
        return {"success": False,
               "error": result.get("error")}

    def _task_content_package_weekly(self):
        """Generate weekly content package (images, captions, video, UPLOAD_GUIDE) for HeroPost."""
        result = self.bridge.generate_weekly_content_package()
        if result.get("success"):
            return {
                "success": True,
                "send_whatsapp": True,
                "message": result.get("summary", "Content package ready."),
            }
        return {
            "success": False,
            "send_whatsapp": True,
            "message": f"❌ Content package failed: {result.get('error', 'unknown')}",
        }
    
    def _task_customer_analysis(self):
        """Weekly customer analysis — uses Win-Back module
        to find inactive customers and notify owner.
        NEVER sends emails automatically."""
        try:
            lines = ["\U0001F465 *WEEKLY CUSTOMER ANALYSIS*"]

            # 1. WooCommerce overview
            woo = self.bridge.tools.get("woocommerce")
            if woo:
                customers = woo.get_customers(save=False)
                if customers.get("success"):
                    total = customers["data"].get(
                        "total_customers", 0
                    )
                    countries = customers["data"].get(
                        "country_breakdown", {}
                    )
                    lines.append(
                        "\U0001F4CA Total Customers: {}".format(
                            total
                        )
                    )
                    lines.append(
                        "\U0001F30D Countries: {}".format(
                            len(countries)
                        )
                    )
                    top = sorted(
                        countries.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5]
                    if top:
                        lines.append("\nTop Markets:")
                        for country, count in top:
                            lines.append(
                                "  {}: {}".format(
                                    country, count
                                )
                            )

            # 2. Win-back scan — finds inactive customers
            wb = self.bridge.tools.get("winback")
            if wb:
                wb_result = wb.find_inactive_customers(days=90)
                if wb_result.get("success"):
                    inactive = wb_result.get("inactive", 0)
                    lines.append(
                        "\n\U0001F6AB Inactive (90+ days): "
                        "{}".format(inactive)
                    )
                    if inactive > 0:
                        lines.append(
                            "\U0001F4E7 Say "
                            "*'generate winback emails'* "
                            "to create reactivation drafts."
                        )

            lines.append(
                "\n\U0001F4C2 data/customer_winback/"
            )

            return {
                "success": True,
                "send_whatsapp": True,
                "message": "\n".join(lines),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _task_vps_health_check(self) -> dict:
        """Check VPS CPU, memory, disk. Alert if any threshold exceeded."""
        try:
            import shutil
            import os
            alerts = []
            stats = {}

            # Prefer psutil when available (cross-platform, cleaner)
            try:
                import psutil
                disk_pct = psutil.disk_usage("/").percent
                stats["disk_percent"] = round(disk_pct, 1)
                stats["disk_free_gb"] = round(
                    psutil.disk_usage("/").free / (1024 ** 3), 1
                )
                if disk_pct > 85:
                    alerts.append(
                        "⚠️ Disk {}% full ({}GB free)".format(
                            stats["disk_percent"], stats["disk_free_gb"]
                        )
                    )
                vm = psutil.virtual_memory()
                mem_pct = vm.percent
                stats["memory_percent"] = round(mem_pct, 1)
                stats["memory_free_mb"] = round(vm.available / (1024 ** 2), 0)
                if mem_pct > 85:
                    alerts.append(
                        "⚠️ Memory {}% used ({}MB free)".format(
                            mem_pct, stats["memory_free_mb"]
                        )
                    )
                try:
                    load1 = psutil.getloadavg()[0]
                except (AttributeError, OSError):
                    load1 = 0.0
                stats["cpu_load_1m"] = load1
                cpu_count = psutil.cpu_count() or 1
                if load1 > cpu_count * 1.5:
                    alerts.append(
                        "⚠️ CPU load {} (cores: {})".format(load1, cpu_count)
                    )
            except ImportError:
                # Fallback: /proc and shutil (Linux VPS)
                usage = shutil.disk_usage("/")
                disk_pct = round(usage.used / usage.total * 100, 1)
                stats["disk_percent"] = disk_pct
                stats["disk_free_gb"] = round(usage.free / (1024 ** 3), 1)
                if disk_pct > 85:
                    alerts.append(
                        "⚠️ Disk {}% full ({}GB free)".format(
                            disk_pct, stats["disk_free_gb"]
                        )
                    )
                try:
                    mem = {}
                    with open("/proc/meminfo") as _mf:
                        for line in _mf:
                            parts = line.split()
                            if len(parts) >= 2:
                                mem[parts[0].rstrip(":")] = int(parts[1])
                    total_kb = mem.get("MemTotal", 1)
                    avail_kb = mem.get("MemAvailable", total_kb)
                    mem_pct = round((1 - avail_kb / total_kb) * 100, 1)
                    stats["memory_percent"] = mem_pct
                    stats["memory_free_mb"] = round(avail_kb / 1024, 0)
                    if mem_pct > 85:
                        alerts.append(
                            "⚠️ Memory {}% used ({}MB free)".format(
                                mem_pct, stats["memory_free_mb"]
                            )
                        )
                except Exception:
                    pass
                try:
                    with open("/proc/loadavg") as _lf:
                        load1 = float(_lf.read().split()[0])
                    stats["cpu_load_1m"] = load1
                    cpu_count = os.cpu_count() or 1
                    if load1 > cpu_count * 1.5:
                        alerts.append(
                            "⚠️ CPU load {} (cores: {})".format(
                                load1, cpu_count
                            )
                        )
                except Exception:
                    pass

            if alerts:
                msg = "🖥️ *VPS ALERT*\n" + "\n".join(alerts)
                return {
                    "success": True,
                    "send_whatsapp": True,
                    "message": msg,
                    "stats": stats
                }

            return {
                "success": True,
                "send_whatsapp": False,
                "message": "VPS healthy",
                "stats": stats
            }
        except Exception as e:
            return {"success": False, "error": str(e)[:100]}

    # ========= DIRECTOR LOOP INTEGRATION =========
    
    def check_and_execute(self, whatsapp_sender=None):
        """
        Call this method from Director's 60-second loop.
        
        Args:
            whatsapp_sender: Function to send WhatsApp messages
                           e.g., commander.send_message(text)
        
        Returns:
            List of executed task results
        """
        pending = self.get_pending_tasks()
        results = []
        
        for task in pending:
            print(f"⏰ Running scheduled task: "
                  f"{task['name']} — {task['description']}")
            
            result = self.execute_task(task["name"])
            results.append({
                "task": task["name"],
                "result": result
            })
            
            # Send WhatsApp if task requested it
            if (result.get("send_whatsapp") and
                    whatsapp_sender and
                    result.get("message")):
                try:
                    whatsapp_sender(result["message"])
                    print(f"  📱 WhatsApp sent for: "
                          f"{task['name']}")
                except Exception as e:
                    print(f"  ❌ WhatsApp failed: {e}")

            # Critical tasks: always alert on failure regardless of send_whatsapp flag
            _CRITICAL_TASKS = {"daily_backup", "site_health_check", "order_check", "vps_health_check"}
            if (result.get("success") is False and
                    task["name"] in _CRITICAL_TASKS and
                    not result.get("send_whatsapp") and
                    whatsapp_sender):
                _err_msg = result.get("message") or result.get("error", "unknown error")
                _alert = "⚠️ *TASK FAILURE: {}*\n{}".format(
                    task["name"].upper().replace("_", " "),
                    str(_err_msg)[:200]
                )
                try:
                    whatsapp_sender(_alert)
                    print(f"  🚨 Critical failure alert sent for: {task['name']}")
                except Exception as e:
                    print(f"  ❌ Critical alert WhatsApp failed: {e}")
        
        return results
    
    def get_schedule_summary(self):
        """WhatsApp-friendly schedule summary"""
        lines = [
            "📅 *SCHEDULED TASKS*",
            "─────────────",
        ]
        
        for name, task in self.schedule["tasks"].items():
            enabled = "✅" if task["enabled"] else "❌"
            freq = task["frequency"]
            time_str = task["time"]
            day = task.get("day", "")
            last = task.get("last_run", "Never")
            
            if last and last != "Never":
                last = last[:16]  # Trim to date+time
            
            lines.append(
                f"{enabled} *{name}*"
            )
            lines.append(
                f"   ⏰ {time_str} "
                f"{'(' + day + ') ' if day else ''}"
                f"[{freq}]"
            )
            lines.append(f"   🕐 Last: {last}")
        
        lines.extend([
            "",
            "─────────────",
            "🤖 _Falcon Agency Scheduler_"
        ])
        
        return "\n".join(lines)
    
    # ========= SMART SCHEDULING (Phase 4) =========
    
    def _record_task_result(
        self, task_name, success, duration_ms=0
    ):
        """Record task execution stats to
        data/task_stats.json for analytics."""
        try:
            stats_file = Path("data/task_stats.json")
            stats_file.parent.mkdir(
                parents=True, exist_ok=True
            )

            if stats_file.exists():
                with open(stats_file,
                          encoding="utf-8") as f:
                    stats = json.load(f)
            else:
                stats = {}

            if task_name not in stats:
                stats[task_name] = {
                    "total_runs": 0,
                    "successes": 0,
                    "failures": 0,
                    "avg_duration_ms": 0,
                    "last_run": None,
                    "last_status": None,
                }

            entry = stats[task_name]
            entry["total_runs"] += 1
            if success:
                entry["successes"] += 1
            else:
                entry["failures"] += 1

            # Rolling average duration
            prev_avg = entry["avg_duration_ms"]
            prev_runs = entry["total_runs"] - 1
            if prev_runs > 0:
                entry["avg_duration_ms"] = round(
                    (prev_avg * prev_runs + duration_ms)
                    / entry["total_runs"]
                )
            else:
                entry["avg_duration_ms"] = duration_ms

            entry["last_run"] = (
                datetime.now().isoformat()
            )
            entry["last_status"] = (
                "success" if success else "failed"
            )

            # Compute success_rate
            entry["success_rate"] = round(
                entry["successes"]
                / max(entry["total_runs"], 1) * 100
            )

            with open(stats_file, "w",
                      encoding="utf-8") as f:
                json.dump(stats, f, indent=2)
        except Exception:
            pass
    
    def _task_weekly_seo_digest(self):
        """Weekly SEO + content + revenue digest.
        Only runs on Mondays."""
        try:
            # Only on Monday
            if datetime.now().weekday() != 0:
                return {
                    "success": True,
                    "send_whatsapp": False,
                    "message": "SEO digest: not Monday",
                }

            lines = [
                "\U0001F4CA *WEEKLY SEO DIGEST*",
                "\U0001F4C5 {}".format(
                    datetime.now().strftime(
                        '%d %b %Y'
                    )
                ),
                "\u2500" * 25,
            ]

            # 1. Content stats
            try:
                drafts_dir = Path(
                    "data/content/drafts"
                )
                if drafts_dir.exists():
                    all_drafts = [
                        f for f in
                        drafts_dir.glob("*.json")
                        if f.name != "__init__.py"
                    ]
                    status_counts = {}
                    for d in all_drafts:
                        try:
                            data = json.loads(
                                d.read_text(
                                    encoding="utf-8"
                                )
                            )
                            s = data.get(
                                "status", "unknown"
                            )
                            status_counts[s] = (
                                status_counts.get(s, 0)
                                + 1
                            )
                        except Exception:
                            continue
                    lines.append(
                        "\n\U0001F4DD *CONTENT:*"
                    )
                    for s, c in sorted(
                        status_counts.items()
                    ):
                        lines.append(
                            "   {} : {}".format(s, c)
                        )
            except Exception:
                pass

            # 2. Product health
            try:
                scan_file = Path(
                    "data/content/product_rewrites/"
                    "last_scan.json"
                )
                if scan_file.exists():
                    data = json.loads(
                        scan_file.read_text(
                            encoding="utf-8"
                        )
                    )
                    lines.append(
                        "\n\U0001F6E1\uFE0F *PRODUCT "
                        "HEALTH:*"
                    )
                    lines.append(
                        "   Scanned: {}".format(
                            data.get("total", 0)
                        )
                    )
                    lines.append(
                        "   Flagged: {}".format(
                            data.get("flagged", 0)
                        )
                    )
            except Exception:
                pass

            # 3. Goal progress
            try:
                from core.goal_tracker import (
                    goal_tracker
                )
                progress = (
                    goal_tracker.get_progress_summary()
                )
                rev_pct = progress[
                    "revenue"
                ]["percentage"]
                lines.append(
                    "\n\U0001F3AF *GOALS:* {}%"
                    " revenue target".format(rev_pct)
                )
            except Exception:
                pass

            # 4. Revenue this week
            try:
                rev = self.bridge.tools.get("revenue")
                if rev:
                    summary = (
                        rev.get_monthly_summary()
                    )
                    lines.append(
                        "\n\U0001F4B0 *REVENUE:* "
                        "\u20B9{:,.0f} this month".format(
                            summary.get("revenue", 0)
                        )
                    )
            except Exception:
                pass

            lines.extend([
                "",
                "\u2500" * 25,
                "\U0001F916 _Falcon Agency "
                "\u2014 Weekly Digest_",
            ])

            return {
                "success": True,
                "send_whatsapp": True,
                "message": "\n".join(lines),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _task_inventory_screening(self):
        """Daily inventory health check"""
        try:
            result = self.bridge.get_burn_rate_report()
            if not result.get("success"):
                return result

            risky = result["data"].get("risky", [])
            
            # Only send WhatsApp if there are alerts
            if risky:
                return {
                    "success": True,
                    "send_whatsapp": True,
                    "message": result.get("summary")
                }
            else:
                return {
                    "success": True,
                    "send_whatsapp": False,
                    "message": "Inventory OK. No low stock alerts."
                }
        except Exception as e:
            return {"success": False, "error": str(e)}


    
    def _task_sentry_scan(self):
        """
        Routine social media compliance scan.
        Requires Meta Graph API (META_ACCESS_TOKEN) for comments.
        When not configured: logs and returns honest status.
        """
        try:
            token = os.environ.get("META_ACCESS_TOKEN") or os.environ.get("WHATSAPP_ACCESS_TOKEN")
            if not token:
                return {
                    "success": True,
                    "send_whatsapp": True,
                    "message": (
                        "🔒 *Social Sentry* — Skipped (no API)\n"
                        "Add META_ACCESS_TOKEN to .env for Facebook/IG comment monitoring."
                    ),
                }
            # TODO: Meta Graph API — fetch comments, run SocialSentry.analyze
            return {
                "success": True,
                "send_whatsapp": False,
                "message": "Social Sentry: API ready. Comment fetch not yet implemented.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _task_aeo_scan(self):
        """
        Monthly AEO brand visibility scan.
        Checks if Falcon Herbs appears in Perplexity/OpenAI answers
        for 25 Ayurveda queries. Saves content gaps automatically.
        Only runs once per calendar month (1st Monday).
        """
        try:
            import os
            has_key = bool(
                os.getenv("PERPLEXITY_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("NVIDIA_API_KEY")
            )

            if not has_key:
                return {
                    "success": True,
                    "send_whatsapp": True,
                    "message": (
                        "\U0001F916 *AEO SCAN SKIPPED*\n"
                        "No API key found.\n"
                        "Add PERPLEXITY_API_KEY to .env\n"
                        "to enable AI visibility monitoring."
                    ),
                }

            result = self.bridge.run_aeo_scan()

            if result.get("success"):
                return {
                    "success": True,
                    "send_whatsapp": True,
                    "message": result.get(
                        "summary",
                        "\u2705 AEO scan complete."
                    ),
                }

            return {
                "success": False,
                "send_whatsapp": False,
                "message": "AEO scan failed: {}".format(
                    result.get("error", "unknown")
                ),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _task_price_scan(self):
        """
        Weekly competitor price scan — every Wednesday 08:30.
        Scrapes Amazon India, computes undercut recommendations,
        alerts if action needed.
        """
        try:
            result = self.bridge.run_price_scan()
            if result.get("success"):
                alerts = result.get("alerts", 0)
                return {
                    "success":      True,
                    "send_whatsapp": alerts > 0,
                    "message":      result.get(
                        "summary",
                        "\u2705 Price scan complete. "
                        "No action needed."
                    ),
                }
            return {
                "success":      False,
                "send_whatsapp": False,
                "message":      "Price scan failed: {}".format(
                    result.get("error", "unknown")
                ),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _task_influencer_scan(self):
        """
        Weekly scan for new influencers to connect with.
        Topic rotates each week across Ayurvedic categories
        so we never repeat the same search twice in a row.
        """
        from agents.pr_outreach import PROutreach
        from core.ai_client import call_ai

        # ── Topic selection ────────────────────────────
        # 1. Try ContentWorkflow's smart picker first
        target_topic = None
        workflow = self.bridge.tools.get("workflow") if self.bridge else None
        if workflow and hasattr(workflow, "pick_next_topic"):
            try:
                topic, _, _ = workflow.pick_next_topic()
                target_topic = topic
            except Exception:
                pass

        # 2. Fall back to week-based rotation from curated list
        if not target_topic:
            _INFLUENCER_TOPICS = [
                "immunity booster ayurveda",
                "ashwagandha stress relief",
                "ayurvedic skincare",
                "natural hair care herbs",
                "triphala gut health",
                "turmeric benefits",
                "moringa superfood",
                "ayurvedic weight loss",
                "shilajit energy",
                "herbal sleep remedy",
                "chyawanprash winter health",
                "neem detox",
                "brahmi memory",
                "shatavari womens health",
                "ayurvedic diabetes management",
                "joint pain herbal remedy",
            ]
            week_num = datetime.now().isocalendar()[1]
            target_topic = _INFLUENCER_TOPICS[
                week_num % len(_INFLUENCER_TOPICS)
            ]
        # ── End topic selection ────────────────────────

        outreach = PROutreach(llm_caller=call_ai)
        results = outreach.find_influencers(
            target_topic, max_results=3
        )

        if isinstance(results, list) and results:
            message = outreach.format_whatsapp_result(results)
            return {
                "success": True,
                "send_whatsapp": True,
                "message": (
                    "\U0001F4C5 *WEEKLY INFLUENCER DISCOVERY*\n"
                    "Topic: {}\n\n{}".format(
                        target_topic, message
                    )
                ),
            }

        return {
            "success": True,
            "send_whatsapp": False,
            "message": "No new influencers found this week "
                       "for topic: {}".format(target_topic),
        }

# ==================== TEST ====================

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    print("⏰ Testing Extended Schedule")
    print("=" * 50)
    
    # Test without bridge
    schedule = ExtendedSchedule()
    
    # Show all tasks
    print("\n📋 Configured Tasks:")
    for name, task in schedule.schedule["tasks"].items():
        print(f"  {'✅' if task['enabled'] else '❌'} "
              f"{name}: {task['time']} ({task['frequency']})")
    
    # Check pending
    pending = schedule.get_pending_tasks()
    print(f"\n⏳ Pending tasks right now: {len(pending)}")
    for task in pending:
        print(f"  → {task['name']}: {task['description']}")
    
    # Show summary
    print("\n" + schedule.get_schedule_summary())
    
    # Test with bridge
    try:
        from core.integration_bridge import IntegrationBridge
        bridge = IntegrationBridge()
        schedule_with_bridge = ExtendedSchedule(
            integration_bridge=bridge
        )
        print("\n✅ Schedule + Bridge connected successfully!")
    except Exception as e:
        print(f"\n⚠️ Bridge connection: {e}")
    
    print("\n✅ Schedule test complete!")
