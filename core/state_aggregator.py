"""
Falcon Agency — Unified Client State Aggregator (GAP 2)
========================================================
One function to know EVERYTHING about current state.
Director calls this to answer "Meri website ka kya haal hai?" with REAL data.

No storage rebuild — aggregates from existing scattered sources.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.director import Director
    from core.integration_bridge import IntegrationBridge

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "falcon.db"


def get_client_state_summary(
    site_id: str = "falconherbs.com",
    director: Optional["Director"] = None,
    bridge: Optional["IntegrationBridge"] = None,
) -> Dict[str, Any]:
    """
    Director calls this to know EVERYTHING about current state.
    One function. Real data. No hallucination.

    Parameters
    ----------
    site_id : str
        Site domain (e.g. falconherbs.com)
    director : Director | None
        If provided, includes running_now and live budget
    bridge : IntegrationBridge | None
        If provided, includes revenue, content, rewrite status from live tools

    Returns
    -------
    dict
        Unified state summary for DirectorBrain context.
    """
    state: Dict[str, Any] = {
        "north_star": _get_north_star(),
        "website_health": _load_latest_health_audit(),
        "last_backup": _get_last_backup_status(site_id),
        "revenue_today": _get_today_revenue(bridge),
        "revenue_monthly": _get_monthly_revenue(bridge),
        "pending_tasks": _get_pending_goals(),
        "running_now": _get_current_agent_activity(director),
        "budget_remaining": _get_budget_status(director),
        "content_status": _get_content_pipeline_status(bridge),
        "rewrite_status": _get_rewrite_status(bridge),
        "security_status": _get_latest_security_scan(),
        "last_owner_message": _get_last_interaction(),
        "schedule_summary": _get_schedule_summary(),
        "serper_usage": _get_serper_usage(),
        "agent_performance": _get_agent_performance(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return state


def format_for_director_context(state: Dict[str, Any]) -> str:
    """Format state dict into readable text for DirectorBrain injection."""
    lines = ["=== CLIENT STATE (use for 'website ka kya haal hai' questions) ===", ""]

    # North-star goal
    ns = state.get("north_star") or {}
    if ns.get("primary_goal"):
        lines.append(f"North-star: {ns['primary_goal']}")
    lines.append("")

    # Website health
    health = state.get("website_health") or {}
    if health:
        total = health.get("total_products", 0)
        clean = health.get("clean", 0)
        report = health.get("report", {})
        pf = len(report.get("products_fixable", []))
        tf = len(report.get("titles_fixable", []))
        ba = len(report.get("blogs_advisory", []))
        pa = len(report.get("pages_advisory", []))
        ca = len(report.get("categories_advisory", []))
        lines.append(f"Health: {total} products | {clean} clean | {pf} desc + {tf} title violations | {ba} blogs, {pa} pages, {ca} cats")
    else:
        lines.append("Health: No audit data (run 'health scan')")
    lines.append("")

    # Backup
    backup = state.get("last_backup") or {}
    if backup.get("last_backup"):
        age = backup.get("last_backup_age_hours", "?")
        status = backup.get("status", "?")
        lines.append(f"Backup: Last {age}h ago | Status: {status}")
    else:
        lines.append("Backup: No backups found")
    lines.append("")

    # Revenue
    rev_today = state.get("revenue_today") or {}
    rev_month = state.get("revenue_monthly") or {}
    if rev_today or rev_month:
        today_val = rev_today.get("total", 0) or rev_today.get("revenue", 0)
        month_val = rev_month.get("revenue", 0) or rev_month.get("total", 0)
        lines.append(f"Revenue: Today Rs {today_val:,.0f} | Month Rs {month_val:,.0f}")
    else:
        lines.append("Revenue: No data (sync WooCommerce)")
    lines.append("")

    # Pending / running
    pending = state.get("pending_tasks") or []
    running = state.get("running_now") or {}
    lines.append(f"Goals: {len(pending)} pending")
    if running.get("task"):
        lines.append(f"Running now: {running.get('task')} on {running.get('site', '')}")
    lines.append("")

    # Budget
    budget = state.get("budget_remaining") or {}
    daily = budget.get("daily_total", 0)
    monthly = budget.get("monthly_total", 0)
    daily_lim = budget.get("daily_limit", 10)
    monthly_lim = budget.get("monthly_limit", 150)
    lines.append(f"Budget: ${daily:.2f}/${daily_lim} today | ${monthly:.2f}/${monthly_lim} month")
    lines.append("")

    # Content
    content = state.get("content_status")
    if content and isinstance(content, str):
        lines.append(f"Content: {content[:200]}...")
    elif content:
        lines.append(f"Content: {content}")
    else:
        lines.append("Content: (check content status)")
    lines.append("")

    # Rewrite
    rw = state.get("rewrite_status")
    if rw and isinstance(rw, str):
        lines.append(f"Rewrites: {rw[:150]}")
    lines.append("")

    # Security
    sec = state.get("security_status")
    if sec:
        lines.append(f"Security: {sec}")
    lines.append("")

    # Serper (Google search API)
    serper = state.get("serper_usage")
    if serper:
        lines.append(f"Serper: {serper.get('used', 0)}/{serper.get('limit', 2500)} this month")
    lines.append("")

    # Agent performance (Director uses to assign work)
    perf = state.get("agent_performance") or {}
    if perf.get("agents"):
        busy = sorted(perf.get("agents", {}).items(), key=lambda x: x[1].get("total", 0), reverse=True)[:5]
        lines.append("Agent workload (7d): " + ", ".join(f"{a}:{s['total']}" for a, s in busy))
    if perf.get("idle"):
        lines.append("Idle: " + ", ".join(perf["idle"][:5]))
    lines.append("")

    # Last message
    last_msg = state.get("last_owner_message")
    if last_msg:
        lines.append(f"Last owner message: {last_msg[:80]}...")
    lines.append("==========================================")
    return "\n".join(lines)


# ─── Loaders (each reads from actual storage) ───────────────────────────────

def _load_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _load_latest_health_audit() -> Optional[Dict]:
    """From data/health_audit/health_audit_report.json"""
    path = DATA_DIR / "health_audit" / "health_audit_report.json"
    data = _load_json(path)
    if not data:
        return None
    # Normalize: integration_bridge format vs scanner format
    if "total_products" in data:
        return data
    if "summary" in data:
        return {
            "total_products": data.get("product_pages_scanned", 0),
            "clean": 0,
            "report": {},
            "summary": data.get("summary", {}),
        }
    return data


def _get_last_backup_status(site_id: str) -> Dict:
    """From data/backups/backup_registry.json"""
    path = DATA_DIR / "backups" / "backup_registry.json"
    data = _load_json(path, [])
    if not isinstance(data, list):
        return {"last_backup": None, "status": "unknown"}

    site_backups = [b for b in data if b.get("site") == site_id]
    site_backups.sort(key=lambda b: b.get("timestamp", ""), reverse=True)

    if not site_backups:
        return {"last_backup": None, "status": "critical", "status_reason": "No backups"}

    latest = site_backups[0]
    ts = latest.get("timestamp", "")
    age_hours = None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 1)
    except Exception:
        pass

    return {
        "last_backup": ts,
        "last_backup_age_hours": age_hours,
        "last_backup_verified": latest.get("verified", False),
        "total_backups": len(site_backups),
        "status": "healthy" if age_hours and age_hours < 25 else "warning",
    }


def _get_today_revenue(bridge: Optional["IntegrationBridge"]) -> Dict:
    """From RevenueTracker or data/revenue"""
    if bridge:
        try:
            rev = bridge.get_revenue_report()
            if rev.get("success") and rev.get("data"):
                d = rev["data"]
                return {"total": d.get("revenue", 0), "month": d.get("month", "")}
        except Exception:
            pass

    path = DATA_DIR / "revenue" / "revenue_log.json"
    data = _load_json(path, {"entries": []})
    if not data:
        return {}
    today = datetime.now().strftime("%Y-%m-%d")
    entries = data.get("entries", [])
    today_total = sum(e.get("amount", 0) for e in entries if str(e.get("date", ""))[:10] == today)
    return {"total": today_total, "entries_today": len([e for e in entries if str(e.get("date", ""))[:10] == today])}


def _get_monthly_revenue(bridge: Optional["IntegrationBridge"]) -> Dict:
    if bridge:
        try:
            rev = bridge.get_revenue_report()
            if rev.get("success") and rev.get("data"):
                return rev["data"]
        except Exception:
            pass

    try:
        from core.revenue_tracker import RevenueTracker
        rt = RevenueTracker()
        return rt.get_monthly_summary() or {}
    except Exception:
        return {}


def _get_pending_goals() -> List[Dict]:
    """From data/goals.json — handles list OR dict with 'goals' key."""
    path = DATA_DIR / "goals.json"
    data = _load_json(path, [])
    goals_list: List[Dict] = []
    if isinstance(data, list):
        goals_list = data
    elif isinstance(data, dict):
        goals_list = data.get("goals", data.get("tasks", [])) or []
    return [g for g in goals_list if isinstance(g, dict) and g.get("status") == "pending"]


def _get_current_agent_activity(director: Optional["Director"]) -> Dict:
    if director is None:
        return {}
    return {
        "task": getattr(director, "_current_task", None),
        "site": getattr(director, "_current_site", None),
    }


def _get_budget_status(director: Optional["Director"]) -> Dict:
    if director and hasattr(director, "_load_spend"):
        try:
            return director._load_spend()
        except Exception:
            pass
    return _load_json(DATA_DIR / "spend.json", {})


def _get_content_pipeline_status(bridge: Optional["IntegrationBridge"]) -> Optional[str]:
    if bridge:
        try:
            return bridge.get_content_queue_status()
        except Exception:
            pass

    path = DATA_DIR / "content" / "content_queue.json"
    data = _load_json(path, {})
    queue = data.get("queue", [])
    stats = data.get("stats", {})
    if not queue:
        return "Queue empty"
    return f"{len(queue)} items | generated: {stats.get('total_generated', 0)} | published: {stats.get('total_published', 0)}"


def _get_rewrite_status(bridge: Optional["IntegrationBridge"]) -> Optional[str]:
    if bridge:
        try:
            return bridge.get_rewrite_status()
        except Exception:
            pass

    path = DATA_DIR / "content" / "product_rewrites" / "last_scan.json"
    data = _load_json(path, {})
    if not data:
        return None
    pending = len(data.get("products_fixable", [])) if isinstance(data.get("products_fixable"), list) else 0
    return f"{pending} pending product rewrites" if pending else "No pending rewrites"


def _get_latest_security_scan() -> Optional[str]:
    """From SQLite action_log — last security_scan"""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT timestamp, status, details FROM action_log "
            "WHERE action LIKE '%security%' OR action LIKE '%scan%' "
            "ORDER BY timestamp DESC LIMIT 1",
        ).fetchone()
        conn.close()
        if row:
            return f"Last scan: {row[0]} | {row[1]}"
    except Exception:
        pass
    return None


def _get_last_interaction() -> Optional[str]:
    """From memory — last owner message"""
    try:
        from core.memory import memory
        history = memory.get_history("owner", last_n=5)
        for m in reversed(history):
            if m.get("role") == "user":
                return (m.get("content") or "")[:200]
    except Exception:
        pass
    return None


def _get_schedule_summary() -> Optional[str]:
    """Next due tasks from extended_schedule"""
    path = DATA_DIR / "extended_schedule.json"
    data = _load_json(path, {})
    tasks = data.get("tasks", {})
    if not tasks:
        return None
    due = []
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    for name, cfg in tasks.items():
        if not cfg.get("enabled", True):
            continue
        last = cfg.get("last_run")
        if not last or not last.startswith(today):
            due.append(name)
    return f"Due today: {', '.join(due[:5])}" if due else "All caught up"


def _get_serper_usage() -> Optional[Dict[str, Any]]:
    """Serper API usage this month (2500 free)."""
    try:
        from core.serper_client import get_serper_usage
        return get_serper_usage()
    except Exception:
        return None


def _get_agent_performance() -> Optional[Dict[str, Any]]:
    """Agent performance — who's busy, who's idle (for Director)."""
    try:
        from core.agent_performance import get_agent_performance
        return get_agent_performance(days=7)
    except Exception:
        return None


def _get_north_star() -> Optional[Dict[str, Any]]:
    """North-star goal — world #1."""
    try:
        path = DATA_DIR / ".." / "config" / "north_star.json"
        path = path.resolve()
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None
