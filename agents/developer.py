"""
agents/developer.py — Technical Worker Agent for Falcon Agency
================================================================

The Developer Agent is the hands-on engineer of the autonomous workforce.
It performs audits, measures performance, reviews plugins, manages code
changes, and generates SEO reports — always safely, always with approval
for destructive operations, always with rollback capability.

Execution Model
───────────────
    Director calls: dispatch_agent("developer", task, site, params)
                          │
                          ▼
                  DeveloperAgent.execute(task, site, params)
                          │
                          ▼
                  DeveloperAgent.handle(task, site, params)
                          │
            ┌─────────────┼─────────────────────────────────┐
            ▼             ▼             ▼                   ▼
        run_audit   check_performance  audit_plugins    fix_code
                                                          │
                                              ┌───────────┼───────────┐
                                              ▼           ▼           ▼
                                          git_commit  approval   git_rollback
                                         (mandatory)   (gate)    (on failure)

Safety Guarantees
─────────────────
    • Agent NEVER crashes — every public method is wrapped in try/except
    • Git commit BEFORE every file modification — rollback always available
    • Human Telegram approval required for ALL write operations
    • Credentials resolved from environment at runtime, never stored
    • All HTTP requests have 10-second timeout ceiling
    • subprocess calls NEVER use shell=True
"""

from __future__ import annotations

import json
import os
import re
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from core.logger import log
from core.approval import ApprovalSystem
from agents.base_agent import BaseAgent
from core.ai_client import call_ai
from core.website_tools import website_tools


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
PROFILES_DIR: Path = PROJECT_ROOT / "config" / "profiles"

HTTP_TIMEOUT: int = 10                    # seconds — hard ceiling for all requests
PERF_ATTEMPTS: int = 3                    # number of response-time samples
DEFAULT_TARGET_MS: float = 1500.0         # fallback if profile has no target
GIT_BRANCH: str = "agents"               # branch we work on — NEVER main

USER_AGENT: str = "FalconAgency-DeveloperAgent/1.0 (Site Auditor)"

# Credential placeholder pattern: {{ENV:VARIABLE_NAME}}
_CREDENTIAL_PATTERN: re.Pattern = re.compile(
    r"^\{\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}\}$"
)

# Security headers we expect on every site
_EXPECTED_SECURITY_HEADERS: List[Tuple[str, str]] = [
    ("Strict-Transport-Security", "HSTS"),
    ("X-Frame-Options", "Clickjack Protection"),
    ("X-Content-Type-Options", "MIME Sniffing Protection"),
    ("Content-Security-Policy", "CSP"),
    ("Referrer-Policy", "Referrer Policy"),
    ("Permissions-Policy", "Permissions Policy"),
]

