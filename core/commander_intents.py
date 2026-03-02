"""
Falcon Agency — Commander Intent Extensions
New intents for WooCommerce, Health Scanner, 
Content Pipeline, Revenue Tracker.

This file EXTENDS the Commander's intent classification.
Import this in commander.py to add new capabilities.
"""

import os
import re
import json
from datetime import datetime

from core.task_verifier import verify_task_result, append_verification_to_response


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
                    r"\bscan\s+karo\b",
                    r"\bsite\s+scan\b",
                    r"\bwebsite\s+scan\b",
                    r"\bfull\s+(?:website|site)\s+scan\b",
                    r"\bpoori\s+website\s+(?:scan|check)\b",
                    r"\bfda\b",
                    r"\bftc\b",
                    r"\bcompliance\b",
                    r"\bhealth\s+claims?\b",
                    r"\bviolation\b",
                    r"\brisk\s+(?:scan|check|report)\b",
                    r"\blegal\s+check\b",
                    r"\bclaims?\s+check\b",
                    r"\bsab\s+jagah\s+(?:scan|check|dhundh)\b",
                    r"\bheader\s+footer\s+(?:bhi\s+)?scan\b",
                    r"\bsab\s+wrong\s+(?:words?|claims?)\s+dhundh\b",
                    r"\bpehle\s+scan\b",
                    r"\bscan\s+pehle\b",
                    r"\bfssai\b",
                ],
                "handler": "handle_health_scan",
                "description": "Full site scan via WooCommerce + WP API — products, blogs, pages, categories, descriptions, titles"
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

            "server_diagnose": {
                "patterns": [
                    r"\bsite\s+down\b",
                    r"\bsite\s+unreachable\b",
                    r"\bserver\s+(?:check|diagnose|status)\b",
                    r"\bwhm\s+(?:check|status)\b",
                    r"\bplugin\s+update\s+crash\b",
                    r"\bapache\s+restart\b",
                    r"\bkya\s+problem\s+hai\s+site\b",
                ],
                "handler": "handle_server_diagnose",
                "description": "Server/site diagnostic — reachability, WHM, common fixes"
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
            
            "send_social_content": {
                "patterns": [
                    r"\baaj\s+ka\s+(?:post|content)\b",
                    r"\baaj\s+ki\s+post\b",
                    r"\bpost\s+bhej\b",
                    r"\bcontent\s+bhej\b",
                    r"\blatest\s+post\b",
                    r"\bsend\s+(?:post|content|social)\b",
                    r"\bpost\s+ready\b",
                    r"\bpost\s+de\b",
                    r"\bpost\s+dedo\b",
                    r"\bsocial\s+content\s+bhej\b",
                    r"\bheropost\s+ke\s+liye\b",
                    r"\bIG\s+post\b",
                    r"\binstagram\s+content\b",
                ],
                "handler": "handle_send_social_content",
                "description": "Send latest social post to WhatsApp in HeroPost-ready format"
            },
            "content_package": {
                "patterns": [
                    r"\bcontent\s+package\b",
                    r"\bhafte\s+ka\s+content\b",
                    r"\bweekly\s+content\s+package\b",
                    r"\bheropost\b.*\bcontent\b",
                    r"\bcontent\s+banao\s+heropost\b",
                    r"\bimages?\s+ke\s+sath\s+content\b",
                ],
                "handler": "handle_content_package",
                "description": "Generate weekly content package (images, captions, video, UPLOAD_GUIDE) for HeroPost"
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
            "email_campaign": {
                "patterns": [
                    r"\bemail\s+campaign\b",
                    r"\bemail\s+banao\b",
                    r"\bemail\s+content\b",
                    r"\bsale\s+ke\s+liye\s+email\b",
                    r"\bnetworksolutions\b.*\bemail\b",
                    r"\bnewsletter\s+content\b",
                ],
                "handler": "handle_email_campaign",
                "description": "Generate email campaign for NetworkSolutions manual send"
            },
            "image_banao": {
                "patterns": [
                    r"\bimage\s+banao\b",
                    r"\bgraphic\s+create\b",
                    r"\bek\s+image\s+banao\b",
                    r"\bimage\s+generate\b",
                    r"\bphoto\s+banao\b",
                ],
                "handler": "handle_image_banao",
                "description": "Generate single image for product/topic"
            },
            "video_banao": {
                "patterns": [
                    r"\bvideo\s+banao\b",
                    r"\breel\s+banao\b",
                    r"\breel\s+create\b",
                    r"\bslideshow\s+video\b",
                    r"\bke\s+liye\s+reel\b",
                ],
                "handler": "handle_video_banao",
                "description": "Generate product reel / slideshow video"
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
                    r"\bbackup\s+(?:verify|check|integrity|theek\s+hai)\b",
                    r"\bbackup\s+theek\s+hai\??\b",
                    r"\bintegrity\s+check\b",
                    r"\bdata\s+(?:safe|check)\b",
                ],
                "handler": "handle_backup_verify",
                "description": "Verify backup integrity"
            },

            # ===== PLUGIN MANAGEMENT (BUILD 2) =====
            "plugin_install": {
                "patterns": [
                    r"\bplugin\s+install\b",
                    r"\binstall\s+plugin\b",
                    r"\bplugin\s+lagao\b",
                    r"\bplugin\s+add\b",
                    r"\brank\s+math\b.*\binstall\b",
                    r"\binstall\s+rank\s+math\b",
                    r"\binstall\s+yoast\b",
                ],
                "handler": "handle_plugin_install",
                "description": "Install plugin (approval gate)"
            },
            "plugin_list": {
                "patterns": [
                    r"\bplugin(?:s)?\s+(?:dikha|list|show|kitne)\b",
                    r"\bplugins?\s+dikhao\b",
                    r"\blist\s+plugin\b",
                    r"\binstalled\s+plugin\b",
                    r"\bkitne\s+plugin\b",
                ],
                "handler": "handle_plugin_list",
                "description": "List installed plugins"
            },
            "plugin_recommend": {
                "patterns": [
                    r"\bspeed\s+improve\b",
                    r"\bsite\s+slow\s+hai\b",
                    r"\bperformance\s+plugin\b",
                    r"\brecommend\s+plugin\b",
                    r"\bplugin\s+recommend\b",
                    r"\bplugin(?:s)?\s+for\s+(?:speed|performance|seo)\b",
                    r"\bkaunse\s+plugin\b",
                ],
                "handler": "handle_plugin_recommend",
                "description": "Recommend plugins for need"
            },
            "plugin_update": {
                "patterns": [
                    r"\bplugin(?:s)?\s+update\b",
                    r"\bupdate\s+plugin(?:s)?\b",
                    r"\bplugins?\s+update\s+karo\b",
                    r"\bplugin\s+upgrade\b",
                ],
                "handler": "handle_plugin_update",
                "description": "Update plugins (backup first)"
            },

            # ===== ADS MONITORING (BUILD 4) =====
            "ads_status": {
                "patterns": [
                    r"\bgoogle\s+ads\s+ka\s+kya\s+haal\b",
                    r"\bgoogle\s+ads\s+(?:status|check|dikhao)\b",
                    r"\bads\s+(?:status|kaisa|kya\s+haal)\b",
                    r"\bmeta\s+ads\s+(?:status|check)\b",
                    r"\bfacebook\s+ads\s+status\b",
                ],
                "handler": "handle_ads_status",
                "description": "Google/Meta Ads status (honest not_configured if no API)"
            },
            "ads_report": {
                "patterns": [
                    r"\bads\s+report\b",
                    r"\bads\s+report\s+banao\b",
                    r"\bads\s+summary\b",
                ],
                "handler": "handle_ads_report",
                "description": "Generate ads report for WhatsApp"
            },
            "ads_pause": {
                "patterns": [
                    r"\bcampaign\s+pause\s+karo\b",
                    r"\bcampaign\s+pause\b",
                    r"\bads\s+campaign\s+pause\b",
                ],
                "handler": "handle_ads_pause",
                "description": "Pause campaign (approval gate)"
            },
            
            "image_generate": {
                "patterns": [
                    r"\bimage\s+(?:generate|bana|create|make)\b",
                    r"\bphoto\s+(?:bana|khinch|click)\b",
                    r"\bdesign\s+(?:karo|banao)\b",
                    r"\bdesign\s+[a-z]",
                    r"\bpicture\s+(?:search|find|bana)\b",
                ],
                "handler": "handle_image_generate",
                "description": "Generate an AI image"
            },

            "ad_creative": {
                "patterns": [
                    r"\bad\s+(?:creative|design|bana|karo)\b",
                    r"\bmeta\s+(?:ad|creative)\b",
                    r"\bgoogle\s+(?:ad|display)\b",
                    r"\bfacebook\s+ad\b",
                    r"\binstagram\s+ad\b",
                    r"\bcampaign\s+(?:creative|visual)\b",
                ],
                "handler": "handle_ad_creative",
                "description": "Generate Meta/Google ad creative"
            },

            "blog_banner": {
                "patterns": [
                    r"\bblog\s+(?:banner|image|featured)\b",
                    r"\bbanner\s+(?:bana|create|generate)\b",
                    r"\bfeatured\s+image\b",
                ],
                "handler": "handle_blog_banner",
                "description": "Generate blog featured image"
            },

            "carousel_design": {
                "patterns": [
                    r"\bcarousel\b",
                    r"\bslide\s+(?:design|bana)\b",
                    r"\bmulti\s+slide\b",
                ],
                "handler": "handle_carousel_design",
                "description": "Generate carousel slides"
            },

            "brand_guidelines": {
                "patterns": [
                    r"\bbrand\s+(?:guidelines|guide|kit)\b",
                    r"\bbranding\b",
                    r"\bdesign\s+system\b",
                ],
                "handler": "handle_brand_guidelines",
                "description": "Show brand guidelines"
            },

            "analytics_traffic": {
                "patterns": [
                    r"\banalytics\b",
                    r"\bga4\b",
                    r"\btraffic\s+(?:report|check|dikhao|dekho)\b",
                    r"\btraffic\s+dekho\b",
                    r"\bwebsite\s+traffic\b",
                    r"\bkitne\s+visitors?\b",
                    r"\busers?\s+(?:count|kitne)\b",
                    r"\bpageviews?\b",
                ],
                "handler": "handle_analytics_traffic",
                "description": "GA4 traffic report"
            },

            "ads_status": {
                "patterns": [
                    r"\bads?\s+(?:status|report|check|check\s+karo)\b",
                    r"\bads?\s+check\s+karo\b",
                    r"\bmeta\s+ads?\b",
                    r"\bgoogle\s+ads?\b",
                    r"\bpaid\s+(?:ads?|campaign)\b",
                    r"\bfacebook\s+ads?\s+status\b",
                ],
                "handler": "handle_ads_status",
                "description": "Paid ads status"
            },

            "video_script": {
                "patterns": [
                    r"\b(?:reel|video|short)\s+(?:script|bana|create)\b",
                    r"\bscript\s+(?:for|of)\s+(?:reel|video|short)\b",
                    r"\binstagram\s+reel\b",
                    r"\byoutube\s+short\b",
                ],
                "handler": "handle_video_script",
                "description": "Generate reel/video script"
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

            "share_draft_text": {
                "patterns": [
                    r"\bdraft.*(?:txt|text|yahan|here|share|bhej|send|copy)\b",
                    r"\b(?:share|send|bhej).*draft\b",
                    r"\bdraft.*(?:content|poora|full|read)\b",
                    r"\b(?:full|poora)\s+draft\b",
                    r"\bdraft\s+(?:padh|read|yahan\s+bhej|here)\b",
                    r"\bshow.*full.*draft\b",
                    r"\bdraft.*(?:mein|main)\s+(?:dikhao|bhej)\b",
                ],
                "handler": "handle_share_draft_text",
                "description": "Share full blog draft content as WhatsApp text"
            },
            
            "publish_blog": {
                "patterns": [
                    r"\bpublish\s+(?:karo|blog|post|draft|it|this)\b",
                    r"\bblog\s+publish\b",
                    r"\bpost\s+(?:karo|publish|daal)\b",
                    r"\bwordpress\s+(?:pe|par|publish|post)\b",
                    r"\bwp\s+(?:publish|post)\b",
                    r"\bdaal\s+(?:do|de)\s+(?:blog|post|website)\b",
                    r"\bpublish\s+live\s+karo\b",
                    r"\blive\s+publish\b",
                    r"\bpublish\s+live\b",
                    r"\blive\s+karo\b",
                    r"\bmake\s+(?:it\s+)?live\b",
                    r"\bgo\s+live\b",
                    r"\bsite\s+pe\s+(?:daal|publish|live)\b",
                    r"\bwebsite\s+(?:pe|par)\s+(?:daal|publish)\b",
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
            
            # ===== CONTENT WORKFLOW (Phase 2) =====
            "content_queue": {
                "patterns": [
                    r"\bdrafts?\s+dikhao\b",
                    r"\bcontent\s+queue\b",
                    r"\bqueue\s+status\b",
                    r"\bdrafts?\s+show\b",
                    r"\bqueue\s+dikhao\b",
                    r"\bpending\s+queue\b",
                ],
                "handler": "handle_content_queue",
                "description": "Show content queue status"
            },
            
            "retry_drafts": {
                "patterns": [
                    r"\bretry\s+drafts?\b",
                    r"\bdrafts?\s+fix\b",
                    r"\bregenerate\s+content\b",
                    r"\bretry\s+content\b",
                    r"\bfix\s+drafts?\b",
                ],
                "handler": "handle_retry_drafts",
                "description": "Retry failed prompt-only drafts"
            },
            
            # ===== UTILS & ENHANCEMENTS =====
            "help": {
                "patterns": [
                    r"\bhelp\b",
                    r"\bcommands?\b",
                    r"\bhelp\s+me\b",
                    r"\bguide\b",
                    r"\bmenu\b",
                    r"\bsab\s+commands\b",
                ],
                "handler": "handle_help",
                "description": "Show all available commands"
            },
            "capabilities": {
                "patterns": [
                    r"\bkya\s+kar\s+sakte\b",
                    r"\bkya\s+karsakte\b",
                    r"\bcapabilities\b",
                    r"\bscope\s+kya\s+hai\b",
                    r"\bwhat\s+can\s+you\s+do\b",
                    r"\bmera\s+scope\b",
                ],
                "handler": "handle_capabilities",
                "description": "Show in-scope vs out-of-scope capabilities"
            },
            
            "bulk_title_fix": {
                "patterns": [
                    r"\bfix\s+(?:all\s+)?titles\b",
                    r"\btitle\s+fix\b",
                    r"\btitle\s+compliance\b",
                    r"\bfix\s+product\s+names\b",
                ],
                "handler": "handle_bulk_title_fix",
                "description": "Scan and fix all risky product titles"
            },

            # ===== HEALTH REWRITER (Phase 3) =====
            "scan_products": {
                "patterns": [
                    r"\bscan\s+(?:all\s+)?products?\b",
                    r"\bproduct(?:s)?\s+scan\b",
                    r"\bproduct(?:s)?\s+(?:compliance|safety)\s+(?:scan|check)\b",
                    r"\bcheck\s+(?:all\s+)?product(?:s)?\s+(?:description|content)\b",
                    r"\bproduct\s+health\s+(?:scan|check)\b",
                    r"\bwoocommerce\s+scan\b",
                    r"\bproduct\s+violations?\b",
                    r"\bscan\s+descriptions?\b",
                ],
                "handler": "handle_scan_products",
                "description": "Scan WooCommerce products for health claim violations"
            },

            "rewrite_products": {
                "patterns": [
                    r"\brewrite\s+(?:flagged\s+)?products?\b",
                    r"\bproduct(?:s)?\s+rewrite\b",
                    r"\bai\s+rewrite\s+products?\b",
                    r"\bgenerate\s+rewrites?\b",
                    r"\bfix\s+(?:product\s+)?descriptions?\b",
                    r"\bcreate\s+rewrites?\b",
                    r"\bdescription\s+rewrite\b",
                ],
                "handler": "handle_rewrite_products",
                "description": "AI-rewrite flagged product descriptions (saves for approval)"
            },

            "apply_rewrite": {
                "patterns": [
                    r"\bapply\s+rewrite\b",
                    r"\brewrite\s+apply\b",
                    r"\bapply\s+product\s+(?:fix|update)\b",
                    r"\bpush\s+rewrite\b",
                    r"\bupdate\s+product\s+description\b",
                    r"\bapply\s+(?:product\s+)?(\d+)\b",
                ],
                "handler": "handle_apply_rewrite",
                "description": "Apply approved product rewrite to WooCommerce"
            },

            "push_all_rewrites": {
                "patterns": [
                    r"\bpush\s+karo\b",
                    r"\bpush\s+rewrites?\b",
                    r"\bapply\s+rewrites?\b",
                    r"\brewrite\s+apply\b",
                    r"\bproduct\s+(?:push|apply)\b",
                ],
                "handler": "handle_push_all_rewrites",
                "description": "Apply all pending product rewrites to WooCommerce"
            },

            "push_all_fixes": {
                "patterns": [
                    r"\bfix\s+all\b",
                    r"\bfix\s+sab\b",
                    r"\ball\s+fix\b",
                    r"\b125\s+fix\b",
                    r"\bpura\s+fix\b",
                    r"\bsab\s+theek\s+karo\b",
                    r"\bcompliance\s+fix\b",
                    r"\bhealth\s+claims?\s+fix\b",
                    r"\bviolations?\s+fix\b",
                    r"\brewrite\s+sab\b",
                    r"\bsab\s+rewrite\b",
                    r"\bapply\s+all\s+fixes\b",
                ],
                "handler": "handle_push_all_fixes",
                "description": "Apply ALL fixes: products + blogs + pages + categories"
            },

            "rewrite_pages": {
                "patterns": [
                    r"\brewrite\s+pages?\b",
                    r"\bpage(?:s)?\s+rewrite\b",
                    r"\bfix\s+pages?\b",
                ],
                "handler": "handle_rewrite_pages",
                "description": "AI-rewrite flagged page titles"
            },

            "push_blog_fixes": {
                "patterns": [
                    r"\bpush\s+blogs?\b",
                    r"\bapply\s+blog\s+fixes?\b",
                    r"\bblog\s+(?:fix|fixes?)\s*(?:karo|push|apply|laga)?\b",
                    r"\bblogs?\s+fix\s+karo\b",
                    r"\bblogs?\s+(?:push|apply)\b",
                ],
                "handler": "handle_push_blog_fixes",
                "description": "Apply all pending blog title rewrites"
            },

            "push_page_fixes": {
                "patterns": [
                    r"\bpush\s+pages?\b",
                    r"\bapply\s+page\s+fixes?\b",
                    r"\bpage\s+(?:fix|fixes?)\s*(?:karo|push|apply|laga)?\b",
                    r"\bpages?\s+fix\s+karo\b",
                    r"\bpages?\s+(?:push|apply)\b",
                ],
                "handler": "handle_push_page_fixes",
                "description": "Apply all pending page title rewrites"
            },

            "changelog_report": {
                "patterns": [
                    r"\bchangelog\b",
                    r"\blast\s+(?:changelog|report)\b",
                    r"\bbefore\s+after\b",
                    r"\bchanges?\s+report\b",
                    r"\bchangelog\s+(?:dikhao|send|bhejo)\b",
                ],
                "handler": "handle_changelog_report",
                "description": "Send last changelog/report file"
            },

            "rewrite_status": {
                "patterns": [
                    r"\brewrite(?:s)?\s+(?:status|pending|dikhao|show|list)\b",
                    r"\bpending\s+rewrites?\b",
                    r"\bproduct\s+rewrite\s+status\b",
                    r"\bkitne\s+rewrites?\b",
                    r"\brewrite\s+queue\b",
                ],
                "handler": "handle_rewrite_status",
                "description": "Show status of pending product rewrites"
            },
            
            "disclaimer_injection": {
                "patterns": [
                    r"\badd\s+disclaimer\b",
                    r"\binject\s+disclaimer\b",
                    r"\bdisclaimer\s+(?:daal|lagao|add)\b",
                    r"\bfda\s+disclaimer\b",
                ],
                "handler": "handle_disclaimer_injection",
                "description": "Add FDA disclaimer to all products"
            },

            "scan_blog_posts": {
                "patterns": [
                    r"\bscan\s+(?:all\s+)?blog(?:s|[\s_]posts?)?\b",
                    r"\bblog\s+(?:scan|check|audit)\b",
                    r"\bblog\s+(?:compliance|violations?|health)\b",
                    r"\bcheck\s+blog\s+posts?\b",
                    r"\bblog\s+posts?\s+(?:scan|check)\b",
                ],
                "handler": "handle_scan_blog_posts",
                "description": "Scan blog posts for health claim violations"
            },

            "rewrite_blogs": {
                "patterns": [
                    r"\brewrite\s+(?:flagged\s+)?blogs?\b",
                    r"\bblog\s+rewrite\b",
                    r"\bfix\s+blog\s+(?:titles?|posts?)\b",
                    r"\bblog\s+title\s+fix\b",
                ],
                "handler": "handle_rewrite_blogs",
                "description": "AI-rewrite flagged blog post titles (saves for approval)"
            },

            "scan_pages": {
                "patterns": [
                    r"\bscan\s+(?:wp\s+)?pages?\b",
                    r"\bpage\s+(?:scan|check|audit)\b",
                    r"\bcheck\s+pages?\s+(?:compliance|violations?|content)\b",
                    r"\bwp\s+pages?\s+scan\b",
                ],
                "handler": "handle_scan_pages",
                "description": "Scan WordPress pages for health claim violations"
            },

            "rename_categories": {
                "patterns": [
                    r"\brename\s+categor(?:y|ies)\b",
                    r"\bcategor(?:y|ies)\s+rename\b",
                    r"\bfix\s+categor(?:y|ies)\b",
                    r"\bcategor(?:y|ies)\s+(?:compliance|violations?|fix)\b",
                    r"\bscan\s+categor(?:y|ies)\b",
                    r"\bcategor(?:y|ies)\s+(?:scan|check)\b",
                    # Hindi
                    r"\bcategory\s+(?:fix|theek|badlo|rename)\s+kar(?:o|en)?\b",
                ],
                "handler": "handle_rename_categories",
                "description": "Scan and rename risky WooCommerce category names"
            },

            "inventory_status": {
                "patterns": [
                    r"\binventory\s+(?:status|report|check)\b",
                    r"\bstock\s+(?:status|report|levels)\b",
                    r"\bburn\s+rate\b",
                    r"\bkitna\s+stock\b",
                    r"\bstock\s+kab\s+khatam\b",
                    r"\bstockout\b",
                    r"\bprediction\s+inventory\b",
                ],
                "handler": "handle_inventory_status",
                "description": "Inventory burn rate and stockout prediction"
            },
            
            "sentry_check": {
                "patterns": [
                    r"\bcheck\s+(this\s+)?comment\b",
                    r"\bscan\s+comment\b",
                    r"\bsentry\b",
                    r"\bis\s+this\s+(comment\s+)?(safe|risky|okay|compliant)\b",
                    r"\bcompliance\s+check\b",
                    r"\bcomment\s+(check|scan|review)\b",
                    # Hindi/Hinglish
                    r"\bcomment\s+check\s+kar(o)?\b",
                    r"\bye\s+safe\s+hai\b",
                ],
                "handler": "handle_sentry_check",
                "description": "Analyze a social media comment for compliance risks"
            },
            
            "pr_outreach": {
                "patterns": [
                    r"\bfind\s+(?:influencers|creators)\s+for\s+(.+)\b",
                    r"\binfluencer\s+search\s+(.+)\b",
                    r"\bfind\s+creators\s+for\s+(.+)\b",
                    r"\bpr\s+outreach\s+(.+)\b",
                ],
                "handler": "handle_pr_outreach",
                "description": "Search for YouTube influencers for PR outreach"
            },

            # ===== AEO — BRAND MONITORING =====
            "aeo_scan": {
                "patterns": [
                    r"\baeo\s+(?:scan|check|run|karo)\b",
                    r"\bbrand\s+(?:scan|monitor|check)\b",
                    r"\bai\s+(?:visibility|monitoring|check)\b",
                    r"\bchatgpt\s+(?:mention|check|scan)\b",
                    r"\bperplexity\s+(?:check|scan|mention)\b",
                    r"\bfind\s+us\s+in\s+ai\b",
                    r"\bai\s+mein\s+(?:check|dhundh|scan)\b",
                    r"\bkya\s+(?:chatgpt|ai)\s+(?:mention|bolte)\b",
                ],
                "handler": "handle_aeo_scan",
                "description": "Run monthly AEO brand visibility scan"
            },

            "aeo_report": {
                "patterns": [
                    r"\baeo\s+(?:report|status|dikhao|show)\b",
                    r"\bbrand\s+(?:visibility|report|score)\b",
                    r"\bai\s+(?:report|status|score)\b",
                    r"\bai\s+visibility\s+report\b",
                    r"\bkitna\s+aata\s+hai\s+ai\s+mein\b",
                    r"\bcontent\s+gaps?\b",
                ],
                "handler": "handle_aeo_report",
                "description": "Show latest AEO brand monitoring report"
            },

            "agent_performance": {
                "patterns": [
                    r"\bagent\s+(?:performance|report|status)\b",
                    r"\bkaun\s+kitna\s+kaam\s+kar\s+raha\b",
                    r"\bperformance\s+report\b",
                    r"\btransparency\s+report\b",
                    r"\bsab\s+agents?\s+(?:ka\s+)?report\b",
                    r"\bwho\s+(?:is\s+)?(?:working|idle)\b",
                    r"\bteam\s+performance\b",
                    r"\bagent\s+report\b",
                ],
                "handler": "handle_agent_performance",
                "description": "Agent performance — who's busy, who's idle"
            },

            "director_complaint": {
                "patterns": [
                    r"\bdirector\s*[,:]?\s*(?:complaint|problem|issue|fix\s+nahi)\b",
                    r"\bcomplaint\s+(?:to\s+)?director\b",
                    r"\bdirector\s+ko\s+(?:batao|report|complaint)\b",
                    r"\b(?:agent|team)\s+ne\s+(?:y|kuch)\s+nahi\s+kiya\b",
                    r"\bproblem\s+hai\s+director\b",
                    r"\bdirector\s+issue\b",
                ],
                "handler": "handle_director_complaint",
                "description": "Report problem/complaint to Director"
            },

            # ===== COMPETITOR PRICING =====
            "price_scan": {
                "patterns": [
                    r"\bprice\s+(?:scan|check|compare|karo)\b",
                    r"\bcompetitor\s+(?:price|pricing)\b",
                    r"\bpricing\s+(?:scan|check|report)\b",
                    r"\bpatanjali\s+price\b",
                    r"\bhimalaya\s+price\b",
                    r"\bkitna\s+(?:price|charge)\s+kar\b",
                    r"\bprice\s+(?:tracking|tracker)\b",
                    r"\bmarket\s+price\b",
                ],
                "handler": "handle_price_scan",
                "description": "Run competitor price scan on Amazon India"
            },

            "price_report": {
                "patterns": [
                    r"\bprice\s+(?:report|status|dikhao|show)\b",
                    r"\bpricing\s+(?:report|status)\b",
                    r"\bcompetitor\s+(?:report|comparison)\b",
                    r"\bkitne\s+mein\s+bech\s+rahe\b",
                    r"\bham(?:ara)?\s+price\s+(?:sahi|theek|ok)\b",
                ],
                "handler": "handle_price_report",
                "description": "Show latest competitor pricing report"
            },

            "price_update": {
                "patterns": [
                    r"\bset\s+(?:competitor\s+)?price\b",
                    r"\bupdate\s+(?:competitor\s+)?price\b",
                    r"\bmanual\s+price\b",
                    r"\bprice\s+set\s+karo\b",
                ],
                "handler": "handle_price_update",
                "description": "Manually update a competitor price"
            },
            "keyword_analysis": {
                "patterns": [
                    r"\bkeyword\s*(?:analysis|check|report|dekho|dikhao)\b",
                    r"\bkeywords?\s+kya\s+hain\b",
                    r"\bseo\s+keywords?\b",
                    r"\brank\s+check\b",
                    r"\bkaunse\s+keywords?\b",
                    r"\bkeyword\s+analysis\b",
                ],
                "handler": "handle_analyse_keywords",
                "description": "Keyword analysis and rank check",
            },
        }
        self.intents["director_complaint"] = {
            "patterns": [
                r"\b(director|you|tum)\s+(are\s+)?(useless|dumb|stupid|idiot|pagal|not\s+working|failing|bekaar|slow)\b",
                r"\b(complaint|complain|feedback)\s+(about\s+)?(director|you)\b",
                r"\b(fix\s+yourself|do\s+better|work\s+properly)\b",
                r"\bwake\s+up\s+director\b",
                r"\byou\s+are\s+(a\s+)?disappointment\b",
            ],
            "handler": "handle_director_complaint",
            "description": "Handle owner complaints about the Director",
        }

        self.intents["show_staging_file"] = {
            "patterns": [r"^show\s+file\s+(.+)$"],
            "handler": "handle_show_staging_file",
            "description": "Show long staging file from content delivery"
        }
        self.intents["show_rewrite"] = {
            "patterns": [r"^show\s+rewrite\s+(\d+)$"],
            "handler": "handle_show_rewrite",
            "description": "Show pending rewrite for a product"
        }
        self.intents["approve_rewrite"] = {
            "patterns": [r"^approve\s+product\s+(\d+)$"],
            "handler": "handle_approve_rewrite",
            "description": "Approve product rewrite"
        }
        self.intents["approve_all_rewrites"] = {
            "patterns": [r"^approve\s+all(?:\s+rewrites)?$", r"^apply\s+all(?:\s+rewrites)?$"],
            "handler": "handle_approve_all_rewrites",
            "description": "Approve all product rewrites"
        }
        self.intents["reject_rewrite"] = {
            "patterns": [r"^reject\s+product\s+(\d+)$"],
            "handler": "handle_reject_rewrite",
            "description": "Reject product rewrite"
        }
        self.intents["rewrite_status"] = {
            "patterns": [
                r"^rewrite\s+status$",
                r"^show\s+pending\s+rewrites$"
            ],
            "handler": "handle_rewrite_status",
            "description": "Show rewrite staging status"
        }
        self.intents["fix_violations"] = {
            "patterns": [r"^fix\s+violations$", r"^sab\s+fix\s+karo$", r"\bsab\s+fix\b", r"\bfix\s+karo\b", r"^apply\s+batch$"],
            "handler": "handle_fix_violations",
            "description": "Fix health violations with clarification flow"
        }
        self.intents["fix_violations_batch"] = {
            "patterns": [r"^fix\s+violations\s+batch\s+(\d+)$"],
            "handler": "handle_fix_violations_batch",
            "description": "Fix health violations in batch"
        }

        # ── STORE INTELLIGENCE ────────────────────────────────────────────────
        self.intents["low_stock_alert"] = {
            "patterns": [
                r"\bstock\s+(?:check|karo|dekho|alert|kam)\b",
                r"\bkam\s+stock\b",
                r"\bout\s+of\s+stock\b",
                r"\binventory\s+(?:check|low|alert)\b",
                r"\bstock\s+(?:khatam|low|warning)\b",
                r"\bkaunse\s+products?\s+(?:khatam|low)\b",
            ],
            "handler": "handle_low_stock_alert",
            "description": "Check products with low/out-of-stock inventory"
        }
        self.intents["refund_check"] = {
            "patterns": [
                r"\brefund\b",
                r"\bcancell?ed?\s+orders?\b",
                r"\bwapas\s+(?:aaye|hua|orders?)\b",
                r"\breturn\s+(?:check|orders?|dikhao)\b",
                r"\bfailed\s+orders?\b",
                r"\brefund\s+(?:kitne|check|status)\b",
            ],
            "handler": "handle_refund_check",
            "description": "Check recent refunds, cancellations and failed orders"
        }
        self.intents["product_performance"] = {
            "patterns": [
                r"\bbest\s+seller\b",
                r"\btop\s+products?\b",
                r"\bkaunsa\s+product\s+(?:best|zyada|top)\b",
                r"\bproduct\s+performance\b",
                r"\bsabse\s+zyada\s+(?:bika|bikne|sell)\b",
                r"\bselling\s+report\b",
                r"\bsales\s+(?:top|best|report|breakdown)\b",
            ],
            "handler": "handle_product_performance",
            "description": "Top selling products this month by revenue"
        }
        self.intents["customer_segments"] = {
            "patterns": [
                r"\bcustomer\s+(?:report|analysis|segments?|kaun)\b",
                r"\bbuyers?\s+(?:report|kaun|analysis)\b",
                r"\bkitne\s+customers?\b",
                r"\bnaye\s+vs\s+purane\s+customers?\b",
                r"\bcustomer\s+breakdown\b",
                r"\bwho\s+(?:are\s+)?(?:my\s+)?customers?\b",
            ],
            "handler": "handle_customer_segments",
            "description": "Customer breakdown: new vs returning, top cities, avg order value"
        }
        self.intents["growth_report"] = {
            "patterns": [
                r"\bgrowth\s+report\b",
                r"\bis\s+mahine\s+ki\s+growth\b",
                r"\bmonth\s+(?:over|vs|comparison)\b",
                r"\bpichle\s+mahine\s+(?:se|vs|compare)\b",
                r"\bmonthly\s+growth\b",
                r"\bgrowth\s+(?:kya|kaisi|dikhao)\b",
                r"\bmom\s+growth\b",
            ],
            "handler": "handle_growth_report",
            "description": "Month-over-month growth: orders, revenue, customers"
        }
        self.intents["gst_report"] = {
            "patterns": [
                r"\bgst\s+(?:report|calculate|nikalo|kya|kitna)\b",
                r"\btax\s+report\b",
                r"\bcgst|sgst|igst\b",
                r"\bkitna\s+(?:gst|tax)\b",
                r"\bgstin\s+report\b",
                r"\btax\s+(?:calculation|breakdown|monthly)\b",
            ],
            "handler": "handle_gst_report",
            "description": "Monthly GST breakdown from WooCommerce orders (CGST/SGST/IGST)"
        }

        # ── CONTENT & MARKETING ───────────────────────────────────────────────
        self.intents["festival_campaign"] = {
            "patterns": [
                r"\b(?:holi|diwali|navratri|eid|christmas|new year|independence|republic|raksha)\b.*(?:campaign|post|content)\b",
                r"\bfestival\s+(?:campaign|content|post|plan)\b",
                r"\b(?:campaign|content)\s+(?:for\s+)?(?:holi|diwali|navratri|eid)\b",
                r"\bt[yY]ohar\s+(?:campaign|content|post)\b",
                r"\bfestive\s+(?:campaign|content|season)\b",
                r"\bfestival\s+(?:wala|ke\s+liye)\s+content\b",
            ],
            "handler": "handle_festival_campaign",
            "description": "Create festival-specific marketing campaign (Holi, Diwali, Navratri, etc.)"
        }
        self.intents["season_strategy"] = {
            "patterns": [
                r"\bseason\s+(?:strategy|plan|content)\b",
                r"\bis\s+mahine\s+ki\s+strategy\b",
                r"\bmonthly\s+strategy\b",
                r"\b(?:summer|winter|monsoon|spring)\s+(?:strategy|plan|content)\b",
                r"\bseasonal\s+(?:plan|strategy|marketing)\b",
                r"\bkya\s+sell\s+karna\s+chahiye\b",
                r"\bkis\s+cheez\s+ka\s+focus\b",
            ],
            "handler": "handle_season_strategy",
            "description": "Monthly ayurvedic season strategy and product focus plan"
        }
        self.intents["product_faq"] = {
            "patterns": [
                r"\bfaq\s+(?:banao|generate|likho|create)\b",
                r"\bsawaal\s+jawab\s+(?:banao|likho)\b",
                r"\bproduct\s+(?:ke\s+liye\s+)?(?:faq|questions?|sawaal)\b",
                r"\bcommon\s+questions?\s+(?:banao|for)\b",
                r"\bfaq\s+(?:for|ke\s+liye)\b",
                r"\bq&a\s+(?:banao|generate)\b",
            ],
            "handler": "handle_product_faq",
            "description": "Generate FAQ Q&A pairs for a product page (SEO + AEO boost)"
        }
        self.intents["trending_topics"] = {
            "patterns": [
                r"\btrend(?:ing)?\s+(?:topics?|kya|search|ayurveda)\b",
                r"\baaj\s+kya\s+trending\b",
                r"\bkya\s+trending\s+(?:hai|hain)\b",
                r"\bpopular\s+(?:topics?|searches?|keywords?)\s+(?:aaj|this\s+week|abhi)\b",
                r"\bviral\s+(?:topics?|content)\b",
                r"\btrending\s+(?:in\s+)?(?:ayurveda|india|herbs?)\b",
            ],
            "handler": "handle_trending_topics",
            "description": "Get trending ayurvedic and wellness topics this week via DuckDuckGo"
        }
        self.intents["content_repurpose"] = {
            "patterns": [
                r"\brepurpose\b",
                r"\bblog\s+(?:se|ko)\s+(?:social|post|caption|tweet)\b",
                r"\bcontent\s+(?:se\s+aur|repurpose|convert)\b",
                r"\b(?:blog|article)\s+(?:ko\s+)?(?:instagram|facebook|tweet|caption)\s+(?:mein|banao|convert)\b",
                r"\bek\s+content\s+se\s+(?:bahut|multiple|alag)\b",
                r"\bconvert\s+(?:blog|content|article)\b",
            ],
            "handler": "handle_content_repurpose",
            "description": "Repurpose a blog post into Instagram caption, FAQ, meta description"
        }
        self.intents["heropost_week"] = {
            "patterns": [
                r"\bheropost\s+(?:week|weekly|plan|schedule)\b",
                r"\b(?:week|hafte)\s+(?:ka|ke|ki)\s+(?:heropost|7\s+posts?|saat\s+posts?)\b",
                r"\b7\s+posts?\s+(?:banao|ready|plan|chahiye)\b",
                r"\bsaat\s+posts?\s+(?:banao|plan|ready)\b",
                r"\b7\s+din\s+(?:ka|ke)\s+(?:post|social)\s+(?:plan|content|schedule)\b",
                r"\bpura\s+hafte\s+(?:ka|ke)\s+(?:post|content|social)\b",
                r"\bweekly\s+social\s+(?:plan|schedule|content)\b",
            ],
            "handler": "handle_heropost_week",
            "description": "Generate 7-day content plan with all posts ready for HeroPost"
        }
        self.intents["whatsapp_broadcast_draft"] = {
            "patterns": [
                r"\bbroadcast\s+(?:message|bhejo|banao|draft)\b",
                r"\bbulk\s+(?:message|whatsapp|sms)\b",
                r"\bsab\s+customers?\s+ko\s+(?:message|bhejo|inform)\b",
                r"\bwhatsapp\s+(?:blast|broadcast|bulk)\b",
                r"\bpromotion(?:al)?\s+message\s+(?:banao|draft)\b",
                r"\bcustomers?\s+ko\s+(?:inform|message|notify)\s+karo\b",
            ],
            "handler": "handle_whatsapp_broadcast_draft",
            "description": "Draft a WhatsApp broadcast/bulk promotional message"
        }
        self.intents["testimonial_campaign"] = {
            "patterns": [
                r"\btestimonial\b",
                r"\breviews?\s+(?:maango|collect|campaign|lao)\b",
                r"\bfeedback\s+(?:maango|collect|campaign)\b",
                r"\bcustomers?\s+se\s+reviews?\s+(?:maango|lao)\b",
                r"\brating\s+(?:maango|campaign)\b",
                r"\breview\s+(?:collection|request|campaign)\b",
            ],
            "handler": "handle_testimonial_campaign",
            "description": "Generate review collection campaign (email/WhatsApp templates)"
        }

        # ── INFRASTRUCTURE / NETWORKSOLUTIONS ────────────────────────────────
        self.intents["ssl_check"] = {
            "patterns": [
                r"\bssl\s+(?:check|karo|status|expiry|certificate)\b",
                r"\bcertificate\s+(?:check|expiry|valid)\b",
                r"\bhttps?\s+(?:check|valid|secure)\b",
                r"\bssl\s+(?:kab\s+expire|kitne\s+din)\b",
            ],
            "handler": "handle_ssl_check",
            "description": "Check SSL certificate expiry for the website"
        }
        self.intents["domain_health"] = {
            "patterns": [
                r"\bdomain\s+(?:check|health|status|expiry|karo)\b",
                r"\bwebsite\s+domain\b",
                r"\bdns\s+(?:check|status)\b",
                r"\bdomain\s+(?:kab\s+expire|kitne\s+din|valid)\b",
                r"\bblacklist\s+check\b",
            ],
            "handler": "handle_domain_health",
            "description": "Check domain expiry, DNS resolution, blacklist status"
        }
        self.intents["email_inbox_check"] = {
            "patterns": [
                r"\bemail(?:s)?\s+(?:check|dekho|inbox|dikhao|padho)\b",
                r"\binbox\s+(?:check|dikhao|kya\s+hai)\b",
                r"\bnaye\s+emails?\b",
                r"\bcustomer\s+emails?\s+(?:check|dikhao|kya)\b",
                r"\bemail\s+(?:kya\s+aaya|aaye|received)\b",
                r"\bnetworksolutions?\s+email\b",
            ],
            "handler": "handle_email_inbox_check",
            "description": "Check NetworkSolutions business email inbox for new messages"
        }
        self.intents["email_blast"] = {
            "patterns": [
                r"\bemail\s+(?:blast|campaign\s+bhejo|bulk|send|bhejo)\b",
                r"\bcustomers?\s+ko\s+email\s+(?:bhejo|send|karo)\b",
                r"\bemail\s+(?:newsletter|promotion|announcement)\s+(?:bhejo|send)\b",
                r"\bnetworksolutions?\s+email\s+(?:send|campaign|blast)\b",
                r"\bbulk\s+email\b",
            ],
            "handler": "handle_email_blast",
            "description": "Compose and send bulk email to customers via NetworkSolutions"
        }

        # ── MULTI-SITE MANAGEMENT ─────────────────────────────────────────────
        self.intents["list_sites"] = {
            "patterns": [
                r"\bsites?\s+(?:dikhao|list|kitne|show|batao)\b",
                r"\bkaun\s+(?:se|si)\s+websites?\s+(?:hain|manage)\b",
                r"\bmanaged?\s+(?:sites?|websites?)\b",
                r"\bwebsites?\s+(?:list|dikhao|kitni)\b",
                r"\bkitne\s+(?:sites?|websites?)\b",
            ],
            "handler": "handle_list_sites",
            "description": "List all websites managed by the agency"
        }
        self.intents["switch_site"] = {
            "patterns": [
                r"\bswitch\s+(?:to\s+)?site\b",
                r"\bsite\s+(?:switch|badlo|change)\b",
                r"\b(?:go\s+to|use|select)\s+site\s+\d+\b",
                r"\bsite\s+\d+\s+(?:pe|par|select|use)\b",
                r"\bdusra\s+(?:site|website)\s+(?:use|select|switch)\b",
                r"\bchange\s+(?:active\s+)?site\b",
            ],
            "handler": "handle_switch_site",
            "description": "Switch the active website the agency operates on"
        }
        self.intents["add_site"] = {
            "patterns": [
                r"\bnaya\s+(?:site|website)\s+(?:add|jodo|register)\b",
                r"\badd\s+(?:a\s+)?(?:new\s+)?(?:site|website)\b",
                r"\bnew\s+(?:site|website)\s+(?:add|register|setup)\b",
                r"\bdusri\s+website\s+(?:add|jodo)\b",
                r"\bregister\s+(?:new\s+)?site\b",
                r"\bsite\s+add\s+karo\b",
            ],
            "handler": "handle_add_site",
            "description": "Add a new website to agency management"
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

        elif intent == "image_generate":
            # Extract design/image description from message
            patterns = [
                r"(?:image|photo|design|picture)\s+(?:generate|bana|create|make)\s+(.+?)$",
                r"(?:design|banao|karo)\s+(.+?)$",
                r"(?:about|for|on|par)\s+[\"']?(.+?)[\"']?\s*$",
                r"social\s+post\s+(?:about|for)\s+(.+?)$",
            ]
            for p in patterns:
                match = re.search(p, message, re.IGNORECASE)
                if match:
                    data["query"] = match.group(1).strip()
                    break
            if not data.get("query"):
                # Fallback: everything after first command word
                stripped = re.sub(
                    r"^(image|photo|design|picture)\s+(?:generate|bana|create|make)\s*",
                    "", message, flags=re.IGNORECASE
                ).strip()
                if len(stripped) > 3:
                    data["query"] = stripped

        elif intent == "ad_creative":
            for p in [
                r"(?:ad|creative)\s+(?:for|about)\s+[\"']?(.+?)[\"']?\s*$",
                r"(?:meta|google|facebook)\s+ad\s+(.+?)$",
            ]:
                m = re.search(p, message, re.IGNORECASE)
                if m and len(m.group(1).strip()) > 2:
                    data["query"] = m.group(1).strip()
                    break
        elif intent in ("blog_banner", "carousel_design"):
            for p in [
                r"(?:banner|carousel|slide)\s+(?:for|about)\s+[\"']?(.+?)[\"']?\s*$",
                r"blog\s+banner\s+(.+?)$",
            ]:
                m = re.search(p, message, re.IGNORECASE)
                if m and len(m.group(1).strip()) > 2:
                    data["topic"] = m.group(1).strip()
                    break
        elif intent == "video_script":
            for p in [
                r"(?:reel|video|short)\s+script\s+(?:for|about)\s+[\"']?(.+?)[\"']?\s*$",
                r"script\s+(?:for|of)\s+(.+?)$",
            ]:
                m = re.search(p, message, re.IGNORECASE)
                if m and len(m.group(1).strip()) > 2:
                    data["topic"] = m.group(1).strip()
                    break

        elif intent == "create_social":
            # Extract topic for social post
            patterns = [
                r"(?:social|post|instagram|facebook)\s+(?:post|content|bana|likh)\s+(?:about|on|for)\s+[\"']?(.+?)[\"']?\s*$",
                r"(?:post|content)\s+(?:bana|likh|create)\s+(?:about|on|for)\s+[\"']?(.+?)[\"']?\s*$",
                r"(?:about|on|par|topic)\s+[\"']?(.+?)[\"']?\s*$",
                r"social\s+post\s+[\"']?(.+?)[\"']?\s*$",
            ]
            for p in patterns:
                match = re.search(p, message, re.IGNORECASE)
                if match:
                    data["topic"] = match.group(1).strip()
                    break
            if not data.get("topic"):
                stripped = re.sub(
                    r"^(social|instagram|facebook|pinterest)\s+(?:post|caption|content)\s*",
                    "", message, flags=re.IGNORECASE
                ).strip()
                if len(stripped) > 3:
                    data["topic"] = stripped

        elif intent == "show_staging_file":
            m = re.search(r"^show\s+(.+)$", message, re.IGNORECASE)
            if m:
                data["filename"] = m.group(1).strip()
        elif intent in ["show_rewrite", "approve_rewrite", "reject_rewrite"]:
            m = re.search(r"product\s+(\d+)$", message, re.IGNORECASE)
            if not m:
                m = re.search(r"rewrite\s+(\d+)$", message, re.IGNORECASE)
            if m:
                data["product_id"] = m.group(1).strip()
        elif intent == "fix_violations_batch":
            m = re.search(r"batch\s+(\d+)$", message, re.IGNORECASE)
            if m:
                data["batch_size"] = int(m.group(1).strip())

        return data


class IntentResponseHandler:
    """
    Handles responses for new intents.
    Each handler returns a WhatsApp-ready response.
    """
    
    def __init__(self, integration_bridge, director=None, memory=None):
        self.bridge = integration_bridge
        self._director = director
        self.memory = memory
    
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

    def handle_server_diagnose(self, intent):
        """Server/site diagnostic — reachability, WHM, common fixes."""
        result = self.bridge.run_server_diagnose()
        if result.get("success"):
            return {"response": result.get("message", "Done."), "success": True}
        return {"response": result.get("error", "Diagnostic failed."), "success": False}
    
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
    
    def handle_help(self, intent):
        """Show all available commands"""
        response = (
            "🛠️ *FALCON AGENCY — WORLD-CLASS COMMANDS*\n"
            "─────────────────────────────────\n"
            "📊 *Transparency & Reports*\n"
            "• \"agent performance\" — Kaun kitna kaam kar raha\n"
            "• \"director complaint\" — Problem report karo\n"
            "• \"kaun kitna kaam kar raha\" — Team report\n\n"
            "🖥️ *Server / Site Down*\n"
            "• \"site down\" / \"server diagnose\" — Check reachability, WHM\n"
            "• MUTE_SITE_ALERTS=1 in .env — Maintenance mode (no alerts)\n\n"
            "🏥 *Health & Compliance*\n"
            "• \"health scan\" — Full site audit (125+ areas)\n"
            "• \"scan products\" — WooCommerce compliance\n"
            "• \"scan blogs\" / \"scan pages\" — Blog & page scan\n"
            "• \"push karo\" — Apply product rewrites\n"
            "• \"sab fix karo\" — Apply ALL (products+blogs+pages+categories)\n"
            "• \"changelog\" — Last report\n\n"
            "🛒 *Store & Sales*\n"
            "• \"store status\" — Product/API audit\n"
            "• \"order check\" — Recent orders\n"
            "• \"revenue\" — Sales summary\n"
            "• \"profit report\" — Munafa\n\n"
            "📝 *Content*\n"
            "• \"blog likh about [topic]\" — Draft blog\n"
            "• \"social post about [topic]\" — IG+FB posts\n"
            "• \"reel script for [topic]\" — Video script\n"
            "• \"content status\" — Drafts\n"
            "• \"publish\" — Go live\n\n"
            "🎨 *Design & Ads*\n"
            "• \"design [subject]\" — AI image\n"
            "• \"ad creative [topic]\" — Meta/Google ad\n"
            "• \"blog banner [topic]\" — Featured image\n"
            "• \"carousel [topics]\" — Carousel slides\n"
            "• \"brand guidelines\" — Brand kit\n\n"
            "📊 *Analytics & Ads*\n"
            "• \"analytics\" / \"ga4\" — Traffic report\n"
            "• \"ads status\" — Paid ads info\n\n"
            "⚙️ *System*\n"
            "• \"status\" — Workforce update\n"
            "• \"backup\" — Data snapshot\n"
            "• \"help\" — This menu"
        )
        return {"response": response, "success": True}

    def handle_capabilities(self, intent):
        """Return structured capability map (in-scope vs out-of-scope)."""
        try:
            from config.capabilities import get_in_scope_capabilities, get_out_of_scope_reasons
            in_scope = get_in_scope_capabilities()
            out_scope = get_out_of_scope_reasons()
            lines = [
                "📋 *FALCON AGENCY — MERA SCOPE*",
                "─────────────────────────────",
                "",
                "✅ *IN SCOPE (yeh kar sakta hoon):*",
            ]
            for c in in_scope:
                lines.append(f"  • {c['description']} ({c['agent']})")
            lines.append("")
            lines.append("❌ *OUT OF SCOPE:*")
            for name, reason in out_scope:
                lines.append(f"  • {name}: {reason}")
            lines.append("")
            lines.append("_Scope check: Agar kuch scope ke bahar maango, honestly bataunga._")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"Capabilities load failed: {e}", "success": False}

    def handle_bulk_title_fix(self, intent):
        """Scan and fix all risky titles"""
        if not intent.get("confirmed"):
            return {
                "response": (
                    "⚠️ *Confirm karein:* Ye saare risky product titles ko scan karke LIVE site par fix karega. "
                    "Type *'haan karo'* ya *'yes do it'* to confirm."
                ),
                "success": True,
                "needs_confirmation": True,
                "pending_action": "bulk_title_fix",
            }
        result = self.bridge.run_bulk_title_fix()
        if result.get("success"):
            return {
                "response": f"✅ *Title Fix Complete*\n{result.get('message')}",
                "success": True
            }
        return {
            "response": f"❌ Title fix failed: {result.get('error')}",
            "success": False
        }

    def handle_disclaimer_injection(self, intent):
        """Add FDA disclaimer to all products"""
        if not intent.get("confirmed"):
            return {
                "response": (
                    "⚠️ *Confirm karein:* Ye FDA disclaimer saare products mein inject karega (LIVE site update). "
                    "Type *'haan karo'* ya *'yes do it'* to confirm."
                ),
                "success": True,
                "needs_confirmation": True,
                "pending_action": "disclaimer_injection",
            }
        result = self.bridge.run_disclaimer_injection()
        if result.get("success"):
            return {
                "response": f"✅ *Disclaimer Injection*\n{result.get('message')}",
                "success": True
            }
        return {
            "response": f"❌ Injection failed: {result.get('error')}",
            "success": False
        }

    # ===== BLOG / PAGE / CATEGORY HANDLERS =====

    def handle_scan_blog_posts(self, intent):
        """Scan all blog posts for health claim violations."""
        result = self.bridge.scan_blog_posts()
        if result.get("success"):
            total = result.get("total", 0)
            flagged = result.get("flagged", 0)
            posts = result.get("posts", [])
            response = (
                "📰 *BLOG POST COMPLIANCE SCAN*\n"
                "─────────────────────\n"
                "📝 Total Posts Scanned: {}\n"
                "⚠️ Flagged: {}\n"
                "✅ Clean: {}\n"
            ).format(total, flagged, total - flagged)
            if posts:
                response += "\n🔴 *Flagged Blog Posts:*\n"
                for p in posts[:15]:
                    response += "   • {}\n".format(p["title"][:60])
                if flagged > 15:
                    response += "   ...and {} more.\n".format(flagged - 15)
            if flagged > 0:
                response += "\n💡 Send 'rewrite blogs' to generate title fixes."
            return {"response": response, "success": True}
        return {
            "response": "❌ Blog scan failed: {}".format(result.get("error")),
            "success": False,
        }

    def handle_rewrite_blogs(self, intent):
        """AI-rewrite flagged blog titles. Saves for approval."""
        result = self.bridge.rewrite_blog_posts()
        if result.get("success"):
            count = result.get("rewrites", 0)
            if count == 0:
                return {
                    "response": (
                        "📝 No flagged blog posts found.\n"
                        "Run 'scan blogs' first."
                    ),
                    "success": True,
                }
            return {
                "response": (
                    "✅ *Blog Rewrites Generated*\n"
                    "─────────────────────\n"
                    "{} title rewrites saved.\n\n"
                    "📂 Saved to: data/content/product_rewrites/\n"
                    "Review before applying."
                ).format(count),
                "success": True,
            }
        return {
            "response": "❌ Blog rewrite failed: {}".format(result.get("error")),
            "success": False,
        }

    def handle_scan_pages(self, intent):
        """Scan WP pages for health claim violations."""
        result = self.bridge.scan_pages()
        if result.get("success"):
            total = result.get("total", 0)
            flagged = result.get("flagged", 0)
            pages = result.get("pages", [])
            response = (
                "📄 *PAGES COMPLIANCE SCAN*\n"
                "─────────────────────\n"
                "📝 Total Pages: {}\n"
                "⚠️ Flagged: {}\n"
                "✅ Clean: {}\n"
            ).format(total, flagged, total - flagged)
            if pages:
                response += "\n🔴 *Flagged Pages:*\n"
                for p in pages:
                    response += "   • {} — {}\n".format(
                        p["title"][:55], p.get("link", "")[:50]
                    )
            if flagged == 0:
                response += "\n✅ All pages are compliant."
            return {"response": response, "success": True}
        return {
            "response": "❌ Page scan failed: {}".format(result.get("error")),
            "success": False,
        }

    def handle_rename_categories(self, intent):
        """Scan and rename risky category names.
        First call is dry-run preview. Second call applies."""
        # Check message for confirmation
        msg = intent.get("message", "").lower()
        apply_now = any(
            w in msg
            for w in ["apply", "haan", "yes", "kar do", "karo", "confirm", "rename now"]
        )
        result = self.bridge.rename_risky_categories(dry_run=not apply_now)
        if result.get("success"):
            if result.get("dry_run"):
                return {
                    "response": result.get("preview", "No risky categories found."),
                    "success": True,
                }
            renamed = result.get("renamed", 0)
            errors = result.get("errors", [])
            response = (
                "✅ *CATEGORIES RENAMED*\n"
                "─────────────────────\n"
                "{} categories renamed successfully.\n"
            ).format(renamed)
            if errors:
                response += "\n❌ Errors:\n"
                for e in errors[:5]:
                    response += "   • {}\n".format(e)
            return {"response": response, "success": True}
        return {
            "response": "❌ Category rename failed: {}".format(result.get("error")),
            "success": False,
        }

    # ===== HEALTH REWRITER HANDLERS (Phase 3) =====

    def handle_scan_products(self, intent):
        """Scan all WooCommerce products for health claim
        violations. Returns flagged count + list."""
        result = self.bridge.scan_products()
        if result.get("success"):
            total = result.get("total", 0)
            flagged = result.get("flagged", 0)
            products = result.get("products", [])

            response = (
                "🔍 *PRODUCT COMPLIANCE SCAN*\n"
                "─────────────────────\n"
                "📦 Total Products: {}\n"
                "⚠️ Flagged: {}\n"
                "✅ Clean: {}\n"
            ).format(total, flagged, total - flagged)

            if products:
                response += "\n🔴 *Flagged Products:*\n"
                for p in products[:10]:
                    issues = p.get("safety_check", {})
                    changes = issues.get("changes", [])
                    high = sum(
                        1 for c in changes
                        if c.get("severity") == "HIGH"
                    )
                    response += "   • {} — {} HIGH issues\n".format(
                        p["name"][:35], high
                    )
                if flagged > 10:
                    response += (
                        "   ...and {} more.\n".format(flagged - 10)
                    )

            if flagged > 0:
                response += (
                    "\n💡 Say *'rewrite products'* to generate "
                    "AI-safe rewrites for approval."
                )
            else:
                response += "\n✅ All products are compliant!"

            return {"response": response, "success": True}

        return {
            "response": "❌ Scan failed: {}".format(
                result.get("error", "unknown")
            ),
            "success": False,
        }

    def handle_rewrite_products(self, intent):
        """AI-rewrite flagged products. Saves for approval —
        NEVER auto-applies to WooCommerce."""
        result = self.bridge.rewrite_flagged_products()
        if result.get("success"):
            count = result.get("rewrites", 0)
            if count == 0:
                return {
                    "response": (
                        "ℹ️ No flagged products to rewrite.\n"
                        "Run *'scan products'* first."
                    ),
                    "success": True,
                }
            return {
                "response": (
                    "✅ *REWRITES GENERATED*\n"
                    "─────────────────────\n"
                    "📝 {} rewrite(s) created.\n"
                    "📂 data/content/product_rewrites/\n\n"
                    "⚠️ *NOT applied yet.*\n"
                    "Review → Say *'apply rewrite [product_id]'*\n"
                    "Or check status: *'rewrite status'*"
                ).format(count),
                "success": True,
            }
        return {
            "response": "❌ Rewrite failed: {}".format(
                result.get("error", "unknown")
            ),
            "success": False,
        }

    def handle_apply_rewrite(self, intent):
        """Apply an approved rewrite to WooCommerce.
        Requires product_id from the message."""
        msg = intent.get("message_text", "").lower()
        # Extract product ID from message
        id_match = re.search(r"\b(\d+)\b", msg)
        if not id_match:
            return {
                "response": (
                    "🤔 *Which product to apply?*\n\n"
                    "Format:\n"
                    "*'apply rewrite [product_id]'*\n\n"
                    "Check pending rewrites:\n"
                    "*'rewrite status'*"
                ),
                "success": True,
            }

        product_id = int(id_match.group(1))
        result = self.bridge.apply_product_rewrite(product_id)
        if result.get("success"):
            resp = (
                "✅ *REWRITE APPLIED*\n"
                "Product ID: {}\n"
                "{}"
            ).format(
                product_id,
                result.get("message", "Updated on WooCommerce.")
            )
            # GAP 3: Verify WooCommerce actually updated
            verification = verify_task_result(
                "health_rewrite",
                {**result, "applied_ids": [product_id]},
                bridge=self.bridge,
            )
            resp = append_verification_to_response(resp, verification)
            return {"response": resp, "success": True}
        return {
            "response": "❌ Apply failed: {}".format(
                result.get("error", "unknown")
            ),
            "success": False,
        }

    def handle_rewrite_status(self, intent):
        """Show pending / applied product rewrites."""
        return {
            "response": self.bridge.get_rewrite_status(),
            "success": True,
        }

    def _is_confirmation(self, intent: dict) -> bool:
        """Check if message is a confirmation (haan karo, yes do it, etc).
        NOTE: Do NOT include 'karo' alone — 'sab fix karo' = request, not confirmation."""
        msg = (intent.get("message_text") or "").lower()
        # Must contain explicit yes/approve — exclude "fix karo", "sab fix karo"
        if any(x in msg for x in ["fix karo", "sab fix", "fix sab", "fix all"]):
            return False
        return any(w in msg for w in ["haan", "yes", "confirm", "do it", "theek", "apply", "ok karo", "agree"])

    def handle_push_all_rewrites(self, intent):
        """Apply all pending product rewrites. Returns summary + document_path."""
        if not intent.get("confirmed") and not self._is_confirmation(intent):
            return {
                "response": (
                    "⚠️ *Confirm karein:* Ye saare pending product rewrites ko LIVE WooCommerce site par update karega. "
                    "Type *'haan karo'* ya *'yes do it'* to confirm."
                ),
                "success": True,
                "needs_confirmation": True,
                "pending_action": "push_all_rewrites",
            }
        result = self.bridge.run_push_all_rewrites()
        if result.get("success"):
            summary = result.get("summary", "Push complete.")
            report_path = result.get("report_path")
            # GAP 3: Verify task actually worked — check WooCommerce has updated
            verification = verify_task_result(
                "health_rewrite", result, bridge=self.bridge
            )
            summary = append_verification_to_response(summary, verification)
            return {
                "response": summary,
                "success": True,
                "document_path": report_path,
            }
        return {
            "response": result.get("summary", result.get("error", "Push failed.")),
            "success": False,
        }

    def handle_push_all_fixes(self, intent):
        """Flow: Generate rewrites → Show preview → Permission → Publish."""
        if not intent.get("confirmed") and not self._is_confirmation(intent):
            # Step 1: Generate rewrites only (no publish), show preview, ask permission
            result = self.bridge.run_push_all(generate_first=True, apply_immediately=False)
            if result.get("success"):
                preview = result.get("preview", result.get("summary", ""))
                return {
                    "response": (
                        "📋 *Rewrites ready — preview:*\n\n" + (preview[:1200] + "…" if len(preview) > 1200 else preview) + "\n\n"
                        "👆 Check karo. Agar sab theek hai toh *'haan karo'* ya *'ok'* bol ke publish kar dunga."
                    ),
                    "success": True,
                    "needs_confirmation": True,
                    "pending_action": "push_all_fixes",
                }
            return {
                "response": result.get("summary", result.get("error", "Generate failed.")),
                "success": False,
            }
        # Step 2: User approved — apply to live site
        result = self.bridge.run_push_all(generate_first=False)
        if result.get("success"):
            return {
                "response": result.get("summary", "Fix all complete."),
                "success": True,
                "document_path": result.get("report_path"),
            }
        return {
            "response": result.get("summary", "No pending fixes or error."),
            "success": True,
        }

    def handle_rewrite_pages(self, intent):
        """AI-rewrite flagged page titles. Run scan pages first."""
        result = self.bridge.run_rewrite_pages()
        if result.get("success"):
            count = result.get("rewrites", 0)
            return {
                "response": f"Page rewrites saved: {count}. Say 'push all' or 'fix all' to apply.",
                "success": True,
            }
        return {"response": result.get("error", "Failed."), "success": False}

    def handle_push_blog_fixes(self, intent):
        """Apply all pending blog title rewrites."""
        if not intent.get("confirmed") and not self._is_confirmation(intent):
            return {
                "response": (
                    "⚠️ *Confirm karein:* Ye saare pending blog title rewrites ko LIVE WordPress site par update karega. "
                    "Type *'haan karo'* ya *'yes do it'* to confirm."
                ),
                "success": True,
                "needs_confirmation": True,
                "pending_action": "push_blog_fixes",
            }
        result = self.bridge.run_push_all_blog_fixes()
        if result.get("success"):
            return {
                "response": result.get("summary", "Blog fixes applied."),
                "success": True,
                "document_path": result.get("report_path"),
            }
        return {
            "response": result.get("summary", result.get("error", "No pending blog fixes.")),
            "success": result.get("applied", 0) > 0,
            "document_path": result.get("report_path"),
        }

    def handle_push_page_fixes(self, intent):
        """Apply all pending page title rewrites."""
        if not intent.get("confirmed") and not self._is_confirmation(intent):
            return {
                "response": (
                    "⚠️ *Confirm karein:* Ye saare pending page title rewrites ko LIVE WordPress site par update karega. "
                    "Type *'haan karo'* ya *'yes do it'* to confirm."
                ),
                "success": True,
                "needs_confirmation": True,
                "pending_action": "push_page_fixes",
            }
        result = self.bridge.run_push_all_page_fixes()
        if result.get("success"):
            return {
                "response": result.get("summary", "✅ Page fixes applied."),
                "success": True,
                "document_path": result.get("report_path"),
            }
        return {
            "response": result.get("summary", result.get("error", "No pending page fixes.")),
            "success": result.get("applied", 0) > 0,
            "document_path": result.get("report_path"),
        }

    def handle_changelog_report(self, intent):
        """Send last changelog/report file via WhatsApp."""
        report_path = self.bridge.get_latest_changelog_report()
        if not report_path:
            return {
                "response": (
                    "📋 Koi changelog/report nahi mila.\n"
                    "Pehle *'push all'* ya *'apply changes'* karo."
                ),
                "success": False,
            }
        return {
            "response": "📋 Last changelog report bhej raha hoon.",
            "success": True,
            "document_path": report_path,
        }

    def handle_inventory_status(self, intent):
        """Inventory burn rate report"""
        result = self.bridge.get_burn_rate_report()
        if result.get("success"):
            return {
                "response": result.get("summary", "✅ Inventory check complete."),
                "success": True
            }
        return {
            "response": f"❌ Inventory report failed: {result.get('error')}",
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
        """Create social media posts — generates when topic provided."""
        topic = intent.get("extracted_data", {}).get("topic", "")
        msg = intent.get("message_text", "")

        if not self.bridge.tools.get("content"):
            return {
                "response": "❌ Content Pipeline not loaded.",
                "success": False
            }

        if not topic or len(topic) < 3:
            return {
                "response": (
                    "📱 *Social Posts Generator*\n\n"
                    "Topic batao — main IG + FB posts bana dunga.\n\n"
                    "Examples:\n"
                    "• \"Social post about ashwagandha benefits\"\n"
                    "• \"Instagram post on turmeric morning routine\"\n"
                    "• \"Facebook post for ayurvedic wellness tips\"\n\n"
                    "Ya \"Generate weekly content\" — full week batch."
                ),
                "success": True
            }

        result = self.bridge.create_social_single(topic)
        if result.get("success"):
            batch = result.get("batch", {})
            posts = batch.get("posts", [])
            total = batch.get("total_posts", 0)
            resp = (
                f"✅ *SOCIAL POSTS GENERATED*\n"
                f"─────────────────────\n"
                f"📌 Topic: {topic}\n"
                f"📱 Posts: {total}\n"
            )
            for p in posts[:3]:
                platform = p.get("platform", "?")
                status = p.get("status", "?")
                content = (p.get("content") or p.get("prompt", ""))[:150]
                resp += f"\n• *{platform.upper()}* ({status})\n"
                if content:
                    resp += f"  {content}…\n"
            if total > 3:
                resp += f"\n... +{total - 3} more.\n"
            resp += f"\n📂 {result.get('file', 'data/content/drafts/')}"
            return {"response": resp, "success": True}
        return {
            "response": f"❌ Social generation failed: {result.get('error')}",
            "success": False
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

    def handle_content_package(self, intent):
        """Generate weekly content package (images, captions, video, UPLOAD_GUIDE) for HeroPost."""
        try:
            result = self.bridge.generate_weekly_content_package()
            if result.get("success"):
                summary = result.get("summary", "Content package ready.")
                return {"response": summary, "success": True}
            return {
                "response": f"❌ Content package failed: {result.get('error', 'unknown')}",
                "success": False,
            }
        except Exception as e:
            return {"response": f"❌ Error: {e}", "success": False}

    # ──────────────────────────────────────────────────────────────────────
    #  SOCIAL CONTENT: Send latest draft to WhatsApp in HeroPost-ready format
    # ──────────────────────────────────────────────────────────────────────

    def _parse_social_post_content(self, raw_content: str) -> dict:
        """
        Parse AI-generated social post content into structured sections.
        Handles both **SECTION** and plain paragraph formats.
        """
        result = {"caption": "", "hashtags": "", "image_prompt": ""}

        # Try to split by bold headers like **CAPTION**, **HASHTAGS**, etc.
        cap_match = re.search(
            r'\*\*CAPTION\*\*\s*(.*?)(?=\*\*HASHTAGS?\*\*|\*\*IMAGE|\Z)',
            raw_content, re.S | re.I
        )
        hash_match = re.search(
            r'\*\*HASHTAGS?\*\*\s*(.*?)(?=\*\*IMAGE|\Z)',
            raw_content, re.S | re.I
        )
        img_match = re.search(
            r'\*\*IMAGE\s*SUGGESTION\*\*\s*(.*?)(?=\*\*|\Z)',
            raw_content, re.S | re.I
        )

        if cap_match:
            result["caption"] = cap_match.group(1).strip()
        if hash_match:
            ht = hash_match.group(1).strip()
            # Keep only lines that have hashtags
            ht_lines = [l.strip() for l in ht.split('\n') if '#' in l]
            result["hashtags"] = ' '.join(ht_lines)
        if img_match:
            result["image_prompt"] = img_match.group(1).strip()

        # Fallback: if no structured headers found, use full content as caption
        if not result["caption"]:
            # Extract hashtags from last section
            lines = raw_content.strip().split('\n')
            hash_lines = [l for l in lines if l.strip().startswith('#')]
            cap_lines = [l for l in lines if not l.strip().startswith('#')]
            result["caption"] = '\n'.join(cap_lines).strip()
            result["hashtags"] = ' '.join(hash_lines)

        return result

    def _format_post_for_whatsapp(self, post: dict, index: int = 1, total: int = 1) -> str:
        """Format a single social post in clean HeroPost-ready WhatsApp format."""
        platform = post.get("platform", "instagram").upper()
        topic = post.get("topic", "")
        raw = post.get("content", "")
        parsed = self._parse_social_post_content(raw)

        icon = "📸" if "INSTAGRAM" in platform else "📘"
        lines = [
            f"{icon} *{platform} POST*{' — ' + topic if topic else ''}",
            "─" * 32,
            "",
            "*CAPTION* (copy this exactly):",
            parsed["caption"],
        ]
        if parsed["hashtags"]:
            lines += ["", "*HASHTAGS*:", parsed["hashtags"]]
        if parsed["image_prompt"]:
            # Trim image prompt to avoid very long messages
            img = parsed["image_prompt"][:400]
            lines += ["", "🖼️ *IMAGE PROMPT*:", img]
        lines += ["", "─" * 32]

        if index < total:
            lines.append(f"_(Post {index}/{total} — next message: Facebook)_")

        return '\n'.join(lines)

    def handle_send_social_content(self, intent) -> dict:
        """
        Find the latest social batch draft and send each post to WhatsApp
        in a clean, HeroPost-ready copy-paste format.
        """
        import glob
        import os

        drafts_dir = "data/content/drafts"
        pattern = os.path.join(drafts_dir, "social_batch_*.json")
        files = sorted(glob.glob(pattern), reverse=True)  # newest first

        if not files:
            return {
                "response": (
                    "❌ Koi social post draft nahi mila.\n"
                    "Try: *'social post about Ashwagandha'* to generate one first."
                ),
                "success": False,
            }

        latest_file = files[0]
        try:
            with open(latest_file, encoding="utf-8") as f:
                batch = json.load(f)
        except Exception as e:
            return {"response": f"❌ Draft read error: {e}", "success": False}

        posts = batch.get("posts", [])
        if not posts:
            return {"response": "❌ Draft file is empty.", "success": False}

        created = batch.get("created_at", "")[:16]
        total = len(posts)

        # First message: summary header
        header = (
            f"📋 *CONTENT READY FOR HEROPOST*\n"
            f"Date: {created} | {total} post(s)\n"
            f"Topic: {posts[0].get('topic', '')}\n"
            f"Copy each post below ↓ and paste into HeroPost"
        )

        # One message per platform — avoids WhatsApp truncation of joined content
        # commander.py handles "messages" list by sending each one separately
        messages = [header]
        for i, post in enumerate(posts, 1):
            messages.append(
                self._format_post_for_whatsapp(post, index=i, total=total)
            )

        return {
            "messages": messages,
            "success": True,
            "filename": os.path.basename(latest_file),
        }

    def handle_email_campaign(self, intent):
        """Generate email campaign for NetworkSolutions manual send."""
        try:
            msg = (intent.get("message_text") or "").lower()
            campaign_type = "sale" if any(w in msg for w in ["sale", "sale ke", "discount"]) else "newsletter"
            result = self.bridge.generate_email_campaign(campaign_type=campaign_type)
            if result.get("success"):
                return {"response": result.get("summary", "Email campaign ready."), "success": True}
            return {"response": f"❌ {result.get('error')}", "success": False}
        except Exception as e:
            return {"response": f"❌ Error: {e}", "success": False}

    def handle_image_banao(self, intent):
        """Generate single image for product/topic."""
        try:
            msg = intent.get("message_text", "") or intent.get("extracted_data", {}).get("query", "")
            # Extract product/topic from message (e.g. "Ashwagandha ke liye image banao")
            product_match = re.search(r"(?:ke\s+liye|for)\s+(.+?)(?:\s+image|\s+graphic|$)", msg, re.I)
            topic = product_match.group(1).strip() if product_match else "Indian herbal wellness"
            if not topic or len(topic) < 2:
                topic = "Falcon Herbs herbal product"
            img = self.bridge.tools.get("image")
            if not img:
                return {"response": "❌ Image generator not loaded.", "success": False}
            r = img.generate(topic, style="product", width=1080, height=1080)
            if r.get("success"):
                if self._director and hasattr(self._director, "log_spend"):
                    self._director.log_spend(0.02, "nvidia_image", "falconherbs.com")
                return {"response": r.get("message", f"✅ Image saved: {r.get('filepath')}"), "success": True}
            return {"response": f"❌ {r.get('error')}", "success": False}
        except Exception as e:
            return {"response": f"❌ Error: {e}", "success": False}

    def handle_video_banao(self, intent):
        """Generate product reel / slideshow video."""
        try:
            msg = intent.get("message_text", "") or intent.get("extracted_data", {}).get("query", "")
            # Extract product name (e.g. "Ashwagandha ke liye reel banao", "neem ke product ka reel")
            product_match = re.search(r"(.+?)\s+ke\s+liye\s+reel", msg, re.I) or re.search(r"(.+?)\s+ka\s+reel", msg, re.I) or re.search(r"reel\s+banao\s+(.+?)(?:\s|$)", msg, re.I)
            product_name = product_match.group(1).strip() if product_match else "herbal product"
            if not product_name or len(product_name) < 2:
                product_name = "Ayurvedic wellness"
            result = self.bridge.generate_product_reel(product_name)
            if result.get("success"):
                return {"response": result.get("summary", f"✅ Reel ready: {result.get('filepath')}"), "success": True}
            return {"response": f"❌ {result.get('error')}", "success": False}
        except Exception as e:
            return {"response": f"❌ Error: {e}", "success": False}
    
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
        """Customer win-back: find inactive customers + generate emails"""
        try:
            wb = self.bridge.tools.get("winback")

            # If winback module not loaded, fall back gracefully
            if not wb:
                return {
                    "response": (
                        "⚠️ Win-Back module not loaded.\n"
                        "Check logs for import errors."
                    ),
                    "success": False,
                }

            # Always show current status first
            status_msg = wb.get_winback_status()

            # Decide action based on message keywords
            msg = (
                intent.get("extracted_data", {})
                .get("raw_message", "")
                .lower()
            )

            # "find" / "dhundh" / "list" → scan for inactive
            if any(
                kw in msg
                for kw in [
                    "find", "dhundh", "search", "list",
                    "scan", "inactive", "purane", "old",
                ]
            ):
                result = wb.find_inactive_customers(days=90)
                if result.get("success"):
                    inactive = result.get("inactive", 0)
                    total = result.get("total_customers", 0)
                    sample = result.get("customers", [])[:5]

                    response = (
                        "👥 *INACTIVE CUSTOMERS FOUND*\n"
                        "─────────────────────\n"
                        "📊 Total customers: {}\n"
                        "🚫 Inactive (90+ days): {}\n\n"
                    ).format(total, inactive)

                    if sample:
                        response += "📋 *Sample (top 5):*\n"
                        for c in sample:
                            response += "   • {} — {}\n".format(
                                c.get("name", "Unknown"),
                                c.get("email", ""),
                            )

                    response += (
                        "\n💡 Say *'generate winback emails'* "
                        "to create reactivation drafts."
                    )
                    return {"response": response, "success": True}

                return {
                    "response": "❌ Scan failed: {}".format(
                        result.get("error", "unknown")
                    ),
                    "success": False,
                }

            # "email" / "generate" / "draft" → create email drafts
            if any(
                kw in msg
                for kw in [
                    "email", "generate", "draft", "bana",
                    "create", "winback", "reactivat",
                ]
            ):
                result = wb.generate_winback_emails(count=10)
                if result.get("success"):
                    generated = result.get("generated", 0)
                    return {
                        "response": (
                            "✅ *WIN-BACK EMAILS READY*\n"
                            "─────────────────────\n"
                            "📧 {} draft(s) created.\n"
                            "📂 data/customer_winback/"
                            "email_drafts/\n\n"
                            "⚠️ *Emails NOT sent automatically.*\n"
                            "Review → approve → send manually."
                        ).format(generated),
                        "success": True,
                    }
                return {
                    "response": "❌ Email generation failed: {}".format(
                        result.get("error", "unknown")
                    ),
                    "success": False,
                }

            # Default: just show status with options
            response = (
                "{}\n\n"
                "💡 *Commands:*\n"
                "• *'find inactive customers'* — scan 90-day lapsed\n"
                "• *'generate winback emails'* — create email drafts\n"
                "• *'customer list'* — see inactive customers"
            ).format(status_msg)

            return {"response": response, "success": True}

        except Exception as e:
            return {
                "response": "❌ Error: {}".format(e),
                "success": False,
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
    
    def handle_analyse_keywords(self, intent):
        """Keyword coverage analysis via StrategistAgent"""
        try:
            from agents.strategist import StrategistAgent
            strat = StrategistAgent()
            site = "falconherbs.com"
            profile = strat._load_profile(site)
            data = strat.analyse_keywords(site, profile)
            if data.get("error"):
                return {"response": f"❌ Keyword analysis failed: {data['error']}", "success": False}
            total = data.get("total_keywords", 0)
            avg = data.get("average_score", 0)
            gaps = data.get("gaps", [])
            recs = data.get("recommendations", [])
            lines = [
                f"📊 *KEYWORD ANALYSIS* — {site}",
                "─" * 22,
                f"Keywords checked: {total}",
                f"Average score: {avg}/5",
            ]
            if gaps:
                lines.append(f"\n⚠️ Gaps: {len(gaps)}")
                for g in gaps[:3]:
                    lines.append(f"  • {g.get('keyword', '?')}")
            if recs:
                lines.append("\n" + recs[0][:200])
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Keyword analysis failed: {e}", "success": False}

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

    def handle_plugin_install(self, intent):
        """Install plugin — approval gate, backup, verify."""
        try:
            msg = (intent.get("message_text") or "").lower()
            slug_map = {
                "rank math": "rank-math-seo",
                "rankmath": "rank-math-seo",
                "yoast": "wordpress-seo",
                "yoast seo": "wordpress-seo",
                "wordfence": "wordfence",
                "updraft": "updraftplus",
                "updraftplus": "updraftplus",
            }
            slug = intent.get("extracted_data", {}).get("plugin_slug", "").strip()
            if not slug:
                for k, v in slug_map.items():
                    if k in msg:
                        slug = v
                        break
            if not slug:
                # Try to extract last word or phrase after "install"
                import re
                m = re.search(r"install\s+(?:plugin\s+)?([a-z0-9\-]+)", msg, re.I)
                if m:
                    slug = m.group(1).replace(" ", "-")
            if not slug:
                return {"response": "Kaun sa plugin install karna hai? Batao, e.g. 'plugin install rank math'", "success": False}
            pm = self.bridge.tools.get("plugin_manager") if self.bridge else None
            if not pm:
                from core.plugin_manager import PluginManager
                pm = PluginManager()
            result = pm.install_plugin(slug)
            if result.get("success"):
                return {"response": f"✅ {result.get('message', 'Plugin installed')}", "success": True}
            return {"response": f"❌ {result.get('error', 'Install failed')}", "success": False}
        except Exception as e:
            return {"response": f"❌ Plugin install failed: {e}", "success": False}

    def handle_plugin_list(self, intent):
        """List installed plugins."""
        try:
            pm = self.bridge.tools.get("plugin_manager") if self.bridge else None
            if not pm:
                from core.plugin_manager import list_installed_plugins
                result = list_installed_plugins({})
            else:
                result = list_installed_plugins(pm.site_config)
            if not result.get("success"):
                return {"response": f"❌ {result.get('error', 'List failed')}", "success": False}
            plugins = result.get("plugins", [])
            if not plugins:
                return {"response": "Koi plugin nahi mila (ya WP auth configure nahi hai).", "success": True}
            lines = [f"• {p.get('name', p.get('plugin', ''))} v{p.get('version', '')} {'✅' if p.get('active') else '⏸️'}" for p in plugins[:20]]
            return {"response": "Installed plugins:\n" + "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ {e}", "success": False}

    def handle_plugin_recommend(self, intent):
        """Recommend plugins for speed/performance/SEO."""
        try:
            msg = (intent.get("message_text") or "").lower()
            need = "performance"
            if "seo" in msg:
                need = "seo"
            elif "security" in msg or "secure" in msg:
                need = "security"
            elif "backup" in msg:
                need = "backup"
            pm = self.bridge.tools.get("plugin_manager") if self.bridge else None
            if not pm:
                from core.plugin_manager import PluginManager
                pm = PluginManager()
            result = pm.recommend_plugins(need)
            suggestions = result.get("suggestions", [])
            lines = []
            for s in suggestions[:5]:
                status = "✅ installed" if s.get("already_installed") else s.get("safety_detail", "")
                lines.append(f"• {s.get('name')} ({s.get('slug')}) — {status}")
            return {"response": f"Suggestions for {need}:\n" + "\n".join(lines) if lines else "Koi suggestion nahi.", "success": True}
        except Exception as e:
            return {"response": f"❌ {e}", "success": False}

    def handle_plugin_update(self, intent):
        """Update plugins — backup first, then update each outdated."""
        try:
            pm = self.bridge.tools.get("plugin_manager") if self.bridge else None
            if not pm:
                from core.plugin_manager import PluginManager, list_installed_plugins
                pm = PluginManager()
                list_result = list_installed_plugins({})
            else:
                list_result = list_installed_plugins(pm.site_config)
            if not list_result.get("success"):
                return {"response": f"❌ {list_result.get('error', 'Cannot list plugins')}", "success": False}
            outdated = [p for p in list_result.get("plugins", []) if p.get("update_available")]
            if not outdated:
                return {"response": "✅ Sab plugins updated hain. Koi update pending nahi.", "success": True}
            results = []
            for p in outdated[:5]:
                slug = (p.get("plugin", "") or "").split("/")[0]
                if slug:
                    r = pm.update_plugin(slug)
                    results.append(f"• {slug}: {'✅' if r.get('success') else '❌ ' + str(r.get('error', ''))}")
            return {"response": "Plugin updates:\n" + "\n".join(results), "success": True}
        except Exception as e:
            return {"response": f"❌ {e}", "success": False}

    def handle_ads_status(self, intent):
        """Google Ads / Meta Ads status — honest not_configured if no API."""
        try:
            from core.ads_monitor import get_google_ads_summary, get_meta_ads_summary
            msg = (intent.get("message_text") or "").lower()
            if "meta" in msg or "facebook" in msg:
                result = get_meta_ads_summary("today")
            else:
                result = get_google_ads_summary("today")
            status = result.get("status", "unknown")
            resp = result.get("message", "")
            if status == "not_configured" and result.get("setup_instructions"):
                resp += "\n\n" + result.get("setup_instructions", "")
            return {"response": resp, "success": True}
        except Exception as e:
            return {"response": f"❌ {e}", "success": False}

    def handle_ads_report(self, intent):
        """Generate ads report for WhatsApp."""
        try:
            am = self.bridge.tools.get("ads_monitor") if self.bridge else None
            if not am:
                from core.ads_monitor import AdsMonitor
                am = AdsMonitor()
            result = am.generate_ads_report(period="weekly")
            return {"response": result.get("report", "No report"), "success": True}
        except Exception as e:
            return {"response": f"❌ {e}", "success": False}

    def handle_ads_pause(self, intent):
        """Pause campaign — approval gate."""
        try:
            msg = (intent.get("message_text") or "").lower()
            import re
            campaign_match = re.search(r"campaign\s*[:\s]*([a-z0-9\-]+)", msg, re.I)
            campaign_id = campaign_match.group(1) if campaign_match else ""
            if not campaign_id:
                return {"response": "Kaun sa campaign pause karna hai? Campaign ID batao.", "success": False}
            platform = "meta" if "meta" in msg or "facebook" in msg else "google"
            am = self.bridge.tools.get("ads_monitor") if self.bridge else None
            if not am:
                from core.ads_monitor import AdsMonitor
                am = AdsMonitor()
            result = am.pause_campaign(campaign_id, platform)
            if result.get("success"):
                return {"response": f"✅ {result.get('message', 'Campaign pause requested')}", "success": True}
            return {"response": f"❌ {result.get('error', 'Pause failed')}", "success": False}
        except Exception as e:
            return {"response": f"❌ {e}", "success": False}
            
    def handle_image_generate(self, intent):
        """Generate an image using bridge ImageGenerator or MediaAgent."""
        try:
            query = intent.get("extracted_data", {}).get("query", "")
            msg = intent.get("message_text", "")
            if not query and msg:
                query = re.sub(
                    r"^(image|photo|design|picture)\s+(?:generate|bana|create|make)\s*",
                    "", msg, flags=re.IGNORECASE
                ).strip()
            if not query or len(query) < 2:
                query = "premium ayurvedic herbal product, wellness theme"

            img_tool = self.bridge.tools.get("image")
            if img_tool:
                result = img_tool.generate(query, style="product")
                if result.get("success"):
                    return {
                        "response": result.get(
                            "message",
                            f"🎨 Image generated: {result.get('filename', '')}"
                        ),
                        "success": True,
                    }
                return {
                    "response": f"❌ {result.get('error', 'Image generation failed')}",
                    "success": False,
                }

            from agents.media import MediaAgent
            media = MediaAgent()
            result = media.execute("design", query)
            return {"response": result, "success": True}
        except Exception as e:
            return {
                "response": f"❌ Image generation failed: {e}",
                "success": False
            }

    def handle_ad_creative(self, intent):
        """Generate Meta/Google ad creative."""
        topic = intent.get("extracted_data", {}).get("query", "") or intent.get("extracted_data", {}).get("topic", "")
        msg = intent.get("message_text", "")
        if not topic:
            topic = re.sub(r"^(ad|meta|google|facebook|instagram)\s+(?:ad|creative|design)\s*", "", msg, flags=re.IGNORECASE).strip()
        if not topic or len(topic) < 2:
            topic = "premium ayurvedic herbal product, wellness"
        try:
            from agents.designer import DesignerAgent
            designer = DesignerAgent()
            result = designer.create_ad_creative(topic)
            return {"response": result, "success": "✅" in result}
        except Exception as e:
            return {"response": f"❌ Ad creative failed: {e}", "success": False}

    def handle_blog_banner(self, intent):
        """Generate blog featured image."""
        topic = intent.get("extracted_data", {}).get("topic", "")
        msg = intent.get("message_text", "")
        if not topic:
            topic = re.sub(r"^(blog|banner|featured)\s+(?:banner|image)\s*", "", msg, flags=re.IGNORECASE).strip()
        if not topic or len(topic) < 2:
            topic = "ayurvedic wellness"
        try:
            from agents.designer import DesignerAgent
            designer = DesignerAgent()
            result = designer.create_blog_banner(topic)
            return {"response": result, "success": "✅" in result}
        except Exception as e:
            return {"response": f"❌ Banner failed: {e}", "success": False}

    def handle_carousel_design(self, intent):
        """Generate carousel slides."""
        topics = intent.get("extracted_data", {}).get("topic", "")
        msg = intent.get("message_text", "")
        if not topics:
            topics = re.sub(r"^(carousel|slide)\s+(?:design|bana)\s*", "", msg, flags=re.IGNORECASE).strip()
        if not topics:
            topics = "ayurvedic benefits, how to use, buy now"
        try:
            from agents.designer import DesignerAgent
            designer = DesignerAgent()
            result = designer.create_carousel(topics)
            return {"response": result, "success": "✅" in result}
        except Exception as e:
            return {"response": f"❌ Carousel failed: {e}", "success": False}

    def handle_brand_guidelines(self, intent):
        """Show brand guidelines."""
        try:
            from agents.designer import DesignerAgent
            designer = DesignerAgent()
            guidelines = designer.get_brand_guidelines()
            return {
                "response": f"📋 *FALCON HERBS BRAND GUIDELINES*\n```\n{guidelines}\n```",
                "success": True
            }
        except Exception as e:
            return {"response": f"❌ {e}", "success": False}

    def handle_analytics_traffic(self, intent):
        """GA4 traffic report - users, sessions, pageviews."""
        try:
            ga4 = self.bridge.tools.get("ga4")
            if not ga4:
                return {"response": "❌ GA4 not loaded.", "success": False}
            result = ga4.get_traffic_report(days=7)
            if result.get("success"):
                u, s, p = result.get("users", 0), result.get("sessions", 0), result.get("pageviews", 0)
                return {
                    "response": (
                        f"📊 *TRAFFIC REPORT — Last 7 Days*\n"
                        f"{'─' * 25}\n"
                        f"👥 Users: {u:,}\n"
                        f"🔄 Sessions: {s:,}\n"
                        f"📄 Pageviews: {p:,}\n"
                        f"\n📅 {result.get('period', '')}"
                    ),
                    "success": True,
                }
            return {
                "response": ga4.get_status() + f"\n\n⚠️ {result.get('error', '')}",
                "success": False,
            }
        except Exception as e:
            return {"response": f"❌ Analytics error: {e}", "success": False}

    def handle_ads_status(self, intent):
        """Paid ads status — honest status, no fake data."""
        meta = bool(os.environ.get("META_ADS_TOKEN") or os.environ.get("META_ACCESS_TOKEN"))
        google = bool(os.environ.get("GOOGLE_ADS_CUSTOMER_ID") and os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"))
        if meta or google:
            configured = "Meta ✅" if meta else "Meta ❌"
            configured += " | Google ✅" if google else " | Google ❌"
            return {
                "response": (
                    f"📢 *PAID ADS*\n{'─' * 22}\n"
                    f"Status: {configured}\n\n"
                    "Ad creatives generate kar sakte ho:\n"
                    "\"ad creative ashwagandha\" bol do."
                ),
                "success": True,
            }
        return {
            "response": (
                "📢 *PAID ADS* — Not configured\n"
                "─────────────────────\n"
                "Add to .env:\n"
                "• META_ADS_TOKEN — Meta Business API\n"
                "• GOOGLE_ADS_CUSTOMER_ID + GOOGLE_ADS_DEVELOPER_TOKEN\n\n"
                "Abhi: \"ad creative [topic]\" se creatives bana sakte ho."
            ),
            "success": True,
        }

    def handle_video_script(self, intent):
        """Generate reel/video script for short-form content."""
        topic = intent.get("extracted_data", {}).get("topic", "")
        msg = intent.get("message_text", "")
        if not topic:
            topic = re.sub(
                r"^(reel|video|short|script)\s+(?:script|bana|create|for)\s*",
                "", msg, flags=re.IGNORECASE
            ).strip()
        if not topic or len(topic) < 2:
            topic = "ayurvedic morning routine"
        try:
            from core.ai_client import call_ai
            prompt = f"""Create a 30-60 second Instagram Reel / YouTube Short script for Falcon Herbs (Ayurvedic wellness brand).

TOPIC: {topic}

Format:
- Hook (first 3 sec): Grab attention
- Body: 2-3 key points, conversational
- CTA: Soft sell, link in bio
- Caption: 1-2 lines
- Hashtags: 5-7 relevant

Keep it punchy, under 150 words. No health claims."""
            messages = [
                {"role": "system", "content": "You write viral short-form video scripts. Punchy, hook-first."},
                {"role": "user", "content": prompt},
            ]
            script = call_ai("media", messages)
            if script:
                return {
                    "response": f"🎬 *REEL SCRIPT*\n{'─'*25}\n{script[:1200]}",
                    "success": True,
                }
            return {"response": "❌ Script generation failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ {e}", "success": False}

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
    
    def handle_share_draft_text(self, intent):
        """
        Read the latest blog draft JSON and send its content directly as WhatsApp text.
        User asked: 'Can you share those drafts in txt here?' — just read and send.
        """
        import glob as _glob
        try:
            from core.wordpress_publisher import wp_publisher
            drafts = wp_publisher.list_drafts() if hasattr(wp_publisher, 'list_drafts') else ""

            # Also check data/content/drafts/ for JSON blog drafts
            import os
            drafts_dir = "data/content/drafts"
            blog_pattern = os.path.join(drafts_dir, "blog_*.json")
            blog_files = sorted(_glob.glob(blog_pattern), reverse=True)

            if not blog_files:
                return {
                    "response": "❌ Koi blog draft nahi mila. Pehle generate karo: 'blog likho'",
                    "success": False,
                }

            # Send up to 2 most recent drafts as separate messages
            messages = []
            for filepath in blog_files[:2]:
                try:
                    with open(filepath, encoding="utf-8") as f:
                        d = json.load(f)
                    title = d.get("title", os.path.basename(filepath))
                    content = d.get("content", d.get("body", d.get("html", "")))
                    # Strip HTML tags for WhatsApp
                    import re as _re
                    content_clean = _re.sub(r'<[^>]+>', '', content).strip()
                    # Truncate at 3500 chars (WhatsApp safe)
                    if len(content_clean) > 3500:
                        content_clean = content_clean[:3500] + "\n\n...[continued - full draft saved locally]"
                    word_count = len(content_clean.split())
                    msg = f"📝 *{title}*\n({word_count} words)\n─────────────────────\n{content_clean}"
                    messages.append(msg)
                except Exception:
                    continue

            if not messages:
                return {
                    "response": "❌ Draft files empty ya read nahi ho saka.",
                    "success": False,
                }

            return {
                "messages": messages,
                "success": True,
            }
        except Exception as e:
            return {"response": f"❌ Draft share error: {e}", "success": False}

    def handle_live_publish(self, intent):
        """Confirmation flow: user said 'haan karo' after live publish prompt. Execute live publish."""
        intent = dict(intent) if intent else {}
        intent["confirmed"] = True
        # Force live (as_draft=False) — this is the confirmation for live
        intent["_force_live"] = True
        return self.handle_publish_blog(intent)

    def handle_publish_blog(self, intent):
        """Approve and publish latest draft via ContentWorkflow.
        Detects 'live' keyword for direct publish vs draft."""
        try:
            workflow = self.bridge.tools.get("workflow")
            if not workflow:
                return {
                    "response": "❌ Content Workflow not loaded.",
                    "success": False
                }
            
            # Confirmation flow (handle_live_publish) sets _force_live
            force_live = intent.get("_force_live", False)
            # Detect live vs draft from original message
            msg = intent.get(
                "original_text",
                intent.get("message_text", intent.get("extracted_data", {}).get("query", "")),
            )
            msg = (msg or "").lower()
            is_live = force_live or any(
                w in msg for w in [
                    "live publish", "publish live",
                    "live karo", "make live", "go live"
                ]
            )
            as_draft = not is_live

            # SAFETY: Live publish requires explicit confirmation (unless already confirmed)
            if is_live and not intent.get("confirmed") and not self._is_confirmation(intent):
                return {
                    "response": (
                        "⚠️ *Live Publish Confirmation*\n\n"
                        "Yeh blog post live ho jayegi — sab visitors dekh sakte hain.\n\n"
                        "Confirm karne ke liye:\n"
                        "✅ *'haan publish karo'* ya *'yes live karo'*"
                    ),
                    "success": True,
                    "awaiting_confirmation": True,
                    "pending_action": "live_publish"
                }

            result = workflow.approve_and_publish(
                as_draft=as_draft
            )
            if result.get("success"):
                # GAP 3: Verify page actually loads
                verification = verify_task_result(
                    "content_publish", result, bridge=self.bridge
                )
                msg = result.get("message", "")
                if not msg:
                    url = result.get("post_url", result.get("url", ""))
                    if as_draft:
                        msg = "✅ Published as WordPress DRAFT"
                        if url:
                            msg += "\n🔗 Review at: {}".format(url)
                        msg += "\n\n📝 Say 'publish live karo' to make it public."
                    else:
                        msg = "🚀 Published LIVE!"
                        if url:
                            msg += "\n🔗 View at: {}".format(url)
                msg = append_verification_to_response(msg, verification)
                return {"response": msg, "success": True}
            return {
                "response": "❌ Publish failed: {}".format(
                    result.get("error", "unknown")),
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
    
    # ===== CONTENT WORKFLOW HANDLERS (Phase 2) =====
    
    def handle_content_queue(self, intent):
        """Show content queue status"""
        try:
            workflow = self.bridge.tools.get("workflow")
            if not workflow:
                return {
                    "response": "❌ Content Workflow not loaded.",
                    "success": False
                }
            return {
                "response": workflow.get_queue_status(),
                "success": True
            }
        except Exception as e:
            return {
                "response": f"❌ Queue check failed: {e}",
                "success": False
            }
    
    def handle_retry_drafts(self, intent):
        """Retry all prompt-only drafts with AI client"""
        try:
            result = self.bridge.retry_prompt_only_drafts()
            if result.get("success"):
                retried = result.get("retried", 0)
                if retried > 0:
                    return {
                        "response": (
                            "✅ *DRAFTS RETRIED*\n"
                            "🔄 {} draft(s) regenerated "
                            "with AI.\n"
                            "Check 'drafts dikhao' for "
                            "updated status.".format(retried)
                        ),
                        "success": True
                    }
                return {
                    "response": (
                        "ℹ️ No prompt-only drafts found "
                        "to retry. All drafts already "
                        "have content."
                    ),
                    "success": True
                }
            return {
                "response": "❌ Retry failed: {}".format(
                    result.get("error", "unknown")),
                "success": False
            }
        except Exception as e:
            return {
                "response": f"❌ Retry error: {e}",
                "success": False
            }


# ==================== TEST ====================

    def handle_pr_outreach(self, intent_result: dict) -> dict:
        """
        Search for YouTube influencers.
        """
        # Extract topic from patterns
        topic = None
        matched_groups = intent_result.get("extracted_data", {}).get("matched_groups", [])
        if matched_groups:
            topic = matched_groups[0]
        
        if not topic:
            # Fallback extraction from raw message if regex groups failed
            raw_message = intent_result.get("message_text", "")
            topic = re.sub(r"^(find influencers for|influencer search|find creators for|pr outreach)\s+", "", raw_message, flags=re.IGNORECASE).strip()

        if not topic or len(topic) < 3:
            return {
                "response": "🤔 Please specify a topic for the influencer search.\n\n"
                           "Example: *find influencers for stress relief*",
                "success": False
            }

        from agents.pr_outreach import PROutreach
        from core.ai_client import call_ai
        
        outreach = PROutreach(llm_caller=call_ai)
        results = outreach.find_influencers(topic)
        
        # Format for WhatsApp
        response = outreach.format_whatsapp_result(results)
        
        # Store results in memory for subsequent "Reply 1" interaction if needed
        # (Though full interaction logic might need more state management)
        # For now, we return the list.
        
        return {
            "response": response,
            "success": True,
            "data": {"influencers": results if isinstance(results, list) else []}
        }

    def handle_sentry_check(self, intent_result: dict) -> dict:
        """
        Analyze a social media comment for compliance risks.
        Expects: "Check this comment: [text]"
        """
        raw_message = intent_result.get("extracted_data", {}).get("raw_message", "")
        # If not in extracted_data, try getting it from the classifier context if available
        # or just fallback to some extraction logic
        
        # In our system, the classifier doesn't always put 'raw_message' in extracted_data
        # We need to make sure we have the text.
        
        message_text = intent_result.get("message_text", "") # We might need to pass this in
        
        # Let's use a helper to extract the comment
        comment = self._extract_comment_text(message_text)
        
        if not comment:
            return {
                "response": "🤔 Please paste the comment after the command.\n\n"
                           "Example: *Check this comment: This product cured my diabetes*",
                "success": False
            }
        
        from agents.social_sentry import SocialSentry
        from core.ai_client import call_ai
        
        sentry = SocialSentry(llm_caller=call_ai)
        result = sentry.analyze(comment)
        alert = sentry.format_whatsapp_alert(result)
        
        return {
            "response": alert,
            "success": True,
            "data": result
        }

    # ===== AEO HANDLERS =====

    def handle_aeo_scan(self, intent_result: dict) -> dict:
        """
        Trigger a live AEO brand visibility scan.
        Queries Perplexity/OpenAI for 25 Ayurveda questions,
        checks Falcon Herbs mentions, saves content gaps.
        """
        aeo = self.bridge.tools.get("aeo")
        if not aeo:
            return {
                "response": (
                    "❌ AEO Agent not loaded.\n"
                    "Check logs for import errors."
                ),
                "success": False,
            }

        import os
        has_serper = bool(os.getenv("SERPER_API_KEY"))
        has_nvidia = bool(os.getenv("NVIDIA_API_KEY"))
        if not has_serper:
            return {
                "response": (
                    "⚠️ *AEO Scan — API Key Missing*\n\n"
                    "Add to .env file:\n"
                    "• SERPER_API_KEY  ← for Google search (serper.dev)\n\n"
                    "Free tier: 2500 searches/month\n"
                    "signup: serper.dev"
                ),
                "success": False,
            }
        if not has_nvidia:
            return {
                "response": (
                    "⚠️ *AEO Scan — NVIDIA API Key needed*\n\n"
                    "NVIDIA_API_KEY is used for AI analysis of search results.\n"
                    "Already configured in project — check .env"
                ),
                "success": False,
            }

        # Kick off scan — takes ~30s for 25 questions
        result = self.bridge.run_aeo_scan()
        if result.get("success"):
            return {
                "response": result.get("summary", "✅ AEO scan complete."),
                "success": True,
                "data": result.get("data", {}),
            }
        return {
            "response": "❌ AEO scan failed: {}".format(
                result.get("error", "unknown")
            ),
            "success": False,
        }

    def handle_aeo_report(self, intent_result: dict) -> dict:
        """Show latest saved AEO report + content gaps."""
        report = self.bridge.get_aeo_report()

        # Also show content gaps count
        gaps = self.bridge.get_aeo_content_gaps()
        unused = [g for g in gaps if not g.get("used", False)]

        suffix = ""
        if unused:
            suffix = (
                "\n\n📝 *{} gaps queued in ContentWorkflow*\n"
                "These will be auto-picked as next blog topics."
            ).format(len(unused))

        return {
            "response": report + suffix,
            "success": True,
        }

    def handle_agent_performance(self, intent_result: dict) -> dict:
        """Agent performance report — who's busy, who's idle, failures."""
        try:
            from core.agent_performance import format_performance_report
            days = 7
            report = format_performance_report(days)
            return {"response": report, "success": True}
        except Exception as e:
            return {"response": "❌ Report failed: " + str(e)[:100], "success": False}

    def handle_director_complaint(self, intent_result: dict) -> dict:
        """Route complaint to Director — show failures + suggest action."""
        try:
            from core.agent_performance import get_agent_performance
            data = get_agent_performance(days=7)
            failures = data.get("failures", [])[:5]
            idle = data.get("idle", [])
            lines = [
                "📋 *DIRECTOR — COMPLAINT RECEIVED*",
                "─" * 25,
                "",
            ]
            if failures:
                lines.append("❌ *Recent failures:*")
                for f in failures:
                    lines.append(f"  • {f['agent']}: {f['action']} — {f['status']}")
                lines.append("")
            if idle:
                lines.append("⚠️ *Idle agents:* " + ", ".join(idle))
                lines.append("")
            lines.append("💡 Director ko yeh data milega. Next digest mein failures include honge.")
            lines.append("Specific fix chahiye? Batao kaun sa agent, kya issue.")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": "Complaint logged. " + str(e)[:80], "success": True}

    # ===== PRICING HANDLERS =====

    def handle_price_scan(self, intent_result: dict) -> dict:
        """Trigger live competitor price scan on Amazon India."""
        pt = self.bridge.tools.get("pricing")
        if not pt:
            return {
                "response": (
                    "❌ Price Tracker not loaded.\n"
                    "Check logs for import errors."
                ),
                "success": False,
            }
        result = self.bridge.run_price_scan()
        if result.get("success"):
            return {
                "response": result.get("summary", "✅ Price scan complete."),
                "success": True,
            }
        return {
            "response": "❌ Price scan failed: {}".format(
                result.get("error", "unknown")
            ),
            "success": False,
        }

    def handle_price_report(self, intent_result: dict) -> dict:
        """Show latest competitor pricing comparison."""
        return {
            "response": self.bridge.get_price_report(),
            "success": True,
        }

    def handle_price_update(self, intent_result: dict) -> dict:
        """
        Manually set a competitor price via WhatsApp.
        Format: 'set price ashwagandha himalaya 299'
        """
        msg = (
            intent_result.get("extracted_data", {})
            .get("raw_message", "")
            .lower()
        )

        # Parse: product brand price
        # e.g. "set competitor price ashwagandha himalaya 299"
        price_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:rs|rupees|₹)?$", msg)
        if not price_match:
            return {
                "response": (
                    "📝 *Manual Price Update*\n\n"
                    "Format:\n"
                    "*'set price [product] [brand] [price]'*\n\n"
                    "Example:\n"
                    "_set price ashwagandha himalaya 399_\n"
                    "_set price triphala patanjali 149_"
                ),
                "success": True,
            }

        price = float(price_match.group(1))
        # Extract remaining words for product + brand
        words = re.sub(
            r"(set|competitor|price|update|manual|rs|rupees|\d+)",
            "", msg
        ).split()

        if len(words) >= 2:
            product = words[0].title()
            brand   = words[1]
        elif len(words) == 1:
            product = words[0].title()
            brand   = "competitor"
        else:
            product = "Unknown"
            brand   = "competitor"

        result = self.bridge.update_competitor_price(
            product, brand, price
        )
        return {
            "response": (
                "✅ {}\n"
                "Run *'price scan'* to update full comparison."
            ).format(result.get("message", "Updated")),
            "success": result.get("success", False),
        }

    def _extract_comment_text(self, message: str) -> str:
        """Pull the actual comment from various input formats"""
        if not message:
            return None
            
        separators = [":", "—", "-", "\n"]
        for sep in separators:
            if sep in message:
                parts = message.split(sep, 1)
                if len(parts) > 1:
                    comment = parts[1].strip().strip('"\'')
                    if len(comment) > 5:
                        return comment
        
        # If no separator, strip the command words and return the rest
        stripped = re.sub(
            r"^(check|scan|sentry|review|compliance)\s+(this\s+)?(comment\s*)?",
            "", message, flags=re.IGNORECASE
        ).strip()
        
        return stripped if len(stripped) > 5 else None

    def handle_director_complaint(self, intent):
        """Handle owner complaints about the Director."""
        msg = intent.get("message_text", "")
        try:
            from core.logger import log
            log.log_action("director_complaint_received", "commander", "failed", {"msg": msg[:100]})
        except Exception:
            pass
            
        return {
            "response": (
                "Boss, I hear you and take full responsibility. If I am failing or slow, I need to fix it immediately. "
                "I exist to run Falcon Herbs perfectly. Please tell me exactly what went wrong — is it a bug, a slow response, or a bad decision? "
                "I am logging this complaint internally."
            ),
            "success": True,
        }

    def handle_show_staging_file(self, intent):
        filename = intent.get("extracted_data", {}).get("filename", "")
        if not filename:
            return {"response": "Need filename to show.", "success": False}
        import os
        from core.content_delivery import content_delivery
        path = os.path.join(content_delivery.STAGING_DIR, filename)
        if not os.path.exists(path):
            return {"response": f"❌ File not found: {filename}", "success": False}
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"response": content, "success": True}

    def handle_rewrite_status(self, intent):
        from core.rewrite_staging import rewrite_staging
        summary = rewrite_staging.get_summary()
        pending = rewrite_staging.get_pending()
        if pending:
            summary += "\n\nPending Products: " + ", ".join(map(str, pending[:10]))
            if len(pending) > 10:
                summary += f" ...and {len(pending) - 10} more"
            summary += "\n\nType 'show rewrite <id>' or 'approve product <id>'."
        return {"response": summary, "success": True}

    def handle_show_rewrite(self, intent):
        pid = intent.get("extracted_data", {}).get("product_id")
        if not pid:
            return {"response": "Need product ID. Example: show rewrite 123", "success": False}
        from core.rewrite_staging import rewrite_staging
        entry = rewrite_staging.get_rewrite(int(pid))
        if not entry:
            return {"response": f"❌ No rewrite found for product {pid}", "success": False}
        msg = f"📄 REWRITE FOR PRODUCT {pid} ({entry.get('product_name')})\n\n"
        msg += f"VIOLATIONS FOUND:\n{', '.join(entry.get('violations_found', []))}\n\n"
        msg += f"NEW DESCRIPTION:\n{entry.get('new_description')[:1000]}...\n\n"
        msg += "Type 'approve product <id>' or 'reject product <id>'."
        return {"response": msg, "success": True}

    def handle_approve_rewrite(self, intent):
        pid = intent.get("extracted_data", {}).get("product_id")
        if not pid:
            return {"response": "Need product ID. Example: approve product 123", "success": False}
        from core.rewrite_staging import rewrite_staging
        if not rewrite_staging.approve(int(pid)):
            return {"response": f"❌ Failed to approve {pid} or not found.", "success": False}
        entry = rewrite_staging.get_rewrite(int(pid))
        if self.bridge:
            res = self.bridge.apply_product_rewrite(int(pid), entry.get("new_description", ""))
            if res.get("success"):
                return {"response": f"✅ Approved and live on site for product {pid}!", "success": True}
        return {"response": f"✅ Approved in staging for {pid} but couldn't apply to live site.", "success": True}

    def handle_approve_all_rewrites(self, intent):
        """Approve all pending rewrites in batches of 10."""
        from core.rewrite_staging import rewrite_staging
        pending = list(rewrite_staging.get_pending())
        
        if not pending:
            return {"response": "Bhai, koi pending rewrite nahi hai.", "success": True}
        
        # Use simple return first, then background batch if there are many
        if len(pending) <= 3:
            count = 0
            for pid in pending:
                entry = rewrite_staging.get_rewrite(int(pid))
                if self.bridge and entry:
                    res = self.bridge.apply_product_rewrite(int(pid), entry.get("new_description", ""))
                    if res.get("success"):
                        rewrite_staging.approve(int(pid))
                        count += 1
                    # else: leave in pending so it can be retried
                else:
                    # No bridge or no entry — skip, don't approve
                    pass
            return {"response": f"✅ Approved and applied {count}/{len(pending)} products.", "success": True}
        
        # Large batch -> return immediate response and background the rest
        # We'll need a way to send follow-up messages. Handlers usually don't have safe_send.
        # But we can import it or use the bridge if it supports notifications.
        
        return {
            "response": f"🚀 {len(pending)} products approve ho rahe hain (Batches of 10). Main status update bhejta rahunga.",
            "success": True,
            "action": "batch_approve_all" # Lead commander to handle the background part
        }

    def handle_reject_rewrite(self, intent):
        pid = intent.get("extracted_data", {}).get("product_id")
        if not pid:
            return {"response": "Need product ID.", "success": False}
        from core.rewrite_staging import rewrite_staging
        if rewrite_staging.reject(int(pid)):
            return {"response": f"❌ Rejected product {pid} rewrite.", "success": True}
        return {"response": f"Could not find rewrite for {pid}.", "success": False}

    def handle_fix_violations(self, intent):
        """Handle 'sab fix karo' by starting a batch scan."""
        sender = intent.get("sender", "owner")
        msg = intent.get("message_text", "").lower()
        
        # Check context if the command is very vague
        if self.memory and ("sab fix" in msg or "fix karo" in msg):
            history = self.memory.get_recent_messages(sender, limit=5)
            # If recent messages mention 'health', 'violations', or 'rewarding', assume health
            context_text = " ".join([m.get("content", "").lower() for m in history])
            if any(k in context_text for k in ["health", "violation", "describe", "product", "rewrite"]):
                return self.handle_fix_violations_batch({"extracted_data": {"batch_size": 10}})
        
        # Default or if context matched health
        if "sab fix karo" in msg or "fix all" in msg or "violations fix karo" in msg or "apply batch" in msg:
            return self.handle_fix_violations_batch({"extracted_data": {"batch_size": 5}})
        return self.handle_fix_violations_batch(intent)
        
    def handle_fix_violations_batch(self, intent):
        batch = intent.get("extracted_data", {}).get("batch_size", 5)
        if not self.bridge:
            return {"response": "Bridge offline.", "success": False}
        res = self.bridge.scan_and_rewrite_violations(batch_size=batch)
        if res.get("success"):
            return {
                "response": f"✅ Batch Complete: Scanned {res.get('scanned')} products.\n"
                            f"Identified {len(res.get('staged_ids', []))} for rewrites.\n"
                            "Type 'rewrite status' to see.",
                "success": True
            }
        return {"response": f"❌ Batch scan failed: {res.get('error')}", "success": False}

    # ═══════════════════════════════════════════════════════════════════════════
    # STORE INTELLIGENCE HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def handle_low_stock_alert(self, intent) -> dict:
        """Check products with qty <= 5 or out_of_stock status."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"response": "❌ WooCommerce not connected.", "success": False}
            products = woo.get_all_products(save=False)
            if isinstance(products, dict):
                products = products.get("products", [])
            low, out = [], []
            for p in products:
                qty = p.get("stock_quantity") or 0
                status = p.get("stock_status", "")
                name = p.get("name", "Unknown")[:40]
                pid = p.get("id", "")
                if status == "outofstock":
                    out.append(f"🔴 P{pid} {name}")
                elif qty is not None and int(qty) <= 5:
                    low.append(f"🟡 P{pid} {name} — Qty: {qty}")
            lines = ["📦 *STOCK ALERT REPORT*", "─────────────────────"]
            if out:
                lines.append(f"\n*OUT OF STOCK ({len(out)}):*")
                lines += out[:10]
            if low:
                lines.append(f"\n*LOW STOCK ≤5 ({len(low)}):*")
                lines += low[:10]
            if not out and not low:
                lines.append("✅ Sabhi products ka stock theek hai!")
            else:
                lines.append(f"\n💡 WooCommerce pe jao aur stock update karo.")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Stock check failed: {e}", "success": False}

    def handle_refund_check(self, intent) -> dict:
        """Check recent refunds, cancellations and failed orders."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"response": "❌ WooCommerce not connected.", "success": False}
            orders_data = woo.get_orders(days_back=30, save=False)
            if isinstance(orders_data, dict):
                orders = orders_data.get("orders", [])
            else:
                orders = []
            bad_statuses = {"refunded", "cancelled", "failed"}
            bad_orders = [o for o in orders if o.get("status", "") in bad_statuses]
            lines = ["💸 *REFUNDS & CANCELLATIONS (Last 30 days)*", "─────────────────────"]
            counts = {}
            total_lost = 0.0
            for o in bad_orders:
                s = o.get("status", "")
                counts[s] = counts.get(s, 0) + 1
                try:
                    total_lost += float(o.get("total", 0))
                except Exception:
                    pass
            if not bad_orders:
                lines.append("✅ Last 30 days mein koi refund/cancellation nahi!")
            else:
                for s, c in counts.items():
                    icon = "🔴" if s == "refunded" else "🟡" if s == "cancelled" else "⚫"
                    lines.append(f"{icon} {s.capitalize()}: {c} orders")
                lines.append(f"\n💰 Total Revenue Lost: ₹{total_lost:,.0f}")
                lines.append(f"\n📋 *Recent ({min(5, len(bad_orders))}) bad orders:*")
                for o in bad_orders[:5]:
                    lines.append(f"• #{o.get('number','?')} — {o.get('status','')} — ₹{o.get('total','0')}")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Refund check failed: {e}", "success": False}

    def handle_product_performance(self, intent) -> dict:
        """Top selling products this month by revenue and quantity."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"response": "❌ WooCommerce not connected.", "success": False}
            orders_data = woo.get_orders(days_back=30, save=False)
            if isinstance(orders_data, dict):
                orders = orders_data.get("orders", [])
            else:
                orders = []
            sales = {}
            for o in orders:
                if o.get("status") in {"completed", "processing"}:
                    for item in o.get("line_items", []):
                        name = item.get("name", "Unknown")[:35]
                        qty = int(item.get("quantity", 0))
                        rev = float(item.get("total", 0))
                        if name not in sales:
                            sales[name] = {"qty": 0, "rev": 0.0}
                        sales[name]["qty"] += qty
                        sales[name]["rev"] += rev
            if not sales:
                return {"response": "❌ Last 30 days mein koi completed orders nahi mila.", "success": False}
            sorted_by_rev = sorted(sales.items(), key=lambda x: x[1]["rev"], reverse=True)[:8]
            lines = ["🏆 *TOP PRODUCTS — Last 30 Days*", "─────────────────────"]
            for i, (name, data) in enumerate(sorted_by_rev, 1):
                lines.append(f"{i}. {name}\n   Sold: {data['qty']} units | Revenue: ₹{data['rev']:,.0f}")
            total_rev = sum(d["rev"] for _, d in sorted_by_rev)
            lines.append(f"\n💰 *Top 8 Revenue: ₹{total_rev:,.0f}*")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Product performance failed: {e}", "success": False}

    def handle_customer_segments(self, intent) -> dict:
        """Customer breakdown: new vs returning, top cities, avg order value."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"response": "❌ WooCommerce not connected.", "success": False}
            orders_data = woo.get_orders(days_back=90, save=False)
            if isinstance(orders_data, dict):
                orders = [o for o in orders_data.get("orders", []) if o.get("status") in {"completed", "processing"}]
            else:
                orders = []
            if not orders:
                return {"response": "❌ No completed orders in last 90 days.", "success": False}
            cities, customer_orders = {}, {}
            total_rev = 0.0
            for o in orders:
                email = o.get("billing", {}).get("email", "").lower()
                city = o.get("billing", {}).get("city", "Unknown")
                cities[city] = cities.get(city, 0) + 1
                customer_orders[email] = customer_orders.get(email, 0) + 1
                try:
                    total_rev += float(o.get("total", 0))
                except Exception:
                    pass
            new_customers = sum(1 for v in customer_orders.values() if v == 1)
            returning = len(customer_orders) - new_customers
            avg_order = total_rev / len(orders) if orders else 0
            top_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:5]
            lines = [
                "👥 *CUSTOMER REPORT — Last 90 Days*",
                "─────────────────────",
                f"📊 Total Unique Buyers: {len(customer_orders)}",
                f"🆕 New Customers: {new_customers}",
                f"🔁 Returning Customers: {returning}",
                f"💰 Avg Order Value: ₹{avg_order:,.0f}",
                f"\n🏙️ *Top Cities:*",
            ]
            for city, count in top_cities:
                lines.append(f"  • {city}: {count} orders")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Customer segments failed: {e}", "success": False}

    def handle_growth_report(self, intent) -> dict:
        """Month-over-month growth: orders, revenue, new customers."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"response": "❌ WooCommerce not connected.", "success": False}
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            # Current month range
            start_this = now.replace(day=1, hour=0, minute=0, second=0)
            # Last month range
            start_last = (start_this - timedelta(days=1)).replace(day=1)
            end_last = start_this
            orders_data = woo.get_orders(days_back=62, save=False)
            if isinstance(orders_data, dict):
                all_orders = [o for o in orders_data.get("orders", []) if o.get("status") in {"completed", "processing"}]
            else:
                all_orders = []
            def _parse_dt(o):
                try:
                    return datetime.fromisoformat(o.get("date_created", "").replace("Z", ""))
                except Exception:
                    return None
            this_month = [o for o in all_orders if _parse_dt(o) and _parse_dt(o) >= start_this]
            last_month = [o for o in all_orders if _parse_dt(o) and start_last <= _parse_dt(o) < end_last]
            def _stats(orders):
                rev = sum(float(o.get("total", 0)) for o in orders)
                customers = len(set(o.get("billing", {}).get("email", "") for o in orders))
                return len(orders), rev, customers
            t_ord, t_rev, t_cust = _stats(this_month)
            l_ord, l_rev, l_cust = _stats(last_month)
            def _pct(new, old):
                if old == 0:
                    return "N/A" if new == 0 else "🆕 New"
                pct = ((new - old) / old) * 100
                arrow = "📈" if pct >= 0 else "📉"
                return f"{arrow} {pct:+.1f}%"
            lines = [
                "📊 *MONTH-OVER-MONTH GROWTH*",
                f"This Month vs Last Month",
                "─────────────────────",
                f"🛒 Orders:    {t_ord} vs {l_ord}  {_pct(t_ord, l_ord)}",
                f"💰 Revenue:   ₹{t_rev:,.0f} vs ₹{l_rev:,.0f}  {_pct(t_rev, l_rev)}",
                f"👥 Customers: {t_cust} vs {l_cust}  {_pct(t_cust, l_cust)}",
            ]
            if t_rev > l_rev:
                lines.append(f"\n✅ Alhamdullilah! Revenue up ₹{t_rev - l_rev:,.0f} this month.")
            elif t_rev < l_rev:
                lines.append(f"\n⚠️ Revenue down ₹{l_rev - t_rev:,.0f}. Marketing boost needed.")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Growth report failed: {e}", "success": False}

    def handle_gst_report(self, intent) -> dict:
        """Monthly GST breakdown from WooCommerce orders (18% GST assumed)."""
        try:
            woo = self.bridge.tools.get("woocommerce")
            if not woo:
                return {"response": "❌ WooCommerce not connected.", "success": False}
            from datetime import datetime
            now = datetime.utcnow()
            orders_data = woo.get_orders(days_back=35, save=False)
            if isinstance(orders_data, dict):
                orders = [o for o in orders_data.get("orders", []) if o.get("status") in {"completed", "processing"}]
            else:
                orders = []
            if not orders:
                return {"response": "❌ No completed orders this month.", "success": False}
            # Filter current month
            month_orders = []
            for o in orders:
                try:
                    dt = datetime.fromisoformat(o.get("date_created", "").replace("Z", ""))
                    if dt.month == now.month and dt.year == now.year:
                        month_orders.append(o)
                except Exception:
                    pass
            taxable = sum(float(o.get("total", 0)) for o in month_orders)
            # Reverse-calculate GST from total (GST-inclusive)
            gst_rate = 0.18
            base = taxable / (1 + gst_rate)
            total_gst = taxable - base
            cgst = total_gst / 2
            sgst = total_gst / 2
            month_name = now.strftime("%B %Y")
            lines = [
                f"🧾 *GST REPORT — {month_name}*",
                "─────────────────────",
                f"📦 Orders (Completed): {len(month_orders)}",
                f"💰 Gross Revenue (GST-inclusive): ₹{taxable:,.2f}",
                f"📊 Base Amount (without GST): ₹{base:,.2f}",
                f"─────────────────────",
                f"GST @ 18%: ₹{total_gst:,.2f}",
                f"  CGST (9%): ₹{cgst:,.2f}",
                f"  SGST (9%): ₹{sgst:,.2f}",
                f"─────────────────────",
                f"⚠️ Note: This assumes standard 18% GST rate.",
                f"For inter-state orders, IGST applies instead of CGST+SGST.",
                f"Verify with your CA before filing.",
            ]
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ GST report failed: {e}", "success": False}

    # ═══════════════════════════════════════════════════════════════════════════
    # CONTENT & MARKETING HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def handle_festival_campaign(self, intent) -> dict:
        """Create festival-specific marketing campaign."""
        try:
            msg = (intent.get("message_text") or "").lower()
            festivals = {
                "holi": ("Holi", "March", "colors, renewal, spring, joy"),
                "diwali": ("Diwali", "October/November", "light, prosperity, gifting, new beginnings"),
                "navratri": ("Navratri", "October", "energy, shakti, fasting, wellness"),
                "eid": ("Eid", "seasonal", "celebration, sharing, gratitude, community"),
                "raksha": ("Raksha Bandhan", "August", "love, protection, family bonds"),
                "independence": ("Independence Day", "August 15", "pride, health, nation"),
                "republic": ("Republic Day", "January 26", "unity, wellness for all"),
            }
            detected = next((v for k, v in festivals.items() if k in msg), ("Festival", "upcoming", "celebration, tradition, wellness"))
            fest_name, fest_time, themes = detected
            from core.ai_client import call_ai
            prompt = f"""Create a complete festival marketing campaign for Falcon Herbs (authentic Ayurvedic herbs brand, India) for {fest_name}.

Themes for this festival: {themes}

Generate:
1. **WHATSAPP MESSAGE** (for broadcast, 150 words max, Hinglish/English, warm & festive)
2. **INSTAGRAM CAPTION** (200 words, emojis, festive vibe, product tie-in, 5 relevant hashtags)
3. **FACEBOOK POST** (150 words, slightly formal, community feel)
4. **OFFER IDEAS** (2-3 festival discount/bundle ideas that make sense for Ayurvedic herbs)
5. **EMAIL SUBJECT LINE** (5 options)

IMPORTANT: All content must be FSSAI compliant — no disease cure claims. Use words like 'support', 'wellness', 'traditionally used'."""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {"response": f"🎉 *{fest_name.upper()} CAMPAIGN — FALCON HERBS*\n\n{response}", "success": True}
            return {"response": f"❌ Campaign generation failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ Festival campaign error: {e}", "success": False}

    def handle_season_strategy(self, intent) -> dict:
        """Monthly ayurvedic season strategy and product focus plan."""
        try:
            from datetime import datetime
            from core.ai_client import call_ai
            month = datetime.now().strftime("%B")
            prompt = f"""You are an expert Ayurvedic business strategist for Falcon Herbs (authentic herb brand, India, {month}).

Create a concise monthly strategy covering:
1. **AYURVEDIC SEASON** this month (Vata/Pitta/Kapha dominance + why)
2. **TOP 5 PRODUCTS TO PUSH** (from a typical Ayurvedic herb catalog — Ashwagandha, Triphala, Tulsi, Shatavari, Brahmi, etc.) — explain why each fits this season
3. **CONTENT FOCUS** (3 content themes that will resonate this month)
4. **MARKETING ANGLE** (1 main message for this month)
5. **QUICK ACTION LIST** (3 things to do this week)

Be specific to Indian climate and {month}. Keep it actionable and WhatsApp-friendly (use bullets)."""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {"response": f"🌿 *{month.upper()} STRATEGY — FALCON HERBS*\n\n{response}", "success": True}
            return {"response": "❌ Strategy generation failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ Season strategy error: {e}", "success": False}

    def handle_product_faq(self, intent) -> dict:
        """Generate FAQ Q&A pairs for a product (SEO + AEO boost)."""
        try:
            from core.ai_client import call_ai
            msg = intent.get("message_text", "")
            # Extract product name from message
            import re as _re
            product_match = _re.search(r"(?:for|ke\s+liye|about|about\s+the\s+)?([A-Za-z\s]+?)(?:\s+(?:ka|ke|ki|faq|FAQ|sawaal|question)|$)", msg, _re.I)
            product = product_match.group(1).strip() if product_match else "Ashwagandha"
            product = product.strip().title()
            prompt = f"""Generate 8 FAQ (Frequently Asked Questions) pairs for {product} for the Falcon Herbs website.

Format each Q&A pair as:
Q: [Question a customer would ask]
A: [Concise, accurate, FSSAI-compliant answer — no disease cure claims]

Requirements:
- Mix of: usage questions, dosage, benefits, safety, sourcing, Ayurvedic context
- Answers must be 2-4 sentences max (good for Google AI Overviews / AEO)
- No claims like "cures", "treats disease", "FDA approved"
- Use: "traditionally used to support", "may support", "as per Ayurveda"
- Include 1-2 questions comparing to similar herbs

These FAQs will be added to the product page for SEO and AEO (Google AI snippets)."""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {"response": f"❓ *FAQ — {product}*\n(Add these to your product page)\n\n{response}", "success": True}
            return {"response": "❌ FAQ generation failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ Product FAQ error: {e}", "success": False}

    def handle_trending_topics(self, intent) -> dict:
        """Get trending ayurvedic topics this week via DuckDuckGo/Serper."""
        try:
            from core.serper_client import search
            from core.ai_client import call_ai
            queries = [
                "ayurveda trending 2026 India",
                "best selling ayurvedic herbs India this week",
                "ayurvedic wellness trending topics India",
            ]
            all_snippets = []
            for q in queries:
                result = search(q, source="trending")
                for item in result.get("organic", [])[:4]:
                    snippet = item.get("snippet", "")
                    if snippet:
                        all_snippets.append(snippet)
            if not all_snippets:
                return {"response": "❌ Search results empty. DuckDuckGo ya Serper unavailable.", "success": False}
            combined = "\n".join(all_snippets[:12])
            prompt = f"""Based on these search results about trending Ayurveda topics in India:

{combined}

Extract and list:
1. **TOP 5 TRENDING TOPICS** this week (herb names, wellness trends, popular searches)
2. **CONTENT OPPORTUNITY** for each (what Falcon Herbs should post about it)
3. **BEST HASHTAGS** for each topic (3 per topic)

Format as WhatsApp-friendly bullets. Be specific and actionable."""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {"response": f"🔥 *TRENDING THIS WEEK — AYURVEDA*\n\n{response}", "success": True}
            return {"response": "❌ Trend analysis failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ Trending topics error: {e}", "success": False}

    def handle_content_repurpose(self, intent) -> dict:
        """Repurpose latest blog post into multiple content formats."""
        try:
            import glob as _glob, os
            from core.ai_client import call_ai
            # Find latest blog draft
            drafts_dir = "data/content/drafts"
            blog_files = sorted(_glob.glob(os.path.join(drafts_dir, "blog_*.json")), reverse=True)
            if not blog_files:
                return {"response": "❌ Koi blog draft nahi mila. Pehle 'blog likho' karo.", "success": False}
            with open(blog_files[0], encoding="utf-8") as f:
                draft = json.load(f)
            title = draft.get("title", "Ayurvedic Blog Post")
            content = draft.get("content", draft.get("body", ""))
            import re as _re
            clean = _re.sub(r'<[^>]+>', '', content)[:2000]
            prompt = f"""Repurpose this blog post for Falcon Herbs into multiple formats:

BLOG TITLE: {title}
CONTENT EXCERPT: {clean}

Generate ALL of these:
1. **INSTAGRAM CAPTION** (150 words, hook + value + CTA, 7 hashtags)
2. **FACEBOOK POST** (100 words, conversational)
3. **META DESCRIPTION** (155 chars, SEO-optimized)
4. **5 FAQ QUESTIONS** (from the blog content, for product/blog page)
5. **WHATSAPP ONE-LINER** (1 sentence teaser to send customers)
6. **EMAIL SUBJECT LINE** (3 options)

All FSSAI compliant — no disease cure claims."""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {"response": f"♻️ *REPURPOSED: {title[:40]}*\n\n{response}", "success": True}
            return {"response": "❌ Repurpose failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ Content repurpose error: {e}", "success": False}

    def handle_heropost_week(self, intent) -> dict:
        """Generate 7-day content plan with all posts ready for HeroPost."""
        try:
            from core.ai_client import call_ai
            from datetime import datetime, timedelta
            today = datetime.now()
            days = [(today + timedelta(days=i)).strftime("%A, %d %b") for i in range(7)]
            prompt = f"""Create a 7-day Instagram + Facebook content plan for Falcon Herbs (authentic Ayurvedic herbs, India).

Starting from: {days[0]}
Days: {', '.join(days)}

For each day provide:
**Day N — [Day Name, Date]**
Topic: [topic]
Caption: [60-word Instagram caption with hook]
Hashtags: #tag1 #tag2 #tag3 #tag4 #tag5
Image Idea: [simple visual description for HeroPost]

Content mix (use this variety):
- Day 1: Product highlight (Ashwagandha or top seller)
- Day 2: Ayurvedic tip / wellness fact
- Day 3: Behind the scenes / sourcing story
- Day 4: Customer benefit story (FSSAI compliant)
- Day 5: Festival/seasonal content OR trending herb
- Day 6: Product comparison / Ayurveda myth bust
- Day 7: Weekend wellness routine

FSSAI: No cure claims. Use 'supports', 'traditionally used', 'wellness'."""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {"response": f"📅 *7-DAY HEROPOST PLAN*\n{days[0]} → {days[-1]}\n\n{response}", "success": True}
            return {"response": "❌ Week plan generation failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ HeroPost week plan error: {e}", "success": False}

    def handle_whatsapp_broadcast_draft(self, intent) -> dict:
        """Draft a WhatsApp broadcast/bulk promotional message."""
        try:
            from core.ai_client import call_ai
            msg = intent.get("message_text", "")
            prompt = f"""Write 3 different WhatsApp broadcast messages for Falcon Herbs customers.
User context: "{msg}"

Each message should be:
- 80-120 words max (WhatsApp broadcast length)
- Hinglish (mix of Hindi + English, informal, warm)
- Include: product highlight, benefit, offer/CTA
- End with: "Reply 'ORDER' to buy" or similar CTA
- FSSAI compliant (no cure claims)

Format:
**Option 1 — [tone: e.g. "Warm/Festive"]**
[message]

**Option 2 — [tone: e.g. "Urgent/Sale"]**
[message]

**Option 3 — [tone: e.g. "Educational/Trust"]**
[message]"""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {"response": f"📢 *WHATSAPP BROADCAST DRAFTS*\n\n{response}\n\n💡 Copy the best option → paste in WhatsApp Broadcast List", "success": True}
            return {"response": "❌ Broadcast draft failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ Broadcast draft error: {e}", "success": False}

    def handle_testimonial_campaign(self, intent) -> dict:
        """Generate review collection campaign templates."""
        try:
            from core.ai_client import call_ai
            prompt = """Create a complete review/testimonial collection campaign for Falcon Herbs:

1. **WHATSAPP MESSAGE TO PAST CUSTOMERS** (80 words, Hinglish, friendly, asking for honest review)
2. **EMAIL SUBJECT LINES** (5 options for review request email)
3. **EMAIL BODY** (150 words, grateful tone, link placeholder [REVIEW_LINK])
4. **FOLLOW-UP MESSAGE** (if no response after 3 days, 50 words)
5. **THANK YOU MESSAGE** (after they leave review, 40 words)
6. **INCENTIVE IDEAS** (3 ethical ways to encourage reviews — discount, points, etc.)

Keep all messages warm, genuine, FSSAI compliant. No fake review tactics."""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {"response": f"⭐ *REVIEW COLLECTION CAMPAIGN*\n\n{response}", "success": True}
            return {"response": "❌ Testimonial campaign failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ Testimonial campaign error: {e}", "success": False}

    # ═══════════════════════════════════════════════════════════════════════════
    # INFRASTRUCTURE / NETWORKSOLUTIONS HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def handle_ssl_check(self, intent) -> dict:
        """Check SSL certificate expiry for the website."""
        try:
            import ssl, socket
            from datetime import datetime
            import os
            site_url = os.getenv("WP_SITE_URL", "falconherbs.com").replace("https://", "").replace("http://", "").rstrip("/")
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=site_url) as s:
                s.settimeout(10)
                s.connect((site_url, 443))
                cert = s.getpeercert()
            expire_str = cert.get("notAfter", "")
            expire_dt = datetime.strptime(expire_str, "%b %d %H:%M:%S %Y %Z")
            days_left = (expire_dt - datetime.utcnow()).days
            icon = "✅" if days_left > 30 else ("⚠️" if days_left > 7 else "🔴")
            issued_to = dict(x[0] for x in cert.get("subject", []))
            lines = [
                f"🔒 *SSL CERTIFICATE — {site_url}*",
                "─────────────────────",
                f"Issued To: {issued_to.get('commonName', site_url)}",
                f"Expires: {expire_dt.strftime('%d %b %Y')}",
                f"{icon} Days Remaining: {days_left} days",
            ]
            if days_left <= 30:
                lines.append(f"\n⚠️ Certificate expires soon! Renew via your hosting panel.")
            else:
                lines.append(f"\n✅ SSL is valid. No action needed.")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ SSL check failed: {e}", "success": False}

    def handle_domain_health(self, intent) -> dict:
        """Check domain DNS resolution and basic reachability."""
        try:
            import socket, os, requests as _req
            site_url = os.getenv("WP_SITE_URL", "https://falconherbs.com").replace("https://", "").replace("http://", "").rstrip("/")
            lines = [f"🌐 *DOMAIN HEALTH — {site_url}*", "─────────────────────"]
            # DNS check
            try:
                ip = socket.gethostbyname(site_url)
                lines.append(f"✅ DNS: Resolving → {ip}")
            except Exception:
                lines.append(f"🔴 DNS: FAILED to resolve {site_url}")
            # HTTP check
            try:
                r = _req.get(f"https://{site_url}", timeout=10, allow_redirects=True)
                lines.append(f"✅ HTTP: {r.status_code} ({r.elapsed.total_seconds():.2f}s)")
            except Exception as e:
                lines.append(f"🔴 HTTP: Failed — {str(e)[:60]}")
            # Blacklist hint
            lines.append(f"\n💡 For domain expiry: check your registrar panel (GoDaddy/Namecheap etc.)")
            lines.append(f"💡 For spam blacklist: check MXToolbox.com → Blacklist check")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Domain health check failed: {e}", "success": False}

    def handle_email_inbox_check(self, intent) -> dict:
        """Check NetworkSolutions business email inbox via IMAP."""
        try:
            import os, imaplib, email as _email
            from email.header import decode_header
            imap_host = os.getenv("NS_IMAP_HOST", "")
            imap_user = os.getenv("NS_EMAIL_USER", "")
            imap_pass = os.getenv("NS_EMAIL_PASS", "")
            if not all([imap_host, imap_user, imap_pass]):
                return {
                    "response": (
                        "⚙️ *NetworkSolutions Email Setup Required*\n\n"
                        "Add to your `.env` file:\n"
                        "```\nNS_IMAP_HOST=mail.yourdomain.com\n"
                        "NS_EMAIL_USER=info@falconherbs.com\n"
                        "NS_EMAIL_PASS=yourpassword\n```\n\n"
                        "IMAP host mila NetworkSolutions email settings mein."
                    ),
                    "success": False
                }
            mail = imaplib.IMAP4_SSL(imap_host, 993)
            mail.login(imap_user, imap_pass)
            mail.select("INBOX")
            _, data = mail.search(None, "UNSEEN")
            ids = data[0].split()
            if not ids:
                mail.logout()
                return {"response": "📬 Inbox empty — koi naya email nahi.", "success": True}
            lines = [f"📧 *INBOX — {len(ids)} unread email(s)*", "─────────────────────"]
            for eid in ids[-8:]:
                _, msg_data = mail.fetch(eid, "(RFC822)")
                msg = _email.message_from_bytes(msg_data[0][1])
                subject_raw, enc = decode_header(msg.get("Subject", "No Subject"))[0]
                subject = subject_raw.decode(enc or "utf-8") if isinstance(subject_raw, bytes) else subject_raw
                sender = msg.get("From", "Unknown")[:50]
                date = msg.get("Date", "")[:20]
                lines.append(f"• {date}\n  From: {sender}\n  Sub: {subject[:60]}")
            mail.logout()
            lines.append(f"\n💡 Reply chahiye? 'Is email ka jawab likho: [subject]' bolo.")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Email inbox check failed: {e}", "success": False}

    def handle_email_blast(self, intent) -> dict:
        """Draft a bulk email campaign (requires approval before send)."""
        try:
            from core.ai_client import call_ai
            msg = intent.get("message_text", "")
            prompt = f"""Write a professional marketing email for Falcon Herbs customers.
Context from user: "{msg}"

Generate:
**SUBJECT LINE:** [compelling subject]

**EMAIL BODY:**
[Professional HTML-friendly email, 200 words, includes:
- Warm greeting
- Main offer/announcement
- 2-3 product benefits (FSSAI compliant)
- Clear CTA button text: [SHOP NOW / LEARN MORE]
- Signature: Falcon Herbs Team]

FSSAI compliant — no cure claims. Warm, trustworthy tone."""
            response = call_ai("content", [{"role": "user", "content": prompt}])
            if response:
                return {
                    "response": (
                        f"📧 *EMAIL CAMPAIGN DRAFT*\n\n{response}\n\n"
                        "─────────────────────\n"
                        "✅ To send via NetworkSolutions:\n"
                        "1. Login → Email Marketing → New Campaign\n"
                        "2. Copy this content into the editor\n"
                        "3. Select your subscriber list\n"
                        "4. Preview → Send\n\n"
                        "💡 For direct send via SMTP, add NS_IMAP_HOST + credentials to .env"
                    ),
                    "success": True
                }
            return {"response": "❌ Email draft failed.", "success": False}
        except Exception as e:
            return {"response": f"❌ Email blast error: {e}", "success": False}

    # ═══════════════════════════════════════════════════════════════════════════
    # MULTI-SITE MANAGEMENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _load_sites(self) -> dict:
        """Load sites registry from config/sites.json."""
        import os
        sites_path = os.path.join("config", "sites.json")
        if not os.path.exists(sites_path):
            return {"active_site": "falconherbs", "sites": {}}
        try:
            with open(sites_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"active_site": "falconherbs", "sites": {}}

    def _save_sites(self, data: dict):
        """Save sites registry."""
        import os
        os.makedirs("config", exist_ok=True)
        with open(os.path.join("config", "sites.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def handle_list_sites(self, intent) -> dict:
        """List all websites managed by the agency."""
        try:
            data = self._load_sites()
            sites = data.get("sites", {})
            active = data.get("active_site", "")
            if not sites:
                return {
                    "response": (
                        "🌐 *MANAGED WEBSITES*\n\n"
                        "Currently managing: 1 site\n\n"
                        "✅ *falconherbs* (active)\n"
                        "   URL: falconherbs.com\n"
                        "   Status: Live & monitored\n\n"
                        "💡 Naya site add karne ke liye: 'naya site add karo'"
                    ),
                    "success": True
                }
            lines = ["🌐 *MANAGED WEBSITES*", "─────────────────────"]
            for key, site in sites.items():
                icon = "✅" if key == active else "⚪"
                lines.append(f"{icon} *{key}* {'(ACTIVE)' if key == active else ''}")
                lines.append(f"   URL: {site.get('url', 'N/A')}")
                lines.append(f"   Niche: {site.get('niche', 'N/A')}")
                lines.append("")
            lines.append(f"Total: {len(sites)} site(s)")
            lines.append("💡 Switch karne ke liye: 'site [name] pe switch karo'")
            lines.append("💡 Add karne ke liye: 'naya site add karo'")
            return {"response": "\n".join(lines), "success": True}
        except Exception as e:
            return {"response": f"❌ Sites list error: {e}", "success": False}

    def handle_switch_site(self, intent) -> dict:
        """Switch active website."""
        try:
            import re as _re
            msg = intent.get("message_text", "")
            data = self._load_sites()
            sites = data.get("sites", {})
            if not sites:
                return {"response": "❌ Sirf 1 site hai abhi. Naya site add karo pehle.", "success": False}
            # Try to extract site name from message
            site_name = None
            for key in sites:
                if key.lower() in msg.lower():
                    site_name = key
                    break
            if not site_name:
                # Try number
                num_match = _re.search(r'\b(\d+)\b', msg)
                if num_match:
                    idx = int(num_match.group(1)) - 1
                    keys = list(sites.keys())
                    if 0 <= idx < len(keys):
                        site_name = keys[idx]
            if not site_name:
                site_list = "\n".join(f"{i+1}. {k} — {v.get('url','')}" for i, (k, v) in enumerate(sites.items()))
                return {
                    "response": f"❓ Kaun sa site?\n\n{site_list}\n\nBolo: 'site 1 pe switch karo'",
                    "success": False
                }
            data["active_site"] = site_name
            self._save_sites(data)
            site = sites[site_name]
            return {
                "response": (
                    f"✅ *Switched to: {site_name}*\n"
                    f"URL: {site.get('url', 'N/A')}\n"
                    f"Niche: {site.get('niche', 'N/A')}\n\n"
                    f"Ab sabhi commands is site pe apply honge."
                ),
                "success": True
            }
        except Exception as e:
            return {"response": f"❌ Site switch failed: {e}", "success": False}

    def handle_add_site(self, intent) -> dict:
        """Guide user through adding a new website to agency management."""
        try:
            return {
                "response": (
                    "🌐 *ADD NEW WEBSITE TO AGENCY*\n\n"
                    "Mujhe yeh details bhejo (ek message mein):\n\n"
                    "```\nSITE_NAME: (short name, e.g. 'myshop')\n"
                    "URL: https://yoursite.com\n"
                    "WC_KEY: ck_xxxxxxxx\n"
                    "WC_SECRET: cs_xxxxxxxx\n"
                    "WP_USER: your_wp_username\n"
                    "WP_PASS: your_wp_app_password\n"
                    "NICHE: (e.g. 'organic food', 'ayurvedic herbs')\n"
                    "CURRENCY: INR\n```\n\n"
                    "📋 *WooCommerce keys kahan milenge?*\n"
                    "WooCommerce → Settings → Advanced → REST API → Add Key\n\n"
                    "📋 *WordPress App Password?*\n"
                    "WP Admin → Users → Profile → Application Passwords\n\n"
                    "Jab yeh details bhejoge, main site add karke saari files setup kar dunga."
                ),
                "success": True
            }
        except Exception as e:
            return {"response": f"❌ Add site error: {e}", "success": False}

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
