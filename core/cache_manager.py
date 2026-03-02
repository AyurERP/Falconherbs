"""
Falcon Agency — Local Cache Manager (Oracle VPS)
================================================

Disk-based TTL cache saved in data/cache/.
Runs on Oracle VPS — zero load on WHM shared server.

TTL defaults:
    products    = 7200   seconds (2 hours)
    blogs       = 21600  seconds (6 hours)
    categories  = 86400  seconds (24 hours)
    scan_state  = 7200   seconds (change-detection fingerprint)

Usage:
    from core.cache_manager import cache
    
    # Store
    cache.set("products_falconherbs", products_list, ttl=7200)
    
    # Retrieve (None if expired or missing)
    data = cache.get("products_falconherbs")
    
    # Get change-detection map: {product_id: date_modified}
    modified_map = cache.get_product_modified_map("falconherbs")
    
    # Save change-detection fingerprint
    cache.save_product_modified_map("falconherbs", modified_map)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from core.ist_time import now_ist, now_ist_str

# TTL constants (seconds)
TTL_PRODUCTS   = 7200    # 2 hours
TTL_BLOGS      = 21600   # 6 hours
TTL_CATEGORIES = 86400   # 24 hours
TTL_SCAN_STATE = 7200    # 2 hours


class CacheManager:
    """
    Disk-based JSON cache with TTL expiry.
    Thread-safe via atomic file replace.
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        """Sanitise key → safe filename."""
        safe = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe}.json"

    def get(self, key: str):
        """
        Return cached value, or None if missing / expired.
        """
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            expires_at = entry.get("expires_at")
            if expires_at:
                if now_ist_str() > expires_at:
                    path.unlink(missing_ok=True)   # expired — delete
                    return None
            return entry.get("value")
        except Exception:
            return None

    def set(self, key: str, value, ttl: int = TTL_PRODUCTS) -> None:
        """
        Store value with TTL expiry (seconds).
        Atomic write — won't corrupt on crash.
        """
        from datetime import timedelta
        expires_dt = now_ist().replace(microsecond=0) + timedelta(seconds=ttl)
        entry = {
            "key": key,
            "cached_at": now_ist_str(),
            "expires_at": expires_dt.isoformat(),
            "ttl_seconds": ttl,
            "value": value,
        }
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False, default=str)
            tmp.replace(path)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            print(f"⚠️ [Cache] Failed to write {key}: {e}")

    def invalidate(self, key: str) -> None:
        """Force-delete a cache entry."""
        path = self._path(key)
        path.unlink(missing_ok=True)

    def invalidate_prefix(self, prefix: str) -> int:
        """Delete all cache entries whose key starts with prefix. Returns count."""
        deleted = 0
        for f in self.cache_dir.glob("*.json"):
            if f.stem.startswith(prefix.replace("/", "_")):
                f.unlink(missing_ok=True)
                deleted += 1
        return deleted

    def is_fresh(self, key: str) -> bool:
        """True if cache entry exists and has not expired."""
        return self.get(key) is not None

    # ── Change-detection helpers ────────────────────────────────────────

    def get_product_modified_map(self, site_key: str) -> dict:
        """
        Return {product_id: date_modified_str} dict from last scan.
        Returns {} if never scanned or cache expired.
        """
        key = f"scan_modified_{site_key}"
        result = self.get(key)
        return result if isinstance(result, dict) else {}

    def save_product_modified_map(self, site_key: str, modified_map: dict) -> None:
        """
        Save {product_id: date_modified} after a full scan.
        Used on next scan to skip unchanged products.
        """
        key = f"scan_modified_{site_key}"
        self.set(key, modified_map, ttl=TTL_SCAN_STATE)

    # ── Cache stats ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return cache stats: total files, total size, expired count."""
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files if f.exists())
        expired = 0
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    entry = json.load(fp)
                if now_ist_str() > entry.get("expires_at", "9999"):
                    expired += 1
            except Exception:
                pass
        return {
            "total_entries": len(files),
            "expired_entries": expired,
            "total_size_kb": round(total_size / 1024, 1),
            "cache_dir": str(self.cache_dir),
        }

    def cleanup_expired(self) -> int:
        """Delete all expired cache entries. Returns count deleted."""
        deleted = 0
        for f in list(self.cache_dir.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    entry = json.load(fp)
                if now_ist_str() > entry.get("expires_at", "9999"):
                    f.unlink(missing_ok=True)
                    deleted += 1
            except Exception:
                f.unlink(missing_ok=True)
                deleted += 1
        return deleted


# Module-level singleton
cache = CacheManager()
