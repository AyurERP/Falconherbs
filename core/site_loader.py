"""
Falcon Agency — Multi-Site Config Loader
==========================================

Loads config/sites.json and resolves env var references to actual values.
Enables multi-site support without changing any code.

Adding a new site: just add an entry to config/sites.json.

Usage:
    from core.site_loader import site_loader
    
    # Get resolved config for active site
    config = site_loader.get_active_site()
    
    # Get config for a specific site
    config = site_loader.get_site("falconherbs")
    
    # Get all active sites
    sites = site_loader.get_all_active_sites()
    
    # Max API calls per minute for a site (default 5)
    max_calls = site_loader.get_max_calls("falconherbs")  # → 5

Config format (resolved):
    {
        "key": "falconherbs",
        "name": "Falcon Herbs",
        "url": "https://falconherbs.com",
        "wc_key": "<actual key from env>",
        "wc_secret": "<actual secret from env>",
        "wp_user": "<actual user from env>",
        "wp_pass": "<actual pass from env>",
        "max_calls_per_minute": 5,
        "status": "live",
        ...
    }
"""

import json
import os
from pathlib import Path

SITES_FILE = Path("config/sites.json")


class SiteLoader:
    """
    Loads and resolves site configs from config/sites.json.
    Caches resolved configs in memory for the process lifetime.
    """

    def __init__(self, sites_file: str = None):
        self._path = Path(sites_file) if sites_file else SITES_FILE
        self._raw: dict = {}
        self._resolved: dict = {}   # site_key → resolved config
        self._reload()

    def _reload(self) -> None:
        """Load the sites JSON from disk."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._raw = json.load(f)
        except FileNotFoundError:
            print(f"⚠️ [SiteLoader] {self._path} not found. Using empty config.")
            self._raw = {"sites": {}, "active_site": ""}
        except Exception as e:
            print(f"⚠️ [SiteLoader] Failed to load {self._path}: {e}")
            self._raw = {"sites": {}, "active_site": ""}
        self._resolved = {}   # clear cache on reload

    def _resolve_env(self, value: str) -> str:
        """
        If value looks like an env var reference (e.g. "FALCONHERBS_WC_API_KEY"),
        resolve it. Otherwise return as-is.
        """
        if not isinstance(value, str):
            return value
        # Env var reference: uppercase, underscores, no spaces
        if value.isupper() and "_" in value and " " not in value:
            return os.getenv(value, "")
        return value

    def _resolve_site(self, site_key: str, raw: dict) -> dict:
        """Build a resolved config dict from a raw site config."""
        resolved = {
            "key": site_key,
            "name": raw.get("name", site_key),
            "url": raw.get("url", ""),
            "niche": raw.get("niche", ""),
            "country": raw.get("country", "India"),
            "currency": raw.get("currency", "INR"),
            "language": raw.get("language", "en"),
            "gst_rate": raw.get("gst_rate", 0.18),
            "status": raw.get("status", "pending"),
            "max_calls_per_minute": raw.get("max_calls_per_minute", 5),
            "notes": raw.get("notes", ""),
            # Resolved credentials
            "wc_key":    self._resolve_env(raw.get("wc_key_env", "")),
            "wc_secret": self._resolve_env(raw.get("wc_secret_env", "")),
            "wp_user":   self._resolve_env(raw.get("wp_user_env", "")),
            "wp_pass":   (
                self._resolve_env(raw.get("wp_pass_env", ""))
                or self._resolve_env(raw.get("wp_app_pass_env", ""))
            ),
            "cpanel_url":  self._resolve_env(raw.get("cpanel_url_env", "")),
            "cpanel_user": self._resolve_env(raw.get("cpanel_user_env", "")),
            "email":       self._resolve_env(raw.get("email_env", "")),
            "imap_host":   self._resolve_env(raw.get("imap_host_env", "")),
            # Raw config for reference
            "_raw": raw,
        }
        return resolved

    def get_site(self, site_key: str) -> dict:
        """
        Return resolved config for site_key.
        Returns {} if site not found.
        """
        if site_key in self._resolved:
            return self._resolved[site_key]

        sites = self._raw.get("sites", {})
        raw = sites.get(site_key)
        if not raw:
            return {}

        resolved = self._resolve_site(site_key, raw)
        self._resolved[site_key] = resolved
        return resolved

    def get_active_site(self) -> dict:
        """Return config for the currently active site."""
        active_key = self._raw.get("active_site", "falconherbs")
        return self.get_site(active_key)

    def get_active_key(self) -> str:
        """Return the key of the active site (e.g. 'falconherbs')."""
        return self._raw.get("active_site", "falconherbs")

    def get_all_active_sites(self) -> list:
        """Return resolved configs for all sites with status='live'."""
        result = []
        for site_key in self._raw.get("sites", {}):
            config = self.get_site(site_key)
            if config.get("status") == "live":
                result.append(config)
        return result

    def get_max_calls(self, site_key: str) -> int:
        """Max WHM API calls per minute for this site."""
        config = self.get_site(site_key)
        return config.get("max_calls_per_minute", 5)

    def list_sites(self) -> list:
        """Return list of all site keys."""
        return list(self._raw.get("sites", {}).keys())

    def reload(self) -> None:
        """Force reload from disk (e.g. after config change)."""
        self._reload()

    def status_report(self) -> str:
        """WhatsApp-friendly site list."""
        lines = ["🌐 *SITE REGISTRY*"]
        for key in self.list_sites():
            cfg = self.get_site(key)
            icon = "✅" if cfg.get("status") == "live" else "⏳"
            has_creds = bool(cfg.get("wc_key") and cfg.get("wc_secret"))
            cred_icon = "🔑" if has_creds else "❌ no keys"
            lines.append(f"  {icon} {cfg['name']} ({key}) — {cred_icon} — max {cfg['max_calls_per_minute']}/min")
        return "\n".join(lines)


# Module-level singleton (loads from config/sites.json)
site_loader = SiteLoader()
