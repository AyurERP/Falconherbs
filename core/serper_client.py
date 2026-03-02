"""
Falcon Agency — Centralized Serper.dev Client
==============================================
Single source for Google search via Serper API.
Tracks usage to maximize 2500/month free quota.

Fallback: DuckDuckGo (free, no API key, no limit)
  → Automatically used when Serper quota is exhausted or key missing.
  → Results are slightly less structured but fully functional.
"""

import json
import os
from datetime import datetime
from pathlib import Path

SERPER_LIMIT_MONTHLY = 2500
USAGE_FILE = Path("data/serper_usage.json")


def _load_usage() -> dict:
    """Load usage from data/serper_usage.json"""
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"month": None, "count": 0, "calls": []}


def _save_usage(data: dict):
    """Persist usage. Keep last 100 call entries."""
    calls = data.get("calls", [])[-100:]
    data["calls"] = calls
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _month_key() -> str:
    return datetime.now().strftime("%Y-%m")


def get_serper_usage() -> dict:
    """Return current month usage: {used, limit, remaining, month}"""
    data = _load_usage()
    month = _month_key()
    if data.get("month") != month:
        data = {"month": month, "count": 0, "calls": []}
    return {
        "used": data.get("count", 0),
        "limit": SERPER_LIMIT_MONTHLY,
        "remaining": max(0, SERPER_LIMIT_MONTHLY - data.get("count", 0)),
        "month": month,
    }


def _search_duckduckgo(query: str) -> dict:
    """
    DuckDuckGo fallback search. Free, no API key, no limit.
    Returns a dict shaped like a minimal Serper response
    so callers don't need to change anything.
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="in-en", max_results=8))
        organic = [
            {
                "title": r.get("title", ""),
                "link": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
        return {"organic": organic, "_source": "duckduckgo"}
    except Exception:
        return {}


def search(query: str, source: str = "unknown") -> dict:
    """
    Run search. Tries Serper first; falls back to DuckDuckGo
    if Serper quota is exhausted or key is missing.
    Tracks Serper usage only (DDG is unlimited).

    Returns raw response or {} on total failure.
    source: caller id for tracking (e.g. "aeo", "weekly_trending")
    """
    api_key = os.getenv("SERPER_API_KEY", "")
    use_serper = bool(api_key) and can_search()

    if use_serper:
        try:
            import requests as _req
            r = _req.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "gl": "in", "hl": "en"},
                timeout=12,
            )
            if r.status_code == 200:
                # Track usage
                data = _load_usage()
                month = _month_key()
                if data.get("month") != month:
                    data = {"month": month, "count": 0, "calls": []}
                data["count"] = data.get("count", 0) + 1
                data.setdefault("calls", []).append({
                    "ts": datetime.now().isoformat(),
                    "source": source,
                    "query": query[:80],
                })
                _save_usage(data)
                result = r.json()
                result["_source"] = "serper"
                return result
            # Non-200 → fall through to DDG
        except Exception:
            pass

    # Fallback: DuckDuckGo
    return _search_duckduckgo(query)


def search_text(query: str, source: str = "unknown") -> str:
    """
    Search and return formatted text (organic + PAA + answer box).
    For Commander / question answering.
    """
    data = search(query, source)
    if not data:
        return ""
    parts = []
    for i, o in enumerate(data.get("organic", [])[:8], 1):
        parts.append(f"{i}. {o.get('title','')}\n   {o.get('snippet','')}")
    for p in data.get("peopleAlsoAsk", [])[:3]:
        parts.append(f"PAA: {p.get('question','')}\n   {p.get('snippet','')}")
    ab = data.get("answerBox", {})
    if ab:
        parts.append(f"Featured: {ab.get('title','')}\n   {ab.get('snippet','')}")
    return "\n\n".join(parts) if parts else ""


def can_search() -> bool:
    """True if Serper has remaining quota. DDG always available."""
    if not os.getenv("SERPER_API_KEY"):
        return False
    u = get_serper_usage()
    return u["remaining"] > 0


def search_available() -> bool:
    """True if ANY search is available (Serper OR DuckDuckGo)."""
    try:
        from duckduckgo_search import DDGS  # noqa
        return True
    except ImportError:
        pass
    return can_search()
