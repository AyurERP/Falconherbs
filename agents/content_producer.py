"""
Content Producer Agent — Creates complete weekly content packages
ready for manual upload to HeroPost.io and NetworkSolutions.

Output: data/content/weekly_packages/week_YYYY_WW/
Owner uploads manually. No browser automation.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import log
from core.ai_client import call_ai

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = PROJECT_ROOT / "data" / "content" / "weekly_packages"
SINGLE_VIDEOS_DIR = PROJECT_ROOT / "data" / "content" / "single_videos"
EMAIL_CAMPAIGNS_DIR = PROJECT_ROOT / "data" / "content" / "email_campaigns"


class ContentProducer:
    """
    Creates complete weekly content packages ready for manual upload.
    Uses NVIDIA for captions, NVIDIA for images, moviepy for video.
    """

    def __init__(
        self,
        brand_guidelines: Optional[Dict] = None,
        woo_connector=None,
        image_generator=None,
        video_creator=None,
        health_scanner=None,
    ):
        self.brand = self._load_brand_guidelines(brand_guidelines)
        self.woo = woo_connector
        self.image_gen = image_generator
        self.video_creator = video_creator or self._video_creator_default()
        self._health_scanner = health_scanner
        self._images_today = 0
        self._MAX_IMAGES_PER_DAY = 50
        if not health_scanner:
            log.warning("ContentProducer: HealthClaimsScanner not available — banned_words only")

    def _load_brand_guidelines(self, brand: Optional[Dict]) -> Dict:
        """Load brand guidelines from file or dict."""
        if brand:
            return brand
        path = PROJECT_ROOT / "config" / "brand_guidelines.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("Could not load brand_guidelines: %s", e)
        return {}

    def _video_creator_default(self):
        """Create VideoCreator with brand guidelines."""
        try:
            from core.video_creator import VideoCreator
            return VideoCreator(self.brand)
        except Exception as e:
            log.warning("VideoCreator not available: %s", e)
            return None

    def generate_weekly_package(self, week_number: Optional[int] = None) -> Dict[str, Any]:
        """
        Main entry: creates entire week's content package.
        Returns summary for WhatsApp.
        """
        now = datetime.now()
        iso = now.isocalendar()
        week_num = week_number or iso[1]
        year = iso[0]
        package_dir = PACKAGES_DIR / f"week_{year}_{week_num:02d}"
        package_dir.mkdir(parents=True, exist_ok=True)

        post_count = 0
        platform_count = 0
        image_count = 0
        video_count = 0

        # 1. Decide content calendar
        calendar = self._build_calendar(week_num, year)
        calendar_path = package_dir / "calendar.json"
        calendar_path.write_text(json.dumps(calendar, indent=2, ensure_ascii=False), encoding="utf-8")

        # 2. Generate posts for each day
        days = ["monday", "wednesday", "friday"]
        for day in days:
            day_dir = package_dir / day
            day_dir.mkdir(exist_ok=True)
            day_plan = calendar.get("days", {}).get(day, {})

            for item in day_plan.get("posts", []):
                platform = item.get("platform", "instagram_post")
                post_type = item.get("post_type", "wellness_tip")
                product = item.get("product")

                # Caption
                caption_data = self.generate_caption(
                    platform=platform,
                    post_type=post_type,
                    product=product,
                    theme=item.get("theme"),
                )
                if caption_data:
                    post_json = package_dir / day / f"{platform}.json"
                    post_json.parent.mkdir(parents=True, exist_ok=True)
                    post_json.write_text(
                        json.dumps(caption_data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    post_count += 1

                # Image
                if self.image_gen and self._images_today < self._MAX_IMAGES_PER_DAY:
                    img_result = self._generate_post_image(
                        post_type=post_type,
                        product=product,
                        platform=platform,
                        output_dir=day_dir,
                    )
                    if img_result.get("success"):
                        image_count += 1
                        self._images_today += 1

            # Reel on Wednesday
            if day == "wednesday" and self.video_creator:
                reel_result = self._generate_reel_for_day(day_dir, package_dir)
                if reel_result.get("success"):
                    video_count += 1

        platform_count = len(set(p.get("platform", "") for d in calendar.get("days", {}).values() for p in d.get("posts", [])))

        # 3. Generate UPLOAD_GUIDE.txt
        self.generate_upload_guide(package_dir, calendar)

        summary = (
            f"Boss, is hafte ka content package ready hai.\n\n"
            f"📁 {package_dir}\n"
            f"📊 {post_count} posts, {platform_count} platforms\n"
            f"🖼️ {image_count} images generated\n"
            f"🎬 {video_count} videos created\n\n"
            f"Upload guide bhi hai. ~20 min lagenge HeroPost mein.\n\n"
            f"Approve karein?"
        )
        return {
            "success": True,
            "package_path": str(package_dir),
            "post_count": post_count,
            "image_count": image_count,
            "video_count": video_count,
            "summary": summary,
        }

    def _build_calendar(self, week_num: int, year: int) -> Dict:
        """Build content calendar for the week."""
        products = self._get_featured_products(3)
        post_types = self.brand.get("post_types", ["product_spotlight", "wellness_tip", "ingredient_education", "customer_lifestyle", "festival_special", "behind_the_scenes", "new_arrival"])

        calendar = {
            "week": week_num,
            "year": year,
            "days": {
                "monday": {
                    "posts": [
                        {"platform": "instagram_post", "post_type": "product_spotlight" if products else "wellness_tip", "product": products[0] if products else None, "theme": "Product highlight"},
                        {"platform": "facebook_post", "post_type": "wellness_tip", "product": None, "theme": "Wellness tip"},
                        {"platform": "whatsapp_status", "post_type": "product_spotlight" if products else "wellness_tip", "product": products[0] if products else None},
                    ],
                },
                "wednesday": {
                    "posts": [
                        {"platform": "instagram_reel", "post_type": "ingredient_education", "product": products[1] if len(products) > 1 else (products[0] if products else None), "theme": "Reel"},
                        {"platform": "twitter_post", "post_type": "wellness_tip", "product": None, "theme": "Quick tip"},
                    ],
                },
                "friday": {
                    "posts": [
                        {"platform": "instagram_post", "post_type": "product_spotlight" if len(products) > 2 else "customer_lifestyle", "product": products[2] if len(products) > 2 else None, "theme": "Product or lifestyle"},
                        {"platform": "facebook_post", "post_type": "behind_the_scenes", "product": None, "theme": "BTS"},
                    ],
                },
            },
        }
        return calendar

    def _get_featured_products(self, limit: int = 5) -> List[Dict]:
        """Get products from WooCommerce for content."""
        if not self.woo:
            return []
        try:
            result = self.woo._make_request("products", {"per_page": limit})
            if result.get("success") and result.get("data"):
                return result["data"]
        except Exception as e:
            log.warning("Could not fetch products: %s", e)
        return []

    def generate_caption(
        self,
        platform: str,
        post_type: str,
        product: Optional[Dict] = None,
        theme: Optional[str] = None,
    ) -> Optional[Dict]:
        """Platform-specific caption with hashtags and CTA."""
        rules = "\n".join(self.brand.get("content_rules", []))
        banned = ", ".join(self.brand.get("banned_words", []))
        hashtags_always = " ".join(self.brand.get("hashtags", {}).get("always", []))
        hashtags_product = " ".join(self.brand.get("hashtags", {}).get("product", []))

        product_info = ""
        if product:
            product_info = f"\nProduct: {product.get('name', '')}\nDescription: {(product.get('description', '') or '')[:200]}"

        platform_guide = {
            "instagram_post": "Longer, storytelling, 20-30 hashtags, emoji heavy",
            "instagram_story": "Brief, punchy, 2-3 hashtags, strong CTA",
            "instagram_reel": "Hook in first line, 15-20 hashtags, trending",
            "facebook_post": "Medium length, conversational, 3-5 hashtags",
            "whatsapp_status": "Brief, direct, one CTA, no hashtags",
            "twitter_post": "Short, punchy, 2-3 hashtags, under 280 chars",
        }

        prompt = f"""Generate a social media caption for Falcon Herbs (Indian herbal products). 

