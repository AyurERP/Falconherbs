"""
Falcon Agency — Capability Registry
====================================
Real map of what the agency CAN and CANNOT do.
Used for scope check (GAP 1) and DirectorBrain self-awareness (GAP 4).

Every in_scope entry maps to ACTUAL tools that exist in the codebase.
Every out_of_scope entry has a reason (what we lack).
"""

from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
#  IN SCOPE — Real capabilities with actual tool references
# ─────────────────────────────────────────────────────────────────────────────

AGENCY_CAPABILITIES: Dict = {
    "in_scope": {
        "seo_optimization": {
            "description": "Website SEO audit, keyword analysis, content gaps",
            "agent": "strategist",
            "tools": [
                "StrategistAgent.handle(seo_audit)",
                "StrategistAgent.handle(analyse_keywords)",
                "IntegrationBridge.run_aeo_scan",
                "AEOAgent.run_monthly_scan",
                "AEOAgent._search_serper",
            ],
            "intents": ["seo_audit", "keyword_analysis", "aeo_scan", "aeo_report"],
            "real": True,
        },
        "health_claims_audit": {
            "description": "Scan and rewrite health claims for FDA/FSSAI compliance",
            "agent": "developer",
            "tools": [
                "IntegrationBridge.run_health_scan",
                "HealthClaimsScanner.scan_page",
                "HealthClaimsScanner.full_scan",
                "HealthRewriter.rewrite_flagged",
                "HealthRewriter.rewrite_blog_post",
                "HealthRewriter.rewrite_pages",
                "IntegrationBridge.run_push_all_rewrites",
                "IntegrationBridge.run_push_all_blog_fixes",
                "IntegrationBridge.run_push_all_page_fixes",
            ],
            "intents": ["health_scan", "sab_fix_karo", "push_all_rewrites", "rewrite_products"],
            "real": True,
        },
        "content_creation": {
            "description": "Generate and publish weekly content (blogs, social, product descriptions)",
            "agent": "media",
            "tools": [
                "ContentPipeline.generate_this_weeks_content",
                "ContentPipeline.generate_content_calendar",
                "ContentWorkflow.generate_and_queue",
                "WordPressPublisher.publish_draft",
                "ImageGenerator.generate_blog_banner",
                "ImageGenerator.generate_social_image",
            ],
            "intents": ["create_blog", "create_social", "generate_weekly", "content_status"],
            "real": True,
        },
        "graphic_design": {
            "description": "Generate branded images for social (NVIDIA), product photos, HeroPost-ready graphics",
            "agent": "content_producer",
            "tools": [
                "ContentProducer.generate_weekly_package",
                "ImageGenerator.generate",
                "ImageGenerator.generate_product_image",
                "ImageGenerator.generate_with_text_overlay",
            ],
            "intents": ["content_package", "image_banao", "hafte ka content"],
            "real": True,
        },
        "basic_video": {
            "description": "Slideshow videos from images (moviepy), product reels for HeroPost",
            "agent": "content_producer",
            "tools": [
                "VideoCreator.create_slideshow",
                "ContentProducer.generate_product_reel",
            ],
            "intents": ["video_banao", "reel banao"],
            "real": True,
        },
        "backup_restore": {
            "description": "Daily backup, verify integrity, restore on approval",
            "agent": "backup",
            "tools": [
                "IntegrationBridge.run_backup",
                "BackupAgent.run_daily_backup",
                "BackupAgent.verify_backup",
                "BackupAgent.quick_snapshot",
            ],
            "intents": ["backup_snapshot", "backup_verify", "backup_list"],
            "real": True,
        },
        "revenue_tracking": {
            "description": "WooCommerce revenue sync and reporting",
            "agent": "internal",
            "tools": [
                "RevenueTracker.sync_from_woocommerce",
                "RevenueTracker.generate_whatsapp_report",
                "RevenueTracker.get_monthly_summary",
                "WooCommerceConnector.get_orders",
            ],
            "intents": ["revenue_check", "order_check", "payment_check"],
            "real": True,
        },
        "security_monitoring": {
            "description": "Security scans, failed login monitoring, uptime checks",
            "agent": "sentinel",
            "tools": [
                "Sentinel.run_scan",
                "Sentinel.monitor_failed_logins",
                "Sentinel.scan_vulnerabilities",
                "Director._quick_uptime_check",
            ],
            "intents": ["security_scan", "uptime_check", "sentry_scan"],
            "real": True,
        },
        "product_management": {
            "description": "WooCommerce product updates (description, title, categories)",
            "agent": "developer",
            "tools": [
                "WooCommerceConnector.update_product",
                "WooCommerceConnector.update_product",
                "WooCommerceConnector.update_wc_category",
                "WooCommerceConnector.get_all_products",
            ],
            "intents": ["push_all_rewrites", "bulk_title_fix", "disclaimer_injection"],
            "real": True,
        },
        "store_audit": {
            "description": "Full WooCommerce store audit (products, orders, inventory)",
            "agent": "developer",
            "tools": [
                "IntegrationBridge.run_store_audit",
                "WooCommerceConnector.full_store_audit",
                "WooCommerceConnector.get_orders",
                "WooCommerceConnector.get_product_issues",
            ],
            "intents": ["store_audit", "order_check"],
            "real": True,
        },
        "competitor_analysis": {
            "description": "Competitor price tracking and positioning",
            "agent": "strategist",
            "tools": [
                "IntegrationBridge.run_price_scan",
                "IntegrationBridge.get_price_report",
                "PriceTracker.run_weekly_scan",
                "StrategistAgent._do_deep_competitor_analysis",
            ],
            "intents": ["price_scan", "competitor_check"],
            "real": True,
        },
        "customer_winback": {
            "description": "Generate winback email drafts for inactive customers",
            "agent": "media",
            "tools": [
                "IntegrationBridge.generate_winback_emails",
                "CustomerWinback.generate_winback_emails",
                "CustomerWinback.get_winback_status",
            ],
            "intents": ["customer_recovery", "winback"],
            "real": True,
        },
        "inventory_analysis": {
            "description": "Burn rate, stock alerts, inventory screening",
            "agent": "internal",
            "tools": [
                "IntegrationBridge.get_burn_rate_report",
                "LeadPredictor.get_burn_rate_report",
            ],
            "intents": ["inventory_check", "burn_rate"],
            "real": True,
        },
        "profit_reporting": {
            "description": "Profit and ROI calculations",
            "agent": "internal",
            "tools": [
                "ProfitTracker.get_profit_report",
                "ProfitTracker.get_summary",
            ],
            "intents": ["profit_report"],
            "real": True,
        },
        "traffic_analytics": {
            "description": "Traffic report (when GA4/GSC configured)",
            "agent": "strategist",
            "tools": [
                "GSCConnector.run_health_check",
                "GA4Connector.get_traffic_report",
            ],
            "intents": ["analytics_traffic", "traffic_dekho"],
            "real": True,
        },
    },

    "out_of_scope": {
        "paid_ads": {
            "reason": "No Google Ads or Meta Ads API integration",
            "keywords": [
                "google ads", "meta ads", "facebook ads", "ad campaign",
                "ads chala", "ads chalao", "google ads chala", "ppc", "paid ads",
                "advertise", "products ke liye ads", "ads lagao", "promote ads",
            ],
        },
        "email_marketing_send": {
            "reason": "Can generate email drafts (winback) but cannot send campaigns via Mailchimp/SendGrid",
            "keywords": ["mailchimp", "email campaign", "newsletter send", "bulk email", "email blast"],
        },
        "advanced_graphic_design": {
            "reason": "Can generate images via NVIDIA; no Canva/Figma/design tools",
            "keywords": ["canva", "figma", "logo design", "banner design from scratch"],
        },
        "ai_video_generation": {
            "reason": "Uses slideshow approach. Full AI video generation when budget allows",
            "keywords": ["ai video", "ai generated video", "sora", "runway"],
        },
        "legal_compliance": {
            "reason": "Can flag health claims risks; cannot give legal advice",
            "keywords": ["legal advice", "lawyer", "compliance certificate", "legal opinion"],
        },
        "payment_gateway_modify": {
            "reason": "Can read WooCommerce orders; cannot modify payment gateway setup",
            "keywords": ["payment gateway", "stripe setup", "paypal config", "payment setup"],
        },
        "server_migration": {
            "reason": "Can backup; cannot migrate hosting",
            "keywords": ["migrate", "hosting change", "server migration", "move to new host"],
        },
        "custom_plugin_dev": {
            "reason": "Cannot build WordPress plugins from scratch",
            "keywords": ["custom plugin", "plugin from scratch", "build plugin", "develop plugin"],
        },
    },
}


