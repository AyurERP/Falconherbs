"""
core/ads_monitor.py — Ads Monitoring for Falcon Agency (Structure Only)
=======================================================================

Structure ready for Google Ads and Meta Ads. NO API keys yet.
When not configured, returns honest "not_configured" — never fake data.
Honesty is core to this agency.

When APIs are connected later:
- get_google_ads_summary / get_meta_ads_summary return real metrics
- check_anomalies alerts on spend/ROAS/CTR anomalies
- pause_campaign goes through approval gate (ONLY write operation)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.logger import log

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG CHECK (no keys = not configured)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GOOGLE_ADS_SETUP = (
    "Owner needs to: 1. Go to Google Ads → Tools → API Center, "
    "2. Generate API credentials, 3. Share with agency"
)
META_ADS_SETUP = (
    "Owner needs to: 1. Go to Meta Business Suite → Settings → Integrations, "
    "2. Create Marketing API token, 3. Share with agency"
)


def _has_google_ads_config() -> bool:
    """Check if Google Ads API credentials are configured."""
    import os
    return bool(
        os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
        or os.getenv("GOOGLE_ADS_CLIENT_ID")
        or os.getenv("GOOGLE_ADS_API_KEY")
    )


def _has_meta_ads_config() -> bool:
    """Check if Meta Marketing API token is configured."""
    import os
    return bool(
        os.getenv("META_ADS_ACCESS_TOKEN")
        or os.getenv("META_MARKETING_API_TOKEN")
    )


def get_google_ads_summary(date_range: str = "today") -> Dict[str, Any]:
    """
    Get Google Ads summary. When no API key: honest not_configured.
    """
    if not _has_google_ads_config():
        return {
            "status": "not_configured",
            "message": (
                "Google Ads API not connected yet. "
                "Jab owner API credentials denge, tab activate ho jayega."
            ),
            "setup_instructions": GOOGLE_ADS_SETUP,
            "date_range": date_range,
        }
    # When configured: would call Google Ads API here
    # For now, structure only
    return {
        "status": "active",
        "message": "Google Ads API connected (placeholder — implement when keys added)",
        "date_range": date_range,
    }


def get_meta_ads_summary(date_range: str = "today") -> Dict[str, Any]:
    """
    Get Meta (Facebook/Instagram) Ads summary. When no token: honest not_configured.
    """
    if not _has_meta_ads_config():
        return {
            "status": "not_configured",
            "message": (
                "Meta Ads API not connected yet. "
                "Jab owner Marketing API token denge, tab activate ho jayega."
            ),
            "setup_instructions": META_ADS_SETUP,
            "date_range": date_range,
        }
    # When configured: would call Meta Marketing API here
    return {
        "status": "active",
        "message": "Meta Ads API connected (placeholder — implement when token added)",
        "date_range": date_range,
    }


def check_anomalies(
    current_spend: float,
    daily_average: float,
    current_roas: Optional[float] = None,
    average_roas: Optional[float] = None,
    current_ctr: Optional[float] = None,
    average_ctr: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Logic ready for when APIs are connected.
    Alert if:
    - spend > 1.5x average
    - ROAS drops > 30%
    - CTR drops > 50%
    """
    alerts: List[Dict[str, Any]] = []
    if daily_average > 0 and current_spend > 1.5 * daily_average:
        alerts.append({
            "type": "spend_spike",
            "message": f"Spend ({current_spend:.2f}) is > 1.5x daily average ({daily_average:.2f})",
            "severity": "high",
        })
    if (
        average_roas is not None
        and average_roas > 0
        and current_roas is not None
        and current_roas < 0.7 * average_roas
    ):
        alerts.append({
            "type": "roas_drop",
            "message": f"ROAS dropped > 30% (current: {current_roas:.2f}, avg: {average_roas:.2f})",
            "severity": "medium",
        })
    if (
        average_ctr is not None
        and average_ctr > 0
        and current_ctr is not None
        and current_ctr < 0.5 * average_ctr
    ):
        alerts.append({
            "type": "ctr_drop",
            "message": f"CTR dropped > 50% (current: {current_ctr:.2%}, avg: {average_ctr:.2%})",
            "severity": "medium",
        })
    return alerts


class AdsMonitor:
    """
    Ads monitoring — structure only until API keys added.
    pause_campaign is the ONLY write operation; MUST go through approval gate.
    """

    def __init__(self, approval_system=None):
        self._approval = approval_system
        self._google_configured = _has_google_ads_config()
        self._meta_configured = _has_meta_ads_config()

    def _ensure_approval(self):
        if self._approval is None:
            from core.approval import ApprovalSystem
            self._approval = ApprovalSystem()

    def get_google_ads_summary(self, date_range: str = "today") -> Dict[str, Any]:
        return get_google_ads_summary(date_range)

    def get_meta_ads_summary(self, date_range: str = "today") -> Dict[str, Any]:
        return get_meta_ads_summary(date_range)

    def pause_campaign(
        self,
        campaign_id: str,
        platform: str,
    ) -> Dict[str, Any]:
        """
        Pause a campaign. MUST go through approval gate.
        platform: "google" or "meta"
        """
        self._ensure_approval()
        approved = self._approval.request_approval(
            action="ads_pause_campaign",
            details={
                "campaign_id": campaign_id,
                "platform": platform,
                "description": f"Pause {platform} campaign {campaign_id}",
            },
        )
        if not approved:
            return {"success": False, "error": "Owner denied campaign pause"}
        # When API connected: would call platform API here
        return {
            "success": True,
            "message": f"Campaign {campaign_id} pause requested (API not connected — manual action needed)",
            "platform": platform,
        }

    def generate_ads_report(self, period: str = "weekly") -> Dict[str, Any]:
        """
        Compile metrics, compare periods, format for WhatsApp.
        When not configured: honest summary of status.
        """
        google = get_google_ads_summary("today")
        meta = get_meta_ads_summary("today")
        lines = [
            f"📊 *Ads Report ({period})*",
            "",
            "*Google Ads:*",
            google.get("message", google.get("status", "unknown")),
            "",
            "*Meta Ads:*",
            meta.get("message", meta.get("status", "unknown")),
        ]
        if google.get("status") == "not_configured" or meta.get("status") == "not_configured":
            lines.append("")
            lines.append("_API credentials add karne par real data aayega._")
        return {
            "success": True,
            "report": "\n".join(lines),
            "google_status": google.get("status"),
            "meta_status": meta.get("status"),
        }
