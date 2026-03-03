"""
core/ga4_connector.py — Google Analytics 4 Real Integration
=============================================================
Fetches real traffic data via Google Analytics Data API v1.

Setup (.env):
  GOOGLE_SERVICE_ACCOUNT_PATH=config/google_service_account.json
  GA4_PROPERTY_ID=526614794
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Support both old and new env var names
GA4_PROPERTY_ID     = os.getenv("GA4_PROPERTY_ID", "")
SERVICE_ACCOUNT_PATH = (
    os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "")
    or os.getenv("GSC_SERVICE_ACCOUNT_JSON", "")
    or os.getenv("GA4_SERVICE_ACCOUNT_JSON", "")
)


class GA4Connector:
    """Fetch GA4 metrics: sessions, users, pageviews, top pages, traffic sources."""

    SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

    def __init__(self):
        self.property_id = GA4_PROPERTY_ID
        self.credentials_path = SERVICE_ACCOUNT_PATH
        self._client = None

    def is_configured(self) -> bool:
        return bool(
            self.property_id
            and self.credentials_path
            and Path(self.credentials_path).exists()
        )

    def get_status(self) -> str:
        ok = self.is_configured()
        return (
            f"📊 *GA4 ANALYTICS*\n"
            f"{'─' * 25}\n"
            f"🔌 Connection: {'✅ Ready' if ok else '❌ Not configured'}\n"
            f"📌 Property: {self.property_id or 'Not set'}\n"
            f"🔑 Credentials: {'✅ Found' if ok else '❌ Missing'}\n\n"
            f"{'✅ Real traffic data ready' if ok else 'Add GOOGLE_SERVICE_ACCOUNT_PATH + GA4_PROPERTY_ID to .env'}"
        )

    def _get_client(self):
        """Lazy-load GA4 client with service account credentials."""
        if self._client:
            return self._client
        from google.analytics.data import BetaAnalyticsDataClient
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=self.SCOPES
        )
        self._client = BetaAnalyticsDataClient(credentials=creds)
        return self._client

    def _run_report(self, dimensions: list, metrics: list, days: int,
                    order_by=None, limit: int = 100) -> list:
        """Generic GA4 report runner. Returns list of row dicts."""
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest, OrderBy
        )
        client = self._get_client()
        end   = datetime.now().date()
        start = end - timedelta(days=days)

        req_kwargs = dict(
            property=f"properties/{self.property_id}",
            dimensions=[Dimension(name=d) for d in dimensions],
            metrics=[Metric(name=m) for m in metrics],
            date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
            limit=limit,
        )
        if order_by:
            req_kwargs["order_bys"] = order_by

        resp = client.run_report(RunReportRequest(**req_kwargs))

        rows = []
        for row in resp.rows:
            r = {}
            for i, dim in enumerate(dimensions):
                r[dim] = row.dimension_values[i].value
            for i, met in enumerate(metrics):
                val = row.metric_values[i].value
                r[met] = int(val) if val.isdigit() else round(float(val), 4)
            rows.append(r)
        return rows

    # ── Public API ──────────────────────────────────────────────────────────

    def get_traffic_summary(self, days: int = 7) -> Dict:
        """Sessions, users, pageviews for last N days."""
        if not self.is_configured():
            return {"success": False, "error": "GA4 not configured", "users": 0, "sessions": 0, "pageviews": 0}
        try:
            rows = self._run_report(
                dimensions=["date"],
                metrics=["activeUsers", "sessions", "screenPageViews", "bounceRate", "averageSessionDuration"],
                days=days,
            )
            users = sessions = pageviews = 0
            bounce_rates = []
            durations = []
            for r in rows:
                users     += r.get("activeUsers", 0)
                sessions  += r.get("sessions", 0)
                pageviews += r.get("screenPageViews", 0)
                if r.get("bounceRate"):
                    bounce_rates.append(r["bounceRate"])
                if r.get("averageSessionDuration"):
                    durations.append(r["averageSessionDuration"])

            end   = datetime.now().date()
            start = end - timedelta(days=days)
            return {
                "success":       True,
                "users":         users,
                "sessions":      sessions,
                "pageviews":     pageviews,
                "bounce_rate":   round(sum(bounce_rates) / len(bounce_rates), 4) if bounce_rates else 0,
                "avg_duration_s": round(sum(durations) / len(durations)) if durations else 0,
                "days":          days,
                "period":        f"{start} to {end}",
            }
        except ImportError:
            return {"success": False, "error": "Install: pip install google-analytics-data"}
        except Exception as e:
            return {"success": False, "error": str(e), "users": 0, "sessions": 0, "pageviews": 0}

    # Keep old name for backwards compat
    def get_traffic_report(self, days: int = 7) -> Dict:
        return self.get_traffic_summary(days=days)

    def get_top_pages(self, days: int = 7, limit: int = 10) -> Dict:
        """Top pages by sessions for last N days."""
        if not self.is_configured():
            return {"success": False, "error": "GA4 not configured", "pages": []}
        try:
            from google.analytics.data_v1beta.types import OrderBy
            rows = self._run_report(
                dimensions=["pagePath", "pageTitle"],
                metrics=["sessions", "activeUsers", "screenPageViews"],
                days=days,
                order_by=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                limit=limit,
            )
            pages = [
                {
                    "path":      r.get("pagePath", ""),
                    "title":     r.get("pageTitle", "")[:60],
                    "sessions":  r.get("sessions", 0),
                    "users":     r.get("activeUsers", 0),
                    "pageviews": r.get("screenPageViews", 0),
                }
                for r in rows
            ]
            return {"success": True, "pages": pages, "days": days}
        except Exception as e:
            return {"success": False, "error": str(e), "pages": []}

    def get_traffic_sources(self, days: int = 7) -> Dict:
        """Traffic by channel/source for last N days."""
        if not self.is_configured():
            return {"success": False, "error": "GA4 not configured", "sources": []}
        try:
            from google.analytics.data_v1beta.types import OrderBy
            rows = self._run_report(
                dimensions=["sessionDefaultChannelGroup"],
                metrics=["sessions", "activeUsers"],
                days=days,
                order_by=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
                limit=10,
            )
            sources = [
                {
                    "channel":  r.get("sessionDefaultChannelGroup", ""),
                    "sessions": r.get("sessions", 0),
                    "users":    r.get("activeUsers", 0),
                }
                for r in rows
            ]
            return {"success": True, "sources": sources, "days": days}
        except Exception as e:
            return {"success": False, "error": str(e), "sources": []}

    def format_whatsapp_report(self, days: int = 7) -> str:
        """Return formatted WhatsApp-ready GA4 report string."""
        summary = self.get_traffic_summary(days=days)
        if not summary.get("success"):
            return f"📊 GA4 Error: {summary.get('error', 'Unknown')}"

        sources = self.get_traffic_sources(days=days)
        top_pages = self.get_top_pages(days=days, limit=5)

        dur_m = summary.get("avg_duration_s", 0) // 60
        dur_s = summary.get("avg_duration_s", 0) % 60
        bounce = round(summary.get("bounce_rate", 0) * 100, 1)

        lines = [
            f"📊 *GA4 TRAFFIC REPORT — Last {days} Days*",
            f"📅 {summary.get('period', '')}",
            f"{'─' * 30}",
            f"👥 Users:      {summary['users']:,}",
            f"🔄 Sessions:   {summary['sessions']:,}",
            f"📄 Pageviews:  {summary['pageviews']:,}",
            f"⏱  Avg Time:   {dur_m}m {dur_s}s",
            f"📉 Bounce:     {bounce}%",
        ]

        if sources.get("success") and sources.get("sources"):
            lines.append(f"\n📡 *Traffic Sources:*")
            for s in sources["sources"][:5]:
                lines.append(f"  • {s['channel']}: {s['sessions']:,} sessions")

        if top_pages.get("success") and top_pages.get("pages"):
            lines.append(f"\n🔝 *Top Pages:*")
            for p in top_pages["pages"][:5]:
                lines.append(f"  • {p['path'][:40]}: {p['sessions']:,}")

        return "\n".join(lines)


# Singleton
ga4_connector = GA4Connector()
