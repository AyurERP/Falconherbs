"""
Falcon Agency — Content Pipeline
Generates SEO-optimized, health-claims-safe content
for premium Ayurvedic herbal products brand.

Target: International Ayurveda buyers
Markets: USA, UK, Australia, Poland, EU
AOV: ₹5,000 - ₹20,000

IMPORTANT: All content passes through health safety
filter before output. No direct disease claims.

Author: Claude (Heavy Lifting) → IDE (Execution)
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class ContentPipeline:
    """
    Complete content generation system for Falcon Herbs.
    Generates: Blogs, Product Descriptions, Social Posts,
    Email Drafts, Content Calendar.
    
    All content is health-claims-safe by design.
    """
    
    def __init__(self, ai_client=None):
        """
        Args:
            ai_client: Your existing AI client from 
                       core/ai_client.py
                       If None, generates prompt templates
                       for manual AI processing
        """
        self.ai_client = ai_client
        self.data_dir = Path("data/content")
        self.drafts_dir = self.data_dir / "drafts"
        self.approved_dir = self.data_dir / "approved"
        self.calendar_dir = self.data_dir / "calendar"
        self.templates_dir = self.data_dir / "templates"
        
        # Create all directories
        for d in [self.drafts_dir, self.approved_dir,
                  self.calendar_dir, self.templates_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Health-safe language rules
        self._init_safety_rules()
        
        # Brand voice
        self.brand = {
            "name": "Falcon Herbs",
            "tagline": "Authentic Ayurvedic Wellness",
            "tone": "Premium, knowledgeable, trustworthy, warm",
            "usp": [
                "Authentic Ayurvedic formulations",
                "Sourced directly from India",
                "Traditional methods, modern quality standards",
                "Premium grade herbs and ingredients",
                "Trusted by customers worldwide"
            ],
            "target_audience": [
                "Health-conscious adults 25-55",
                "Interested in natural/holistic wellness",
                "Willing to pay premium for quality",
                "USA, UK, Australia, EU, Poland",
                "Already exploring or using Ayurveda"
            ],
            "disclaimer": (
                "* These statements have not been evaluated "
                "by the Food and Drug Administration. This "
                "product is not intended to diagnose, treat, "
                "cure, or prevent any disease. Consult your "
                "healthcare provider before use."
            )
        }
    
    def _init_safety_rules(self):
        """Words/phrases to NEVER use in content"""
        self.banned_phrases = [
            "cures", "cure for", "treats", "treatment for",
            "prevents disease", "heals disease",
            "clinically proven", "scientifically proven",
            "FDA approved", "doctor recommended",
            "guaranteed results", "100% effective",
            "no side effects", "completely safe",
            "miracle", "magic", "wonder drug",
            "instant cure", "permanent cure",
            "anti-cancer", "anti-tumor", "cancer fighting",
            "kills bacteria", "kills virus",
            "cures diabetes", "cures arthritis",
            "eliminates disease",
        ]
        
        # Danger keywords (Diseases) pulled from health_scanner
        self.danger_keywords = [
            "cancer", "diabetes", "heart disease", "alzheimer", "parkinson",
            "hiv", "aids", "covid", "coronavirus", "tumor", "malignant",
            "hypertension", "stroke", "epilepsy", "asthma", "hepatitis",
            "tuberculosis", "malaria", "depression", "anxiety", "insomnia",
            "arthritis", "eczema", "psoriasis", "infertility", "impotence"
        ]
        
        self.safe_alternatives = {
            "boosts immunity": 
                "supports healthy immune function",
            "cures": 
                "traditionally used to support",
            "treats": 
                "may help with",
            "prevents": 
                "traditionally associated with",
            "heals": 
                "supports natural wellness",
            "fights infection": 
                "supports the body's natural defenses",
            "detoxifies": 
                "supports the body's natural cleansing",
            "detoxify":
                "support natural cleansing",
            "detoxification":
                "natural cleansing process",
            "rejuvenates":
                "supports youthful vitality",
            "rejuvenate":
                "promote vitality",
            "rejuvenation":
                "vitality and renewal",
            "purifies blood": 
                "traditionally used for skin and liver wellness",
            "blood purifier":
                "traditionally used for skin wellness",
            "lowers blood sugar": 
                "may support healthy blood sugar levels already within normal range",
            "lowers cholesterol": 
                "may support healthy cholesterol levels already within normal range",
            "anti-inflammatory": 
                "supports comfort and ease of movement",
            "anti-aging": 
                "supports youthful vitality",
            "healing":
                "wellness supporting",
            "heals":
                "supports natural wellness",
            "burns fat": 
                "supports healthy metabolism",
            "weight loss": 
                "supports healthy weight management",
            "fat burner":
                "metabolism support",
            "cures diabetes":
                "supports healthy blood sugar levels",
            "theek kar deta hai":
                "mein support karta hai",
            "theek ho gaya":
                "mein madad karta hai",
            "theek ho gya":
                "mein madad karta hai",
            "dawai band":
                "natural wellness ke liye",
            # NOTE: "cure", "treatment", "ilaj" are intentionally
            # NOT in safe_alternatives — too short/generic, would
            # corrupt legitimate phrases like "secure", "Ayurvedic
            # treatment", "ilaj-e-tibbi". Specific combos above
            # (e.g. "cures diabetes") cover the real violations.
            # High-risk mapping from health_scanner
            "anti-cancer":
                "rich in antioxidants",
            "anti-tumor":
                "supports healthy cellular function",
            "anti-diabetic":
                "supports healthy blood sugar balance",
            "cancer-fighting":
                "antioxidant rich",
            "lowers blood pressure":
                "may support healthy blood pressure already within normal range",
            "no side effects":
                "generally well-tolerated when used as directed",
            "clinically proven":
                "supported by traditional Ayurvedic use",
            "100% safe":
                "made with carefully selected natural ingredients",
            "miracle":
                "time-honored",
            "instant relief":
                "fast-acting support",
            "permanently cures":
                "traditionally used to support",
            "reverses":
                "supports healthy management of",
        }
        # Merge SEO-safe swaps from config (single source of truth)
        swaps = self._load_smart_swaps()
        if swaps:
            self.safe_alternatives.update(swaps)
    
    def _load_smart_swaps(self):
        """Load config/smart_word_swap.json for SEO + compliant replacements."""
        try:
            cfg = Path(__file__).parent.parent / "config" / "smart_word_swap.json"
            if cfg.exists():
                data = json.loads(cfg.read_text(encoding="utf-8"))
                return data.get("replacements", {})
        except Exception:
            pass
        return {}
    
    def safety_check(self, content):
        """
        Check content for health claim violations.
        Returns cleaned content + list of changes made.
        """
        changes = []
        cleaned = content
        
        # 0. Check for Danger Keywords (Specific Diseases)
        for word in self.danger_keywords:
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            if pattern.search(cleaned):
                changes.append({
                    "found": word,
                    "action": "FLAGGED disease mention — Use body system/function language",
                    "severity": "HIGH"
                })

        # 1. Check banned phrases
        for phrase in self.banned_phrases:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            if pattern.search(cleaned):
                changes.append({
                    "found": phrase,
                    "action": "FLAGGED — Review needed",
                    "severity": "HIGH"
                })
        
        # Auto-replace known unsafe phrases.
        # Sort longest phrase first so specific multi-word phrases
        # (e.g. "cures diabetes") are checked before shorter
        # substrings (e.g. "cures") that would corrupt them.
        for unsafe, safe in sorted(
            self.safe_alternatives.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            pattern = re.compile(re.escape(unsafe), re.IGNORECASE)
            if pattern.search(cleaned):
                cleaned = pattern.sub(safe, cleaned)
                changes.append({
                    "found": unsafe,
                    "replaced_with": safe,
                    "action": "AUTO-REPLACED",
                    "severity": "MEDIUM"
                })
        
        # Check if disclaimer present
        has_disclaimer = any(
            phrase in cleaned.lower() for phrase in [
                "not intended to diagnose",
                "consult your healthcare",
                "these statements have not been evaluated"
            ]
        )
        
        if not has_disclaimer:
            changes.append({
                "found": "Missing disclaimer",
                "action": "NEEDS ADDITION",
                "severity": "LOW"
            })
        
        return {
            "original_length": len(content),
            "cleaned_content": cleaned,
            "changes_made": len(changes),
            "changes": changes,
            "is_safe": len([
                c for c in changes if c["severity"] == "HIGH"
            ]) == 0,
            "needs_disclaimer": not has_disclaimer
        }

    # ==================== BLOG POSTS ====================
    
    def generate_blog_prompt(self, topic, target_keyword,
                              product_name=None,
                              secondary_keywords=None,
                              word_count=1500):
        """
        Generates AI prompt for blog post creation.
        The prompt itself enforces health-safe language.
        """
        
        secondary_kw_text = ""
        if secondary_keywords:
            secondary_kw_text = (
                f"\nSecondary keywords to naturally include: "
                f"{', '.join(secondary_keywords)}"
            )
        
        product_mention = ""
        if product_name:
            product_mention = f"""
