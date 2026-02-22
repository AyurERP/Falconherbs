"""
Falcon Agency — Commander Intent Extensions
New intents for WooCommerce, Health Scanner, 
Content Pipeline, Revenue Tracker.

This file EXTENDS the Commander's intent classification.
Import this in commander.py to add new capabilities.
"""

import re
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
                    r"\bstore\s+health\b",
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
                    r"\bprofit\b",
                    r"\bpaise\b",
                    r"\bmoney\b",
                    r"\brevenue\s+report\b",
                    r"\bdaily\s+report\b",
                    r"\bfinancial\b",
                    r"\bkitna\s+hua\b",
                    r"\btarget\b",
                    r"\bgoal\b",
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
                    r"\bcalendar\b",
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
