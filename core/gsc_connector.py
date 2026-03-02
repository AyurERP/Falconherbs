"""
core/gsc_connector.py — Google Search Console Real Integration
==============================================================
Fetches real search performance data: clicks, impressions, CTR, position.

Setup required (.env):
  GSC_SERVICE_ACCOUNT_JSON=/path/to/service-account.json
  OR GSC_CLIENT_ID + GSC_CLIENT_SECRET + GSC_REFRESH_TOKEN (OAuth)

How to get service account:
  1. Google Cloud Console → Create project → Enable Search Console API
  2. IAM → Service Accounts → Create → Download JSON key
  3. Search Console → Settings → Users → Add service account email (as Owner)
  4. Save JSON path to GSC_SERVICE_ACCOUNT_JSON in .env
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

GSC_JSON        = os.getenv("GSC_SERVICE_ACCOUNT_JSON", "")
GSC_CLIENT_ID   = os.getenv("GSC_CLIENT_ID", "")
GSC_CLIENT_SECRET = os.getenv("GSC_CLIENT_SECRET", "")
GSC_REFRESH_TOKEN = os.getenv("GSC_REFRESH_TOKEN", "")
SITE_URL        = os.getenv("WP_SITE_URL", "https://falconherbs.com").rstrip("/")

DATA_DIR = Path(__file__).parent.parent / "data" / "seo"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class GSCConnector:
    """Google Search Console — real search performance data."""

    def __init__(self):
        self.json_path = GSC_JSON
        self.site_url  = SITE_URL
        # GSC uses sc-domain: prefix for domain properties
        self._sc_site  = (
            f"sc-domain:{SITE_URL.split('//')[-1]}"
            if not SITE_URL.startswith("sc-domain")
            else SITE_URL
        )
        self._service  = None

    # ── Setup check ────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        service_account_ok = bool(self.json_path and Path(self.json_path).exists())
        oauth_ok = bool(GSC_CLIENT_ID and GSC_CLIENT_SECRET and GSC_REFRESH_TOKEN)
        return service_account_ok or oauth_ok

    def get_status(self) -> str:
        ok = self.is_configured()
        method = "Service Account" if (self.json_path and Path(self.json_path).exists()) else \
                 "OAuth" if (GSC_CLIENT_ID and GSC_REFRESH_TOKEN) else "Not configured"
        return (
            f"🔍 *SEARCH CONSOLE*\n"
            f"{'─' * 25}\n"
            f"🔌 Connection: {'✅ ' + method if ok else '❌ Not configured'}\n"
            f"🌐 Site: {SITE_URL}\n\n"
            f"{'✅ Ready — fetch rankings, CTR, impressions' if ok else 'Add GSC_SERVICE_ACCOUNT_JSON to .env'}"
        )

    # ── Service builder ─────────────────────────────────────────────────

    def _build_service(self):
        """Build Google Search Console API service."""
        if self._service:
            return self._service

        try:
            from googleapiclient.discovery import build
            from google.oauth2 import service_account
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request

            SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

            if self.json_path and Path(self.json_path).exists():
                creds = service_account.Credentials.from_service_account_file(
                    self.json_path, scopes=SCOPES
                )
            elif GSC_CLIENT_ID and GSC_REFRESH_TOKEN:
                creds = Credentials(
                    token=None,
                    refresh_token=GSC_REFRESH_TOKEN,
                    client_id=GSC_CLIENT_ID,
                    client_secret=GSC_CLIENT_SECRET,
                    token_uri="https://oauth2.googleapis.com/token",
                    scopes=SCOPES,
                )
                creds.refresh(Request())
            else:
                raise RuntimeError("No GSC credentials configured")

            self._service = build("searchconsole", "v1", credentials=creds)
            return self._service

        except ImportError:
            raise RuntimeError(
                "Install: pip install google-api-python-client google-auth"
            )

    # ── Core data fetchers ──────────────────────────────────────────────

    def get_search_performance(
        self,
        days: int = 28,
        dimensions: List[str] = None,
        row_limit: int = 25,
    ) -> Dict:
        """
        Fetch search performance: clicks, impressions, CTR, position.

        Parameters
        ----------
        days : int
            Number of days to look back (default 28).
        dimensions : list
            Breakdown dimensions — ["query", "page", "country", "device"].
            Default: ["query"].
        row_limit : int
            Max rows to return (default 25, max 25000).

        Returns
        -------
        dict with keys: success, rows, totals, period
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "GSC not configured. Add GSC_SERVICE_ACCOUNT_JSON to .env",
                "rows": [], "totals": {},
            }

        dimensions = dimensions or ["query"]

        try:
            service  = self._build_service()
            end_dt   = datetime.utcnow().date()
            start_dt = end_dt - timedelta(days=days)

            body = {
                "startDate": str(start_dt),
                "endDate":   str(end_dt),
                "dimensions": dimensions,
                "rowLimit":   row_limit,
                "orderBy": [{"fieldName": "clicks", "sortOrder": "DESCENDING"}],
            }

            resp = (
                service.searchanalytics()
                .query(siteUrl=self._sc_site, body=body)
                .execute()
            )

            rows = resp.get("rows", [])

            # Build totals
            totals = {
                "clicks":      sum(r.get("clicks", 0) for r in rows),
                "impressions": sum(r.get("impressions", 0) for r in rows),
                "ctr":         round(sum(r.get("ctr", 0) for r in rows) / max(len(rows), 1) * 100, 2),
                "position":    round(sum(r.get("position", 0) for r in rows) / max(len(rows), 1), 1),
            }

            # Clean rows for output
            clean_rows = []
            for row in rows:
                keys = row.get("keys", [])
                clean_rows.append({
                    "query" if dimensions[0] == "query" else dimensions[0]: keys[0] if keys else "",
                    "clicks":      row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr":         round(row.get("ctr", 0) * 100, 2),
                    "position":    round(row.get("position", 0), 1),
                })

            result = {
                "success": True,
                "rows": clean_rows,
                "totals": totals,
                "period": f"{start_dt} to {end_dt}",
                "dimensions": dimensions,
                "fetched_at": datetime.utcnow().isoformat(),
            }

            # Cache result
            cache_file = DATA_DIR / f"gsc_{dimensions[0]}_{days}d.json"
            cache_file.write_text(json.dumps(result, indent=2))

            return result

        except Exception as exc:
            return {"success": False, "error": str(exc)[:300], "rows": [], "totals": {}}

    def get_top_keywords(self, days: int = 28, limit: int = 20) -> Dict:
        """Top search queries by clicks."""
        result = self.get_search_performance(days=days, dimensions=["query"], row_limit=limit)
        if result["success"]:
            result["label"] = f"Top {limit} keywords (last {days}d)"
        return result

    def get_top_pages(self, days: int = 28, limit: int = 20) -> Dict:
        """Top pages by clicks."""
        result = self.get_search_performance(days=days, dimensions=["page"], row_limit=limit)
        if result["success"]:
            result["label"] = f"Top {limit} pages (last {days}d)"
        return result

    def run_health_check(self) -> Dict:
        """
        Check GSC health — fetch last 7d totals.
        Returns honest status for integration_bridge reporting.
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "GSC not configured",
                "data": {"errors": None, "warnings": None, "indexed": None},
            }

        try:
            perf = self.get_search_performance(days=7, dimensions=["query"], row_limit=5)
            if perf["success"]:
                t = perf["totals"]
                return {
                    "success": True,
                    "message": (
                        f"🔍 GSC (7d): {t['clicks']:,} clicks | "
                        f"{t['impressions']:,} impressions | "
                        f"Avg pos {t['position']}"
                    ),
                    "data": {
                        "clicks":      t["clicks"],
                        "impressions": t["impressions"],
                        "ctr":         t["ctr"],
                        "position":    t["position"],
                    },
                }
            return {"success": False, "error": perf["error"], "data": {}}
        except Exception as exc:
            return {"success": False, "error": str(exc), "data": {}}

    def format_whatsapp_report(self, days: int = 7) -> str:
        """Returns WhatsApp-ready GSC summary."""
        perf = self.get_search_performance(days=days, dimensions=["query"], row_limit=10)
        if not perf["success"]:
            return f"❌ GSC: {perf.get('error', 'Not configured')}"

        t    = perf["totals"]
        rows = perf["rows"]

        lines = [
            f"🔍 *SEARCH CONSOLE — {days}d*",
            f"{'─' * 28}",
            f"👆 Clicks: {t['clicks']:,}",
            f"👁 Impressions: {t['impressions']:,}",
            f"📊 Avg CTR: {t['ctr']}%",
            f"📍 Avg Position: {t['position']}",
            "",
            "*Top Keywords:*",
        ]
        for i, row in enumerate(rows[:8], 1):
            kw  = row.get("query", "")[:35]
            clk = row.get("clicks", 0)
            pos = row.get("position", 0)
            lines.append(f"  {i}. {kw} — {clk} clicks (pos {pos})")

        lines.append(f"\n🦅 _Falcon Agency — Search Console_")
        return "\n".join(lines)


# Singleton
gsc_connector = GSCConnector()
