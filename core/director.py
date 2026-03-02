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

import concurrent.futures
import importlib
import json
import os
import signal
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from core.ist_time import now_ist, now_ist_str, today_ist, month_ist, IST
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
from core.director_schedule import ExtendedSchedule
from core.integration_bridge import IntegrationBridge
from core.ai_client import call_ai
from core.woocommerce_connector import WooCommerceConnector
from core.revenue_tracker import RevenueTracker
from core.learning_cache import learning


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PATHS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent   # F:/FALCON AGENCY
AGENT_TIMEOUT: int = 300  # 5 minutes max per agent task
DATA_DIR:     Path = PROJECT_ROOT / "data"
GOALS_FILE:   Path = DATA_DIR / "goals.json"
SCHEDULE_FILE: Path = DATA_DIR / "schedule.json"
SPEND_FILE:   Path = DATA_DIR / "spend.json"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SPEND LIMITS — set high intentionally
#  Real protection = NVIDIA billing system (no payment on file = 402, no charge).
#  These are kept only so the spend tracker has a ceiling to log against.
#  Old values ($10/$150) were false-triggering and blocking chat replies.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DAILY_LIMIT:   float = 500.00   # USD — effectively open (NVIDIA is the real guard)
MONTHLY_LIMIT: float = 5000.00  # USD — effectively open


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TIMING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CYCLE_SECONDS: int          = 60     # main loop period
CYCLE_TIME_BUDGET: float    = 25.0   # max seconds of work per cycle
IDLE_ALERT_SECONDS: int     = 3600   # 60 minutes → "Director idle" alert
MAX_TASKS_PER_CYCLE: int    = 10     # cap to avoid monopolising the loop
UPTIME_CHECK_TIMEOUT: int   = 20     # seconds; SSL handshake from VPS can be slow


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TASK CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Which agent handles which scheduled task
TASK_AGENT_MAP: Dict[str, str] = {
    "security_scan":  "sentinel",
    "uptime_check":   "sentinel",
    "seo_audit":      "strategist",
    "revenue_sync":   "internal",
}

# Estimated API cost per task (USD).  Zero = free (local HTTP only).
TASK_ESTIMATED_COST: Dict[str, float] = {
    "uptime_check":     0.00,
    "security_scan":    0.00,
    "revenue_sync":     0.00,
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
                   "ssl", "firewall", "intrusion", "brute", "malware",
                   "health", "login", "threat", "block"],
    "developer":  ["code", "deploy", "develop", "fix", "update", "css",
                   "html", "javascript", "bug", "patch", "refactor", "build",
                   "performance", "speed", "load", "target", "slow", "fast",
                   "plugin", "theme", "backup", "restore", "inventory", "stock"],
    "strategist": ["seo", "ranking", "keyword", "strategy", "analytics",
                   "traffic", "serp", "backlink", "competitor", "audit",
                   "revenue", "sales", "woocommerce", "order", "customer",
                   "conversion", "revenue", "sync", "data", "report",
                   "growth", "market", "product", "pricing", "profit"],
    "media":      ["content", "media", "image", "video", "photo", "design",
                   "social", "post", "graphic", "thumbnail", "copy",
                   "blog", "draft", "publish", "queue", "caption", "review"],
}

