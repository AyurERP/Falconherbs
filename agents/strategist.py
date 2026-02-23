"""
agents/strategist.py — Strategic Intelligence Agent for Falcon Agency
=======================================================================

The Strategist is the analytical brain of the autonomous workforce.
It reads data, spots patterns, generates insights, and produces
actionable growth recommendations — always in **read-only** mode.

It never modifies site files, never deploys, never writes code.
Its output is intelligence and recommendations only.

Execution Model
───────────────
    Director dispatches → execute() → handle() → [analysis method]
                                                        │
                                    ┌───────────────────┼──────────────────┐
                                    ▼                   ▼                  ▼
                             analyse_keywords    analyse_sales     analyse_traffic
                             check_serp_positions check_competitors analyse_content_gaps
                                    │                   │                  │
                                    └───────────────────┼──────────────────┘
                                                        ▼
                                               generate_recommendations()
                                                        │
                                                        ▼
                                            generate_weekly_report()
                                             ├── save to data/reports/
                                             └── send summary via WhatsApp

Safety Guarantees
─────────────────
    • READ-ONLY — never writes to site, never modifies files beyond reports
    • Never crashes — every method wrapped in try/except
    • Polite to external services — 2s delay between SERP queries, max 5 per run
    • Graceful skip when credentials missing (WooCommerce API)
    • All HTTP requests: 10s timeout ceiling
    • All reports persisted to data/reports/ before returning

Primary Market : Global — AU, UAE, USA, UK, India (en)
Primary Site   : falconherbs.com (WooCommerce, Indian herbal products)
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core.logger import log
from core.approval import ApprovalSystem
from agents.base_agent import BaseAgent
from core.ai_client import call_ai


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PATHS & CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
PROFILES_DIR: Path = PROJECT_ROOT / "config" / "profiles"
REPORTS_DIR:  Path = PROJECT_ROOT / "data" / "reports"

HTTP_TIMEOUT: int   = 10          # seconds — hard ceiling for all requests
SERP_DELAY:   float = 2.0         # seconds between Google queries
SERP_MAX_KW:  int   = 5           # max keywords per SERP run
SERP_PAGES:   int   = 3           # check first 3 pages (30 results)

USER_AGENT: str = "FalconAgency-Strategist/1.0 (Analytics)"
# A browser-like UA is needed for SERP checks so Google doesn't instantly block
BROWSER_UA: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Credential placeholder pattern: {{ENV:VARIABLE_NAME}}
_CREDENTIAL_RE: re.Pattern = re.compile(
    r"^\{\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}\}$"
)

# Performance grading thresholds (average response time in ms)
_PERF_GRADES: List[Tuple[float, str]] = [
    (500,   "A"),   # Excellent
    (1000,  "B"),   # Good
    (1500,  "C"),   # Acceptable
    (3000,  "D"),   # Poor
    (99999, "F"),   # Critical
]

# SEO best-practice thresholds
_MIN_HOMEPAGE_WORDS:     int = 300
_MIN_INTERNAL_LINKS:     int = 10
_IDEAL_TITLE_MIN:        int = 30
_IDEAL_TITLE_MAX:        int = 60
_IDEAL_DESC_MIN:         int = 120
_IDEAL_DESC_MAX:         int = 155

# Impact/effort scoring matrix for recommendations
_IMPACT_SCORE: Dict[str, int] = {"high": 3, "medium": 2, "low": 1}
_EFFORT_SCORE: Dict[str, int] = {"low": 3, "medium": 2, "high": 1}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _today_str() -> str:
    return _utcnow().strftime("%Y%m%d")


def _normalise_url(url: str) -> str:
    url = url.strip()
    if not url:
        return "https://localhost"
    if not urlparse(url).scheme:
        return f"https://{url}"
    return url


def _site_slug(site: str) -> str:
    """``falconherbs.com`` → ``falconherbs_com``"""
    slug = site.strip().lower()
    slug = slug.replace("https://", "").replace("http://", "")
    slug = slug.rstrip("/").split("/")[0]
    slug = slug.replace("www.", "")
    return slug.replace(".", "_").replace("-", "_")


def _grade_performance(avg_ms: float) -> str:
    for threshold, grade in _PERF_GRADES:
        if avg_ms <= threshold:
            return grade
    return "F"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STRATEGIST AGENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class StrategistAgent(BaseAgent):
    """
    Analytical intelligence agent for Falcon Agency.

    Capabilities (all read-only):
        • On-page keyword coverage analysis
        • SERP position checking on google.com (global / India locale)
        • WooCommerce sales summary via REST API
        • Performance trend analysis from stored scans
        • Competitor domain signal checking
        • Content gap identification
        • Prioritised growth recommendations
        • Weekly strategy report with WhatsApp delivery

    Parameters
    ----------
    approval : ApprovalSystem
        Used for sending reports and summaries to the owner via WhatsApp.
    """

    # ──────────────────────────────────────────────────────────────────
    #  Init
    # ──────────────────────────────────────────────────────────────────

    def __init__(self, whatsapp_client=None):
        """
        Initialise the Strategist Agent.
        """
        super().__init__(whatsapp_client)
        self.name = "Strategist"
        self.ai_role = "strategist"  # Uses DeepSeek for strategic thinking and compliance
        self.capabilities = [
            "Market analysis",
            "Competitor research", 
            "Content strategy",
            "Business planning",
            "Trend analysis",
            "Growth recommendations",
            "Health claims compliance audit"
        ]

        # Preserve legacy properties
        self._approval = None
        self._session: requests.Session = self._build_session()

        # Ensure reports directory exists
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.warning("Cannot create reports dir: %s", exc)

        log.info("StrategistAgent initialised  |  reports_dir=%s", REPORTS_DIR)

    @staticmethod
    def _build_session() -> requests.Session:
        """Create a reusable HTTP session with safe defaults."""
        s = requests.Session()
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
            "Accept-Language": "pl,en;q=0.5",
        })
        return s

    # ══════════════════════════════════════════════════════════════════
    #  DISPATCH INTERFACE
    # ══════════════════════════════════════════════════════════════════

    def execute(self, action: str, details: str) -> str:
        """Strategist executes business/strategy tasks"""
        
        plan = self.think(action, {"details": details})
        
        if plan.get("confidence") == "low":
            self.escalate(f"Need more info for: {action}")
            return "Escalated — need clarity"
        
        action_lower = action.lower()
        
        if "market" in action_lower or "competitor" in action_lower:
            return self._do_market_analysis(action, details)
        elif "content" in action_lower or "strategy" in action_lower:
            return self._do_content_strategy(action, details)
        elif "health" in action_lower or "compliance" in action_lower:
            return self._do_compliance_audit(action, details)
        elif "trend" in action_lower:
            return self._do_trend_analysis(action, details)
        else:
            return self._do_generic_strategy(action, details)
    
    def _do_market_analysis(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": """You are a market analyst expert. 
Provide deep market insights with actionable recommendations.
Output JSON: {"market_overview": "...", "competitors": [...], "opportunities": [...], "threats": [...], "recommendations": [...]}"""},
            {"role": "user", "content": f"Action: {action}\nDetails: {details}"}
        ]
        response = call_ai("director", messages)
        self.report_to_owner(f"📊 Market analysis completed")
        return response
    
    def _do_content_strategy(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": """You are a content strategist.
Create comprehensive content plans that drive engagement and conversions.
Output JSON: {"content_pillars": [...], "topics": [...], "schedule": {...}, "kpis": [...]}"""},
            {"role": "user", "content": f"Action: {action}\nDetails: {details}"}
        ]
        response = call_ai("director", messages)
        self.report_to_owner(f"📝 Content strategy ready")
        return response
    
    def _do_compliance_audit(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": """You are a health claims compliance expert.
Audit content for regulatory compliance (FDA, FTC, etc).
Output JSON: {"violations": [...], "risk_level": "high|medium|low", "fixes": [...], "safe_alternatives": [...]}"""},
            {"role": "user", "content": f"Audit this: {action}\nDetails: {details}"}
        ]
        response = call_ai("director", messages)
        self.report_to_owner(f"⚖️ Compliance audit done", priority="high")
        return response
    
    def _do_trend_analysis(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": """You are a trend analyst.
