"""
core/director.py — The Orchestrator Brain of Falcon Agency
============================================================

The Director is the always-running control loop that coordinates the
entire autonomous workforce.  It never does the work itself — it decides
WHAT needs doing, checks that it's SAFE and AFFORDABLE, and then wakes
up the appropriate agent to execute.

Execution Model
───────────────
    ┌──────────────────────────────────────────────────────────────┐
    │                     DIRECTOR MAIN LOOP                       │
    │                    (every 60 seconds)                         │
    │                                                              │
    │  ┌─────────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐ │
    │  │Heartbeat│──▶│ Schedule  │──▶│  Budget  │──▶│ Approval │ │
    │  │  Check  │   │  Check    │   │  Gate    │   │   Gate   │ │
    │  └─────────┘   └─────┬─────┘   └────┬─────┘   └────┬─────┘ │
    │                      │              │              │        │
    │                      ▼              ▼              ▼        │
    │               ┌─────────────────────────────────────┐      │
    │               │         AGENT DISPATCH              │      │
    │               │  sentinel · developer · strategist  │      │
    │               │           · media                   │      │
    │               └────────────────┬────────────────────┘      │
    │                                │                            │
    │                                ▼                            │
    │                     ┌─────────────────┐                    │
    │                     │   LOG + SAVE    │                    │
    │                     │  (SQLite + JSON)│                    │
    │                     └─────────────────┘                    │
    └──────────────────────────────────────────────────────────────┘

Safety Guarantees
─────────────────
    • Director NEVER crashes.  Every call is wrapped.
    • Budget limits are NON-NEGOTIABLE — $10/day, $150/month.
    • Sensitive actions REQUIRE human Telegram approval.
    • Every action, spend, and decision is logged to SQLite.
    • Graceful shutdown on SIGINT / SIGTERM with state persistence.

Project Location : F:/FALCON AGENCY
Python Version   : 3.11+
"""

from __future__ import annotations

import importlib
import json
import signal
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from config.keys import KeyVault
from config.settings import AgencySettings, IS_PRODUCTION
from config.safety import SafetyGuard
from core.logger import log
from core.approval import ApprovalSystem
from core.sentinel import Sentinel
from core.whatsapp import WhatsAppNotifier
from core.commander import FalconCommander
from core.webhook import FalconWebhook


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PATHS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent   # F:/FALCON AGENCY
DATA_DIR:     Path = PROJECT_ROOT / "data"
GOALS_FILE:   Path = DATA_DIR / "goals.json"
SCHEDULE_FILE: Path = DATA_DIR / "schedule.json"
SPEND_FILE:   Path = DATA_DIR / "spend.json"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HARD LIMITS — NON-NEGOTIABLE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DAILY_LIMIT:   float = 10.00    # USD — absolute ceiling per calendar day
MONTHLY_LIMIT: float = 150.00   # USD — absolute ceiling per calendar month


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TIMING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CYCLE_SECONDS: int          = 60     # main loop period
CYCLE_TIME_BUDGET: float    = 25.0   # max seconds of work per cycle
IDLE_ALERT_SECONDS: int     = 300    # 5 minutes → "Director idle" alert
MAX_TASKS_PER_CYCLE: int    = 10     # cap to avoid monopolising the loop
UPTIME_CHECK_TIMEOUT: int   = 5      # seconds for lightweight HEAD request


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TASK CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Which agent handles which scheduled task
TASK_AGENT_MAP: Dict[str, str] = {
    "security_scan":  "sentinel",
    "uptime_check":   "sentinel",
    "seo_audit":      "strategist",
}

# Estimated API cost per task (USD).  Zero = free (local HTTP only).
TASK_ESTIMATED_COST: Dict[str, float] = {
    "uptime_check":     0.00,
    "security_scan":    0.00,
    "seo_audit":        0.05,
    "content_update":   0.50,
    "code_deploy":      0.10,
    "media_generation": 0.30,
}

# Tasks that REQUIRE human Telegram approval before execution
SENSITIVE_TASKS: frozenset[str] = frozenset({
    "code_deploy",
    "file_write",
    "file_delete",
    "content_update",
    "database_modify",
    "config_change",
    "security_action",
    "ip_block",
})

# Keyword → agent mapping for goal inference
_GOAL_AGENT_KEYWORDS: Dict[str, List[str]] = {
    "sentinel":   ["security", "scan", "vulnerability", "uptime", "monitor",
                   "ssl", "firewall", "intrusion", "brute", "malware"],
    "developer":  ["code", "deploy", "develop", "fix", "update", "css",
                   "html", "javascript", "bug", "patch", "refactor", "build"],
    "strategist": ["seo", "ranking", "keyword", "strategy", "analytics",
                   "traffic", "serp", "backlink", "competitor", "audit"],
    "media":      ["content", "media", "image", "video", "photo", "design",
                   "social", "post", "graphic", "thumbnail", "copy"],
}

