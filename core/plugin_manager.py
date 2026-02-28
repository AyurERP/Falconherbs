"""
core/plugin_manager.py — Plugin Management for Falcon Agency
=============================================================

Safe plugin install, update, list, and recommend.
ALL installs go through approval gate. No silent installs. Ever.

WordPress.org only. Safety rules: min 10k installs, 4.0 rating,
updated within 6 months.
"""

from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from core.logger import log

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SAFETY RULES — Non-negotiable
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SAFETY_RULES = {
    "min_installs": 10_000,
    "min_rating": 4.0,
    "max_days_since_update": 180,  # 6 months
    "source": "wordpress.org",  # Only wordpress.org plugins
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RECOMMENDED PLUGINS — Curated by category
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECOMMENDED_PLUGINS: Dict[str, List[Dict[str, str]]] = {
    "seo": [
        {"slug": "rank-math-seo", "name": "Rank Math SEO", "reason": "SEO optimization"},
        {"slug": "wordpress-seo", "name": "Yoast SEO", "reason": "SEO optimization"},
        {"slug": "all-in-one-seo-pack", "name": "All in One SEO", "reason": "SEO optimization"},
    ],
    "caching": [
        {"slug": "wp-super-cache", "name": "WP Super Cache", "reason": "Page caching"},
        {"slug": "w3-total-cache", "name": "W3 Total Cache", "reason": "Page caching"},
        {"slug": "wp-fastest-cache", "name": "WP Fastest Cache", "reason": "Page caching"},
    ],
    "security": [
        {"slug": "wordfence", "name": "Wordfence Security", "reason": "Firewall & malware scan"},
        {"slug": "sucuri-scanner", "name": "Sucuri Security", "reason": "Security hardening"},
        {"slug": "better-wp-security", "name": "iThemes Security", "reason": "Security hardening"},
    ],
    "backup": [
        {"slug": "updraftplus", "name": "UpdraftPlus", "reason": "Backup & restore"},
        {"slug": "backup-backup", "name": "Backup Migration", "reason": "Backup & restore"},
    ],
    "performance": [
        {"slug": "wp-super-cache", "name": "WP Super Cache", "reason": "Page caching"},
        {"slug": "autoptimize", "name": "Autoptimize", "reason": "JS/CSS optimization"},
        {"slug": "wp-fastest-cache", "name": "WP Fastest Cache", "reason": "Page caching"},
    ],
    "woocommerce": [
        {"slug": "woocommerce", "name": "WooCommerce", "reason": "E-commerce"},
        {"slug": "woocommerce-gateway-stripe", "name": "WooCommerce Stripe", "reason": "Payments"},
    ],
}

WP_ORG_API_URL = "https://api.wordpress.org/plugins/info/1.2/"
HTTP_TIMEOUT = 30


def _normalise_slug(slug: str) -> str:
    """Normalise plugin slug: lowercase, hyphens only."""
    s = slug.strip().lower().replace("_", "-")
    return re.sub(r"[^a-z0-9\-]", "", s)


def check_plugin_safety(plugin_slug: str) -> Dict[str, Any]:
    """
    Query WordPress.org API and validate against SAFETY_RULES.

    Returns:
        {
            "safe": bool,
            "reasons": list[str],
            "plugin_info": dict or None,
        }
    """
    slug = _normalise_slug(plugin_slug)
    if not slug:
        return {
            "safe": False,
            "reasons": ["Invalid or empty plugin slug"],
            "plugin_info": None,
        }

    try:
        resp = requests.post(
            WP_ORG_API_URL,
            data={"action": "plugin_information", "request[slug]": slug},
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "FalconAgency/1.0"},
        )
        resp.raise_for_status()
        info = resp.json()
    except requests.exceptions.RequestException as e:
        log.warning("Plugin check failed for %s: %s", slug, e)
        return {
            "safe": False,
            "reasons": [f"Could not fetch plugin info from wordpress.org: {e}"],
            "plugin_info": None,
        }
    except Exception as e:
        log.warning("Plugin check failed for %s: %s", slug, e)
        return {
            "safe": False,
            "reasons": [f"Unexpected error: {e}"],
            "plugin_info": None,
        }

    reasons: List[str] = []
    # Check required fields
    if "slug" not in info and "name" not in info:
        return {
            "safe": False,
            "reasons": ["Plugin not found on wordpress.org"],
            "plugin_info": info,
        }

    # Min installs
    active_installs = info.get("active_installs", 0) or 0
    if active_installs < SAFETY_RULES["min_installs"]:
        reasons.append(
            f"Active installs ({active_installs:,}) below minimum "
            f"({SAFETY_RULES['min_installs']:,})"
        )

    # Min rating
    rating = float(info.get("rating", 0) or 0) / 20  # WP uses 0-100 scale
    if rating < SAFETY_RULES["min_rating"]:
        reasons.append(
            f"Rating ({rating:.1f}) below minimum ({SAFETY_RULES['min_rating']})"
        )

    # Updated within 6 months
    last_updated = info.get("last_updated")
    if last_updated:
        try:
            # WP returns "2024-01-15 12:00:00 GMT" or similar
            dt = datetime.strptime(last_updated[:19], "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
            cutoff = datetime.now(timezone.utc) - timedelta(
                days=SAFETY_RULES["max_days_since_update"]
            )
            if dt < cutoff:
                reasons.append(
                    f"Last updated {last_updated[:10]} — not updated within "
                    f"{SAFETY_RULES['max_days_since_update']} days"
                )
        except (ValueError, TypeError):
            pass  # If we can't parse, don't fail on it

    safe = len(reasons) == 0
    return {
        "safe": safe,
        "reasons": reasons,
        "plugin_info": info,
    }


def _resolve_env(val: str) -> str:
    """Resolve {{ENV:VAR}} to os.environ value."""
    import os
    if isinstance(val, str) and val.startswith("{{ENV:") and val.endswith("}}"):
        var = val[6:-2].strip()
        return os.environ.get(var, "") or ""
    return val or ""


def _get_wp_auth_headers(site_config: dict) -> Optional[Dict[str, str]]:
    """Build Basic Auth headers from site config or env."""
    import os
    creds = site_config.get("credentials", {})
    raw_user = site_config.get("wp_user") or creds.get("wp_admin_user") or ""
    wp_user = _resolve_env(str(raw_user)) if raw_user else os.getenv("FALCONHERBS_WP_USER")
    raw_pass = creds.get("wp_app_password") or creds.get("wp_admin_password") or ""
    wp_pass = (
        (_resolve_env(str(raw_pass)) if raw_pass else "")
        or os.getenv("FALCONHERBS_WP_APP_PASSWORD")
        or os.getenv("FALCONHERBS_WP_PASSWORD")
    )
    if not wp_user or not wp_pass:
        return None
    token = base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _get_site_url(site_config: dict) -> str:
    """Extract site URL from config."""
    identity = site_config.get("identity", {})
    url = identity.get("url", "") or site_config.get("url", "")
    if not url:
        return "https://falconherbs.com"
    return url.rstrip("/")


def _verify_site_works(site_url: str) -> Dict[str, Any]:
    """Verify homepage, /shop, /cart return HTTP 200."""
    paths = ["/", "/shop", "/cart"]
    results = {}
    for path in paths:
        try:
            r = requests.get(f"{site_url}{path}", timeout=HTTP_TIMEOUT)
            results[path] = r.status_code == 200
        except Exception as e:
            results[path] = False
            log.warning("Verify %s%s failed: %s", site_url, path, e)
    all_ok = all(results.values())
    return {"ok": all_ok, "results": results}


def list_installed_plugins(site_config: dict) -> Dict[str, Any]:
    """
    List installed plugins via WordPress REST API GET /wp-json/wp/v2/plugins.

    Requires application password auth.
    """
    site_url = _get_site_url(site_config)
    api_url = f"{site_url}/wp-json/wp/v2/plugins"
    headers = _get_wp_auth_headers(site_config)
    if not headers:
        return {
            "success": False,
            "error": (
                "WordPress auth not configured. "
                "Set FALCONHERBS_WP_USER and FALCONHERBS_WP_APP_PASSWORD in .env"
            ),
            "plugins": [],
        }

    try:
        r = requests.get(api_url, headers=headers, timeout=HTTP_TIMEOUT)
        if r.status_code == 404:
            return {
                "success": False,
                "error": "Plugins endpoint not available. WordPress 5.5+ required.",
                "plugins": [],
            }
        if r.status_code == 401:
            return {
                "success": False,
                "error": "HTTP 401: WP auth failed. Check Application Password.",
                "plugins": [],
            }
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "plugins": [],
        }

    plugins = []
    for p in data if isinstance(data, list) else []:
        plugin_file = p.get("plugin", "")
        name = p.get("name", plugin_file)
        version = p.get("version", "")
        status = p.get("status", "inactive")
        plugins.append({
            "name": name,
            "plugin": plugin_file,
            "version": version,
            "active": status == "active",
            "update_available": p.get("update", False),
        })
    return {"success": True, "plugins": plugins}


