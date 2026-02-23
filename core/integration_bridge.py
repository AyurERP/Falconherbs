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
    
    def get_status(self):
        """Check which tools are available"""
        return {
            "timestamp": datetime.now().isoformat(),
            "tools": self.status,
            "all_loaded": all(
                v == "loaded" for v in self.status.values()
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
    
    # ========= MORNING REPORT =========
    
    def generate_morning_report(self):
        """Combined morning report for WhatsApp"""
        
        lines = [
            "🦅 *FALCON AGENCY — MORNING REPORT*",
            f"📅 {datetime.now().strftime('%A, %d %b %Y')}",
            "═" * 30,
        ]
        
        # Revenue
        rev = self.get_revenue_report()
        if rev.get("success"):
            lines.append("\n💰 *REVENUE:*")
            lines.append(rev["report"])
        
        # Content Status
        content_status = self.get_content_status()
        if isinstance(content_status, str) and \
                "Error" not in content_status:
            lines.append(f"\n{content_status}")
        
        # Tool Status
        status = self.get_status()
        all_ok = status["all_loaded"]
        lines.append(f"\n🔧 *SYSTEM STATUS:* "
                     f"{'✅ All OK' if all_ok else '⚠️ Issues'}")
        
        for tool, state in status["tools"].items():
            icon = "✅" if state == "loaded" else "❌"
            lines.append(f"   {icon} {tool}: {state}")
        
        lines.extend([
            "",
            "═" * 30,
            "🤖 _Falcon Agency — Automated Report_"
        ])
        
        return "\n".join(lines)
    
    # ========= EVENING REPORT =========
    
    def generate_evening_report(self):
        """Combined evening report for WhatsApp"""
        
        lines = [
            "🦅 *FALCON AGENCY — EVENING REPORT*",
            f"📅 {datetime.now().strftime('%A, %d %b %Y')}",
            "═" * 30,
        ]
        
        # Revenue
        rev = self.get_revenue_report()
        if rev.get("success"):
            lines.append("\n💰 *TODAY'S REVENUE:*")
            lines.append(rev["report"])
        
        # Content
        content_status = self.get_content_status()
        if isinstance(content_status, str):
            lines.append(f"\n{content_status}")
        
        # Tomorrow's plan
        lines.extend([
            "\n📋 *TOMORROW'S PLAN:*",
            "   📝 Generate content drafts",
            "   📱 Social media posts",
            "   🔍 Monitor site health",
            "   📊 Track ad performance",
            "",
            "═" * 30,
            "💤 _Goodnight! System monitoring continues..._",
            "🤖 _Falcon Agency_"
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
