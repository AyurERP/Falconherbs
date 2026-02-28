"""
Falcon Agency — Agent Performance Tracker
==========================================
Who's performing, who's idle. Full transparency for the boss.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

DB_PATH = Path("data/falcon.db")


def get_agent_performance(days: int = 7) -> Dict[str, Any]:
    """
    Returns performance report: tasks per agent, success/fail, idle agents.
    Used by Director to know who needs more work.
    """
    if not DB_PATH.exists():
        return {"agents": {}, "idle": [], "failures": [], "period_days": days}

    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_PATH)

    # Count by agent
    rows = conn.execute(
        """
        SELECT agent, status, COUNT(*) as cnt
        FROM action_log
        WHERE timestamp >= ?
        GROUP BY agent, status
        """,
        (since,),
    ).fetchall()

    # Aggregate
    by_agent: Dict[str, Dict] = {}
    for agent, status, cnt in rows:
        if agent not in by_agent:
            by_agent[agent] = {"total": 0, "success": 0, "failed": 0, "last_action": None}
        by_agent[agent]["total"] += cnt
        if status.lower() in ("success", "ok", "complete", "done"):
            by_agent[agent]["success"] += cnt
        else:
            by_agent[agent]["failed"] += cnt

    # Last action per agent
    last_rows = conn.execute(
        """
        SELECT agent, MAX(timestamp) FROM action_log
        WHERE timestamp >= ?
        GROUP BY agent
        """,
        (since,),
    ).fetchall()
    for agent, ts in last_rows:
        if agent in by_agent:
            by_agent[agent]["last_action"] = ts

    # Recent failures (for Director report)
    fail_rows = conn.execute(
        """
        SELECT agent, action, status, timestamp, details
        FROM action_log
        WHERE timestamp >= ? AND LOWER(status) NOT IN ('success','ok','complete','done')
        ORDER BY id DESC LIMIT 20
        """,
        (since,),
    ).fetchall()

    failures = [
        {"agent": r[0], "action": r[1], "status": r[2], "timestamp": r[3], "details": r[4]}
        for r in fail_rows
    ]

    conn.close()

    # Known agents — who we expect to work
    known_agents = [
        "commander", "developer", "strategist", "media", "backup",
        "sentinel", "aeo", "health_scanner", "content_pipeline",
        "woocommerce", "integration_bridge", "system",
    ]
    idle = [a for a in known_agents if by_agent.get(a, {}).get("total", 0) == 0]

    return {
        "agents": by_agent,
        "idle": idle,
        "failures": failures,
        "period_days": days,
        "total_tasks": sum(a.get("total", 0) for a in by_agent.values()),
    }


def format_performance_report(days: int = 7) -> str:
    """WhatsApp-ready agent performance report."""
    data = get_agent_performance(days)
    lines = [
        "📊 *AGENT PERFORMANCE REPORT*",
        f"Period: Last {days} days",
        "─" * 28,
        "",
    ]

    # Sort by total (busiest first)
    agents = data.get("agents", {})
    sorted_agents = sorted(
        agents.items(),
        key=lambda x: x[1].get("total", 0),
        reverse=True,
    )

    for agent, stats in sorted_agents:
        total = stats.get("total", 0)
        success = stats.get("success", 0)
        failed = stats.get("failed", 0)
        last = stats.get("last_action", "never")[:16] if stats.get("last_action") else "never"
        icon = "🟢" if failed == 0 else "🟡"
        lines.append(f"{icon} *{agent}*: {total} tasks | ✅{success} ❌{failed} | Last: {last}")

    idle = data.get("idle", [])
    if idle:
        lines.append("")
        lines.append("⚠️ *IDLE (no tasks):* " + ", ".join(idle))

    failures = data.get("failures", [])[:5]
    if failures:
        lines.append("")
        lines.append("❌ *RECENT FAILURES:*")
        for f in failures:
            lines.append(f"  • {f['agent']}: {f['action']} — {f['status']}")

    lines.append("")
    lines.append(f"Total tasks: {data.get('total_tasks', 0)}")
    lines.append("─" * 28)
    return "\n".join(lines)
