"""
Falcon Agency — Centralized Serper.dev Client (v2)
===================================================
Dual-key rotation + DuckDuckGo fallback.

Search priority:
  1. SERPER_API_KEY   (key 1 — primary)
  2. SERPER_API_KEY_2 (key 2 — rotates when key1 quota low)
  3. DuckDuckGo       (free, unlimited, no API key needed)

Monthly quota: 2500/key → 5000 combined.
Usage tracked per key in data/serper_usage.json.
Auto-rotates to key2 when key1 < 200 remaining.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SERPER_LIMIT_MONTHLY = 2500          # per key
ROTATION_THRESHOLD   = 200           # switch to key2 when key1 < this
USAGE_FILE = Path("data/serper_usage.json")


# ── Usage tracking ──────────────────────────────────────────────────────────

def _load_usage() -> dict:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"month": None, "key1": {"count": 0}, "key2": {"count": 0}, "calls": []}


def _save_usage(data: dict):
    calls = data.get("calls", [])[-100:]
    data["calls"] = calls
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _month_key() -> str:
    return datetime.now().strftime("%Y-%m")


def _ensure_month(data: dict) -> dict:
    month = _month_key()
    if data.get("month") != month:
        data = {
            "month": month,
            "key1": {"count": 0},
            "key2": {"count": 0},
            "calls": [],
        }
    return data


def get_serper_usage() -> dict:
    """Return combined usage for both keys."""
    data = _ensure_month(_load_usage())
    k1   = data["key1"]["count"]
    k2   = data["key2"]["count"]
    return {
        "month":       data["month"],
        "key1_used":   k1,
        "key1_remain": max(0, SERPER_LIMIT_MONTHLY - k1),
        "key2_used":   k2,
        "key2_remain": max(0, SERPER_LIMIT_MONTHLY - k2),
        "total_used":  k1 + k2,
        "total_limit": SERPER_LIMIT_MONTHLY * 2,
        "total_remain": max(0, SERPER_LIMIT_MONTHLY - k1) + max(0, SERPER_LIMIT_MONTHLY - k2),
    }


# ── Key selection ────────────────────────────────────────────────────────────

def _get_active_key() -> tuple[str, str]:
    """
    Pick which Serper key to use.
    Returns (api_key, slot_name) where slot_name is 'key1' or 'key2'.
    Prefers key1; switches to key2 when key1 < ROTATION_THRESHOLD remaining.
    """
    key1 = os.getenv("SERPER_API_KEY", "").strip()
    key2 = os.getenv("SERPER_API_KEY_2", "").strip()

    if not key1 and not key2:
        return "", ""

    if not key1:
        return key2, "key2"
    if not key2:
        return key1, "key1"

    # Both available — check usage
    data  = _ensure_month(_load_usage())
    k1_used = data["key1"].get("count", 0)
    k1_left = SERPER_LIMIT_MONTHLY - k1_used

    # If key1 is running low, use key2
    if k1_left < ROTATION_THRESHOLD:
        k2_used = data["key2"].get("count", 0)
        k2_left = SERPER_LIMIT_MONTHLY - k2_used
        if k2_left > 0:
            return key2, "key2"

    if k1_left > 0:
        return key1, "key1"

    # Both exhausted — DDG fallback (caller handles)
    return "", ""


# ── DuckDuckGo fallback ─────────────────────────────────────────────────────

def _search_duckduckgo(query: str) -> dict:
    """
    DuckDuckGo fallback — free, no API key, unlimited.
    Returns dict shaped like Serper response so callers need no changes.
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="in-en", max_results=10))
        organic = [
            {
                "title":   r.get("title", ""),
                "link":    r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
        return {"organic": organic, "_source": "duckduckgo"}
    except ImportError:
        return {}
    except Exception:
        return {}


# ── Core search ──────────────────────────────────────────────────────────────

def search(query: str, source: str = "unknown") -> dict:
    """
    Run Google search via Serper (dual-key) → DuckDuckGo fallback.

    Priority:
      SERPER_API_KEY  (key1, primary)
      SERPER_API_KEY_2 (key2, auto-rotates when key1 < 200 left)
      DuckDuckGo      (free fallback, unlimited)

    Parameters
    ----------
    query  : str  — Search query
    source : str  — Caller ID for usage tracking (e.g. "aeo", "trending")

    Returns
    -------
    dict with "organic", "peopleAlsoAsk", "answerBox" etc.
    Includes "_source": "serper_key1" | "serper_key2" | "duckduckgo"
    """
    api_key, slot = _get_active_key()

    if api_key:
        try:
            import requests as _req
            r = _req.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "gl": "in", "hl": "en"},
                timeout=12,
            )
            if r.status_code == 200:
                # Track usage for this key
                data = _ensure_month(_load_usage())
                data[slot]["count"] = data[slot].get("count", 0) + 1
                data.setdefault("calls", []).append({
                    "ts":     datetime.now().isoformat(),
                    "source": source,
                    "query":  query[:80],
                    "key":    slot,
                })
                _save_usage(data)

                result = r.json()
                result["_source"] = f"serper_{slot}"
                return result

            # 429 quota exceeded → try other key
            if r.status_code == 429:
                # Mark this key as exhausted for the session
                other_key = os.getenv("SERPER_API_KEY_2" if slot == "key1" else "SERPER_API_KEY", "").strip()
                other_slot = "key2" if slot == "key1" else "key1"
                if other_key:
                    r2 = _req.post(
                        "https://google.serper.dev/search",
                        headers={"X-API-KEY": other_key, "Content-Type": "application/json"},
                        json={"q": query, "gl": "in", "hl": "en"},
                        timeout=12,
                    )
                    if r2.status_code == 200:
                        data = _ensure_month(_load_usage())
                        data[other_slot]["count"] = data[other_slot].get("count", 0) + 1
                        _save_usage(data)
                        result = r2.json()
                        result["_source"] = f"serper_{other_slot}_429rescue"
                        return result
            # Other non-200 → fall through to DDG

        except Exception:
            pass

    # Final fallback: DuckDuckGo
    return _search_duckduckgo(query)


def search_text(query: str, source: str = "unknown") -> str:
    """Search and return formatted text for Commander/QA."""
    data = search(query, source)
    if not data:
        return ""
    parts = []
    for i, o in enumerate(data.get("organic", [])[:8], 1):
        parts.append(f"{i}. {o.get('title', '')}\n   {o.get('snippet', '')}")
    for p in data.get("peopleAlsoAsk", [])[:3]:
        parts.append(f"PAA: {p.get('question', '')}\n   {p.get('snippet', '')}")
    ab = data.get("answerBox", {})
    if ab:
        parts.append(f"Featured: {ab.get('title', '')}\n   {ab.get('snippet', '')}")
    return "\n\n".join(parts) if parts else ""


def can_search() -> bool:
    """True if any Serper key has remaining quota."""
    key1 = os.getenv("SERPER_API_KEY", "").strip()
    key2 = os.getenv("SERPER_API_KEY_2", "").strip()
    if not key1 and not key2:
        return False
    u = get_serper_usage()
    return u["total_remain"] > 0


def search_available() -> bool:
    """True if ANY search method is available (Serper OR DuckDuckGo)."""
    if can_search():
        return True
    try:
        from duckduckgo_search import DDGS  # noqa
        return True
    except ImportError:
        return False