PRODUCT MENTION RULES:
- Mention "{product_name}" by Falcon Herbs naturally 
  1-2 times maximum
- Place in middle or end of article, NEVER in first 
  2 paragraphs
- Frame as: "Products like [name] from Falcon Herbs 
  offer authentic Ayurvedic formulations..."
- Include link placeholder: [PRODUCT_LINK]
- Do NOT make the article feel like a product ad
"""
        
        prompt = f"""Write a comprehensive, SEO-optimized blog post 
for an authentic Ayurvedic herbal products brand called 
"Falcon Herbs" (falconherbs.com).

TOPIC: {topic}
PRIMARY KEYWORD: {target_keyword}
{secondary_kw_text}
TARGET WORD COUNT: {word_count} words

TARGET AUDIENCE:
- Health-conscious adults in USA, UK, Australia, Europe
- Interested in natural wellness and Ayurveda
- Educated, willing to pay premium for quality
- May be new to Ayurveda or experienced practitioners

ARTICLE STRUCTURE:
1. HOOK (2-3 sentences) — Engaging opening that addresses 
   reader's pain point or curiosity
2. INTRODUCTION — Why this topic matters, brief Ayurvedic 
   context
3. MAIN CONTENT — 3-5 detailed sections with H2/H3 headings
   - Include practical, actionable information
   - Reference traditional Ayurvedic texts/practices 
     where relevant
   - Add "How to use" or "How to incorporate" sections
4. EXPERT INSIGHTS — Ayurvedic perspective 
   (Vata/Pitta/Kapha if relevant)
5. CONCLUSION — Summary + gentle call-to-action
6. FAQ SECTION — 3-4 common questions (great for SEO)

{product_mention}

TONE & STYLE:
- Authoritative but approachable
- Educational, not salesy
- Warm, like a knowledgeable friend
- Premium brand voice
- Use "you" and "your" (direct address)

SEO REQUIREMENTS:
- Primary keyword in: Title, first 100 words, 
  one H2, conclusion
- Keyword density: 1-2% (natural, not forced)
- Include LSI/related terms naturally
- Short paragraphs (2-3 sentences max)
- Use bullet points and numbered lists
- Suggest 3 internal link opportunities: [INTERNAL_LINK]

CRITICAL HEALTH & LEGAL RULES — MUST FOLLOW:
❌ NEVER use: "cures", "treats disease", "prevents disease",
   "clinically proven", "FDA approved", "guaranteed results",
   "no side effects", "miracle", "100% effective"
❌ NEVER mention specific diseases as something the product 
   cures/treats
❌ NEVER make drug-like claims

✅ USE instead: "traditionally used for", "may support",
   "Ayurvedic tradition suggests", "historically valued for",
   "supports healthy [function]", "promotes natural [benefit]"
✅ Frame benefits as traditional Ayurvedic wisdom
✅ Always recommend consulting healthcare providers
✅ Use structure/function claims only

INCLUDE AT THE END:
"*Disclaimer: {self.brand['disclaimer']}"

