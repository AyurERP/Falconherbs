"""
core/sentinel.py — 24/7 Security Watchdog for Falcon Agency
=============================================================

The Sentinel exists because the owner was hacked before.
Its single job: make sure that never happens again.

What it watches:
    ┌────────────────────────────────────────────────────────┐
    │  LAYER 1 — Transport & Headers (scan_vulnerabilities)  │
    │  LAYER 2 — Authentication Logs (monitor_failed_logins) │
    │  LAYER 3 — Filesystem Tamper   (check_file_integrity)  │
    │  LAYER 4 — Active Response     (block_ip)              │
    │  LAYER 5 — Continuous Loop     (start_monitoring)      │
    └────────────────────────────────────────────────────────┘

Every layer assumes the layer above it has already been breached.
Defence in depth — there is no single point of failure.

Operational guarantees:
    • Sentinel NEVER crashes the host process. Every public method
      is wrapped in a top-level try/except that logs and returns a
      safe default.
    • Sentinel usually takes only non-destructive actions. IP blocks require
      manual execution. However, specific security headers (HSTS, CSP) are 
      automatically patched via cPanel if missing, as approved by the owner.
    • Every finding, every scan, every decision is recorded via
      log.log_action() into SQLite for post-incident forensics.

Dependencies:
    requests   — HTTP probing
    hashlib    — SHA-256 file fingerprinting
    schedule   — Cron-like interval loop
    (all stdlib otherwise)
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import socket
import ssl
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
import schedule

from config.settings import settings
from core.approval import ApprovalSystem
from core.logger import log
from core.cpanel_connector import cpanel


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONSTANTS & CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── HTTP probing ──
_HTTP_TIMEOUT: int = 25                    # seconds; SSL handshake from VPS can be slow
_SLOW_RESPONSE_THRESHOLD: float = 3.0      # seconds; triggers MEDIUM alert
_USER_AGENT: str = "FalconAgency-Sentinel/2.0 (Internal Security Scanner)"
_SSL_EXPIRY_THRESHOLD_DAYS: int = 15        # triggers HIGH alert

# ── File integrity ──
_HASH_CHUNK_SIZE: int = 65_536             # 64 KiB read blocks
_MAX_FILE_BYTES: int = 100 * 1024 * 1024   # 100 MiB ceiling

_SKIP_EXTENSIONS: FrozenSet[str] = frozenset({
    # Compiled / binary
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".o", ".a",
    # Images / media
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg", ".webp",
    ".mp4", ".mp3", ".wav", ".avi", ".mov", ".flv",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z",
    # Data / runtime
    ".db", ".sqlite", ".sqlite3", ".log", ".tmp", ".cache", ".pid",
})

# ── Security headers we check ──
# Each tuple: (header_name, acceptable_values_substring_match, severity_if_missing, recommendation)
_REQUIRED_HEADERS: List[Tuple[str, List[str], str, str, str]] = [
    (
        "Strict-Transport-Security",
        ["max-age="],
        "HIGH",
        "Missing HSTS — browsers can be downgraded to plain HTTP via MITM.",
        "Add: Strict-Transport-Security: max-age=63072000; includeSubDomains; preload",
    ),
    (
        "Content-Security-Policy",
        ["default-src", "script-src"],
        "HIGH",
        "Missing CSP — site is wide open to XSS and injection attacks.",
        "Start with: Content-Security-Policy: default-src 'self'; script-src 'self'",
    ),
    (
        "X-Frame-Options",
        ["DENY", "SAMEORIGIN"],
        "MEDIUM",
        "Missing X-Frame-Options — site can be embedded in malicious iframes (clickjacking).",
        "Add: X-Frame-Options: DENY",
    ),
    (
        "X-Content-Type-Options",
        ["nosniff"],
        "MEDIUM",
        "Missing X-Content-Type-Options — browser may MIME-sniff responses into executable types.",
        "Add: X-Content-Type-Options: nosniff",
    ),
    (
        "Referrer-Policy",
        ["no-referrer", "strict-origin", "same-origin", "origin"],
        "LOW",
        "Missing Referrer-Policy — full URL paths may leak to third-party sites.",
        "Add: Referrer-Policy: strict-origin-when-cross-origin",
    ),
    (
        "Permissions-Policy",
        [],  # any value is better than missing
        "LOW",
        "Missing Permissions-Policy — browser features (camera, mic, geolocation) are unrestricted.",
        "Add: Permissions-Policy: camera=(), microphone=(), geolocation=()",
    ),
    (
        "X-XSS-Protection",
        ["1"],
        "LOW",
        "Missing X-XSS-Protection — legacy browsers lose built-in XSS filter.",
        "Add: X-XSS-Protection: 1; mode=block",
    ),
]

# ── Failed login regex patterns ──
# Each pattern MUST expose a named group (?P<ip>...) for the attacker IP.
# We cast a wide net because log formats vary wildly across stacks.
_FAILED_LOGIN_PATTERNS: List[re.Pattern] = [
    # sshd / PAM
    re.compile(
        r"Failed (?:password|publickey) for\s+\S+\s+from\s+(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
        re.IGNORECASE,
    ),
    # WordPress wp-login.php POST → 200 but "login failed"
    re.compile(
        r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3}).*POST.*/wp-login\.php.*(?:200)",
        re.IGNORECASE,
    ),
    # Generic "failed" or "invalid" + IP anywhere on the line
    re.compile(
        r"(?:failed|invalid|unauthorized|denied|rejected).*?(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
        re.IGNORECASE,
    ),
    # IP-first lines with 401 / 403 status
    re.compile(
        r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3}).*\s(?:401|403)\s",
    ),
    # Reverse order — IP after the failure message
    re.compile(
        r"(?:authentication failure|login failure|auth error).*?(?P<ip>\d{1,3}(?:\.\d{1,3}){3})",
        re.IGNORECASE,
    ),
]

# ── Severity ordering (for comparisons) ──
_SEVERITY_RANK: Dict[str, int] = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPER: safe timestamp for display
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _utcnow() -> str:
    """ISO-ish UTC timestamp string for reports and alerts."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _severity_gte(a: str, b: str) -> bool:
    """Return True if severity *a* >= severity *b*."""
    return _SEVERITY_RANK.get(a, 0) >= _SEVERITY_RANK.get(b, 0)


