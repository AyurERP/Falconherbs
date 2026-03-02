"""
core/autopilot.py — Falcon Agency Auto-Pilot Intelligence
==========================================================

The AutoPilot makes the Director genuinely proactive — it
thinks every minute and decides what to do WITHOUT being asked.

How it works:
  Director calls autopilot.tick(director) every 60s loop.
  AutoPilot checks conditions and injects goals to Director's queue.

Rules (safe by design):
  • Never runs the same proactive check twice within its cooldown window
  • Never fires more than 3 auto-goals per hour (flood protection)
  • All actions still go through Director's budget gate + approval gate
  • Read-only checks (ping, revenue read) run freely
  • Write actions (email, rewrite push) always need approval

Proactive triggers:
  1. Revenue drought    — no orders for 48h → suggest winback / promo
  2. Zero-day Tuesday   — Tuesday morning no action → inject growth scan
  3. Content gap        — no blog in 14 days → queue blog idea
  4. Rewrite backlog    — >10 rewrites pending → WhatsApp nudge
  5. Site slow          — response > 5s → alert owner
  6. Write queue firing — near 2 AM IST → remind of pending writes
  7. Weekly digest      — Monday 7 AM IST → auto-trigger weekly report
  8. SSL proximity      — (future: when SSL check integrated)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.logger import log
from core.ist_time import now_ist, today_ist, is_write_window, minutes_until_write_window

if TYPE_CHECKING:
    pass  # avoid circular import — Director passed at runtime

DATA_DIR = Path(__file__).parent.parent / "data"
_STATE_FILE = DATA_DIR / "cache" / "autopilot_state.json"

# Max auto-goals injected per hour (flood protection)
_MAX_AUTO_GOALS_PER_HOUR = 3

# Cooldown between same trigger firing again (seconds)
_COOLDOWNS: Dict[str, int] = {
    "revenue_drought":    6 * 3600,   # 6h
    "tuesday_growth":     7 * 24 * 3600,  # 7d (once a week)
    "content_gap":        24 * 3600,  # 24h
    "rewrite_backlog":    4 * 3600,   # 4h
    "site_slow":          30 * 60,    # 30min
    "write_window_nudge": 24 * 3600,  # 24h
    "weekly_digest":      7 * 24 * 3600,  # 7d
}


class AutoPilot:
    """
    Proactive intelligence layer for Falcon Agency Director.

    Usage in Director main loop:
        from core.autopilot import autopilot
        ...
        # Inside Director._run_idle_monitoring() or main loop:
        autopilot.tick(director=self)
    """

    def __init__(self) -> None:
        self._state: Dict[str, Any] = {}
        self._goals_this_hour: List[float] = []  # timestamps of auto-goals
        self._load_state()

    # ── Public API ──────────────────────────────────────────────────────────

    def tick(self, director=None) -> List[Dict]:
        """
        Called every Director cycle. Evaluates all proactive triggers.
        Returns list of goals injected this tick (for logging).

        director: Director instance (optional — enables goal injection)
        """
        injected = []
        now = now_ist()

        # Flood protection — max 3 auto-goals/hour
        hour_ago = now.timestamp() - 3600
        self._goals_this_hour = [t for t in self._goals_this_hour if t > hour_ago]
        if len(self._goals_this_hour) >= _MAX_AUTO_GOALS_PER_HOUR:
            log.info("AutoPilot: flood gate active (%d goals/hr)", len(self._goals_this_hour))
            return []

        triggers = [
            self._check_revenue_drought,
            self._check_tuesday_growth_scan,
            self._check_content_gap,
            self._check_rewrite_backlog,
            self._check_site_slow,
            self._check_write_window_nudge,
            self._check_weekly_digest,
        ]

        for trigger_fn in triggers:
            if len(self._goals_this_hour) >= _MAX_AUTO_GOALS_PER_HOUR:
                break
            try:
                result = trigger_fn(now=now, director=director)
                if result:
                    injected.append(result)
                    if director:
                        self._inject_goal(director, result)
                    self._goals_this_hour.append(now.timestamp())
            except Exception as exc:
                log.info("AutoPilot trigger %s failed: %s", trigger_fn.__name__, exc)

        if injected:
            self._save_state()
            log.info("AutoPilot: %d proactive goal(s) injected", len(injected))

        return injected

    def get_status(self) -> Dict:
        """Return current auto-pilot status for WhatsApp/dashboard."""
        now = now_ist()
        hour_ago = now.timestamp() - 3600
        recent = [t for t in self._goals_this_hour if t > hour_ago]
        last_fires = {}
        for trigger, ts in self._state.get("last_fired", {}).items():
            try:
                ago = int((now.timestamp() - ts) / 60)
                last_fires[trigger] = f"{ago}m ago"
            except Exception:
                pass
        return {
            "auto_goals_this_hour": len(recent),
            "max_per_hour": _MAX_AUTO_GOALS_PER_HOUR,
            "last_fired": last_fires,
            "write_window_open": is_write_window(),
            "mins_until_write_window": minutes_until_write_window(),
        }

    # ── Proactive Triggers ──────────────────────────────────────────────────

    def _check_revenue_drought(self, now: datetime, director=None) -> Optional[Dict]:
        """
        No orders for 48h → suggest owner to run winback or promo.
        Reads revenue_tracker data — never makes API call.
        """
        if not self._cooldown_ok("revenue_drought", now):
            return None

        try:
            rev_file = DATA_DIR / "revenue" / "daily_revenue.json"
            if not rev_file.exists():
                return None

            data = json.loads(rev_file.read_text())
            records = data if isinstance(data, list) else data.get("records", [])
            if not records:
                return None

            # Sort by date desc
            records = sorted(records, key=lambda r: r.get("date", ""), reverse=True)
            # Check last 2 days
            today = today_ist()
            from datetime import timedelta
            yesterday = (datetime.fromisoformat(today) - timedelta(days=1)).strftime("%Y-%m-%d")

            today_rev = next((r.get("revenue", 0) for r in records if r.get("date") == today), None)
            yesterday_rev = next((r.get("revenue", 0) for r in records if r.get("date") == yesterday), None)

            if today_rev == 0 and yesterday_rev == 0:
                self._mark_fired("revenue_drought", now)
                return {
                    "description": "Revenue drought: 0 orders for 48h. Run winback campaign or check site.",
                    "priority": 2,
                    "agent": "strategist",
                    "task": "analyse_sales",
                    "trigger": "autopilot:revenue_drought",
                    "auto": True,
                }
        except Exception as exc:
            log.info("AutoPilot revenue_drought check: %s", exc)
        return None

    def _check_tuesday_growth_scan(self, now: datetime, director=None) -> Optional[Dict]:
        """
        Tuesday 07:00-09:00 IST → inject weekly growth scan automatically.
        This is the most impactful day for planning the week.
        """
        if not self._cooldown_ok("tuesday_growth", now):
            return None

        is_tuesday = now.strftime("%A") == "Tuesday"
        is_morning = 7 <= now.hour < 9
        if not (is_tuesday and is_morning):
            return None

        self._mark_fired("tuesday_growth", now)
        return {
            "description": "Auto: Tuesday morning growth scan — analyse last week, plan this week.",
            "priority": 3,
            "agent": "strategist",
            "task": "run_analysis",
            "trigger": "autopilot:tuesday_growth",
            "auto": True,
        }

    def _check_content_gap(self, now: datetime, director=None) -> Optional[Dict]:
        """
        No blog published in 14 days → queue a blog idea generation task.
        Reads from data/content/ — no API call.
        """
        if not self._cooldown_ok("content_gap", now):
            return None

        try:
            content_dir = DATA_DIR / "content" / "blogs"
            if not content_dir.exists():
                return None

            published = [
                f for f in content_dir.glob("*.json")
                if json.loads(f.read_text()).get("status") == "published"
            ]
            if not published:
                cutoff_days = 14
            else:
                latest_ts = max(
                    json.loads(f.read_text()).get("published_at", "2000-01-01")
                    for f in published
                )
                days_since = (now - datetime.fromisoformat(latest_ts[:19])).days
                if days_since < 14:
                    return None
                cutoff_days = days_since

            self._mark_fired("content_gap", now)
            return {
                "description": f"Auto: No blog in {cutoff_days}d — generate fresh content ideas for falconherbs.com.",
                "priority": 5,
                "agent": "media",
                "task": "generate_content",
                "trigger": "autopilot:content_gap",
                "auto": True,
            }
        except Exception as exc:
            log.info("AutoPilot content_gap: %s", exc)
        return None

    def _check_rewrite_backlog(self, now: datetime, director=None) -> Optional[Dict]:
        """
        >10 product rewrites staged and pending approval → WhatsApp nudge.
        """
        if not self._cooldown_ok("rewrite_backlog", now):
            return None

        try:
            staging_file = DATA_DIR / "content" / "rewrite_staging.json"
            if not staging_file.exists():
                return None

            staging = json.loads(staging_file.read_text())
            pending = [
                r for r in (staging if isinstance(staging, list) else staging.get("rewrites", []))
                if r.get("status") == "staged"
            ]
            if len(pending) < 10:
                return None

            self._mark_fired("rewrite_backlog", now)
            return {
                "description": f"Auto: {len(pending)} product rewrites staged — owner approval needed.",
                "priority": 2,
                "agent": "director",           # Director handles WhatsApp nudge
                "task": "notify_pending_rewrites",
                "trigger": "autopilot:rewrite_backlog",
                "auto": True,
                "meta": {"pending_count": len(pending)},
            }
        except Exception as exc:
            log.info("AutoPilot rewrite_backlog: %s", exc)
        return None

    def _check_site_slow(self, now: datetime, director=None) -> Optional[Dict]:
        """
        Quick HTTP check — if site takes >5s, alert owner.
        Only runs every 30 min (cooldown).
        """
        if not self._cooldown_ok("site_slow", now):
            return None

        # Only check every 30th minute to be lightweight
        if now.minute % 30 != 0:
            return None

        try:
            import urllib.request as _urlreq
            site = os.getenv("WOO_SITE_URL", "https://falconherbs.com")
            t0 = time.time()
            _urlreq.urlopen(site, timeout=6)
            elapsed = time.time() - t0
            if elapsed < 5.0:
                return None  # Fast enough

            self._mark_fired("site_slow", now)
            return {
                "description": f"Auto: falconherbs.com slow ({elapsed:.1f}s response). Check server load.",
                "priority": 1,  # High priority
                "agent": "sentinel",
                "task": "uptime_check",
                "trigger": "autopilot:site_slow",
                "auto": True,
                "meta": {"response_ms": int(elapsed * 1000)},
            }
        except Exception:
            # Timeout = site down — mark as high priority
            if self._cooldown_ok("site_slow", now):
                self._mark_fired("site_slow", now)
                return {
                    "description": "Auto: falconherbs.com not responding — possible downtime.",
                    "priority": 1,
                    "agent": "sentinel",
                    "task": "uptime_check",
                    "trigger": "autopilot:site_down",
                    "auto": True,
                }
        return None

    def _check_write_window_nudge(self, now: datetime, director=None) -> Optional[Dict]:
        """
        At 01:50 IST (10 min before write window) — if queue has pending
        writes, log a reminder so Director knows to expect execution.
        """
        if not self._cooldown_ok("write_window_nudge", now):
            return None

        # Fire only at 01:50 IST
        if not (now.hour == 1 and now.minute >= 50):
            return None

        try:
            queue_file = DATA_DIR / "cache" / "write_queue.json"
            if not queue_file.exists():
                return None
            queue = json.loads(queue_file.read_text())
            pending = [x for x in queue if x.get("status") == "pending"]
            if not pending:
                return None

            self._mark_fired("write_window_nudge", now)
            return {
                "description": f"Auto: Write window opens in 10min — {len(pending)} WHM updates queued.",
                "priority": 3,
                "agent": "director",
                "task": "whm_write_queue",
                "trigger": "autopilot:write_window",
                "auto": True,
                "meta": {"pending_writes": len(pending)},
            }
        except Exception as exc:
            log.info("AutoPilot write_window_nudge: %s", exc)
        return None

    def _check_weekly_digest(self, now: datetime, director=None) -> Optional[Dict]:
        """
        Monday 07:00-08:00 IST → auto-trigger the full weekly report.
        """
        if not self._cooldown_ok("weekly_digest", now):
            return None

        is_monday = now.strftime("%A") == "Monday"
        is_morning = now.hour == 7
        if not (is_monday and is_morning):
            return None

        self._mark_fired("weekly_digest", now)
        return {
            "description": "Auto: Monday morning — generate full weekly performance digest.",
            "priority": 2,
            "agent": "strategist",
            "task": "run_analysis",
            "trigger": "autopilot:weekly_digest",
            "auto": True,
        }

    # ── Goal Injection ──────────────────────────────────────────────────────

    def _inject_goal(self, director, goal: Dict) -> None:
        """Add the auto-generated goal to Director's goals queue."""
        try:
            import uuid as _uuid
            goals = director.load_goals()
            new_goal = {
                "id": str(_uuid.uuid4())[:8],
                "description": goal["description"],
                "priority": goal.get("priority", 5),
                "status": "pending",
                "agent": goal.get("agent", ""),
                "task": goal.get("task", ""),
                "trigger": goal.get("trigger", "autopilot"),
                "auto": True,
                "created_at": now_ist().isoformat(),
                "meta": goal.get("meta", {}),
            }
            goals.append(new_goal)
            director.save_goals(goals)
            log.info("AutoPilot injected goal: %s", goal["description"][:60])
        except Exception as exc:
            log.warning("AutoPilot._inject_goal failed: %s", exc)

    # ── State persistence ────────────────────────────────────────────────────

    def _cooldown_ok(self, trigger: str, now: datetime) -> bool:
        """Return True if enough time has passed since trigger last fired."""
        last = self._state.get("last_fired", {}).get(trigger)
        if last is None:
            return True
        cooldown = _COOLDOWNS.get(trigger, 3600)
        return (now.timestamp() - last) >= cooldown

    def _mark_fired(self, trigger: str, now: datetime) -> None:
        """Record that trigger fired at this moment."""
        if "last_fired" not in self._state:
            self._state["last_fired"] = {}
        self._state["last_fired"][trigger] = now.timestamp()

    def _load_state(self) -> None:
        try:
            _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            if _STATE_FILE.exists():
                self._state = json.loads(_STATE_FILE.read_text())
        except Exception:
            self._state = {}

    def _save_state(self) -> None:
        try:
            _STATE_FILE.write_text(json.dumps(self._state, indent=2))
        except Exception as exc:
            log.info("AutoPilot state save failed: %s", exc)


# ── Singleton ──────────────────────────────────────────────────────────────────
autopilot = AutoPilot()