def get_in_scope_capabilities() -> List[Dict]:
    """Return list of in-scope capabilities for DirectorBrain context."""
    return [
        {
            "name": k,
            "description": v["description"],
            "agent": v["agent"],
        }
        for k, v in AGENCY_CAPABILITIES["in_scope"].items()
    ]


def get_out_of_scope_reasons() -> List[Tuple[str, str]]:
    """Return (capability, reason) for out-of-scope items."""
    return [
        (k, v["reason"])
        for k, v in AGENCY_CAPABILITIES["out_of_scope"].items()
    ]


def check_scope(user_message: str) -> Optional[Dict]:
    """
    Check if user message requests something OUT OF SCOPE.
    Returns None if in-scope or unclear.
    Returns dict with out_of_scope key, reason, and alternatives if out-of-scope.
    """
    lower = user_message.lower().strip()

    if len(lower) < 5:
        return None

    for key, data in AGENCY_CAPABILITIES["out_of_scope"].items():
        for kw in data["keywords"]:
            if kw in lower:
                return {
                    "out_of_scope": key,
                    "reason": data["reason"],
                    "alternatives": _get_alternatives(key),
                }

    return None


def _get_alternatives(out_key: str) -> List[str]:
    """Suggest in-scope alternatives for common out-of-scope requests."""
    mapping = {
        "paid_ads": [
            "SEO se organic traffic badha sakta hoon",
            "Content pipeline se product pages optimize kar sakta hoon",
            "AEO scan se AI search mein rank kara sakta hoon",
        ],
        "email_marketing_send": [
            "Winback email drafts generate kar sakta hoon (approval ke baad aap send karenge)",
        ],
        "graphic_design": [
            "ImageGenerator se blog/social images generate kar sakta hoon (AI-generated)",
        ],
        "video_production": [
            "Content (blog, social captions) generate kar sakta hoon",
        ],
        "legal_compliance": [
            "Health claims audit kar sakta hoon (risk flagging only, not legal advice)",
        ],
        "payment_gateway_modify": [
            "Order data, revenue report de sakta hoon",
        ],
        "server_migration": [
            "Daily backup le sakta hoon — restore point ready rahega",
        ],
        "custom_plugin_dev": [
            "Existing plugin updates kar sakta hoon (Developer agent)",
        ],
    }
    return mapping.get(out_key, [])


def format_for_director_brain() -> str:
    """Format capability registry for injection into DirectorBrain system prompt."""
    lines = [
        "=== YOUR REAL CAPABILITIES (use this for scope) ===",
        "",
        "IN SCOPE:",
    ]
    for k, v in AGENCY_CAPABILITIES["in_scope"].items():
        lines.append(f"  • {k}: {v['description']} (agent: {v['agent']})")
    lines.append("")
    lines.append("OUT OF SCOPE:")
    for k, v in AGENCY_CAPABILITIES["out_of_scope"].items():
        lines.append(f"  • {k}: {v['reason']}")
    lines.append("")
    lines.append(
        "SCOPE RULE: When owner asks for something OUT OF SCOPE, "
        "say honestly 'Mere scope mein nahi hai' + reason. "
        "Then offer IN SCOPE alternatives. Never say 'haan kar deta hoon' for out-of-scope."
    )
    lines.append("==========================================")
    return "\n".join(lines)
