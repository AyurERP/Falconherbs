"""
core/changelog_manager.py — Falcon Agency Change Audit Trail
=============================================================

Every time the agency modifies data on falconherbs.com (products,
blog posts, categories, pages), it MUST record a changelog entry
with before/after values.

This provides:
  • Full audit trail — who changed what and when
  • Rollback capability — every original is saved
  • WhatsApp reports — human-readable summaries
  • File reports — detailed TXT files sent via WhatsApp

File layout:
  data/reports/
    changelog_YYYY-MM-DD.json         ← daily log (all changes)
    report_YYYY-MM-DD_HH-MM-SS.txt   ← human-readable report file
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


REPORTS_DIR = Path("data/reports")


class ChangelogManager:
    """
    Records before/after for every agency-applied change.

    Usage:
        cm = ChangelogManager()
        cm.record("product", product_id, product_name,
                  field="description",
                  before=old_text, after=new_text)
        cm.save_report()   # generates .txt report file
    """

    def __init__(self) -> None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self._session_changes: List[Dict] = []
        self._session_start = datetime.now()

    # ── Record a single change ─────────────────────────────────────

    def record(
        self,
        change_type: str,       # "product", "blog_post", "page", "category"
        item_id: Any,
        item_name: str,
        field: str,             # "description", "title", "name", etc.
        before: str,
        after: str,
        url: str = "",
    ) -> None:
        """Record a single before/after change."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": change_type,
            "id": item_id,
            "name": item_name,
            "field": field,
            "url": url,
            "before": before,
            "after": after,
            "chars_before": len(before),
            "chars_after": len(after),
        }
        self._session_changes.append(entry)
        self._append_to_daily_log(entry)

    # ── Save to daily JSON log ─────────────────────────────────────

    def _append_to_daily_log(self, entry: Dict) -> None:
        """Append to data/reports/changelog_YYYY-MM-DD.json."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = REPORTS_DIR / f"changelog_{today}.json"

        existing = []
        if log_file.exists():
            try:
                existing = json.loads(log_file.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        existing.append(entry)
        log_file.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Generate human-readable TXT report ────────────────────────

    def save_report(
        self,
        title: str = "FALCON AGENCY — CHANGE REPORT",
    ) -> Path:
        """
        Generate a full before/after TXT report for this session.
        Saves to data/reports/report_TIMESTAMP.txt.
        Returns the file path.
        """
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
        report_file = REPORTS_DIR / f"report_{timestamp_str}.txt"

        changes = self._session_changes
        total = len(changes)

        # Header
        lines = [
            "=" * 70,
            f"  {title}",
            f"  Generated: {now.strftime('%d %b %Y at %I:%M %p')}",
            f"  Total Changes: {total}",
            "=" * 70,
            "",
        ]

        # Group by type
        by_type: Dict[str, List[Dict]] = {}
        for c in changes:
            ct = c["type"]
            by_type.setdefault(ct, []).append(c)

        for change_type, items in by_type.items():
            section_title = {
                "product": "PRODUCT DESCRIPTIONS",
                "blog_post": "BLOG POST TITLES",
                "page": "WORDPRESS PAGES",
                "category": "CATEGORY NAMES",
            }.get(change_type, change_type.upper())

            lines.append(f"{'─' * 70}")
            lines.append(f"  {section_title} ({len(items)} changes)")
            lines.append(f"{'─' * 70}")
            lines.append("")

            for i, c in enumerate(items, 1):
                lines.append(f"[{i}] {c['name']}")
                if c.get("url"):
                    lines.append(f"    URL: {c['url']}")
                lines.append(f"    Field: {c['field']}")
                lines.append("")

                # Before
                before_text = c["before"][:800] if c["before"] else "(empty)"
                lines.append("  BEFORE:")
                for ln in before_text.split("\n")[:15]:
                    lines.append(f"    {ln}")
                if len(c["before"]) > 800:
                    lines.append(f"    ... [{c['chars_before']} chars total]")
                lines.append("")

                # After
                after_text = c["after"][:800] if c["after"] else "(empty)"
                lines.append("  AFTER:")
                for ln in after_text.split("\n")[:15]:
                    lines.append(f"    {ln}")
                if len(c["after"]) > 800:
                    lines.append(f"    ... [{c['chars_after']} chars total]")
                lines.append("")
                lines.append("")

        # Footer
        lines += [
            "=" * 70,
            "  Falcon Agency — Automated Compliance Fix",
            f"  All changes recorded in: data/reports/changelog_{now.strftime('%Y-%m-%d')}.json",
            "=" * 70,
        ]

        report_file.write_text("\n".join(lines), encoding="utf-8")
        return report_file

    # ── WhatsApp-friendly short summary ───────────────────────────

    def get_whatsapp_summary(self, task_name: str = "Health Fix") -> str:
        """Short WhatsApp summary of all changes in this session."""
        changes = self._session_changes
        total = len(changes)
        if not total:
            return f"✅ {task_name}\nNo changes were needed."

        by_type: Dict[str, int] = {}
        for c in changes:
            by_type[c["type"]] = by_type.get(c["type"], 0) + 1

        type_labels = {
            "product": "Product descriptions",
            "blog_post": "Blog post titles",
            "page": "Pages",
            "category": "Category names",
        }

        lines = [
            f"✅ *{task_name} Complete*",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📋 Total changes: *{total}*",
            "",
        ]
        for ct, count in by_type.items():
            label = type_labels.get(ct, ct)
            lines.append(f"  ✔️ {label}: {count}")

        # List first 10 items
        lines.append("")
        lines.append("📝 *Changed:*")
        for c in changes[:10]:
            lines.append(f"  • {c['name'][:50]}")
        if total > 10:
            lines.append(f"  ... and {total - 10} more")

        lines += [
            "",
            f"📂 Full report: data/reports/",
            f"⏱ {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        ]

        return "\n".join(lines)

    # ── Session info ───────────────────────────────────────────────

    @property
    def change_count(self) -> int:
        return len(self._session_changes)

    @property
    def changes(self) -> List[Dict]:
        return self._session_changes.copy()

    # ── Aliases for Windsurf spec compatibility ──
    def record_change(
        self,
        product_id: Any,
        field: str,
        before_value: str,
        after_value: str,
        status: str = "applied",
    ) -> None:
        """Alias for record() — compatibility with push_all_rewrites."""
        self.record(
            "product", product_id, str(product_id),
            field=field, before=before_value, after=after_value,
        )

    def generate_summary(self, task_name: str = "Health Fix") -> str:
        """Alias for get_whatsapp_summary()."""
        return self.get_whatsapp_summary(task_name)

    def generate_report_file(self, title: str = "FALCON AGENCY — CHANGE REPORT") -> Path:
        """Alias for save_report(). Returns path to generated report file."""
        return self.save_report(title=title)