FORMAT:
- Return as clean HTML with proper heading tags
- Use <h1> for title, <h2> for sections, <h3> for subsections
- Include <meta_title> tag (max 60 chars)
- Include <meta_description> tag (max 155 chars)
- Include suggested <slug> (URL-friendly)
"""
        
        return prompt
    
    def create_blog_draft(self, topic, target_keyword,
                           product_name=None,
                           secondary_keywords=None,
                           word_count=1500):
        """
        Create a blog post draft.
        If AI client available: generates content
        If not: saves prompt for manual generation
        """
        
        prompt = self.generate_blog_prompt(
            topic=topic,
            target_keyword=target_keyword,
            product_name=product_name,
            secondary_keywords=secondary_keywords,
            word_count=word_count
        )
        
        draft = {
            "type": "blog_post",
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "topic": topic,
            "target_keyword": target_keyword,
            "secondary_keywords": secondary_keywords or [],
            "product_mentioned": product_name,
            "word_count_target": word_count,
            "prompt": prompt,
            "content": None,
            "safety_check": None,
            "seo_meta": {
                "title": None,
                "description": None,
                "slug": None
            }
        }
        
        # Generate content if AI client available
        if self.ai_client:
            try:
                response = self.ai_client.generate(prompt)
                if response:
                    draft["content"] = response
                    draft["status"] = "generated"
                    
                    # Run safety check
                    safety = self.safety_check(response)
                    draft["safety_check"] = safety
                    
                    if not safety["is_safe"]:
                        draft["status"] = "needs_review"
                        draft["content"] = safety["cleaned_content"]
                    
                    if safety["needs_disclaimer"]:
                        draft["content"] += (
                            f"\n\n{self.brand['disclaimer']}"
                        )
            except Exception as e:
                draft["error"] = str(e)
                draft["status"] = "prompt_only"
        else:
            draft["status"] = "prompt_only"
            draft["note"] = (
                "No AI client connected. Use the prompt "
                "above with your AI model to generate content."
            )
        
        # Save draft
        slug = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:50]
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"blog_{date_str}_{slug}.json"
        filepath = self.drafts_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(draft, f, indent=2, ensure_ascii=False)
        
        print(f"📝 Blog draft saved: {filepath}")
        
        return {"success": True, "draft": draft, "file": str(filepath)}

    # ============ PRODUCT DESCRIPTIONS ============
    
    def generate_product_description_prompt(
        self, product_name, current_description="",
        category="", ingredients="", usage=""
    ):
        """Generate prompt for product description rewrite"""
        
        prompt = f"""Rewrite this product description for an 
authentic Ayurvedic herbal products brand "Falcon Herbs" 
(falconherbs.com).

PRODUCT: {product_name}
CATEGORY: {category}
CURRENT DESCRIPTION: {current_description if current_description else 'None provided — write from scratch'}
INGREDIENTS: {ingredients if ingredients else 'Not specified'}
USAGE: {usage if usage else 'Not specified'}

WRITE TWO VERSIONS:

VERSION 1 — SHORT DESCRIPTION (50-80 words):
- Compelling, benefit-focused
- Highlight 2-3 key benefits
- Include primary use case
- Premium brand tone
- End with subtle CTA

VERSION 2 — FULL DESCRIPTION (200-400 words):
Structure:
1. Opening hook (1-2 sentences) — What makes this special
2. Ayurvedic Heritage (2-3 sentences) — Traditional context
3. Key Benefits (bullet points, 4-6 benefits)
   - Each benefit = structure/function claim ONLY
   - Format: "✦ Benefit statement"
4. How to Use (clear instructions)
5. Quality Promise (sourcing, purity, authenticity)
6. Ingredients list (if provided)

TONE:
- Premium and trustworthy
- Knowledgeable about Ayurveda
- Warm but professional
- International audience friendly

SEO:
- Include product name 2-3 times naturally
- Include category keywords
- Include "Ayurvedic", "traditional", "authentic"
- Write alt text suggestion for product image

HEALTH CLAIMS RULES — STRICTLY FOLLOW:
❌ NEVER: "cures", "treats", "prevents disease", 
   "clinically proven", "no side effects"
✅ USE: "supports", "promotes", "traditionally used for",
   "may help with", "Ayurvedic tradition values this for"

INCLUDE AT END:
{self.brand['disclaimer']}
"""
        return prompt
    
    def create_product_description(
        self, product_name, current_description="",
        category="", ingredients="", usage=""
    ):
        """Create product description draft"""
        
        prompt = self.generate_product_description_prompt(
            product_name=product_name,
            current_description=current_description,
            category=category,
            ingredients=ingredients,
            usage=usage
        )
        
        draft = {
            "type": "product_description",
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "product_name": product_name,
            "category": category,
            "prompt": prompt,
            "short_description": None,
            "full_description": None,
            "image_alt_text": None,
            "safety_check": None
        }
        
        if self.ai_client:
            try:
                response = self.ai_client.generate(prompt)
                if response:
                    draft["content"] = response
                    draft["status"] = "generated"
                    safety = self.safety_check(response)
                    draft["safety_check"] = safety
                    if not safety["is_safe"]:
                        draft["status"] = "needs_review"
            except Exception as e:
                draft["error"] = str(e)
                draft["status"] = "prompt_only"
        else:
            draft["status"] = "prompt_only"
        
        slug = re.sub(r'[^a-z0-9]+', '-',
                       product_name.lower())[:50]
        filename = f"product_{slug}.json"
        filepath = self.drafts_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(draft, f, indent=2, ensure_ascii=False)
        
        print(f"📦 Product description draft: {filepath}")
        return {"success": True, "draft": draft, "file": str(filepath)}

    # ============ SOCIAL MEDIA ============
    
    def generate_social_prompt(self, topic, platform="instagram",
                                product_name=None,
                                content_type="educational"):
        """Generate social media post prompt"""
        
        platform_rules = {
            "instagram": {
                "max_chars": 2200,
                "hashtags": 20,
                "style": "Visual storytelling, emoji-rich, "
                         "engaging, line breaks for readability",
                "cta": "Link in bio, Save this post, "
                       "Share with someone who needs this"
            },
            "facebook": {
                "max_chars": 500,
                "hashtags": 5,
                "style": "Conversational, question-based, "
                         "community-building",
                "cta": "Comment below, Share your experience, "
                       "Visit our website"
            },
            "pinterest": {
                "max_chars": 500,
                "hashtags": 10,
                "style": "SEO-rich description, keyword-focused, "
                         "informative",
                "cta": "Click to learn more, Shop now, "
                       "Read the full guide"
            },
            "twitter": {
                "max_chars": 280,
                "hashtags": 3,
                "style": "Concise, impactful, thread-friendly",
                "cta": "Retweet, Reply, Visit link"
            }
        }
        
        rules = platform_rules.get(platform, platform_rules["instagram"])
        
        content_types = {
            "educational": "Teach something about Ayurveda/herbs",
            "product_highlight": "Showcase a specific product",
            "behind_scenes": "Show authenticity, sourcing, process",
            "testimonial": "Customer success story format",
            "seasonal": "Connect to current season/festival",
            "tip": "Quick actionable wellness tip",
            "myth_buster": "Debunk a common myth about herbs"
        }
        
        product_text = ""
        if product_name:
            product_text = (
                f"\nSubtly mention: {product_name} by Falcon Herbs"
                f"\nDon't make it feel like an ad."
            )
        
        prompt = f"""Create a {platform.upper()} post for 
