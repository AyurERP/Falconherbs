"""
Image Generator — Generate product images, blog banners, 
and social media graphics via NVIDIA Stable Diffusion API.

For social posts and blog featured images.
Uses NVIDIA NIM (same API key as rest of agency). No DALL-E.
"""

import os
import json
import base64
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
IMAGES_DIR = Path(__file__).parent.parent / "data" / "content" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# NVIDIA Stable Diffusion XL endpoint
SDXL_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"

# Brand style suffix (added to all prompts when brand_guidelines provided)
BRAND_STYLE_SUFFIX = (
    "Indian herbal products, warm earthy tones, natural lighting, "
    "professional product photography style, clean background, no text in image, "
    "NOT cartoon, NOT anime, NOT clipart"
)


class ImageGenerator:
    """Generate images using NVIDIA Stable Diffusion API."""
    
    def __init__(self, brand_guidelines: Optional[Dict[str, Any]] = None):
        self.api_key = NVIDIA_API_KEY
        self.output_dir = IMAGES_DIR
        self.brand = brand_guidelines or {}
    
    def generate(self, prompt: str, style: str = "product",
                 width: int = 1024, height: int = 1024,
                 filename: str = None, output_path: Optional[Path] = None) -> dict:
        """
        Generate an image from text prompt.
        
        Args:
            prompt: Text description of the image
            style: "product", "blog_banner", "social", "lifestyle"
            width/height: Image dimensions
            filename: Optional output filename
        """
        if not self.api_key:
            return {"success": False, "error": "NVIDIA_API_KEY not set"}
        
        # Enhance prompt based on style + brand
        enhanced = self._enhance_prompt(prompt, style)
        if self.brand:
            enhanced = f"{enhanced}, {BRAND_STYLE_SUFFIX}"
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            payload = {
                "text_prompts": [
                    {"text": enhanced, "weight": 1.0},
                    {"text": "blurry, low quality, text, watermark, logo", "weight": -1.0}
                ],
                "cfg_scale": 7,
                "height": height,
                "width": width,
                "steps": 30,
                "seed": 0,
                "samples": 1
            }
            
            response = requests.post(
                SDXL_URL, headers=headers, 
                json=payload, timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                artifacts = data.get("artifacts", [])
                
                if artifacts:
                    img_data = base64.b64decode(artifacts[0]["base64"])
                    
                    if not filename:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{style}_{timestamp}.png"
                    
                    if output_path:
                        filepath = Path(output_path)
                        filepath.parent.mkdir(parents=True, exist_ok=True)
                    else:
                        filepath = self.output_dir / filename
                    filepath.write_bytes(img_data)
                    
                    return {
                        "success": True,
                        "filepath": str(filepath),
                        "filename": filename,
                        "size_kb": len(img_data) // 1024,
                        "message": f"🎨 Image generated!\n📁 {filename}\n📐 {width}x{height}\n💾 {len(img_data)//1024}KB"
                    }
                
                return {"success": False, "error": "No image in response"}
            
            return {
                "success": False, 
                "error": f"API error: {response.status_code} — {response.text[:200]}"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _enhance_prompt(self, prompt: str, style: str) -> str:
        """Add style-specific qualifiers to the prompt."""
        bases = {
            "product": (
                f"Professional product photography of {prompt}, "
                "on clean white background, studio lighting, "
                "high resolution, 4K, commercial quality, "
                "ayurvedic herbal product"
            ),
            "blog_banner": (
                f"Wide banner image for blog article about {prompt}, "
                "modern clean design, natural herbs and wellness theme, "
                "warm earthy tones, professional quality, no text"
            ),
            "social": (
                f"Instagram-ready image of {prompt}, "
                "vibrant colors, wellness aesthetic, "
                "modern lifestyle, clean composition, no text overlay"
            ),
            "lifestyle": (
                f"Lifestyle photography showing {prompt}, "
                "natural lighting, warm tones, wellness theme, "
                "authentic ayurvedic setting, premium quality"
            ),
            "ad_creative": (
                f"Premium ad creative for {prompt}, "
                "conversion-focused, clean composition, "
                "earthy greens and warm browns, "
                "ayurvedic wellness brand, professional, no text overlay"
            ),
        }
        return bases.get(style, f"High quality image of {prompt}, professional, 4K")
    
    def generate_blog_banner(self, topic: str) -> dict:
        """Generate a banner for a blog post."""
        return self.generate(topic, style="blog_banner", width=1200, height=628)
    
    def generate_social_image(self, topic: str) -> dict:
        """Generate an image for social media post."""
        return self.generate(topic, style="social", width=1080, height=1080)
    
    def generate_product_image(
        self,
        product: str,
        product_description: str = "",
        platform: str = "instagram_post",
        output_path: Optional[Path] = None,
    ) -> dict:
        """
        Generate product-focused image for a specific platform.
        Auto-builds prompt from product data.
        """
        # Extract key ingredients from description (first 100 chars)
        desc_hint = ""
        if product_description:
            desc_hint = product_description[:150].replace("\n", " ").strip()
        prompt = (
            f"Professional product photography of {product}"
            + (f", {desc_hint}" if desc_hint else "")
            + ", Indian herbal product, warm natural lighting, wooden/natural surface, "
            "green leaves as accent, earthy tones, clean composition, no text"
        )
        size = (1080, 1080)
        if self.brand and "platforms" in self.brand:
            plat = self.brand["platforms"].get(platform, {})
            size = (plat.get("width", 1080), plat.get("height", 1080))
        return self.generate(
            prompt, style="product", width=size[0], height=size[1],
            filename=output_path.name if output_path else None,
            output_path=output_path,
        )

    def generate_with_text_overlay(
        self,
        prompt: str,
        width: int,
        height: int,
        text: str,
        font_size: int = 48,
        style: str = "social",
        output_path: Optional[Path] = None,
    ) -> dict:
        """
        Generate base image via NVIDIA, then add text using Pillow.
        AI is bad at text — Pillow gives exact brand fonts/colors.
        """
        result = self.generate(prompt, style=style, width=width, height=height)
        if not result.get("success"):
            return result

        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return {**result, "note": "Pillow not installed — text overlay skipped"}

        filepath = Path(result["filepath"])
        img = Image.open(filepath).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Brand colors
        text_color = self.brand.get("colors", {}).get("text", "#1A1A1A")
        if text_color.startswith("#"):
            text_rgba = (*self._hex_to_rgb(text_color), 255)
        else:
            text_rgba = (26, 26, 26, 255)

        # Try to load font; fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        # Position text bottom-center
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (img.width - tw) // 2
        y = img.height - th - 60
        draw.text((x, y), text, fill=text_rgba, font=font)

        if output_path is None:
            output_path = filepath.with_stem(filepath.stem + "_text")
        img.convert("RGB").save(output_path, "PNG")
        return {
            "success": True,
            "filepath": str(output_path),
            "filename": output_path.name,
            "message": f"🎨 Image with text overlay saved: {output_path.name}",
        }

    def _hex_to_rgb(self, hex_str: str) -> tuple:
        """Convert #RRGGBB to (r, g, b)."""
        h = hex_str.lstrip("#")
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


# Global instance (backward compat — no brand)
image_generator = ImageGenerator()
