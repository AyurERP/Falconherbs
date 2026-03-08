"""
core/gsc_connector.py — Google Search Console Real Integration
==============================================================
Fetches real search performance data via Search Console API v1.

Setup (.env):
  GOOGLE_SERVICE_ACCOUNT_PATH=config/google_service_account.json
  (same service account as GA4)

GSC property: https://www.falconherbs.com/
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# Service account — shared with GA4
SERVICE_ACCOUNT_PATH = (
    os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "")
    or os.getenv("GSC_SERVICE_ACCOUNT_JSON", "")
)
SITE_URL = os.getenv("WP_SITE_URL", "https://www.falconherbs.com").rstrip("/")

DATA_DIR = Path(__file__).parent.parent / "data" / "seo"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class GSCConnector:
    """Google Search Console — real search performance data."""

    SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

    def __init__(self):
        self.json_path = SERVICE_ACCOUNT_PATH
        self.site_url  = SITE_URL
        # Use full URL property (service account has siteFullUser on www.falconherbs.com)
        self._sc_site  = self.site_url + "/"
        self._service  = None

    # ── Auth ───────────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(self.json_path and Path(self.json_path).exists())

    def get_status(self) -> str:
        ok = self.is_configured()
        return (
            f"🔍 *SEARCH CONSOLE*\n"
            f"{'─' * 25}\n"
            f"🔌 Status: {'✅ Ready' if ok else '❌ Not configured'}\n"
            f"🌐 Site: {self._sc_site}\n"
            f"🔑 Credentials: {'✅ Found' if ok else '❌ Missing'}\n\n"
            f"{'✅ Real GSC data ready' if ok else 'Add GOOGLE_SERVICE_ACCOUNT_PATH to .env'}"
        )

    def _get_service(self):
        """Lazy-load GSC API service."""
        if self._service:
            return self._service
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            self.json_path, scopes=self.SCOPES
        )
        self._service = build("searchconsole", "v1", credentials=creds)
        return self._service

    # ── Data helpers ────────────────────────────────────────────────────────

    def _query(self, days: int, dimensions: list, row_limit: int = 25,
               start_row: int = 0) -> list:
        """Run a Search Analytics query. Returns list of row dicts."""
        svc = self._get_service()
        end   = (datetime.now() - timedelta(days=3)).date()   # GSC has 3-day lag
        start = end - timedelta(days=days)

        body = {
            "startDate":   str(start),
            "endDate":     str(end),
            "dimensions":  dimensions,
            "rowLimit":    row_limit,
            "startRow":    start_row,
        }
        resp = (
            svc.searchanalytics()
            .query(siteUrl=self._sc_site, body=body)
            .execute()
        )
        rows_raw = resp.get("rows", [])
        rows = []
        for row in rows_raw:
            keys = row.get("keys", [])
            r = {dimensions[i]: keys[i] for i in range(len(keys))}
            r["clicks"]      = int(row.get("clicks", 0))
            r["impressions"] = int(row.get("impressions", 0))
            r["ctr"]         = round(row.get("ctr", 0), 4)
            r["position"]    = round(row.get("position", 0), 1)
            rows.append(r)
        return rows

    # ── Public API ──────────────────────────────────────────────────────────

    def get_top_queries(self, days: int = 7, limit: int = 20) -> Dict:
        """Top search queries by clicks."""
        if not self.is_configured():
            return {"success": False, "error": "GSC not configured", "queries": []}
        try:
            rows = self._query(days=days, dimensions=["query"], row_limit=limit)
            queries = [
                {
                    "query":       r.get("query", ""),
                    "clicks":      r["clicks"],
                    "impressions": r["impressions"],
                    "ctr":         f"{round(r['ctr'] * 100, 1)}%",
                    "position":    r["position"],
                }
                for r in rows
            ]
            return {"success": True, "queries": queries, "days": days}
        except Exception as e:
            return {"success": False, "error": str(e), "queries": []}

    def get_top_pages(self, days: int = 7, limit: int = 20) -> Dict:
        """Top pages by clicks."""
        if not self.is_configured():
            return {"success": False, "error": "GSC not configured", "pages": []}
        try:
            rows = self._query(days=days, dimensions=["page"], row_limit=limit)
            pages = [
                {
                    "page":        r.get("page", "").replace(self.site_url, ""),
                    "clicks":      r["clicks"],
                    "impressions": r["impressions"],
                    "ctr":         f"{round(r['ctr'] * 100, 1)}%",
                    "position":    r["position"],
                }
                for r in rows
            ]
            return {"success": True, "pages": pages, "days": days}
        except Exception as e:
            return {"success": False, "error": str(e), "pages": []}

    def get_search_performance(self, days: int = 7) -> Dict:
        """Overall totals: clicks, impressions, avg CTR, avg position."""
        if not self.is_configured():
            return {"success": False, "error": "GSC not configured"}
        try:
            rows = self._query(days=days, dimensions=["date"], row_limit=90)
            total_clicks  = sum(r["clicks"] for r in rows)
            total_impr    = sum(r["impressions"] for r in rows)
            avg_ctr       = round(total_clicks / total_impr * 100, 2) if total_impr else 0
            avg_pos       = round(sum(r["position"] for r in rows) / len(rows), 1) if rows else 0
            end   = (datetime.now() - timedelta(days=3)).date()
            start = end - timedelta(days=days)
            return {
                "success":     True,
                "clicks":      total_clicks,
                "impressions": total_impr,
                "avg_ctr":     f"{avg_ctr}%",
                "avg_position": avg_pos,
                "days":        days,
                "period":      f"{start} to {end}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_indexing_status(self) -> Dict:
        """Check indexed pages count via GSC URL inspection (basic version)."""
        if not self.is_configured():
            return {"success": False, "error": "GSC not configured"}
        try:
            svc = self._get_service()
            result = svc.sites().list().execute()
            sites = result.get("siteEntry", [])
            return {
                "success":    True,
                "sites":      [s.get("siteUrl") for s in sites],
                "target_site": self._sc_site,
                "verified":   any(self._sc_site in s.get("siteUrl", "") for s in sites),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def format_whatsapp_report(self, days: int = 7) -> str:
        """Return GA4-style WhatsApp-ready GSC report string."""
        perf = self.get_search_performance(days=days)
        if not perf.get("success"):
            return f"🔍 GSC Error: {perf.get('error', 'Unknown')}"

        queries  = self.get_top_queries(days=days, limit=10)
        pages    = self.get_top_pages(days=days, limit=5)

        lines = [
            f"🔍 *SEARCH CONSOLE REPORT — Last {days} Days*",
            f"📅 {perf.get('period', '')}",
            f"{'─' * 30}",
            f"👆 Clicks:      {perf['clicks']:,}",
            f"👁  Impressions: {perf['impressions']:,}",
            f"📊 Avg CTR:     {perf['avg_ctr']}",
            f"📍 Avg Position:{perf['avg_position']}",
        ]

        if queries.get("success") and queries.get("queries"):
            lines.append(f"\n🔑 *Top Keywords:*")
            for q in queries["queries"][:10]:
                lines.append(
                    f"  • {q['query'][:35]}: {q['clicks']} clicks @ pos {q['position']}"
                )

        if pages.get("success") and pages.get("pages"):
            lines.append(f"\n📄 *Top Pages:*")
            for p in pages["pages"][:5]:
                lines.append(f"  • {p['page'][:40]}: {p['clicks']} clicks")

        return "\n".join(lines)


# Singleton
gsc_connector = GSCConnector()
