"""
Falcon Agency — Director Schedule Extensions
Adds new scheduled tasks for content, health scans,
revenue tracking, and store monitoring.

This EXTENDS the Director's existing schedule.
Import in director.py to add new capabilities.
"""

import json
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
        """Load or create schedule state"""
        if self.schedule_file.exists():
            with open(self.schedule_file) as f:
                return json.load(f)
        
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
            },
            "created_at": datetime.now().isoformat()
        }
        
        self._save_schedule(default)
        return default
    
    def _save_schedule(self, data=None):
        """Save schedule state"""
        if data is None:
            data = self.schedule
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.schedule_file, "w") as f:
            json.dump(data, f, indent=2)
    
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
            "morning_report": self._task_morning_report,
            "evening_report": self._task_evening_report,
            "site_health_check": self._task_site_health,
            "order_check": self._task_order_check,
            "content_generation": self._task_daily_content,
            "revenue_update": self._task_revenue_update,
            "full_store_audit": self._task_store_audit,
            "health_claims_scan": self._task_health_scan,
            "weekly_content_batch": self._task_weekly_content,
            "customer_analysis": self._task_customer_analysis,
            "daily_backup": self._task_daily_backup,
            "weekly_seo_digest": self._task_weekly_seo_digest,
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
    
    def _task_morning_report(self):
        """Generate and return morning report"""
        report = self.bridge.generate_morning_report()
        return {
            "success": True,
            "send_whatsapp": True,
            "message": report
        }
    
    def _task_daily_backup(self):
        """Execute and return daily backup result"""
        return self.bridge.run_backup()
    
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
                
                if total > 0:
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
    
    def _task_customer_analysis(self):
        """Weekly customer analysis"""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"success": False,
                       "error": "WooCommerce not loaded"}
            
            customers = woo.get_customers()
            if customers["success"]:
                total = customers["data"]["total_customers"]
                countries = customers["data"].get(
                    "country_breakdown", {}
                )
                
                message = (
                    f"👥 *WEEKLY CUSTOMER ANALYSIS*\n"
                    f"Total Customers: {total}\n"
                    f"Countries: {len(countries)}\n\n"
                    f"Top Markets:\n"
                )
                for country, count in sorted(
                    countries.items(),
                    key=lambda x: x[1], reverse=True
                )[:5]:
                    message += f"  {country}: {count}\n"
                
                return {
                    "success": True,
                    "send_whatsapp": True,
                    "message": message
                }
            
            return {"success": False,
                   "error": customers.get("error")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
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
            
            # Send WhatsApp if needed
            if (result.get("send_whatsapp") and 
                    whatsapp_sender and 
                    result.get("message")):
                try:
                    whatsapp_sender(result["message"])
                    print(f"  📱 WhatsApp sent for: "
                          f"{task['name']}")
                except Exception as e:
                    print(f"  ❌ WhatsApp failed: {e}")
        
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
