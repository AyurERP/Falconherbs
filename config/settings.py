"""
FALCON AGENCY — Global Settings
Change behaviour here, not scattered across files.
"""

import os
from dataclasses import dataclass, field
from typing import List

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"


@dataclass
class AgencySettings:

    # === IDENTITY ===
    agency_name: str = "Falcon Agency"
    version: str = "0.1.0"
    primary_site: str = "falconherbs.com"

    # === SAFETY — NEVER CHANGE THESE WITHOUT REVIEW ===
    require_approval_for: List[str] = field(default_factory=lambda: [
        "deploy_code",
        "send_mass_email",
        "modify_ads",
        "delete_content",
        "change_dns",
        "purchase",
        "modify_database_schema",
    ])
    approval_timeout_seconds: int = 900  # 15 min to approve, then auto-reject
    max_retries_per_task: int = 3

    # === PERFORMANCE TARGETS ===
    target_page_load_seconds: float = 2.0
    target_lighthouse_score: int = 90

    # === COST GOVERNOR ===
    daily_api_spend_limit_usd: float = 10.0   # auto-pause if exceeded
    monthly_api_spend_limit_usd: float = 150.0

    # === SECURITY ===
    max_failed_logins_before_block: int = 5
    scan_interval_minutes: int = 30
    blocked_ip_ttl_hours: int = 24

    # === LOGGING ===
    log_every_action: bool = True
    log_retention_days: int = 90


settings = AgencySettings()