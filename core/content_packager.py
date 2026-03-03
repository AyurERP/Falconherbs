"""
core/content_packager.py — Social Content Package Delivery
===========================================================
HeroPost ke bina kaam karta hai. Agency weekly content create karti hai
aur ZIP file bana ke WhatsApp pe directly bhejti hai.

ZIP Contents:
  📄 UPLOAD_GUIDE.txt      → Step-by-step paste instructions
  📝 instagram_posts.txt   → All IG captions with hashtags
  📝 facebook_posts.txt    → FB posts (longer, more descriptive)
  📝 whatsapp_status.txt   → Short WA status messages
  📅 posting_schedule.txt  → What to post on which day/time
  🖼  images/              → AI-generated product images (if any)

How it works:
  1. Director calls create_weekly_package() with captions + images
  2. Packages everything into data/content_packages/YYYY-WW.zip
  3. Sends ZIP via WhatsApp: notifier.send_document(zip_path, caption)
  4. Also sends UPLOAD_GUIDE as a separate text message (easy reading)
"""

import os
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

PACKAGES_DIR = Path("data/content_packages")
PACKAGES_DIR.mkdir(parents=True, exist_ok=True)


class ContentPackager:
    """
    Bundles weekly social media content into a ZIP file
    and delivers to owner via WhatsApp.
    """

    BEST_TIMES = {
        # Platform: [(day, time_IST), ...]
        "instagram": [
            ("Monday",    "09:00"),
            ("Wednesday", "17:00"),
            ("Friday",    "12:00"),
            ("Sunday",    "11:00"),
        ],
        "facebook": [
            ("Tuesday",   "10:00"),
            ("Thursday",  "15:00"),
            ("Saturday",  "10:00"),
        ],
        "whatsapp_status": [
            ("Monday",    "08:00"),
            ("Wednesday", "08:00"),
            ("Friday",    "08:00"),
        ],
    }

    def create_weekly_package(
        self,
        posts: List[Dict],
        week_label: str = None,
        images: List[str] = None,
        send_via_whatsapp: bool = True,
    ) -> Dict:
        """
        Main entry point. Called by director with list of posts.

        posts format:
          [
            {
              "topic": "Ashwagandha Benefits",
              "ig_caption": "...",
              "fb_caption": "...",
              "wa_status": "...",
              "image_path": "data/images/ashwagandha.jpg"  # optional
            },
            ...
          ]

        Returns: {"success": bool, "zip_path": str, "whatsapp_sent": bool}
        """
        if not week_label:
            now = datetime.now()
            week_label = f"{now.strftime('%Y')}-W{now.strftime('%V')}"

        zip_path = PACKAGES_DIR / f"content_{week_label}.zip"

        try:
            # Build file contents
            ig_text    = self._build_platform_file(posts, "ig_caption",  "Instagram")
            fb_text    = self._build_platform_file(posts, "fb_caption",  "Facebook")
            wa_text    = self._build_platform_file(posts, "wa_status",   "WhatsApp Status")
            schedule   = self._build_schedule(posts, week_label)
            guide      = self._build_upload_guide(posts, week_label)

            # Create ZIP
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("UPLOAD_GUIDE.txt",      guide)
                zf.writestr("instagram_posts.txt",   ig_text)
                zf.writestr("facebook_posts.txt",    fb_text)
                zf.writestr("whatsapp_status.txt",   wa_text)
                zf.writestr("posting_schedule.txt",  schedule)

                # Add images if provided
                all_images = images or []
                for post in posts:
                    img = post.get("image_path", "")
                    if img and Path(img).exists():
                        all_images.append(img)

                for img_path in all_images:
                    p = Path(img_path)
                    if p.exists():
                        zf.write(p, f"images/{p.name}")

            # Save manifest
            manifest = {
                "week": week_label,
                "created": datetime.now().isoformat(),
                "posts_count": len(posts),
                "zip_path": str(zip_path),
                "images_count": len(all_images),
                "sent_via_whatsapp": False,
            }

            result = {
                "success": True,
                "zip_path": str(zip_path),
                "week": week_label,
                "posts_count": len(posts),
                "whatsapp_sent": False,
            }

            # Deliver via WhatsApp
            if send_via_whatsapp:
                wa_result = self._send_via_whatsapp(zip_path, posts, week_label, guide)
                result["whatsapp_sent"] = wa_result.get("sent", False)
                manifest["sent_via_whatsapp"] = result["whatsapp_sent"]

            # Save manifest JSON
            manifest_path = PACKAGES_DIR / f"content_{week_label}_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

            return result

        except Exception as e:
            return {"success": False, "error": str(e), "whatsapp_sent": False}

    def _send_via_whatsapp(self, zip_path: Path, posts: List[Dict],
                           week_label: str, guide: str) -> Dict:
        """Send ZIP as document + guide as text message."""
        try:
            from core.whatsapp import WhatsAppNotifier
            wa = WhatsAppNotifier()

            # 1. Send guide as text first (easy to read on phone)
            guide_preview = "\n".join(guide.split("\n")[:30])  # first 30 lines
            wa.send_message(
                f"📦 *WEEKLY CONTENT PACKAGE — {week_label}*\n"
                f"{'─' * 30}\n"
                f"📊 Posts this week: {len(posts)}\n"
                f"📱 Platforms: Instagram, Facebook, WhatsApp Status\n\n"
                f"{guide_preview}\n\n"
                f"⬇️ ZIP file bhej raha hoon — sab files iske andar hain:"
            )

            import time; time.sleep(1)

            # 2. Send ZIP as document
            caption = (
                f"📦 Content Week {week_label} | {len(posts)} posts | "
                f"Instagram + Facebook + WA Status + Schedule"
            )
            sent = wa.send_document(
                zip_path,
                caption=caption[:200],
                filename=f"FalconHerbs_Content_{week_label}.zip",
            )

            return {"sent": bool(sent)}

        except Exception as e:
            return {"sent": False, "error": str(e)}

    def _build_platform_file(self, posts: List[Dict], key: str, platform: str) -> str:
        """Build formatted text for one platform."""
        lines = [
            f"{'=' * 50}",
            f"🌿 FALCON HERBS — {platform.upper()} POSTS",
            f"Generated: {datetime.now().strftime('%d %b %Y')}",
            f"{'=' * 50}",
            "",
        ]
        for i, post in enumerate(posts, 1):
            caption = post.get(key, post.get("ig_caption", ""))
            if not caption:
                continue
            lines += [
                f"━━━ POST {i} — {post.get('topic', 'Content')} ━━━",
                caption,
                "",
                f"📅 Best time: {self._get_best_time(platform, i)}",
                "",
            ]
        return "\n".join(lines)

    def _build_schedule(self, posts: List[Dict], week_label: str) -> str:
        """Build day-by-day posting schedule."""
        # Get Monday of current week
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())

        lines = [
            f"📅 POSTING SCHEDULE — Week {week_label}",
            f"{'=' * 40}",
            "",
            "Copy-paste this into your calendar app:",
            "",
        ]

        ig_times  = self.BEST_TIMES["instagram"]
        fb_times  = self.BEST_TIMES["facebook"]
        wa_times  = self.BEST_TIMES["whatsapp_status"]

        # Map day name to date
        days = {
            "Monday":    monday,
            "Tuesday":   monday + timedelta(1),
            "Wednesday": monday + timedelta(2),
            "Thursday":  monday + timedelta(3),
            "Friday":    monday + timedelta(4),
            "Saturday":  monday + timedelta(5),
            "Sunday":    monday + timedelta(6),
        }

        schedule = {}
        for day, t in ig_times[:len(posts)]:
            schedule.setdefault(day, []).append(f"📸 Instagram {t} IST")
        for day, t in fb_times[:len(posts)]:
            schedule.setdefault(day, []).append(f"📘 Facebook {t} IST")
        for day, t in wa_times[:len(posts)]:
            schedule.setdefault(day, []).append(f"💬 WA Status {t} IST")

        for day_name in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]:
            date = days[day_name]
            day_items = schedule.get(day_name, [])
            if day_items:
                lines.append(f"─── {day_name.upper()} {date.strftime('%d %b')} ───")
                for item in day_items:
                    lines.append(f"  ✅ {item}")
                lines.append("")

        return "\n".join(lines)

    def _build_upload_guide(self, posts: List[Dict], week_label: str) -> str:
        """Build step-by-step guide for manual uploading."""
        lines = [
            f"🌿 FALCON HERBS — WEEKLY CONTENT GUIDE",
            f"Week: {week_label} | {datetime.now().strftime('%d %b %Y')}",
            f"{'=' * 50}",
            "",
            f"📦 IS PACKAGE MEIN HAI:",
            f"  1. instagram_posts.txt  — {len(posts)} Instagram captions",
            f"  2. facebook_posts.txt   — {len(posts)} Facebook posts",
            f"  3. whatsapp_status.txt  — WA status messages",
            f"  4. posting_schedule.txt — Kab kya post karna hai",
            f"  5. images/              — Product images (agar hain)",
            "",
            f"📱 INSTAGRAM UPLOAD (Manual Steps):",
            f"  1. instagram_posts.txt kholo",
            f"  2. POST 1 copy karo",
            f"  3. Instagram → New Post → Image select karo",
            f"  4. Caption paste karo",
            f"  5. Share karo — schedule wale time pe!",
            "",
            f"📘 FACEBOOK UPLOAD:",
            f"  1. facebook_posts.txt kholo",
            f"  2. Copy karo, Facebook Page → Create Post → Paste",
            f"  3. Ya Meta Business Suite mein schedule kar sakte ho",
            "",
            f"💬 WHATSAPP STATUS:",
            f"  1. whatsapp_status.txt kholo",
            f"  2. Copy karo, WA → Status → Text → Paste",
            "",
            f"⏰ BEST POSTING TIMES (IST):",
            f"  Instagram: Mon/Wed/Fri/Sun — 9am, 5pm, 12pm, 11am",
            f"  Facebook:  Tue/Thu/Sat    — 10am, 3pm, 10am",
            f"  WA Status: Mon/Wed/Fri    — 8am",
            "",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Koi bhi post change karni ho main hoon — bolo!",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        return "\n".join(lines)

    def _get_best_time(self, platform: str, post_num: int) -> str:
        """Get recommended posting time for platform."""
        platform_lower = platform.lower()
        if "instagram" in platform_lower:
            times = self.BEST_TIMES["instagram"]
        elif "facebook" in platform_lower:
            times = self.BEST_TIMES["facebook"]
        else:
            times = self.BEST_TIMES["whatsapp_status"]
        t = times[(post_num - 1) % len(times)]
        return f"{t[0]} {t[1]} IST"

    def send_individual_post(self, post: Dict, post_num: int = 1) -> Dict:
        """
        Send a single post's content via WhatsApp (for immediate sharing).
        Useful when director generates one post and wants to share it instantly.
        """
        try:
            from core.whatsapp import WhatsAppNotifier
            wa = WhatsAppNotifier()

            topic   = post.get("topic", "Content")
            ig_cap  = post.get("ig_caption", "")
            fb_cap  = post.get("fb_caption", "")
            wa_st   = post.get("wa_status", "")

            msg = (
                f"📱 *POST #{post_num} — {topic}*\n"
                f"{'─' * 30}\n\n"
                f"📸 *INSTAGRAM:*\n{ig_cap}\n\n"
            )
            if fb_cap and fb_cap != ig_cap:
                msg += f"📘 *FACEBOOK:*\n{fb_cap}\n\n"
            if wa_st:
                msg += f"💬 *WA STATUS:*\n{wa_st}\n\n"
            msg += f"📅 Best time: {self._get_best_time('instagram', post_num)}"

            wa.send_message(msg)

            # Send image if available
            img = post.get("image_path", "")
            if img and Path(img).exists():
                wa.send_document(img, caption=f"🖼 {topic} — Post Image")

            return {"success": True, "sent": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_package_list(self) -> List[Dict]:
        """List all generated content packages."""
        packages = []
        for p in sorted(PACKAGES_DIR.glob("*.zip"), reverse=True)[:10]:
            stat = p.stat()
            packages.append({
                "file": p.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "created": datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y %H:%M"),
            })
        return packages


# Singleton
content_packager = ContentPackager()