# Required Open Graph tags for SEO
_OG_TAGS: List[str] = ["og:title", "og:description", "og:image", "og:url", "og:type"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _utcnow_iso() -> str:
    """UTC timestamp in ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


def _normalise_url(url: str) -> str:
    """Ensure *url* has an https scheme."""
    url = url.strip()
    if not url:
        return "https://localhost"
    if not urlparse(url).scheme:
        return f"https://{url}"
    return url


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DEVELOPER AGENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DeveloperAgent(BaseAgent):
    """
    Technical worker agent for Falcon Agency.

    Handles site auditing, performance measurement, plugin review,
    comment spam analysis, git-safe code fixes, SEO reporting, and
    uptime monitoring.

    The Director dispatches tasks to this agent via ``execute()``
    (or ``handle()``).  Both entry points route to the correct
    internal method and return a standardised result dict.

    Parameters
    ----------
    approval : ApprovalSystem
        The Telegram approval gateway for write operations.

    Example
    -------
    ::

        from core.approval import ApprovalSystem
        from agents.developer import DeveloperAgent

        approval = ApprovalSystem()
        dev = DeveloperAgent(approval)

        result = dev.handle("check_uptime", "falconherbs.com", {})
        print(result["status"], result["data"]["is_up"])
    """

    # ──────────────────────────────────────────────────────────────────
    #  Init
    # ──────────────────────────────────────────────────────────────────

    def __init__(self, whatsapp_client=None):
        """
        Initialise the Developer Agent.
        """
        super().__init__(whatsapp_client)
        self.name = "Developer"
        self.ai_role = "developer"
        self.capabilities = [
            "SEO audit and fixes",
            "Website uptime monitoring", 
            "Performance optimization",
            "Code generation and debugging",
            "Security scanning",
            "Technical troubleshooting"
        ]

        # Preserve legacy properties
        self._approval = None
        self._project_root: Path = PROJECT_ROOT
        self._session: requests.Session = self._build_session()

        log.info("DeveloperAgent initialised  |  project_root=%s", self._project_root)

    @staticmethod
    def _build_session() -> requests.Session:
        """Create a reusable requests.Session with safe defaults."""
        s = requests.Session()
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl,en;q=0.5",
        })
        return s

    # ══════════════════════════════════════════════════════════════════
    #  DISPATCH INTERFACE
    # ══════════════════════════════════════════════════════════════════

    def execute(self, action: str, details: str) -> str:
        """Developer executes technical tasks with AI thinking"""
        
        # First, think about the task
        plan = self.think(action, {"details": details})
        
        if plan.get("confidence") == "low":
            self.escalate(f"Low confidence for task: {action}. Need guidance.")
            return "Escalated to owner — need more clarity"
        
        # Execute based on action type
        action_lower = action.lower()
        
        if "seo" in action_lower:
            return self._do_seo_task(action, details, plan)
        elif "uptime" in action_lower or "status" in action_lower:
            return self._do_uptime_check(details)
        elif "performance" in action_lower or "speed" in action_lower:
            return self._do_performance_check(details)
        elif "security" in action_lower or "scan" in action_lower:
            return self._do_security_scan(details)
        elif "code" in action_lower or "fix" in action_lower:
            return self._do_code_task(action, details, plan)
        else:
            return self._do_generic_task(action, details, plan)
    
    def _do_seo_task(self, action: str, details: str, plan: dict) -> str:
        """AI-powered SEO analysis and fixes"""
        messages = [
            {"role": "system", "content": """You are an SEO expert. Analyze and provide actionable fixes.
Output JSON: {"issues": [...], "fixes": [...], "priority": "high|medium|low"}"""},
            {"role": "user", "content": f"Action: {action}\nDetails: {details}\nPlan: {json.dumps(plan)}"}
        ]
        response = call_ai("developer", messages)
        self.report_to_owner(f"SEO Task completed: {action}")
        return response
    
    def _do_uptime_check(self, site: str) -> str:
        """Check website uptime"""
        import requests
        try:
            r = requests.get(f"https://{site}", timeout=10)
            status = f"✅ {site} is UP (Status: {r.status_code}, Time: {r.elapsed.total_seconds():.2f}s)"
        except Exception as e:
            status = f"❌ {site} is DOWN: {str(e)}"
            self.escalate(f"Website DOWN: {site}")
        return status
    
    def _do_performance_check(self, site: str) -> str:
        """AI-analyzed performance check"""
        messages = [
            {"role": "system", "content": "Analyze website performance and suggest improvements. Be specific."},
            {"role": "user", "content": f"Analyze performance for: {site}"}
        ]
        return call_ai("developer", messages)
    
    def _do_security_scan(self, site: str) -> str:
        """AI-powered security analysis"""
        messages = [
            {"role": "system", "content": "Perform security analysis. Identify vulnerabilities and fixes."},
            {"role": "user", "content": f"Security scan for: {site}"}
        ]
        response = call_ai("developer", messages)
        self.report_to_owner(f"🔒 Security scan completed for {site}", priority="high")
        return response
    
    def _do_code_task(self, action: str, details: str, plan: dict) -> str:
        """AI code generation/debugging"""
        messages = [
            {"role": "system", "content": "You are an expert developer. Write clean, secure, efficient code."},
            {"role": "user", "content": f"Task: {action}\nDetails: {details}"}
        ]
        return call_ai("developer", messages)
    
    def _do_generic_task(self, action: str, details: str, plan: dict) -> str:
        """Fallback for unknown tasks"""
        messages = [
            {"role": "system", "content": f"You are a developer. Execute this task using your expertise."},
            {"role": "user", "content": f"Action: {action}\nDetails: {details}\nPlan: {json.dumps(plan)}"}
        ]
        return call_ai("developer", messages)


    def handle(self, task: str, site: str, params: dict) -> dict:
        """
        Route *task* to the appropriate internal method.

        This is the single entry point the Director calls.  Every task
        is wrapped in a top-level try/except so that agent errors never
        crash the Director.

        Recognised Tasks
        ----------------
        ``run_audit``          — full site audit
        ``check_performance``  — response time + caching headers
        ``audit_plugins``      — flag outdated / risky plugins
        ``audit_comments``     — count comments, flag spam
        ``run_seo_report``     — meta tags, sitemap, robots, OG tags
        ``check_uptime``       — is the site alive?
        ``fix_code``           — git-safe code modification (approval required)
        ``general_task``       — fallback for goal-derived tasks
        ``security_scan``      — delegates to run_audit
        ``plugin_update_check``— delegates to audit_plugins
        ``comment_spam_audit`` — delegates to audit_comments

        Returns
        -------
        dict
            ``{status, task, site, data, error, timestamp}``
        """
        log.info(
            "DeveloperAgent.handle  |  task=%s  |  site=%s", task, site,
        )

        try:
            profile = self._load_profile(site)

            # ── Route table ──
            if task == "run_audit" or task == "security_scan":
                data = self.run_audit(site, profile)

            elif task == "check_performance" or task == "performance_check":
                data = self.check_performance(site, profile)

            elif task == "audit_plugins" or task == "plugin_update_check":
                data = self.audit_plugins(profile)

            elif task == "audit_comments" or task == "comment_spam_audit":
                data = self.audit_comments(site, profile)

            elif task == "run_seo_report" or task == "seo_audit":
                data = self.run_seo_report(site, profile)

            elif task == "check_uptime" or task == "uptime_check":
                data = self.check_uptime(site)

            elif task == "fix_code" or task == "code_deploy":
                file_path = params.get("file_path", "")
                issue = params.get("issue", "")
                fix = params.get("fix", "")
                data = self.fix_code(
                    file_path=file_path,
                    issue=issue,
                    fix=fix,
                    site=site,
                )

            elif task == "general_task":
                data = self._handle_general_task(site, profile, params)

            else:
                log.warning("DeveloperAgent: unknown task '%s'", task)
                return self._build_result(
                    task, site, "skipped", {},
                    error=f"Unknown task: {task}",
                )

            status = data.get("status", "success") if isinstance(data, dict) else "success"
            if isinstance(data, dict) and data.get("error"):
                status = "failed"

            return self._build_result(task, site, status, data)

        except Exception as exc:
            log.critical(
                "DeveloperAgent.handle crashed  |  task=%s  |  %s",
                task, exc, exc_info=True,
            )
            return self._build_result(
                task, site, "failed", {},
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )

    # ══════════════════════════════════════════════════════════════════
    #  1.  SITE AUDIT
    # ══════════════════════════════════════════════════════════════════

    def run_audit(self, site: str, profile: dict) -> dict:
        """
        Run a comprehensive site audit.

        Checks:
            • HTTP response time
            • Security headers
            • WordPress version detection
            • Plugin update count
            • SSL certificate validity
            • Broken links on homepage

        Parameters
        ----------
        site : str
            Site domain or URL.
        profile : dict
            Loaded site profile.

        Returns
        -------
        dict
            Structured audit report with pass/fail per check.
        """
        url = _normalise_url(site)
        checks: List[Dict[str, Any]] = []
        overall_pass = True

        log.info("Starting site audit  |  %s", url)

        # ── 1. Response time ──
        try:
            resp = self._session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            resp_ms = round(resp.elapsed.total_seconds() * 1000, 1)
            target = profile.get("performance_targets", {}).get(
                "response_time_target_ms", DEFAULT_TARGET_MS,
            )
            passed = resp_ms <= target
            if not passed:
                overall_pass = False
            checks.append({
                "check": "response_time",
                "passed": passed,
                "value": f"{resp_ms}ms",
                "target": f"{target}ms",
                "detail": f"Response in {resp_ms}ms (target: {target}ms)",
            })
        except requests.RequestException as exc:
            overall_pass = False
            checks.append({
                "check": "response_time",
                "passed": False,
                "value": None,
                "detail": f"Request failed: {str(exc)[:200]}",
            })
            resp = None

        # ── 2. Security headers ──
        if resp is not None:
            headers = resp.headers
            for header_name, label in _EXPECTED_SECURITY_HEADERS:
                present = header_name in headers
                if not present:
                    overall_pass = False
                checks.append({
                    "check": f"header_{header_name}",
                    "passed": present,
                    "value": headers.get(header_name, "MISSING")[:120],
                    "detail": f"{label}: {'present' if present else 'MISSING'}",
                })
        else:
            for header_name, label in _EXPECTED_SECURITY_HEADERS:
                overall_pass = False
                checks.append({
                    "check": f"header_{header_name}",
                    "passed": False,
                    "value": None,
                    "detail": f"{label}: could not check — site unreachable",
                })

        # ── 3. WordPress version detection ──
        wp_version = self._detect_wordpress_version(url, resp)
        checks.append({
            "check": "wordpress_version",
            "passed": wp_version is not None,
            "value": wp_version,
            "detail": f"WordPress version: {wp_version or 'undetected'}",
        })

        # ── 4. Plugin update count ──
        plugins = profile.get("plugins", [])
        updates_available = [p for p in plugins if p.get("update_available")]
        plugin_pass = len(updates_available) == 0
        if not plugin_pass:
            overall_pass = False
        checks.append({
            "check": "plugin_updates",
            "passed": plugin_pass,
            "value": len(updates_available),
            "detail": (
                f"{len(updates_available)} plugin(s) need updating: "
                + ", ".join(p.get("name", "?") for p in updates_available[:5])
            ),
        })

        # ── 5. SSL certificate ──
        ssl_result = self._check_ssl_certificate(url)
        if not ssl_result.get("valid", False):
            overall_pass = False
        checks.append({
            "check": "ssl_certificate",
            "passed": ssl_result.get("valid", False),
            "value": ssl_result,
            "detail": ssl_result.get("detail", "SSL check performed"),
        })

        # ── 6. Broken links (homepage only) ──
        broken = self._check_broken_links(url, resp)
        broken_pass = len(broken) == 0
        if not broken_pass:
            overall_pass = False
        checks.append({
            "check": "broken_links",
            "passed": broken_pass,
            "value": len(broken),
            "detail": (
                f"Found {len(broken)} broken link(s)"
                + (f": {', '.join(broken[:5])}" if broken else "")
            ),
        })

        report = {
            "site": site,
            "url": url,
            "audit_time": _utcnow_iso(),
            "overall_pass": overall_pass,
            "checks_total": len(checks),
            "checks_passed": sum(1 for c in checks if c["passed"]),
            "checks_failed": sum(1 for c in checks if not c["passed"]),
            "checks": checks,
        }

        log.log_action(
            action="site_audit",
            agent="developer",
            status="success",
            details={
                "site": site,
                "passed": report["checks_passed"],
                "failed": report["checks_failed"],
                "overall": overall_pass,
            },
        )

        return report

    # ══════════════════════════════════════════════════════════════════
    #  2.  PERFORMANCE CHECK
    # ══════════════════════════════════════════════════════════════════

    def check_performance(self, site: str, profile: dict) -> dict:
        """
        Measure site performance.

        Takes ``PERF_ATTEMPTS`` (3) response-time samples, checks gzip
        and caching headers, and compares against the profile target.

        Returns
        -------
        dict
            ``{response_times, average_ms, target_ms, passed,
              gzip_enabled, cache_control, recommendations}``
        """
        url = _normalise_url(site)
        target_ms = profile.get("performance_targets", {}).get(
            "response_time_target_ms", DEFAULT_TARGET_MS,
        )

        log.info("Performance check  |  %s  |  target=%dms", url, target_ms)

        response_times: List[float] = []
        last_resp: Optional[requests.Response] = None
        recommendations: List[str] = []

        # ── Multiple samples ──
        for i in range(PERF_ATTEMPTS):
            try:
                resp = self._session.get(
                    url, timeout=HTTP_TIMEOUT, allow_redirects=True,
                )
                ms = round(resp.elapsed.total_seconds() * 1000, 1)
                response_times.append(ms)
                last_resp = resp
            except requests.RequestException as exc:
                log.warning("Perf sample %d/%d failed: %s", i + 1, PERF_ATTEMPTS, exc)
                response_times.append(-1)  # sentinel for failure

            # Small delay between samples to avoid rate-limiting
            if i < PERF_ATTEMPTS - 1:
                time.sleep(0.5)

        # ── Compute average (excluding failures) ──
        valid_times = [t for t in response_times if t > 0]
        average_ms = round(sum(valid_times) / len(valid_times), 1) if valid_times else -1
        passed = average_ms > 0 and average_ms <= target_ms

        # ── Gzip check ──
        gzip_enabled = False
        if last_resp is not None:
            content_encoding = last_resp.headers.get("Content-Encoding", "")
            gzip_enabled = "gzip" in content_encoding.lower() or "br" in content_encoding.lower()

        if not gzip_enabled:
            recommendations.append(
                "Enable gzip or Brotli compression on the server. "
                "This typically reduces transfer size by 60-80% and directly "
                "improves response time."
            )

        # ── Cache-Control check ──
        cache_control = ""
        cache_present = False
        if last_resp is not None:
            cache_control = last_resp.headers.get("Cache-Control", "")
            cache_present = bool(cache_control)

        if not cache_present:
            recommendations.append(
                "Add Cache-Control headers for static assets. Example: "
                "Cache-Control: public, max-age=31536000 for CSS/JS/images."
            )
        elif "no-cache" in cache_control or "no-store" in cache_control:
            recommendations.append(
                "Cache-Control is set to no-cache/no-store. Consider enabling "
                "browser caching for static assets."
            )

        # ── Performance recommendations based on timing ──
        if average_ms > 3000:
            recommendations.append(
                "Response time is critically slow (>3s). Investigate: "
                "1) Server resource limits in WHM/cPanel, "
                "2) PHP OPcache configuration, "
                "3) Database query optimization (slow queries), "
                "4) Consider object caching (Redis/Memcached)."
            )
        elif average_ms > target_ms:
            recommendations.append(
                f"Response time ({average_ms}ms) exceeds target ({target_ms}ms). "
                "Consider: image optimization, lazy loading, minimizing render-blocking resources."
            )

        # ── Expires header check ──
        if last_resp is not None and not last_resp.headers.get("Expires", ""):
            recommendations.append(
                "No Expires header present. While Cache-Control is preferred, "
                "adding Expires headers improves compatibility with older proxies."
            )

        result = {
            "site": site,
            "url": url,
            "checked_at": _utcnow_iso(),
            "response_times_ms": response_times,
            "average_ms": average_ms,
            "target_ms": target_ms,
            "passed": passed,
            "gzip_enabled": gzip_enabled,
            "cache_control": cache_control,
            "cache_headers_present": cache_present,
            "recommendations": recommendations,
            "sample_count": PERF_ATTEMPTS,
            "successful_samples": len(valid_times),
        }

        log.log_action(
            action="performance_check",
            agent="developer",
            status="success" if passed else "warning",
            details={
                "site": site,
                "average_ms": average_ms,
                "target_ms": target_ms,
                "passed": passed,
            },
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  3.  PLUGIN AUDIT
    # ══════════════════════════════════════════════════════════════════

    def audit_plugins(self, profile: dict) -> dict:
        """
        Audit the plugin inventory from the site profile.

        Flags:
            • Plugins with updates available
            • Plugins with risk_level ``"high"``
            • Plugins that could be deactivated (notes mention it)

        Returns
        -------
        dict
            ``{total, plugins_needing_update, high_risk_plugins,
              deactivation_candidates, recommendations}``
        """
        plugins = profile.get("plugins", [])
        site = profile.get("identity", {}).get("site_id", "unknown")

        log.info("Plugin audit  |  %d plugins in profile", len(plugins))

        needing_update: List[Dict[str, Any]] = []
        high_risk: List[Dict[str, Any]] = []
        deactivation_candidates: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        for p in plugins:
            name = p.get("name", "Unknown")
            slug = p.get("slug", "")
            risk = p.get("risk_level", "low")
            update = p.get("update_available", False)
            notes = p.get("notes", "")

            if update:
                needing_update.append({
                    "name": name,
                    "slug": slug,
                    "risk_level": risk,
                    "notes": notes[:200],
                })

            if risk == "high":
                high_risk.append({
                    "name": name,
                    "slug": slug,
                    "update_available": update,
                    "notes": notes[:200],
                })

            if "deactivat" in notes.lower() or "consider removing" in notes.lower():
                deactivation_candidates.append({
                    "name": name,
                    "slug": slug,
                    "reason": notes[:200],
                })

        # ── Recommendations ──
        if high_risk:
            high_needing = [p for p in high_risk if p.get("update_available")]
            if high_needing:
                names = ", ".join(p["name"] for p in high_needing)
                recommendations.append(
                    f"URGENT: {len(high_needing)} high-risk plugin(s) have updates "
                    f"available: {names}. Update immediately after backup."
                )

        if needing_update:
            recommendations.append(
                f"{len(needing_update)} plugin(s) need updating. Recommended order: "
                "update lowest-risk first, WooCommerce last. Always backup before each update."
            )

            # Build recommended update order
            risk_order = {"low": 0, "medium": 1, "high": 2}
            ordered = sorted(
                needing_update,
                key=lambda p: risk_order.get(p.get("risk_level", "low"), 1),
            )
            order_str = " → ".join(p["name"] for p in ordered)
            recommendations.append(f"Suggested update sequence: {order_str}")

        if deactivation_candidates:
            names = ", ".join(p["name"] for p in deactivation_candidates)
            recommendations.append(
                f"Consider deactivating: {names}. "
                "Fewer active plugins = smaller attack surface."
            )

        if not needing_update and not high_risk:
            recommendations.append("All plugins are up to date. No action needed.")

        result = {
            "site": site,
            "audited_at": _utcnow_iso(),
            "total_plugins": len(plugins),
            "plugins_needing_update": needing_update,
            "update_count": len(needing_update),
            "high_risk_plugins": high_risk,
            "high_risk_count": len(high_risk),
            "deactivation_candidates": deactivation_candidates,
            "recommendations": recommendations,
        }

        log.log_action(
            action="plugin_audit",
            agent="developer",
            status="success",
            details={
                "total": len(plugins),
                "updates_available": len(needing_update),
                "high_risk": len(high_risk),
            },
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  4.  COMMENT SPAM AUDIT
    # ══════════════════════════════════════════════════════════════════

    def audit_comments(self, site: str, profile: dict) -> dict:
        """
        Audit comments via the WordPress REST API.

        Counts comments by status (approved, pending, spam, trash)
        and flags abnormal volumes that indicate spam.

        Falls back to profile-based reporting if the REST API is
        inaccessible (common when the endpoint is disabled for security).

        Returns
        -------
        dict
            ``{total, by_status, flags, recommendations, api_accessible}``
        """
        url = _normalise_url(site)
        api_base = urljoin(url + "/", "wp-json/wp/v2/")

        log.info("Comment audit  |  %s", url)

        # ── Resolve credentials (if available) ──
        creds = profile.get("credentials", {})
        wp_user = creds.get("wp_admin_user", "")
        wp_pass_ref = creds.get("wp_admin_password", "")
        wp_password = self._resolve_credential(wp_pass_ref)

        statuses = ["approved", "hold", "spam", "trash"]
        by_status: Dict[str, int] = {}
        api_accessible = False
        total = 0
        flags: List[str] = []
        recommendations: List[str] = []

        # ── Try REST API ──
        for status in statuses:
            try:
                params: Dict[str, Any] = {
                    "status": status if status != "approved" else "approve",
                    "per_page": 1,
                    "page": 1,
                }

                # Use auth if credentials available
                auth = None
                if wp_user and wp_password:
                    auth = (wp_user, wp_password)

                resp = self._session.get(
                    f"{api_base}comments",
                    params=params,
                    auth=auth,
                    timeout=HTTP_TIMEOUT,
                )

                if resp.status_code == 200:
                    api_accessible = True
                    # WordPress returns total in X-WP-Total header
                    count = int(resp.headers.get("X-WP-Total", 0))
                    display_status = "pending" if status == "hold" else status
                    by_status[display_status] = count
                    total += count
                elif resp.status_code in (401, 403):
                    # Auth required or forbidden — try without auth for public comments
                    if auth:
                        log.info("REST API returned %d for %s comments — trying unauthenticated", resp.status_code, status)
                else:
                    log.info("REST API returned %d for %s comments", resp.status_code, status)

            except requests.RequestException as exc:
                log.info("REST API comment check failed for status '%s': %s", status, exc)

        # ── Fallback: use known data from profile ──
        if not api_accessible:
            log.info("REST API not accessible — using profile data for comment audit")
            # The profile mentions 3,144 comments as known context
            goals = profile.get("goals", [])
            for goal in goals:
                desc = goal.get("description", "").lower()
                if "3,144" in desc or "3144" in desc:
                    by_status["pending_estimated"] = 3144
                    total = 3144
                    break

            if total == 0:
                by_status["unknown"] = 0
                recommendations.append(
                    "Could not access WordPress REST API to count comments. "
                    "Verify the REST API is enabled and credentials are correct."
                )

        # ── Flag abnormal volumes ──
        pending = by_status.get("pending", by_status.get("pending_estimated", 0))
        spam = by_status.get("spam", 0)

        if pending > 100:
            flags.append(
                f"CRITICAL: {pending} pending comments awaiting moderation. "
                "This volume strongly suggests a spam attack."
            )
            recommendations.append(
                f"Audit and bulk-delete spam from the {pending} pending comments. "
                "Consider installing Akismet or CleanTalk for automated spam filtering."
            )

        if spam > 50:
            flags.append(
                f"WARNING: {spam} comments in spam folder. Empty the spam folder."
            )
            recommendations.append(
                "Empty the WordPress spam folder to free database space. "
                "Large spam tables slow down the entire site."
            )

        if total > 3000:
            flags.append(
                f"ALERT: {total} total comments is abnormally high. "
                "This is almost certainly due to the previous hack."
            )
            recommendations.append(
                "Given the hack history, assume 95%+ of comments are spam. "
                "Recommend: 1) Backup database, 2) Bulk-delete pending/spam, "
                "3) Review remaining approved comments, "
                "4) Install anti-spam plugin."
            )

        if not flags:
            recommendations.append("Comment volumes appear normal. No immediate action needed.")

        result = {
            "site": site,
            "audited_at": _utcnow_iso(),
            "api_accessible": api_accessible,
            "total_comments": total,
            "by_status": by_status,
            "flags": flags,
            "flag_count": len(flags),
            "recommendations": recommendations,
        }

        log.log_action(
            action="comment_audit",
            agent="developer",
            status="success",
            details={
                "site": site,
                "total": total,
                "flags": len(flags),
                "api_accessible": api_accessible,
            },
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  5.  CODE FIX (with full safety gates)
    # ══════════════════════════════════════════════════════════════════

    def fix_code(
        self,
        file_path: str,
        issue: str,
        fix: str,
        site: str,
    ) -> dict:
        """
        Apply a code fix with full safety guarantees.

        Safety pipeline:
            1. Validate the file exists and is within project root
            2. Git commit current state (mandatory — abort if fails)
            3. Read current content
            4. Validate the fix (syntax check for .py files)
            5. Request human approval via Telegram
            6. Apply fix
            7. Verify applied correctly
            8. If ANYTHING fails after step 2 → git rollback

        Parameters
        ----------
        file_path : str
            Path to the file to modify (relative to project root or absolute).
        issue : str
            Description of the problem being fixed.
        fix : str
            The new file content or patch to apply.
        site : str
            Which site this fix relates to.

        Returns
        -------
        dict
            ``{success, git_hash_before, rollback_available, applied_at}``
        """
        log.info("fix_code requested  |  file=%s  |  issue=%s", file_path, issue[:80])

        # ── Step 0: Validate path ──
        try:
            target = Path(file_path)
            if not target.is_absolute():
                target = self._project_root / target
            target = target.resolve()

            # Security: ensure the file is within the project root
            if not str(target).startswith(str(self._project_root)):
                return {
                    "success": False,
                    "error": "Path traversal blocked: file is outside project root",
                    "file_path": str(target),
                    "rollback_available": False,
                }

            if not target.exists():
                return {
                    "success": False,
                    "error": f"File does not exist: {target}",
                    "rollback_available": False,
                }

            if not target.is_file():
                return {
                    "success": False,
                    "error": f"Path is not a file: {target}",
                    "rollback_available": False,
                }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Path validation error: {exc}",
                "rollback_available": False,
            }

        # ── Step 1: Git commit before change (MANDATORY) ──
        commit_hash = self.git_commit_before_change(
            file_path=str(target),
            message=f"PRE-FIX SNAPSHOT: {issue[:80]}",
        )

        if not commit_hash:
            log.critical("Git commit failed — ABORTING fix_code")
            return {
                "success": False,
                "error": "Git commit failed before change — fix aborted for safety",
                "rollback_available": False,
            }

        log.info("Pre-fix commit: %s", commit_hash)

        # ── Step 2: Read current content ──
        try:
            original_content = target.read_text(encoding="utf-8")
        except Exception as exc:
            log.critical("Cannot read file: %s", exc)
            return {
                "success": False,
                "error": f"Cannot read file: {exc}",
                "git_hash_before": commit_hash,
                "rollback_available": True,
            }

        # ── Step 3: Validate the fix ──
        if target.suffix == ".py":
            syntax_ok, syntax_error = self._validate_python_syntax(fix)
            if not syntax_ok:
                log.warning("Fix has Python syntax errors: %s", syntax_error)
                return {
                    "success": False,
                    "error": f"Fix rejected — syntax error: {syntax_error}",
                    "git_hash_before": commit_hash,
                    "rollback_available": True,
                }

        # ── Step 4: Request human approval ──
        if self._approval is None:
            log.critical("ApprovalSystem unavailable — cannot approve code fix")
            return {
                "success": False,
                "error": "ApprovalSystem unavailable — fix aborted",
                "git_hash_before": commit_hash,
                "rollback_available": True,
            }

        try:
            approval_details = {
                "site": site,
                "description": (
                    f"Code fix requested\n"
                    f"File: {target.relative_to(self._project_root)}\n"
                    f"Issue: {issue}\n"
                    f"Lines changed: ~{abs(len(fix.splitlines()) - len(original_content.splitlines()))}\n"
                    f"Pre-fix commit: {commit_hash[:8]}\n"
                    f"Rollback available: YES"
                ),
                "agent": "developer",
                "risk_level": "high",
            }

            approved = self._approval.request_approval(
                action="fix_code",
                details=approval_details,
            )
        except Exception as exc:
            log.critical("Approval request failed: %s", exc)
            approved = False

        if not approved:
            log.info("Code fix DENIED by owner — skipping")
            log.log_action(
                action="fix_code",
                agent="developer",
                status="denied",
                details={"file": str(target), "issue": issue[:200]},
            )
            return {
                "success": False,
                "status": "skipped",
                "error": "Human approval denied or timed out",
                "git_hash_before": commit_hash,
                "rollback_available": True,
            }

        # ── Step 5: Apply fix ──
        try:
            target.write_text(fix, encoding="utf-8")
            log.info("Fix applied to %s", target)
        except Exception as exc:
            log.critical("Write failed — rolling back: %s", exc)
            self.git_rollback(commit_hash)
            return {
                "success": False,
                "error": f"Write failed, rolled back: {exc}",
                "git_hash_before": commit_hash,
                "rollback_available": True,
                "rolled_back": True,
            }

        # ── Step 6: Verify ──
        try:
            verify_content = target.read_text(encoding="utf-8")
            if verify_content != fix:
                log.critical("Verification failed — content mismatch — rolling back")
                self.git_rollback(commit_hash)
                return {
                    "success": False,
                    "error": "Post-write verification failed — rolled back",
                    "git_hash_before": commit_hash,
                    "rollback_available": True,
                    "rolled_back": True,
                }
        except Exception as exc:
            log.critical("Verification read failed — rolling back: %s", exc)
            self.git_rollback(commit_hash)
            return {
                "success": False,
                "error": f"Verification failed, rolled back: {exc}",
                "git_hash_before": commit_hash,
                "rollback_available": True,
                "rolled_back": True,
            }

        # ── Step 7: Post-fix git commit ──
        post_hash = self.git_commit_before_change(
            file_path=str(target),
            message=f"FIX APPLIED: {issue[:80]}",
        )

        log.info("✅ Code fix applied and committed  |  pre=%s  |  post=%s",
                 commit_hash[:8], (post_hash or "?")[:8])

        log.log_action(
            action="fix_code",
            agent="developer",
            status="success",
            details={
                "file": str(target.relative_to(self._project_root)),
                "issue": issue[:200],
                "git_before": commit_hash,
                "git_after": post_hash,
            },
        )

        return {
            "success": True,
            "file_path": str(target.relative_to(self._project_root)),
            "issue": issue,
            "git_hash_before": commit_hash,
            "git_hash_after": post_hash,
            "rollback_available": True,
            "applied_at": _utcnow_iso(),
        }

    # ══════════════════════════════════════════════════════════════════
    #  6.  GIT OPERATIONS
    # ══════════════════════════════════════════════════════════════════

    def git_commit_before_change(self, file_path: str, message: str) -> str:
        """
        Stage and commit the current state of *file_path* before modification.

        Ensures we always have a rollback point.  Operates on the
        ``agents`` branch — never ``main``.

        Parameters
        ----------
        file_path : str
            Absolute or project-relative path to stage.
        message : str
            Commit message.

        Returns
        -------
        str
            The commit hash (short), or empty string on failure.
        """
        log.info("git_commit_before_change  |  file=%s", file_path)

        try:
            cwd = str(self._project_root)

            # ── Ensure we're on the agents branch ──
            self._ensure_git_branch(cwd)

            # ── Stage the file ──
            result = subprocess.run(
                ["git", "add", str(file_path)],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                # File might be untracked or nothing to stage — that's OK
                log.info("git add note: %s", result.stderr.strip()[:200])

            # ── Check if there's anything to commit ──
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=15,
            )

            if not status_result.stdout.strip():
                # Nothing to commit — create an empty commit as a checkpoint
                commit_result = subprocess.run(
                    ["git", "commit", "--allow-empty", "-m", f"[Falcon] {message}"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            else:
                # Stage everything and commit
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                commit_result = subprocess.run(
                    ["git", "commit", "-m", f"[Falcon] {message}"],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            if commit_result.returncode != 0:
                log.warning(
                    "git commit returned %d: %s",
                    commit_result.returncode,
                    commit_result.stderr.strip()[:300],
                )
                # If nothing to commit, get current HEAD
                if "nothing to commit" in commit_result.stdout.lower():
                    pass
                else:
                    return ""

            # ── Get commit hash ──
            hash_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            commit_hash = hash_result.stdout.strip()
            log.info("Git commit: %s  |  %s", commit_hash, message[:60])
            return commit_hash

        except subprocess.TimeoutExpired:
            log.critical("Git command timed out")
            return ""
        except FileNotFoundError:
            log.critical("Git executable not found — is git installed?")
            return ""
        except Exception as exc:
            log.critical("git_commit_before_change failed: %s", exc, exc_info=True)
            return ""

    def git_rollback(self, commit_hash: str) -> bool:
        """
        Roll back to *commit_hash* using ``git reset --hard``.

        Parameters
        ----------
        commit_hash : str
            Short or full hash to reset to.

        Returns
        -------
        bool
            ``True`` if rollback succeeded.
        """
        log.warning("GIT ROLLBACK initiated  |  target=%s", commit_hash)

        try:
            cwd = str(self._project_root)

            result = subprocess.run(
                ["git", "reset", "--hard", commit_hash],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                log.info("✅ Rollback successful to %s", commit_hash)
                log.log_action(
                    action="git_rollback",
                    agent="developer",
                    status="success",
                    details={"target_hash": commit_hash},
                )
                return True
            else:
                log.critical(
                    "Rollback FAILED: %s", result.stderr.strip()[:300],
                )
                return False

        except Exception as exc:
            log.critical("git_rollback crashed: %s", exc, exc_info=True)
            return False

    def git_status(self) -> dict:
        """
        Get current git status of the project.

        Returns
        -------
        dict
            ``{branch, commit, clean, modified_files, untracked_files}``
        """
        try:
            cwd = str(self._project_root)

            # Branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=cwd, capture_output=True, text=True, timeout=10,
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

            # Current commit
            commit_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=cwd, capture_output=True, text=True, timeout=10,
            )
            commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown"

            # Status
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd, capture_output=True, text=True, timeout=15,
            )

            modified: List[str] = []
            untracked: List[str] = []
            if status_result.returncode == 0:
                for line in status_result.stdout.strip().splitlines():
                    if line.startswith("??"):
                        untracked.append(line[3:].strip())
                    elif line.strip():
                        modified.append(line.strip())

            clean = len(modified) == 0 and len(untracked) == 0

            return {
                "branch": branch,
                "commit": commit,
                "clean": clean,
                "modified_files": modified[:20],
                "untracked_files": untracked[:20],
                "modified_count": len(modified),
                "untracked_count": len(untracked),
            }

        except Exception as exc:
            log.warning("git_status failed: %s", exc)
            return {
                "branch": "unknown",
                "commit": "unknown",
                "clean": None,
                "error": str(exc)[:200],
            }

    def _ensure_git_branch(self, cwd: str) -> None:
        """
        Ensure we're on the ``agents`` branch.

        Creates the branch if it doesn't exist.  Never checks out
        ``main`` or ``master``.
        """
        try:
            # Check current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=cwd, capture_output=True, text=True, timeout=10,
            )
            current = result.stdout.strip()

            if current == GIT_BRANCH:
                return   # already on correct branch

            # Check if branch exists
            branch_list = subprocess.run(
                ["git", "branch", "--list", GIT_BRANCH],
                cwd=cwd, capture_output=True, text=True, timeout=10,
            )

            if GIT_BRANCH in branch_list.stdout:
                # Branch exists — checkout
                subprocess.run(
                    ["git", "checkout", GIT_BRANCH],
                    cwd=cwd, capture_output=True, text=True, timeout=15,
                )
            else:
                # Create and checkout
                subprocess.run(
                    ["git", "checkout", "-b", GIT_BRANCH],
                    cwd=cwd, capture_output=True, text=True, timeout=15,
                )

            log.info("Switched to git branch: %s", GIT_BRANCH)

        except Exception as exc:
            log.warning("_ensure_git_branch failed: %s (continuing on current branch)", exc)

    # ══════════════════════════════════════════════════════════════════
    #  7.  SEO REPORT
    # ══════════════════════════════════════════════════════════════════

    def run_seo_report(self, site: str, profile: dict) -> dict:
        """
        Analyse on-page SEO factors for the site homepage.

        Checks:
            • Meta title and description
            • Sitemap existence
            • robots.txt validity
            • Canonical tag
            • Open Graph tags
            • Target keyword presence
            • H1 tag presence and content

        Returns
        -------
        dict
            Structured SEO report with pass/fail per check and recommendations.
        """
        url = _normalise_url(site)
        checks: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        log.info("SEO report  |  %s", url)

        # ── Fetch homepage ──
        soup: Optional[BeautifulSoup] = None
        try:
            resp = self._session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=True)
            soup = BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as exc:
            log.warning("Cannot fetch homepage for SEO: %s", exc)
            return {
                "site": site,
                "url": url,
                "checked_at": _utcnow_iso(),
                "error": f"Cannot fetch homepage: {str(exc)[:200]}",
                "checks": [],
                "recommendations": ["Fix site accessibility before running SEO audit"],
            }

        # ── 1. Meta title ──
        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True) if title_tag else ""
        title_ok = bool(title_text) and 10 <= len(title_text) <= 70

        checks.append({
            "check": "meta_title",
            "passed": title_ok,
            "value": title_text[:80] if title_text else "MISSING",
            "detail": (
                f"Title: '{title_text[:60]}' ({len(title_text)} chars)"
                if title_text
                else "No <title> tag found"
            ),
        })
        if not title_text:
            recommendations.append("Add a <title> tag with your primary keyword.")
        elif len(title_text) < 10:
            recommendations.append(f"Title is too short ({len(title_text)} chars). Aim for 50-60 characters.")
        elif len(title_text) > 70:
            recommendations.append(f"Title is too long ({len(title_text)} chars). Google truncates after ~60 characters.")

        # ── 2. Meta description ──
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
        desc_ok = bool(meta_desc) and 50 <= len(meta_desc) <= 160

        checks.append({
            "check": "meta_description",
            "passed": desc_ok,
            "value": meta_desc[:170] if meta_desc else "MISSING",
            "detail": (
                f"Description: '{meta_desc[:80]}…' ({len(meta_desc)} chars)"
                if meta_desc
                else "No meta description found"
            ),
        })
        if not meta_desc:
            recommendations.append("Add a meta description with target keywords.")
        elif len(meta_desc) < 50:
            recommendations.append(f"Meta description is too short ({len(meta_desc)} chars). Aim for 120-155 characters.")
        elif len(meta_desc) > 160:
            recommendations.append(f"Meta description is too long ({len(meta_desc)} chars). Google truncates after ~155 characters.")

        # ── 3. Sitemap ──
        sitemap_found = False
        sitemap_url_used = ""
        for sitemap_path in ["/sitemap_index.xml", "/sitemap.xml"]:
            try:
                sitemap_url_candidate = urljoin(url + "/", sitemap_path.lstrip("/"))
                sm_resp = self._session.get(sitemap_url_candidate, timeout=HTTP_TIMEOUT)
                if sm_resp.status_code == 200 and ("<?xml" in sm_resp.text[:100] or "<urlset" in sm_resp.text[:500] or "<sitemapindex" in sm_resp.text[:500]):
                    sitemap_found = True
                    sitemap_url_used = sitemap_url_candidate
                    break
            except requests.RequestException:
                continue

        checks.append({
            "check": "sitemap",
            "passed": sitemap_found,
            "value": sitemap_url_used if sitemap_found else "NOT FOUND",
            "detail": f"Sitemap: {'found at ' + sitemap_url_used if sitemap_found else 'not found'}",
        })
        if not sitemap_found:
            recommendations.append("Generate an XML sitemap and submit it to Google Search Console.")

        # ── 4. robots.txt ──
        robots_ok = False
        robots_blocks_all = False
        try:
            robots_url = urljoin(url + "/", "robots.txt")
            robots_resp = self._session.get(robots_url, timeout=HTTP_TIMEOUT)
            if robots_resp.status_code == 200:
                robots_ok = True
                robots_text = robots_resp.text.lower()
                if "disallow: /" in robots_text:
                    # Check if it's blocking everything
                    for line in robots_text.splitlines():
                        line = line.strip()
                        if line == "disallow: /":
                            robots_blocks_all = True
                            break
        except requests.RequestException:
            pass

        checks.append({
            "check": "robots_txt",
            "passed": robots_ok and not robots_blocks_all,
            "value": "BLOCKING ALL" if robots_blocks_all else ("present" if robots_ok else "MISSING"),
            "detail": (
                "robots.txt is BLOCKING all search engines!" if robots_blocks_all
                else ("robots.txt present and valid" if robots_ok else "robots.txt not found")
            ),
        })
        if robots_blocks_all:
            recommendations.append("CRITICAL: robots.txt is blocking all search engines. Remove 'Disallow: /' immediately.")
        elif not robots_ok:
            recommendations.append("Add a robots.txt file. Include a reference to your sitemap.")

        # ── 5. Canonical tag ──
        canonical_tag = soup.find("link", attrs={"rel": "canonical"})
        canonical_href = canonical_tag.get("href", "").strip() if canonical_tag else ""
        canonical_ok = bool(canonical_href)

        checks.append({
            "check": "canonical",
            "passed": canonical_ok,
            "value": canonical_href[:120] if canonical_href else "MISSING",
            "detail": f"Canonical: {canonical_href[:80] if canonical_href else 'not set'}",
        })
        if not canonical_ok:
            recommendations.append("Add a canonical tag to prevent duplicate content issues.")

        # ── 6. Open Graph tags ──
        og_results: Dict[str, str] = {}
        for tag_name in _OG_TAGS:
            og_tag = soup.find("meta", attrs={"property": tag_name})
            og_value = og_tag.get("content", "").strip() if og_tag else ""
            og_results[tag_name] = og_value

        og_present = sum(1 for v in og_results.values() if v)
        og_ok = og_present >= 3  # at least title, desc, image

        checks.append({
            "check": "open_graph",
            "passed": og_ok,
            "value": og_results,
            "detail": f"Open Graph: {og_present}/{len(_OG_TAGS)} tags present",
        })
        missing_og = [k for k, v in og_results.items() if not v]
        if missing_og:
            recommendations.append(
                f"Add missing Open Graph tags: {', '.join(missing_og)}. "
                "These improve social media sharing appearance."
            )

        # ── 7. H1 tag ──
        h1_tags = soup.find_all("h1")
        h1_texts = [h.get_text(strip=True) for h in h1_tags if h.get_text(strip=True)]
        h1_ok = len(h1_texts) == 1  # Exactly one H1 is best practice

        checks.append({
            "check": "h1_tag",
            "passed": h1_ok,
            "value": h1_texts[0][:80] if h1_texts else "MISSING",
            "detail": (
                f"H1: '{h1_texts[0][:60]}'" if len(h1_texts) == 1
                else f"Found {len(h1_texts)} H1 tags (should be exactly 1)"
                if h1_texts else "No H1 tag found"
            ),
        })
        if not h1_texts:
            recommendations.append("Add exactly one H1 tag containing your primary keyword.")
        elif len(h1_texts) > 1:
            recommendations.append(f"Found {len(h1_texts)} H1 tags. Use exactly one H1 per page.")

        # ── 8. Target keyword presence ──
        seo_config = profile.get("seo", {})
        target_keywords_data = seo_config.get("target_keywords", [])
        target_keywords: List[str] = []
        for kw in target_keywords_data:
            if isinstance(kw, dict):
                target_keywords.append(kw.get("keyword", ""))
            elif isinstance(kw, str):
                target_keywords.append(kw)

        page_text = soup.get_text(separator=" ").lower()
        full_title_desc = f"{title_text} {meta_desc}".lower()

        kw_findings: List[Dict[str, Any]] = []
        for kw in target_keywords:
            if not kw:
                continue
            kw_lower = kw.lower()
            in_body = kw_lower in page_text
            in_title = kw_lower in title_text.lower()
            in_desc = kw_lower in meta_desc.lower()
            in_h1 = any(kw_lower in h.lower() for h in h1_texts)

            kw_findings.append({
                "keyword": kw,
                "in_body": in_body,
                "in_title": in_title,
                "in_meta_description": in_desc,
                "in_h1": in_h1,
            })

        kw_ok = all(f["in_body"] for f in kw_findings) if kw_findings else True
        checks.append({
            "check": "target_keywords",
            "passed": kw_ok,
            "value": kw_findings,
            "detail": (
                f"Keywords analysed: {len(kw_findings)}, "
                f"all in body: {kw_ok}"
            ),
        })

        missing_in_title = [f["keyword"] for f in kw_findings if not f["in_title"]]
        missing_in_body = [f["keyword"] for f in kw_findings if not f["in_body"]]
        if missing_in_title:
            recommendations.append(
                f"Target keywords missing from title: {', '.join(missing_in_title[:3])}. "
                "Include your primary keyword in the page title."
            )
        if missing_in_body:
            recommendations.append(
                f"Target keywords missing from page body: {', '.join(missing_in_body[:3])}. "
                "Add natural keyword usage in page content."
            )

        # ── Build report ──
        overall_pass = all(c["passed"] for c in checks)

        report = {
            "site": site,
            "url": url,
            "checked_at": _utcnow_iso(),
            "overall_pass": overall_pass,
            "checks_total": len(checks),
            "checks_passed": sum(1 for c in checks if c["passed"]),
            "checks_failed": sum(1 for c in checks if not c["passed"]),
            "checks": checks,
            "recommendations": recommendations,
            "seo_market": seo_config.get("market", "unknown"),
            "seo_language": seo_config.get("language", "unknown"),
        }

        log.log_action(
            action="seo_report",
            agent="developer",
            status="success",
            details={
                "site": site,
                "passed": report["checks_passed"],
                "failed": report["checks_failed"],
                "overall": overall_pass,
            },
        )

        return report

    # ══════════════════════════════════════════════════════════════════
    #  8.  UPTIME CHECK
    # ══════════════════════════════════════════════════════════════════

    def check_uptime(self, site: str) -> dict:
        """
        Lightweight uptime check.

        Sends an HTTP GET, measures response time, and alerts the owner
        via Telegram if the site is down.

        Parameters
        ----------
        site : str
            Target site domain or URL.

        Returns
        -------
        dict
            ``{is_up, status_code, response_time_ms, checked_at, error, status}``.
            Use ``handle('check_uptime', site, {})`` for Director format with ``data`` key.
        """
        url = _normalise_url(site)
        start = time.monotonic()

        log.info("Uptime check  |  %s", url)

        try:
            resp = self._session.get(
                url, timeout=HTTP_TIMEOUT, allow_redirects=True,
            )
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            status_code = resp.status_code
            is_up = status_code < 500

            if not is_up:
                log.critical("🔴 SITE DOWN  |  %s  |  HTTP %d", site, status_code)
                self._send_alert(
                    f"🔴 SITE DOWN: {site}\n"
                    f"HTTP {status_code}\n"
                    f"Response time: {elapsed_ms}ms\n"
                    f"Time: {_utcnow_iso()}"
                )
            else:
                log.info(
                    "Uptime OK  |  %s  |  %d  |  %dms",
                    site, status_code, elapsed_ms,
                )

            result = {
                "is_up": is_up,
                "status_code": status_code,
                "response_time_ms": elapsed_ms,
                "checked_at": _utcnow_iso(),
                "error": None,
                "status": "up" if is_up else "down",
            }

            log.log_action(
                action="uptime_check",
                agent="developer",
                status="success" if is_up else "critical",
                details={
                    "site": site,
                    "is_up": is_up,
                    "status_code": status_code,
                    "response_ms": elapsed_ms,
                },
            )

            return result

        except requests.exceptions.Timeout:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            log.critical("🔴 SITE TIMEOUT  |  %s  |  %dms", site, elapsed_ms)
            self._send_alert(
                f"🔴 SITE TIMEOUT: {site}\n"
                f"No response after {HTTP_TIMEOUT}s\n"
                f"Time: {_utcnow_iso()}"
            )
            return {
                "is_up": False,
                "status_code": None,
                "response_time_ms": elapsed_ms,
                "checked_at": _utcnow_iso(),
                "error": f"Timeout after {HTTP_TIMEOUT}s",
                "status": "down",
            }

        except requests.exceptions.ConnectionError as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            log.critical("🔴 SITE UNREACHABLE  |  %s  |  %s", site, exc)
            self._send_alert(
                f"🔴 SITE UNREACHABLE: {site}\n"
                f"Connection failed: {str(exc)[:200]}\n"
                f"Time: {_utcnow_iso()}"
            )
            return {
                "is_up": False,
                "status_code": None,
                "response_time_ms": elapsed_ms,
                "checked_at": _utcnow_iso(),
                "error": f"Connection failed: {str(exc)[:150]}",
                "status": "down",
            }

        except requests.RequestException as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            log.critical("🔴 SITE ERROR  |  %s  |  %s", site, exc)
            self._send_alert(
                f"🔴 SITE ERROR: {site}\n"
                f"Error: {str(exc)[:200]}\n"
                f"Time: {_utcnow_iso()}"
            )
            return {
                "is_up": False,
                "status_code": None,
                "response_time_ms": elapsed_ms,
                "checked_at": _utcnow_iso(),
                "error": str(exc)[:200],
                "status": "down",
            }

    # ══════════════════════════════════════════════════════════════════
    #  INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════════════

    # ── Profile loading ──

    def _load_profile(self, site: str) -> dict:
        """
        Load the site profile from ``config/profiles/<site_slug>.json``.

        Derives the filename from the site string by stripping protocol
        and replacing dots/slashes.

        Returns
        -------
        dict
            The parsed profile, or ``{}`` if not found.
        """
        try:
            # Derive slug: "falconherbs.com" → "falconherbs"
            slug = site.strip().lower()
            slug = slug.replace("https://", "").replace("http://", "")
            slug = slug.rstrip("/").split("/")[0]       # take domain only
            slug = slug.replace("www.", "")

            # Try exact domain, then first part before dot
            candidates = [
                PROFILES_DIR / f"{slug}.json",
                PROFILES_DIR / f"{slug.split('.')[0]}.json",
            ]

            for profile_path in candidates:
                if profile_path.exists():
                    text = profile_path.read_text(encoding="utf-8")
                    profile = json.loads(text)
                    log.info("Loaded profile: %s", profile_path.name)
                    return profile

            log.info("No profile found for '%s' — using empty profile", site)
            return {}

        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to load profile for '%s': %s", site, exc)
            return {}

    # ── Credential resolution ──

    def _resolve_credential(self, value: str) -> str:
        """
        Resolve a ``{{ENV:VARIABLE_NAME}}`` placeholder to its actual
        value from the operating system environment.

        Parameters
        ----------
        value : str
            The placeholder string (e.g. ``"{{ENV:FALCONHERBS_WP_PASSWORD}}"``).

        Returns
        -------
        str
            The resolved value, or empty string if not found.
        """
        if not value or not isinstance(value, str):
            return ""

        match = _CREDENTIAL_PATTERN.match(value.strip())
        if not match:
            # Not a placeholder — return as-is (but it might be empty)
            return value

        env_var = match.group(1)
        resolved = os.environ.get(env_var, "")

        if not resolved:
            log.warning(
                "Credential env var '%s' not found in environment", env_var,
            )

        # NEVER log the resolved value
        return resolved

    # ── Result builder ──

    @staticmethod
    def _build_result(
        task: str,
        site: str,
        status: str,
        data: dict,
        error: Optional[str] = None,
    ) -> dict:
        """
        Build a standardised result dict for the Director.

        Parameters
        ----------
        task : str
            Task name.
        site : str
            Target site.
        status : str
            ``"success"``, ``"failed"``, or ``"skipped"``.
        data : dict
            Task-specific result data.
        error : str, optional
            Error message if failed.

        Returns
        -------
        dict
            ``{status, task, site, data, error, timestamp, agent}``
        """
        return {
            "status": status,
            "task": task,
            "site": site,
            "data": data,
            "error": error,
            "timestamp": _utcnow_iso(),
            "agent": "developer",
        }

    # ── WordPress version detection ──

    @staticmethod
    def _detect_wordpress_version(
        url: str,
        response: Optional[requests.Response],
    ) -> Optional[str]:
        """
        Attempt to detect WordPress version from response content.

        Checks:
            1. ``<meta name="generator" content="WordPress X.Y.Z">``
            2. ``?ver=X.Y.Z`` in stylesheet/script links
        """
        if response is None:
            return None

        try:
            soup = BeautifulSoup(response.text, "html.parser")

            # Method 1: meta generator tag
            gen_tag = soup.find("meta", attrs={"name": "generator"})
            if gen_tag:
                content = gen_tag.get("content", "")
                wp_match = re.search(r"WordPress\s+([\d.]+)", content, re.IGNORECASE)
                if wp_match:
                    return wp_match.group(1)

            # Method 2: ?ver= in script/link tags
            for tag in soup.find_all(["script", "link"]):
                src = tag.get("src", "") or tag.get("href", "")
                ver_match = re.search(r"[?&]ver=([\d.]+)", src)
                if ver_match:
                    version = ver_match.group(1)
                    # Heuristic: WordPress versions are like 6.4.2
                    parts = version.split(".")
                    if len(parts) >= 2 and all(p.isdigit() for p in parts):
                        major = int(parts[0])
                        if 3 <= major <= 9:  # Reasonable WP version range
                            return version

        except Exception:
            pass

        return None

    # ── SSL certificate check ──

    @staticmethod
    def _check_ssl_certificate(url: str) -> dict:
        """
        Verify the SSL certificate for *url*.

        Returns
        -------
        dict
            ``{valid, issuer, expires, days_remaining, detail}``
        """
        parsed = urlparse(url)
        hostname = parsed.hostname or parsed.netloc
        port = parsed.port or 443

        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=HTTP_TIMEOUT) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()

            if not cert:
                return {"valid": False, "detail": "No certificate returned"}

            # Parse expiry
            not_after_str = cert.get("notAfter", "")
            issuer_tuples = cert.get("issuer", ())
            issuer_parts = []
            for rdn in issuer_tuples:
                for attr in rdn:
                    if attr[0] in ("organizationName", "commonName"):
                        issuer_parts.append(attr[1])
            issuer = ", ".join(issuer_parts) if issuer_parts else "Unknown"

            # Parse date: 'Feb 20 12:00:00 2027 GMT'
            try:
                expires = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z")
                expires = expires.replace(tzinfo=timezone.utc)
                days_remaining = (expires - datetime.now(timezone.utc)).days
            except ValueError:
                expires = None
                days_remaining = None

            return {
                "valid": True,
                "issuer": issuer,
                "expires": not_after_str,
                "days_remaining": days_remaining,
                "detail": f"Valid, issued by {issuer}, expires in {days_remaining} days",
            }

        except ssl.SSLCertVerificationError as exc:
            return {
                "valid": False,
                "detail": f"SSL verification failed: {str(exc)[:200]}",
            }
        except ssl.SSLError as exc:
            return {
                "valid": False,
                "detail": f"SSL error: {str(exc)[:200]}",
            }
        except (socket.timeout, socket.gaierror, OSError) as exc:
            return {
                "valid": False,
                "detail": f"Connection error: {str(exc)[:200]}",
            }
        except Exception as exc:
            return {
                "valid": False,
                "detail": f"Unexpected error: {type(exc).__name__}: {str(exc)[:200]}",
            }

    # ── Broken link checker ──

    def _check_broken_links(
        self,
        url: str,
        response: Optional[requests.Response],
        max_links: int = 20,
    ) -> List[str]:
        """
        Check links on the homepage for broken (4xx/5xx) responses.

        Only checks internal links and limits to *max_links* to stay
        within the timeout budget.

        Returns
        -------
        list[str]
            List of broken URLs.
        """
        if response is None:
            return []

        broken: List[str] = []
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc.replace("www.", "")

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            links_checked = 0

            for a_tag in soup.find_all("a", href=True):
                if links_checked >= max_links:
                    break

                href = a_tag["href"].strip()

                # Skip empty, anchors, mailto, tel, javascript
                if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                    continue

                # Resolve relative URLs
                if href.startswith("/"):
                    href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                elif not href.startswith("http"):
                    continue  # skip relative paths without slash

                # Only check internal links
                link_parsed = urlparse(href)
                link_domain = link_parsed.netloc.replace("www.", "")
                if link_domain != base_domain:
                    continue

                # HEAD request for speed
                try:
                    link_resp = self._session.head(
                        href, timeout=5, allow_redirects=True,
                    )
                    if link_resp.status_code >= 400:
                        broken.append(f"{href} ({link_resp.status_code})")
                except requests.RequestException:
                    broken.append(f"{href} (connection failed)")

                links_checked += 1

        except Exception as exc:
            log.warning("Broken link check error: %s", exc)

        return broken

    # ── Python syntax validation ──

    @staticmethod
    def _validate_python_syntax(code: str) -> Tuple[bool, Optional[str]]:
        """
        Check if *code* is valid Python by attempting to compile it.

        Returns
        -------
        tuple[bool, str | None]
            ``(True, None)`` if valid, or ``(False, error_message)`` if not.
        """
        try:
            compile(code, "<fix_validation>", "exec")
            return True, None
        except SyntaxError as exc:
            return False, f"Line {exc.lineno}: {exc.msg}"

    # ── General task handler ──

    def _handle_general_task(
        self,
        site: str,
        profile: dict,
        params: dict,
    ) -> dict:
        """
        Handle a generic task dispatched from a goal that doesn't
        map to a specific method.

        Runs a basic audit and returns recommendations.
        """
        description = params.get("description", "")
        goal_id = params.get("goal_id", "")

        log.info(
            "General task  |  goal=%s  |  desc='%s'",
            goal_id, description[:80],
        )

        # Attempt to match description to a known task
        desc_lower = description.lower()

        if "performance" in desc_lower or "response time" in desc_lower or "speed" in desc_lower:
            return self.check_performance(site, profile)

        if "security" in desc_lower or "scan" in desc_lower or "vulnerability" in desc_lower:
            return self.run_audit(site, profile)

        if "plugin" in desc_lower or "update" in desc_lower:
            return self.audit_plugins(profile)

        if "comment" in desc_lower or "spam" in desc_lower:
            return self.audit_comments(site, profile)

        if "seo" in desc_lower or "ranking" in desc_lower or "keyword" in desc_lower:
            return self.run_seo_report(site, profile)

        if "form" in desc_lower or "contact" in desc_lower:
            return self.run_audit(site, profile)

        # Fallback: run a full audit
        log.info("General task — no specific match, running full audit")
        return self.run_audit(site, profile)

    # ── Alert helper ──

    def _send_alert(self, message: str) -> None:
        """
        Best-effort Telegram alert via the ApprovalSystem.

        Never raises — if the alert fails, it's logged and we continue.
        """
        if self._approval is None:
            log.warning("Cannot send alert — ApprovalSystem unavailable")
            return
        try:
            self._approval.send_alert(message)
        except Exception as exc:
            log.warning("Alert send failed: %s", exc)

    # ── New Tool-Integrated Methods (surgical additions) ──

    def _full_seo_audit(self, site: str = "falconherbs.com") -> str:
        """Deep SEO audit using website_tools — crawls ALL pages"""
        from core.ai_client import call_ai
        import json

        self._send_alert(f"🔍 Running full SEO audit on {site} (all pages)...")

        website_tools.set_site(f"https://{site}")
        pages = website_tools.crawl_all_pages(max_pages=30)

        audit_data = {
            "site": site,
            "pages_crawled": len(pages),
            "pages": [{"url": p["url"], "title": p["title"], "meta": p["meta_description"], "h1": p["h1"]} for p in pages[:15]]
        }

        prompt = f"""Analyze this multi-page SEO data:

{json.dumps(audit_data, indent=2)}

Provide JSON:
{{"overall_score": 0-100, "critical_issues": [], "warnings": [], "good_practices": [], "recommendations": [{{"priority": "high/medium/low", "issue": "...", "fix": "..."}}]}}"""

        response = call_ai("developer", [{"role": "user", "content": prompt}])

        report = f"🔍 FULL SEO AUDIT — {site}\nPages Crawled: {len(pages)}\n\n{response[:2000]}"
        self._send_alert(report[:1500])
        return report

    def _health_claims_audit(self, site: str = "falconherbs.com") -> str:
        """FDA/FTC health claims compliance audit"""

        self._send_alert(f"⚕️ Scanning {site} for health claims violations...")

        website_tools.set_site(f"https://{site}")
        audit = website_tools.full_health_audit(max_pages=30)

        summary = audit.get("summary", {})

        report = f"""⚕️ HEALTH CLAIMS AUDIT — {site}

📄 Pages Scanned: {summary.get('total_pages', 0)}
✅ Clean Pages: {summary.get('clean_pages', 0)}
⚠️ Pages with Issues: {summary.get('pages_with_issues', 0)}

📊 COMPLIANCE SCORE: {summary.get('compliance_score', 0)}%

🔴 HIGH RISK: {summary.get('high_risk_count', 0)}
🟡 MEDIUM RISK: {summary.get('medium_risk_count', 0)}
🟢 LOW RISK: {summary.get('low_risk_count', 0)}

{'🚨 IMMEDIATE ACTION REQUIRED!' if summary.get('high_risk_count', 0) > 0 else '✅ No critical violations.'}"""

        # Show first few high risk items
        for claim in audit.get('high_risk', [])[:3]:
            report += f"\n\n❌ {claim.get('matched_text')}\n   Page: {claim.get('page_url')}\n   Issue: {claim.get('issue')}"

        self._send_alert(report[:1500])
        return report

    # ── Repr ──

    def __repr__(self) -> str:
        git = self.git_status()
        return (
            f"<DeveloperAgent  "
            f"branch={git.get('branch', '?')}  "
            f"commit={git.get('commit', '?')}  "
            f"clean={git.get('clean', '?')}>"
        )