def _max_severity(findings: List[Dict[str, Any]]) -> str:
    """Return the highest severity string from a list of finding dicts."""
    highest = "INFO"
    for f in findings:
        sev = f.get("severity", "INFO")
        if _SEVERITY_RANK.get(sev, 0) > _SEVERITY_RANK.get(highest, 0):
            highest = sev
    return highest


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SENTINEL CLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Sentinel:
    """
    24/7 Security Watchdog for Falcon Agency.

    Instantiate with an ``ApprovalSystem`` so Sentinel can push alerts
    to the owner's WhatsApp.  Then call ``start_monitoring(url)`` to
    begin the continuous scan loop, or invoke individual checks ad-hoc.

    Example::

        from core.approval import ApprovalSystem
        from core.sentinel import Sentinel

        approval  = ApprovalSystem()
        sentinel  = Sentinel(approval)

        # One-time full scan
        report = sentinel.run_scan("https://falconherbs.com")

        # Continuous background guard
        sentinel.start_monitoring("https://falconherbs.com")
    """

    # ──────────────────────────────────────────────────────────────────
    #  Construction
    # ──────────────────────────────────────────────────────────────────

    def __init__(self, approval_system: ApprovalSystem) -> None:
        self._approval: ApprovalSystem = approval_system
        self._last_unreachable_scan_alert: Dict[str, float] = {}  # site -> monotonic; cooldown 30 min

        # Runtime state
        self._blocked_ips: Set[str] = set()            # IPs we've already alerted about
        self._monitoring_active: bool = False           # flag for the loop thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_lock: threading.Lock = threading.Lock()  # serialise start/stop

        # Load tunable knobs from settings (with sane fallbacks)
        self._scan_interval_min: int = int(
            getattr(settings, "scan_interval_minutes", 15)
        )
        self._max_failed_logins: int = int(
            getattr(settings, "max_failed_logins_before_block", 5)
        )
        self._blocked_ip_ttl_h: int = int(
            getattr(settings, "blocked_ip_ttl_hours", 24)
        )

        log.info(
            "Sentinel initialised  |  scan_interval=%dm  |  "
            "max_failed_logins=%d  |  blocked_ip_ttl=%dh",
            self._scan_interval_min,
            self._max_failed_logins,
            self._blocked_ip_ttl_h,
        )

    # ══════════════════════════════════════════════════════════════════
    #  1.  scan_vulnerabilities
    # ══════════════════════════════════════════════════════════════════

    def scan_vulnerabilities(self, site_url: str) -> Dict[str, Any]:
        """
        Probe *site_url* for transport-layer and HTTP-header weaknesses.

        Checks performed (in order):
            1. URL scheme — is the site served over HTTPS?
            2. SSL/TLS certificate — does it validate?
            3. Response time — does it exceed 3 seconds?
            4. HTTP status — is the server healthy?
            5. Security headers — see ``_REQUIRED_HEADERS``.
            6. Information leakage — Server / X-Powered-By.

        Returns
        -------
        dict
            {
                "site_url": str,
                "scan_time": str,
                "reachable": bool,
                "response_time_s": float | None,
                "status_code": int | None,
                "findings": [  {category, title, severity, description, recommendation, raw} , … ],
                "highest_severity": str,
                "error": str | None,
            }
        """
        scan_start = time.monotonic()
        findings: List[Dict[str, Any]] = []

        log.info("Vulnerability scan starting  |  site=%s", site_url)

        try:
            # ── Normalise URL ──
            site_url = self._normalise_url(site_url)
            parsed = urlparse(site_url)

            # ── CHECK 1: HTTPS ──
            if parsed.scheme != "https":
                findings.append(self._finding(
                    category="transport",
                    title="HTTPS Not Enforced",
                    severity="CRITICAL",
                    description=(
                        f"Site is served over {parsed.scheme.upper()}. "
                        "All traffic — including credentials and session cookies — "
                        "is transmitted in cleartext."
                    ),
                    recommendation="Obtain a TLS certificate (Let's Encrypt is free) and redirect all HTTP → HTTPS.",
                    raw=parsed.scheme,
                ))

            # ── HTTP request ──
            response: Optional[requests.Response] = None
            response_time: Optional[float] = None
            status_code: Optional[int] = None

            try:
                response = requests.get(
                    site_url,
                    timeout=_HTTP_TIMEOUT,
                    headers={"User-Agent": _USER_AGENT},
                    allow_redirects=True,
                    verify=True,
                )
                response_time = response.elapsed.total_seconds()
                status_code = response.status_code

            except requests.exceptions.SSLError as exc:
                # ── CHECK 2: SSL certificate failure ──
                findings.append(self._finding(
                    category="ssl",
                    title="SSL/TLS Certificate Invalid",
                    severity="CRITICAL",
                    description=(
                        f"Certificate validation failed: {self._truncate(str(exc), 300)}. "
                        "Browsers will show a security warning; attackers can MITM the connection."
                    ),
                    recommendation="Renew or replace the SSL certificate immediately. Check expiry and domain match.",
                    raw=self._truncate(str(exc), 500),
                ))
                # Retry without verification so we can still inspect headers
                try:
                    response = requests.get(
                        site_url,
                        timeout=_HTTP_TIMEOUT,
                        headers={"User-Agent": _USER_AGENT},
                        allow_redirects=True,
                        verify=False,
                    )
                    response_time = response.elapsed.total_seconds()
                    status_code = response.status_code
                except requests.RequestException:
                    pass  # truly dead

            except requests.exceptions.ConnectionError as exc:
                return self._unreachable_report(
                    site_url, scan_start, findings,
                    error=f"Connection refused or DNS failure: {self._truncate(str(exc), 200)}",
                )

            except requests.exceptions.Timeout:
                return self._unreachable_report(
                    site_url, scan_start, findings,
                    error=f"Request timed out after {_HTTP_TIMEOUT}s",
                )

            except requests.RequestException as exc:
                return self._unreachable_report(
                    site_url, scan_start, findings,
                    error=f"Request error: {self._truncate(str(exc), 200)}",
                )

            if response is None:
                return self._unreachable_report(
                    site_url, scan_start, findings,
                    error="No HTTP response obtained after all retries",
                )

            # ── CHECK 2.5: SSL Certificate Expiry (Self-Healing awareness) ──
            if site_url.startswith("https://"):
                try:
                    hostname = urlparse(site_url).hostname
                    if hostname:
                        context = ssl.create_default_context()
                        with socket.create_connection((hostname, 443), timeout=10) as sock:
                            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                                cert = ssock.getpeercert()
                                if cert:
                                    not_after = cert.get('notAfter')
                                    if not_after:
                                        expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                                        days_left = (expiry - datetime.utcnow()).days
                                        if days_left < _SSL_EXPIRY_THRESHOLD_DAYS:
                                            findings.append(self._finding(
                                                category="transport",
                                                title="SSL Certificate Expiring Soon",
                                                severity="HIGH" if days_left < 7 else "MEDIUM",
                                                description=f"SSL certificate for {hostname} expires in {days_left} days. Your site will soon show scary security warnings to customers.",
                                                recommendation="Login to cPanel/WHM and verify Auto-SSL is running, or renew certificate manually.",
                                                raw=f"Expires: {not_after} ({days_left} days left)",
                                            ))
                                            log.warning("🔒 SSL EXPIRING  |  host=%s  |  days_left=%d", hostname, days_left)
                except Exception as ssl_err:
                    log.warning("Failed to probe SSL expiry for %s: %s", site_url, ssl_err)

            # ── CHECK 3: Response time ──
            if response_time is not None and response_time > _SLOW_RESPONSE_THRESHOLD:
                findings.append(self._finding(
                    category="performance",
                    title="Abnormally Slow Response",
                    severity="MEDIUM",
                    description=(
                        f"Server took {response_time:.2f}s to respond "
                        f"(threshold: {_SLOW_RESPONSE_THRESHOLD}s). "
                        "This could indicate resource exhaustion, a DDoS attack in progress, "
                        "or a crypto-miner consuming CPU."
                    ),
                    recommendation="Investigate server load, check for runaway processes, review recent deployments.",
                    raw=f"{response_time:.3f}s",
                ))

            # ── CHECK 4: HTTP status ──
            if status_code is not None:
                if status_code >= 500:
                    findings.append(self._finding(
                        category="availability",
                        title=f"Server Error (HTTP {status_code})",
                        severity="HIGH",
                        description=f"Server returned {status_code}. The site may be down or misconfigured.",
                        recommendation="Check application logs, database connectivity, and disk space.",
                        raw=str(status_code),
                    ))
                elif status_code in (403, 401):
                    findings.append(self._finding(
                        category="availability",
                        title=f"Access Denied (HTTP {status_code})",
                        severity="MEDIUM",
                        description=f"Server returned {status_code}. The scanner may be blocked, or the site requires auth.",
                        recommendation="Verify URL, check .htaccess / firewall rules, whitelist scanner IP if needed.",
                        raw=str(status_code),
                    ))

            # ── CHECK 5: Security headers ──
            hdrs = response.headers

            for (name, acceptable, sev, desc, rec) in _REQUIRED_HEADERS:
                value = hdrs.get(name, "")

                if not value:
                    findings.append(self._finding(
                        category="headers",
                        title=f"Missing {name}",
                        severity=sev,
                        description=desc,
                        recommendation=rec,
                    ))
                    # --- AUTO-FIX: Security Headers ---
                    if name in ("Strict-Transport-Security", "Content-Security-Policy"):
                        log.info(f"Sentinel: Detected missing {name}. Attempting auto-fix via cPanel...")
                        if cpanel.patch_htaccess_security_headers():
                            log.info(f"Sentinel: Successfully patched {name} in .htaccess")
                            # Notify the owner
                            self._approval.send_alert(
                                f"🛡️ *SENTINEL AUTO-FIX*\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"Detected missing security header:\n"
                                f"*{name}*\n\n"
                                f"✅ Successfully patched `.htaccess` via cPanel. "
                                f"Your site is now more secure."
                            )
                        else:
                            log.warning(f"Sentinel: Failed to auto-fix {name}. Manual intervention needed.")
                elif acceptable:
                    # Header exists — quick sanity check
                    val_lower = value.lower()
                    if not any(token.lower() in val_lower for token in acceptable):
                        findings.append(self._finding(
                            category="headers",
                            title=f"Weak {name}",
                            severity="LOW",
                            description=f"Header is present but its value '{self._truncate(value, 120)}' does not contain expected tokens.",
                            recommendation=rec,
                            raw=value,
                        ))

            # ── HSTS max-age depth check ──
            hsts = hdrs.get("Strict-Transport-Security", "")
            if hsts:
                ma_match = re.search(r"max-age=(\d+)", hsts, re.IGNORECASE)
                if ma_match:
                    max_age = int(ma_match.group(1))
                    if max_age < 15_768_000:  # < 6 months
                        findings.append(self._finding(
                            category="headers",
                            title="HSTS max-age Too Short",
                            severity="LOW",
                            description=f"max-age={max_age} ({max_age // 86_400} days). Should be ≥ 1 year for HSTS preload eligibility.",
                            recommendation="Increase to: max-age=63072000; includeSubDomains; preload",
                            raw=hsts,
                        ))

            # ── CSP unsafe directive check ──
            csp = hdrs.get("Content-Security-Policy", "")
            if csp:
                unsafe_tokens = []
                if "'unsafe-inline'" in csp:
                    unsafe_tokens.append("unsafe-inline")
                if "'unsafe-eval'" in csp:
                    unsafe_tokens.append("unsafe-eval")
                if unsafe_tokens:
                    findings.append(self._finding(
                        category="headers",
                        title="CSP Contains Unsafe Directives",
                        severity="MEDIUM",
                        description=f"CSP includes {', '.join(unsafe_tokens)}, significantly weakening XSS protection.",
                        recommendation="Refactor inline scripts to external files; use nonces/hashes instead of unsafe-inline.",
                        raw=self._truncate(csp, 300),
                    ))

            # ── CHECK 6: Information leakage ──
            server_hdr = hdrs.get("Server", "")
            if server_hdr and re.search(r"\d+\.\d+", server_hdr):
                findings.append(self._finding(
                    category="info_leak",
                    title="Server Version Disclosed",
                    severity="LOW",
                    description=f"Server header exposes software version: '{server_hdr}'. Attackers use this to target known CVEs.",
                    recommendation="Strip version from Server header (e.g., `server_tokens off;` in Nginx).",
                    raw=server_hdr,
                ))

            powered_by = hdrs.get("X-Powered-By", "")
            if powered_by:
                findings.append(self._finding(
                    category="info_leak",
                    title="Technology Stack Exposed",
                    severity="LOW",
                    description=f"X-Powered-By: {powered_by}. Reveals backend technology to attackers.",
                    recommendation="Remove the X-Powered-By header entirely.",
                    raw=powered_by,
                ))

            # ── Build report ──
            duration = time.monotonic() - scan_start
            highest = _max_severity(findings)

            report = {
                "site_url": site_url,
                "scan_time": _utcnow(),
                "reachable": True,
                "response_time_s": round(response_time, 3) if response_time else None,
                "status_code": status_code,
                "findings": findings,
                "findings_count": len(findings),
                "highest_severity": highest,
                "scan_duration_s": round(duration, 3),
                "error": None,
            }

            log.info(
                "Vulnerability scan complete  |  site=%s  |  "
                "findings=%d  |  highest=%s  |  %.2fs",
                site_url, len(findings), highest, duration,
            )

            return report

        except Exception as exc:
            # ── ABSOLUTE SAFETY NET ──
            log.critical(
                "scan_vulnerabilities crashed (returning safe default): %s",
                exc, exc_info=True,
            )
            return self._unreachable_report(
                site_url, scan_start, findings,
                error=f"Internal scanner error: {type(exc).__name__}: {self._truncate(str(exc), 200)}",
            )

    # ══════════════════════════════════════════════════════════════════
    #  2.  monitor_failed_logins
    # ══════════════════════════════════════════════════════════════════

    def monitor_failed_logins(self, log_file_path: str) -> List[Dict[str, Any]]:
        """
        Parse *log_file_path* for failed authentication attempts,
        group by source IP, and return IPs that exceed the configured
        threshold (``settings.max_failed_logins_before_block``).

        Supports:
            • sshd / PAM ``auth.log``
            • Apache / Nginx access logs (401/403)
            • WordPress login failures
            • Generic "failed" / "invalid" / "denied" patterns

        Returns
        -------
        list[dict]
            Sorted by ``attempt_count`` descending.  Each entry::

                {
                    "ip": "192.168.1.50",
                    "attempt_count": 37,
                    "first_seen": "2024-06-10T03:12:44+00:00",
                    "last_seen": "2024-06-10T04:58:01+00:00",
                }
        """
        log.info("Analysing failed logins  |  file=%s  |  threshold=%d",
                 log_file_path, self._max_failed_logins)

        try:
            path = Path(log_file_path)

            # ── Pre-flight checks ──
            if not path.exists():
                log.warning("Log file does not exist: %s", log_file_path)
                return []
            if not path.is_file():
                log.warning("Path is not a regular file: %s", log_file_path)
                return []

            # ── Accumulator: ip → {count, first_ts, last_ts} ──
            tracker: Dict[str, Dict[str, Any]] = defaultdict(
                lambda: {"count": 0, "first": None, "last": None}
            )

            lines_read: int = 0
            matches_found: int = 0

            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    for raw_line in fh:
                        lines_read += 1
                        line = raw_line.rstrip("\n\r")

                        for pattern in _FAILED_LOGIN_PATTERNS:
                            m = pattern.search(line)
                            if m:
                                ip = m.group("ip")
                                if not self._is_valid_ipv4(ip):
                                    continue

                                ts = self._parse_log_timestamp(line)
                                rec = tracker[ip]
                                rec["count"] += 1
                                if rec["first"] is None or ts < rec["first"]:
                                    rec["first"] = ts
                                if rec["last"] is None or ts > rec["last"]:
                                    rec["last"] = ts

                                matches_found += 1
                                break  # one match per line is enough
            except PermissionError:
                log.critical("Permission denied: %s", log_file_path)
                return []
            except OSError as exc:
                log.critical("OS error reading %s: %s", log_file_path, exc)
                return []

            # ── Filter by threshold ──
            offenders: List[Dict[str, Any]] = []

            for ip, data in tracker.items():
                if data["count"] >= self._max_failed_logins:
                    entry = {
                        "ip": ip,
                        "attempt_count": data["count"],
                        "first_seen": (data["first"] or datetime.now(timezone.utc)).isoformat(),
                        "last_seen": (data["last"] or datetime.now(timezone.utc)).isoformat(),
                    }
                    offenders.append(entry)

                    log.warning(
                        "🚨 Brute-force suspect  |  ip=%s  |  attempts=%d  |  "
                        "window=%s → %s",
                        ip, data["count"],
                        entry["first_seen"], entry["last_seen"],
                    )

                    log.log_action(
                        action="brute_force_detected",
                        details={
                            "ip": ip,
                            "attempt_count": data["count"],
                            "first_seen": entry["first_seen"],
                            "last_seen": entry["last_seen"],
                            "log_file": log_file_path,
                        },
                        approved=None,
                        reason="threshold_exceeded",
                    )

            # Sort — worst offenders first
            offenders.sort(key=lambda x: x["attempt_count"], reverse=True)

            log.info(
                "Failed-login analysis done  |  lines=%d  |  "
                "matches=%d  |  unique_ips=%d  |  over_threshold=%d",
                lines_read, matches_found, len(tracker), len(offenders),
            )

            return offenders

        except Exception as exc:
            log.critical(
                "monitor_failed_logins crashed: %s", exc, exc_info=True,
            )
            return []

    # ══════════════════════════════════════════════════════════════════
    #  3.  check_file_integrity
    # ══════════════════════════════════════════════════════════════════

    def check_file_integrity(
        self,
        directory: str,
        known_hashes: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """
        Walk *directory*, SHA-256 every eligible file, and compare
        against *known_hashes*.

        Detects three classes of tampering:

        ``modified``
            File exists but its hash differs → possible backdoor injection.
        ``added``
            File exists on disk but is **not** in *known_hashes*
            → possible webshell upload.
        ``deleted``
            File is in *known_hashes* but missing from disk
            → possible evidence destruction.

        Parameters
        ----------
        directory : str
            Absolute or relative path to the site's document root.
        known_hashes : dict
            ``{relative/path: sha256_hex}`` baseline created by
            ``create_baseline_hashes()``.

        Returns
        -------
        list[dict]
            Each entry::

                {
                    "filepath":      "includes/plugin.php",
                    "issue_type":    "modified" | "added" | "deleted",
                    "expected_hash": "abc..." | null,
                    "actual_hash":   "def..." | null,
                    "severity":      "CRITICAL" | "HIGH",
                }
        """
        log.info(
            "File integrity check starting  |  dir=%s  |  baseline_files=%d",
            directory, len(known_hashes),
        )

        issues: List[Dict[str, Any]] = []

        try:
            base = Path(directory).resolve()

            if not base.exists():
                log.critical("Directory does not exist: %s", directory)
                issues.append({
                    "filepath": directory,
                    "issue_type": "deleted",
                    "expected_hash": None,
                    "actual_hash": None,
                    "severity": "CRITICAL",
                })
                return issues

            if not base.is_dir():
                log.critical("Path is not a directory: %s", directory)
                return issues

            # ── Walk and hash ──
            seen_relative: Set[str] = set()

            for root, dirs, filenames in os.walk(base):
                # Skip hidden directories (.git, .svn, .env, etc.)
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for fname in filenames:
                    if fname.startswith("."):
                        continue

                    full_path = Path(root) / fname

                    # Skip by extension
                    if full_path.suffix.lower() in _SKIP_EXTENSIONS:
                        continue

                    # Skip oversized files
                    try:
                        size = full_path.stat().st_size
                        if size > _MAX_FILE_BYTES:
                            log.info("Skipping oversized file (%d B): %s", size, full_path)
                            continue
                    except OSError:
                        continue

                    # Relative key (normalised forward slashes)
                    try:
                        rel = str(full_path.relative_to(base)).replace("\\", "/")
                    except ValueError:
                        continue

                    seen_relative.add(rel)
                    actual_hash = self._sha256_file(full_path)
                    if actual_hash is None:
                        continue  # unreadable — logged inside helper

                    if rel in known_hashes:
                        expected = known_hashes[rel]
                        if actual_hash != expected:
                            issues.append({
                                "filepath": rel,
                                "issue_type": "modified",
                                "expected_hash": expected,
                                "actual_hash": actual_hash,
                                "severity": "CRITICAL",
                            })
                            log.critical(
                                "🔴 FILE MODIFIED  |  %s  |  expected=%s…  |  actual=%s…",
                                rel, expected[:12], actual_hash[:12],
                            )
                    else:
                        issues.append({
                            "filepath": rel,
                            "issue_type": "added",
                            "expected_hash": None,
                            "actual_hash": actual_hash,
                            "severity": "HIGH",
                        })
                        log.warning(
                            "🟠 NEW FILE  |  %s  |  hash=%s…",
                            rel, actual_hash[:12],
                        )

            # ── Detect deletions ──
            for known_path in sorted(known_hashes.keys()):
                if known_path not in seen_relative:
                    issues.append({
                        "filepath": known_path,
                        "issue_type": "deleted",
                        "expected_hash": known_hashes[known_path],
                        "actual_hash": None,
                        "severity": "HIGH",
                    })
                    log.warning("🟠 FILE DELETED  |  %s", known_path)

            # ── Summary ──
            n_mod = sum(1 for i in issues if i["issue_type"] == "modified")
            n_add = sum(1 for i in issues if i["issue_type"] == "added")
            n_del = sum(1 for i in issues if i["issue_type"] == "deleted")

            log.info(
                "File integrity check done  |  modified=%d  |  added=%d  |  "
                "deleted=%d  |  total_issues=%d",
                n_mod, n_add, n_del, len(issues),
            )

            if issues:
                log.log_action(
                    action="file_integrity_violation",
                    details={
                        "directory": directory,
                        "modified_count": n_mod,
                        "added_count": n_add,
                        "deleted_count": n_del,
                        "modified_files": [i["filepath"] for i in issues if i["issue_type"] == "modified"][:20],
                        "added_files": [i["filepath"] for i in issues if i["issue_type"] == "added"][:20],
                        "deleted_files": [i["filepath"] for i in issues if i["issue_type"] == "deleted"][:20],
                    },
                    approved=None,
                    reason="integrity_violation",
                )

            return issues

        except Exception as exc:
            log.critical(
                "check_file_integrity crashed: %s", exc, exc_info=True,
            )
            return issues  # return whatever we found before the crash

    # ══════════════════════════════════════════════════════════════════
    #  4.  block_ip
    # ══════════════════════════════════════════════════════════════════

    def block_ip(self, ip_address: str) -> bool:
        """
        Request a block of *ip_address*.

        ╔═══════════════════════════════════════════════════════════╗
        ║  ⚠️  THIS METHOD DOES NOT EXECUTE FIREWALL COMMANDS.     ║
        ║  It sends an alert to the owner with copy-paste          ║
        ║  commands.  The human must act.  Autonomous firewall     ║
        ║  manipulation is too dangerous — an attacker could       ║
        ║  trick Sentinel into blocking the owner's own IP.        ║
        ╚═══════════════════════════════════════════════════════════╝

        Platform-specific commands sent to the owner for reference:

        LINUX — iptables (most distros):
            sudo iptables -I INPUT -s <IP> -j DROP
            sudo iptables-save > /etc/iptables/rules.v4

        LINUX — ufw (Ubuntu simplified):
            sudo ufw insert 1 deny from <IP> to any

        LINUX — firewalld (RHEL / CentOS):
            sudo firewall-cmd --permanent --add-rich-rule=\\
              'rule family="ipv4" source address="<IP>" drop'
            sudo firewall-cmd --reload

        WINDOWS — netsh:
            netsh advfirewall firewall add rule \\
              name="Falcon-Block-<IP>" dir=in action=block \\
              remoteip=<IP> enable=yes

        CLOUDFLARE — API (preferred if available):
            curl -X POST "https://api.cloudflare.com/client/v4/..." \\
              with mode="block" and target IP

        NGINX — deny directive (application level):
            deny <IP>;   # inside server { } or location { }

        Parameters
        ----------
        ip_address : str
            IPv4 address to block.

        Returns
        -------
        bool
            ``True`` if the alert was dispatched successfully.
            ``False`` on invalid IP or delivery failure.
        """
        log.info("IP block requested  |  ip=%s", ip_address)

        try:
            # ── Validate ──
            if not self._is_valid_ipv4(ip_address):
                log.warning("Rejected block request — invalid IP: %s", ip_address)
                return False

            # ── Prevent alert spam — skip if already alerted ──
            if ip_address in self._blocked_ips:
                log.info("Already alerted about %s — skipping duplicate", ip_address)
                return True

            # ── Record internally ──
            self._blocked_ips.add(ip_address)

            # ── Log to audit trail ──
            log.log_action(
                action="ip_block_requested",
                details={
                    "ip": ip_address,
                    "timestamp": _utcnow(),
                    "ttl_hours": self._blocked_ip_ttl_h,
                    "auto_executed": False,
                },
                approved=None,  # not an approval action; owner decides
                reason="security_threat_detected",
            )

            # ── Compose alert with platform-specific commands ──
            alert = (
                "🚫 IP BLOCK RECOMMENDED\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  IP Address : {ip_address}\n"
                f"  Detected   : {_utcnow()}\n"
                f"  Auto-expire: {self._blocked_ip_ttl_h} hours\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "⚠️ MANUAL ACTION REQUIRED — pick your platform:\n"
                "\n"
                "🐧 Linux (iptables):\n"
                f"  sudo iptables -I INPUT -s {ip_address} -j DROP\n"
                "\n"
                "🐧 Linux (ufw):\n"
                f"  sudo ufw insert 1 deny from {ip_address} to any\n"
                "\n"
                "🪟 Windows (netsh):\n"
                f'  netsh advfirewall firewall add rule name="Falcon-Block-{ip_address}" '
                f"dir=in action=block remoteip={ip_address}\n"
                "\n"
                "☁️ Cloudflare (recommended):\n"
                f"  Add {ip_address} to Firewall Rules → Block\n"
                "\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Reply 'BLOCKED {ip_address}' when done."
            )

            self._approval.send_alert(alert)
            log.info("Block alert dispatched  |  ip=%s", ip_address)
            return True

        except Exception as exc:
            log.critical(
                "block_ip failed: %s", exc, exc_info=True,
            )
            return False

    # ══════════════════════════════════════════════════════════════════
    #  5.  run_scan  (master orchestrator)
    # ══════════════════════════════════════════════════════════════════

    def run_scan(self, site_url: str) -> Dict[str, Any]:
        """
        Execute a full security sweep on *site_url* and return a
        unified report.

        Orchestration flow::

            run_scan
              ├── scan_vulnerabilities  →  transport + header findings
              ├── aggregate severity counts
              ├── log full report to SQLite
              └── if HIGH or CRITICAL → push WhatsApp alert

        Parameters
        ----------
        site_url : str
            Target URL.

        Returns
        -------
        dict
            Comprehensive report including all findings, severity
            breakdown, and metadata.
        """
        scan_id = (
            f"SCAN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-"
            f"{id(self) % 0xFFFF:04X}"
        )
        overall_start = time.monotonic()

        log.info("━" * 64)
        log.info("COMPREHENSIVE SCAN  |  id=%s  |  target=%s", scan_id, site_url)
        log.info("━" * 64)

        try:
            # ── Phase 1: Vulnerability scan ──
            vuln_report = self.scan_vulnerabilities(site_url)

            # ── Aggregate ──
            all_findings: List[Dict[str, Any]] = vuln_report.get("findings", [])
            highest = _max_severity(all_findings)

            severity_counts = {
                "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0,
            }
            for f in all_findings:
                sev = f.get("severity", "INFO")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

            overall_duration = time.monotonic() - overall_start

            full_report: Dict[str, Any] = {
                "scan_id": scan_id,
                "site_url": site_url,
                "scan_time": _utcnow(),
                "scan_duration_s": round(overall_duration, 3),
                "vulnerability_scan": vuln_report,
                "total_findings": len(all_findings),
                "highest_severity": highest,
                "severity_counts": severity_counts,
            }

            # ── Log to audit trail ──
            log.log_action(
                action="security_scan_complete",
                details={
                    "scan_id": scan_id,
                    "site_url": site_url,
                    "total_findings": len(all_findings),
                    "highest_severity": highest,
                    "severity_counts": severity_counts,
                    "duration_s": round(overall_duration, 3),
                },
                approved=None,
                reason="scheduled_scan",
            )

            # ── Alert on HIGH or CRITICAL ──
            if _severity_gte(highest, "HIGH"):
                self._dispatch_scan_alert(scan_id, site_url, all_findings, severity_counts)

            log.info(
                "Scan complete  |  id=%s  |  findings=%d  |  "
                "highest=%s  |  C=%d H=%d M=%d L=%d  |  %.2fs",
                scan_id, len(all_findings), highest,
                severity_counts["CRITICAL"], severity_counts["HIGH"],
                severity_counts["MEDIUM"], severity_counts["LOW"],
                overall_duration,
            )
            log.info("━" * 64)

            return full_report

        except Exception as exc:
            log.critical(
                "run_scan crashed: %s", exc, exc_info=True,
            )
            return {
                "scan_id": scan_id,
                "site_url": site_url,
                "scan_time": _utcnow(),
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                "total_findings": 0,
                "highest_severity": "CRITICAL",
            }

    # ══════════════════════════════════════════════════════════════════
    #  6.  scan_health_claims (Govt compliance check)
    # ══════════════════════════════════════════════════════════════════

    # Wrong health claims that can get you in trouble with govt
    HEALTH_CLAIM_PATTERNS = [
        r"\bcures?\b.*\b(cancer|diabetes|heart|tb| hiv|aids|covid)\b",
        r"\btreats?\b.*\b(cancer|diabetes|heart|tb|hiv|aids|covid)\b",
        r"\bheals?\b.*\b(cancer|diabetes|heart|tb|hiv|aids|covid)\b",
        r"\bmagic\b.*\b(cure|treat|heal)\b",
        r"\bproven\b.*\b(cure|treat|heal)\b",
        r"\bguaranteed\b.*\b(cure|treat|heal)\b",
        r"\b100%\b.*\bcure\b",
        r"\bpermanent\b.*\bcure\b",
        r"\b彝\s*根\b",  # "magic root" in Chinese
        r"\b instantánea\b",  # "instant" in Spanish
    ]

    def scan_health_claims(self, site_url: str) -> Dict[str, Any]:
        """
        Scan website for wrong health claims that can attract
        govt action or legal trouble.
        
        Checks for:
        - Claims about curing diseases (cancer, diabetes, etc)
        - Magic/proven/guaranteed cure language
        - False medical promises
        
        Returns list of problematic pages/claims.
        """
        scan_id = f"HCLAIM-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        
        log.info("━" * 64)
        log.info("HEALTH CLAIM AUDIT  |  id=%s  |  target=%s", scan_id, site_url)
        log.info("━" * 64)
        
        issues = []
        pages_checked = 0
        
        try:
            # Import requests here to avoid issues
            import requests
            from bs4 import BeautifulSoup
            
            # Check homepage first
            pages_to_check = [
                site_url,
                f"{site_url}/shop",
                f"{site_url}/products",
                f"{site_url}/about",
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; FalconAgency/1.0)'
            }
            
            for page_url in pages_to_check:
                try:
                    resp = requests.get(page_url, headers=headers, timeout=15, verify=False)
                    pages_checked += 1
                    
                    if resp.status_code != 200:
                        continue
                    
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    text = soup.get_text(separator=' ', strip=True).lower()
                    
                    # Check each pattern
                    for pattern in self.HEALTH_CLAIM_PATTERNS:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        if matches:
                            # Find where in page
                            for match in matches[:3]:  # Limit per page
                                issues.append({
                                    "page": page_url,
                                    "pattern": pattern[:50],
                                    "match": str(match)[:100],
                                    "severity": "HIGH"
                                })
                    
                except Exception as e:
                    log.warning(f"Error checking {page_url}: {e}")
                    continue
            
            # Also check sitemap if available
            sitemap_url = f"{site_url}/sitemap.xml"
            try:
                resp = requests.get(sitemap_url, headers=headers, timeout=10, verify=False)
                if resp.status_code == 200:
                    # Could parse sitemap for more URLs here
                    log.info("Found sitemap, could scan more pages")
            except:
                pass
            
            report = {
                "scan_id": scan_id,
                "site_url": site_url,
                "scan_time": _utcnow(),
                "pages_checked": pages_checked,
                "total_issues": len(issues),
                "issues": issues[:20],  # Limit to 20
                "severity": "HIGH" if issues else "PASS",
            }
            
            log.info(
                "Health claim audit complete  |  id=%s  |  pages=%d  |  issues=%d",
                scan_id, pages_checked, len(issues)
            )
            log.info("━" * 64)
            
            return report
            
        except Exception as exc:
            log.critical(
                "scan_health_claims crashed: %s", exc, exc_info=True,
            )
            return {
                "scan_id": scan_id,
                "site_url": site_url,
                "scan_time": _utcnow(),
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                "total_issues": 0,
                "issues": [],
                "severity": "ERROR",
            }

    # ══════════════════════════════════════════════════════════════════
    #  6.  start_monitoring  /  stop_monitoring
    # ══════════════════════════════════════════════════════════════════

    def start_monitoring(self, site_url: str) -> None:
        """
        Launch a background thread that runs ``run_scan(site_url)``
        every ``settings.scan_interval_minutes`` minutes.

        The thread is a **daemon** — it dies automatically when the
        main process exits.  It wraps every iteration in try/except
        so a single scan failure can never kill the watchdog.

        Call ``stop_monitoring()`` for a graceful shutdown.

        Parameters
        ----------
        site_url : str
            The URL to continuously monitor.
        """
        with self._monitor_lock:
            if self._monitoring_active:
                log.warning(
                    "Monitoring is already active — call stop_monitoring() first"
                )
                return

            self._monitoring_active = True

            log.info(
                "Starting continuous monitoring  |  site=%s  |  interval=%dm",
                site_url, self._scan_interval_min,
            )

            def _loop() -> None:
                """
                Background monitoring loop.

                Uses the ``schedule`` library to trigger scans at the
                configured interval.  Each scan is wrapped individually
                so that a single failure does not exit the thread.
                """
                # Register the scheduled job
                job = schedule.every(self._scan_interval_min).minutes.do(
                    self._safe_scan_wrapper, site_url,
                )

                # Run an immediate scan at startup
                self._safe_scan_wrapper(site_url)

                # Enter loop
                while self._monitoring_active:
                    try:
                        schedule.run_pending()
                    except Exception as exc:
                        # schedule itself crashed — should never happen,
                        # but if it does, log and continue
                        log.critical(
                            "schedule.run_pending() error: %s", exc,
                            exc_info=True,
                        )

                    # Sleep in short increments so stop_monitoring()
                    # takes effect within ~5 seconds
                    for _ in range(10):
                        if not self._monitoring_active:
                            break
                        time.sleep(1)

                # Clean up the specific job we registered
                try:
                    schedule.cancel_job(job)
                except Exception:
                    pass

                log.info("Monitoring loop exited cleanly  |  site=%s", site_url)

            self._monitor_thread = threading.Thread(
                target=_loop,
                name=f"Sentinel-Monitor-{urlparse(site_url).netloc}",
                daemon=True,
            )
            self._monitor_thread.start()

            log.info(
                "Monitor thread launched  |  thread=%s  |  daemon=True",
                self._monitor_thread.name,
            )

    def stop_monitoring(self) -> None:
        """Gracefully stop the background monitoring loop."""
        with self._monitor_lock:
            if not self._monitoring_active:
                log.info("Monitoring is not active — nothing to stop")
                return

            log.info("Stopping monitoring…")
            self._monitoring_active = False

            if self._monitor_thread and self._monitor_thread.is_alive():
                # Wait up to 30 seconds for a clean exit
                self._monitor_thread.join(timeout=30)
                if self._monitor_thread.is_alive():
                    log.warning("Monitor thread did not exit within 30s")
                else:
                    log.info("Monitor thread stopped cleanly")

            self._monitor_thread = None
            log.info("Monitoring stopped")

    @property
    def is_monitoring(self) -> bool:
        """``True`` if the background monitoring loop is running."""
        return self._monitoring_active

    # ══════════════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ══════════════════════════════════════════════════════════════════

    # ── Scan wrapper for the scheduler ──

    def _safe_scan_wrapper(self, site_url: str) -> None:
        """
        Wrapper around ``run_scan()`` that catches absolutely everything.
        Used by the scheduler — a crash here must NEVER kill the thread.
        """
        try:
            self.run_scan(site_url)
        except Exception as exc:
            log.critical(
                "Safe scan wrapper caught unhandled exception: %s",
                exc, exc_info=True,
            )

    # ── Finding builder ──

    @staticmethod
    def _finding(
        *,
        category: str,
        title: str,
        severity: str,
        description: str,
        recommendation: str,
        raw: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct a normalised finding dict."""
        return {
            "category": category,
            "title": title,
            "severity": severity,
            "description": description,
            "recommendation": recommendation,
            "raw": raw,
        }

    # ── Error report builder ──

    def _unreachable_report(
        self,
        site_url: str,
        scan_start: float,
        existing_findings: List[Dict[str, Any]],
        *,
        error: str,
    ) -> Dict[str, Any]:
        """Build a report when the site cannot be reached."""
        existing_findings.append(self._finding(
            category="availability",
            title="Site Unreachable",
            severity="CRITICAL",
            description=error,
            recommendation=(
                "1. Check DNS resolution (dig / nslookup).  "
                "2. Verify server process is running.  "
                "3. Check firewall / security group rules.  "
                "4. Test from a different network."
            ),
        ))

        duration = time.monotonic() - scan_start

        log.critical("Site unreachable  |  %s  |  %s", site_url, error)

        return {
            "site_url": site_url,
            "scan_time": _utcnow(),
            "reachable": False,
            "response_time_s": None,
            "status_code": None,
            "findings": existing_findings,
            "findings_count": len(existing_findings),
            "highest_severity": "CRITICAL",
            "scan_duration_s": round(duration, 3),
            "error": error,
        }

    # ── WhatsApp alert for scans ──

    def _dispatch_scan_alert(
        self,
        scan_id: str,
        site_url: str,
        findings: List[Dict[str, Any]],
        counts: Dict[str, int],
    ) -> None:
        """Send a concise WhatsApp alert for HIGH / CRITICAL findings."""
        try:
            # Cooldown: if ONLY finding is "Site Unreachable", max 1 per site per 30 min
            critical_titles = [f.get("title", "") for f in findings if f.get("severity") == "CRITICAL"]
            if critical_titles == ["Site Unreachable"] and counts.get("CRITICAL", 0) == 1:
                now_mono = time.monotonic()
                last = self._last_unreachable_scan_alert.get(site_url, 0)
                if now_mono - last < 1800:  # 30 min
                    log.info("Skipping Site Unreachable scan alert (cooldown)  |  %s", site_url)
                    return
                self._last_unreachable_scan_alert[site_url] = now_mono

            # Build a bullet list of the worst findings
            bullet_lines: List[str] = []
            for f in findings:
                sev = f.get("severity", "")
                if sev in ("CRITICAL", "HIGH"):
                    icon = "🔴" if sev == "CRITICAL" else "🟠"
                    bullet_lines.append(
                        f"  {icon} [{sev}] {f.get('title', '?')}"
                    )

            # Cap at 15 lines to stay within WhatsApp limits
            display = bullet_lines[:15]
            overflow = len(bullet_lines) - 15

            body = (
                "🛡️ SECURITY SCAN ALERT\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  Scan ID : {scan_id}\n"
                f"  Site    : {site_url}\n"
                f"  Time    : {_utcnow()}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  🔴 CRITICAL : {counts.get('CRITICAL', 0)}\n"
                f"  🟠 HIGH     : {counts.get('HIGH', 0)}\n"
                f"  🟡 MEDIUM   : {counts.get('MEDIUM', 0)}\n"
                f"  ⚪ LOW      : {counts.get('LOW', 0)}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                + "\n".join(display)
                + (f"\n  … and {overflow} more" if overflow > 0 else "")
                + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Review and remediate immediately."
            )

            self._approval.send_alert(body)
            log.info("Scan alert dispatched  |  id=%s", scan_id)

        except Exception as exc:
            # Alert delivery failure must not crash the scan
            log.critical("Failed to dispatch scan alert: %s", exc, exc_info=True)

    # ── File hashing ──

    @staticmethod
    def _sha256_file(filepath: Path) -> Optional[str]:
        """
        Compute SHA-256 of *filepath*.

        Returns the hex digest, or ``None`` if the file is unreadable.
        Reads in ``_HASH_CHUNK_SIZE`` chunks to handle large files
        without blowing up memory.
        """
        try:
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(_HASH_CHUNK_SIZE)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except (OSError, IOError) as exc:
            log.warning("Cannot hash %s: %s", filepath, exc)
            return None

    # ── IP validation ──

    @staticmethod
    def _is_valid_ipv4(ip: str) -> bool:
        """
        Validate an IPv4 address string.

        Uses ``ipaddress.IPv4Address`` for correctness — manual regex
        can miss edge cases (leading zeros, 999.999.999.999, etc.).
        """
        try:
            addr = ipaddress.IPv4Address(ip)
            # Reject loopback, link-local, and private as brute-force sources
            # (they are almost certainly log noise in production)
            # NOTE: We still *accept* them — the caller decides.
            return True
        except (ipaddress.AddressValueError, ValueError):
            return False

    # ── Log timestamp extraction ──

    @staticmethod
    def _parse_log_timestamp(line: str) -> datetime:
        """
        Best-effort timestamp extraction from a log line.

        Supports (in priority order):
            1. ISO 8601:        2024-06-10T14:30:00
            2. ISO space-sep:   2024-06-10 14:30:00
            3. Apache combined: 10/Jun/2024:14:30:00 +0000
            4. Syslog:          Jun 10 14:30:00
            5. Fallback:        datetime.now(UTC)
        """
        _MONTH_MAP = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        # 1. ISO 8601 / space-separated
        iso_m = re.search(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})", line)
        if iso_m:
            try:
                return datetime(
                    *map(int, iso_m.groups()),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                pass

        # 2. Apache combined
        apache_m = re.search(
            r"(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2})", line,
        )
        if apache_m:
            try:
                day, mon_s, year, hh, mm, ss = apache_m.groups()
                return datetime(
                    int(year),
                    _MONTH_MAP.get(mon_s.lower(), 1),
                    int(day),
                    int(hh), int(mm), int(ss),
                    tzinfo=timezone.utc,
                )
            except (ValueError, KeyError):
                pass

        # 3. Syslog (no year — assume current)
        syslog_m = re.search(
            r"([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})", line,
        )
        if syslog_m:
            try:
                mon_s, day, hh, mm, ss = syslog_m.groups()
                return datetime(
                    datetime.now().year,
                    _MONTH_MAP.get(mon_s.lower(), 1),
                    int(day),
                    int(hh), int(mm), int(ss),
                    tzinfo=timezone.utc,
                )
            except (ValueError, KeyError):
                pass

        # 4. Fallback
        return datetime.now(timezone.utc)

    # ── URL normalisation ──

    @staticmethod
    def _normalise_url(url: str) -> str:
        """Ensure *url* has a scheme; default to https."""
        url = url.strip()
        if not url:
            return "https://localhost"
        parsed = urlparse(url)
        if not parsed.scheme:
            return f"https://{url}"
        return url

    # ── Text truncation ──

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        """Truncate *text* to *limit* chars, adding '…' if cut."""
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"

    # ── Repr ──

    def __repr__(self) -> str:
        return (
            f"<Sentinel  "
            f"interval={self._scan_interval_min}m  "
            f"threshold={self._max_failed_logins}  "
            f"blocked={len(self._blocked_ips)}  "
            f"monitoring={'🟢' if self._monitoring_active else '⚫'}>"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MODULE UTILITY: Baseline Hash Generator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def create_baseline_hashes(directory: str) -> Dict[str, str]:
    """
    Walk *directory* and compute SHA-256 for every eligible file.

    Use this to create the ``known_hashes`` dict that
    ``Sentinel.check_file_integrity()`` compares against.

    Typical workflow::

        # On a KNOWN-CLEAN deployment:
        import json
        from core.sentinel import create_baseline_hashes

        hashes = create_baseline_hashes("/var/www/falconherbs.com")
        with open("baseline_falconherbs.json", "w") as f:
            json.dump(hashes, f, indent=2)

        # Later, Sentinel loads this JSON and checks for drift.

    Parameters
    ----------
    directory : str
        Root directory to fingerprint.

    Returns
    -------
    dict
        ``{relative/path: sha256_hex, …}``
    """
    hashes: Dict[str, str] = {}
    base = Path(directory).resolve()

    if not base.is_dir():
        log.warning("create_baseline_hashes: not a directory: %s", directory)
        return hashes

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for fname in files:
            if fname.startswith("."):
                continue

            full = Path(root) / fname

            if full.suffix.lower() in _SKIP_EXTENSIONS:
                continue

            try:
                if full.stat().st_size > _MAX_FILE_BYTES:
                    continue
            except OSError:
                continue

            try:
                rel = str(full.relative_to(base)).replace("\\", "/")
            except ValueError:
                continue

            h = hashlib.sha256()
            try:
                with open(full, "rb") as fh:
                    while True:
                        chunk = fh.read(_HASH_CHUNK_SIZE)
                        if not chunk:
                            break
                        h.update(chunk)
                hashes[rel] = h.hexdigest()
            except (OSError, IOError):
                continue

    log.info(
        "Baseline created  |  directory=%s  |  files=%d", directory, len(hashes)
    )
    return hashes
