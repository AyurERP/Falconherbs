"""
Google Analytics 4 Connector — Traffic, users, conversions.
World-class agency needs analytics. GA4 Data API v1.

Requires: GA4_PROPERTY_ID, GSC_SERVICE_ACCOUNT_JSON (or GA4 credentials)
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")
SERVICE_ACCOUNT_JSON = os.getenv("GSC_SERVICE_ACCOUNT_JSON", "") or os.getenv("GA4_SERVICE_ACCOUNT_JSON", "")


class GA4Connector:
    """Fetch GA4 metrics for agency reporting."""

    def __init__(self):
        self.property_id = GA4_PROPERTY_ID
        self.credentials_path = SERVICE_ACCOUNT_JSON
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.property_id and self.credentials_path and Path(self.credentials_path).exists())

    def get_status(self) -> str:
        configured = self.is_configured()
        return (
            f"📊 *GA4 ANALYTICS*\n"
            f"{'─' * 25}\n"
            f"🔌 Connection: {'✅ Ready' if configured else '❌ Not configured'}\n"
            f"📌 Property: {self.property_id or 'Not set'}\n\n"
            f"{'Add GA4_PROPERTY_ID + service account JSON to .env' if not configured else '✅ Fetch traffic, users, conversions'}"
        )

    def get_traffic_report(self, days: int = 7) -> Dict:
        """Fetch users, sessions, pageviews for last N days."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "GA4 not configured. Add GA4_PROPERTY_ID and service account.",
                "users": 0,
                "sessions": 0,
                "pageviews": 0,
            }
        try:
            from google.analytics.data import BetaAnalyticsDataClient
            from google.analytics.data_v1beta.types import (
                DateRange,
                Dimension,
                Metric,
                RunReportRequest,
            )
            from google.oauth2 import service_account

            creds = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            )
            client = BetaAnalyticsDataClient(credentials=creds)

            end = datetime.now().date()
            start = end - timedelta(days=days)

            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[Dimension(name="date")],
                metrics=[
                    Metric(name="activeUsers"),
                    Metric(name="sessions"),
                    Metric(name="screenPageViews"),
                ],
                date_ranges=[DateRange(start_date=str(start), end_date=str(end))],
            )
            response = client.run_report(request)

            users = sessions = pageviews = 0
            for row in response.rows:
                if len(row.metric_values) >= 3:
                    users += int(row.metric_values[0].value)
                    sessions += int(row.metric_values[1].value)
                    pageviews += int(row.metric_values[2].value)

            return {
                "success": True,
                "users": users,
                "sessions": sessions,
                "pageviews": pageviews,
                "days": days,
                "period": f"{start} to {end}",
            }
        except ImportError:
            return {
                "success": False,
                "error": "Install: pip install google-analytics-data",
                "users": 0,
                "sessions": 0,
                "pageviews": 0,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "users": 0,
                "sessions": 0,
                "pageviews": 0,
            }


ga4_connector = GA4Connector()
