"""
FALCON AGENCY — main.py
Run this to start the entire agency.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')

# Create required directories before anything else (fresh install resilience)
REQUIRED_DIRS = [
    "data",
    "data/goals",
    "data/content",
    "data/content/weekly_packages",
    "data/content/product_rewrites",
    "data/content/email_campaigns",
    "data/backups",
    "data/health_audit",
    "data/revenue",
    "data/reports",
    "data/woocommerce",
    "config/profiles",
    "assets",
]
for d in REQUIRED_DIRS:
    os.makedirs(d, exist_ok=True)

from config.keys import KeyVault
from config.settings import AgencySettings, IS_PRODUCTION
from config.safety import SafetyGuard
from core.logger import log
from core.approval import ApprovalSystem
from core.sentinel import Sentinel
from core.director import Director


def run_system_check() -> bool:
    """Run pre-flight checks before starting Director loop."""
    log.info("=" * 65)
    log.info("FALCON AGENCY — Starting up")
    log.info("=" * 65)

    checks = []

    # 1. KeyVault
    try:
        vault = KeyVault()
        log.info("[OK] KeyVault — credentials loaded from .env")
        checks.append(True)
    except Exception as e:
        log.critical(f"[FAIL] KeyVault — {e}")
        checks.append(False)

    # 2. Settings
    try:
        settings = AgencySettings()
        log.info(f"[OK] Settings — production={IS_PRODUCTION}")
        checks.append(True)
    except Exception as e:
        log.critical(f"[FAIL] Settings — {e}")
        checks.append(False)

    # 3. SafetyGuard
    try:
        safety = SafetyGuard()
        log.info("[OK] SafetyGuard — active")
        checks.append(True)
    except Exception as e:
        log.critical(f"[FAIL] SafetyGuard — {e}")
        checks.append(False)

    # 4. ApprovalSystem
    try:
        approval = ApprovalSystem()
        log.info("[OK] ApprovalSystem — WhatsApp connected")
        checks.append(True)
    except Exception as e:
        log.critical(f"[FAIL] ApprovalSystem — {e}")
        checks.append(False)

    # 5. Sentinel
    try:
        sentinel = Sentinel(approval)
        log.info("[OK] Sentinel — security watchdog ready")
        checks.append(True)
    except Exception as e:
        log.critical(f"[FAIL] Sentinel — {e}")
        checks.append(False)

    # 6. Goals file (create if missing)
    try:
        goals_path = Path("data/goals.json")
        if not goals_path.exists():
            default_goals = {
                "goals": [],
                "created_at": datetime.now().isoformat(),
                "note": "Auto-created on first run",
            }
            goals_path.parent.mkdir(parents=True, exist_ok=True)
            goals_path.write_text(json.dumps(default_goals, indent=2))
            goals = default_goals
            log.info("[OK] Goals — auto-created empty goals.json")
        else:
            goals = json.loads(goals_path.read_text())
            # Accept both formats: legacy list [] OR new dict {"goals": [...]}
            if isinstance(goals, list):
                goal_count = len(goals)
            else:
                goal_count = len(goals.get('goals', []))
            log.info(f"[OK] Goals — {goal_count} goals loaded")
        checks.append(True)
    except Exception as e:
        log.critical(f"[FAIL] Goals file — {e}")
        checks.append(False)

    # 7. Site profile (create if missing)
    try:
        profile_path = Path("config/profiles/falconherbs.json")
        if not profile_path.exists():
            default_profile = {
                "identity": {
                    "site_id": "falconherbs",
                    "name": "Falcon Herbs",
                    "url": "",
                    "status": "needs_configuration",
                },
                "note": "Auto-created. Owner needs to fill in URL and credentials.",
            }
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(json.dumps(default_profile, indent=2))
            profile = default_profile
            log.warning("[OK] Profile — auto-created. Some features won't work until configured.")
        else:
            profile = json.loads(profile_path.read_text())
            log.info(f"[OK] Profile — {profile.get('identity', {}).get('url', '?')} loaded")
        checks.append(True)
    except Exception as e:
        log.critical(f"[FAIL] Site profile — {e}")
        checks.append(False)

    log.info("=" * 65)
    passed = sum(checks)
    total = len(checks)

    if all(checks):
        log.info(f"[FALCON] All systems nominal ({passed}/{total})")
        log.info("=" * 65)
        return True
    else:
        log.critical(f"[FALCON] {total - passed} system(s) failed — cannot start")
        log.info("=" * 65)
        return False


if __name__ == "__main__":

    if "--check" in sys.argv:
        # Just run system check, don't start Director loop
        ok = run_system_check()
        sys.exit(0 if ok else 1)

    # Full startup
    ok = run_system_check()
    if not ok:
        log.critical("Pre-flight failed. Fix errors above before starting.")
        sys.exit(1)

    log.info("[FALCON] Starting Director loop...")
    log.info("[FALCON] Press Ctrl+C to stop safely")
    log.info("=" * 65)

    director = Director()
    director.run()