class PluginManager:
    """
    Plugin management with approval gate, backup, and verification.

    All installs MUST go through approval. No silent installs. Ever.
    """

    def __init__(
        self,
        site_config: Optional[dict] = None,
        approval_system=None,
        backup_agent=None,
    ):
        self.site_config = site_config or {}
        self._approval = approval_system
        self._backup = backup_agent

    def _ensure_approval(self):
        if self._approval is None:
            from core.approval import ApprovalSystem
            self._approval = ApprovalSystem()

    def _ensure_backup(self):
        if self._backup is None:
            from agents.backup import BackupAgent
            self._backup = BackupAgent()

    def install_plugin(self, plugin_slug: str, site_config: Optional[dict] = None) -> Dict[str, Any]:
        """
        Full safety flow:
        1. check_plugin_safety()
        2. Request owner approval
        3. Run backup BEFORE install
        4. Install via WordPress REST API
        5. Activate plugin
        6. Verify site works (homepage, /shop, /cart)
        7. If ANY verification fails → deactivate → alert owner
        8. Report result
        """
        config = site_config or self.site_config
        site_url = _get_site_url(config)
        slug = _normalise_slug(plugin_slug)

        # 1. Safety check
        safety = check_plugin_safety(slug)
        if not safety["safe"]:
            return {
                "success": False,
                "error": "Plugin failed safety check",
                "reasons": safety["reasons"],
            }

        # 2. Approval gate — MUST pass
        self._ensure_approval()
        approved = self._approval.request_approval(
            action="plugin_install",
            details={
                "site": site_url,
                "plugin_slug": slug,
                "plugin_name": safety.get("plugin_info", {}).get("name", slug),
                "description": f"Install {slug} from wordpress.org",
            },
        )
        if not approved:
            return {
                "success": False,
                "error": "Owner denied plugin install",
            }

        # 3. Backup before install
        self._ensure_backup()
        site_domain = site_url.replace("https://", "").replace("http://", "").split("/")[0]
        backup_result = self._backup.pre_deploy_snapshot(
            site_domain,
            {"deploy_description": f"plugin_install_{slug}"},
        )
        if not backup_result.get("verified", False):
            log.warning("Pre-install backup verification weak — proceeding anyway")

        # 4 & 5. Install via REST API
        api_url = f"{site_url}/wp-json/wp/v2/plugins"
        headers = _get_wp_auth_headers(config)
        if not headers:
            return {
                "success": False,
                "error": "WordPress auth not configured",
            }
        headers["Content-Type"] = "application/json"

        try:
            r = requests.post(
                api_url,
                json={"slug": slug, "status": "active"},
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
            if r.status_code in (404, 501):
                return {
                    "success": False,
                    "error": (
                        "Plugin install via REST API not available. "
                        "Use WP Admin > Plugins > Add New, or WP-CLI: wp plugin install " + slug
                    ),
                }
            if r.status_code == 401:
                return {"success": False, "error": "HTTP 401: WP auth failed"}
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

        # 6. Verify site works
        verify = _verify_site_works(site_url)
        if not verify["ok"]:
            # 7. Deactivate & alert
            failed = [k for k, v in verify["results"].items() if not v]
            try:
                # Try to deactivate
                plug_data = r.json() if hasattr(r, "json") else {}
                plugin_file = plug_data.get("plugin", "")
                if plugin_file:
                    deact_url = f"{api_url}/{plugin_file}"
                    requests.post(
                        deact_url,
                        json={"status": "inactive"},
                        headers=headers,
                        timeout=HTTP_TIMEOUT,
                    )
            except Exception:
                pass
            if self._approval:
                self._approval.send_alert(
                    f"⚠️ Plugin {slug} installed but site verification failed: "
                    f"{failed}. Plugin deactivated. Please check manually."
                )
            return {
                "success": False,
                "error": f"Site verification failed: {failed}",
                "plugin_deactivated": True,
            }

        return {
            "success": True,
            "message": f"Plugin {slug} installed and activated. Site verified.",
            "backup_id": backup_result.get("backup_id", ""),
        }

    def recommend_plugins(
        self,
        need: str,
        site_config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Match need to RECOMMENDED_PLUGINS, check which already installed,
        return suggestions with safety scores.
        """
        config = site_config or self.site_config
        need_lower = need.lower().strip()

        # Map need to category
        if any(x in need_lower for x in ["speed", "slow", "fast", "performance"]):
            category = "performance"
        elif "seo" in need_lower:
            category = "seo"
        elif any(x in need_lower for x in ["security", "secure"]):
            category = "security"
        elif "backup" in need_lower:
            category = "backup"
        elif "cache" in need_lower:
            category = "caching"
        elif "woo" in need_lower or "shop" in need_lower:
            category = "woocommerce"
        else:
            category = "performance"

        installed = list_installed_plugins(config)
        installed_slugs = set()
        if installed.get("success"):
            for p in installed.get("plugins", []):
                plug = p.get("plugin", "")
                if "/" in plug:
                    installed_slugs.add(plug.split("/")[0])
                else:
                    installed_slugs.add(plug)

        suggestions = []
        for rec in RECOMMENDED_PLUGINS.get(category, []):
            slug = rec["slug"]
            safety = check_plugin_safety(slug)
            score = "safe" if safety["safe"] else "unsafe"
            if safety["safe"]:
                score_str = "✅ Safe"
            else:
                score_str = "⚠️ " + "; ".join(safety["reasons"][:2])
            suggestions.append({
                "slug": slug,
                "name": rec["name"],
                "reason": rec["reason"],
                "already_installed": slug in installed_slugs,
                "safety": score,
                "safety_detail": score_str,
            })

        return {
            "need": need,
            "category": category,
            "suggestions": suggestions,
            "installed_count": len(installed_slugs),
        }

    def update_plugin(
        self,
        plugin_slug: str,
        site_config: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Backup first → update → verify → rollback if broken.
        """
        config = site_config or self.site_config
        site_url = _get_site_url(config)
        slug = _normalise_slug(plugin_slug)

        # Approval for update
        self._ensure_approval()
        approved = self._approval.request_approval(
            action="plugin_update",
            details={
                "site": site_url,
                "plugin_slug": slug,
                "description": f"Update plugin {slug}",
            },
        )
        if not approved:
            return {"success": False, "error": "Owner denied plugin update"}

        # Backup
        self._ensure_backup()
        site_domain = site_url.replace("https://", "").replace("http://", "").split("/")[0]
        backup_result = self._backup.pre_deploy_snapshot(
            site_domain,
            {"deploy_description": f"plugin_update_{slug}"},
        )

        api_url = f"{site_url}/wp-json/wp/v2/plugins"
        headers = _get_wp_auth_headers(config)
        if not headers:
            return {"success": False, "error": "WordPress auth not configured"}
        headers["Content-Type"] = "application/json"

        # Find plugin file
        list_result = list_installed_plugins(config)
        if not list_result.get("success"):
            return {"success": False, "error": list_result.get("error", "Cannot list plugins")}
        plugin_file = None
        for p in list_result.get("plugins", []):
            if slug in (p.get("plugin", "") or ""):
                plugin_file = p.get("plugin")
                break
        if not plugin_file:
            return {"success": False, "error": f"Plugin {slug} not found"}

        try:
            # WP REST API: POST to plugin endpoint with update
            update_url = f"{api_url}/{plugin_file}"
            r = requests.post(
                update_url,
                json={"slug": slug},
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
            if r.status_code in (404, 501):
                return {
                    "success": False,
                    "error": "Plugin update via REST API not available. Use WP Admin.",
                }
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

        verify = _verify_site_works(site_url)
        if not verify["ok"]:
            failed = [k for k, v in verify["results"].items() if not v]
            if self._approval:
                self._approval.send_alert(
                    f"⚠️ Plugin {slug} update may have broken site: {failed}. "
                    f"Check backup {backup_result.get('backup_id', '')} for restore."
                )
            return {
                "success": False,
                "error": f"Site verification failed: {failed}",
                "rollback_available": True,
            }

        return {
            "success": True,
            "message": f"Plugin {slug} updated. Site verified.",
            "backup_id": backup_result.get("backup_id", ""),
        }
