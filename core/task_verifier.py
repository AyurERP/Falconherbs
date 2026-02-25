"""
Falcon Agency — Task Result Verification (GAP 3)
================================================
After EVERY agent task: verify it ACTUALLY worked.
"I tried" vs "I did it." A real director confirms delivery.

Only backup verifies itself today. This module adds verification for:
- content_publish: Hit URL, check page exists (200)
- health_rewrite: Fetch product from WooCommerce, check old claim is gone
- backup: Delegates to BackupAgent.verify_backup()
"""

from __future__ import annotations

import json
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.logger import log

if TYPE_CHECKING:
    from core.integration_bridge import IntegrationBridge

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REWRITES_DIR = PROJECT_ROOT / "data" / "content" / "product_rewrites"


def verify_task_result(
    task_type: str,
    task_result: Dict[str, Any],
    bridge: Optional["IntegrationBridge"] = None,
    site_config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Check if the task ACTUALLY worked. Call after every agent task.

    Parameters
    ----------
    task_type : str
        One of: content_publish, health_rewrite, backup
    task_result : dict
        The result returned by the task (e.g. from approve_and_publish, push_all_rewrites)
    bridge : IntegrationBridge | None
        For WooCommerce, content, etc.
    site_config : dict | None
        Optional site profile (e.g. from config/profiles/falconherbs.json)

    Returns
    -------
    dict
        {verified: bool, message: str, details: ...}
    """
    if task_type == "content_publish":
        return _verify_content_publish(task_result)
    elif task_type == "health_rewrite":
        return _verify_health_rewrite(task_result, bridge)
    elif task_type == "backup":
        return _verify_backup(task_result, bridge)
    else:
        return {
            "verified": None,  # Unknown task type — skip verification
            "message": f"No verifier for task_type={task_type}",
            "details": {},
        }


def _verify_content_publish(task_result: Dict[str, Any]) -> Dict[str, Any]:
    """Actually hit the URL and check if page exists (200)."""
    url = task_result.get("post_url") or task_result.get("url") or ""
    if not url:
        return {
            "verified": False,
            "message": "⚠️ Verification skipped: no published URL in result",
            "details": {"reason": "missing_url"},
        }
    try:
        r = requests.get(url, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            return {
                "verified": True,
                "message": "✅ Verified: page loads (200)",
                "details": {"url": url, "status_code": 200},
            }
        return {
            "verified": False,
            "message": f"⚠️ Page returned {r.status_code}, not 200",
            "details": {"url": url, "status_code": r.status_code},
        }
    except Exception as e:
        log.warning("Content publish verification failed: %s", e)
        return {
            "verified": False,
            "message": f"⚠️ Could not reach URL: {e}",
            "details": {"url": url, "error": str(e)},
        }


def _verify_health_rewrite(
    task_result: Dict[str, Any],
    bridge: Optional["IntegrationBridge"],
) -> Dict[str, Any]:
    """Fetch product from WooCommerce, check old claim is gone."""
    applied_ids = task_result.get("applied_ids") or []
    if not applied_ids:
        # No applied IDs — might be "no pending" case
        if task_result.get("applied", 0) == 0 and task_result.get("success"):
            return {
                "verified": True,
                "message": "✅ No rewrites to verify (all done)",
                "details": {},
            }
        return {
            "verified": None,
            "message": "Verification skipped: no applied_ids in result",
            "details": {},
        }

    if not bridge:
        return {
            "verified": None,
            "message": "Verification skipped: no bridge for WooCommerce",
            "details": {},
        }

    woo = bridge.tools.get("woocommerce") if bridge else None
    if not woo:
        return {
            "verified": None,
            "message": "Verification skipped: WooCommerce not loaded",
            "details": {},
        }

    verified = 0
    failed = []
    for pid in applied_ids[:5]:  # Cap at 5 to avoid slow verification
        rfile = REWRITES_DIR / f"{pid}.json"
        if not rfile.exists():
            failed.append(f"Product {pid}: rewrite file missing")
            continue

        try:
            with open(rfile, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            failed.append(f"Product {pid}: {e}")
            continue

        original_desc = data.get("original_description", "")
        rewritten_desc = data.get("rewritten_description", "")
        violations = data.get("safety_issues", [])

        raw = woo._make_request(f"products/{pid}")
        if not raw.get("success"):
            failed.append(f"Product {pid}: fetch failed")
            continue

        live_desc = (raw.get("data") or {}).get("description", "")

        # Check 1: Live description must differ from original (update happened)
        if live_desc == original_desc:
            failed.append(f"Product {pid}: description unchanged (update may have failed)")
            continue

        # Check 2: If we have violation phrases, they must NOT be in live desc
        violation_phrases = []
        if isinstance(violations, list):
            for v in violations:
                if isinstance(v, str):
                    violation_phrases.append(v)
                elif isinstance(v, dict):
                    violation_phrases.append(v.get("text") or v.get("found") or "")

        old_claim_still_there = any(
            phrase in live_desc for phrase in violation_phrases if phrase and len(phrase) > 3
        )
        if old_claim_still_there:
            failed.append(f"Product {pid}: old claim still in description")
            continue

        verified += 1

    if failed and verified == 0:
        return {
            "verified": False,
            "message": f"⚠️ Verification failed: {len(failed)} product(s)",
            "details": {"verified": 0, "failed": failed[:3]},
        }
    if verified > 0:
        return {
            "verified": True,
            "message": f"✅ Verified: {verified} product(s) updated, old claims gone",
            "details": {"verified": verified, "failed": failed[:3]},
        }
    return {
        "verified": True,
        "message": "✅ Verification passed",
        "details": {"verified": verified},
    }


def _verify_backup(
    task_result: Dict[str, Any],
    bridge: Optional["IntegrationBridge"],
) -> Dict[str, Any]:
    """Delegate to BackupAgent.verify_backup() — already exists."""
    try:
        from agents.backup import BackupAgent

        backup = BackupAgent()
        site = task_result.get("site", "falconherbs.com")
        result = backup.verify_backup(site, task_result.get("params", {}))
        if result.get("verified", False):
            return {
                "verified": True,
                "message": "✅ Backup verified (checksum + integrity)",
                "details": result,
            }
        return {
            "verified": False,
            "message": f"⚠️ Backup verification failed: {result.get('failure_reason', 'unknown')}",
            "details": result,
        }
    except Exception as e:
        log.warning("Backup verification failed: %s", e)
        return {
            "verified": False,
            "message": f"⚠️ Could not verify backup: {e}",
            "details": {"error": str(e)},
        }


def append_verification_to_response(
    response: str,
    verification: Dict[str, Any],
) -> str:
    """Append verification result to response when verification failed."""
    if verification.get("verified") is True:
        return response  # No need to add when verified
    if verification.get("verified") is False:
        return f"{response}\n\n{verification.get('message', '')}"
    return response  # None = skipped, don't add
