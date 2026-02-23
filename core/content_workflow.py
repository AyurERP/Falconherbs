"""
Falcon Agency -- Content Workflow Orchestrator
================================================
End-to-end: Generate -> Safety -> Image -> Queue ->
            WhatsApp Preview -> Approve -> Publish

This module connects ContentPipeline + HealthScanner +
ImageGenerator + WordPressPublisher into a single
automated pipeline.

Safety: All content runs through health claims safety
check. Nothing publishes without owner approval.
"""

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict


# Evergreen topics for Ayurvedic content
EVERGREEN_TOPICS = [
    {"topic": "Complete Guide to Ashwagandha Benefits",
     "keyword": "ashwagandha benefits",
     "product": "Ashwagandha"},
    {"topic": "Ayurvedic Morning Routine for Better Health",
     "keyword": "ayurvedic morning routine",
     "product": None},
    {"topic": "Triphala Benefits: Ancient Digestive Support",
     "keyword": "triphala benefits",
     "product": "Triphala"},
    {"topic": "Natural Hair Care with Bhringraj",
     "keyword": "bhringraj for hair",
     "product": "Bhringraj"},
    {"topic": "Tulsi: The Queen of Herbs",
     "keyword": "tulsi benefits",
     "product": "Tulsi"},
    {"topic": "Neem for Skin: Traditional Ayurvedic Remedy",
     "keyword": "neem for skin",
     "product": "Neem"},
    {"topic": "Shatavari: Women's Health in Ayurveda",
     "keyword": "shatavari benefits",
     "product": "Shatavari"},
    {"topic": "Brahmi for Memory and Focus",
     "keyword": "brahmi benefits",
     "product": "Brahmi"},
    {"topic": "How to Choose Quality Ayurvedic Products",
     "keyword": "quality ayurvedic products",
     "product": None},
    {"topic": "Moringa: The Miracle Tree of Ayurveda",
     "keyword": "moringa benefits",
     "product": "Moringa"},
    {"topic": "Amla: Indian Gooseberry for Hair and Immunity",
     "keyword": "amla benefits",
     "product": "Amla"},
    {"topic": "Giloy for Immunity: Ayurvedic Powerhouse",
     "keyword": "giloy benefits",
     "product": "Giloy"},
    {"topic": "Arjuna Bark for Heart Health",
     "keyword": "arjuna bark benefits",
     "product": "Arjuna"},
    {"topic": "Best Mouth Fresheners: Indian Mukhwas Guide",
     "keyword": "indian mouth freshener",
     "product": None},
    {"topic": "Ayurvedic Face Packs for Glowing Skin",
     "keyword": "ayurvedic face pack",
     "product": None},
    {"topic": "Licorice Root Benefits in Ayurveda",
     "keyword": "licorice root benefits",
     "product": "Licorice"},
]


