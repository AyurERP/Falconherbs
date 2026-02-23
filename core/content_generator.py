"""Content Generator — Blog posts, Social media, Product descriptions"""

import json
from typing import Dict, List, Optional
from core.ai_client import call_ai
from datetime import datetime

class ContentGenerator:
    """AI-powered content generation"""
    
    def __init__(self):
        self.brand_voice = """
        Brand Voice Guidelines:
        - Professional yet approachable
        - Focus on natural, herbal benefits
        - Avoid health claims (FDA compliance)
        - Use phrases like "traditionally used", "may support", "helps maintain"
        - Never use: cures, treats, heals, prevents disease
        """
    
    def generate_blog_post(self, topic: str, keywords: List[str] = None, word_count: int = 800) -> Dict:
        """Generate SEO-optimized blog post"""
        
        keywords_str = ", ".join(keywords) if keywords else "natural herbs, ayurveda, wellness"
        
        prompt = f"""
Write a blog post about: {topic}

Requirements:
1. Word count: approximately {word_count} words
2. SEO optimized for keywords: {keywords_str}
3. Include: Title, Meta Description, Headers (H2, H3), Body paragraphs
4. Tone: Professional, informative, trustworthy
5. CRITICAL: No health claims! Use "may support", "traditionally used", "helps maintain"

{self.brand_voice}

Output format (JSON):
{{
    "title": "SEO optimized title",
    "meta_description": "155 characters max",
    "slug": "url-friendly-slug",
    "headers": ["H2 header 1", "H2 header 2"],
    "content": "Full blog post content with markdown formatting",
    "keywords_used": ["keyword1", "keyword2"],
    "word_count": 800
}}
"""
        
        response = call_ai("media", [{"role": "user", "content": prompt}])
        
        try:
            return json.loads(response)
        except:
            return {"raw_content": response, "error": "Could not parse JSON"}
    
    def generate_social_post(self, topic: str, platform: str = "instagram", include_hashtags: bool = True) -> Dict:
        """Generate social media post"""
        
        platform_guidelines = {
            "instagram": "2200 chars max, visual focus, 20-30 hashtags",
            "facebook": "500 chars optimal, engagement focus, 3-5 hashtags",
            "twitter": "280 chars max, concise, 2-3 hashtags"
        }
        
        prompt = f"""
Create a {platform} post about: {topic}

Platform: {platform}
Guidelines: {platform_guidelines.get(platform, platform_guidelines['instagram'])}

{self.brand_voice}

IMPORTANT: No health claims!

Output format (JSON):
{{
    "caption": "Main post text",
    "hashtags": ["hashtag1", "hashtag2"],
    "emoji_suggestions": ["🌿", "✨"],
    "image_suggestion": "Description of ideal image",
    "best_posting_time": "e.g., 10 AM - 12 PM",
    "cta": "Call to action"
}}
"""
        
        response = call_ai("media", [{"role": "user", "content": prompt}])
        
        try:
            return json.loads(response)
        except:
            return {"raw_content": response, "platform": platform}
    
    def generate_product_description(self, product_name: str, features: List[str] = None, benefits: List[str] = None) -> Dict:
        """Generate compliant product description"""
        
        features_str = ", ".join(features) if features else "natural ingredients, traditional formulation"
        benefits_str = ", ".join(benefits) if benefits else "wellness support, daily health"
        
        prompt = f"""
Write a product description for: {product_name}

Features: {features_str}
Benefits: {benefits_str}

{self.brand_voice}

CRITICAL COMPLIANCE:
- NO disease claims (cures, treats, heals)
- Use "may support", "traditionally used for", "helps maintain"
- Focus on traditional use and general wellness

Output format (JSON):
{{
    "short_description": "50-100 words",
    "long_description": "200-300 words",
    "bullet_points": ["benefit 1", "benefit 2", "benefit 3"],
    "meta_description": "SEO meta description",
    "usage_instructions": "How to use",
    "compliance_check": true
}}
"""
        
        response = call_ai("media", [{"role": "user", "content": prompt}])
        
        try:
            return json.loads(response)
        except:
            return {"raw_content": response, "product": product_name}
    
    def generate_content_calendar(self, days: int = 30, posts_per_day: int = 1) -> Dict:
        """Generate content calendar"""
        
        prompt = f"""
Create a {days}-day content calendar for an herbal products brand.

Requirements:
- {posts_per_day} post(s) per day
- Mix of: product features, educational content, user tips, seasonal themes
- Platform: Instagram/Facebook
- Include variety: quotes, tips, product highlights, behind-the-scenes

{self.brand_voice}

Output format (JSON):
{{
    "calendar": [
        {{
            "day": 1,
            "theme": "Product Monday",
            "topic": "Triphala benefits",
            "content_type": "product_feature",
            "caption_idea": "Brief caption concept",
            "hashtag_theme": "wellness, ayurveda"
        }}
    ],
    "themes_used": ["list of weekly themes"],
    "total_posts": {days * posts_per_day}
}}
"""
        
        response = call_ai("media", [{"role": "user", "content": prompt}])
        
        try:
            return json.loads(response)
        except:
            return {"raw_content": response, "days": days}
    
    def generate_image_prompt(self, concept: str, style: str = "professional product photography") -> Dict:
        """Generate AI image generation prompt"""
        
        prompt = f"""
Create an image generation prompt for: {concept}

Style: {style}
Brand: Herbal/Ayurvedic products
Mood: Natural, clean, professional, trustworthy

Output format (JSON):
{{
    "midjourney_prompt": "Detailed prompt for Midjourney",
    "dalle_prompt": "Detailed prompt for DALL-E",
    "canva_search_terms": ["search term 1", "search term 2"],
    "color_palette": ["#color1", "#color2"],
    "composition_notes": "Layout and composition suggestions"
}}
"""
        
        response = call_ai("media", [{"role": "user", "content": prompt}])
        
        try:
            return json.loads(response)
        except:
            return {"raw_content": response, "concept": concept}

# Global instance
content_generator = ContentGenerator()
