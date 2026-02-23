"""
Falcon Agency — Commander Intent Extensions
New intents for WooCommerce, Health Scanner, 
Content Pipeline, Revenue Tracker.

This file EXTENDS the Commander's intent classification.
Import this in commander.py to add new capabilities.
"""

import re
import json
from datetime import datetime


class ExtendedIntentClassifier:
    """
    Classifies new intent categories from WhatsApp messages.
    Works alongside existing intent classifier, not replacing it.
    """
    
    def __init__(self, integration_bridge=None):
        self.bridge = integration_bridge
        self._init_intent_patterns()
    
    def _init_intent_patterns(self):
        """Define new intent patterns"""
        
        self.intents = {
            # ===== STORE / WOOCOMMERCE =====
            "store_audit": {
                "patterns": [
                    r"\bstore\s+audit\b",
                    r"\bcheck\s+store\b",
                    r"\bstore\s+(?:check|health)\b",
                    r"\bstore\s+status\b",
                    r"\bwoocommerce\b",
                    r"\bproduct(?:s)?\s+check\b",
                    r"\bproduct(?:s)?\s+status\b",
                    r"\bkitne\s+product\b",
                    r"\bstore\s+kaisa\b",
                    r"\bdukaan\b",
                    r"\bshop\s+status\b",
                    r"\binventory\b",
                    r"\bstock\s+check\b",
                ],
                "handler": "handle_store_audit",
                "description": "Full WooCommerce store audit"
            },
            
            "order_check": {
                "patterns": [
                    r"\border(?:s)?\s*(?:check|status|kitne|how\s+many)\b",
                    r"\bhow\s+many\s+orders?\b",
                    r"\bkitne\s+order\b",
                    r"\border\s+history\b",
                    r"\brecent\s+orders?\b",
                    r"\bnew\s+orders?\b",
                    r"\bkoi\s+order\s+aaya\b",
                    r"\border\s+aa(?:ya|ye|yi)\b",
                    r"\bsales\s+check\b",
                    r"\bsales\s+kitni\b",
                ],
                "handler": "handle_order_check",
                "description": "Check recent orders"
            },
            
            "payment_check": {
                "patterns": [
                    r"\bpayment\s+(?:gateway|status|check)\b",
                    r"\bpayment\s+kaam\b",
                    r"\brazorpay\b",
                    r"\bpaypal\b",
                    r"\bpayment\s+method\b",
                    r"\bpayment\s+chal\b",
                    r"\bcustomer(?:s)?\s+pay\b",
                    r"\bpayment\s+gateway\b",
                ],
                "handler": "handle_payment_check",
                "description": "Check payment gateways"
            },
            
            # ===== HEALTH CLAIMS =====
            "health_scan": {
                "patterns": [
                    r"\bhealth\s+(?:scan|check|audit|claims?)\b",
                    r"\bfda\b",
                    r"\bftc\b",
                    r"\bcompliance\b",
                    r"\bhealth\s+claims?\b",
                    r"\bviolation\b",
                    r"\brisk\s+(?:scan|check|report)\b",
                    r"\blegal\s+check\b",
                    r"\bclaims?\s+check\b",
                    r"\bsite\s+scan\b",
                    r"\bwebsite\s+scan\b",
                ],
                "handler": "handle_health_scan",
                "description": "Scan for health claim violations"
            },
            
            "safety_check": {
                "patterns": [
                    r"\bis\s+this\s+safe\b",
                    r"\bcheck\s+this\s+(?:text|content|line)\b",
                    r"\bcan\s+(?:i|we)\s+(?:say|write|use)\b",
                    r"\bsafe\s+to\s+(?:say|write|use)\b",
                    r"\bhealth\s+safe\b",
                    r"\bclaim\s+safe\b",
                    r"\bye\s+likh\s+sakte\b",
                    r"\bye\s+bol\s+sakte\b",
                ],
                "handler": "handle_safety_check",
                "description": "Quick health safety check on text"
            },
            
            # ===== REVENUE =====
            "revenue_check": {
                "patterns": [
                    r"\brevenue\b",
                    r"\bearnings?\b",
                    r"\bkitna\s+kamaya\b",
                    r"\bkamai\b",
                    r"\bincome\b",
                    r"\bpaise\b",
                    r"\bmoney\b",
                    r"\brevenue\s+report\b",
                    r"\bfinancial\b",
                    r"\bkitna\s+hua\b",
                ],
                "handler": "handle_revenue_check",
                "description": "Revenue and financial report"
            },
            
            # ===== CONTENT =====
            "create_blog": {
                "patterns": [
                    r"\bblog\s+(?:likh|write|create|bana|generate)\b",
                    r"\b(?:likh|write|create|bana)\s+(?:a\s+)?blog\b",
                    r"\bblog\s+post\b",
                    r"\barticle\s+(?:likh|write|create)\b",
                    r"\b(?:likh|write)\s+(?:about|on|par)\b",
                    r"\bcontent\s+(?:create|generate|bana)\b",
                ],
                "handler": "handle_create_blog",
                "description": "Generate blog post draft"
            },
            
            "create_social": {
                "patterns": [
                    r"\bsocial\s+(?:post|media|content)\b",
                    r"\binstagram\s+(?:post|caption)\b",
                    r"\bfacebook\s+(?:post|caption)\b",
                    r"\bpinterest\s+(?:pin|post)\b",
                    r"\bcaption(?:s)?\s+(?:likh|write|bana|create)\b",
                    r"\bsocial\s+(?:likh|write|bana|create)\b",
                    r"\bpost\s+(?:bana|likh|create)\b",
                ],
                "handler": "handle_create_social",
                "description": "Generate social media posts"
            },
            
            "content_status": {
                "patterns": [
                    r"\bcontent\s+(?:status|report|kitna)\b",
                    r"\bdraft(?:s)?\s+(?:status|kitne|check)\b",
                    r"\bcontent\s+(?:kahan|where)\b",
                    r"\bkitna\s+content\b",
                    r"\bcontent\s+ready\b",
                    r"\bblog(?:s)?\s+(?:kitne|status|ready)\b",
                ],
                "handler": "handle_content_status",
                "description": "Content pipeline status"
            },
            
            "generate_weekly": {
                "patterns": [
                    r"\bweekly\s+content\b",
                    r"\bweek\s+ka\s+content\b",
                    r"\bhafta\b.*\bcontent\b",
                    r"\bgenerate\s+(?:all|weekly|this\s+week)\b",
                    r"\bsab\s+(?:bana|generate)\b",
                    r"\bpura\s+(?:content|week)\b",
                    r"\bfull\s+generation\b",
                ],
                "handler": "handle_generate_weekly",
                "description": "Generate full week's content"
            },
            
            # ===== REPORTS =====
            "morning_report": {
                "patterns": [
                    r"\bmorning\s+report\b",
                    r"\bsubah\s+(?:ka\s+)?report\b",
                    r"\bsummary\b",
                    r"\bstatus\s+report\b",
                    r"\boverall\s+status\b",
                    r"\bsab\s+batao\b",
                    r"\bkya\s+chal\b",
                    r"\bkya\s+ho\s+raha\b",
                    r"\bupdate\s+do\b",
                    r"\bbrief\s+do\b",
                ],
                "handler": "handle_morning_report",
                "description": "Full system status report"
            },
            
            "evening_report": {
                "patterns": [
                    r"\bevening\s+report\b",
                    r"\bsham\s+(?:ka\s+)?report\b",
                    r"\bend\s+of\s+day\b",
                    r"\bdin\s+(?:ka|khatam)\b",
                    r"\btoday\s+(?:ka\s+)?summary\b",
                    r"\baaj\s+ka\s+(?:summary|report)\b",
                    r"\bday\s+report\b",
                ],
                "handler": "handle_evening_report",
                "description": "End of day summary"
            },
            
            # ===== CUSTOMER RECOVERY =====
            "customer_recovery": {
                "patterns": [
                    r"\bpolish\s+customer\b",
                    r"\bpoland\b",
                    r"\breconnect\b",
                    r"\bpurane\s+customer\b",
                    r"\bold\s+customer\b",
                    r"\bcustomer\s+(?:dhundh|find|search)\b",
                    r"\breactivat\w+\b",
                    r"\bcustomer\s+wapas\b",
                    r"\bcustomer\s+list\b",
                ],
                "handler": "handle_customer_recovery",
                "description": "Customer recovery and reactivation"
            },
            
            # ===== GOALS & TRACKING (new) =====
            "goal_set": {
                "patterns": [
                    r"\bgoal\s+set\b",
                    r"\bgoal\s+(?:lagao|rakho|karo)\b",
                    r"\btarget\s+set\b",
                    r"\btarget\s+(?:lagao|rakho|karo)\b",
                    r"\bset\s+(?:monthly|30.?day)\s+goal\b",
                    r"\bmonthly\s+(?:target|goal)\b",
                    r"\b30\s*day\s+goal\b",
                    r"\bgoal.*\brevenue\b",
                    r"\btarget.*\brevenue\b",
                    r"\bgoal.*\bblog\b",
                    r"\bgoal.*\bsocial\b",
                ],
                "handler": "handle_goal_set",
                "description": "Set 30-day goals"
            },
            
            "progress_check": {
                "patterns": [
                    r"\bprogress\s+(?:dikhao|check|status|batao|show)\b",
                    r"\bgoal\s+(?:progress|status|update)\b",
                    r"\btarget\s+(?:progress|status|kahan)\b",
                    r"\bkitna\s+(?:hua|done|complete)\b",
                    r"\btrack\s+(?:dikhao|check|show)\b",
                    r"\bdaily\s+report\b",
                ],
                "handler": "handle_progress_check",
                "description": "Check goal progress"
            },
            
            "profit_report": {
                "patterns": [
                    r"\bprofit\s+report\b",
                    r"\bprofit\s+(?:dikhao|batao|show|check)\b",
                    r"\bkitna\s+profit\b",
                    r"\bcost\s+(?:report|check|kitna)\b",
                    r"\broi\b",
                    r"\bexpense\b",
                    r"\bkharcha\b",
                    r"\bmunafa\b",
                ],
                "handler": "handle_profit_report",
                "description": "Profit and cost report"
            },
            
            # ===== FULL SEO (new) =====
            "full_seo_audit": {
                "patterns": [
                    r"\bfull\s+seo\b",
                    r"\bseo\s+audit\b",
                    r"\bseo\s+(?:karo|check|scan|report)\b",
                    r"\bcomplete\s+seo\b",
                    r"\bdeep\s+seo\b",
                    r"\bseo\s+analysis\b",
                ],
                "handler": "handle_full_seo_audit",
                "description": "Full multi-page SEO audit"
            },
            
            # ===== CONTENT CALENDAR (new) =====
            "content_calendar": {
                "patterns": [
                    r"\bcontent\s+calendar\b",
                    r"\bcalendar\s+(?:bana|create|generate)\b",
                    r"\bmonthly\s+(?:content|plan)\b",
                    r"\b30\s*day\s+(?:content|plan)\b",
                    r"\bposting\s+(?:plan|schedule)\b",
                ],
                "handler": "handle_content_calendar",
                "description": "Generate content calendar"
            },
            
            # ===== COMPETITOR (new) =====
            "competitor_analysis": {
                "patterns": [
                    r"\bcompetitor\s+(?:analysis|check|scan)\b",
                    r"\bcompetition\s+(?:check|dekho|analysis)\b",
                    r"\bcompetitor\s+(?:karo|dekho)\b",
                    r"\brival\b",
                    r"\bcompete\b",
                ],
                "handler": "handle_competitor_analysis",
                "description": "Deep competitor analysis"
            },
            
            # ===== BACKUP (new) =====
            "backup_create": {
                "patterns": [
                    r"\bbackup\s+(?:bana|create|le|karo|banao)\b",
                    r"\bsnapshot\s+(?:bana|le|create)\b",
                    r"\bdata\s+(?:backup|save)\b",
                    r"\bbackup\s+le\b",
                    r"\bbanao\s+backup\b",
                ],
                "handler": "handle_backup_create",
                "description": "Create backup snapshot"
            },
            
            "backup_list": {
                "patterns": [
                    r"\bbackup(?:s)?\s+(?:dikhao|list|show|kitne)\b",
                    r"\blist\s+backup\b",
                    r"\bkitne\s+backup\b",
                    r"\bavailable\s+backup\b",
                ],
                "handler": "handle_backup_list",
                "description": "List available backups"
            },
            
            "backup_verify": {
                "patterns": [
                    r"\bdata\s+verify\b",
                    r"\bbackup\s+(?:verify|check|integrity)\b",
                    r"\bintegrity\s+check\b",
                    r"\bdata\s+(?:safe|check)\b",
                ],
                "handler": "handle_backup_verify",
                "description": "Verify backup integrity"
            },
            
            # ===== WORDPRESS PUBLISHING (B1) =====
            "list_drafts": {
                "patterns": [
                    r"\bdraft(?:s)?\s+(?:dikhao|list|show|kitne|batao)\b",
                    r"\blist\s+draft\b",
                    r"\bblog(?:s)?\s+(?:dikhao|list|pending|drafts?)\b",
                    r"\bpending\s+(?:blog|content|post)\b",
                ],
                "handler": "handle_list_drafts",
                "description": "List pending blog drafts"
            },
            
            "preview_draft": {
                "patterns": [
                    r"\bpreview\s+(?:blog|draft|post|karo|dikhao)\b",
                    r"\bdraft\s+preview\b",
                    r"\bblog\s+(?:preview|dekho|dekhao)\b",
                    r"\bdekhao\s+draft\b",
                ],
                "handler": "handle_preview_draft",
                "description": "Preview a blog draft for approval"
            },
            
            "publish_blog": {
                "patterns": [
                    r"\bpublish\s+(?:karo|blog|post|draft|it|this)\b",
                    r"\bblog\s+publish\b",
                    r"\bpost\s+(?:karo|publish|daal)\b",
                    r"\bwordpress\s+(?:pe|par|publish|post)\b",
                    r"\bwp\s+(?:publish|post)\b",
                    r"\bdaal\s+(?:do|de)\s+(?:blog|post|website)\b",
                ],
                "handler": "handle_publish_blog",
                "description": "Publish blog to WordPress"
            },
            
            "reject_draft": {
                "patterns": [
                    r"\breject\s+(?:karo|blog|draft|it)\b",
                    r"\bdraft\s+(?:reject|delete|hata)\b",
                    r"\bblog\s+(?:reject|delete|hata|cancel)\b",
                    r"\bhata\s+(?:do|de)\s+(?:draft|blog)\b",
                ],
                "handler": "handle_reject_draft",
                "description": "Reject and delete a draft"
            },
        }
    
    def classify(self, message):
        """
        Classify a message into new intent categories.
        
        Returns:
            dict with 'intent', 'confidence', 'handler', 
            'extracted_data' or None if no match
        """
        message_lower = message.lower().strip()
        
        best_match = None
        best_score = 0
        
        for intent_name, intent_data in self.intents.items():
            score = 0
            matched_patterns = []
            
            for pattern in intent_data["patterns"]:
                if re.search(pattern, message_lower):
                    score += 1
                    matched_patterns.append(pattern)
            
            if score > best_score:
                best_score = score
                best_match = {
                    "intent": intent_name,
                    "handler": intent_data["handler"],
                    "description": intent_data["description"],
                    "confidence": min(score / 2, 1.0),
                    "matched_patterns": len(matched_patterns),
                    "extracted_data": self._extract_data(
                        intent_name, message
                    )
                }
        
        if best_match and best_match["confidence"] >= 0.5:
            return best_match
        
        return None
    
    def _extract_data(self, intent, message):
        """Extract relevant data from message based on intent"""
        data = {}
        
        if intent == "create_blog":
            # Try to extract topic
            patterns = [
                r"(?:about|on|par|topic)\s+[\"']?(.+?)[\"']?\s*$",
                r"blog\s+(?:likh|write|create|bana)\s+(.+?)$",
                r"(?:likh|write)\s+(?:about|on|par)\s+(.+?)$",
            ]
            for p in patterns:
                match = re.search(p, message, re.IGNORECASE)
                if match:
                    data["topic"] = match.group(1).strip()
                    break
        
        elif intent == "safety_check":
            # Extract the text to check
            patterns = [
                r"(?:check|safe)\s*[:\-]?\s*[\"'](.+?)[\"']",
                r"(?:can\s+(?:i|we)\s+(?:say|write))\s+[\"'](.+?)[\"']",
                r"(?:ye\s+(?:likh|bol)\s+sakte)\s*[:\-]?\s*(.+?)$",
            ]
            for p in patterns:
                match = re.search(p, message, re.IGNORECASE)
                if match:
                    data["text_to_check"] = match.group(1).strip()
                    break
        
        elif intent in ("health_scan",):
            # Check if specific URL mentioned
            url_match = re.search(
                r'(https?://\S+)', message
            )
            if url_match:
                data["url"] = url_match.group(1)
        
        elif intent == "goal_set":
            # Extract revenue target
            rev_match = re.search(
                r'(?:revenue|target|kamana)\s+(?:₹)?\s*(\d[\d,]*)', message, re.IGNORECASE
            )
            if rev_match:
                data["revenue_target"] = int(rev_match.group(1).replace(',', ''))
            
            blog_match = re.search(r'blog(?:s)?\s+(\d+)', message, re.IGNORECASE)
            if blog_match:
                data["blog_posts_target"] = int(blog_match.group(1))
            
            social_match = re.search(r'social\s+(\d+)', message, re.IGNORECASE)
            if social_match:
                data["social_posts_target"] = int(social_match.group(1))
        
        elif intent == "competitor_analysis":
            # Extract competitor URL
            url_match = re.search(r'(https?://\S+)', message)
            if url_match:
                data["competitor_url"] = url_match.group(1)
            else:
                # Try bare domain
                domain_match = re.search(r'([a-zA-Z0-9-]+\.(?:com|in|co\.in|net|org))', message)
                if domain_match:
                    data["competitor_url"] = f"https://{domain_match.group(1)}"
        
        return data