# Default schedule template for a new site
_DEFAULT_SITE_SCHEDULE: Dict[str, Dict[str, Any]] = {
    "security_scan": {"interval_minutes": 30,   "last_run": None},
    "seo_audit":     {"interval_minutes": 1440, "last_run": None},
    "uptime_check":  {"interval_minutes": 5,    "last_run": None},
    "revenue_sync":  {"interval_minutes": 60,   "last_run": None},
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
    """IST now (India Standard Time, UTC+5:30)."""
    return now_ist()


def _utcnow_iso() -> str:
    """ISO-8601 IST timestamp — e.g. '2026-03-02T22:41:43+05:30'."""
    return now_ist_str()


def _today_str() -> str:
    """Current IST date as YYYY-MM-DD."""
    return today_ist()


def _month_str() -> str:
    """Current IST year-month as YYYY-MM."""
    return month_ist()


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

    def __init__(self, whatsapp_client=None) -> None:
        """
        Initialise the Director.

        Creates data directory and default JSON files if they don't exist,
        boots the approval channel and sentinel scanner, and installs
        signal handlers for graceful shutdown.
        """
        self._running: bool = False              # main-loop flag
        self._last_activity: float = time.monotonic()
        self._last_idle_alert_time: float = 0.0  # monotonic time of last idle alert
        self._last_unreachable_alert: Dict[str, float] = {}  # site -> monotonic time; cooldown
        self._site_down_count: Dict[str, int] = {}    # consecutive down count per site
        self._site_last_alert: Dict[str, float] = {}  # monotonic time of last down alert per site
        self._cycle_count: int = 0
        self._retry_queue: List[Dict[str, Any]] = []  # tasks deferred when Director busy
        self._current_task: Optional[str] = None
        self._current_site: Optional[str] = None
        self._failure_log: List[Dict[str, Any]] = []   # rolling failure accumulator (reset daily)
        self._failure_digest_sent_date: str = ""        # "YYYY-MM-DD" of last digest sent

        # ── Ensure data directory exists ──
        self._ensure_data_dir()

        # ── Boot subsystems (each is individually guarded) ──
        self._vault:    Optional[KeyVault]       = self._safe_init("KeyVault",       KeyVault)
        self._settings: Optional[AgencySettings] = self._safe_init("AgencySettings", AgencySettings)
        self._safety:   Optional[SafetyGuard]    = self._safe_init("SafetyGuard",    SafetyGuard)
        self._approval: Optional[ApprovalSystem] = self._safe_init("ApprovalSystem", ApprovalSystem)
        self._sentinel: Optional[Sentinel]       = self._init_sentinel()

        # ── WhatsApp + Commander + Webhook ──
        self._whatsapp: Optional[WhatsAppNotifier] = whatsapp_client or self._safe_init("WhatsAppNotifier", WhatsAppNotifier)
        self._commander: Optional[FalconCommander] = self._init_commander()
        self._webhook: Optional[FalconWebhook]     = self._init_webhook()

        # ── Import and initialize agents ──
        from agents.developer import DeveloperAgent
        from agents.strategist import StrategistAgent
        from agents.media import MediaAgent
        from agents.backup import BackupAgent
        
        self._developer = DeveloperAgent(self._whatsapp)
        self._strategist = StrategistAgent(self._whatsapp)
        self._media = MediaAgent(self._whatsapp)
        self._backup = BackupAgent(self._whatsapp)

        # ── Extended schedule (safe — if fails, old system continues) ──
        try:
            self._bridge = IntegrationBridge()
            self._extended_schedule = ExtendedSchedule(self._bridge)
            log.info("Extended schedule loaded (bridge OK)")
        except Exception as e:
            self._bridge = None
            self._extended_schedule = None
            log.warning("Extended schedule unavailable: %s", e)

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
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                goals = data.get("goals", data.get("tasks", [])) or []
                return goals if isinstance(goals, list) else []
            return []
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

        When all goals are exhausted, auto-injects recurring maintenance
        goals so the Director is never permanently idle.
        """
        try:
            goals = self.load_goals()
            pending = [g for g in goals if g.get("status") == "pending"]
            if not pending:
                # All goals done — inject recurring maintenance goals
                self._auto_refresh_goals(goals)
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

    _MAINTENANCE_GOALS = [
        {
            "description": "Monitor site health and uptime",
            "agent": "sentinel",
            "task": "uptime_check",
            "priority": 10,
        },
        {
            "description": "Review content queue for pending drafts",
            "agent": "media",
            "task": "content_queue_review",
            "priority": 10,
        },
        {
            "description": "Sync latest revenue data from WooCommerce",
            "agent": "internal",
            "task": "revenue_sync",
            "priority": 10,
        },
        {
            "description": "Check inventory levels for low-stock alerts",
            "agent": "internal",
            "task": "inventory_check",
            "priority": 10,
        },
    ]

    def _auto_refresh_goals(self, existing_goals: list) -> None:
        """When all goals are exhausted, inject recurring maintenance
        goals so the Director is never idle indefinitely.

        Only injects if no maintenance goal was added in the last
        3 hours (prevents goal flooding)."""
        try:
            # Check if we recently added maintenance goals
            recent_maintenance = [
                g for g in existing_goals
                if g.get("auto_maintenance")
                and g.get("created_at", "") > (
                    datetime.now(timezone.utc)
                    - timedelta(hours=3)
                ).isoformat()
            ]
            if recent_maintenance:
                return  # Don't flood — wait 3 hours between refreshes

            new_goals = []
            for template in self._MAINTENANCE_GOALS:
                new_goals.append({
                    "id": str(uuid.uuid4()),
                    "description": template["description"],
                    "agent": template["agent"],
                    "task": template.get("task"),
                    "site": "falconherbs.com",
                    "priority": template["priority"],
                    "status": "pending",
                    "created_at": _utcnow_iso(),
                    "auto_maintenance": True,
                })

            updated = existing_goals + new_goals
            self.save_goals(updated)
            log.info(
                "Director: Auto-refreshed %d maintenance goals",
                len(new_goals),
            )
        except Exception as exc:
            log.warning("_auto_refresh_goals failed: %s", exc)

    def _run_idle_monitoring(self) -> None:
        """Called when a cycle completes with zero work done.
        Performs lightweight background checks and updates
        _current_task so WhatsApp status is always meaningful."""
        import json as _json

        status_parts: list[str] = []

        # 1. Content queue check
        try:
            drafts_dir = DATA_DIR / "content" / "drafts"
            if drafts_dir.exists():
                needs_review = sum(
                    1 for f in drafts_dir.glob("*.json")
                    if _json.loads(
                        f.read_text(encoding="utf-8")
                    ).get("status") == "needs_review"
                )
                if needs_review:
                    status_parts.append(
                        "{} draft(s) need review".format(needs_review)
                    )
        except Exception:
            pass

        # 2. Pending product rewrites
        try:
            rw_dir = (
                DATA_DIR / "content" / "product_rewrites"
            )
            if rw_dir.exists():
                pending_rw = 0
                for f in rw_dir.glob("*.json"):
                    if f.name == "last_scan.json":
                        continue
                    try:
                        if _json.loads(
                            f.read_text(encoding="utf-8")
                        ).get("status") == "pending":
                            pending_rw += 1
                    except Exception:
                        continue
                if pending_rw:
                    status_parts.append(
                        "{} product rewrite(s) pending "
                        "approval".format(pending_rw)
                    )
        except Exception:
            pass

        # 3. Quick site ping every 10 idle cycles
        if self._cycle_count % 10 == 0:
            try:
                import os
                site_url = os.getenv(
                    "WOO_SITE_URL", "https://falconherbs.com"
                )
                urllib.request.urlopen(site_url, timeout=5)
                status_parts.append("site responding OK")
            except Exception:
                status_parts.append("site ping timeout")
                log.warning(
                    "Director idle-monitoring: site ping failed"
                )

        # 5. AutoPilot — proactive intelligence tick (every idle cycle)
        try:
            from core.autopilot import autopilot
            injected = autopilot.tick(director=self)
            if injected:
                for goal in injected:
                    status_parts.append(
                        f"🤖 AutoPilot: {goal['description'][:50]}..."
                    )
        except Exception as exc:
            log.debug("AutoPilot tick error: %s", exc)

        summary = (
            "Monitoring: " + " | ".join(status_parts)
            if status_parts
            else "Monitoring: all systems OK"
        )
        self._current_task = summary
        self._current_site = "falconherbs.com"
        log.info("Director idle: %s", summary)


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

    def think(self, goal: str, context: dict = None) -> dict:
        """
        Director thinks about a goal and creates execution plan.
        Returns: {"plan": [...steps], "assigned_agents": [...], "estimated_time": "..."}
        """
        system_prompt = """You are the Director of Falcon Agency — a strategic mastermind.

Your job:
1. Break complex goals into clear actionable steps
2. Decide which agent should handle each step
3. Identify risks and dependencies
4. Estimate time for completion

Available Agents:
- Developer: SEO, uptime, performance, code fixes, technical tasks
- Strategist: Market analysis, content strategy, competitor research, business planning
- Media: Graphics, social media content, design, visual assets
- Backup: Data snapshots, restore, safety backups

Respond in JSON:
{
    "understanding": "what you understood from the goal",
    "plan": [
        {"step": 1, "action": "...", "agent": "developer|strategist|media|backup", "details": "..."},
        {"step": 2, "action": "...", "agent": "...", "details": "..."}
    ],
    "risks": ["..."],
    "estimated_time": "X minutes/hours",
    "needs_approval": true/false
}
"""

        context_str = json.dumps(context) if context else "No additional context"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Goal: {goal}\n\nContext: {context_str}"}
        ]
        
        response = call_ai("director", messages)
        
        try:
            return json.loads(response)
        except:
            return {"error": "Failed to parse plan", "raw": response}

    def execute_plan(self, plan: dict) -> list:
        """
        Executes each step of the plan by delegating to appropriate agent.
        Returns list of results.
        """
        results = []
        
        for step in plan.get("plan", []):
            agent_name = step.get("agent", "").lower()
            action = step.get("action", "")
            details = step.get("details", "")
            
            result = {
                "step": step.get("step"),
                "action": action,
                "agent": agent_name,
                "status": "pending"
            }
            
            try:
                if agent_name == "developer":
                    result["output"] = self._developer.execute(action, details)
                    result["status"] = "completed"
                elif agent_name == "strategist":
                    result["output"] = self._strategist.execute(action, details)
                    result["status"] = "completed"
                elif agent_name == "media":
                    result["output"] = self._media.execute(action, details)
                    result["status"] = "completed"
                elif agent_name == "backup":
                    result["output"] = self._backup.execute(action, details)
                    result["status"] = "completed"
                else:
                    result["output"] = f"Unknown agent: {agent_name}"
                    result["status"] = "failed"
            except Exception as e:
                result["output"] = str(e)
                result["status"] = "failed"
            
            results.append(result)
        
        return results

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
                        # On first startup, skip heavy long-interval tasks (daily/weekly/monthly).
                        # Only fire short-interval tasks immediately (uptime, heartbeat, etc.)
                        # Long-interval tasks start counting from now — will run at their next due time.
                        if interval >= 1440:  # >= 1 day → skip first run, start clock from now
                            # Write "now" as last_run so it schedules from this point forward
                            self._update_schedule_last_run(site, task_name)
                            is_due = False
                        else:
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

        _CRITICAL_TASKS = {"daily_backup", "site_health_check", "order_check", "vps_health_check", "content_package_weekly", "generate_weekly_content_package"}

        def _do_dispatch() -> dict:
            # --- SELF-LEARNING: Check for past failures ---
            lesson = learning.get_lesson(task, agent)
            if lesson:
                log.warning(f"Director: Task suggestion from experience: {lesson}")
                # We could even notify WhatsApp here if it's a persistent blocker

            if agent == "sentinel":
                return self._dispatch_sentinel(task, site, params)
            elif agent in ("developer", "strategist", "media", "backup"):
                return self._dispatch_dynamic_agent(agent, task, site, params)
            elif agent == "internal":
                return self._dispatch_internal(task, site, params)
            else:
                return {"status": "error", "message": f"Unknown agent: {agent}"}

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_dispatch)
                try:
                    result = future.result(timeout=AGENT_TIMEOUT)
                except concurrent.futures.TimeoutError:
                    error_msg = f"Agent {agent} timed out after {AGENT_TIMEOUT}s on task: {task}"
                    log.critical(error_msg)
                    log.log_action(
                        action="agent_timeout",
                        details={"agent": agent, "task": task, "site": site},
                        agent=agent,
                        status="timeout",
                    )
                    if task in _CRITICAL_TASKS:
                        self._send_alert(
                            f"⚠️ {agent} agent {AGENT_TIMEOUT}s mein complete nahi hua. "
                            f"Task: {task}. Retry queue mein daal diya hai."
                        )
                    if len(self._retry_queue) < 20:
                        self._retry_queue.append({"task": task, "site": site, "agent": agent})
                    result = {"status": "timeout", "error": error_msg}

            duration = time.monotonic() - dispatch_start

            # --- SELF-LEARNING: Update repository ---
            if result.get("status") in ("success", "ok", "complete", "done"):
                learning.record_success(task, agent)
            elif result.get("status") in ("error", "failed", "timeout"):
                learning.record_failure(task, result.get("error", "Unknown error"), agent)
                # Accumulate for daily failure digest (capped at 500 to prevent unbounded growth)
                if len(self._failure_log) < 500:
                    self._failure_log.append({
                        "ts": datetime.now().strftime("%H:%M"),
                        "agent": agent,
                        "task": task,
                        "status": result.get("status"),
                        "error": str(result.get("error", ""))[:120],
                    })

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

    # ── Internal dispatcher ──

    def _dispatch_internal(self, task: str, site: str, params: dict) -> dict:
        """Route internal non-agent tasks."""
        if task == "revenue_sync":
            try:
                # Add protocol if missing
                url = site if site.startswith("http") else f"https://{site}"
                woo = WooCommerceConnector(site_url=url)
                
                # Fetch recent orders
                orders_data = woo.get_orders(days_back=7, save=False)
                if not orders_data["success"]:
                    return {
                        "status": "error",
                        "error": f"WooCommerce failed: {orders_data.get('error')}"
                    }
                
                tracker = RevenueTracker()
                result = tracker.sync_from_woocommerce(orders_data)
                
                if "error" in result:
                    return {
                        "status": "error",
                        "error": f"Revenue sync error: {result['error']}"
                    }
                
                return {
                    "status": "success",
                    "message": f"Revenue synced successfully. {result.get('imported', 0)} new entries."
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": f"Internal task crash: {str(e)}"
                }
                
        return {"status": "error", "message": f"Unknown internal task: {task}"}

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
        # Look for the canonical class name first (e.g. "StrategistAgent"),
        # then fall back to any *Agent class — but never pick BaseAgent since
        # it raises NotImplementedError from execute().
        target_class_name = agent_name.title() + "Agent"  # e.g. "StrategistAgent"
        agent_class = None
        canonical = getattr(module, target_class_name, None)
        if canonical and isinstance(canonical, type) and hasattr(canonical, "execute"):
            agent_class = canonical
        else:
            for attr_name in dir(module):
                if attr_name == "BaseAgent":
                    continue
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
            # All agents use execute(action: str, details: str) signature
            import json as _json
            _details = f"site={site}"
            if params:
                _details += f", params={_json.dumps(params)}"
            result = instance.execute(action=task, details=_details)
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
        20-second timeout (SSL handshake from VPS can be slow).

        Env: MUTE_SITE_ALERTS=1 to silence site-down alerts (maintenance mode).
        Env: SITE_ALERT_COOLDOWN_MIN=30 to reduce alert frequency (default 10).
        """
        url = site if site.startswith("http") else f"https://{site}"
        start = time.monotonic()
        mute = os.environ.get("MUTE_SITE_ALERTS", "").strip().lower() in ("1", "true", "yes")
        cooldown_sec = int(os.environ.get("SITE_ALERT_COOLDOWN_MIN", "10")) * 60

        def _maybe_send_site_alert(msg: str) -> None:
            if not mute:
                self._send_alert(msg)

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
                self._site_down_count[site] = self._site_down_count.get(site, 0) + 1
                _now_mono_h = time.monotonic()
                _last_alert_h = self._site_last_alert.get(site, 0)
                _down_n_h = self._site_down_count[site]
                if _now_mono_h - _last_alert_h >= cooldown_sec:
                    self._site_last_alert[site] = _now_mono_h
                    if _down_n_h >= 3:
                        _maybe_send_site_alert(
                            f"🚨 URGENT: {site} has been down for 15+ min!\n"
                            f"HTTP {resp.status} | Down checks: {_down_n_h}\n"
                            f"Time: {_utcnow_iso()}"
                        )
                    else:
                        _maybe_send_site_alert(
                            f"🔴 SITE DOWN: {site}\n"
                            f"HTTP {resp.status}\n"
                            f"Time: {_utcnow_iso()}"
                        )
            else:
                if self._site_down_count.get(site, 0) > 0:
                    log.info("Site RECOVERED  |  %s  |  %dms", site, elapsed_ms)
                    self._site_down_count[site] = 0
                    self._site_last_alert[site] = 0
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
                self._site_down_count[site] = self._site_down_count.get(site, 0) + 1
                _now_mono_e = time.monotonic()
                _last_alert_e = self._site_last_alert.get(site, 0)
                _down_n_e = self._site_down_count[site]
                if _now_mono_e - _last_alert_e >= cooldown_sec:
                    self._site_last_alert[site] = _now_mono_e
                    if _down_n_e >= 3:
                        _maybe_send_site_alert(
                            f"🚨 URGENT: {site} has been down for 15+ min!\n"
                            f"HTTP {exc.code} | Down checks: {_down_n_e}\n"
                            f"Time: {_utcnow_iso()}"
                        )
                    else:
                        _maybe_send_site_alert(
                            f"🔴 SITE DOWN: {site}\n"
                            f"HTTP {exc.code}\n"
                            f"Time: {_utcnow_iso()}"
                        )
            else:
                if self._site_down_count.get(site, 0) > 0:
                    log.info("Site RECOVERED (HTTPError)  |  %s", site)
                    self._site_down_count[site] = 0
                    self._site_last_alert[site] = 0

            return {
                "status": level,
                "status_code": exc.code,
                "response_time_ms": elapsed_ms,
                "message": f"{site} returned HTTP {exc.code}",
            }

        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            log.warning("Site UNREACHABLE  |  %s  |  %s", site, exc)
            now_mono = time.monotonic()
            self._site_down_count[site] = self._site_down_count.get(site, 0) + 1
            _down_n_u = self._site_down_count[site]
            _last_alert_u = self._site_last_alert.get(site, 0)
            if now_mono - _last_alert_u >= cooldown_sec:
                self._last_unreachable_alert[site] = now_mono
                self._site_last_alert[site] = now_mono
                if _down_n_u >= 3:
                    _maybe_send_site_alert(
                        f"🚨 URGENT: {site} has been down for 15+ min!\n"
                        f"Error: {str(exc)[:150]}\n"
                        f"Down checks: {_down_n_u} | Time: {_utcnow_iso()}"
                    )
                else:
                    _maybe_send_site_alert(
                        f"🔴 SITE UNREACHABLE: {site}\n"
                        f"Error: {str(exc)[:200]}\n"
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

            # ── Idle detection (repeat every 60 min, not once total) ──
            idle_seconds = now - self._last_activity
            if idle_seconds > IDLE_ALERT_SECONDS:
                # Repeat alert every IDLE_ALERT_SECONDS (60 min)
                time_since_last = now - self._last_idle_alert_time
                if time_since_last >= IDLE_ALERT_SECONDS or self._last_idle_alert_time == 0:
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
                    self._last_idle_alert_time = now

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

            # ── 2. Scheduled tasks (merge retry queue + newly due) ──
            due_tasks = self.check_schedule()
            # Process retry queue first (tasks deferred when Director was busy)
            if self._retry_queue:
                retry_items = self._retry_queue[:MAX_TASKS_PER_CYCLE]
                self._retry_queue = self._retry_queue[MAX_TASKS_PER_CYCLE:]
                due_tasks = retry_items + due_tasks
                log.info("Retry queue: %d items this cycle", len(retry_items))
            if due_tasks:
                log.info("Due tasks this cycle: %d", len(due_tasks))

            tasks_completed = 0
            _MAX_RETRY_QUEUE = 20  # cap to avoid unbounded growth

            for idx, task_info in enumerate(due_tasks):
                # Time budget guard
                if time.monotonic() - cycle_start > CYCLE_TIME_BUDGET:
                    remaining = due_tasks[idx:]
                    if remaining and len(self._retry_queue) < _MAX_RETRY_QUEUE:
                        self._retry_queue = (
                            self._retry_queue + remaining
                        )[-_MAX_RETRY_QUEUE:]
                        log.warning(
                            "Cycle time budget (%.0fs) exceeded — "
                            "queued %d tasks for retry",
                            CYCLE_TIME_BUDGET, len(remaining),
                        )
                    break

                # Max tasks per cycle guard
                if tasks_completed >= MAX_TASKS_PER_CYCLE:
                    remaining = due_tasks[idx:]
                    if remaining and len(self._retry_queue) < _MAX_RETRY_QUEUE:
                        self._retry_queue = (
                            self._retry_queue + remaining
                        )[-_MAX_RETRY_QUEUE:]
                        log.info(
                            "Task-per-cycle cap (%d) reached — "
                            "queued %d for retry", MAX_TASKS_PER_CYCLE, len(remaining),
                        )
                    break

                task_name = task_info["task"]
                site      = task_info["site"]
                agent     = task_info["agent"]

                # Budget check
                estimated_cost = TASK_ESTIMATED_COST.get(task_name, 0.0)
                if estimated_cost > 0 and not self.check_budget(estimated_cost):
                    remaining = due_tasks[idx:]
                    if remaining and len(self._retry_queue) < _MAX_RETRY_QUEUE:
                        self._retry_queue = (
                            self._retry_queue + remaining
                        )[-_MAX_RETRY_QUEUE:]
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

            # ── 3. Goal processing (if time remains) ──
            goal = None
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

            cycle_duration = time.monotonic() - cycle_start

            # ── 4. Extended schedule check ──
            ext_ran = 0
            if self._extended_schedule:
                try:
                    ext_results = self._extended_schedule.check_and_execute(
                        whatsapp_sender=getattr(self._whatsapp, 'send_message', None)
                    )
                    ext_ran = len([
                        r for r in ext_results
                        if r["result"].get("success")
                    ])
                    for r in ext_results:
                        if r["result"].get("success"):
                            log.info("Extended task %s completed", r["task"])
                            # Keep _current_task updated with last extended task
                            self._current_task = "Completed: {}".format(
                                r["task"].replace("_", " ")
                            )
                            self._last_activity = time.monotonic()
                except Exception as e:
                    log.warning("Extended schedule check failed: %s", e)

            # ── 5. Idle monitoring ──
            # When truly nothing ran this cycle, run background checks
            # so the Director always has a meaningful status.
            goal_ran = goal is not None
            if tasks_completed == 0 and ext_ran == 0 and not goal_ran:
                self._run_idle_monitoring()

            # ── 6. Daily failure digest (sends at ~18:00 IST if any failures today) ──
            try:
                from datetime import datetime as _dt
                _now = _dt.now()
                _today_str = _now.strftime("%Y-%m-%d")
                # Send digest once per day after 18:00
                if (
                    _now.hour >= 18
                    and self._failure_digest_sent_date != _today_str
                    and self._failure_log
                ):
                    lines = [
                        f"  • {f['ts']} | {f['agent']}/{f['task']} → {f['status']}"
                        + (f": {f['error']}" if f['error'] else "")
                        for f in self._failure_log
                    ]
                    digest_msg = (
                        f"📋 *Director — Daily Failure Digest*\n"
                        f"─────────────────────\n"
                        f"Total failures today: {len(self._failure_log)}\n\n"
                        + "\n".join(lines)
                        + "\n\n_Auto-generated by Director. Check logs for details._"
                    )
                    self._send_alert(digest_msg)
                    self._failure_digest_sent_date = _today_str
                    self._failure_log.clear()
                    log.info("Failure digest sent (%d items)", len(lines))
                elif _today_str != self._failure_digest_sent_date and _now.hour < 1:
                    # Reset failure log at midnight for new day
                    self._failure_log.clear()
            except Exception as _de:
                log.warning("Failure digest check failed: %s", _de)

            log.info(
                "Cycle #%d complete  |  scheduled=%d  |  executed=%d  |"
                "  ext=%d  |  %.1fs",
                self._cycle_count,
                len(due_tasks),
                tasks_completed,
                ext_ran,
                time.monotonic() - cycle_start,
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