Platform: {platform}
Post type: {post_type}
Theme: {theme or post_type}
{product_info}

Platform style: {platform_guide.get(platform, 'Professional, engaging')}

Rules (MUST follow):
{rules}
NEVER use these words: {banned}

Hashtags to include: {hashtags_always} {hashtags_product if product else ''}

Return JSON only:
{{"caption": "...", "hashtags": ["#..."], "cta": "..."}}
"""

        try:
            reply = call_ai("media", [{"role": "user", "content": prompt}], max_tokens=500)
            if reply.startswith("AI_ERROR"):
                return None
            # Extract JSON from reply
            clean = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
            if "```" in clean:
                clean = clean.split("```")[1].replace("json", "").strip()
            data = json.loads(clean)
            caption = data.get("caption", "")
            product_name = product.get("name", "") if product else None
            caption = self._validate_caption(caption, product_name, platform, post_type, theme)
            return {
                "caption": caption,
                "hashtags": data.get("hashtags", []),
                "cta": data.get("cta", "Shop now at falconherbs.com"),
                "platform": platform,
                "post_type": post_type,
            }
        except Exception as e:
            log.warning("Caption generation failed: %s", e)
            return {"caption": f"Discover {self.brand.get('brand_name', 'Falcon Herbs')} — authentic Ayurvedic wellness.", "hashtags": self.brand.get("hashtags", {}).get("always", []), "cta": "Shop now", "platform": platform}

    def _validate_caption(self, caption: str, product_name: Optional[str], platform: str, post_type: str, theme: Optional[str]) -> str:
        """Run banned_words check and HealthClaimsScanner on caption. Regenerate if needed."""
        if not caption:
            return caption
        banned = self.brand.get("banned_words", [])
        for word in banned:
            if word.lower() in caption.lower():
                caption = self._regenerate_clean(caption, [word], product_name, platform, post_type, theme)
                break
        if self._health_scanner:
            try:
                findings = self._health_scanner.scan_page("", caption, "", is_product=False)
                claims = []
                for item in findings.get("high_risk", []) + findings.get("medium_risk", []):
                    claims.append(item.get("matched", ""))
                if claims:
                    caption = self._regenerate_clean(caption, claims, product_name, platform, post_type, theme)
            except Exception as e:
                log.warning("Health scan on caption failed: %s", e)
        return caption

    def _regenerate_clean(
        self,
        original: str,
        claims_found: List[str],
        product_name: Optional[str],
        platform: str,
        post_type: str,
        theme: Optional[str],
    ) -> str:
        """Regenerate caption explicitly avoiding health claims."""
        prod = product_name or "herbal product"
        prompt = f"""Rewrite this caption for {prod}.