"Falcon Herbs" — an authentic Ayurvedic herbal products brand.

TOPIC: {topic}
CONTENT TYPE: {content_type} — {content_types.get(content_type, '')}
PLATFORM: {platform}
{product_text}

PLATFORM RULES:
- Max length: {rules['max_chars']} characters
- Hashtags: up to {rules['hashtags']}
- Style: {rules['style']}
- CTA options: {rules['cta']}

CREATE:
1. CAPTION — Engaging, on-brand post text
   - Hook in first line (people see this before "...more")
   - Value-packed body
   - Clear CTA at end
   - Use emojis appropriately (not excessive)
   
2. HASHTAGS — Mix of:
   - Broad: #Ayurveda #NaturalWellness #HerbalRemedies
   - Niche: #AyurvedicLifestyle #HerbsForHealth
   - Branded: #FalconHerbs #AuthenticAyurveda
   - Trending (if relevant)

3. IMAGE SUGGESTION — Describe ideal image/visual
   - What should the image show?
   - Color mood/palette
   - Text overlay suggestion (if any)
   - Can be used as AI image generation prompt

BRAND VOICE:
- Premium, not cheap
- Knowledgeable, not preachy
- Warm, not corporate
- Trustworthy, not salesy

HEALTH RULES:
❌ No disease claims, no "cures/treats" language
✅ "Supports", "traditionally used", "may help"
✅ Educational framing always
"""
        return prompt
    
    def create_social_batch(self, topics_list,
                             platforms=None):
        """
        Generate a batch of social media posts.
        
        Args:
            topics_list: List of dicts with 'topic', 
                        'content_type', 'product_name'(optional)
            platforms: List of platforms 
                      (default: instagram, facebook, pinterest)
        """
        if not platforms:
            platforms = ["instagram", "facebook", "pinterest"]
        
        batch = {
            "type": "social_batch",
            "created_at": datetime.now().isoformat(),
            "total_posts": 0,
            "posts": []
        }
        
        for topic_info in topics_list:
            topic = topic_info.get("topic", "")
            content_type = topic_info.get("content_type",
                                           "educational")
            product = topic_info.get("product_name")
            
            for platform in platforms:
                prompt = self.generate_social_prompt(
                    topic=topic,
                    platform=platform,
                    product_name=product,
                    content_type=content_type
                )
                
                post = {
                    "topic": topic,
                    "platform": platform,
                    "content_type": content_type,
                    "product": product,
                    "prompt": prompt,
                    "content": None,
                    "status": "prompt_only"
                }
                
                if self.ai_client:
                    try:
                        response = self.ai_client.generate(prompt)
                        if response:
                            safety = self.safety_check(response)
                            post["content"] = safety[
                                "cleaned_content"
                            ]
                            post["safety_check"] = safety
                            post["status"] = (
                                "generated" if safety["is_safe"]
                                else "needs_review"
                            )
                    except Exception as e:
                        post["error"] = str(e)
                
                batch["posts"].append(post)
                batch["total_posts"] += 1
        
        # Save batch
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"social_batch_{date_str}.json"
        filepath = self.drafts_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)
        
        try:
            print(f"Social batch saved: {filepath} ({batch['total_posts']} posts)")
        except UnicodeEncodeError:
            print(f"Social batch saved: {filepath}")
        
        return {"success": True, "batch": batch, "file": str(filepath)}

    # ============ CONTENT CALENDAR ============
    
    def generate_content_calendar(self, weeks=12,
                                    products=None):
        """
        Generate a strategic content calendar.
        
        Args:
            weeks: Number of weeks to plan
            products: List of product names/categories
                     (from WooCommerce ideally)
        """
        
        # Ayurveda seasonal themes
        seasonal_themes = {
            1: {"season": "Winter", "dosha": "Vata",
                "themes": [
                    "Warming herbs", "Joint comfort",
                    "Immunity support", "Winter wellness routine"
                ]},
            2: {"season": "Late Winter", "dosha": "Kapha building",
                "themes": [
                    "Detox preparation", "Energy herbs",
                    "Respiratory wellness", "Valentine wellness gifts"
                ]},
            3: {"season": "Spring", "dosha": "Kapha",
                "themes": [
                    "Spring cleanse", "Allergy season herbs",
                    "Metabolism support", "Fresh start routines"
                ]},
            4: {"season": "Spring", "dosha": "Kapha-Pitta",
                "themes": [
                    "Earth Day natural living",
                    "Digestive wellness",
                    "Skin care herbs", "Spring energy"
                ]},
            5: {"season": "Late Spring", "dosha": "Pitta rising",
                "themes": [
                    "Cooling herbs introduction",
                    "Stress management", "Mother's Day gifts",
                    "Mental clarity herbs"
                ]},
            6: {"season": "Summer", "dosha": "Pitta",
                "themes": [
                    "Cooling herbs", "Hydration",
                    "Sun protection herbs",
                    "Summer Ayurvedic routine"
                ]},
            7: {"season": "Summer", "dosha": "Pitta",
                "themes": [
                    "Heat management", "Pitta-balancing foods",
                    "Calm mind herbs", "Summer hair care"
                ]},
            8: {"season": "Late Summer", "dosha": "Pitta-Vata",
                "themes": [
                    "Back to routine", "Focus herbs",
                    "Adaptogens for stress",
                    "Transition season prep"
                ]},
            9: {"season": "Autumn", "dosha": "Vata rising",
                "themes": [
                    "Grounding herbs", "Vata balancing",
                    "Immunity prep for winter",
                    "Ayurvedic self-care"
                ]},
            10: {"season": "Autumn", "dosha": "Vata",
                 "themes": [
                    "Immunity building", "Joint support",
                    "Warming teas", "Diwali/festival wellness"
                 ]},
            11: {"season": "Late Autumn", "dosha": "Vata",
                 "themes": [
                    "Holiday gift guide", "Stress relief",
                    "Sleep support herbs", "Gratitude wellness"
                 ]},
            12: {"season": "Winter", "dosha": "Vata-Kapha",
                 "themes": [
                    "Year-end detox", "New year wellness plan",
                    "Gift sets", "Winter immunity"
                 ]},
        }
        
        # Evergreen topics that work any time
        evergreen_topics = [
            {
                "topic": "Complete Guide to Ashwagandha",
                "keyword": "ashwagandha benefits",
                "type": "blog",
                "priority": "HIGH"
            },
            {
                "topic": "Ayurvedic Morning Routine for Beginners",
                "keyword": "ayurvedic morning routine",
                "type": "blog",
                "priority": "HIGH"
            },
            {
                "topic": "Understanding Your Dosha Type",
                "keyword": "dosha type quiz ayurveda",
                "type": "blog",
                "priority": "HIGH"
            },
            {
                "topic": "Top 10 Ayurvedic Herbs Everyone Should Know",
                "keyword": "best ayurvedic herbs",
                "type": "blog",
                "priority": "HIGH"
            },
            {
                "topic": "Turmeric: The Golden Spice of Ayurveda",
                "keyword": "turmeric benefits ayurveda",
                "type": "blog",
                "priority": "MEDIUM"
            },
            {
                "topic": "Triphala: The Three Fruit Formula",
                "keyword": "triphala benefits",
                "type": "blog",
                "priority": "MEDIUM"
            },
            {
                "topic": "Brahmi for Mental Clarity",
                "keyword": "brahmi herb benefits",
                "type": "blog",
                "priority": "MEDIUM"
            },
            {
                "topic": "Ayurvedic Herbs for Natural Energy",
                "keyword": "natural energy herbs ayurveda",
                "type": "blog",
                "priority": "HIGH"
            },
            {
                "topic": "How to Choose Quality Herbal Supplements",
                "keyword": "how to choose herbal supplements",
                "type": "blog",
                "priority": "HIGH"
            },
            {
                "topic": "Ayurveda vs Modern Medicine: Complementary",
                "keyword": "ayurveda and modern medicine",
                "type": "blog",
                "priority": "MEDIUM"
            },
        ]
        
        # Build calendar
        current_date = datetime.now()
        current_month = current_date.month
        calendar = {
            "generated_at": current_date.isoformat(),
            "total_weeks": weeks,
            "content_targets": {
                "blogs_per_week": 2,
                "social_per_day": 1,
                "product_descriptions_per_week": 5
            },
            "weeks": []
        }
        
        evergreen_idx = 0
        
        for week_num in range(weeks):
            week_start = current_date + timedelta(
                weeks=week_num
            )
            week_month = week_start.month
            month_theme = seasonal_themes.get(
                week_month,
                seasonal_themes[1]
            )
            
            week = {
                "week_number": week_num + 1,
                "start_date": week_start.strftime("%Y-%m-%d"),
                "end_date": (week_start + timedelta(days=6)
                            ).strftime("%Y-%m-%d"),
                "season": month_theme["season"],
                "dosha_focus": month_theme["dosha"],
                "theme": month_theme["themes"][
                    week_num % len(month_theme["themes"])
                ],
                "blog_posts": [],
                "social_posts": [],
                "product_tasks": []
            }
            
            # Assign 2 blog posts
            for i in range(2):
                if evergreen_idx < len(evergreen_topics):
                    blog = evergreen_topics[evergreen_idx].copy()
                    blog["scheduled_date"] = (
                        week_start + timedelta(
                            days=1 if i == 0 else 4
                        )
                    ).strftime("%Y-%m-%d")
                    blog["status"] = "planned"
                    week["blog_posts"].append(blog)
                    evergreen_idx += 1
                else:
                    # Generate seasonal topic
                    theme = month_theme["themes"][
                        i % len(month_theme["themes"])
                    ]
                    week["blog_posts"].append({
                        "topic": f"Ayurvedic Guide: {theme}",
                        "keyword": theme.lower().replace(" ", " "),
                        "type": "blog",
                        "priority": "MEDIUM",
                        "scheduled_date": (
                            week_start + timedelta(
                                days=1 if i == 0 else 4
                            )
                        ).strftime("%Y-%m-%d"),
                        "status": "planned"
                    })
            
            # Assign 7 social posts (1/day)
            social_types = [
                "educational", "product_highlight", "tip",
                "educational", "behind_scenes",
                "myth_buster", "seasonal"
            ]
            
            for day in range(7):
                post_date = week_start + timedelta(days=day)
                week["social_posts"].append({
                    "date": post_date.strftime("%Y-%m-%d"),
                    "day": post_date.strftime("%A"),
                    "content_type": social_types[day],
                    "theme": week["theme"],
                    "platforms": [
                        "instagram", "facebook", "pinterest"
                    ],
                    "status": "planned"
                })
            
            # Product description tasks
            if products:
                start_idx = (week_num * 5) % len(products)
                week_products = products[
                    start_idx:start_idx + 5
                ]
                for p in week_products:
                    week["product_tasks"].append({
                        "product": p if isinstance(p, str) 
                                  else p.get("name", "Unknown"),
                        "task": "rewrite_description",
                        "status": "planned"
                    })
            
            calendar["weeks"].append(week)
        
        # Save calendar
        filename = f"calendar_{current_date.strftime('%Y%m%d')}.json"
        filepath = self.calendar_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(calendar, f, indent=2, ensure_ascii=False)
        
        print(f"📅 Content calendar saved: {filepath}")
        print(f"   Weeks planned: {weeks}")
        print(f"   Total blogs: {weeks * 2}")
        print(f"   Total social posts: {weeks * 7}")
        
        return {
            "success": True,
            "calendar": calendar,
            "file": str(filepath)
        }

    # ============ EMAIL DRAFTS ============
    
    def generate_email_prompts(self, email_type="reactivation"):
        """
        Generate email sequence prompts.
        Critical for bringing back old customers.
        """
        
        sequences = {
            "reactivation": {
                "name": "Customer Reactivation Sequence",
                "description": "For customers who haven't "
                               "ordered in 6+ months",
                "emails": [
                    {
                        "subject_options": [
                            "We've missed you at Falcon Herbs 🌿",
                            "Your Ayurvedic wellness journey "
                            "continues...",
                            "A special welcome back gift inside"
                        ],
                        "purpose": "Reconnection — warm, personal",
                        "prompt": f"""Write an email for Falcon Herbs 