Identify emerging trends and their business implications.
Output JSON: {"trends": [...], "relevance": "...", "action_items": [...]}"""},
            {"role": "user", "content": f"Action: {action}\nDetails: {details}"}
        ]
        return call_ai("director", messages)
    
    def _do_generic_strategy(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": "You are a business strategist. Provide expert strategic advice."},
            {"role": "user", "content": f"Action: {action}\nDetails: {details}"}
        ]
        return call_ai("director", messages)

    def handle(self, task: str, site: str, params: dict) -> dict:
        """
        Route *task* to the appropriate analysis method.

        Every task is wrapped in a top-level try/except so that
        agent errors never crash the Director.

        Recognised Tasks
        ----------------
        ``run_analysis``          — generate_weekly_report (master)
        ``seo_audit``             — generate_weekly_report (alias)
        ``analyse_keywords``      — keyword coverage analysis
        ``check_serp``            — SERP position check
        ``analyse_sales``         — WooCommerce sales analysis
        ``analyse_traffic``       — performance trend analysis
        ``check_competitors``     — competitor signal check
        ``analyse_content_gaps``  — content gap analysis
        ``get_recommendations``   — growth recommendations
        ``general_task``          — best-effort routing

        Returns
        -------
        dict
            ``{status, task, site, data, error, timestamp, agent}``
        """
        log.info("StrategistAgent.handle  |  task=%s  |  site=%s", task, site)

        try:
            profile = self._load_profile(site)

            if task in ("run_analysis", "seo_audit"):
                data = self.generate_weekly_report(site, profile)

            elif task == "analyse_keywords":
                data = self.analyse_keywords(site, profile)

            elif task == "check_serp":
                keywords = self._extract_keywords(profile, params)
                market = profile.get("seo", {}).get("market", "India")
                data = self.check_serp_positions(keywords, market)

            elif task == "analyse_sales":
                data = self.analyse_sales(site, profile)

            elif task in ("analyse_traffic", "performance_check"):
                data = self.analyse_traffic(site, profile)

            elif task == "check_competitors":
                keywords = self._extract_keywords(profile, params)
                market = profile.get("seo", {}).get("market", "India")
                data = self.check_competitors(keywords, market)

            elif task == "analyse_content_gaps":
                data = self.analyse_content_gaps(site, profile)

            elif task in ("get_recommendations", "generate_recommendations"):
                # Run a lightweight set of analyses to feed the recommendation engine
                all_findings = params.get("all_findings", {})
                if not all_findings:
                    all_findings = self._quick_analysis(site, profile)
                recs = self.generate_recommendations(all_findings)
                data = {"recommendations": recs, "count": len(recs)}

            elif task == "general_task":
                data = self._handle_general_task(site, profile, params)

            else:
                log.warning("StrategistAgent: unknown task '%s'", task)
                return self._build_result(
                    task, site, "skipped", {},
                    error=f"Unknown task: {task}",
                )

            status = "success"
            if isinstance(data, dict):
                if data.get("error"):
                    status = "failed"
                elif data.get("status") == "skipped":
                    status = "skipped"

            return self._build_result(task, site, status, data)

        except Exception as exc:
            log.critical(
                "StrategistAgent.handle crashed  |  task=%s  |  %s",
                task, exc, exc_info=True,
            )
            return self._build_result(
                task, site, "failed", {},
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )

    # ══════════════════════════════════════════════════════════════════
    #  1.  KEYWORD ANALYSIS
    # ══════════════════════════════════════════════════════════════════

    def analyse_keywords(self, site: str, profile: dict) -> dict:
        """
        Analyse target keyword coverage on the site homepage.

        For each keyword in the profile, checks presence in:
            1. Page ``<title>``
            2. Meta description
            3. ``<h1>`` tags
            4. Body text
            5. URL structure

        Each keyword scores 0–5 (one point per location).

        Parameters
        ----------
        site : str
            Target site URL or domain.
        profile : dict
            Site profile containing SEO target keywords.

        Returns
        -------
        dict
            ``{keyword_scores, gaps, opportunities, recommendations,
              total_keywords, average_score}``
        """
        url = _normalise_url(site)
        keywords = self._extract_keywords(profile, {})

        log.info("Keyword analysis  |  %s  |  %d keywords", url, len(keywords))

        if not keywords:
            return {
                "keyword_scores": {},
                "gaps": [],
                "opportunities": [],
                "recommendations": ["No target keywords defined in profile. Add target keywords to begin SEO tracking."],
                "total_keywords": 0,
                "average_score": 0,
            }

        # ── Fetch homepage ──
        title_text, meta_desc, h1_texts, body_text, soup = self._fetch_page_elements(url)
        url_lower = url.lower()

        # ── Score each keyword ──
        keyword_scores: Dict[str, Dict[str, Any]] = {}
        gaps: List[Dict[str, Any]] = []
        opportunities: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        total_score = 0

        for kw_data in keywords:
            kw = kw_data if isinstance(kw_data, str) else kw_data.get("keyword", "")
            translation = kw_data.get("translation", "") if isinstance(kw_data, dict) else ""
            priority = kw_data.get("priority", 3) if isinstance(kw_data, dict) else 3

            if not kw:
                continue

            kw_lower = kw.lower()
            score = 0
            locations: Dict[str, bool] = {}

            # Check title
            in_title = kw_lower in title_text.lower()
            locations["title"] = in_title
            if in_title:
                score += 1

            # Check meta description
            in_desc = kw_lower in meta_desc.lower()
            locations["meta_description"] = in_desc
            if in_desc:
                score += 1

            # Check H1
            in_h1 = any(kw_lower in h.lower() for h in h1_texts)
            locations["h1"] = in_h1
            if in_h1:
                score += 1

            # Check body text
            in_body = kw_lower in body_text.lower()
            locations["body"] = in_body
            if in_body:
                score += 1

            # Check URL
            # Check keyword variations including partial matches
            kw_url_safe = kw_lower.replace(" ", "-").replace("ł", "l").replace("ó", "o").replace("ą", "a").replace("ę", "e").replace("ś", "s").replace("ć", "c").replace("ż", "z").replace("ź", "z").replace("ń", "n")
            in_url = kw_lower in url_lower or kw_url_safe in url_lower
            locations["url"] = in_url
            if in_url:
                score += 1

            keyword_scores[kw] = {
                "keyword": kw,
                "translation": translation,
                "priority": priority,
                "score": score,
                "max_score": 5,
                "locations": locations,
            }

            total_score += score

            # Classify
            if score == 0:
                gaps.append({
                    "keyword": kw,
                    "translation": translation,
                    "priority": priority,
                    "recommendation": f"'{kw}' not found anywhere on homepage. Add it to title, H1, and body content.",
                })
            elif score <= 2:
                missing = [loc for loc, present in locations.items() if not present]
                opportunities.append({
                    "keyword": kw,
                    "translation": translation,
                    "priority": priority,
                    "score": score,
                    "missing_from": missing,
                    "recommendation": f"'{kw}' found in {score}/5 locations. Easy win: add to {', '.join(missing[:2])}.",
                })

        average_score = round(total_score / len(keyword_scores), 2) if keyword_scores else 0

        # ── Generate recommendations ──
        if gaps:
            high_prio_gaps = [g for g in gaps if g.get("priority", 3) <= 2]
            if high_prio_gaps:
                kw_list = ", ".join(g["keyword"] for g in high_prio_gaps[:3])
                recommendations.append(
                    f"PRIORITY: {len(high_prio_gaps)} high-priority keywords have ZERO presence on homepage: {kw_list}. "
                    "These must be integrated into page content immediately."
                )
            else:
                kw_list = ", ".join(g["keyword"] for g in gaps[:3])
                recommendations.append(
                    f"{len(gaps)} target keyword(s) not found on homepage: {kw_list}. "
                    "Add them to page content, meta tags, and headings."
                )

        if opportunities:
            kw_list = ", ".join(o["keyword"] for o in opportunities[:3])
            recommendations.append(
                f"{len(opportunities)} keyword(s) are easy wins (score 1-2): {kw_list}. "
                "Adding these to title or meta description can boost rankings quickly."
            )

        if average_score >= 4:
            recommendations.append(
                "Strong keyword coverage overall. Focus on maintaining positions and expanding to long-tail variants."
            )
        elif average_score >= 2.5:
            recommendations.append(
                f"Average keyword score is {average_score}/5. Good foundation but significant room for improvement."
            )
        else:
            recommendations.append(
                f"Average keyword score is {average_score}/5. Homepage needs major SEO content overhaul."
            )

        result = {
            "site": site,
            "analysed_at": _utcnow_iso(),
            "keyword_scores": keyword_scores,
            "total_keywords": len(keyword_scores),
            "average_score": average_score,
            "gaps": gaps,
            "gap_count": len(gaps),
            "opportunities": opportunities,
            "opportunity_count": len(opportunities),
            "recommendations": recommendations,
        }

        log.log_action(
            action="keyword_analysis",
            agent="strategist",
            status="success",
            details={
                "site": site,
                "keywords": len(keyword_scores),
                "avg_score": average_score,
                "gaps": len(gaps),
                "opportunities": len(opportunities),
            },
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  2.  SERP POSITION CHECK
    # ══════════════════════════════════════════════════════════════════

    def check_serp_positions(
        self,
        keywords: list,
        market: str,
    ) -> dict:
        """
        Check where falconherbs.com ranks for target keywords on Google.

        Queries google.com with India/global locale parameters and scans the
        first 3 pages (30 results) for the target domain.

        Polite to Google:
            • 2-second delay between queries
            • Maximum 5 keywords per run
            • Browser-like User-Agent to avoid instant blocking

        Parameters
        ----------
        keywords : list
            List of keyword strings or keyword dicts from the profile.
        market : str
            Target market (e.g. ``"India"``).

        Returns
        -------
        dict
            ``{positions, ranked_keywords, unranked_keywords,
              keywords_checked, market}``
        """
        # ── Extract raw keyword strings ──
        kw_strings: List[str] = []
        for kw in keywords:
            if isinstance(kw, dict):
                kw_strings.append(kw.get("keyword", ""))
            elif isinstance(kw, str):
                kw_strings.append(kw)
        kw_strings = [k for k in kw_strings if k]

        # Enforce limit
        kw_to_check = kw_strings[:SERP_MAX_KW]

        log.info(
            "SERP position check  |  %d keywords  |  market=%s  |  max=%d",
            len(kw_to_check), market, SERP_MAX_KW,
        )

        positions: Dict[str, Any] = {}
        ranked: List[str] = []
        unranked: List[str] = []

        target_domain = "falconherbs.com"

        for idx, keyword in enumerate(kw_to_check):
            # ── Polite delay (skip before first query) ──
            if idx > 0:
                time.sleep(SERP_DELAY)

            log.info("SERP checking: '%s' (%d/%d)", keyword, idx + 1, len(kw_to_check))

            position = self._query_google_position(keyword, target_domain)

            positions[keyword] = position

            if position is not None and position != "not_found":
                ranked.append(keyword)
            else:
                unranked.append(keyword)

        result = {
            "analysed_at": _utcnow_iso(),
            "market": market,
            "target_domain": target_domain,
            "keywords_checked": len(kw_to_check),
            "keywords_skipped": max(0, len(kw_strings) - SERP_MAX_KW),
            "positions": positions,
            "ranked_keywords": ranked,
            "ranked_count": len(ranked),
            "unranked_keywords": unranked,
            "unranked_count": len(unranked),
        }

        log.log_action(
            action="serp_check",
            agent="strategist",
            status="success",
            details={
                "keywords_checked": len(kw_to_check),
                "ranked": len(ranked),
                "unranked": len(unranked),
            },
        )

        return result

    def _query_google_position(
        self,
        keyword: str,
        target_domain: str,
    ) -> Any:
        """
        Query Google for *keyword* and find *target_domain* position.

        Returns
        -------
        int or str
            Position (1-30) if found, ``"not_found"`` if not in top 30,
            ``"error"`` on failure.
        """
        try:
            # Build Google search URL for global/India market
            params = {
                "q": keyword,
                "hl": "en",
                "gl": "in",
                "num": "10",
            }

            # Check up to SERP_PAGES pages
            for page in range(SERP_PAGES):
                if page > 0:
                    params["start"] = str(page * 10)

                try:
                    resp = requests.get(
                        "https://www.google.com/search",
                        params=params,
                        headers={
                            "User-Agent": BROWSER_UA,
                            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.5",
                        },
                        timeout=HTTP_TIMEOUT,
                        allow_redirects=True,
                    )

                    if resp.status_code == 429:
                        log.warning("Google rate-limited us (429) — stopping SERP checks")
                        return "rate_limited"

                    if resp.status_code != 200:
                        log.warning(
                            "Google returned %d for '%s'",
                            resp.status_code, keyword,
                        )
                        return "error"

                    # Parse results
                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Google organic results are in various containers.
                    # We look for all links and check their hrefs.
                    position = (page * 10) + 1
                    result_links = soup.find_all("a", href=True)

                    for link in result_links:
                        href = link.get("href", "")

                        # Google wraps results in /url?q= or directly has the URL
                        if target_domain in href:
                            log.info(
                                "Found %s at position ~%d for '%s'",
                                target_domain, position, keyword,
                            )
                            return position

                        # Track position for organic-looking results
                        # Check if href looks like an organic result (external URL)
                        if href.startswith("http") and "google" not in href:
                            position += 1

                except requests.RequestException as exc:
                    log.warning("SERP request failed for '%s' page %d: %s", keyword, page, exc)
                    return "error"

                # Small extra delay between pages of the same keyword
                if page < SERP_PAGES - 1:
                    time.sleep(1.0)

            return "not_found"

        except Exception as exc:
            log.warning("SERP query error for '%s': %s", keyword, exc)
            return "error"

    # ══════════════════════════════════════════════════════════════════
    #  3.  WOOCOMMERCE SALES ANALYSIS
    # ══════════════════════════════════════════════════════════════════

    def analyse_sales(self, site: str, profile: dict) -> dict:
        """
        Analyse WooCommerce sales data via the REST API.

        Pulls last 30 days of sales and top sellers, calculates
        KPIs (revenue, orders, AOV), and generates recommendations.

        Gracefully skips if WooCommerce credentials are missing or
        invalid — returns a skip result, never crashes.

        Parameters
        ----------
        site : str
            Target site URL or domain.
        profile : dict
            Site profile with WooCommerce API credentials.

        Returns
        -------
        dict
            ``{sales_summary, top_products, top_by_quantity,
              period, recommendations, api_accessible}``
        """
        url = _normalise_url(site)
        log.info("Sales analysis  |  %s", url)

        # ── Resolve credentials ──
        creds = profile.get("credentials", {})
        api_key = self._resolve_credential(creds.get("woocommerce_api_key", ""))
        api_secret = self._resolve_credential(creds.get("woocommerce_api_secret", ""))
        api_url = creds.get("woocommerce_api_url", "")

        if not api_url:
            api_url = urljoin(url + "/", "wp-json/wc/v3/")

        if not api_key or not api_secret:
            log.info("WooCommerce API credentials not configured — skipping sales analysis")
            return {
                "status": "skipped",
                "api_accessible": False,
                "reason": "WooCommerce API key/secret not configured in environment",
                "recommendation": "Set FALCONHERBS_WC_API_KEY and FALCONHERBS_WC_API_SECRET in .env",
                "sales_summary": {},
                "top_products": [],
                "recommendations": [
                    "Configure WooCommerce REST API credentials to enable sales tracking.",
                ],
            }

        auth = (api_key, api_secret)

        # ── Date range: last 30 days ──
        now = _utcnow()
        date_min = (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
        date_max = now.strftime("%Y-%m-%dT23:59:59")

        sales_summary: Dict[str, Any] = {}
        top_products: List[Dict[str, Any]] = []
        top_by_quantity: List[Dict[str, Any]] = []
        recommendations: List[str] = []
        api_accessible = False

        # ── Sales reports ──
        try:
            sales_resp = self._session.get(
                f"{api_url}reports/sales",
                params={"date_min": date_min, "date_max": date_max},
                auth=auth,
                timeout=HTTP_TIMEOUT,
            )

            if sales_resp.status_code == 200:
                api_accessible = True
                sales_data = sales_resp.json()

                if isinstance(sales_data, list) and sales_data:
                    report = sales_data[0]
                    total_sales = float(report.get("total_sales", 0))
                    total_orders = int(report.get("total_orders", 0))
                    avg_order_value = round(total_sales / total_orders, 2) if total_orders > 0 else 0
                    total_items = int(report.get("total_items", 0))
                    total_customers = int(report.get("total_customers", 0))

                    sales_summary = {
                        "total_revenue_inr": total_sales,
                        "total_orders": total_orders,
                        "average_order_value_inr": avg_order_value,
                        "total_items_sold": total_items,
                        "total_customers": total_customers,
                        "total_refunds": float(report.get("total_refunds", 0)),
                        "net_revenue_inr": float(report.get("net_sales", total_sales)),
                        "period_days": 30,
                    }

                    # ── Revenue recommendations ──
                    if total_orders == 0:
                        recommendations.append(
                            "CRITICAL: Zero orders in the last 30 days. "
                            "Check checkout flow, payment gateway, and site traffic."
                        )
                    elif avg_order_value < 50:
                        recommendations.append(
                            f"Average order value is ₹{avg_order_value:.2f}. "
                            "Consider product bundles, minimum order thresholds, or cross-selling to increase AOV."
                        )

                    if total_customers > 0 and total_orders > total_customers:
                        repeat_rate = round(
                            ((total_orders - total_customers) / total_customers) * 100, 1
                        )
                        recommendations.append(
                            f"Estimated repeat purchase rate: {repeat_rate}%. "
                            "Consider a loyalty program or email campaigns to increase retention."
                        )

            elif sales_resp.status_code in (401, 403):
                log.warning("WooCommerce API auth failed (HTTP %d)", sales_resp.status_code)
                return {
                    "status": "skipped",
                    "api_accessible": False,
                    "reason": f"API authentication failed (HTTP {sales_resp.status_code})",
                    "sales_summary": {},
                    "top_products": [],
                    "recommendations": [
                        "WooCommerce API credentials are invalid. Regenerate them in WooCommerce → Settings → REST API.",
                    ],
                }
            else:
                log.warning("WooCommerce sales API returned %d", sales_resp.status_code)

        except requests.RequestException as exc:
            log.warning("WooCommerce sales API error: %s", exc)
            if not api_accessible:
                return {
                    "status": "skipped",
                    "api_accessible": False,
                    "reason": f"API request failed: {str(exc)[:200]}",
                    "sales_summary": {},
                    "top_products": [],
                    "recommendations": [
                        "Could not reach WooCommerce REST API. Check site accessibility and API URL.",
                    ],
                }

        # ── Top sellers ──
        try:
            top_resp = self._session.get(
                f"{api_url}reports/top_sellers",
                params={"date_min": date_min, "date_max": date_max, "per_page": "10"},
                auth=auth,
                timeout=HTTP_TIMEOUT,
            )

            if top_resp.status_code == 200:
                api_accessible = True
                top_data = top_resp.json()

                if isinstance(top_data, list):
                    for item in top_data[:5]:
                        top_products.append({
                            "product_id": item.get("product_id"),
                            "name": item.get("title", f"Product #{item.get('product_id', '?')}"),
                            "quantity_sold": int(item.get("quantity", 0)),
                        })

                    # Top by quantity (same data, re-sorted)
                    top_by_quantity = sorted(
                        [
                            {
                                "product_id": item.get("product_id"),
                                "name": item.get("title", f"Product #{item.get('product_id', '?')}"),
                                "quantity_sold": int(item.get("quantity", 0)),
                            }
                            for item in top_data[:10]
                        ],
                        key=lambda x: x["quantity_sold"],
                        reverse=True,
                    )[:5]

        except requests.RequestException as exc:
            log.warning("WooCommerce top sellers API error: %s", exc)

        # ── General recommendations ──
        if not top_products:
            recommendations.append(
                "No top-selling products data available. Ensure products are published and visible."
            )

        if not recommendations:
            recommendations.append(
                "Sales data retrieved successfully. Set up weekly tracking to monitor trends."
            )

        result = {
            "site": site,
            "analysed_at": _utcnow_iso(),
            "api_accessible": api_accessible,
            "period": f"{date_min[:10]} to {date_max[:10]}",
            "period_days": 30,
            "sales_summary": sales_summary,
            "top_products": top_products,
            "top_by_quantity": top_by_quantity,
            "recommendations": recommendations,
        }

        log.log_action(
            action="sales_analysis",
            agent="strategist",
            status="success" if api_accessible else "skipped",
            details={
                "site": site,
                "api_accessible": api_accessible,
                "revenue": sales_summary.get("total_revenue_inr", 0),
                "orders": sales_summary.get("total_orders", 0),
            },
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  4.  TRAFFIC TREND ANALYSIS
    # ══════════════════════════════════════════════════════════════════

    def analyse_traffic(self, site: str, profile: dict) -> dict:
        """
        Analyse performance trends from stored audit reports.

        Reads ``data/reports/`` for previous DeveloperAgent and
        Strategist scan results, extracts response time samples,
        identifies trends (improving/degrading/stable), and assigns
        a performance grade (A–F).

        Parameters
        ----------
        site : str
            Target site.
        profile : dict
            Site profile with performance targets.

        Returns
        -------
        dict
            ``{trend, performance_grade, average_ms, target_ms,
              samples, recommendations}``
        """
        log.info("Traffic/performance trend analysis  |  %s", site)

        target_ms = profile.get("performance_targets", {}).get(
            "response_time_target_ms", 1500,
        )
        current_ms = profile.get("performance_targets", {}).get(
            "current_response_time_ms", None,
        )

        # ── Collect response time samples from stored reports ──
        samples: List[Dict[str, Any]] = []
        site_slug = _site_slug(site)

        try:
            if REPORTS_DIR.exists():
                for report_file in sorted(REPORTS_DIR.glob("*.json")):
                    try:
                        data = json.loads(report_file.read_text(encoding="utf-8"))
                        ts = self._extract_response_time_from_report(data)
                        if ts is not None:
                            samples.append({
                                "file": report_file.name,
                                "response_time_ms": ts,
                                "timestamp": data.get("analysed_at", data.get("scan_time", data.get("checked_at", ""))),
                            })
                    except (json.JSONDecodeError, OSError):
                        continue
        except Exception as exc:
            log.warning("Error scanning reports directory: %s", exc)

        # ── If we have the profile's current value, add it ──
        if current_ms is not None:
            samples.append({
                "file": "profile",
                "response_time_ms": current_ms,
                "timestamp": profile.get("performance_targets", {}).get(
                    "response_time_measured_at", _utcnow_iso(),
                ),
            })

        # ── Also do a live check right now ──
        live_ms = self._live_response_time(_normalise_url(site))
        if live_ms is not None:
            samples.append({
                "file": "live_check",
                "response_time_ms": live_ms,
                "timestamp": _utcnow_iso(),
            })

        # ── Analyse trend ──
        recommendations: List[str] = []
        time_values = [s["response_time_ms"] for s in samples if s["response_time_ms"] is not None]

        if len(time_values) == 0:
            average_ms = 0
            trend_direction = "unknown"
            grade = "?"
        elif len(time_values) == 1:
            average_ms = round(time_values[0], 1)
            trend_direction = "insufficient_data"
            grade = _grade_performance(average_ms)
        else:
            average_ms = round(sum(time_values) / len(time_values), 1)
            grade = _grade_performance(average_ms)

            # Compare first half to second half for trend
            mid = len(time_values) // 2
            first_half_avg = sum(time_values[:mid]) / mid if mid > 0 else 0
            second_half_avg = sum(time_values[mid:]) / (len(time_values) - mid)

            change_pct = 0
            if first_half_avg > 0:
                change_pct = round(
                    ((second_half_avg - first_half_avg) / first_half_avg) * 100, 1,
                )

            if change_pct > 15:
                trend_direction = "degrading"
                recommendations.append(
                    f"Performance is DEGRADING — response time increased ~{change_pct}% "
                    f"(from ~{first_half_avg:.0f}ms to ~{second_half_avg:.0f}ms). "
                    "Investigate server load, database growth, and recent changes."
                )
            elif change_pct < -15:
                trend_direction = "improving"
                recommendations.append(
                    f"Performance is IMPROVING — response time decreased ~{abs(change_pct)}%. "
                    "Continue monitoring."
                )
            else:
                trend_direction = "stable"

        # ── Grade-based recommendations ──
        if grade == "F":
            recommendations.append(
                f"CRITICAL: Average response time {average_ms}ms is unacceptable. "
                "Enable PHP OPcache, install object caching (Redis), and check for runaway queries."
            )
        elif grade == "D":
            recommendations.append(
                f"Response time {average_ms}ms is poor (target: {target_ms}ms). "
                "Priority: enable gzip compression, optimize images, and review heavy plugins."
            )
        elif grade == "C":
            recommendations.append(
                f"Response time {average_ms}ms meets minimum but exceeds target ({target_ms}ms). "
                "Optimise render-blocking CSS/JS and consider a CDN."
            )
        elif grade in ("A", "B"):
            recommendations.append(
                f"Response time {average_ms}ms is good (grade {grade}). "
                "Monitor for regressions."
            )

        # ── Target comparison ──
        if average_ms > 0 and average_ms > target_ms:
            gap_pct = round(((average_ms - target_ms) / target_ms) * 100, 1)
            recommendations.append(
                f"Current response time exceeds target by {gap_pct}% "
                f"({average_ms:.0f}ms vs {target_ms}ms target)."
            )

        result = {
            "site": site,
            "analysed_at": _utcnow_iso(),
            "trend": {
                "direction": trend_direction,
                "average_ms": average_ms,
                "target_ms": target_ms,
                "sample_count": len(time_values),
            },
            "performance_grade": grade,
            "average_ms": average_ms,
            "target_ms": target_ms,
            "samples": samples[-20:],   # keep the latest 20 for report readability
            "recommendations": recommendations,
        }

        log.log_action(
            action="traffic_analysis",
            agent="strategist",
            status="success",
            details={
                "site": site,
                "avg_ms": average_ms,
                "grade": grade,
                "trend": trend_direction,
                "samples": len(time_values),
            },
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  5.  COMPETITOR SIGNAL CHECK
    # ══════════════════════════════════════════════════════════════════

    def check_competitors(
        self,
        keywords: list,
        market: str,
    ) -> dict:
        """
        Identify competing domains ranking for top target keywords.

        For the top 3 keywords, queries Google, extracts ranking
        domains, and checks basic security/performance signals of
        each competitor.

        Parameters
        ----------
        keywords : list
            Target keywords (strings or dicts).
        market : str
            Target market.

        Returns
        -------
        dict
            ``{competitors_found, our_positions,
              competitive_gap_assessment, keywords_analysed}``
        """
        log.info("Competitor signal check  |  market=%s", market)

        # ── Extract and limit keywords ──
        kw_strings: List[str] = []
        for kw in keywords:
            if isinstance(kw, dict):
                kw_strings.append(kw.get("keyword", ""))
            elif isinstance(kw, str):
                kw_strings.append(kw)
        kw_strings = [k for k in kw_strings if k]

        # Top 3 keywords for competitor check
        kw_to_check = kw_strings[:3]

        target_domain = "falconherbs.com"
        all_competitors: Dict[str, Dict[str, Any]] = {}
        our_positions: Dict[str, Any] = {}
        keywords_analysed: List[str] = []

        for idx, keyword in enumerate(kw_to_check):
            if idx > 0:
                time.sleep(SERP_DELAY)

            log.info("Competitor check: '%s' (%d/%d)", keyword, idx + 1, len(kw_to_check))

            try:
                resp = requests.get(
                    "https://www.google.com/search",
                    params={"q": keyword, "hl": "en", "gl": "in", "num": "10"},
                    headers={
                        "User-Agent": BROWSER_UA,
                        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.5",
                    },
                    timeout=HTTP_TIMEOUT,
                    allow_redirects=True,
                )

                if resp.status_code != 200:
                    log.warning("Google returned %d for competitor check", resp.status_code)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Extract domains from search result links
                position = 0
                our_pos_for_kw = "not_found"

                for link in soup.find_all("a", href=True):
                    href = link["href"]

                    # Skip Google's own links
                    if "google" in href and "/search" in href:
                        continue

                    parsed = urlparse(href)
                    domain = parsed.netloc.replace("www.", "").lower()

                    if not domain or "." not in domain:
                        continue
                    if domain in ("google.com", "youtube.com",
                                  "facebook.com", "twitter.com", "wikipedia.org",
                                  "webcache.googleusercontent.com"):
                        continue

                    # Only count if it looks like a real external domain
                    if not parsed.scheme.startswith("http"):
                        continue

                    position += 1
                    if position > 10:
                        break

                    # Is this us?
                    if target_domain in domain:
                        our_pos_for_kw = position
                        continue

                    # Track competitor
                    if domain not in all_competitors:
                        all_competitors[domain] = {
                            "domain": domain,
                            "keywords_ranked_for": [],
                            "best_position": position,
                            "appearances": 0,
                        }

                    all_competitors[domain]["keywords_ranked_for"].append(keyword)
                    all_competitors[domain]["appearances"] += 1
                    if position < all_competitors[domain]["best_position"]:
                        all_competitors[domain]["best_position"] = position

                our_positions[keyword] = our_pos_for_kw
                keywords_analysed.append(keyword)

            except requests.RequestException as exc:
                log.warning("Competitor check failed for '%s': %s", keyword, exc)
                continue

        # ── Check competitor signals (top 5 by appearances) ──
        sorted_competitors = sorted(
            all_competitors.values(),
            key=lambda c: (-c["appearances"], c["best_position"]),
        )[:5]

        competitors_with_signals: List[Dict[str, Any]] = []

        for comp in sorted_competitors:
            domain = comp["domain"]
            signal = self._check_domain_signals(domain)
            comp_entry = {
                **comp,
                "has_ssl": signal.get("has_ssl", None),
                "response_time_ms": signal.get("response_time_ms", None),
                "has_security_headers": signal.get("has_security_headers", None),
            }
            competitors_with_signals.append(comp_entry)

        # ── Competitive gap assessment ──
        our_ranked_count = sum(1 for p in our_positions.values() if p != "not_found")
        total_checked = len(kw_to_check)

        if our_ranked_count == total_checked and total_checked > 0:
            assessment = (
                f"STRONG: falconherbs.com ranks for all {total_checked} checked keywords. "
                "Focus on improving positions and defending rankings."
            )
        elif our_ranked_count > 0:
            assessment = (
                f"MODERATE: falconherbs.com ranks for {our_ranked_count}/{total_checked} keywords. "
                f"Gap exists for: {', '.join(k for k, p in our_positions.items() if p == 'not_found')}. "
                "These keywords need content investment."
            )
        elif total_checked > 0:
            assessment = (
                f"WEAK: falconherbs.com does not rank in top 10 for any of the "
                f"{total_checked} checked keywords. Significant SEO work needed. "
                "Competitors are dominating these search terms."
            )
        else:
            assessment = "UNKNOWN: No keywords could be checked. Verify Google accessibility."

        result = {
            "analysed_at": _utcnow_iso(),
            "market": market,
            "target_domain": target_domain,
            "keywords_analysed": keywords_analysed,
            "our_positions": our_positions,
            "competitors_found": competitors_with_signals,
            "competitor_count": len(competitors_with_signals),
            "competitive_gap_assessment": assessment,
        }

        log.log_action(
            action="competitor_check",
            agent="strategist",
            status="success",
            details={
                "keywords": len(kw_to_check),
                "competitors": len(competitors_with_signals),
                "our_ranked": our_ranked_count,
            },
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  6.  CONTENT GAP ANALYSIS
    # ══════════════════════════════════════════════════════════════════

    def analyse_content_gaps(self, site: str, profile: dict) -> dict:
        """
        Assess content depth and structure on the homepage.

        Checks:
            • Visible word count (target: >300)
            • Internal link count (target: >10)
            • Product category links
            • Blog/articles section presence
            • Content structure (headings hierarchy)

        Parameters
        ----------
        site : str
            Target site.
        profile : dict
            Site profile.

        Returns
        -------
        dict
            ``{content_metrics, gaps, content_recommendations}``
        """
        url = _normalise_url(site)
        log.info("Content gap analysis  |  %s", url)

        title_text, meta_desc, h1_texts, body_text, soup = self._fetch_page_elements(url)

        if soup is None:
            return {
                "site": site,
                "error": "Cannot fetch homepage for content analysis",
                "content_metrics": {},
                "gaps": ["Site unreachable"],
                "content_recommendations": ["Fix site accessibility before content analysis"],
            }

        # ── Word count ──
        words = body_text.split()
        word_count = len(words)

        # ── Internal links ──
        parsed_site = urlparse(url)
        site_domain = parsed_site.netloc.replace("www.", "").lower()

        internal_links: List[str] = []
        external_links: List[str] = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            # Resolve relative URLs
            if href.startswith("/"):
                internal_links.append(href)
            elif href.startswith("http"):
                link_domain = urlparse(href).netloc.replace("www.", "").lower()
                if site_domain in link_domain:
                    internal_links.append(href)
                else:
                    external_links.append(href)

        # ── Category links (heuristic) ──
        category_patterns = [
            "/product-category/", "/kategoria-produktu/",
            "/category/", "/kategoria/", "/shop/",
            "/sklep/", "/produkty/", "/products/",
        ]
        category_links = [
            link for link in internal_links
            if any(pat in link.lower() for pat in category_patterns)
        ]

        # ── Blog / articles ──
        blog_patterns = ["/blog", "/artykuly", "/articles", "/news", "/aktualnosci", "/poradnik"]
        has_blog = any(
            any(pat in link.lower() for pat in blog_patterns)
            for link in internal_links
        )

        # Also check for a blog link in navigation
        nav_links = []
        for nav in soup.find_all(["nav", "header"]):
            for a in nav.find_all("a", href=True):
                nav_links.append(a["href"].lower())
        has_blog_nav = any(any(pat in nl for pat in blog_patterns) for nl in nav_links)
        has_blog = has_blog or has_blog_nav

        # ── Heading structure ──
        headings: Dict[str, int] = {}
        for level in range(1, 7):
            tag = f"h{level}"
            count = len(soup.find_all(tag))
            if count > 0:
                headings[tag] = count

        # ── Content metrics ──
        content_metrics = {
            "word_count": word_count,
            "word_count_target": _MIN_HOMEPAGE_WORDS,
            "word_count_passed": word_count >= _MIN_HOMEPAGE_WORDS,
            "internal_links": len(internal_links),
            "internal_links_target": _MIN_INTERNAL_LINKS,
            "internal_links_passed": len(internal_links) >= _MIN_INTERNAL_LINKS,
            "external_links": len(external_links),
            "category_links": len(category_links),
            "has_blog_section": has_blog,
            "heading_structure": headings,
            "h1_count": headings.get("h1", 0),
            "h2_count": headings.get("h2", 0),
            "title_length": len(title_text),
            "meta_description_length": len(meta_desc),
            "images_count": len(soup.find_all("img")),
            "images_with_alt": len([
                img for img in soup.find_all("img")
                if img.get("alt", "").strip()
            ]),
        }

        # ── Identify gaps ──
        gaps: List[str] = []
        content_recommendations: List[str] = []

        if word_count < _MIN_HOMEPAGE_WORDS:
            gaps.append(f"Homepage has only {word_count} words (minimum: {_MIN_HOMEPAGE_WORDS})")
            content_recommendations.append(
                f"Add more descriptive content to the homepage. Currently {word_count} words — "
                f"target at least {_MIN_HOMEPAGE_WORDS}. Include product descriptions, "
                "brand story, and herbal expertise content in English targeting global markets."
            )

        if len(internal_links) < _MIN_INTERNAL_LINKS:
            gaps.append(f"Only {len(internal_links)} internal links (minimum: {_MIN_INTERNAL_LINKS})")
            content_recommendations.append(
                "Add more internal links to product categories, popular products, and informational pages. "
                "Internal linking improves crawlability and distributes page authority."
            )

        if len(category_links) == 0:
            gaps.append("No product category links found on homepage")
            content_recommendations.append(
                "Add visible links to your main product categories on the homepage. "
                "This helps both users and search engines discover your full inventory."
            )

        if not has_blog:
            gaps.append("No blog or articles section detected")
            content_recommendations.append(
                "Create a blog section with articles about herbal remedies, tea preparation, "
                "and natural health topics in English. Blog content targets long-tail keywords "
                "and drives organic traffic. Suggested topics: 'Jak parzyć herbatę ziołową', "
                "'Zioła na odporność — poradnik', 'Naturalne suplementy diety'."
            )

        if headings.get("h1", 0) == 0:
            gaps.append("No H1 heading on homepage")
            content_recommendations.append("Add exactly one H1 tag containing your primary keyword.")
        elif headings.get("h1", 0) > 1:
            gaps.append(f"Multiple H1 tags ({headings['h1']}) — should be exactly 1")
            content_recommendations.append(
                f"Reduce H1 tags from {headings['h1']} to exactly 1. Use H2 for sub-sections."
            )

        if headings.get("h2", 0) == 0:
            gaps.append("No H2 headings — lack of content structure")
            content_recommendations.append(
                "Add H2 headings to structure your homepage content. "
                "Use them for sections like 'Najpopularniejsze zioła', 'Kategorie produktów', etc."
            )

        total_images = content_metrics["images_count"]
        images_with_alt = content_metrics["images_with_alt"]
        if total_images > 0 and images_with_alt < total_images:
            missing_alt = total_images - images_with_alt
            gaps.append(f"{missing_alt} images missing alt text")
            content_recommendations.append(
                f"{missing_alt}/{total_images} images lack alt text. "
                "Add descriptive alt attributes in English for accessibility and image SEO."
            )

        if not gaps:
            content_recommendations.append(
                "Homepage content structure meets all minimum thresholds. "
                "Focus on content quality, keyword density, and regular updates."
            )

        result = {
            "site": site,
            "url": url,
            "analysed_at": _utcnow_iso(),
            "content_metrics": content_metrics,
            "gaps": gaps,
            "gap_count": len(gaps),
            "content_recommendations": content_recommendations,
        }

        log.log_action(
            action="content_gap_analysis",
            agent="strategist",
            status="success",
            details={
                "site": site,
                "word_count": word_count,
                "internal_links": len(internal_links),
                "gaps": len(gaps),
                "has_blog": has_blog,
            },
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  7.  WEEKLY STRATEGY REPORT
    # ══════════════════════════════════════════════════════════════════

    def generate_weekly_report(self, site: str, profile: dict) -> dict:
        """
        Generate a comprehensive weekly strategy report.

        Orchestrates all analysis methods, assembles findings into
        a unified report, saves to disk, and sends a human-readable
        summary via WhatsApp.

        Parameters
        ----------
        site : str
            Target site.
        profile : dict
            Site profile.

        Returns
        -------
        dict
            ``{report_path, summary_text, keyword_analysis,
              traffic_analysis, content_analysis, sales_analysis,
              recommendations, generated_at}``
        """
        log.info("━" * 60)
        log.info("Generating weekly strategy report  |  %s", site)
        log.info("━" * 60)

        report_start = time.monotonic()

        # ── Run all analyses ──
        keyword_data = {}
        traffic_data = {}
        content_data = {}
        sales_data = {}

        try:
            keyword_data = self.analyse_keywords(site, profile)
        except Exception as exc:
            log.warning("Keyword analysis failed: %s", exc)
            keyword_data = {"error": str(exc)[:200]}

        try:
            traffic_data = self.analyse_traffic(site, profile)
        except Exception as exc:
            log.warning("Traffic analysis failed: %s", exc)
            traffic_data = {"error": str(exc)[:200]}

        try:
            content_data = self.analyse_content_gaps(site, profile)
        except Exception as exc:
            log.warning("Content gap analysis failed: %s", exc)
            content_data = {"error": str(exc)[:200]}

        try:
            sales_data = self.analyse_sales(site, profile)
        except Exception as exc:
            log.warning("Sales analysis failed: %s", exc)
            sales_data = {"error": str(exc)[:200], "status": "skipped"}

        # ── Assemble all findings for recommendation engine ──
        all_findings = {
            "keyword_analysis": keyword_data,
            "traffic_analysis": traffic_data,
            "content_analysis": content_data,
            "sales_analysis": sales_data,
        }

        # ── Generate prioritised recommendations ──
        recommendations = self.generate_recommendations(all_findings)

        duration = time.monotonic() - report_start

        # ── Build full report ──
        report = {
            "report_type": "weekly_strategy",
            "site": site,
            "generated_at": _utcnow_iso(),
            "generation_time_s": round(duration, 2),
            "profile_version": profile.get("metadata", {}).get("profile_version", "unknown"),
            "keyword_analysis": keyword_data,
            "traffic_analysis": traffic_data,
            "content_analysis": content_data,
            "sales_analysis": sales_data,
            "recommendations": recommendations,
            "recommendation_count": len(recommendations),
        }

        # ── Save report ──
        report_path = self._save_report(site, report)
        report["report_path"] = report_path

        # ── Format and send WhatsApp summary ──
        summary_text = self._format_telegram_summary(report)
        report["summary_text"] = summary_text

        self._send_telegram_summary(summary_text)

        log.info(
            "Strategy report complete  |  site=%s  |  recs=%d  |  %.1fs  |  %s",
            site, len(recommendations), duration, report_path,
        )
        log.info("━" * 60)

        log.log_action(
            action="weekly_strategy_report",
            agent="strategist",
            status="success",
            details={
                "site": site,
                "report_path": report_path,
                "recommendations": len(recommendations),
                "duration_s": round(duration, 2),
            },
        )

        return report

    # ══════════════════════════════════════════════════════════════════
    #  8.  GROWTH RECOMMENDATIONS ENGINE
    # ══════════════════════════════════════════════════════════════════

    def generate_recommendations(
        self,
        all_findings: dict,
    ) -> list[dict]:
        """
        Generate prioritised growth recommendations from analysis findings.

        Scores each recommendation by:
            • **Impact** — how much will this move the needle?
            • **Effort** — how hard is it to implement?
            • **Priority score** — (impact × 3) + (inverse_effort × 2)

        Returns top 10 recommendations sorted by priority.

        Parameters
        ----------
        all_findings : dict
            Combined output from all analysis methods.

        Returns
        -------
        list[dict]
            Top 10 recommendations, each with:
            ``{id, title, description, impact, effort, priority_score,
              agent, task, category}``
        """
        log.info("Generating growth recommendations")

        raw_recs: List[Dict[str, Any]] = []
        rec_counter = 0

        def _add(
            title: str,
            description: str,
            impact: str,
            effort: str,
            agent: str,
            task: str,
            category: str = "general",
        ) -> None:
            nonlocal rec_counter
            rec_counter += 1
            priority = (_IMPACT_SCORE.get(impact, 1) * 3) + (_EFFORT_SCORE.get(effort, 1) * 2)
            raw_recs.append({
                "id": f"rec-{rec_counter:03d}",
                "title": title,
                "description": description,
                "impact": impact,
                "effort": effort,
                "priority_score": priority,
                "agent": agent,
                "task": task,
                "category": category,
            })

        # ── From keyword analysis ──
        kw_data = all_findings.get("keyword_analysis", {})
        if not kw_data.get("error"):
            avg_score = kw_data.get("average_score", 0)
            gaps = kw_data.get("gaps", [])
            opps = kw_data.get("opportunities", [])

            if avg_score < 2:
                _add(
                    "Major SEO Content Overhaul",
                    f"Average keyword score is {avg_score}/5. Homepage needs "
                    "comprehensive content rewrite with target keywords integrated naturally.",
                    impact="high", effort="high", agent="developer",
                    task="content_update", category="seo",
                )

            if gaps:
                gap_kws = ", ".join(g.get("keyword", "?") for g in gaps[:3])
                _add(
                    "Fix Keyword Gaps",
                    f"{len(gaps)} target keywords have ZERO presence on homepage: {gap_kws}. "
                    "Add these to title, headings, and body content.",
                    impact="high", effort="low", agent="developer",
                    task="content_update", category="seo",
                )

            if opps:
                opp_kws = ", ".join(o.get("keyword", "?") for o in opps[:3])
                _add(
                    "Quick Keyword Wins",
                    f"{len(opps)} keywords score 1-2/5 and are easy to improve: {opp_kws}. "
                    "Add them to meta description or H1.",
                    impact="medium", effort="low", agent="developer",
                    task="content_update", category="seo",
                )

        # ── From traffic/performance analysis ──
        traffic_data = all_findings.get("traffic_analysis", {})
        if not traffic_data.get("error"):
            grade = traffic_data.get("performance_grade", "?")
            avg_ms = traffic_data.get("average_ms", 0)
            trend_dir = traffic_data.get("trend", {}).get("direction", "unknown")

            if grade in ("D", "F"):
                _add(
                    "Critical Performance Fix",
                    f"Site response time is {avg_ms:.0f}ms (grade {grade}). "
                    "Enable server-side caching, optimise database, and reduce plugin overhead.",
                    impact="high", effort="medium", agent="developer",
                    task="fix_code", category="performance",
                )

            if trend_dir == "degrading":
                _add(
                    "Investigate Performance Degradation",
                    "Response times are trending upward. Check for database bloat, "
                    "new plugin conflicts, or server resource limits.",
                    impact="high", effort="medium", agent="developer",
                    task="check_performance", category="performance",
                )

            if grade == "C":
                _add(
                    "Performance Optimisation",
                    f"Response time {avg_ms:.0f}ms is acceptable but not optimal. "
                    "Add CDN, enable lazy loading, and minify CSS/JS.",
                    impact="medium", effort="medium", agent="developer",
                    task="fix_code", category="performance",
                )

        # ── From content gap analysis ──
        content_data = all_findings.get("content_analysis", {})
        if not content_data.get("error"):
            content_gaps = content_data.get("gaps", [])
            metrics = content_data.get("content_metrics", {})

            if not metrics.get("has_blog_section", True):
                _add(
                    "Launch Blog Section",
                    "No blog detected. Create a blog with English articles about herbal "
                    "remedies, tea preparation, and natural health. Targets long-tail keywords "
                    "and drives organic traffic.",
                    impact="high", effort="high", agent="media",
                    task="create_content", category="content",
                )

            word_count = metrics.get("word_count", 0)
            if word_count < _MIN_HOMEPAGE_WORDS:
                _add(
                    "Expand Homepage Content",
                    f"Homepage has only {word_count} words (minimum: {_MIN_HOMEPAGE_WORDS}). "
                    "Add product highlights, category overviews, and trust signals.",
                    impact="medium", effort="low", agent="media",
                    task="create_content", category="content",
                )

            if not metrics.get("word_count_passed", True) or len(content_gaps) > 3:
                _add(
                    "Content Structure Improvement",
                    f"{len(content_gaps)} content gaps identified. "
                    "Improve heading hierarchy, add internal links, and ensure images have alt text.",
                    impact="medium", effort="low", agent="developer",
                    task="content_update", category="content",
                )

        # ── From sales analysis ──
        sales_data = all_findings.get("sales_analysis", {})
        if not sales_data.get("error") and sales_data.get("api_accessible"):
            summary = sales_data.get("sales_summary", {})
            orders = summary.get("total_orders", 0)
            aov = summary.get("average_order_value_inr", 0)

            if orders == 0:
                _add(
                    "Investigate Zero Sales",
                    "No orders in the last 30 days. Audit checkout flow, payment gateway "
                    "configuration, and product visibility.",
                    impact="high", effort="medium", agent="developer",
                    task="run_audit", category="revenue",
                )

            if aov > 0 and aov < 50:
                _add(
                    "Increase Average Order Value",
                    f"AOV is ₹{aov:.2f}. Implement product bundles, 'frequently bought together', "
                    "and minimum free shipping threshold to increase basket size.",
                    impact="medium", effort="medium", agent="strategist",
                    task="analyse_sales", category="revenue",
                )

        elif sales_data.get("status") == "skipped":
            _add(
                "Configure WooCommerce API",
                "Sales data unavailable — WooCommerce REST API credentials not configured. "
                "Generate API keys in WooCommerce → Settings → REST API and add to .env file.",
                impact="medium", effort="low", agent="developer",
                task="fix_code", category="setup",
            )

        # ── Always-useful recommendations ──
        _add(
            "Set Up Google Search Console",
            "Verify site ownership in Google Search Console for falconherbs.com. "
            "This provides real keyword ranking data, crawl error alerts, and indexing status.",
            impact="high", effort="low", agent="developer",
            task="general_task", category="seo",
        )

        _add(
            "Install Structured Data (Schema)",
            "Add Product schema markup to all WooCommerce products. "
            "This enables rich snippets (price, availability, reviews) in Google results.",
            impact="medium", effort="medium", agent="developer",
            task="fix_code", category="seo",
        )

        _add(
            "Email Marketing Setup",
            "Configure abandoned cart recovery emails in CartFlows and post-purchase "
            "follow-up sequences in Mailchimp. Email is the highest-ROI channel for e-commerce.",
            impact="high", effort="medium", agent="strategist",
            task="general_task", category="marketing",
        )

        # ── Sort by priority score (descending) and take top 10 ──
        raw_recs.sort(key=lambda r: r["priority_score"], reverse=True)
        top_recs = raw_recs[:10]

        # Re-number
        for i, rec in enumerate(top_recs, 1):
            rec["rank"] = i

        log.info(
            "Generated %d recommendations (showing top %d)",
            len(raw_recs), len(top_recs),
        )

        return top_recs

    # ══════════════════════════════════════════════════════════════════
    #  INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════════════

    # ── Page element fetcher (shared by keyword + content analysis) ──

    def _fetch_page_elements(
        self,
        url: str,
    ) -> Tuple[str, str, List[str], str, Optional[BeautifulSoup]]:
        """
        Fetch a page and extract core SEO elements.

        Returns
        -------
        tuple
            ``(title, meta_description, h1_texts, body_text, soup)``
            On failure: ``("", "", [], "", None)``
        """
        try:
            resp = self._session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove script/style content from body text extraction
            for element in soup(["script", "style", "noscript"]):
                element.decompose()

            title_tag = soup.find("title")
            title_text = title_tag.get_text(strip=True) if title_tag else ""

            meta_tag = soup.find("meta", attrs={"name": "description"})
            meta_desc = meta_tag.get("content", "").strip() if meta_tag else ""

            h1_tags = soup.find_all("h1")
            h1_texts = [h.get_text(strip=True) for h in h1_tags if h.get_text(strip=True)]

            body_text = soup.get_text(separator=" ", strip=True)

            return title_text, meta_desc, h1_texts, body_text, soup

        except requests.RequestException as exc:
            log.warning("Cannot fetch %s: %s", url, exc)
            return "", "", [], "", None

    # ── Live response time check ──

    def _live_response_time(self, url: str) -> Optional[float]:
        """Measure current response time in milliseconds."""
        try:
            resp = self._session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            return round(resp.elapsed.total_seconds() * 1000, 1)
        except requests.RequestException:
            return None

    # ── Domain signal checker (for competitor analysis) ──

    def _check_domain_signals(self, domain: str) -> dict:
        """
        Quick check of a competitor domain's basic signals.

        Returns
        -------
        dict
            ``{has_ssl, response_time_ms, has_security_headers}``
        """
        result: Dict[str, Any] = {
            "has_ssl": None,
            "response_time_ms": None,
            "has_security_headers": None,
        }

        try:
            url = f"https://{domain}"
            resp = self._session.get(url, timeout=5, allow_redirects=True)

            result["has_ssl"] = True
            result["response_time_ms"] = round(resp.elapsed.total_seconds() * 1000, 1)

            # Quick header check
            headers = resp.headers
            security_headers_present = sum([
                1 for h in [
                    "Strict-Transport-Security",
                    "X-Frame-Options",
                    "X-Content-Type-Options",
                    "Content-Security-Policy",
                ]
                if h in headers
            ])
            result["has_security_headers"] = security_headers_present >= 2

        except requests.exceptions.SSLError:
            result["has_ssl"] = False
            # Try HTTP
            try:
                resp = self._session.get(f"http://{domain}", timeout=5, allow_redirects=True)
                result["response_time_ms"] = round(resp.elapsed.total_seconds() * 1000, 1)
            except requests.RequestException:
                pass
        except requests.RequestException:
            pass

        return result

    # ── Response time extraction from stored reports ──

    @staticmethod
    def _extract_response_time_from_report(data: dict) -> Optional[float]:
        """Extract a response time value from a stored report dict."""
        # Try various known keys from different report formats
        for key_path in [
            ("average_ms",),
            ("data", "average_ms"),
            ("data", "response_time_ms"),
            ("vulnerability_scan", "response_time_s"),
            ("response_time_ms",),
        ]:
            obj = data
            for key in key_path:
                if isinstance(obj, dict):
                    obj = obj.get(key)
                else:
                    obj = None
                    break
            if obj is not None:
                try:
                    val = float(obj)
                    # If it looks like seconds (< 30), convert to ms
                    if val < 30 and "response_time_s" in str(key_path):
                        val *= 1000
                    return val
                except (ValueError, TypeError):
                    pass

        # Try extracting from checks array
        checks = data.get("checks", data.get("data", {}).get("checks", []))
        if isinstance(checks, list):
            for check in checks:
                if isinstance(check, dict) and check.get("check") == "response_time":
                    val_str = str(check.get("value", ""))
                    ms_match = re.search(r"([\d.]+)", val_str)
                    if ms_match:
                        try:
                            return float(ms_match.group(1))
                        except ValueError:
                            pass

        return None

    # ── Keyword extraction from profile ──

    @staticmethod
    def _extract_keywords(profile: dict, params: dict) -> list:
        """Extract keyword list from profile or params."""
        # Check params first
        if params.get("keywords"):
            return params["keywords"]

        # From profile SEO section
        seo = profile.get("seo", {})
        keywords = seo.get("target_keywords", [])

        if keywords:
            return keywords

        return []

    # ── Quick analysis (lightweight for recommendation engine) ──

    def _quick_analysis(self, site: str, profile: dict) -> dict:
        """Run lightweight analyses to feed the recommendation engine."""
        results = {}
        try:
            results["keyword_analysis"] = self.analyse_keywords(site, profile)
        except Exception:
            results["keyword_analysis"] = {"error": "failed"}

        try:
            results["traffic_analysis"] = self.analyse_traffic(site, profile)
        except Exception:
            results["traffic_analysis"] = {"error": "failed"}

        try:
            results["content_analysis"] = self.analyse_content_gaps(site, profile)
        except Exception:
            results["content_analysis"] = {"error": "failed"}

        return results

    # ── General task handler ──

    def _handle_general_task(
        self,
        site: str,
        profile: dict,
        params: dict,
    ) -> dict:
        """Route general tasks by keyword matching in description."""
        description = params.get("description", "").lower()

        if "seo" in description or "keyword" in description or "ranking" in description:
            return self.generate_weekly_report(site, profile)

        if "sales" in description or "revenue" in description or "order" in description:
            return self.analyse_sales(site, profile)

        if "traffic" in description or "performance" in description:
            return self.analyse_traffic(site, profile)

        if "content" in description or "blog" in description:
            return self.analyse_content_gaps(site, profile)

        if "competitor" in description:
            keywords = self._extract_keywords(profile, params)
            market = profile.get("seo", {}).get("market", "Poland")
            return self.check_competitors(keywords, market)

        # Default: full weekly report
        return self.generate_weekly_report(site, profile)

    # ── Profile loading ──

    def _load_profile(self, site: str) -> dict:
        """
        Load the site profile JSON from ``config/profiles/``.

        Derives the filename from the site string.

        Returns
        -------
        dict
            Parsed profile or ``{}`` if not found.
        """
        try:
            slug = site.strip().lower()
            slug = slug.replace("https://", "").replace("http://", "")
            slug = slug.rstrip("/").split("/")[0]
            slug = slug.replace("www.", "")

            candidates = [
                PROFILES_DIR / f"{slug}.json",
                PROFILES_DIR / f"{slug.split('.')[0]}.json",
            ]

            for path in candidates:
                if path.exists():
                    text = path.read_text(encoding="utf-8")
                    profile = json.loads(text)
                    log.info("Loaded profile: %s", path.name)
                    return profile

            log.info("No profile found for '%s' — using empty", site)
            return {}

        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Profile load error for '%s': %s", site, exc)
            return {}

    # ── Credential resolution ──

    def _resolve_credential(self, value: str) -> str:
        """
        Resolve ``{{ENV:VARIABLE_NAME}}`` to its environment value.

        Returns
        -------
        str
            Resolved value, or empty string if not found.
        """
        if not value or not isinstance(value, str):
            return ""

        match = _CREDENTIAL_RE.match(value.strip())
        if not match:
            return value

        env_var = match.group(1)
        resolved = os.environ.get(env_var, "")

        if not resolved:
            log.warning("Env var '%s' not found", env_var)

        return resolved

    # ── Report persistence ──

    def _save_report(self, site: str, data: dict) -> str:
        """
        Save report to ``data/reports/strategy_{site}_{date}.json``.

        Returns
        -------
        str
            The file path of the saved report.
        """
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)

            slug = _site_slug(site)
            filename = f"strategy_{slug}_{_today_str()}.json"
            filepath = REPORTS_DIR / filename

            # If file exists (multiple reports same day), add suffix
            counter = 1
            while filepath.exists():
                counter += 1
                filename = f"strategy_{slug}_{_today_str()}_{counter}.json"
                filepath = REPORTS_DIR / filename

            # Write atomically
            tmp_path = filepath.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps(data, indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp_path.replace(filepath)

            log.info("Report saved: %s", filepath)
            return str(filepath)

        except OSError as exc:
            log.critical("Cannot save report: %s", exc)
            return f"SAVE_FAILED: {exc}"

    # ── WhatsApp summary formatter ──

    def _format_telegram_summary(self, report: dict) -> str:
        """
        Format a human-readable WhatsApp summary of the weekly report.

        Parameters
        ----------
        report : dict
            The full weekly report.

        Returns
        -------
        str
            Plain-text summary suitable for WhatsApp.
        """
        site = report.get("site", "unknown")
        generated = report.get("generated_at", "?")

        lines: List[str] = [
            "📊 FALCON AGENCY — Weekly Strategy Report",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"🌐 Site: {site}",
            f"🕐 Generated: {generated}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        # ── Keyword summary ──
        kw = report.get("keyword_analysis", {})
        if not kw.get("error"):
            lines.append("")
            lines.append("🔑 KEYWORDS")
            lines.append(f"  Score: {kw.get('average_score', '?')}/5 average")
            lines.append(f"  Gaps: {kw.get('gap_count', '?')} keywords missing")
            lines.append(f"  Quick wins: {kw.get('opportunity_count', '?')}")

        # ── Performance summary ──
        traffic = report.get("traffic_analysis", {})
        if not traffic.get("error"):
            lines.append("")
            lines.append("⚡ PERFORMANCE")
            grade = traffic.get("performance_grade", "?")
            avg = traffic.get("average_ms", 0)
            trend = traffic.get("trend", {}).get("direction", "?")
            grade_emoji = {"A": "🟢", "B": "🟢", "C": "🟡", "D": "🟠", "F": "🔴"}.get(grade, "⚪")
            lines.append(f"  Grade: {grade_emoji} {grade}")
            lines.append(f"  Avg response: {avg:.0f}ms")
            lines.append(f"  Trend: {trend}")

        # ── Content summary ──
        content = report.get("content_analysis", {})
        if not content.get("error"):
            lines.append("")
            lines.append("📝 CONTENT")
            metrics = content.get("content_metrics", {})
            lines.append(f"  Words: {metrics.get('word_count', '?')}")
            lines.append(f"  Internal links: {metrics.get('internal_links', '?')}")
            lines.append(f"  Blog: {'✅' if metrics.get('has_blog_section') else '❌'}")
            lines.append(f"  Gaps: {content.get('gap_count', '?')}")

        # ── Sales summary ──
        sales = report.get("sales_analysis", {})
        if sales.get("api_accessible"):
            summary = sales.get("sales_summary", {})
            lines.append("")
            lines.append("💰 SALES (30 days)")
            lines.append(f"  Revenue: ₹{summary.get('total_revenue_inr', 0):.2f}")
            lines.append(f"  Orders: {summary.get('total_orders', 0)}")
            lines.append(f"  AOV: ₹{summary.get('average_order_value_inr', 0):.2f}")
        elif sales.get("status") == "skipped":
            lines.append("")
            lines.append("💰 SALES: ⚠️ API not configured")

        # ── Top recommendations ──
        recs = report.get("recommendations", [])
        if recs:
            lines.append("")
            lines.append("🎯 TOP RECOMMENDATIONS")
            for i, rec in enumerate(recs[:5], 1):
                impact_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    rec.get("impact", ""), "⚪"
                )
                lines.append(f"  {i}. {impact_emoji} {rec.get('title', '?')}")

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"Full report: {report.get('report_path', 'see data/reports/')}")

        return "\n".join(lines)

    # ── WhatsApp send ──

    def _send_telegram_summary(self, summary: str) -> None:
        """Send summary via WhatsApp. Never raises."""
        if self._approval is None:
            log.warning("Cannot send WhatsApp summary — ApprovalSystem unavailable")
            return
        try:
            self._approval.send_alert(summary)
            log.info("Strategy summary sent via WhatsApp")
        except Exception as exc:
            log.warning("WhatsApp summary send failed: %s", exc)

    # ── Result builder ──

    @staticmethod
    def _build_result(
        task: str,
        site: str,
        status: str,
        data: dict,
        error: Optional[str] = None,
    ) -> dict:
        """Build standardised result dict for the Director."""
        return {
            "status": status,
            "task": task,
            "site": site,
            "data": data,
            "error": error,
            "timestamp": _utcnow_iso(),
            "agent": "strategist",
        }

    # ── Repr ──

    def __repr__(self) -> str:
        return (
            f"<StrategistAgent  "
            f"reports_dir={REPORTS_DIR}  "
            f"approval={'✅' if self._approval else '❌'}>"
        )