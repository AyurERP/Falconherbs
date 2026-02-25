"""
Image Generator — Generate product images, blog banners, 
and social media graphics via NVIDIA Stable Diffusion API.

For social posts and blog featured images.
"""

import os
import json
import base64
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
IMAGES_DIR = Path(__file__).parent.parent / "data" / "content" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# NVIDIA Stable Diffusion XL endpoint
SDXL_URL = "https://ai.api.nvidia.com/v1/genai/stabilityai/stable-diffusion-xl"


class ImageGenerator:
    """Generate images using NVIDIA Stable Diffusion API."""
    
    def __init__(self):
        self.api_key = NVIDIA_API_KEY
        self.output_dir = IMAGES_DIR
    
    def generate(self, prompt: str, style: str = "product",
                 width: int = 1024, height: int = 1024,
                 filename: str = None) -> dict:
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
        
        # Enhance prompt based on style
        enhanced = self._enhance_prompt(prompt, style)
        
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
    
    def generate_product_image(self, product: str) -> dict:
        """Generate a product showcase image."""
        return self.generate(product, style="product", width=1024, height=1024)


# Global instance
image_generator = ImageGenerator()