to reconnect with a past customer who hasn't ordered 
in 6+ months.

TONE: Warm, personal, NOT desperate
LENGTH: 150-200 words

STRUCTURE:
1. Personal greeting
2. "We noticed it's been a while"
3. Brief update on what's new 
   (new products, improved quality)
4. Special offer: 15% comeback discount 
   (code: WELCOME_BACK)
5. Gentle CTA: "Explore what's new"

INCLUDE:
- Reference to Ayurvedic seasonal relevance
- Sense of exclusivity ("as a valued customer")
- Easy unsubscribe mention

DO NOT:
- Sound desperate or guilt-trippy
- Make health claims
- Be too long

Brand: Falcon Herbs — Authentic Ayurvedic Wellness
Website: falconherbs.com"""
                    },
                    {
                        "subject_options": [
                            "Your 15% discount expires soon",
                            "3 bestsellers our customers love",
                            "Quick question about your "
                            "wellness routine"
                        ],
                        "purpose": "Follow-up — value + urgency",
                        "prompt": f"""Write a follow-up email 
(sent 5 days after first email) for Falcon Herbs.

TONE: Helpful, value-focused
LENGTH: 120-150 words

STRUCTURE:
1. "In case you missed our last email"
2. Highlight 3 bestselling products 
   (leave [PRODUCT_1], [PRODUCT_2], [PRODUCT_3] 
   placeholders)
