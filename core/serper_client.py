"""
Falcon Agency — Centralized Serper.dev Client
==============================================
Single source for Google search via Serper API.
Tracks usage to maximize 2500/month free quota.
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


def search(query: str, source: str = "unknown") -> dict:
    """
    Run Serper search. Tracks usage.
    Returns raw Serper response or {} on failure.
    source: caller id for tracking (e.g. "commander", "aeo", "trending_scan")
    """
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        return {}

    try:
        import requests as _req
        r = _req.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "gl": "in", "hl": "en"},
            timeout=12,
        )
        if r.status_code != 200:
            return {}

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

        return r.json()
    except Exception:
        return {}


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
    """True if we have API key and remaining quota."""
    if not os.getenv("SERPER_API_KEY"):
        return False
    u = get_serper_usage()
    return u["remaining"] > 0