class ContentWorkflow:
    """
    End-to-end content workflow manager.
    Connects ContentPipeline + HealthScanner +
    ImageGenerator + WordPressPublisher.
    """

    def __init__(self, bridge):
        self.bridge = bridge
        self.queue_file = Path("data/content/content_queue.json")
        self._init_queue()

    def _init_queue(self):
        if not self.queue_file.exists():
            self.queue_file.parent.mkdir(
                parents=True, exist_ok=True
            )
            self._save_queue({
                "queue": [],
                "stats": {
                    "total_generated": 0,
                    "total_published": 0,
                    "total_rejected": 0
                }
            })

    def _load_queue(self):
        try:
            with open(self.queue_file, "r",
                       encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"queue": [], "stats": {}}

    def _save_queue(self, data):
        tmp = str(self.queue_file) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        Path(tmp).replace(self.queue_file)

    # ========= CORE WORKFLOW =========

    def generate_and_queue(self, topic, keyword,
                           product=None):
        """Full workflow: generate -> safety -> image ->
        queue for approval"""
        pipeline = self.bridge.tools.get("content")
        image_gen = self.bridge.tools.get("image")

        if not pipeline:
            return {
                "success": False,
                "error": "Content Pipeline not loaded"
            }

        # Step 1: Generate blog content via AI
        result = pipeline.create_blog_draft(
            topic=topic,
            target_keyword=keyword,
            product_name=product
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": "Blog generation failed: {}".format(
                    result.get("error", "unknown")
                )
            }

        draft = result["draft"]
        draft_file = result.get("file", "")

        # If prompt_only, AI client was not available
        if draft.get("status") == "prompt_only":
            return {
                "success": False,
                "error": "AI client not connected - "
                         "content is prompt_only"
            }

        # Step 2: Generate featured image
        image_file = None
        if image_gen and draft.get("content"):
            try:
                img_result = image_gen.generate(
                    prompt=(
                        "Ayurvedic herbs, {}, natural "
                        "wellness, premium product "
                        "photography, warm earthy tones, "
                        "clean background".format(topic)
                    ),
                    style="blog_banner",
                    width=1200,
                    height=630
                )
                if img_result and img_result.get("success"):
                    image_file = img_result.get("file")
            except Exception:
                pass  # Image failure should not block content

        # Step 3: Add to queue
        content_id = "content_{}".format(
            datetime.now().strftime('%Y%m%d_%H%M%S')
        )
        queue_entry = {
            "id": content_id,
            "type": "blog",
            "topic": topic,
            "keyword": keyword,
            "product": product,
            "draft_file": draft_file,
            "image_file": image_file,
            "status": draft.get("status", "generated"),
            "safety_passed": draft.get(
                "safety_check", {}
            ).get("is_safe", False),
            "safety_issues": draft.get(
                "safety_check", {}
            ).get("changes", []),
            "word_count": len(
                (draft.get("content") or "").split()
            ),
            "created_at": datetime.now().isoformat(),
            "approved_at": None,
            "published_at": None,
            "wp_url": None,
            "wp_post_id": None
        }

        queue = self._load_queue()
        queue["queue"].append(queue_entry)
        queue["stats"]["total_generated"] = queue["stats"].get(
            "total_generated", 0
        ) + 1
        self._save_queue(queue)

        return {
            "success": True,
            "entry": queue_entry,
            "message": (
                "\U0001F4DD *NEW BLOG QUEUED*\n"
                "\U0001F4CB Topic: {}\n"
                "\U0001F50D Keyword: {}\n"
                "{}"
                "\U0001F4CA Words: ~{}\n"
                "\U0001F6E1 Safety: {}\n\n"
                "Reply 'drafts dikhao' to preview\n"
                "Reply 'publish karo' to publish".format(
                    topic, keyword,
                    "\U0001F5BC Image: YES\n"
                    if image_file else "",
                    queue_entry["word_count"],
                    "PASSED" if queue_entry["safety_passed"]
                    else "NEEDS REVIEW"
                )
            )
        }

    def approve(self, content_id):
        """Mark content as approved"""
        queue = self._load_queue()
        for entry in queue["queue"]:
            if entry["id"] == content_id:
                entry["status"] = "approved"
                entry["approved_at"] = (
                    datetime.now().isoformat()
                )
                self._save_queue(queue)
                return {
                    "success": True,
                    "message": "Content approved: {}".format(
                        entry["topic"]
                    )
                }
        return {"success": False, "error": "Content not found"}

    def approve_and_publish(self, content_id=None,
                            as_draft=True):
        """Approve and publish to WordPress.
        If content_id is None, publishes the latest
        generated/approved draft."""
        wp = self.bridge.tools.get("wp")
        if not wp:
            return {
                "success": False,
                "error": "WordPress Publisher not loaded"
            }

        queue = self._load_queue()

        # Find the target entry
        target = None
        if content_id:
            for entry in queue["queue"]:
                if entry["id"] == content_id:
                    target = entry
                    break
        else:
            # Find latest publishable draft
            for entry in reversed(queue["queue"]):
                if entry["status"] in (
                    "generated", "approved", "needs_review"
                ):
                    target = entry
                    break

        if not target:
            return {
                "success": False,
                "error": "No publishable content found"
            }

        # Publish to WordPress
        try:
            result = wp.publish_draft(
                draft_name=target.get("draft_file"),
                as_draft=as_draft
            )

            if result.get("success"):
                target["status"] = "published"
                target["published_at"] = (
                    datetime.now().isoformat()
                )
                target["wp_url"] = result.get("post_url")
                target["wp_post_id"] = result.get("post_id")
                queue["stats"]["total_published"] = (
                    queue["stats"].get(
                        "total_published", 0
                    ) + 1
                )
                self._save_queue(queue)

                return {
                    "success": True,
                    "post_url": result.get("post_url"),
                    "post_id": result.get("post_id"),
                    "message": (
                        "\u2705 *BLOG PUBLISHED!*\n"
                        "\U0001F4CB {}\n"
                        "\U0001F517 {}\n"
                        "{}"
                    ).format(
                        target["topic"],
                        result.get("post_url", "?"),
                        "(as WP draft)"
                        if as_draft else "(LIVE!)"
                    )
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown")
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    # ========= TOPIC PICKER =========

    def pick_next_topic(self):
        """
        Pick the next topic that hasn't been generated recently.

        Priority order (highest → lowest):
          1. AEO content gaps  — topics where Falcon Herbs is
             missing from AI search results (auto-fed by AEOAgent)
          2. Content calendar  — today's scheduled topic
          3. Evergreen list    — curated Ayurvedic topics
          4. Cycle-back        — restart from top of evergreen list
        """
        queue = self._load_queue()
        used_topics = {
            e.get("topic", "").lower()
            for e in queue["queue"]
        }

        # ── Priority 1: AEO content gaps ─────────────────
        try:
            gaps_file = Path("data/aeo/content_gaps.json")
            if gaps_file.exists():
                gaps = json.loads(
                    gaps_file.read_text(encoding="utf-8")
                )
                for gap in gaps:
                    if (not gap.get("used", False)
                            and gap.get("topic", "").lower()
                            not in used_topics):
                        # Mark as used so we don't repeat
                        gap["used"] = True
                        gap["used_date"] = (
                            datetime.now().isoformat()
                        )
                        gaps_file.write_text(
                            json.dumps(gaps, indent=2,
                                       ensure_ascii=False),
                            encoding="utf-8",
                        )
                        return (
                            gap["topic"],
                            gap.get("keyword",
                                    gap["topic"].lower()),
                            None,  # AEO gaps don't map to a
                                   # specific product
                        )
        except Exception:
            pass

        # ── Priority 2: Content calendar ─────────────────
        try:
            calendar_dir = Path("data/content/calendar")
            today = datetime.now().strftime("%Y%m%d")
            cal_file = calendar_dir / "calendar_{}.json".format(
                today
            )
            if cal_file.exists():
                with open(cal_file, "r") as f:
                    cal = json.load(f)
                for item in cal.get("items", []):
                    if item.get("topic", "").lower() \
                            not in used_topics:
                        return (
                            item["topic"],
                            item.get("keyword", ""),
                            item.get("product")
                        )
        except Exception:
            pass

        # ── Priority 3: Evergreen topics ─────────────────
        for t in EVERGREEN_TOPICS:
            if t["topic"].lower() not in used_topics:
                return (
                    t["topic"],
                    t["keyword"],
                    t.get("product")
                )

        # ── Priority 4: Cycle back ────────────────────────
        if EVERGREEN_TOPICS:
            t = EVERGREEN_TOPICS[0]
            return t["topic"], t["keyword"], t.get("product")

        return (
            "Benefits of Ayurvedic Herbs",
            "ayurvedic herbs",
            None
        )

    # ========= QUEUE STATUS =========

    def get_queue_status(self):
        """WhatsApp-friendly queue summary"""
        queue = self._load_queue()
        statuses = {}
        for entry in queue["queue"]:
            s = entry.get("status", "unknown")
            statuses[s] = statuses.get(s, 0) + 1

        total = len(queue["queue"])
        if total == 0:
            return (
                "\U0001F4CB *CONTENT QUEUE*\n"
                "\u2500" * 25 + "\n"
                "Queue is empty. Send 'blog likh' "
                "to generate."
            )

        icons = {
            "generated": "\U0001F535",
            "needs_review": "\U0001F7E1",
            "approved": "\U0001F7E2",
            "published": "\u2705",
            "rejected": "\u274C",
        }
        lines = [
            "\U0001F4CB *CONTENT QUEUE* ({})".format(total),
            "\u2500" * 25
        ]
        for status, count in statuses.items():
            icon = icons.get(status, "\u2753")
            lines.append(
                "{} {}: {}".format(icon, status, count)
            )

        stats = queue.get("stats", {})
        lines.append("\n\U0001F4CA Generated: {} | "
                     "Published: {}".format(
                         stats.get("total_generated", 0),
                         stats.get("total_published", 0)
                     ))

        return "\n".join(lines)

    def get_latest_drafts(self, count=5):
        """Get latest drafts for WhatsApp preview"""
        queue = self._load_queue()
        recent = queue["queue"][-count:]
        if not recent:
            return "No drafts in queue."

        lines = [
            "\U0001F4DD *RECENT DRAFTS*",
            "\u2500" * 25
        ]
        for i, entry in enumerate(reversed(recent), 1):
            icon = {
                "generated": "\U0001F535",
                "needs_review": "\U0001F7E1",
                "approved": "\U0001F7E2",
                "published": "\u2705"
            }.get(entry.get("status"), "\u2753")
            lines.append(
                "{}. {} {} (~{} words)".format(
                    i, icon, entry.get("topic", "?"),
                    entry.get("word_count", 0)
                )
            )
            if entry.get("wp_url"):
                lines.append(
                    "   \U0001F517 {}".format(entry["wp_url"])
                )

        return "\n".join(lines)

    def reject(self, content_id):
        """Reject a content piece"""
        queue = self._load_queue()
        for entry in queue["queue"]:
            if entry["id"] == content_id:
                entry["status"] = "rejected"
                queue["stats"]["total_rejected"] = (
                    queue["stats"].get(
                        "total_rejected", 0
                    ) + 1
                )
                self._save_queue(queue)
                return {
                    "success": True,
                    "message": "Rejected: {}".format(
                        entry["topic"]
                    )
                }
        return {"success": False, "error": "Not found"}


# ==================== TEST ====================

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..')
    ))

    print("Testing ContentWorkflow...")

    from core.integration_bridge import IntegrationBridge
    bridge = IntegrationBridge()
    workflow = ContentWorkflow(bridge)

    # Test topic picker
    topic, keyword, product = workflow.pick_next_topic()
    print("Next topic: {} | {} | {}".format(
        topic, keyword, product
    ))

    # Test queue status
    print("\n{}".format(workflow.get_queue_status()))

    print("\nContentWorkflow test complete!")