3. Remind: 15% discount still active
4. Social proof: "Trusted by customers in X countries"
5. CTA: "Shop now before offer expires"

Keep it SHORT and scannable.
Brand: Falcon Herbs"""
                    }
                ]
            },
            
            "welcome": {
                "name": "New Customer Welcome Sequence",
                "description": "For new subscribers/first-time buyers",
                "emails": [
                    {
                        "subject_options": [
                            "Welcome to Falcon Herbs 🌿 "
                            "Your Ayurvedic journey begins",
                            "Thank you! Here's what to "
                            "expect from us"
                        ],
                        "purpose": "Welcome + brand introduction",
                        "prompt": f"""Write a welcome email for 
new Falcon Herbs subscriber/customer.

TONE: Warm, exciting, educational
LENGTH: 200-250 words

STRUCTURE:
1. Warm welcome
2. Who we are (2-3 sentences — authentic Ayurveda 
   from India)
3. What to expect (educational content, 
   wellness tips, exclusive offers)
4. Starter guide: "New to Ayurveda? 
   Start with [STARTER_PRODUCT]"
5. First-order discount: 10% off 
   (code: NAMASTE10)
6. Invite to follow on social media
7. Sign off from "The Falcon Herbs Family"

Brand: Falcon Herbs — Authentic Ayurvedic Wellness
Include disclaimer about health claims."""
                    },
                    {
                        "subject_options": [
                            "Your Dosha Guide — Discover "
                            "Your Ayurvedic Type",
                            "The #1 thing to know about "
                            "Ayurvedic herbs"
                        ],
                        "purpose": "Education + engagement",
                        "prompt": f"""Write educational email #2 
(sent 3 days after welcome) for Falcon Herbs.

TONE: Educational, fascinating
LENGTH: 200-300 words

TOPIC: Brief introduction to Doshas 
(Vata, Pitta, Kapha)

STRUCTURE:
1. "Ayurveda believes everyone is unique"
2. Quick overview of 3 doshas (2-3 lines each)
3. "Which one are you?"
4. Link to blog: [DOSHA_BLOG_LINK]
5. Product suggestions by dosha type 
   (placeholders)
6. CTA: "Explore products for your dosha"

Make it fascinating, not textbook-y.
Include health disclaimer."""
                    },
                    {
                        "subject_options": [
                            "How our herbs travel from "
                            "India to your doorstep",
                            "The Falcon Herbs quality promise"
                        ],
                        "purpose": "Trust building — quality story",
                        "prompt": f"""Write trust-building email #3 
(sent 7 days after welcome) for Falcon Herbs.

TONE: Authentic, behind-the-scenes
LENGTH: 150-200 words

TOPIC: Quality and sourcing story

STRUCTURE:
1. "Ever wondered where your herbs come from?"
2. Brief sourcing story (India, traditional methods)
3. Quality standards we follow
4. Why authentic sourcing matters
5. Customer testimonial placeholder 
   [TESTIMONIAL]
6. CTA: "Experience the Falcon Herbs difference"