REMOVE these health claims (they violate FSSAI rules):
{chr(10).join('- ' + c for c in claims_found)}

ORIGINAL: {original}

RULES:
- NO health claims whatsoever
- Focus on: ingredients, tradition, lifestyle, aroma, taste
- Keep the same tone and platform style ({platform}, {post_type})
- Keep hashtags if present

REWRITTEN (caption only, no JSON):"""
        try:
            reply = call_ai("media", [{"role": "user", "content": prompt}], max_tokens=400)
            if reply.startswith("AI_ERROR"):
                return original
            clean = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
            if "```" in clean:
                clean = clean.split("```")[1].replace("json", "").replace("caption", "").strip()
            return clean[:1500] if clean else original
        except Exception as e:
            log.warning("Caption regenerate failed: %s", e)
            return original

    def _generate_post_image(
        self,
        post_type: str,
        product: Optional[Dict],
        platform: str,
        output_dir: Path,
    ) -> Dict:
        """Generate branded image for post."""
        size = self.brand.get("platforms", {}).get(platform, {"width": 1080, "height": 1080})
        w, h = size.get("width", 1080), size.get("height", 1080)

        if post_type == "product_spotlight" and product:
            return self.image_gen.generate_product_image(
                product.get("name", "herbal product"),
                product_description=product.get("description", "") or "",
                platform=platform,
                output_path=output_dir / f"{platform}_image.png",
            )
        elif post_type == "wellness_tip":
            prompt = "Serene wellness lifestyle, herbal tea, morning routine, Indian home, natural light"
            return self.image_gen.generate(prompt, style="lifestyle", width=w, height=h, output_path=output_dir / f"{platform}_image.png")
        elif post_type == "ingredient_education":
            name = product.get("name", "herbal ingredient") if product else "Ayurvedic herbs"
            prompt = f"Educational infographic style, {name}, natural herbs, botanical illustration, clean layout"
            return self.image_gen.generate(prompt, style="social", width=w, height=h, output_path=output_dir / f"{platform}_image.png")
        else:
            prompt = "Indian herbal products, warm earthy tones, wellness lifestyle, authentic Ayurvedic setting"
            return self.image_gen.generate(prompt, style="lifestyle", width=w, height=h, output_path=output_dir / f"{platform}_image.png")

    def _generate_reel_for_day(self, day_dir: Path, package_dir: Path) -> Dict:
        """Generate reel slideshow video for the day."""
        if not self.video_creator:
            return {"success": False, "error": "VideoCreator not available"}

        # Get or create 5-7 images for reel
        images = list(day_dir.glob("*.png"))
        if len(images) < 3:
            # Generate placeholder images
            for i in range(5 - len(images)):
                if self.image_gen and self._images_today < self._MAX_IMAGES_PER_DAY:
                    r = self.image_gen.generate(
                        f"Herbal wellness scene {i+1}, Indian aesthetic, warm tones",
                        style="lifestyle",
                        width=1080,
                        height=1920,
                        output_path=day_dir / f"reel_frame_{i}.png",
                    )
                    if r.get("success"):
                        images.append(Path(r["filepath"]))
                        self._images_today += 1

        if len(images) < 2:
            return {"success": False, "error": "Not enough images for reel"}

        reel_dir = day_dir / "reel_images"
        reel_dir.mkdir(exist_ok=True)
        output_video = day_dir / "reel_video.mp4"
        return self.video_creator.create_slideshow(
            image_paths=images[:7],
            output_path=output_video,
            duration_per_image=3,
            size=(1080, 1920),
        )

    def generate_upload_guide(self, package_path: Path, calendar: Dict) -> str:
        """Create UPLOAD_GUIDE.txt with exact HeroPost steps."""
        lines = [
            "FALCON HERBS — HEROPOST UPLOAD GUIDE",
            "=" * 50,
            "",
            "Follow these steps to upload this week's content to HeroPost.io",
            "",
        ]
        for day, day_data in calendar.get("days", {}).items():
            day_dir = package_path / day
            for post in day_data.get("posts", []):
                platform = post.get("platform", "")
                plat_name = platform.replace("_", " ").title()
                json_file = day_dir / f"{platform}.json"
                img_file = day_dir / f"{platform}_image.png"
                if not img_file.exists():
                    img_file = next(day_dir.glob("*.png"), None)
                lines.append(f"{day.upper()} - {plat_name}:")
                lines.append("  1. Open HeroPost → New Post → " + plat_name.split()[0])
                lines.append(f"  2. Upload: {day}/{img_file.name if img_file else 'image.png'}")
                if json_file.exists():
                    try:
                        data = json.loads(json_file.read_text(encoding="utf-8"))
                        cap = data.get("caption", "") + " " + " ".join(data.get("hashtags", []))
                        lines.append(f"  3. Caption: {cap[:100]}...")
                    except Exception:
                        lines.append("  3. Caption: [paste from JSON file]")
                lines.append(f"  4. Schedule: {day.title()} 10:00 AM IST")
                lines.append("  5. Done.")
                lines.append("")
        guide_path = package_path / "UPLOAD_GUIDE.txt"
        guide_path.write_text("\n".join(lines), encoding="utf-8")
        return str(guide_path)

    def generate_product_reel(self, product_name: str) -> Dict:
        """
        Owner: "Ashwagandha ke liye ek reel banao"
        Generate standalone product reel.
        """
        SINGLE_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_dir = SINGLE_VIDEOS_DIR / f"{product_name.replace(' ', '_')}_{ts}"
        out_dir.mkdir(parents=True, exist_ok=True)

        product = None
        if self.woo:
            try:
                result = self.woo._make_request("products", {"search": product_name, "per_page": 5})
                if result.get("success") and result.get("data"):
                    product = result["data"][0] if result["data"] else None
            except Exception:
                pass

        images = []
        for i in range(5):
            if self.image_gen and self._images_today < self._MAX_IMAGES_PER_DAY:
                prompts = [
                    f"Professional product photography of {product_name}, Indian herbal product",
                    f"Ingredients of {product_name}, botanical, natural",
                    f"Lifestyle use of {product_name}, wellness, Indian home",
                    f"Packaging of {product_name}, premium, earthy tones",
                    f"Benefits of {product_name}, holistic wellness, natural",
                ]
                r = self.image_gen.generate(
                    prompts[i] if i < len(prompts) else prompts[0],
                    style="product",
                    width=1080,
                    height=1920,
                    output_path=out_dir / f"scene_{i}.png",
                )
                if r.get("success"):
                    images.append(Path(r["filepath"]))
                    self._images_today += 1

        if len(images) < 2:
            return {"success": False, "error": "Could not generate enough images"}

        video_path = out_dir / "reel.mp4"
        if self.video_creator:
            vr = self.video_creator.create_slideshow(images, video_path, duration_per_image=3, size=(1080, 1920))
            if vr.get("success"):
                return {
                    "success": True,
                    "filepath": str(video_path),
                    "summary": f"Reel ready hai. 🎬 {video_path}\n\nHeroPost pe upload kar do.",
                }
        return {"success": False, "error": "Video creation failed"}

    def generate_email_campaign(self, campaign_type: str = "sale", products: Optional[List] = None) -> Dict:
        """Create email content for NetworkSolutions manual send."""
        ts = datetime.now().strftime("%Y_%m_%d")
        campaign_dir = EMAIL_CAMPAIGNS_DIR / f"campaign_{ts}"
        campaign_dir.mkdir(parents=True, exist_ok=True)

        subject = f"Falcon Herbs — {campaign_type.title()} | Authentic Ayurvedic Wellness"
        body_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{self.brand.get('brand_name', 'Falcon Herbs')}</title></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<h1 style="color: #2D5016;">{self.brand.get('brand_name', 'Falcon Herbs')}</h1>
<p>Discover authentic Indian herbal products. Traditionally used for wellness.</p>
<p>Shop now: <a href="https://falconherbs.com">falconherbs.com</a></p>
<p><em>Consult your healthcare provider before use. These statements have not been evaluated by FDA.</em></p>
</body>
</html>"""
        body_txt = f"{self.brand.get('brand_name', 'Falcon Herbs')}\n\nDiscover authentic Indian herbal products. Shop: https://falconherbs.com\n\nConsult your healthcare provider before use."

        (campaign_dir / "subject_line.txt").write_text(subject, encoding="utf-8")
        (campaign_dir / "email_body.html").write_text(body_html, encoding="utf-8")
        (campaign_dir / "email_body.txt").write_text(body_txt, encoding="utf-8")
        send_guide = f"""NETWORKSOLUTIONS SEND GUIDE
========================
1. Log in to NetworkSolutions email
2. Create new campaign
3. Subject: {subject}
4. Paste email_body.html into HTML editor (or email_body.txt for plain text)
5. Send to your list
6. Done.
"""
        (campaign_dir / "SEND_GUIDE.txt").write_text(send_guide, encoding="utf-8")

        return {
            "success": True,
            "campaign_path": str(campaign_dir),
            "summary": f"Email campaign ready: {campaign_dir}\n\nSEND_GUIDE.txt mein steps hain.",
        }