# Default schedule template for a new site
_DEFAULT_SITE_SCHEDULE: Dict[str, Dict[str, Any]] = {
    "security_scan": {"interval_minutes": 30,   "last_run": None},
    "seo_audit":     {"interval_minutes": 1440, "last_run": None},
    "uptime_check":  {"interval_minutes": 5,    "last_run": None},
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MODULE-LEVEL LOGGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Use shared FalconLogger singleton (same as approval, sentinel)
# FalconLogger does not accept a name argument; use global log


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    """ISO-8601 UTC timestamp for JSON serialisation."""
    return _utcnow().isoformat()


def _today_str() -> str:
    """Current UTC date as YYYY-MM-DD."""
    return _utcnow().strftime("%Y-%m-%d")


def _month_str() -> str:
    """Current UTC year-month as YYYY-MM."""
    return _utcnow().strftime("%Y-%m")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DIRECTOR CLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class Director:
    """
    The always-running orchestrator brain of Falcon Agency.

    Responsibilities:
        1. Goal Management     — load, prioritise, dispatch, track completion
        2. Task Scheduling     — timed scans, audits, uptime checks
        3. Agent Dispatch      — wake agents, never do the work itself
        4. Cost Governor       — hard daily/monthly USD limits
        5. Approval Gate       — Telegram approval for sensitive actions
        6. Heartbeat           — liveness signal every 60 s
        7. Graceful Shutdown   — save state, notify owner, exit clean

    Quick-start::

        from core.director import Director

        d = Director()
        d.run()           # blocks forever — Ctrl-C to stop
    """

    # ──────────────────────────────────────────────────────────────────────
    #  Initialisation
    # ──────────────────────────────────────────────────────────────────────

    def __init__(self) -> None:
        """
        Initialise the Director.

        Creates data directory and default JSON files if they don't exist,
        boots the approval channel and sentinel scanner, and installs
        signal handlers for graceful shutdown.
        """
        self._running: bool = False              # main-loop flag
        self._last_activity: float = time.monotonic()
        self._idle_alert_sent: bool = False       # prevent alert spam
        self._cycle_count: int = 0
        self._current_task: Optional[str] = None
        self._current_site: Optional[str] = None

        # ── Ensure data directory exists ──
        self._ensure_data_dir()

        # ── Boot subsystems (each is individually guarded) ──
        self._vault:    Optional[KeyVault]       = self._safe_init("KeyVault",       KeyVault)
        self._settings: Optional[AgencySettings] = self._safe_init("AgencySettings", AgencySettings)
        self._safety:   Optional[SafetyGuard]    = self._safe_init("SafetyGuard",    SafetyGuard)
        self._approval: Optional[ApprovalSystem] = self._safe_init("ApprovalSystem", ApprovalSystem)
        self._sentinel: Optional[Sentinel]       = self._init_sentinel()

        # ── WhatsApp + Commander + Webhook ──
        self._whatsapp: Optional[WhatsAppNotifier] = self._safe_init("WhatsAppNotifier", WhatsAppNotifier)
        self._commander: Optional[FalconCommander] = self._init_commander()
        self._webhook: Optional[FalconWebhook]     = self._init_webhook()

        # ── Ensure JSON state files ──
        self._ensure_goals_file()
        self._ensure_schedule_file()
        self._ensure_spend_file()

        # ── Signal handlers for graceful shutdown ──
        self._install_signal_handlers()

        log.info("━" * 60)
        log.info("FALCON AGENCY DIRECTOR — Initialised")
        log.info("  Project root : %s", PROJECT_ROOT)
        log.info("  Data dir     : %s", DATA_DIR)
        log.info("  Daily limit  : $%.2f", DAILY_LIMIT)
        log.info("  Monthly limit: $%.2f", MONTHLY_LIMIT)
        log.info("  Cycle        : %ds", CYCLE_SECONDS)
        log.info("  Production   : %s", IS_PRODUCTION)
        log.info("━" * 60)

    # ──────────────────────────────────────────────────────────────────────
    #  Safe subsystem initialisation helpers
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_init(name: str, cls: type) -> Any:
        """
        Attempt to instantiate *cls*.  On failure, log and return None.

        The Director must ALWAYS boot — a broken subsystem degrades
        capability but must never prevent startup.
        """
        try:
            instance = cls()
            log.info("  ✔ %s ready", name)
            return instance
        except Exception as exc:
            log.critical("  ✖ %s failed to init: %s", name, exc, exc_info=True)
            return None

    def _init_sentinel(self) -> Optional[Sentinel]:
        """Initialise Sentinel with the approval system (if available)."""
        try:
            if self._approval is not None:
                sentinel = Sentinel(self._approval)
            else:
                sentinel = Sentinel(ApprovalSystem())
            log.info("  ✔ Sentinel ready")
            return sentinel
        except Exception as exc:
            log.critical("  ✖ Sentinel failed to init: %s", exc, exc_info=True)
            return None

    def _init_commander(self) -> Optional[FalconCommander]:
        """Initialise FalconCommander with Director + WhatsApp."""
        try:
            if self._whatsapp is not None:
                commander = FalconCommander(self, self._whatsapp)
                log.info("  ✔ FalconCommander ready")
                return commander
            log.warning("  ⚠ FalconCommander skipped — WhatsApp unavailable")
            return None
        except Exception as exc:
            log.critical("  ✖ FalconCommander failed: %s", exc, exc_info=True)
            return None

    def _init_webhook(self) -> Optional[FalconWebhook]:
        """Initialise FalconWebhook."""
        try:
            if self._whatsapp is not None and self._commander is not None:
                webhook = FalconWebhook(self._whatsapp, self._commander)
                log.info("  ✔ FalconWebhook ready")
                return webhook
            log.warning("  ⚠ FalconWebhook skipped — dependencies unavailable")
            return None
        except Exception as exc:
            log.critical("  ✖ FalconWebhook failed: %s", exc, exc_info=True)
            return None

    # ══════════════════════════════════════════════════════════════════════
    #  DATA FILE MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _ensure_data_dir() -> None:
        """Create the data directory tree if absent."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.critical("Cannot create data dir %s: %s", DATA_DIR, exc)

    # ── Generic JSON read / write ──

    @staticmethod
    def _read_json(path: Path, default: Any = None) -> Any:
        """
        Read and parse a JSON file.

        Returns *default* (or ``None``) on any error — never raises.
        """
        try:
            if not path.exists():
                return default
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                return default
            return json.loads(text)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to read %s: %s — using default", path.name, exc)
            return default

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        """
        Atomically write *data* as formatted JSON.

        Writes to a ``.tmp`` sibling then replaces, preventing corruption
        if the process is killed mid-write.
        """
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(data, indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp_path.replace(path)     # atomic on same filesystem
        except OSError as exc:
            log.critical("Failed to write %s: %s", path.name, exc)
            # Clean up temp file if it still exists
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    # ── Default file creators ──

    def _ensure_goals_file(self) -> None:
        """Create data/goals.json with a seed goal if the file does not exist."""
        if GOALS_FILE.exists():
            return
        seed: list = [
            {
                "id": "goal-001",
                "site": "falconherbs.com",
                "description": "Run daily security scan",
                "priority": 1,
                "status": "pending",
                "created_at": _utcnow_iso(),
            },
        ]
        self._write_json(GOALS_FILE, seed)
        log.info("Created seed goals file: %s", GOALS_FILE)

    def _ensure_schedule_file(self) -> None:
        """Create data/schedule.json with a default site schedule if absent."""
        if SCHEDULE_FILE.exists():
            return
        default_schedule: Dict[str, Any] = {
            "falconherbs.com": {
                task: dict(cfg) for task, cfg in _DEFAULT_SITE_SCHEDULE.items()
            },
        }
        self._write_json(SCHEDULE_FILE, default_schedule)
        log.info("Created default schedule file: %s", SCHEDULE_FILE)

    def _ensure_spend_file(self) -> None:
        """Create data/spend.json with zeroed counters if absent."""
        if SPEND_FILE.exists():
            return
        self._write_json(SPEND_FILE, self._fresh_spend_record())
        log.info("Created spend tracking file: %s", SPEND_FILE)

    @staticmethod
    def _fresh_spend_record() -> Dict[str, Any]:
        """Return a zeroed-out spend record for today."""
        return {
            "date": _today_str(),
            "daily_total": 0.0,
            "monthly_total": 0.0,
            "daily_limit": DAILY_LIMIT,
            "monthly_limit": MONTHLY_LIMIT,
        }

    # ══════════════════════════════════════════════════════════════════════
    #  1.  GOAL MANAGEMENT
    # ══════════════════════════════════════════════════════════════════════

    def load_goals(self) -> list:
        """
        Load the goal list from ``data/goals.json``.

        Returns
        -------
        list[dict]
            List of goal dicts, or empty list on error / missing file.
        """
        try:
            data = self._read_json(GOALS_FILE, default=[])
            if not isinstance(data, list):
                log.warning("goals.json root is not a list — resetting to empty")
                return []
            return data
        except Exception as exc:
            log.critical("load_goals crashed: %s", exc, exc_info=True)
            return []

    def save_goals(self, goals: list) -> None:
        """
        Persist *goals* to ``data/goals.json``.

        Parameters
        ----------
        goals : list[dict]
            The full goal list to write.
        """
        try:
            self._write_json(GOALS_FILE, goals)
        except Exception as exc:
            log.critical("save_goals crashed: %s", exc, exc_info=True)

    def get_next_goal(self) -> Optional[dict]:
        """
        Return the highest-priority pending goal, or ``None``.

        Priority 1 is the most urgent.  Ties are broken by ``created_at``
        (earliest first).
        """
        try:
            goals = self.load_goals()
            pending = [g for g in goals if g.get("status") == "pending"]
            if not pending:
                return None
            # Sort: lowest priority number first, then earliest creation
            pending.sort(key=lambda g: (
                g.get("priority", 999),
                g.get("created_at", ""),
            ))
            return pending[0]
        except Exception as exc:
            log.critical("get_next_goal crashed: %s", exc, exc_info=True)
            return None

    def _update_goal_status(
        self,
        goal_id: str,
        new_status: str,
        *,
        result_summary: str = "",
    ) -> None:
        """
        Update the status of a goal in goals.json.

        Parameters
        ----------
        goal_id : str
            The ``id`` field of the goal.
        new_status : str
            One of ``"pending"``, ``"in_progress"``, ``"complete"``, ``"failed"``.
        result_summary : str, optional
            A short human-readable note appended to the goal.
        """
        try:
            goals = self.load_goals()
            for g in goals:
                if g.get("id") == goal_id:
                    g["status"] = new_status
                    g["updated_at"] = _utcnow_iso()
                    if result_summary:
                        g["result_summary"] = result_summary
                    break
            self.save_goals(goals)
            log.info("Goal %s → %s", goal_id, new_status)
        except Exception as exc:
            log.critical(
                "_update_goal_status crashed for %s: %s",
                goal_id, exc, exc_info=True,
            )

    def _infer_agent_for_goal(self, goal: dict) -> str:
        """
        Determine which agent should handle *goal* by keyword matching
        against the description.

        Returns
        -------
        str
            Agent name (``"sentinel"``, ``"developer"``, ``"strategist"``,
            ``"media"``) or ``"unknown"`` if no match.
        """
        desc = goal.get("description", "").lower()
        for agent, keywords in _GOAL_AGENT_KEYWORDS.items():
            if any(kw in desc for kw in keywords):
                return agent
        return "unknown"

    def _process_goal(self, goal: dict) -> None:
        """
        Take a pending goal through the full lifecycle:
        mark in_progress → infer agent → budget check → approval gate →
        dispatch → mark complete / failed.
        """
        goal_id: str = goal.get("id", "unknown")
        site: str = goal.get("site", "unknown")
        desc: str = goal.get("description", "")

        log.info(
            "Processing goal  |  id=%s  |  site=%s  |  desc='%s'",
            goal_id, site, desc[:80],
        )

        # Mark in_progress
        self._update_goal_status(goal_id, "in_progress")

        # Infer which agent handles this goal
        agent = self._infer_agent_for_goal(goal)
        if agent == "unknown":
            log.warning(
                "Cannot infer agent for goal %s — skipping", goal_id,
            )
            self._update_goal_status(
                goal_id, "failed",
                result_summary="No agent matched for this goal description",
            )
            return

        # Derive a task name from the description (simplified)
        task = self._derive_task_name(desc)

        # Budget check (use estimated cost for the task)
        estimated_cost = TASK_ESTIMATED_COST.get(task, 0.0)
        if estimated_cost > 0 and not self.check_budget(estimated_cost):
            self._update_goal_status(
                goal_id, "pending",   # back to pending — retry when budget allows
                result_summary="Deferred: daily/monthly budget exhausted",
            )
            return

        # Approval gate for sensitive tasks
        if self._is_sensitive(task):
            if not self._gate_approval(task, site, desc):
                self._update_goal_status(
                    goal_id, "pending",
                    result_summary="Deferred: human approval denied or timed out",
                )
                return

        # Dispatch
        try:
            result = self.dispatch_agent(
                agent=agent,
                task=task,
                site=site,
                params={"goal_id": goal_id, "description": desc},
            )
        except Exception as exc:
            log.critical("dispatch_agent threw in _process_goal: %s", exc, exc_info=True)
            result = {"status": "error", "error": str(exc)[:300]}

        # Log spend if applicable
        if estimated_cost > 0 and result.get("status") != "error":
            self.log_spend(estimated_cost, task, site)

        # Determine outcome
        status_val = result.get("status", "")
        if status_val in ("success", "up", "skipped") or "error" not in result:
            self._update_goal_status(
                goal_id, "complete",
                result_summary=str(result.get("message", "Completed"))[:500],
            )
        else:
            self._update_goal_status(
                goal_id, "failed",
                result_summary=str(result.get("error", result.get("message", "Failed")))[:500],
            )

    @staticmethod
    def _derive_task_name(description: str) -> str:
        """
        Best-effort mapping of a free-text goal description to a
        canonical task name.
        """
        desc = description.lower()
        mapping = [
            ("security_scan",    ["security scan", "vulnerability scan", "security check"]),
            ("uptime_check",     ["uptime", "availability"]),
            ("seo_audit",        ["seo audit", "seo check", "ranking"]),
            ("code_deploy",      ["deploy", "push code", "release"]),
            ("content_update",   ["content update", "content change", "write content"]),
            ("media_generation", ["media", "image", "video", "graphic"]),
        ]
        for task_name, triggers in mapping:
            if any(t in desc for t in triggers):
                return task_name
        return "general_task"

    # ══════════════════════════════════════════════════════════════════════
    #  2.  TASK SCHEDULING
    # ══════════════════════════════════════════════════════════════════════

    def _load_schedule(self) -> Dict[str, Any]:
        """Load schedule.json, returning empty dict on error."""
        try:
            data = self._read_json(SCHEDULE_FILE, default={})
            if not isinstance(data, dict):
                return {}
            return data
        except Exception as exc:
            log.critical("_load_schedule crashed: %s", exc, exc_info=True)
            return {}

    def _save_schedule(self, schedule: Dict[str, Any]) -> None:
        """Persist schedule data."""
        try:
            self._write_json(SCHEDULE_FILE, schedule)
        except Exception as exc:
            log.critical("_save_schedule crashed: %s", exc, exc_info=True)

    def check_schedule(self) -> list:
        """
        Scan the schedule for tasks whose interval has elapsed.

        Returns
        -------
        list[dict]
            Each dict: ``{site, task, interval_minutes, last_run, agent}``.
            Sorted by priority: uptime_check first, then security_scan,
            then seo_audit.
        """
        try:
            schedule = self._load_schedule()
            now = _utcnow()
            due: list = []

            for site, tasks in schedule.items():
                if not isinstance(tasks, dict):
                    continue
                for task_name, config in tasks.items():
                    if not isinstance(config, dict):
                        continue

                    interval = config.get("interval_minutes", 60)
                    last_run_str = config.get("last_run")

                    is_due = False
                    if last_run_str is None:
                        is_due = True
                    else:
                        try:
                            last_run = datetime.fromisoformat(last_run_str)
                            # Make offset-aware if naive
                            if last_run.tzinfo is None:
                                last_run = last_run.replace(tzinfo=timezone.utc)
                            elapsed_min = (now - last_run).total_seconds() / 60.0
                            is_due = elapsed_min >= interval
                        except (ValueError, TypeError):
                            is_due = True   # corrupt timestamp → treat as due

                    if is_due:
                        due.append({
                            "site": site,
                            "task": task_name,
                            "interval_minutes": interval,
                            "last_run": last_run_str,
                            "agent": TASK_AGENT_MAP.get(task_name, "unknown"),
                        })

            # Priority order: uptime first (lightweight), then security, then seo
            priority = {"uptime_check": 0, "security_scan": 1, "seo_audit": 2}
            due.sort(key=lambda t: priority.get(t["task"], 99))

            return due

        except Exception as exc:
            log.critical("check_schedule crashed: %s", exc, exc_info=True)
            return []

    def _update_schedule_last_run(self, site: str, task: str) -> None:
        """Record that *task* for *site* was just executed."""
        try:
            schedule = self._load_schedule()
            if site not in schedule:
                schedule[site] = {
                    t: dict(c) for t, c in _DEFAULT_SITE_SCHEDULE.items()
                }
            if task not in schedule[site]:
                schedule[site][task] = {
                    "interval_minutes": _DEFAULT_SITE_SCHEDULE.get(
                        task, {}
                    ).get("interval_minutes", 60),
                    "last_run": None,
                }
            schedule[site][task]["last_run"] = _utcnow_iso()
            self._save_schedule(schedule)
        except Exception as exc:
            log.critical("_update_schedule_last_run crashed: %s", exc, exc_info=True)

    def _ensure_site_in_schedule(self, site: str) -> None:
        """Add *site* with default intervals if it's missing from the schedule."""
        try:
            schedule = self._load_schedule()
            if site not in schedule:
                schedule[site] = {
                    t: dict(c) for t, c in _DEFAULT_SITE_SCHEDULE.items()
                }
                self._save_schedule(schedule)
                log.info("Added new site to schedule: %s", site)
        except Exception as exc:
            log.warning("_ensure_site_in_schedule failed: %s", exc)

    # ══════════════════════════════════════════════════════════════════════
    #  3.  COST GOVERNOR
    # ══════════════════════════════════════════════════════════════════════

    def _load_spend(self) -> Dict[str, Any]:
        """
        Load spend.json, automatically rolling over on date / month change.

        Returns a dict with ``date``, ``daily_total``, ``monthly_total``,
        ``daily_limit``, ``monthly_limit``.
        """
        try:
            data = self._read_json(SPEND_FILE, default=self._fresh_spend_record())
            if not isinstance(data, dict):
                data = self._fresh_spend_record()

            today = _today_str()
            this_month = _month_str()
            stored_date = data.get("date", "")

            # ── Day rollover ──
            if stored_date != today:
                old_daily = data.get("daily_total", 0.0)
                log.info(
                    "Spend day rollover: %s ($%.2f) → %s",
                    stored_date, old_daily, today,
                )
                data["daily_total"] = 0.0
                data["date"] = today

                # ── Month rollover ──
                if not stored_date.startswith(this_month):
                    log.info(
                        "Spend month rollover: monthly total was $%.2f → reset",
                        data.get("monthly_total", 0.0),
                    )
                    data["monthly_total"] = 0.0

                # Persist the rollover immediately
                self._write_json(SPEND_FILE, data)

            # Always enforce our hard limits regardless of what the file says
            data["daily_limit"] = DAILY_LIMIT
            data["monthly_limit"] = MONTHLY_LIMIT

            return data

        except Exception as exc:
            log.critical("_load_spend crashed: %s", exc, exc_info=True)
            return self._fresh_spend_record()

    def check_budget(self, estimated_cost: float) -> bool:
        """
        Check whether *estimated_cost* (USD) is within budget.

        Returns
        -------
        bool
            ``True`` if the spend is allowed.
            ``False`` if either daily or monthly limit would be exceeded.

        Side Effects
        ------------
        If over-limit: logs ``CRITICAL``, sends Telegram alert, returns False.
        """
        try:
            spend = self._load_spend()
            daily  = spend.get("daily_total", 0.0)
            monthly = spend.get("monthly_total", 0.0)

            # ── Daily check ──
            if daily + estimated_cost > DAILY_LIMIT:
                msg = (
                    f"💸 DAILY BUDGET EXCEEDED  |  "
                    f"current=${daily:.2f}  |  requested=${estimated_cost:.2f}  |  "
                    f"limit=${DAILY_LIMIT:.2f}"
                )
                log.critical(msg)
                self._send_alert(f"🚨 BUDGET ALERT\n\n{msg}\n\nAll spending is HALTED.")
                log.log_action(
                    action="budget_exceeded",
                    details={"type": "daily", "current": daily,
                             "requested": estimated_cost, "limit": DAILY_LIMIT},
                    agent="director",
                    status="blocked",
                )
                return False

            # ── Monthly check ──
            if monthly + estimated_cost > MONTHLY_LIMIT:
                msg = (
                    f"💸 MONTHLY BUDGET EXCEEDED  |  "
                    f"current=${monthly:.2f}  |  requested=${estimated_cost:.2f}  |  "
                    f"limit=${MONTHLY_LIMIT:.2f}"
                )
                log.critical(msg)
                self._send_alert(f"🚨 BUDGET ALERT\n\n{msg}\n\nAll spending is HALTED.")
                log.log_action(
                    action="budget_exceeded",
                    details={"type": "monthly", "current": monthly,
                             "requested": estimated_cost, "limit": MONTHLY_LIMIT},
                    agent="director",
                    status="blocked",
                )
                return False

            return True

        except Exception as exc:
            # On error, DENY — safe default
            log.critical("check_budget crashed — DENYING spend: %s", exc, exc_info=True)
            return False

    def log_spend(self, amount: float, reason: str, site: str) -> None:
        """
        Record a spend event.

        Adds *amount* to both daily and monthly accumulators in spend.json,
        and logs a row into the SQLite ``spend_log`` table.

        Parameters
        ----------
        amount : float
            USD amount spent.
        reason : str
            What the money was spent on (task name).
        site : str
            Which site the spend is associated with.
        """
        try:
            spend = self._load_spend()
            spend["daily_total"]   = round(spend.get("daily_total", 0.0) + amount, 4)
            spend["monthly_total"] = round(spend.get("monthly_total", 0.0) + amount, 4)
            self._write_json(SPEND_FILE, spend)

            log.info(
                "Spend recorded  |  $%.4f  |  reason=%s  |  site=%s  |  "
                "day=$%.2f/$%.2f  |  month=$%.2f/$%.2f",
                amount, reason, site,
                spend["daily_total"], DAILY_LIMIT,
                spend["monthly_total"], MONTHLY_LIMIT,
            )

            log.log_action(
                action="spend",
                details={
                    "amount": amount,
                    "reason": reason,
                    "site": site,
                    "daily_total": spend["daily_total"],
                    "monthly_total": spend["monthly_total"],
                },
                agent="director",
                status="success",
            )

        except Exception as exc:
            log.critical("log_spend crashed: %s", exc, exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    #  4.  APPROVAL GATE
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _is_sensitive(task: str) -> bool:
        """Return ``True`` if *task* requires human approval."""
        return task in SENSITIVE_TASKS

    def _gate_approval(self, task: str, site: str, details: str) -> bool:
        """
        Request human Telegram approval for a sensitive task.

        Returns ``True`` if approved, ``False`` if denied / timed-out /
        approval system unavailable.
        """
        if self._approval is None:
            log.critical(
                "Approval system unavailable — DENYING sensitive task '%s'",
                task,
            )
            return False

        try:
            log.info("Requesting approval  |  task=%s  |  site=%s", task, site)

            # ApprovalSystem.request_approval(action, details) — no risk_level kwarg
            approved = self._approval.request_approval(
                action=task,
                details={
                    "site": site,
                    "description": details,
                    "agent": "director",
                    "risk_level": "high",
                },
            )

            if approved:
                log.info("✅ Approved: %s on %s", task, site)
            else:
                log.warning("❌ Denied / timed-out: %s on %s", task, site)

            return approved

        except Exception as exc:
            log.critical("Approval gate crashed — DENYING: %s", exc, exc_info=True)
            return False

    # ══════════════════════════════════════════════════════════════════════
    #  5.  AGENT DISPATCH
    # ══════════════════════════════════════════════════════════════════════

    def dispatch_agent(
        self,
        agent: str,
        task: str,
        site: str,
        params: dict,
    ) -> dict:
        """
        Dispatch a task to the named agent and return its result.

        The Director never does work itself — this method routes to the
        correct agent, catches all errors, and logs the outcome.

        Parameters
        ----------
        agent : str
            ``"sentinel"``, ``"developer"``, ``"strategist"``, or ``"media"``.
        task : str
            Canonical task name (e.g. ``"security_scan"``).
        site : str
            Target site (e.g. ``"falconherbs.com"``).
        params : dict
            Extra parameters forwarded to the agent.

        Returns
        -------
        dict
            ``{status: "success"|"error"|"skipped", ...}``
        """
        dispatch_start = time.monotonic()
        self._current_task = task
        self._current_site = site

        log.info(
            "Dispatching  |  agent=%s  |  task=%s  |  site=%s",
            agent, task, site,
        )

        try:
            # ── Route to handler ──
            if agent == "sentinel":
                result = self._dispatch_sentinel(task, site, params)
            elif agent in ("developer", "strategist", "media"):
                result = self._dispatch_dynamic_agent(agent, task, site, params)
            else:
                result = {
                    "status": "error",
                    "message": f"Unknown agent: {agent}",
                }

            duration = time.monotonic() - dispatch_start

            # ── Log the dispatch ──
            log.log_action(
                action=f"dispatch_{agent}",
                details={
                    "task": task,
                    "site": site,
                    "params": params,
                    "duration_s": round(duration, 2),
                    "result_status": result.get("status", "unknown"),
                },
                agent=agent,
                status=result.get("status", "unknown"),
            )

            log.info(
                "Dispatch complete  |  agent=%s  |  task=%s  |  site=%s  |  "
                "status=%s  |  %.2fs",
                agent, task, site, result.get("status", "?"), duration,
            )

            return result

        except Exception as exc:
            duration = time.monotonic() - dispatch_start
            log.critical(
                "dispatch_agent crashed  |  agent=%s  |  task=%s  |  %s",
                agent, task, exc, exc_info=True,
            )
            log.log_action(
                action=f"dispatch_{agent}",
                details={
                    "task": task, "site": site,
                    "error": str(exc)[:300],
                    "duration_s": round(duration, 2),
                },
                agent=agent,
                status="error",
            )
            return {"status": "error", "error": str(exc)[:300]}

        finally:
            self._current_task = None
            self._current_site = None

    # ── Sentinel dispatcher ──

    def _dispatch_sentinel(self, task: str, site: str, params: dict) -> dict:
        """Route Sentinel tasks."""
        if self._sentinel is None:
            return {"status": "error", "message": "Sentinel not initialised"}

        if task == "security_scan":
            # Sentinel.run_scan expects URL; add scheme if missing
            url = site if site.startswith("http") else f"https://{site}"
            report = self._sentinel.run_scan(url)
            return {
                "status": "success",
                "report": report,
                "message": (
                    f"Security scan complete — "
                    f"{report.get('total_findings', '?')} findings, "
                    f"highest: {report.get('highest_severity', '?')}"
                ),
            }

        if task == "uptime_check":
            return self._quick_uptime_check(site)

        return {"status": "error", "message": f"Unknown sentinel task: {task}"}

    # ── Dynamic agent dispatcher (developer / strategist / media) ──

    def _dispatch_dynamic_agent(
        self,
        agent_name: str,
        task: str,
        site: str,
        params: dict,
    ) -> dict:
        """
        Attempt to dynamically load and invoke an agent module.

        Expected agent module convention:
            ``agents/<agent_name>.py`` must expose a class whose name ends
            with ``Agent`` (e.g. ``DeveloperAgent``), and that class must
            have an ``execute(task, site, params) -> dict`` method.

        If the module is empty or not ready, a warning is logged and
        the task is skipped gracefully.
        """
        module_path = f"agents.{agent_name}"

        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            log.warning(
                "Agent module '%s' not importable — skipping: %s",
                module_path, exc,
            )
            return {"status": "skipped", "message": f"Module {module_path} not available"}

        # ── Find agent class ──
        agent_class = None
        for attr_name in dir(module):
            obj = getattr(module, attr_name, None)
            if (
                isinstance(obj, type)
                and attr_name.lower().endswith("agent")
                and hasattr(obj, "execute")
            ):
                agent_class = obj
                break

        if agent_class is None:
            log.warning(
                "Agent module '%s' has no *Agent class with execute() — skipping",
                module_path,
            )
            return {
                "status": "skipped",
                "message": f"No ready agent class in {module_path}",
            }

        # ── Instantiate and execute ──
        try:
            instance = agent_class()
            result = instance.execute(task=task, site=site, params=params)
            if not isinstance(result, dict):
                result = {"status": "success", "raw": str(result)[:500]}
            return result
        except Exception as exc:
            log.critical(
                "Agent %s.execute() threw: %s", agent_name, exc, exc_info=True,
            )
            return {"status": "error", "error": str(exc)[:300]}

    # ── Lightweight uptime check ──

    def _quick_uptime_check(self, site: str) -> dict:
        """
        Lightweight HTTP HEAD check.

        Uses ``urllib`` from stdlib — no external dependency — with a
        5-second timeout.  Good enough for a 5-minute heartbeat probe.
        """
        url = site if site.startswith("http") else f"https://{site}"
        start = time.monotonic()

        try:
            req = urllib.request.Request(
                url,
                method="HEAD",
                headers={"User-Agent": "FalconAgency-Director/1.0"},
            )
            resp = urllib.request.urlopen(req, timeout=UPTIME_CHECK_TIMEOUT)  # noqa: S310
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            status = "up" if resp.status < 500 else "down"

            if status == "down":
                log.warning("Site DOWN  |  %s  |  HTTP %d", site, resp.status)
                self._send_alert(
                    f"🔴 SITE DOWN: {site}\nHTTP {resp.status}\nTime: {_utcnow_iso()}"
                )
            else:
                log.info("Uptime OK  |  %s  |  %dms", site, elapsed_ms)

            return {
                "status": status,
                "status_code": resp.status,
                "response_time_ms": elapsed_ms,
                "message": f"{site} is {status}",
            }

        except urllib.error.HTTPError as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            is_up = exc.code < 500
            level = "up" if is_up else "down"

            if not is_up:
                log.warning("Site DOWN  |  %s  |  HTTP %d", site, exc.code)
                self._send_alert(
                    f"🔴 SITE DOWN: {site}\nHTTP {exc.code}\nTime: {_utcnow_iso()}"
                )

            return {
                "status": level,
                "status_code": exc.code,
                "response_time_ms": elapsed_ms,
                "message": f"{site} returned HTTP {exc.code}",
            }

        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            log.warning("Site UNREACHABLE  |  %s  |  %s", site, exc)
            self._send_alert(
                f"🔴 SITE UNREACHABLE: {site}\nError: {str(exc)[:200]}\n"
                f"Time: {_utcnow_iso()}"
            )
            return {
                "status": "down",
                "response_time_ms": elapsed_ms,
                "error": str(exc)[:200],
                "message": f"{site} is unreachable",
            }

    # ══════════════════════════════════════════════════════════════════════
    #  6.  HEARTBEAT
    # ══════════════════════════════════════════════════════════════════════

    def run_heartbeat(self) -> None:
        """
        Emit a heartbeat record to the console and SQLite.

        Includes current state: timestamp, active site, current task,
        daily spend.  Also checks for idle condition (>5 min no activity)
        and sends a Telegram alert if so.
        """
        try:
            now = time.monotonic()
            spend = self._load_spend()

            log.info(
                "♥  Heartbeat #%d  |  site=%s  |  task=%s  |  "
                "spend=$%.2f/$%.2f  |  %s",
                self._cycle_count,
                self._current_site or "idle",
                self._current_task or "none",
                spend.get("daily_total", 0.0),
                DAILY_LIMIT,
                _utcnow_iso(),
            )

            log.log_action(
                action="heartbeat",
                details={
                    "cycle": self._cycle_count,
                    "active_site": self._current_site,
                    "current_task": self._current_task,
                    "daily_spend": spend.get("daily_total", 0.0),
                    "monthly_spend": spend.get("monthly_total", 0.0),
                    "timestamp": _utcnow_iso(),
                },
                agent="director",
                status="success",
            )

            # ── Idle detection ──
            idle_seconds = now - self._last_activity
            if idle_seconds > IDLE_ALERT_SECONDS and not self._idle_alert_sent:
                idle_min = round(idle_seconds / 60, 1)
                log.warning(
                    "Director idle for %.1f minutes — sending alert", idle_min,
                )
                self._send_alert(
                    f"⏳ FALCON AGENCY — Director Idle\n\n"
                    f"No task activity for {idle_min} minutes.\n"
                    f"Last heartbeat: {_utcnow_iso()}\n"
                    f"Daily spend: ${spend.get('daily_total', 0.0):.2f}"
                )
                self._idle_alert_sent = True

        except Exception as exc:
            log.warning("Heartbeat failed: %s", exc, exc_info=True)

    # ══════════════════════════════════════════════════════════════════════
    #  7.  MAIN LOOP
    # ══════════════════════════════════════════════════════════════════════

    def process_cycle(self) -> None:
        """
        Execute one full orchestration cycle.

        Steps:
            1. Heartbeat
            2. Check schedule → get due tasks
            3. For each due task (budget permitting):
                 a. Budget check
                 b. Approval gate (if sensitive)
                 c. Dispatch agent
                 d. Log spend
                 e. Update schedule
            4. Process next pending goal (if time permits)

        The cycle is time-budgeted to ~25 seconds.  Any remaining
        work is deferred to the next cycle.
        """
        cycle_start = time.monotonic()
        self._cycle_count += 1

        try:
            # ── 1. Heartbeat ──
            self.run_heartbeat()

            # ── 2. Scheduled tasks ──
            due_tasks = self.check_schedule()
            if due_tasks:
                log.info("Due tasks this cycle: %d", len(due_tasks))

            tasks_completed = 0

            for task_info in due_tasks:
                # Time budget guard
                if time.monotonic() - cycle_start > CYCLE_TIME_BUDGET:
                    log.warning(
                        "Cycle time budget (%.0fs) exceeded — "
                        "deferring %d remaining tasks",
                        CYCLE_TIME_BUDGET,
                        len(due_tasks) - tasks_completed,
                    )
                    break

                # Max tasks per cycle guard
                if tasks_completed >= MAX_TASKS_PER_CYCLE:
                    log.info("Task-per-cycle cap (%d) reached", MAX_TASKS_PER_CYCLE)
                    break

                task_name = task_info["task"]
                site      = task_info["site"]
                agent     = task_info["agent"]

                # Budget check
                estimated_cost = TASK_ESTIMATED_COST.get(task_name, 0.0)
                if estimated_cost > 0 and not self.check_budget(estimated_cost):
                    log.critical("Budget exhausted — halting all scheduled tasks")
                    break

                # Approval gate (sensitive tasks only)
                if self._is_sensitive(task_name):
                    if not self._gate_approval(task_name, site, f"Scheduled {task_name}"):
                        log.info("Skipping denied task: %s on %s", task_name, site)
                        continue

                # Dispatch
                result = self.dispatch_agent(
                    agent=agent,
                    task=task_name,
                    site=site,
                    params={"source": "schedule"},
                )

                # Record spend
                if estimated_cost > 0 and result.get("status") not in ("error", "skipped"):
                    self.log_spend(estimated_cost, task_name, site)

                # Update schedule regardless of outcome (prevents retry storm)
                self._update_schedule_last_run(site, task_name)

                tasks_completed += 1
                self._last_activity = time.monotonic()
                self._idle_alert_sent = False

            # ── 3. Goal processing (if time remains) ──
            elapsed = time.monotonic() - cycle_start
            if elapsed < CYCLE_TIME_BUDGET:
                goal = self.get_next_goal()
                if goal is not None:
                    # Ensure the goal's site is in the schedule for future scans
                    goal_site = goal.get("site", "")
                    if goal_site:
                        self._ensure_site_in_schedule(goal_site)

                    self._process_goal(goal)
                    self._last_activity = time.monotonic()
                    self._idle_alert_sent = False

            cycle_duration = time.monotonic() - cycle_start
            log.info(
                "Cycle #%d complete  |  scheduled=%d  |  executed=%d  |  %.1fs",
                self._cycle_count,
                len(due_tasks),
                tasks_completed,
                cycle_duration,
            )

        except Exception as exc:
            log.critical(
                "process_cycle crashed (recovering): %s",
                exc, exc_info=True,
            )

    def run(self) -> None:
        """
        Start the infinite Director loop.

        Blocks forever.  Catches ``KeyboardInterrupt`` and signals for
        graceful shutdown.

        The loop sleeps in 1-second increments so shutdown is responsive
        (< 2 seconds to exit after signal).
        """
        log.info("━" * 60)
        log.info("🦅  FALCON AGENCY DIRECTOR — STARTING MAIN LOOP")
        log.info("━" * 60)

        self._running = True
        self._last_activity = time.monotonic()

        # ── Start webhook server (WhatsApp incoming messages) ──
        if self._webhook is not None:
            self._webhook.start(host="0.0.0.0", port=8000)
            log.info("WhatsApp webhook listening on port 8000")

        # Announce startup
        self._send_alert(
            "🦅 FALCON AGENCY — Director Started\n\n"
            f"Time: {_utcnow_iso()}\n"
            f"Mode: {'PRODUCTION' if IS_PRODUCTION else 'DEVELOPMENT'}\n"
            f"Cycle: {CYCLE_SECONDS}s\n"
            f"Budget: ${DAILY_LIMIT}/day, ${MONTHLY_LIMIT}/month"
        )

        try:
            while self._running:
                try:
                    self.process_cycle()
                except Exception as exc:
                    # process_cycle has its own handler, but if it somehow
                    # re-raises, we catch here to keep the loop alive.
                    log.critical(
                        "Unhandled exception escaped process_cycle: %s",
                        exc, exc_info=True,
                    )

                # Sleep in 1-second increments for responsive shutdown
                for _ in range(CYCLE_SECONDS):
                    if not self._running:
                        break
                    time.sleep(1)

        except KeyboardInterrupt:
            log.info("KeyboardInterrupt received")
        finally:
            self._shutdown("Main loop exited")

    # ══════════════════════════════════════════════════════════════════════
    #  8.  GRACEFUL SHUTDOWN
    # ══════════════════════════════════════════════════════════════════════

    def _install_signal_handlers(self) -> None:
        """
        Register OS signal handlers for graceful shutdown.

        Handles platform differences:
            Linux/macOS : SIGINT + SIGTERM
            Windows     : SIGINT + SIGBREAK
        """
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
        except (OSError, ValueError):
            pass   # Can fail if not on main thread

        if hasattr(signal, "SIGTERM"):
            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
            except (OSError, ValueError):
                pass

        if hasattr(signal, "SIGBREAK"):
            try:
                signal.signal(signal.SIGBREAK, self._signal_handler)  # type: ignore[attr-defined]
            except (OSError, ValueError):
                pass

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """
        Signal callback — sets the shutdown flag.

        Does NOT call ``_shutdown()`` directly because signal handlers
        have restrictions (no I/O, no locks).  The ``run()`` loop will
        notice ``self._running == False`` and call ``_shutdown()``.
        """
        try:
            sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        except (ValueError, AttributeError):
            sig_name = str(signum)
        # Use print here because logging in a signal handler can deadlock
        print(f"\n[FALCON] Signal {sig_name} received — initiating shutdown…")
        self._running = False

    def _shutdown(self, reason: str = "Unknown") -> None:
        """
        Persist state, notify owner, and log final message.

        Called exactly once when the Director is exiting.
        """
        log.info("━" * 60)
        log.info("FALCON AGENCY DIRECTOR — SHUTTING DOWN")
        log.info("  Reason : %s", reason)
        log.info("  Time   : %s", _utcnow_iso())
        log.info("  Cycles : %d", self._cycle_count)

        # ── Save goals (in case any are in_progress → back to pending) ──
        try:
            goals = self.load_goals()
            reverted = 0
            for g in goals:
                if g.get("status") == "in_progress":
                    g["status"] = "pending"
                    g["updated_at"] = _utcnow_iso()
                    g["result_summary"] = "Reverted: Director shutdown"
                    reverted += 1
            if reverted:
                self.save_goals(goals)
                log.info("  Reverted %d in-progress goal(s) to pending", reverted)
        except Exception as exc:
            log.critical("Failed to save goals on shutdown: %s", exc)

        # ── Log final spend summary ──
        try:
            spend = self._load_spend()
            log.info(
                "  Spend  : day=$%.2f  month=$%.2f",
                spend.get("daily_total", 0.0),
                spend.get("monthly_total", 0.0),
            )
        except Exception:
            pass

        # ── Stop webhook ──
        if hasattr(self, "_webhook") and self._webhook is not None:
            self._webhook.stop()

        # ── WhatsApp shutdown notification ──
        try:
            self._send_alert(
                "🛑 FALCON AGENCY — Director Stopped\n\n"
                f"Reason: {reason}\n"
                f"Cycles completed: {self._cycle_count}\n"
                f"Time: {_utcnow_iso()}"
            )
        except Exception:
            pass

        log.log_action(
            action="director_shutdown",
            details={
                "reason": reason,
                "cycles": self._cycle_count,
                "timestamp": _utcnow_iso(),
            },
            agent="director",
            status="success",
        )

        log.info("━" * 60)
        log.info("Goodbye.")
        log.info("━" * 60)

    # ══════════════════════════════════════════════════════════════════════
    #  INTERNAL UTILITIES
    # ══════════════════════════════════════════════════════════════════════

    def _send_alert(self, message: str) -> None:
        """
        Best-effort alert via WhatsApp.

        Failures are logged but never raised — the Director must not
        crash because WhatsApp is unreachable.
        """
        if self._approval is None:
            log.warning("ApprovalSystem unavailable — cannot send alert")
            return
        try:
            self._approval.send_alert(message)
        except Exception as exc:
            log.warning("Failed to send Telegram alert: %s", exc)

    def __repr__(self) -> str:
        spend = self._load_spend()
        return (
            f"<Director  "
            f"cycle={self._cycle_count}  "
            f"running={'🟢' if self._running else '⚫'}  "
            f"spend_today=${spend.get('daily_total', 0):.2f}  "
            f"task={self._current_task or 'idle'}>"
        )