class IntentResponseHandler:
    """
    Handles responses for new intents.
    Each handler returns a WhatsApp-ready response.
    """
    
    def __init__(self, integration_bridge):
        self.bridge = integration_bridge
    
    def handle(self, intent_result):
        """Route to appropriate handler"""
        handler_name = intent_result.get("handler")
        handler = getattr(self, handler_name, None)
        
        if handler:
            return handler(intent_result)
        
        return {
            "response": "🤔 Intent samajh aaya but handler "
                       "not ready yet. Coming soon!",
            "success": False
        }
    
    def handle_store_audit(self, intent):
        """Run full store audit"""
        result = self.bridge.run_store_audit()
        if result.get("success"):
            return {
                "response": result.get("summary", 
                    "✅ Store audit complete! "
                    "Check data/woocommerce/full_audit.json"),
                "success": True,
                "data": result.get("data")
            }
        return {
            "response": f"❌ Store audit failed: "
                       f"{result.get('error', 'Unknown error')}\n\n"
                       f"Possible issues:\n"
                       f"1. WooCommerce API keys not in .env\n"
                       f"2. Site offline\n"
                       f"3. API permissions issue",
            "success": False
        }
    
    def handle_order_check(self, intent):
        """Check recent orders"""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {
                    "response": "❌ WooCommerce not connected. "
                               "API keys check karo .env mein.",
                    "success": False
                }
            
            result = woo.get_orders(days_back=30)
            if result["success"]:
                data = result["data"]
                total = data["total_orders"]
                revenue = data["revenue"]["total"]
                aov = data["revenue"]["average_order_value"]
                
                response = (
                    f"🛒 *ORDERS — Last 30 Days*\n"
                    f"─────────────────\n"
                    f"📦 Total Orders: {total}\n"
                    f"💰 Revenue: ₹{revenue:,.0f}\n"
                    f"📊 Avg Order: ₹{aov:,.0f}\n"
                )
                
                if data.get("country_breakdown"):
                    response += "\n🌍 *By Country:*\n"
                    for country, count in sorted(
                        data["country_breakdown"].items(),
                        key=lambda x: x[1], reverse=True
                    )[:5]:
                        response += f"   {country}: {count}\n"
                
                if total == 0:
                    response += (
                        "\n⚠️ Koi order nahi aaya. "
                        "Content + ads start karna hoga."
                    )
                
                return {"response": response, "success": True}
            
            return {
                "response": f"❌ Error: {result.get('error')}",
                "success": False
            }
        except Exception as e:
            return {
                "response": f"❌ Order check failed: {e}",
                "success": False
            }
    
    def handle_payment_check(self, intent):
        """Check payment gateways"""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {
                    "response": "❌ WooCommerce not connected.",
                    "success": False
                }
            
            result = woo.get_payment_gateways()
            if result["success"]:
                data = result["data"]
                active = data.get("active_gateways", [])
                
                response = "💳 *PAYMENT GATEWAYS*\n─────────────\n"
                
                if active:
                    response += f"✅ Active: {len(active)}\n"
                    for g in active:
                        response += f"   ✅ {g['title']}\n"
                else:
                    response += (
                        "❌ *NO ACTIVE PAYMENT GATEWAY!*\n"
                        "⚠️ Customers CANNOT pay!\n"
                        "🔧 Action: Go to WooCommerce → "
                        "Settings → Payments\n"
                        "   Enable Razorpay or PayPal immediately!"
                    )
                
                inactive = data.get("inactive_gateways", [])
                if inactive:
                    response += f"\n🔴 Inactive: {len(inactive)}\n"
                    for g in inactive:
                        response += f"   🔴 {g['title']}\n"
                
                return {"response": response, "success": True}
            
            return {
                "response": f"❌ Error: {result.get('error')}",
                "success": False
            }
        except Exception as e:
            return {
                "response": f"❌ Payment check failed: {e}",
                "success": False
            }
    
    def handle_health_scan(self, intent):
        """Run health claims scan"""
        url = intent.get("extracted_data", {}).get("url")
        
        response = (
            "🏥 *Health Claims Scan Starting...*\n"
            "⏱️ This takes 2-5 minutes depending on "
            "site size.\n"
            "📊 Results will be saved to "
            "data/health_audit/\n\n"
            "🔄 Scanning..."
        )
        
        result = self.bridge.run_health_scan(max_pages=100)
        
        if result.get("success"):
            return {
                "response": result.get("summary",
                    "✅ Scan complete! Check report."),
                "success": True
            }
        
        return {
            "response": f"❌ Scan failed: "
                       f"{result.get('error')}\n"
                       f"Check: Is site online? "
                       f"Is beautifulsoup4 installed?",
            "success": False
        }
    
    def handle_safety_check(self, intent):
        """Quick safety check on specific text"""
        text = intent.get("extracted_data", {}).get(
            "text_to_check", ""
        )
        
        if not text:
            return {
                "response": (
                    "🤔 Kya check karna hai?\n\n"
                    "Example:\n"
                    "\"Check this: our herb cures diabetes\"\n"
                    "\"Is this safe: boosts immunity naturally\""
                ),
                "success": True
            }
        
        result = self.bridge.check_health_safety(text)
        
        if result.get("success"):
            data = result["result"]
            
            response = "🏥 *HEALTH SAFETY CHECK*\n─────────────\n"
            response += f"📝 Text: \"{text[:100]}\"\n\n"
            
            if data["is_safe"]:
                response += "✅ *SAFE* — No major issues found.\n"
            else:
                response += "❌ *NOT SAFE* — Issues found:\n\n"
            
            for change in data.get("changes", []):
                if change["severity"] == "HIGH":
                    icon = "🔴"
                elif change["severity"] == "MEDIUM":
                    icon = "🟡"
                else:
                    icon = "🟢"
                
                response += f"{icon} {change.get('found', '')}\n"
                
                if "replaced_with" in change:
                    response += (
                        f"   ✅ Better: \"{change['replaced_with']}\"\n"
                    )
                else:
                    response += (
                        f"   ⚠️ {change.get('action', 'Review needed')}\n"
                    )
                response += "\n"
            
            if data.get("needs_disclaimer"):
                response += "📋 Add FDA disclaimer to this content.\n"
            
            return {"response": response, "success": True}
        
        return {
            "response": f"❌ Check failed: {result.get('error')}",
            "success": False
        }
    
    def handle_revenue_check(self, intent):
        """Revenue report"""
        result = self.bridge.get_revenue_report()
        
        if result.get("success"):
            return {
                "response": result["report"],
                "success": True
            }
        
        return {
            "response": f"❌ Revenue check failed: "
                       f"{result.get('error')}",
            "success": False
        }
    
    def handle_create_blog(self, intent):
        """Create a blog post"""
        topic = intent.get("extracted_data", {}).get("topic", "")
        
        if not topic:
            return {
                "response": (
                    "📝 Blog kis topic pe likhna hai?\n\n"
                    "Examples:\n"
                    "• \"Write blog about ashwagandha benefits\"\n"
                    "• \"Blog likh par turmeric for immunity\"\n"
                    "• \"Create blog on ayurvedic morning routine\""
                ),
                "success": True
            }
        
        result = self.bridge.create_blog(
            topic=topic,
            keyword=topic.lower().replace(" ", " "),
            product=None
        )
        
        if result.get("success"):
            draft = result.get("draft", {})
            status = draft.get("status", "unknown")
            
            response = (
                f"📝 *BLOG DRAFT CREATED*\n"
                f"─────────────\n"
                f"📌 Topic: {topic}\n"
                f"📊 Status: {status}\n"
                f"📂 File: {result.get('file', 'N/A')}\n\n"
            )
            
            if status == "prompt_only":
                response += (
                    "ℹ️ AI client connected nahi hai abhi.\n"
                    "Prompt saved hai — manually AI se "
                    "generate kar sakte ho.\n"
                    "Ya Phase 4 mein auto-generation "
                    "setup karenge."
                )
            elif status == "generated":
                response += "✅ Content generated! Review karo."
            elif status == "needs_review":
                response += (
                    "⚠️ Content mein health claims found.\n"
                    "Auto-cleaned but review zaroor karna."
                )
            
            return {"response": response, "success": True}
        
        return {
            "response": f"❌ Blog creation failed: "
                       f"{result.get('error')}",
            "success": False
        }
    
    def handle_create_social(self, intent):
        """Create social media posts"""
        result = self.bridge.tools.get("content")
        
        if not result:
            return {
                "response": "❌ Content Pipeline not loaded.",
                "success": False
            }
        
        return {
            "response": (
                "📱 *Social Posts Generator*\n\n"
                "Options:\n"
                "1️⃣ \"Generate weekly content\" — "
                "Full week batch\n"
                "2️⃣ \"Social post about [topic]\" — "
                "Single post\n\n"
                "Current drafts check karo:\n"
                "\"Content status\" bol do"
            ),
            "success": True
        }
    
    def handle_content_status(self, intent):
        """Content pipeline status"""
        report = self.bridge.get_content_status()
        return {
            "response": report if isinstance(report, str)
                       else str(report),
            "success": True
        }
    
    def handle_generate_weekly(self, intent):
        """Generate full week's content"""
        response = (
            "🚀 *Weekly Content Generation Starting...*\n"
            "⏱️ This takes 1-2 minutes.\n\n"
            "Generating:\n"
            "📝 2 Blog drafts\n"
            "📱 84+ Social post options\n"
            "📧 Email sequences\n"
            "📅 12-week calendar\n\n"
            "🔄 Working..."
        )
        
        result = self.bridge.generate_weekly_content()
        
        if result.get("success"):
            return {
                "response": (
                    "✅ *WEEKLY CONTENT GENERATED!*\n"
                    "─────────────\n"
                    "📝 Blog drafts: 2\n"
                    "📱 Social batch: 84+ options\n"
                    "📧 Email sequences: 3\n"
                    "📅 Calendar: 12 weeks\n"
                    "🤝 Reconnect page: Ready\n\n"
                    "📂 All files in: data/content/drafts/\n"
                    "👀 Review → Approve → Publish"
                ),
                "success": True
            }
        
        return {
            "response": f"❌ Generation failed: "
                       f"{result.get('error')}",
            "success": False
        }
    
    def handle_morning_report(self, intent):
        """Full morning report"""
        return {
            "response": self.bridge.generate_morning_report(),
            "success": True
        }
    
    def handle_evening_report(self, intent):
        """Evening report"""
        return {
            "response": self.bridge.generate_evening_report(),
            "success": True
        }
    
    def handle_customer_recovery(self, intent):
        """Customer recovery info"""
        # Check if customer data available
        try:
            woo = self.bridge.tools.get("woocommerce")
            customers = None
            
            if woo:
                result = woo.get_customers()
                if result.get("success"):
                    customers = result["data"]
            
            response = "👥 *CUSTOMER RECOVERY*\n─────────────\n\n"
            
            if customers:
                total = customers.get("total_customers", 0)
                countries = customers.get(
                    "country_breakdown", {}
                )
                polish = countries.get("PL", 0)
                
                response += f"📊 Total Customers: {total}\n"
                response += f"🇵🇱 Polish Customers: {polish}\n\n"
                
                if polish > 0:
                    response += (
                        "✅ Polish customer data FOUND "
                        "in WooCommerce!\n"
                        "Check data/woocommerce/"
                        "customers.json\n"
                        "Search for country: 'PL'\n\n"
                    )
                
                response += "🌍 Customer Countries:\n"
                for country, count in sorted(
                    countries.items(),
                    key=lambda x: x[1], reverse=True
                )[:10]:
                    response += f"   {country}: {count}\n"
            else:
                response += (
                    "⚠️ WooCommerce data not available.\n"
                    "Run 'store audit' first.\n"
                )
            
            response += (
                "\n📧 *RECOVERY TOOLS READY:*\n"
                "├── Reactivation emails: ✅ Drafted\n"
                "├── Polish customer email: ✅ Drafted\n"
                "├── Reconnect page: ✅ Ready\n"
                "└── Welcome sequence: ✅ Ready\n\n"
                "📂 Check: data/content/drafts/email_*.json\n"
                "📂 Check: data/content/drafts/"
                "reconnect_page.json"
            )
            
            return {"response": response, "success": True}
            
        except Exception as e:
            return {
                "response": f"❌ Error: {e}",
                "success": False
            }
    
    # ===== NEW HANDLERS (Phase 2 additions) =====
    
    def handle_goal_set(self, intent):
        """Set 30-day goals"""
        from core.goal_tracker import goal_tracker
        
        data = intent.get("extracted_data", {})
        revenue = data.get("revenue_target", 0)
        blogs = data.get("blog_posts_target", 0)
        social = data.get("social_posts_target", 0)
        
        if not revenue and not blogs and not social:
            return {
                "response": (
                    "🎯 *Goal Set karna hai!*\n\n"
                    "Format:\n"
                    "\"Goal set karo revenue 12500 blogs 8 social 30\"\n\n"
                    "Ya individual set karo:\n"
                    "\"Target set karo revenue 12500\""
                ),
                "success": True
            }
        
        goals = {}
        if revenue:
            goals["revenue_target"] = revenue
        if blogs:
            goals["blog_posts_target"] = blogs
        if social:
            goals["social_posts_target"] = social
        
        goal_tracker.set_monthly_goals(goals)
        
        response = "🎯 *30-DAY GOALS SET!*\n─────────────\n"
        if revenue:
            response += f"💰 Revenue Target: ₹{revenue:,}\n"
        if blogs:
            response += f"📝 Blog Posts: {blogs}\n"
        if social:
            response += f"📱 Social Posts: {social}\n"
        response += "\n✅ Tracking started! \"Progress dikhao\" bol ke check karo."
        
        return {"response": response, "success": True}
    
    def handle_progress_check(self, intent):
        """Check goal progress and daily report"""
        from core.goal_tracker import goal_tracker
        
        try:
            report = goal_tracker.generate_daily_report()
            return {"response": report, "success": True}
        except Exception as e:
            return {
                "response": f"❌ Progress check failed: {e}\n"
                           "Pehle goals set karo: \"Goal set karo revenue 12500\"",
                "success": False
            }
    
    def handle_profit_report(self, intent):
        """Profit and cost report"""
        from core.profit_tracker import profit_tracker
        
        try:
            report = profit_tracker.generate_profit_report(days=30)
            return {"response": report, "success": True}
        except Exception as e:
            return {
                "response": f"❌ Profit report failed: {e}",
                "success": False
            }
    
    def handle_full_seo_audit(self, intent):
        """Full multi-page SEO audit via DeveloperAgent"""
        try:
            from agents.developer import DeveloperAgent
            dev = DeveloperAgent()
            report = dev._full_seo_audit(site="falconherbs.com")
            return {"response": report[:1500], "success": True}
        except Exception as e:
            return {
                "response": f"❌ SEO audit failed: {e}",
                "success": False
            }
    
    def handle_content_calendar(self, intent):
        """Generate 30-day content calendar"""
        try:
            from agents.strategist import StrategistAgent
            strat = StrategistAgent()
            report = strat._content_calendar(days=30)
            return {"response": report[:1500], "success": True}
        except Exception as e:
            return {
                "response": f"❌ Calendar generation failed: {e}",
                "success": False
            }
    
    def handle_competitor_analysis(self, intent):
        """Deep competitor analysis"""
        url = intent.get("extracted_data", {}).get("competitor_url", "")
        
        if not url:
            return {
                "response": (
                    "🔍 *Competitor Analysis*\n\n"
                    "Kiska analysis karna hai?\n\n"
                    "Format:\n"
                    "\"Competitor analysis karo https://example.com\"\n"
                    "\"Competition check karo herbsforever.com\""
                ),
                "success": True
            }
        
        try:
            from agents.strategist import StrategistAgent
            strat = StrategistAgent()
            report = strat._deep_competitor_analysis(competitor_url=url)
            return {"response": report[:1500], "success": True}
        except Exception as e:
            return {
                "response": f"❌ Competitor analysis failed: {e}",
                "success": False
            }
    
    def handle_backup_create(self, intent):
        """Create backup snapshot"""
        try:
            from agents.backup import BackupAgent
            backup = BackupAgent()
            report = backup.quick_snapshot()
            return {"response": report[:1500], "success": True}
        except Exception as e:
            return {
                "response": f"❌ Backup failed: {e}",
                "success": False
            }
    
    def handle_backup_list(self, intent):
        """List available backups"""
        try:
            from agents.backup import BackupAgent
            backup = BackupAgent()
            report = backup.quick_list()
            return {"response": report[:1500], "success": True}
        except Exception as e:
            return {
                "response": f"❌ Backup list failed: {e}",
                "success": False
            }
    
    def handle_backup_verify(self, intent):
        """Verify backup integrity"""
        try:
            from agents.backup import BackupAgent
            backup = BackupAgent()
            report = backup.quick_verify()
            return {"response": report[:1500], "success": True}
        except Exception as e:
            return {
                "response": f"❌ Integrity check failed: {e}",
                "success": False
            }
    
    # ===== WORDPRESS PUBLISHING (B1) =====
    
    def handle_list_drafts(self, intent):
        """List pending blog drafts"""
        try:
            from core.wordpress_publisher import wp_publisher
            drafts = wp_publisher.list_drafts()
            return {"response": drafts, "success": True}
        except Exception as e:
            return {
                "response": f"❌ Drafts list error: {e}",
                "success": False
            }
    
    def handle_preview_draft(self, intent):
        """Preview a draft for WhatsApp approval"""
        try:
            from core.wordpress_publisher import wp_publisher
            draft_name = intent.get("extracted_data", {}).get("topic")
            result = wp_publisher.get_draft_preview(draft_name)
            if result["success"]:
                return {"response": result["preview"], "success": True}
            return {
                "response": f"❌ {result['error']}",
                "success": False
            }
        except Exception as e:
            return {
                "response": f"❌ Preview error: {e}",
                "success": False
            }
    
    def handle_publish_blog(self, intent):
        """Publish draft to WordPress"""
        try:
            from core.wordpress_publisher import wp_publisher
            draft_name = intent.get("extracted_data", {}).get("topic")
            result = wp_publisher.publish_draft(draft_name, as_draft=False)
            if result["success"]:
                return {"response": result["message"], "success": True}
            return {
                "response": f"❌ Publish failed: {result['error']}",
                "success": False
            }
        except Exception as e:
            return {
                "response": f"❌ Publish error: {e}",
                "success": False
            }
    
    def handle_reject_draft(self, intent):
        """Reject and delete a draft"""
        try:
            from core.wordpress_publisher import wp_publisher
            draft_name = intent.get("extracted_data", {}).get("topic")
            result = wp_publisher.reject_draft(draft_name)
            if result["success"]:
                return {"response": result["message"], "success": True}
            return {
                "response": f"❌ {result['error']}",
                "success": False
            }
        except Exception as e:
            return {
                "response": f"❌ Reject error: {e}",
                "success": False
            }


# ==================== TEST ====================

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    print("🧪 Testing Extended Intent Classifier")
    print("=" * 50)
    
    classifier = ExtendedIntentClassifier()
    
    test_messages = [
        "Store audit karo",
        "Kitne order aaye last month?",
        "Payment gateway chal raha hai?",
        "Health scan karo website ka",
        "Is this safe: our herb cures diabetes",
        "Kitna kamaya is month?",
        "Blog likh about ashwagandha benefits",
        "Social media post bana do",
        "Content status batao",
        "Weekly content generate karo",
        "Morning report do",
        "Aaj ka summary batao",
        "Polish customer dhundho",
        "Kya chal raha hai sab?",
        "Revenue report dikhao",
        "Check this: boosts immunity naturally",
        "ye likh sakte hain kya: cures arthritis",
        "Purane customer ki list do",
        "Hello kaise ho",  # Should NOT match
    ]
    
    for msg in test_messages:
        result = classifier.classify(msg)
        if result:
            print(f"  ✅ \"{msg[:40]}...\"")
            print(f"     → {result['intent']} "
                  f"(confidence: {result['confidence']})")
        else:
            print(f"  ⚪ \"{msg[:40]}...\" → No new intent match")
    
    print(f"\n✅ Classifier test complete!")
