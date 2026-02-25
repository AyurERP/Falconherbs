"""
agents/designer.py — Falcon Agency Designer Agent
==================================================

World-class design capabilities for a digital marketing agency:
- Brand templates (Falcon Herbs guidelines)
- Ad creatives (Meta, Google format)
- Carousel designs
- Blog banners, social graphics
- Campaign visuals

Uses AI + ImageGenerator for production-ready assets.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import log
from core.ai_client import call_ai
from agents.base_agent import BaseAgent


# Brand guidelines — Falcon Herbs
BRAND = {
    "name": "Falcon Herbs",
    "tagline": "Authentic Ayurvedic Wellness",
    "colors": {
        "primary": "#2D5016",      # forest green
        "secondary": "#8B4513",    # earthy brown
        "accent": "#D4A574",       # warm gold
        "background": "#F5F0E8",   # cream
    },
    "fonts": "Clean, modern sans-serif; avoid script fonts",
    "mood": "Premium, natural, trustworthy, warm, authentic",
    "avoid": "Cheap, clinical, overly medicinal, cluttered",
}

# Ad format specs
AD_FORMATS = {
    "meta_feed": {"width": 1080, "height": 1080, "ratio": "1:1"},
    "meta_story": {"width": 1080, "height": 1920, "ratio": "9:16"},
    "google_display": {"width": 1200, "height": 628, "ratio": "1.91:1"},
    "google_square": {"width": 1200, "height": 1200, "ratio": "1:1"},
    "carousel_slide": {"width": 1080, "height": 1080, "ratio": "1:1"},
    "blog_banner": {"width": 1200, "height": 628, "ratio": "1.91:1"},
    "social_post": {"width": 1080, "height": 1080, "ratio": "1:1"},
}


class DesignerAgent(BaseAgent):
    """
    Designer Agent — Brand-aligned visual assets for Falcon Herbs.
    Generates ad creatives, social graphics, blog banners, carousel slides.
    """

    def __init__(self, whatsapp_client=None):
        super().__init__(whatsapp_client)
        self.name = "DesignerAgent"
        self.ai_role = "media"
        self.capabilities = [
            "ad_creatives",
            "brand_templates",
            "carousel_designs",
            "blog_banners",
            "social_graphics",
            "campaign_visuals",
        ]
        self.output_dir = Path("data/content/designs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, action: str, details: str) -> str:
        """Route design requests."""
        action_lower = action.lower()
        if "ad" in action_lower or "meta" in action_lower or "google" in action_lower:
            return self.create_ad_creative(details, platform="meta")
        if "carousel" in action_lower:
            return self.create_carousel(details)
        if "banner" in action_lower or "blog" in action_lower:
            return self.create_blog_banner(details)
        if "social" in action_lower or "instagram" in action_lower:
            return self.create_social_graphic(details)
        return self.create_social_graphic(details)

    def _build_prompt(self, subject: str, format_type: str, extra: str = "") -> str:
        """Build brand-aligned AI image prompt."""
        fmt = AD_FORMATS.get(format_type, AD_FORMATS["social_post"])
        return f"""Create a professional marketing image for Falcon Herbs — Ayurvedic wellness brand.

SUBJECT: {subject}
FORMAT: {format_type} ({fmt['width']}x{fmt['height']})
BRAND: {BRAND['name']} — {BRAND['tagline']}
MOOD: {BRAND['mood']}
COLORS: Earthy greens, warm browns, cream backgrounds
AVOID: {BRAND['avoid']}
{extra}

Output: High-quality, commercial-ready, no text overlay (we add in post)."""

    def create_ad_creative(self, subject: str, platform: str = "meta") -> str:
        """Generate Meta/Google ad creative."""
        try:
            from core.image_generator import ImageGenerator
            gen = ImageGenerator()
            format_type = "meta_feed" if platform == "meta" else "google_display"
            fmt = AD_FORMATS[format_type]
            prompt = f"{subject}, premium ad creative, ayurvedic wellness"
            result = gen.generate(
                prompt,
                style="ad_creative",
                width=fmt["width"],
                height=fmt["height"],
            )
            if result.get("success"):
                return f"✅ Ad creative ready!\n📁 {result.get('filename')}\n📐 {fmt['width']}x{fmt['height']}\n💡 Use for {platform.upper()} ads"
            return f"❌ {result.get('error', 'Failed')}"
        except Exception as e:
            log.error("DesignerAgent ad creative failed: %s", e)
            return f"❌ Design failed: {e}"

    def create_blog_banner(self, topic: str) -> str:
        """Generate blog featured image."""
        try:
            from core.image_generator import ImageGenerator
            gen = ImageGenerator()
            result = gen.generate_blog_banner(topic)
            if result.get("success"):
                return f"✅ Blog banner ready!\n📁 {result.get('filename')}\n📐 1200x628"
            return f"❌ {result.get('error')}"
        except Exception as e:
            return f"❌ {e}"

    def create_social_graphic(self, subject: str) -> str:
        """Generate Instagram/Facebook social graphic."""
        try:
            from core.image_generator import ImageGenerator
            gen = ImageGenerator()
            result = gen.generate_social_image(subject)
            if result.get("success"):
                return f"✅ Social graphic ready!\n📁 {result.get('filename')}\n📐 1080x1080"
            return f"❌ {result.get('error')}"
        except Exception as e:
            return f"❌ {e}"

    def create_carousel(self, topics: str) -> str:
        """Generate carousel slide prompts or first slide.
        topics: comma-separated e.g. 'ashwagandha benefits, how to use, testimonials'
        """
        try:
            parts = [p.strip() for p in topics.split(",") if p.strip()]
            if not parts:
                return "❌ Carousel topics chahiye. Example: ashwagandha benefits, how to use, buy now"
            from core.image_generator import ImageGenerator
            gen = ImageGenerator()
            first = parts[0]
            result = gen.generate(first, style="social", width=1080, height=1080)
            if result.get("success"):
                slides_info = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(parts))
                return (
                    f"✅ Carousel slide 1 ready!\n📁 {result.get('filename')}\n\n"
                    f"📋 Full carousel plan:\n{slides_info}\n\n"
                    f"Say 'design carousel slide 2' for next."
                )
            return f"❌ {result.get('error')}"
        except Exception as e:
            return f"❌ {e}"

    def get_brand_guidelines(self) -> str:
        """Return brand guidelines as text."""
        return json.dumps(BRAND, indent=2)