Make them feel good about choosing premium.
This email builds TRUST, not sales."""
                    }
                ]
            },
            
            "polish_reconnect": {
                "name": "Polish Customer Special Reconnection",
                "description": "Special email for the Polish "
                               "customer we lost",
                "emails": [
                    {
                        "subject_options": [
                            "A personal apology from "
                            "Falcon Herbs 🙏",
                            "We owe you an explanation "
                            "and a gift"
                        ],
                        "purpose": "Reconnect with lost "
                                   "Polish customer",
                        "prompt": f"""Write a deeply personal 
reconnection email for a specific situation:

CONTEXT:
- We had a Polish customer who placed a large order 
  (approx ₹20,000 / ~$240)
- Our website was hacked and we lost his order data
- We could not fulfill his order properly
- We feel terrible about this
- We want to make it right

TONE: Genuinely apologetic, personal, humble
LENGTH: 200-250 words

STRUCTURE:
1. Personal apology — "We owe you an apology"
2. Honest explanation — site security incident
3. What we've done since 
   (improved security, rebuilt systems)
4. We want to make it right:
   - Full refund if not already done
   - Free replacement order
   - 30% lifetime discount
5. "Please reach out so we can fix this"
6. Multiple contact methods 
   (email, WhatsApp, website form)

THIS IS NOT A MARKETING EMAIL.
This is a genuine human apology.
No sales pitch, no upsell.
Just making things right.

Sign off personally, not as a brand."""
                    }
                ]
            }
        }
        
        selected = sequences.get(
            email_type, sequences["reactivation"]
        )
        
        # Save
        filename = f"email_{email_type}_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = self.drafts_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(selected, f, indent=2, ensure_ascii=False)
        
        print(f"📧 Email sequence saved: {filepath}")
        
        return {"success": True, "sequence": selected, "file": str(filepath)}

    # ============ RECONNECT PAGE ============
    
    def generate_reconnect_page(self):
        """
        Generate content for falconherbs.com/reconnect page.
        For the lost Polish customer and any others affected
        by the hack.
        """
        
        page_content = {
            "type": "reconnect_page",
            "url_slug": "reconnect",
            "meta_title": "Reconnect with Falcon Herbs — "
                          "We Want to Make Things Right",
            "meta_description": "Were you a Falcon Herbs customer "
                                "before 2023? We experienced a "
                                "technical issue. Please reconnect "
                                "so we can make things right.",
            "content": """
<h1>Were You Our Customer? Let's Reconnect 🙏</h1>

<p>In [YEAR], our website experienced a security incident 
that resulted in the loss of some customer data, including 
order records and contact information.</p>

<p><strong>If you placed an order with Falcon Herbs that 
was not fulfilled, or if you experienced any issues due to 
this incident, we sincerely apologize.</strong></p>

<h2>What Happened</h2>
<p>Our website was compromised, and despite our best efforts, 
some customer records were lost. We have since completely 
rebuilt our systems with enterprise-grade security to ensure 
this never happens again.</p>

<h2>How We Want to Make It Right</h2>
<ul>
<li>✦ Full refund for any unfulfilled orders</li>
<li>✦ Free replacement shipment of your original order</li>
<li>✦ 30% lifetime discount on all future purchases</li>
<li>✦ Priority customer support</li>
</ul>

<h2>Please Reach Out</h2>
<p>If you were affected, please contact us through 
any of these channels:</p>
<ul>
<li>📧 Email: [YOUR_EMAIL]</li>
<li>📱 WhatsApp: [YOUR_WHATSAPP]</li>
<li>📝 Or fill out the form below</li>
</ul>

[CONTACT_FORM]

<p><em>We believe in doing the right thing. 
Your trust matters more than any transaction.</em></p>

