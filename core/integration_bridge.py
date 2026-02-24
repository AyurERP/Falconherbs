"""
Falcon Agency — Integration Bridge
Connects new tools (WooCommerce, Health Scanner, 
Content Pipeline, Revenue Tracker) to existing 
Director/Commander/Agents system.

This is the SAFE bridge — if new tools fail,
old system keeps working.
"""

import sys
import os
import json
import traceback
from datetime import datetime
from pathlib import Path

# Add project root to python path for standalone execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class IntegrationBridge:
    """
    Safe connector between new and existing systems.
    Every call is wrapped in try/except.
    Old system NEVER breaks because of new tools.
    """
    
    def __init__(self):
        self.tools = {}
        self.status = {}
        self._load_tools()
    
    def _load_tools(self):
        """Load new tools safely"""
        
        # WooCommerce
        try:
            from core.woocommerce_connector import (
                WooCommerceConnector
            )
            self.tools["woocommerce"] = WooCommerceConnector()
            self.status["woocommerce"] = "loaded"
        except Exception as e:
            self.status["woocommerce"] = f"failed: {e}"
        
        # Health Scanner
        try:
            from core.health_scanner import HealthClaimsScanner
            self.tools["health_scanner"] = HealthClaimsScanner()
            self.status["health_scanner"] = "loaded"
        except Exception as e:
            self.status["health_scanner"] = f"failed: {e}"
        
        # Revenue Tracker
        try:
            from core.revenue_tracker import RevenueTracker
            self.tools["revenue"] = RevenueTracker()
            self.status["revenue"] = "loaded"
        except Exception as e:
            self.status["revenue"] = f"failed: {e}"
        
        # Content AI Client (load before pipeline)
        try:
            from core.content_ai_client import ContentAIClient
            self.tools["ai_client"] = ContentAIClient()
            self.status["ai_client"] = "loaded"
        except Exception as e:
            self.tools["ai_client"] = None
            self.status["ai_client"] = f"failed: {e}"
        
        # Content Pipeline (with AI client if available)
        try:
            from core.content_pipeline import ContentPipeline
            ai = self.tools.get("ai_client")
            self.tools["content"] = ContentPipeline(ai_client=ai)
            self.status["content"] = (
                "loaded+ai" if ai else "loaded (no AI)"
            )
        except Exception as e:
            self.status["content"] = f"failed: {e}"
        
        # ── Tier 2 Modules ──
        
        # WordPress Publisher
        try:
            from core.wordpress_publisher import WordPressPublisher
            self.tools["wp"] = WordPressPublisher()
            self.status["wp"] = "loaded"
        except Exception as e:
            self.status["wp"] = f"failed: {e}"
            
        # Image Generator
        try:
            from core.image_generator import ImageGenerator
            self.tools["image"] = ImageGenerator()
            self.status["image"] = "loaded"
        except Exception as e:
            self.status["image"] = f"failed: {e}"
            
        # Email System
        try:
            from core.email_system import EmailSystem
            self.tools["email"] = EmailSystem()
            self.status["email"] = "loaded"
        except Exception as e:
            self.status["email"] = f"failed: {e}"
            
        # Auto Backup
        try:
            from core.auto_backup import AutoBackup
            self.tools["backup"] = AutoBackup()
            self.status["backup"] = "loaded"
        except Exception as e:
            self.status["backup"] = f"failed: {e}"
            
        # GSC Connector (B4)
        try:
            from core.gsc_connector import gsc_connector
            self.tools["gsc"] = gsc_connector
            self.status["gsc"] = "loaded"
        except Exception as e:
            self.status["gsc"] = f"failed: {e}"
        
        # Content Workflow (Phase 2)
        try:
            from core.content_workflow import ContentWorkflow
            self.workflow = ContentWorkflow(self)
            self.tools["workflow"] = self.workflow
            self.status["workflow"] = "loaded"
        except Exception as e:
            self.workflow = None
            self.status["workflow"] = f"failed: {e}"
            
        # Health Rewriter (Phase 5)
        try:
            from core.health_rewriter import HealthClaimsRewriter
            self.tools["rewriter"] = HealthClaimsRewriter(bridge=self)
            self.status["rewriter"] = "loaded"
        except Exception as e:
            self.status["rewriter"] = f"failed: {e}"
            
        # Lead Predictor (Pillar 1)
        try:
            from core.lead_predictor import LeadPredictor
            self.tools["predictor"] = LeadPredictor(bridge=self)
            self.status["predictor"] = "loaded"
        except Exception as e:
            self.status["predictor"] = f"failed: {e}"

        # Customer Win-Back
        try:
            from core.customer_winback import CustomerWinback
            self.tools["winback"] = CustomerWinback(bridge=self)
            self.status["winback"] = "loaded"
        except Exception as e:
            self.status["winback"] = f"failed: {e}"

        # AEO Agent (brand monitoring in AI answers)
        try:
            from agents.aeo_agent import AEOAgent
            self.tools["aeo"] = AEOAgent(bridge=self)
            self.status["aeo"] = "loaded"
        except Exception as e:
            self.status["aeo"] = f"failed: {e}"

        # Competitor Price Tracker
        try:
            from agents.price_tracker import PriceTrackerAgent
            self.tools["pricing"] = PriceTrackerAgent(bridge=self)
            self.status["pricing"] = "loaded"
        except Exception as e:
            self.status["pricing"] = f"failed: {e}"

    def get_status(self):
        """Check which tools are available"""
        return {
            "timestamp": datetime.now().isoformat(),
            "tools": self.status,
            "all_loaded": all(
                "loaded" in str(v) for v in self.status.values()
            )
        }
    
    # ========= SAFE WRAPPERS =========
    
    def run_store_audit(self):
        """Safe wrapper for WooCommerce audit"""
        try:
            woo = self.tools.get("woocommerce")
            if not woo:
                return {
                    "success": False,
                    "error": "WooCommerce not loaded"
                }
            return woo.full_store_audit()
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def run_health_scan(self, max_pages=100):
        """Safe wrapper for health claims scan"""
        try:
            scanner = self.tools.get("health_scanner")
            if not scanner:
                return {
                    "success": False,
                    "error": "Health Scanner not loaded"
                }
            return scanner.full_scan(max_pages=max_pages)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def get_revenue_report(self):
        """Safe wrapper for revenue report"""
        try:
            tracker = self.tools.get("revenue")
            if not tracker:
                return {
                    "success": False,
                    "error": "Revenue Tracker not loaded"
                }
            return {
                "success": True,
                "report": tracker.generate_whatsapp_report(),
                "data": tracker.get_monthly_summary()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_weekly_content(self, products=None):
        """Safe wrapper for content generation"""
        try:
            pipeline = self.tools.get("content")
            if not pipeline:
                return {
                    "success": False,
                    "error": "Content Pipeline not loaded"
                }
            return {
                "success": True,
                "results": pipeline.generate_this_weeks_content(
                    products
                )
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_content_status(self):
        """Safe wrapper for content status"""
        try:
            pipeline = self.tools.get("content")
            if not pipeline:
                return "Content Pipeline not loaded"
            return pipeline.generate_content_status_report()
        except Exception as e:
            return f"Error: {e}"
    
    def create_blog(self, topic, keyword, product=None):
        """Safe wrapper for single blog creation"""
        try:
            pipeline = self.tools.get("content")
            if not pipeline:
                return {
                    "success": False,
                    "error": "Content Pipeline not loaded"
                }
            return pipeline.create_blog_draft(
                topic=topic,
                target_keyword=keyword,
                product_name=product
            )
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_health_safety(self, text):
        """Quick health claims check on any text"""
        try:
            pipeline = self.tools.get("content")
            if not pipeline:
                return {
                    "success": False,
                    "error": "Content Pipeline not loaded"
                }
            return {
                "success": True,
                "result": pipeline.safety_check(text)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    # ── Health Rewriter Wrappers ────────────────────────────

    def scan_products(self) -> dict:
        """Scan all WooCommerce products for health claim
        violations. Returns {total, flagged, products}."""
        try:
            rewriter = self.tools.get("rewriter")
            if not rewriter:
                return {"success": False,
                        "error": "Health Rewriter not loaded"}
            return rewriter.scan_all_products()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rewrite_flagged_products(
        self, product_id=None
    ) -> dict:
        """AI-rewrite flagged product descriptions.
        Saves to data/content/product_rewrites/ — NEVER
        auto-applies."""
        try:
            rewriter = self.tools.get("rewriter")
            if not rewriter:
                return {"success": False,
                        "error": "Health Rewriter not loaded"}
            return rewriter.rewrite_flagged(
                product_id=product_id
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_product_rewrite(
        self, product_id: int
    ) -> dict:
        """Apply an approved rewrite to WooCommerce.
        Only call after explicit human approval."""
        try:
            rewriter = self.tools.get("rewriter")
            if not rewriter:
                return {"success": False,
                        "error": "Health Rewriter not loaded"}
            return rewriter.apply_rewrite(product_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_rewrite_status(self) -> str:
        """WhatsApp-friendly summary of pending rewrites."""
        try:
            rewriter = self.tools.get("rewriter")
            if not rewriter:
                return "Health Rewriter not loaded"
            return rewriter.get_rewrite_status()
        except Exception as e:
            return f"❌ Rewrite status error: {e}"

    def run_bulk_title_fix(self):
        """Scan all products and apply title-only safety fixes"""
        try:
            rewriter = self.tools.get("rewriter")
            if not rewriter:
                return {"success": False, "error": "Health Rewriter not loaded"}
            return rewriter.bulk_fix_titles()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_disclaimer_injection(self):
        """Inject FDA disclaimer into all products missing it"""
        try:
            rewriter = self.tools.get("rewriter")
            if not rewriter:
                return {"success": False, "error": "Health Rewriter not loaded"}
            return rewriter.inject_disclaimer()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_burn_rate_report(self):
        """Get inventory/burn rate analysis"""
        try:
            predictor = self.tools.get("predictor")
            if not predictor:
                return {"success": False, "error": "Lead Predictor not loaded"}
            return predictor.get_burn_rate_report()
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Customer Win-Back Wrappers ──────────────────────────

    def find_inactive_customers(self, days=90):
        """Find customers with no orders in last N days"""
        try:
            wb = self.tools.get("winback")
            if not wb:
                return {"success": False, "error": "Win-Back not loaded"}
            return wb.find_inactive_customers(days=days)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_winback_emails(self, count=10):
        """Generate reactivation email drafts (never auto-sends)"""
        try:
            wb = self.tools.get("winback")
            if not wb:
                return {"success": False, "error": "Win-Back not loaded"}
            return wb.generate_winback_emails(count=count)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_winback_status(self):
        """WhatsApp-friendly win-back summary"""
        try:
            wb = self.tools.get("winback")
            if not wb:
                return "Win-Back module not loaded"
            return wb.get_winback_status()
        except Exception as e:
            return f"❌ Win-back status error: {e}"

    # ── AEO Agent Wrappers ──────────────────────────────

    def run_aeo_scan(self) -> dict:
        """Run monthly AEO brand visibility scan"""
        try:
            aeo = self.tools.get("aeo")
            if not aeo:
                return {"success": False,
                        "error": "AEO Agent not loaded"}
            return aeo.run_monthly_scan()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_aeo_report(self) -> str:
        """Get latest AEO scan report (WhatsApp format)"""
        try:
            aeo = self.tools.get("aeo")
            if not aeo:
                return "AEO Agent not loaded"
            return aeo.get_latest_report()
        except Exception as e:
            return f"❌ AEO report error: {e}"

    def get_aeo_content_gaps(self) -> list:
        """Return unused AEO content gaps"""
        try:
            aeo = self.tools.get("aeo")
            if not aeo:
                return []
            return aeo.get_content_gaps()
        except Exception:
            return []

    # ── Competitor Price Tracker Wrappers ──────────────────

    def run_price_scan(self) -> dict:
        """Run weekly competitor price scan"""
        try:
            pt = self.tools.get("pricing")
            if not pt:
                return {"success": False,
                        "error": "Price Tracker not loaded"}
            return pt.run_weekly_scan()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_price_report(self) -> str:
        """Get latest price comparison report"""
        try:
            pt = self.tools.get("pricing")
            if not pt:
                return "Price Tracker not loaded"
            return pt.get_latest_report()
        except Exception as e:
            return f"❌ Price report error: {e}"

    def update_competitor_price(
        self, product: str, brand: str, price: float
    ) -> dict:
        """Manually update a competitor price"""
        try:
            pt = self.tools.get("pricing")
            if not pt:
                return {"success": False,
                        "error": "Price Tracker not loaded"}
            return pt.update_manual_price(product, brand, price)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_backup(self):
        """Safe wrapper for daily backup"""
        try:
            backup = self.tools.get("backup")
            if not backup:
                return {
                    "success": False,
                    "error": "Backup tool not loaded"
                }
            return backup.create_daily_backup()
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    def run_gsc_check(self):
        """Safe wrapper for GSC health check"""
        try:
            gsc = self.tools.get("gsc")
            if not gsc:
                return {
                    "success": False,
                    "error": "GSC not loaded"
                }
            return gsc.run_health_check()
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def retry_prompt_only_drafts(self):
        """Retry all prompt_only drafts with AI client"""
        try:
            pipeline = self.tools.get("content")
            if not pipeline or not pipeline.ai_client:
                return {
                    "success": False,
                    "error": "Content Pipeline or AI not loaded"
                }

            retried = 0
            drafts_dir = Path("data/content/drafts")
            for draft_file in drafts_dir.glob("*.json"):
                if draft_file.name == "__init__.py":
                    continue
                try:
                    with open(draft_file, encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("status") != "prompt_only":
                        continue
                    if not data.get("prompt"):
                        continue

                    response = pipeline.ai_client.generate(
                        data["prompt"]
                    )
                    if response:
                        data["content"] = response
                        safety = pipeline.safety_check(response)
                        data["safety_check"] = safety
                        data["status"] = (
                            "needs_review"
                            if not safety["is_safe"]
                            else "generated"
                        )
                        if not safety["is_safe"]:
                            data["content"] = safety[
                                "cleaned_content"
                            ]
                        data["retried_at"] = (
                            datetime.now().isoformat()
                        )

                        with open(draft_file, "w",
                                  encoding="utf-8") as f:
                            json.dump(data, f, indent=2,
                                      ensure_ascii=False)
                        retried += 1
                except Exception:
                    continue

            return {"success": True, "retried": retried}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_content_queue_status(self):
        """Get content queue summary"""
        try:
            workflow = self.tools.get("workflow")
            if workflow:
                return workflow.get_queue_status()
            return "Content Workflow not loaded"
        except Exception as e:
            return f"Error: {e}"

    # ========= SMART STATUS (Phase 4) =========
    # generate_daily_digest() is defined further below.
    # This is a placeholder comment to preserve file structure.

    def generate_smart_status(self) -> str:
        """Rich status for WhatsApp 'kya ho raha hai' queries.
        Shows active tools, last task, scheduled upcoming tasks,
        and any queues needing attention."""

        now = datetime.now()
        lines = [
            "\U0001F985 *FALCON AGENCY STATUS*",
            "\u23F0 {}".format(now.strftime('%d %b %H:%M')),
            "",
        ]

        # Tools loaded (include "loaded+ai", "loaded (no AI)", etc.)
        loaded = [
            k for k, v in self.status.items()
            if "loaded" in str(v)
        ]
        failed = [
            k for k, v in self.status.items()
            if "loaded" not in str(v)
        ]
        lines.append(
            "\u2705 *Tools active:* {}/{}".format(
                len(loaded), len(loaded) + len(failed)
            )
        )
        if failed:
            lines.append(
                "   \u26A0\uFE0F Not loaded: {}".format(
                    ", ".join(failed)
                )
            )

        # Content queue
        try:
            drafts_dir = Path("data/content/drafts")
            if drafts_dir.exists():
                all_drafts = list(drafts_dir.glob("*.json"))
                pending = 0
                needs_review = 0
                for d in all_drafts:
                    try:
                        data = json.loads(
                            d.read_text(encoding="utf-8")
                        )
                        s = data.get("status", "")
                        if s == "generated":
                            pending += 1
                        elif s == "needs_review":
                            needs_review += 1
                    except Exception:
                        continue
                lines.append(
                    "\n\U0001F4DD *Content:* "
                    "{} ready  |  {} need review".format(
                        pending, needs_review
                    )
                )
        except Exception:
            pass

        # Extended schedule — next upcoming task
        try:
            sched_file = Path("data/extended_schedule.json")
            if sched_file.exists():
                sched = json.loads(
                    sched_file.read_text(encoding="utf-8")
                )
                tasks = sched.get("tasks", {})
                # Find next task that will run today
                upcoming = []
                today_str = now.strftime("%A").lower()
                now_min = now.hour * 60 + now.minute
                for name, task in tasks.items():
                    if not task.get("enabled"):
                        continue
                    freq = task.get("frequency", "daily")
                    t_str = task.get("time", "00:00")
                    t_h, t_m = map(int, t_str.split(":"))
                    t_min = t_h * 60 + t_m
                    day = task.get("day", "")
                    if freq == "weekly" and day != today_str:
                        continue
                    if t_min > now_min:
                        upcoming.append((t_min, name, t_str))
                upcoming.sort()
                if upcoming:
                    _, next_name, next_time = upcoming[0]
                    lines.append(
                        "\n\u23F3 *Next scheduled:* "
                        "{} @ {}".format(next_name, next_time)
                    )
        except Exception:
            pass

        # Pending product rewrites
        try:
            rewrites_dir = Path(
                "data/content/product_rewrites"
            )
            if rewrites_dir.exists():
                pending_rw = sum(
                    1 for f in rewrites_dir.glob("*.json")
                    if f.name not in ("last_scan.json",)
                    and json.loads(
                        f.read_text(encoding="utf-8")
                    ).get("status") == "pending"
                )
                if pending_rw:
                    lines.append(
                        "\n\U0001F6E1\uFE0F *Product rewrites "
                        "pending:* {}".format(pending_rw)
                    )
        except Exception:
            pass

        lines.append(
            "\n\U0001F916 _Director is monitoring — "
            "always on._"
        )

        return "\n".join(lines)

    # ========= MORNING REPORT =========

    def generate_morning_report(self):
        """Combined morning report with LIVE WooCommerce data"""

        lines = [
            "\U0001F985 *FALCON AGENCY \u2014 MORNING REPORT*",
            "\U0001F4C5 {}".format(
                datetime.now().strftime('%A, %d %b %Y')
            ),
            "\u2550" * 30,
        ]

        # LIVE orders from WooCommerce
        woo = self.tools.get("woocommerce")
        if woo:
            try:
                today_orders = woo.get_orders(
                    days_back=1, save=False
                )
                if today_orders.get("success"):
                    data = today_orders["data"]
                    lines.append(
                        "\n\U0001F4E6 *ORDERS (Last 24h):*"
                    )
                    lines.append(
                        "   Orders: {}".format(
                            data['total_orders']
                        )
                    )
                    lines.append(
                        "   Revenue: \u20B9{:,.0f}".format(
                            data['revenue']['total']
                        )
                    )
            except Exception:
                pass

        # Monthly revenue from tracker
        rev = self.get_revenue_report()
        if rev.get("success"):
            lines.append("\n\U0001F4B0 *MONTHLY REVENUE:*")
            lines.append(rev["report"])

        # Content queue
        queue_status = self.get_content_queue_status()
        if isinstance(queue_status, str) and \
                "Error" not in queue_status:
            lines.append("\n{}".format(queue_status))

        # Content Status
        content_status = self.get_content_status()
        if isinstance(content_status, str) and \
                "Error" not in content_status:
            lines.append("\n{}".format(content_status))

        # Tool Status
        status = self.get_status()
        all_ok = all(
            "loaded" in str(v) for v in status["tools"].values()
        )
        lines.append(
            "\n\U0001F527 *SYSTEM:* {}".format(
                "\u2705 All OK" if all_ok else "\u26A0\uFE0F Issues"
            )
        )

        failed = [
            t for t, s in status["tools"].items()
            if "loaded" not in str(s)
        ]
        if failed:
            for t in failed:
                lines.append(
                    "   \u274C {}: {}".format(
                        t, status["tools"][t]
                    )
                )

        lines.extend([
            "",
            "\u2550" * 30,
            "\U0001F916 _Falcon Agency \u2014 Automated Report_"
        ])

        return "\n".join(lines)
    
    # ========= EVENING REPORT =========

    def generate_evening_report(self):
        """Combined evening report with LIVE data"""

        lines = [
            "\U0001F985 *FALCON AGENCY \u2014 EVENING REPORT*",
            "\U0001F4C5 {}".format(
                datetime.now().strftime('%A, %d %b %Y')
            ),
            "\u2550" * 30,
        ]

        # LIVE today's orders
        woo = self.tools.get("woocommerce")
        if woo:
            try:
                today_orders = woo.get_orders(
                    days_back=1, save=False
                )
                if today_orders.get("success"):
                    data = today_orders["data"]
                    lines.append(
                        "\n\U0001F4E6 *TODAY'S ORDERS:* {}".format(
                            data['total_orders']
                        )
                    )
                    lines.append(
                        "   Revenue: \u20B9{:,.0f}".format(
                            data['revenue']['total']
                        )
                    )
                    if data['total_orders'] == 0:
                        lines.append(
                            "   \u26A0\uFE0F No orders today"
                        )
            except Exception:
                pass

        # Monthly revenue
        rev = self.get_revenue_report()
        if rev.get("success"):
            lines.append("\n\U0001F4B0 *MONTHLY SUMMARY:*")
            lines.append(rev["report"])

        # Content produced today
        try:
            from pathlib import Path
            today = datetime.now().strftime("%Y%m%d")
            drafts = Path("data/content/drafts")
            blogs = len(list(drafts.glob(
                "blog_{}_*.json".format(today)
            )))
            social = len(list(drafts.glob(
                "social_batch_{}_*.json".format(today)
            )))
            lines.append(
                "\n\U0001F4DD *CONTENT TODAY:*"
            )
            lines.append(
                "   Blogs: {} | Social: {}".format(
                    blogs, social
                )
            )
        except Exception:
            pass

        # Goal progress
        try:
            from core.goal_tracker import goal_tracker
            progress = goal_tracker.get_progress_summary()
            rev_pct = progress["revenue"]["percentage"]
            lines.append(
                "\n\U0001F3AF *GOAL PROGRESS:* {}%".format(
                    rev_pct
                )
            )
            lines.append(
                "   Day {}/30".format(
                    progress["period"]["days_elapsed"]
                )
            )
        except Exception:
            pass

        lines.extend([
            "",
            "\u2550" * 30,
            "\U0001F634 _System monitoring continues..._",
            "\U0001F916 _Falcon Agency_"
        ])

        return "\n".join(lines)

    def generate_daily_digest(self):
        """Unified daily digest — pulls ALL data sources
        into one comprehensive WhatsApp report.
        Replaces separate morning/evening reports."""

        lines = [
            "\U0001F985 *FALCON AGENCY \u2014 DAILY DIGEST*",
            "\U0001F4C5 {}".format(
                datetime.now().strftime('%A, %d %b %Y')
            ),
            "\u2550" * 30,
        ]

        # 1. LIVE Revenue — orders today
        woo = self.tools.get("woocommerce")
        if woo:
            try:
                orders = woo.get_orders(
                    days_back=1, save=False
                )
                if orders.get("success"):
                    d = orders["data"]
                    lines.append(
                        "\n\U0001F4B0 *ORDERS TODAY:* {} "
                        "| \u20B9{:,.0f}".format(
                            d['total_orders'],
                            d['revenue']['total']
                        )
                    )
            except Exception:
                pass

        # 2. Monthly revenue summary
        rev = self.get_revenue_report()
        if rev.get("success"):
            summary = rev.get("data", {})
            lines.append(
                "\U0001F4CA *MONTH:* \u20B9{:,.0f} / "
                "\u20B9{:,.0f} ({}%)".format(
                    summary.get("revenue", 0),
                    summary.get("target", 0),
                    summary.get("progress_pct", 0)
                )
            )

        # 3. Content queue status
        queue_status = self.get_content_queue_status()
        if isinstance(queue_status, str) and \
                "Error" not in queue_status and \
                "not loaded" not in queue_status:
            lines.append("\n{}".format(queue_status))

        # 4. Content stats (drafts)
        try:
            from pathlib import Path as _P
            today = datetime.now().strftime("%Y%m%d")
            drafts = _P("data/content/drafts")
            if drafts.exists():
                total_drafts = len([
                    f for f in drafts.glob("*.json")
                    if f.name != "__init__.py"
                ])
                today_drafts = len(list(
                    drafts.glob(
                        "*{}_*.json".format(today)
                    )
                ))
                lines.append(
                    "\U0001F4DD *CONTENT:* {} today "
                    "| {} total drafts".format(
                        today_drafts, total_drafts
                    )
                )
        except Exception:
            pass

        # 5. Goal progress
        try:
            from core.goal_tracker import goal_tracker
            progress = (
                goal_tracker.get_progress_summary()
            )
            rev_pct = progress["revenue"]["percentage"]
            lines.append(
                "\n\U0001F3AF *GOAL PROGRESS:* "
                "{}%".format(rev_pct)
            )
            lines.append(
                "   Day {}/30".format(
                    progress["period"]["days_elapsed"]
                )
            )
        except Exception:
            pass

        # 6. Security / Health status
        try:
            scan_file = Path(
                "data/content/product_rewrites/"
                "last_scan.json"
            )
            if scan_file.exists():
                import json as _json
                scan = _json.loads(
                    scan_file.read_text(encoding="utf-8")
                )
                flagged = scan.get("flagged", 0)
                total = scan.get("total", 0)
                lines.append(
                    "\U0001F6E1\uFE0F *HEALTH:* "
                    "{}/{} products flagged".format(
                        flagged, total
                    )
                )
        except Exception:
            pass

        # 7. Pricing alerts (if latest.json exists)
        try:
            pricing_file = Path("data/pricing/latest.json")
            if pricing_file.exists():
                import json as _pj
                pd = _pj.loads(
                    pricing_file.read_text(encoding="utf-8")
                )
                price_alerts = [
                    r for r in pd.get("results", [])
                    if r.get("recommendation", {}).get(
                        "action"
                    ) == "lower"
                ]
                if price_alerts:
                    lines.append(
                        "\n\U0001F4B9 *PRICING ALERTS:* "
                        "{} products to adjust".format(
                            len(price_alerts)
                        )
                    )
                    for pa in price_alerts[:3]:
                        rec = pa.get("recommendation", {})
                        lines.append(
                            "   \u2022 {} \u2192 "
                            "\u20B9{}".format(
                                pa["product"][:25],
                                rec.get("recommended", "?"),
                            )
                        )
        except Exception:
            pass

        # 7b. Pending product rewrites
        try:
            rewriter = self.tools.get("rewriter")
            if rewriter:
                rw_status = rewriter.get_rewrite_status()
                if "pending" in rw_status.lower():
                    first_line = rw_status.split("\n")[0]
                    lines.append(
                        "\n\U0001F6E1\uFE0F *REWRITES:* "
                        "{}".format(first_line)
                    )
        except Exception:
            pass

        # 8. System health
        status = self.get_status()
        tools_ok = sum(
            1 for v in status["tools"].values()
            if "loaded" in str(v)
        )
        tools_total = len(status["tools"])
        lines.append(
            "\U0001F527 *SYSTEM:* {}/{} tools OK".format(
                tools_ok, tools_total
            )
        )

        # 9. Task success rates
        try:
            stats_file = Path("data/task_stats.json")
            if stats_file.exists():
                import json as _json
                stats = _json.loads(
                    stats_file.read_text()
                )
                total_runs = sum(
                    s.get("total_runs", 0)
                    for s in stats.values()
                )
                avg_rate = sum(
                    s.get("success_rate", 0)
                    for s in stats.values()
                ) / max(len(stats), 1)
                lines.append(
                    "\u2699\uFE0F *TASKS:* {} runs "
                    "| {:.0f}% success".format(
                        total_runs, avg_rate
                    )
                )
        except Exception:
            pass

        lines.extend([
            "",
            "\u2550" * 30,
            "\U0001F916 _Falcon Agency \u2014 "
            "Unified Daily Digest_"
        ])

        return "\n".join(lines)


# ==================== TEST ====================

if __name__ == "__main__":
    print("🔌 Integration Bridge — Loading...")
    bridge = IntegrationBridge()
    
    # Check status
    status = bridge.get_status()
    print(f"\nTool Status:")
    for tool, state in status["tools"].items():
        icon = "✅" if state == "loaded" else "❌"
        print(f"  {icon} {tool}: {state}")
    
    # Morning report
    print("\n" + bridge.generate_morning_report())