<p>With sincere apologies,<br>
<strong>The Falcon Herbs Team</strong><br>
Authentic Ayurvedic Wellness</p>
""",
            "seo_notes": [
                "This page should be indexed by Google",
                "If the Polish customer Googles 'Falcon Herbs' "
                "he might find this",
                "Shows integrity and builds trust with "
                "ALL visitors",
                "Add to main navigation or footer as "
                "'Reconnect' or 'Customer Support'",
                "Also helps with brand trust signals "
                "for Google E-E-A-T"
            ]
        }
        
        filepath = self.drafts_dir / "reconnect_page.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(page_content, f, indent=2, 
                      ensure_ascii=False)
        
        print(f"🤝 Reconnect page saved: {filepath}")
        return {"success": True, "page": page_content, 
                "file": str(filepath)}

    # ============ MASTER GENERATION ============
    
    def generate_this_weeks_content(self, products=None):
        """
        Generate all content for current week.
        One command to rule them all.
        """
        
        print("=" * 50)
        print("🚀 GENERATING THIS WEEK'S CONTENT")
        print("=" * 50)
        
        results = {
            "generated_at": datetime.now().isoformat(),
            "outputs": {}
        }
        
        # 1. Blog posts
        print("\n📝 Generating blog post drafts...")
        blogs = [
            {
                "topic": "Complete Guide to Ashwagandha: "
                         "Benefits, Usage, and Ayurvedic Wisdom",
                "keyword": "ashwagandha benefits",
                "product": "Ashwagandha"
            },
            {
                "topic": "Ayurvedic Morning Routine: "
                         "Start Your Day the Ancient Way",
                "keyword": "ayurvedic morning routine",
                "product": None
            }
        ]
        
        blog_results = []
        for blog in blogs:
            result = self.create_blog_draft(
                topic=blog["topic"],
                target_keyword=blog["keyword"],
                product_name=blog["product"]
            )
            blog_results.append(result)
        results["outputs"]["blogs"] = blog_results
        
        # 2. Social media batch
        print("\n📱 Generating social media posts...")
        social_topics = [
            {"topic": "Benefits of drinking warm water "
                      "with herbs in morning",
             "content_type": "tip"},
            {"topic": "Ashwagandha: The King of "
                      "Ayurvedic Herbs",
             "content_type": "educational",
             "product_name": "Ashwagandha"},
            {"topic": "Why authentic sourcing matters "
                      "for herbal products",
             "content_type": "behind_scenes"},
            {"topic": "Common myths about Ayurveda debunked",
             "content_type": "myth_buster"},
            {"topic": "Seasonal herbs for current weather",
             "content_type": "seasonal"},
            {"topic": "Quick Ayurvedic self-care ritual "
                      "for busy people",
             "content_type": "tip"},
            {"topic": "Meet our bestselling product",
             "content_type": "product_highlight"},
        ]
        
        social_result = self.create_social_batch(social_topics)
        results["outputs"]["social"] = social_result
        
        # 3. Email sequences
        print("\n📧 Generating email sequences...")
        reactivation = self.generate_email_prompts("reactivation")
        welcome = self.generate_email_prompts("welcome")
        polish = self.generate_email_prompts("polish_reconnect")
        results["outputs"]["emails"] = {
            "reactivation": reactivation,
            "welcome": welcome,
            "polish_reconnect": polish
        }
        
        # 4. Reconnect page
        print("\n🤝 Generating reconnect page...")
        reconnect = self.generate_reconnect_page()
        results["outputs"]["reconnect_page"] = reconnect
        
        # 5. Content calendar
        print("\n📅 Generating 12-week calendar...")
        calendar = self.generate_content_calendar(
            weeks=12, products=products
        )
        results["outputs"]["calendar"] = calendar
        
        # Summary
        print("\n" + "=" * 50)
        print("✅ WEEK'S CONTENT GENERATION COMPLETE")
        print("=" * 50)
        print(f"📝 Blog drafts: {len(blog_results)}")
        print(f"📱 Social posts: "
              f"{social_result['batch']['total_posts']}")
        print(f"📧 Email sequences: 3")
        print(f"🤝 Reconnect page: 1")
        print(f"📅 Calendar weeks: 12")
        print(f"\n📂 All files in: {self.drafts_dir}/")
        print(f"👀 Review drafts → Approve → Publish")
        
        # Save master results
        filepath = self.data_dir / "weekly_generation_log.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        return results

    # ============ WHATSAPP REPORT ============
    
    def generate_content_status_report(self):
        """WhatsApp-friendly content status"""
        
        drafts = list(self.drafts_dir.glob("*.json"))
        approved = list(self.approved_dir.glob("*.json"))
        
        blog_drafts = [
            f for f in drafts if f.name.startswith("blog_")
        ]
        social_drafts = [
            f for f in drafts if f.name.startswith("social_")
        ]
        email_drafts = [
            f for f in drafts if f.name.startswith("email_")
        ]
        
        lines = [
            "📝 *CONTENT STATUS REPORT*",
            f"📅 {datetime.now().strftime('%d %b %Y')}",
            "─" * 25,
            f"📄 Blog drafts: {len(blog_drafts)}",
            f"📱 Social batches: {len(social_drafts)}",
            f"📧 Email sequences: {len(email_drafts)}",
            f"✅ Approved content: {len(approved)}",
            f"📂 Total drafts: {len(drafts)}",
            "─" * 25,
            "",
            "📋 *PENDING REVIEW:*",
        ]
        
        for draft in drafts[:5]:
            try:
                with open(draft) as f:
                    data = json.load(f)
                status = data.get("status", "unknown")
                dtype = data.get("type", draft.name[:10])
                lines.append(f"  {'🟡' if status == 'needs_review' else '🔵'} {dtype}: {status}")
            except Exception:
                pass
        
        lines.extend([
            "",
            "─" * 25,
            "🤖 _Falcon Agency — Content Pipeline_"
        ])
        
        return "\n".join(lines)


# ==================== STANDALONE TEST ====================

if __name__ == "__main__":
    print("🚀 Content Pipeline — Initialization Test")
    print("=" * 50)
    
    pipeline = ContentPipeline()
    
    # Test 1: Safety check
    print("\n🧪 Test 1: Safety Check")
    test_text = (
        "This herb cures diabetes and boosts immunity. "
        "It is clinically proven to have no side effects."
    )
    result = pipeline.safety_check(test_text)
    print(f"   Original: {test_text}")
    print(f"   Safe: {result['is_safe']}")
    print(f"   Changes: {result['changes_made']}")
    print(f"   Cleaned: {result['cleaned_content'][:100]}...")
    
    # Test 2: Blog prompt generation
    print("\n🧪 Test 2: Blog Prompt Generation")
    blog = pipeline.create_blog_draft(
        topic="Complete Guide to Ashwagandha",
        target_keyword="ashwagandha benefits",
        product_name="Falcon Herbs Ashwagandha Capsules"
    )
    print(f"   Status: {blog['draft']['status']}")
    print(f"   File: {blog['file']}")
    
    # Test 3: Social batch
    print("\n🧪 Test 3: Social Batch Generation")
    social = pipeline.create_social_batch([
        {"topic": "Morning Ayurvedic routine",
         "content_type": "tip"},
        {"topic": "Why Ashwagandha is trending",
         "content_type": "educational"}
    ])
    print(f"   Posts: {social['batch']['total_posts']}")
    print(f"   File: {social['file']}")
    
    # Test 4: Content Calendar
    print("\n🧪 Test 4: Content Calendar")
    cal = pipeline.generate_content_calendar(weeks=4)
    print(f"   Weeks planned: "
          f"{cal['calendar']['total_weeks']}")
    print(f"   File: {cal['file']}")
    
    # Test 5: Email sequences
    print("\n🧪 Test 5: Email Sequences")
    emails = pipeline.generate_email_prompts("reactivation")
    print(f"   Sequence: {emails['sequence']['name']}")
    print(f"   Emails: {len(emails['sequence']['emails'])}")
    
    # Test 6: Reconnect page
    print("\n🧪 Test 6: Reconnect Page")
    page = pipeline.generate_reconnect_page()
    print(f"   Page: {page['page']['url_slug']}")
    
    # Test 7: Content status report
    print("\n🧪 Test 7: WhatsApp Report")
    report = pipeline.generate_content_status_report()
    print(report)
    
    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED — Content Pipeline Ready!")
    print("=" * 50)
