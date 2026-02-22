"""
agents/media.py — Revenue Engine Content Agent for Falcon Agency
==================================================================

The Media Agent is the revenue engine of Falcon Agency. Every piece
of content it generates must earn trust, rank in search, and convert
skeptical international buyers into paying customers.

It generates, scores, and queues:
    • Product descriptions (SEO-optimised, buyer-psychology-driven)
    • Blog posts (E-E-A-T compliant, featured-snippet targeted)
    • Social posts (Instagram + Facebook, HeroPost-ready)
    • Trust content (shipping pages, about us, quality pages)
    • Seasonal campaigns (complete multi-channel packages)

Content Pipeline:
    Generate → Score (algorithmic + AI) → Queue/Rewrite → Export → Approve → Publish
                        │
                   Score ≥ 70? ─── YES → data/content_queue/{type}/
                        │
                        NO → One rewrite attempt → Score again
                                    │
                              Still < 70? → data/content_queue/{type}/review/
                                              + WhatsApp notification to owner

Safety:
    • Medical claims auto-detected and blocked
    • No content published without owner approval
    • Atomic file writes prevent corruption
    • Cost governance: every API call logged with token count and USD estimate
    • Directory traversal protection on all file paths

Business Context:
    Indian herbal products (falconherbs.com) → AU, UAE, USA, UK, India
    Buyer psychology: skeptical of Indian vendors, need trust signals
    E-E-A-T: Experience, Expertise, Authority, Trust in every piece
    Never: "cures", "treats", "heals" — Always: "may support", "traditionally used"
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.logger import log
from core.approval import ApprovalSystem
from agents.base_agent import BaseAgent
from core.ai_client import call_ai


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PATHS & CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR:     Path = PROJECT_ROOT / "data"

# Queue directories
QUEUE_DIR:     Path = DATA_DIR / "content_queue"
PRODUCTS_DIR:  Path = QUEUE_DIR / "products"
BLOG_DIR:      Path = QUEUE_DIR / "blog"
SOCIAL_DIR:    Path = QUEUE_DIR / "social"
TRUST_DIR:     Path = QUEUE_DIR / "trust"
HEROPOST_DIR:  Path = DATA_DIR / "heropost_queue"
ARCHIVE_DIR:   Path = DATA_DIR / "content_archive"
INDEX_FILE:    Path = DATA_DIR / "content_index.json"

# Review subdirectories (content that failed auto-scoring)
PRODUCTS_REVIEW: Path = PRODUCTS_DIR / "review"
BLOG_REVIEW:     Path = BLOG_DIR / "review"

# API configuration
HTTP_TIMEOUT: int = 30  # Claude can take a moment for long content
DEFAULT_MAX_TOKENS: int = 4000
SCORE_THRESHOLD: int = 70

# Model selection — Gemini (free tier)
MODEL_SONNET: str = "gemini-flash-lite-latest"
MODEL_HAIKU:  str = "gemini-flash-lite-latest"

# Cost tracking — Gemini free tier, cost = 0
COST_PER_1K: Dict[str, Dict[str, float]] = {
    MODEL_SONNET: {"input": 0.0, "output": 0.0},
    MODEL_HAIKU:  {"input": 0.0, "output": 0.0},
}

# Medical claims — FORBIDDEN phrases (case-insensitive)
_FORBIDDEN_CLAIMS: List[str] = [
    "cures", "cure for", "treats", "treatment for", "heals",
    "healing properties that eliminate", "prevents disease",
    "clinically proven to cure", "guaranteed results",
    "FDA approved", "100% effective", "miracle", "magic cure",
    "eliminates cancer", "reverses diabetes", "instant relief guaranteed",
    "scientifically proven to treat", "drug replacement",
    "no side effects guaranteed", "replaces medication",
]

# Absolute claims — FLAGGED phrases
_ABSOLUTE_CLAIMS: List[str] = [
    "guaranteed", "100% proven", "absolutely", "never fails",
    "always works", "instant results", "overnight results",
    "permanent cure", "complete elimination",
]

# Spam trigger words for safety scoring
_SPAM_TRIGGERS: List[str] = [
    "buy now!!!", "limited time only!!!", "act fast!!!",
    "you won't believe", "doctors hate this", "one weird trick",
    "click here immediately", "FREE FREE FREE",
]

# Transition words for readability scoring
_TRANSITION_WORDS: List[str] = [
    "however", "therefore", "additionally", "moreover", "furthermore",
    "consequently", "meanwhile", "nevertheless", "in addition",
    "for example", "in contrast", "similarly", "as a result",
    "on the other hand", "in conclusion", "specifically",
    "importantly", "notably", "interestingly", "traditionally",
]

# Default keywords per herb (used when params don't include keywords)
_DEFAULT_KEYWORDS: Dict[str, List[str]] = {
    "ashwagandha": ["buy ashwagandha online", "ashwagandha powder", "ashwagandha benefits", "withania somnifera", "ashwagandha for stress"],
    "tulsi": ["holy basil", "tulsi tea", "tulsi benefits", "tulsi for immunity", "buy tulsi online"],
    "triphala": ["triphala powder", "triphala benefits", "triphala for digestion", "buy triphala online", "ayurvedic detox"],
    "brahmi": ["brahmi powder", "brahmi for memory", "bacopa monnieri", "brahmi benefits", "buy brahmi online"],
    "neem": ["neem powder", "neem benefits", "neem for skin", "buy neem online", "neem capsules"],
    "shatavari": ["shatavari powder", "shatavari for women", "shatavari benefits", "asparagus racemosus", "buy shatavari online"],
    "moringa": ["moringa powder", "moringa benefits", "moringa oleifera", "buy moringa online", "moringa superfood"],
    "amla": ["amla powder", "indian gooseberry", "amla for hair", "amla vitamin c", "buy amla online"],
    "giloy": ["giloy benefits", "guduchi", "giloy for immunity", "tinospora cordifolia", "buy giloy online"],
    "haritaki": ["haritaki powder", "haritaki benefits", "haritaki for digestion", "buy haritaki online", "terminalia chebula"],
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _timestamp_hex() -> str:
    return uuid.uuid4().hex[:8]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SYSTEM PROMPTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRODUCT_SYSTEM_PROMPT: str = (
    "You are an expert Ayurvedic product copywriter with 15 years experience "
    "selling Indian herbal products to international markets. You understand "
    "both the ancient wisdom of Ayurveda AND modern Western buyer psychology.\n\n"
    "Your writing:\n"
    "- Opens with the buyer's pain/desire (not with 'Introducing...')\n"
    "- Weaves Ayurvedic tradition with modern scientific validation\n"
    "- Uses sensory language where appropriate\n"
    "- Includes trust signals naturally (not salesy)\n"
    "- Has a clear call to action\n"
    "- Is SEO-optimised without keyword stuffing\n"
    "- Never makes unsubstantiated medical claims\n"
    "- Always says 'may support' / 'traditionally used for' not 'cures' / 'treats'\n"
    "- Speaks to international buyers who are skeptical of Indian online vendors\n"
    "- Builds confidence through authenticity, sourcing transparency, and heritage"
)

BLOG_SYSTEM_PROMPT: str = (
    "You are a medical content writer specialising in Ayurvedic and herbal "
    "medicine for Western audiences. You write for E-E-A-T compliance.\n\n"
    "Your articles:\n"
    "- Are factually accurate and cite traditional Ayurvedic sources\n"
    "- Use clear, accessible language (Flesch reading ease 60+)\n"
    "- Include relevant scientific backing where available\n"
    "- Build genuine expertise and trust — no fluff\n"
    "- Are structured for featured snippet capture\n"
    "- Include natural internal linking opportunities to falconherbs.com\n"
    "- Never make medical claims — always 'may support', 'traditionally used'\n"
    "- Follow Google's helpful content guidelines\n\n"
    "You write in this voice: knowledgeable friend who happens to be an "
    "Ayurvedic expert, not a corporate health brand."
)

SOCIAL_SYSTEM_PROMPT: str = (
    "You are a social media content strategist for an authentic Indian herbal "
    "products company. You create content that stops the scroll and builds "
    "genuine community around Ayurvedic wellness.\n\n"
    "Your posts:\n"
    "- Hook in the first line (visible before 'more')\n"
    "- Educate AND inspire — never just sell\n"
    "- Use storytelling or relatable scenarios\n"
    "- Sound authentic, not corporate\n"
    "- Include strategic emoji use (not excessive)\n"
    "- Drive engagement through questions and community building\n"
    "- Never make medical claims\n"
    "- Build trust for international buyers considering an Indian brand"
)

TRUST_SYSTEM_PROMPT: str = (
    "You write compelling, confidence-building website content that converts "
    "hesitant international buyers into customers. You understand that buying "
    "herbal products from India requires trust, and you know how to build it.\n\n"
    "Your content:\n"
    "- Is specific, not vague (exact delivery timeframes, not 'fast shipping')\n"
    "- Addresses real concerns international buyers have\n"
    "- Sounds warm and genuine, not corporate\n"
    "- Shows pride in Indian herbal heritage without being defensive\n"
    "- Builds confidence through transparency and generosity\n"
    "- Makes the buyer feel they've found something authentic and special"
)

SCORING_SYSTEM_PROMPT: str = (
    "You are a strict content quality auditor for an Indian herbal products "
    "company that sells to Australia, UAE, USA, and UK. Score quickly and precisely. "
    "You evaluate content for trust-building effectiveness with skeptical "
    "international buyers and compliance with health content regulations."
)

IDEAS_SYSTEM_PROMPT: str = (
    "You are a content strategist for an Indian herbal products company "
    "selling globally. Generate specific, actionable content ideas that will "
    "rank in international search results and convert health-conscious buyers. "
    "Focus on search intent — what are people actually typing into Google "
    "when looking for Ayurvedic products? Think like a buyer in each market."
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MEDIA AGENT CLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class MediaAgent(BaseAgent):
    """
    Revenue-engine content agent for Falcon Agency.

    Generates, scores, queues, and exports content for falconherbs.com.
    Every piece of content targets international buyers searching for
    authentic Indian herbal products.

    Parameters
    ----------
    approval : ApprovalSystem
        For notifications and publish-gating.
    """

    # ──────────────────────────────────────────────────────────────────
    #  Init
    # ──────────────────────────────────────────────────────────────────

    def __init__(self, whatsapp_client=None):
        """
        Initialise the Media Agent.
        """
        super().__init__(whatsapp_client)
        self.name = "Media"
        self.ai_role = "media"
        self.capabilities = [
            "Social media content",
            "Graphic design prompts",
            "Visual content planning",
            "Brand consistency",
            "Caption writing",
            "Hashtag strategy"
        ]

        # Preserve legacy properties
        self._approval = None

        # ── Gemini client ──
        self._client: Any = None
        self._api_available: bool = False
        try:
            from google import genai
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if api_key:
                self._client = genai.Client(api_key=api_key)
                self._api_available = True
                log.info("MediaAgent: Gemini client ready")
            else:
                log.warning("MediaAgent: GEMINI_API_KEY not set — content generation disabled")
        except ImportError:
            log.critical("MediaAgent: 'google-genai' package not installed — run: pip install google-genai")
        except Exception as exc:
            log.critical("MediaAgent: Gemini init failed: %s", exc)

        # ── Cost tracking ──
        self._session_spend: float = 0.0
        self._session_calls: int = 0

        # ── Create directory structure ──
        for d in [PRODUCTS_DIR, PRODUCTS_REVIEW, BLOG_DIR, BLOG_REVIEW,
                  SOCIAL_DIR, TRUST_DIR, HEROPOST_DIR, ARCHIVE_DIR]:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                log.warning("Cannot create directory %s: %s", d, exc)

        # ── Load or create content index ──
        if not INDEX_FILE.exists():
            self._write_json(INDEX_FILE, [])

        log.info(
            "MediaAgent initialised  |  api=%s  |  queue=%s  |  spend=$%.4f",
            "✅" if self._api_available else "❌",
            QUEUE_DIR,
            self._session_spend,
        )

    # ══════════════════════════════════════════════════════════════════
    #  DISPATCH INTERFACE
    # ══════════════════════════════════════════════════════════════════

    def execute(self, action: str, details: str) -> str:
        """Media agent handles creative tasks"""
        
        plan = self.think(action, {"details": details})
        
        action_lower = action.lower()
        
        if "social" in action_lower or "post" in action_lower:
            return self._do_social_content(action, details)
        elif "design" in action_lower or "graphic" in action_lower:
            return self._do_design_prompt(action, details)
        elif "caption" in action_lower:
            return self._do_caption(action, details)
        elif "hashtag" in action_lower:
            return self._do_hashtags(action, details)
        else:
            return self._do_generic_creative(action, details)
    
    def _do_social_content(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": """You are a social media expert.
Create engaging, viral-worthy content.
Output JSON: {"posts": [{"platform": "...", "content": "...", "media_suggestion": "...", "best_time": "..."}], "campaign_theme": "..."}"""},
            {"role": "user", "content": f"Action: {action}\nDetails: {details}"}
        ]
        response = call_ai("media", messages)
        self.report_to_owner(f"📱 Social content ready")
        return response
    
    def _do_design_prompt(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": """You are a creative director.
Generate detailed prompts for AI image generation tools.
Output JSON: {"prompts": [{"tool": "midjourney|dalle|stable", "prompt": "...", "style": "...", "aspect_ratio": "..."}]}"""},
            {"role": "user", "content": f"Create design for: {action}\nDetails: {details}"}
        ]
        response = call_ai("media", messages)
        self.report_to_owner(f"🎨 Design prompts ready")
        return response
    
    def _do_caption(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": "Write engaging captions that drive engagement. Include CTA."},
            {"role": "user", "content": f"Caption for: {action}\nContext: {details}"}
        ]
        return call_ai("media", messages)
    
    def _do_hashtags(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": """Generate strategic hashtag sets.
Output JSON: {"primary": [...], "secondary": [...], "niche": [...], "avoid": [...]}"""},
            {"role": "user", "content": f"Hashtags for: {action}\nDetails: {details}"}
        ]
        return call_ai("media", messages)
    
    def _do_generic_creative(self, action: str, details: str) -> str:
        messages = [
            {"role": "system", "content": "You are a creative expert. Help with any media/creative task."},
            {"role": "user", "content": f"Action: {action}\nDetails: {details}"}
        ]
        return call_ai("media", messages)

    def handle(self, task: str, site: str, params: dict) -> dict:
        """
        Route *task* to the appropriate content method.

        Every task is wrapped in try/except — agent errors never crash the Director.

        Recognised Tasks
        ----------------
        ``create_product_description`` — SEO product copy
        ``create_blog_post``           — E-E-A-T blog article
        ``create_social_post``         — Instagram/Facebook content
        ``create_trust_content``       — Shipping, About Us, Quality pages
        ``create_content``             — General content (routes by params)
        ``score_content``              — Quality gate scoring
        ``get_content_queue``          — Pipeline status
        ``export_to_heropost``         — HeroPost export
        ``get_content_ideas``          — AI content calendar
        ``create_campaign``            — Seasonal campaign package
        ``general_task``               — Best-effort routing

        Returns
        -------
        dict
            Standard result: ``{status, task, site, data, error, timestamp, agent}``
        """
        log.info("MediaAgent.handle  |  task=%s  |  site=%s", task, site)

        try:
            if task == "create_product_description":
                data = self.write_product_description(site, params)
            elif task == "create_blog_post":
                data = self.write_blog_post(site, params)
            elif task == "create_social_post":
                data = self.write_social_post(site, params)
            elif task == "create_trust_content":
                data = self.write_trust_content(site, params)
            elif task == "create_content":
                data = self._route_create_content(site, params)
            elif task == "score_content":
                data = self.score_content(site, params)
            elif task in ("get_content_queue", "content_status"):
                data = self.get_queue_status(site, params)
            elif task == "export_to_heropost":
                data = self.export_for_heropost(site, params)
            elif task == "get_content_ideas":
                data = self.generate_content_ideas(site, params)
            elif task == "create_campaign":
                data = self.create_seasonal_campaign(site, params)
            elif task == "general_task":
                data = self._handle_general_task(site, params)
            else:
                log.warning("MediaAgent: unknown task '%s'", task)
                return self._build_result(task, site, "skipped", {}, error=f"Unknown task: {task}")

            status = "success"
            if isinstance(data, dict):
                if data.get("error"):
                    status = "failed"
                elif data.get("status") == "skipped":
                    status = "skipped"

            return self._build_result(task, site, status, data)

        except Exception as exc:
            log.critical("MediaAgent.handle crashed  |  task=%s  |  %s", task, exc, exc_info=True)
            return self._build_result(task, site, "failed", {}, error=f"{type(exc).__name__}: {str(exc)[:300]}")

    # ══════════════════════════════════════════════════════════════════
    #  1. PRODUCT DESCRIPTION
    # ══════════════════════════════════════════════════════════════════

    def write_product_description(self, site: str, params: dict) -> dict:
        """
        Generate an SEO-optimised product description for an herbal product.

        Generates content via Claude Sonnet, auto-scores it, and either
        queues it (score ≥ 70) or triggers one rewrite attempt. If the
        rewrite still fails, saves to the review queue with a WhatsApp
        notification to the owner.

        Parameters
        ----------
        site : str
            Target site.
        params : dict
            Required: ``product_name``, ``product_slug``.
            Optional: ``target_market``, ``keywords``, ``word_count``.

        Returns
        -------
        dict
            Content data including text, scores, file path, word count.
        """
        if not self._api_available:
            return {"status": "skipped", "reason": "Anthropic API not configured"}

        product_name = params.get("product_name", "Herbal Product")
        product_slug = params.get("product_slug", product_name.lower().replace(" ", "-"))
        target_market = params.get("target_market", "GLOBAL")
        word_count = min(max(params.get("word_count", 200), 150), 350)
        keywords = params.get("keywords", [])

        log.info(
            "Writing product description  |  product=%s  |  market=%s  |  words=%d",
            product_name, target_market, word_count,
        )

        # Auto-generate keywords if not provided
        if not keywords:
            herb_key = product_slug.split("-")[0].lower()
            keywords = _DEFAULT_KEYWORDS.get(herb_key, [f"buy {product_name} online"])
            if target_market != "GLOBAL":
                keywords = [f"{kw} {target_market.lower()}" for kw in keywords[:3]] + keywords

        primary_kw = keywords[0] if keywords else product_name.lower()
        secondary_kw = ", ".join(keywords[1:4]) if len(keywords) > 1 else ""

        # Build market-specific shipping line
        shipping_line = ""
        if target_market != "GLOBAL":
            shipping_line = f"\nInclude naturally: shipping confidence for {target_market} buyers."

        user_prompt = (
            f"Write a product description for: {product_name}\n"
            f"Target market: {target_market}\n"
            f"Primary keyword: {primary_kw}\n"
            f"Secondary keywords: {secondary_kw}\n"
            f"Word count: {word_count} words\n\n"
            "Structure:\n"
            "1. Hook (1-2 sentences — buyer's desire or problem)\n"
            "2. Product intro with Ayurvedic heritage (2-3 sentences)\n"
            "3. Key benefits (3-4 benefits, naturally integrated)\n"
            "4. Quality/sourcing signal (1-2 sentences)\n"
            "5. How to use (1-2 sentences)\n"
            "6. Trust close + CTA (1-2 sentences)\n\n"
            "Include naturally: 'authentic', 'traditionally sourced'."
            f"{shipping_line}\n\n"
            "Return ONLY the description text. No headers. No markdown. Plain paragraphs only."
        )

        # Generate
        content = self._call_claude(
            system_prompt=PRODUCT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL_SONNET,
            max_tokens=1500,
            temperature=0.7,
        )

        if not content:
            return {"status": "failed", "error": "Claude API returned empty response"}

        # Score
        score_result = self._score_content_internal(
            content=content,
            content_type="product",
            target_keyword=primary_kw,
            target_market=target_market,
        )

        total_score = score_result.get("total_score", 0)

        # Rewrite if below threshold
        if total_score < SCORE_THRESHOLD:
            log.info(
                "Product description scored %d — attempting rewrite",
                total_score,
            )
            improvements = ", ".join(score_result.get("improvement_areas", ["overall quality"]))
            rewrite_prompt = (
                f"Previous attempt scored {total_score}/100. "
                f"Improve these areas: {improvements}\n\n"
                f"Rewrite this product description for {product_name}:\n"
                f"{content}\n\n"
                f"Primary keyword: {primary_kw}\n"
                f"Target market: {target_market}\n"
                f"Word count: {word_count} words\n"
                "Return ONLY the improved description text. Plain paragraphs."
            )

            content_v2 = self._call_claude(
                system_prompt=PRODUCT_SYSTEM_PROMPT,
                user_prompt=rewrite_prompt,
                model=MODEL_SONNET,
                max_tokens=1500,
                temperature=0.6,
            )

            if content_v2:
                score_result_v2 = self._score_content_internal(
                    content=content_v2,
                    content_type="product",
                    target_keyword=primary_kw,
                    target_market=target_market,
                )

                if score_result_v2.get("total_score", 0) > total_score:
                    content = content_v2
                    score_result = score_result_v2
                    total_score = score_result["total_score"]
                    log.info("Rewrite improved score to %d", total_score)

        # Build content record
        content_id = self._generate_content_id("prod", product_slug)
        needs_review = total_score < SCORE_THRESHOLD

        content_data = {
            "id": content_id,
            "type": "product_description",
            "product": product_name,
            "slug": product_slug,
            "target_market": target_market,
            "content": content,
            "word_count": self._count_words(content),
            "seo_score": score_result.get("seo_score", 0),
            "readability_score": score_result.get("readability_score", 0),
            "safety_score": score_result.get("safety_score", 0),
            "trust_signal_score": score_result.get("trust_signal_score", 0),
            "buyer_psychology_score": score_result.get("buyer_psychology_score", 0),
            "total_score": total_score,
            "keywords_used": keywords[:5],
            "improvement_areas": score_result.get("improvement_areas", []),
            "needs_human_review": needs_review,
            "status": "review" if needs_review else "queued",
            "created_at": _utcnow_iso(),
            "site": site,
        }

        # Save
        saved_path = self._save_content(content_data, "product")

        # Notify if needs review
        if needs_review and self._approval:
            try:
                self._approval.send_alert(
                    f"📝 Content needs review!\n"
                    f"Product: {product_name}\n"
                    f"Score: {total_score}/100\n"
                    f"Issues: {', '.join(score_result.get('improvement_areas', [])[:3])}\n"
                    f"File: {saved_path}"
                )
            except Exception:
                pass

        log.log_action(
            action="product_description_created",
            agent="media",
            status="success",
            details={
                "product": product_name,
                "score": total_score,
                "words": content_data["word_count"],
                "needs_review": needs_review,
            },
        )

        return content_data

    # ══════════════════════════════════════════════════════════════════
    #  2. BLOG POST
    # ══════════════════════════════════════════════════════════════════

    def write_blog_post(self, site: str, params: dict) -> dict:
        """
        Generate an E-E-A-T compliant blog post targeting international
        herbal product buyers.

        Generates a structured article with metadata, scores it, and
        queues or flags for review.

        Parameters
        ----------
        site : str
            Target site.
        params : dict
            Required: ``topic``, ``herb``.
            Optional: ``target_market``, ``target_keyword``,
            ``secondary_keywords``, ``word_count``, ``post_type``.

        Returns
        -------
        dict
            Content data with article body, metadata, scores, file path.
        """
        if not self._api_available:
            return {"status": "skipped", "reason": "Anthropic API not configured"}

        topic = params.get("topic", "Benefits of Ayurvedic Herbs")
        herb = params.get("herb", "ashwagandha")
        target_market = params.get("target_market", "GLOBAL")
        target_keyword = params.get("target_keyword", f"{herb} benefits")
        secondary_keywords = params.get("secondary_keywords", [])
        word_count = min(max(params.get("word_count", 1200), 800), 1800)
        post_type = params.get("post_type", "educational")

        log.info(
            "Writing blog post  |  topic=%s  |  herb=%s  |  market=%s  |  words=%d",
            topic[:50], herb, target_market, word_count,
        )

        # Auto-fill secondary keywords
        if not secondary_keywords:
            herb_key = herb.lower().strip()
            secondary_keywords = _DEFAULT_KEYWORDS.get(herb_key, [])[:4]

        secondary_kw_str = ", ".join(secondary_keywords) if secondary_keywords else "related herbal terms"

        user_prompt = (
            f"Write a {word_count}-word blog post:\n\n"
            f"Title: {topic}\n"
            f"Primary keyword: {target_keyword} (use in title, first 100 words, "
            "2-3 times naturally throughout, conclusion)\n"
            f"Secondary keywords: {secondary_kw_str} (use naturally 1-2 times each)\n"
            f"Target audience: Health-conscious buyers in {target_market}\n"
            f"Post type: {post_type}\n\n"
            "Structure:\n"
            f"## [SEO-optimised H1 title with '{target_keyword}']\n\n"
            "[Introduction — 100-150 words]\n"
            "Hook with relatable problem or surprising fact.\n"
            f"Introduce {herb} and Ayurvedic context.\n"
            "Promise what reader will learn.\n\n"
            f"## What is {herb.title()}? [or relevant H2]\n"
            "[150-200 words — herb background, traditional use, origin]\n\n"
            f"## Key Benefits of {herb.title()} [or relevant H2]\n"
            "[300-400 words — 3-5 benefits, each with traditional + modern context]\n\n"
            f"## How to Use {herb.title()} [or relevant H2]\n"
            "[150-200 words — dosage, forms, timing, combinations]\n\n"
            "## Why Source Matters [or relevant H2]\n"
            "[100-150 words — authenticity, Indian sourcing advantage, quality]\n"
            "[NATURAL mention of falconherbs.com product range]\n\n"
            "## Frequently Asked Questions\n"
            "[150-200 words — 3 questions buyers actually ask, answer each concisely]\n\n"
            "## Conclusion\n"
            "[100 words — summary + gentle CTA to explore products]\n\n"
            "---\n"
            "METADATA (return as JSON block after article, starting with {):\n"
            "{\n"
            '  "suggested_slug": "url-slug-here",\n'
            '  "meta_description": "155 char max",\n'
            '  "suggested_tags": ["tag1", "tag2"],\n'
            '  "internal_link_suggestions": ["product page", "related post"],\n'
            '  "featured_snippet_target": "which question could win featured snippet"\n'
            "}"
        )

        # Generate
        raw_output = self._call_claude(
            system_prompt=BLOG_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL_SONNET,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=0.7,
        )

        if not raw_output:
            return {"status": "failed", "error": "Claude API returned empty response"}

        # Parse article and metadata
        article_body, metadata = self._parse_blog_output(raw_output, herb)

        # Score
        score_result = self._score_content_internal(
            content=article_body,
            content_type="blog",
            target_keyword=target_keyword,
            target_market=target_market,
        )

        total_score = score_result.get("total_score", 0)

        # Rewrite if below threshold
        if total_score < SCORE_THRESHOLD:
            log.info("Blog post scored %d — attempting rewrite", total_score)
            improvements = ", ".join(score_result.get("improvement_areas", ["overall quality"]))

            rewrite_prompt = (
                f"Previous attempt scored {total_score}/100. "
                f"Improve: {improvements}\n\n"
                f"Rewrite and improve this blog post about {herb}:\n\n"
                f"{article_body[:3000]}\n\n"
                f"Keep the same structure but improve quality.\n"
                f"Primary keyword: {target_keyword}\n"
                f"Target market: {target_market}\n"
                f"Word count target: {word_count}\n\n"
                "Return the improved article followed by the metadata JSON block."
            )

            raw_v2 = self._call_claude(
                system_prompt=BLOG_SYSTEM_PROMPT,
                user_prompt=rewrite_prompt,
                model=MODEL_SONNET,
                max_tokens=DEFAULT_MAX_TOKENS,
                temperature=0.6,
            )

            if raw_v2:
                article_v2, metadata_v2 = self._parse_blog_output(raw_v2, herb)
                score_v2 = self._score_content_internal(
                    content=article_v2,
                    content_type="blog",
                    target_keyword=target_keyword,
                    target_market=target_market,
                )
                if score_v2.get("total_score", 0) > total_score:
                    article_body = article_v2
                    metadata = metadata_v2
                    score_result = score_v2
                    total_score = score_result["total_score"]
                    log.info("Blog rewrite improved score to %d", total_score)

        # Build content record
        slug = metadata.get("suggested_slug", f"{herb}-{post_type}")
        content_id = self._generate_content_id("blog", slug)
        needs_review = total_score < SCORE_THRESHOLD

        content_data = {
            "id": content_id,
            "type": "blog_post",
            "topic": topic,
            "herb": herb,
            "post_type": post_type,
            "slug": slug,
            "target_market": target_market,
            "content": article_body,
            "metadata": metadata,
            "word_count": self._count_words(article_body),
            "seo_score": score_result.get("seo_score", 0),
            "readability_score": score_result.get("readability_score", 0),
            "safety_score": score_result.get("safety_score", 0),
            "trust_signal_score": score_result.get("trust_signal_score", 0),
            "buyer_psychology_score": score_result.get("buyer_psychology_score", 0),
            "total_score": total_score,
            "keywords_used": [target_keyword] + secondary_keywords[:4],
            "improvement_areas": score_result.get("improvement_areas", []),
            "needs_human_review": needs_review,
            "status": "review" if needs_review else "queued",
            "created_at": _utcnow_iso(),
            "site": site,
        }

        saved_path = self._save_content(content_data, "blog")

        if needs_review and self._approval:
            try:
                self._approval.send_alert(
                    f"📝 Blog post needs review!\n"
                    f"Topic: {topic}\n"
                    f"Score: {total_score}/100\n"
                    f"Words: {content_data['word_count']}\n"
                    f"File: {saved_path}"
                )
            except Exception:
                pass

        log.log_action(
            action="blog_post_created",
            agent="media",
            status="success",
            details={"topic": topic[:60], "score": total_score, "words": content_data["word_count"]},
        )

        return content_data

    # ══════════════════════════════════════════════════════════════════
    #  3. SOCIAL POST
    # ══════════════════════════════════════════════════════════════════

    def write_social_post(self, site: str, params: dict) -> dict:
        """
        Generate social media content for Instagram and/or Facebook.

        Creates platform-specific copy with hashtags and visual suggestions.
        Saves simultaneously to social queue and HeroPost queue.

        Parameters
        ----------
        site : str
            Target site.
        params : dict
            Required: ``herb``.
            Optional: ``platform``, ``angle``, ``target_market``,
            ``linked_product_slug``.

        Returns
        -------
        dict
            Social content with per-platform text, hashtags, visual briefs.
        """
        if not self._api_available:
            return {"status": "skipped", "reason": "Anthropic API not configured"}

        platform = params.get("platform", "both")
        herb = params.get("herb", "ashwagandha")
        angle = params.get("angle", "wellness benefits")
        target_market = params.get("target_market", "GLOBAL")
        linked_slug = params.get("linked_product_slug", herb.lower())

        log.info(
            "Writing social post  |  herb=%s  |  platform=%s  |  angle=%s",
            herb, platform, angle,
        )

        # Market-specific hashtag additions
        market_tags = {
            "Australia": "#australianwellness #healthylivingaustralia #aushealth",
            "UAE": "#dubaiwellness #uaehealth #gccwellness #dubailife",
            "USA": "#uswellness #americanhealth #holisticusa",
            "UK": "#ukwellness #britishhealth #ukherbs",
            "India": "#indianwellness #ayurvedaindia #desiherbs",
        }
        extra_tags = market_tags.get(target_market, "#globalwellness")

        user_prompt = (
            f"Create social media content about {herb} with the angle: '{angle}'\n"
            f"Target market: {target_market}\n"
            f"Brand: falconherbs.com (authentic Indian herbal products)\n"
            f"Product link: https://falconherbs.com/product/{linked_slug}\n\n"
        )

        if platform in ("instagram", "both"):
            user_prompt += (
                "INSTAGRAM POST:\n"
                "- Caption: 150-300 words\n"
                "- Hook first line (visible before 'more' button)\n"
                "- Story-driven or educational angle\n"
                "- 3-5 line breaks for readability\n"
                "- Strategic emoji use (2-4 total)\n"
                "- CTA: 'Link in bio' or 'DM for more info'\n"
                f"- Generate 20-25 hashtags including {extra_tags}\n"
                "- Include mix of: #ayurveda #herbalmedicine #naturalremedies\n"
                "- Include a visual suggestion for the image/reel\n\n"
            )

        if platform in ("facebook", "both"):
            user_prompt += (
                "FACEBOOK POST:\n"
                "- Post: 200-400 words (Facebook rewards longer posts)\n"
                "- More conversational, community-feel\n"
                "- Educational hook\n"
                "- Question at end to drive comments\n"
                "- 5-8 hashtags only\n"
                "- CTA: link to product or blog\n"
                "- Visual suggestion\n\n"
            )

        user_prompt += (
            "Return ONLY valid JSON in this format:\n"
            "{\n"
            '  "instagram": {\n'
            '    "caption": "full caption text",\n'
            '    "first_comment_hashtags": "#tag1 #tag2 ...",\n'
            '    "visual_suggestion": "what the image should show"\n'
            "  },\n"
            '  "facebook": {\n'
            '    "post": "full post text",\n'
            '    "hashtags": "#tag1 #tag2 ...",\n'
            '    "visual_suggestion": "what the image should show"\n'
            "  }\n"
            "}\n"
            "If only one platform requested, include only that key."
        )

        raw = self._call_claude(
            system_prompt=SOCIAL_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL_SONNET,
            max_tokens=2000,
            temperature=0.8,
        )

        if not raw:
            return {"status": "failed", "error": "Claude API returned empty response"}

        # Quick safety check before parsing
        claims = self._detect_medical_claims(raw)
        if claims:
            log.warning("Social post medical claims detected: %s", claims)
            return {"status": "failed", "error": f"Medical claims detected in social content: {claims}"}

        # Parse JSON
        social_content = self._parse_json_from_text(raw)
        if not social_content:
            social_content = {"raw_text": raw}

        # Build content record
        content_id = self._generate_content_id("soc", f"{herb}-{angle.replace(' ', '-')[:20]}")

        content_data = {
            "id": content_id,
            "type": "social_post",
            "herb": herb,
            "angle": angle,
            "platform": platform,
            "target_market": target_market,
            "linked_product_slug": linked_slug,
            "content": social_content,
            "status": "queued",
            "created_at": _utcnow_iso(),
            "site": site,
        }

        # Save to social queue
        self._save_content(content_data, "social")

        # Also save to HeroPost queue (social content is ready to use)
        heropost_data = {
            "heropost_version": "1.0",
            "export_date": _utcnow_iso(),
            "content_id": content_id,
            "platform": platform,
            "content": social_content,
            "product_link": f"https://falconherbs.com/product/{linked_slug}",
            "falcon_source": "media_agent",
            "status": "ready_for_heropost",
        }
        heropost_filename = f"{_today_str()}_{content_id}.json"
        self._write_json(HEROPOST_DIR / heropost_filename, heropost_data)

        log.log_action(
            action="social_post_created",
            agent="media",
            status="success",
            details={"herb": herb, "platform": platform, "angle": angle},
        )

        content_data["heropost_file"] = str(HEROPOST_DIR / heropost_filename)
        return content_data

    # ══════════════════════════════════════════════════════════════════
    #  4. TRUST CONTENT
    # ══════════════════════════════════════════════════════════════════

    def write_trust_content(self, site: str, params: dict) -> dict:
        """
        Generate trust-building website pages that convert skeptical
        international buyers.

        Supports: shipping pages, about us, quality pages, FAQ pages.

        Parameters
        ----------
        site : str
            Target site.
        params : dict
            Required: ``content_type``.
            Optional: ``target_market``.

        Returns
        -------
        dict
            Content data with page text, scores, and file path.
        """
        if not self._api_available:
            return {"status": "skipped", "reason": "Anthropic API not configured"}

        content_type = params.get("content_type", "about_us")
        target_market = params.get("target_market", "GLOBAL")

        log.info(
            "Writing trust content  |  type=%s  |  market=%s",
            content_type, target_market,
        )

        if content_type == "shipping_page":
            user_prompt = (
                f"Write a shipping information page for falconherbs.com targeting "
                f"buyers in {target_market}.\n\n"
                "Include:\n"
                f"- 'We ship to {target_market} every week' (specific, confident)\n"
                "- Delivery timeframes (realistic: 7-21 business days, honest about customs)\n"
                "- Packaging quality (herbs protected, airtight, food-safe, tamper-proof)\n"
                f"- Import/customs note specific to {target_market}\n"
                "- What to do if order arrives damaged (generous return/replace policy)\n"
                "- Tracking information details\n"
                "- [Add real customer testimonial here] placeholder\n"
                "- 300-500 words\n\n"
                "Voice: warm, confident, specific — not corporate boilerplate.\n"
                "Return ONLY the page text. No markdown headers."
            )
            word_target = "300-500"

        elif content_type == "about_us":
            user_prompt = (
                "Write an About Us page for falconherbs.com — an Indian herbal "
                "products company selling authentic Ayurvedic herbs globally.\n\n"
                "Include:\n"
                "- Company origin story (authentic Indian herbal heritage, generations of knowledge)\n"
                "- Why we source directly from Indian farms and forests\n"
                "- Quality control process (selection, testing, packaging)\n"
                "- The people behind the company (humanise the brand)\n"
                "- Our commitment to authenticity vs mass-produced alternatives\n"
                "- Why international buyers choose us\n"
                "- 500-700 words\n\n"
                "Voice: warm, genuine, proud of heritage — not defensive.\n"
                "Make the reader feel they've discovered something real and special.\n"
                "Return ONLY the page text."
            )
            word_target = "500-700"

        elif content_type == "quality_page":
            user_prompt = (
                "Write a Quality & Sourcing page for falconherbs.com.\n\n"
                "Include:\n"
                "- How herbs are selected (regions, harvest timing, traditional knowledge)\n"
                "- Testing and quality control standards\n"
                "- Storage and packaging standards (freshness, potency preservation)\n"
                "- What sets authentic Indian-sourced herbs apart from Western-repackaged versions\n"
                "- Certifications and standards we follow\n"
                "- Our relationship with farming communities\n"
                "- 400-600 words\n\n"
                "Voice: knowledgeable, transparent, quality-obsessed.\n"
                "Return ONLY the page text."
            )
            word_target = "400-600"

        elif content_type == "faq_page":
            user_prompt = (
                "Write a comprehensive FAQ page for falconherbs.com — an Indian "
                "herbal products company selling to Australia, UAE, USA, UK.\n\n"
                "Include 12-15 questions covering:\n"
                "- Product quality and sourcing (3-4 questions)\n"
                "- Shipping and delivery (3-4 questions)\n"
                "- Usage and dosage (3-4 questions)\n"
                "- Returns and customer service (2-3 questions)\n\n"
                "For each question:\n"
                "- Write the question as a buyer would actually phrase it\n"
                "- Answer in 50-80 words — concise, specific, confidence-building\n"
                "- Structure answers for Google featured snippets\n\n"
                "Voice: helpful, transparent, reassuring.\n"
                "Return as Q: and A: format."
            )
            word_target = "600-900"

        else:
            return {"status": "failed", "error": f"Unknown trust content type: {content_type}"}

        # Generate
        content = self._call_claude(
            system_prompt=TRUST_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL_SONNET,
            max_tokens=2500,
            temperature=0.6,
        )

        if not content:
            return {"status": "failed", "error": "Claude API returned empty response"}

        # Score
        score_result = self._score_content_internal(
            content=content,
            content_type="trust",
            target_keyword=content_type.replace("_", " "),
            target_market=target_market,
        )

        total_score = score_result.get("total_score", 0)
        needs_review = total_score < SCORE_THRESHOLD

        content_id = self._generate_content_id("trst", f"{content_type}-{target_market.lower()}")

        content_data = {
            "id": content_id,
            "type": "trust_content",
            "content_subtype": content_type,
            "target_market": target_market,
            "content": content,
            "word_count": self._count_words(content),
            "total_score": total_score,
            "seo_score": score_result.get("seo_score", 0),
            "readability_score": score_result.get("readability_score", 0),
            "safety_score": score_result.get("safety_score", 0),
            "trust_signal_score": score_result.get("trust_signal_score", 0),
            "improvement_areas": score_result.get("improvement_areas", []),
            "needs_human_review": needs_review,
            "status": "review" if needs_review else "queued",
            "created_at": _utcnow_iso(),
            "site": site,
        }

        self._save_content(content_data, "trust")

        log.log_action(
            action="trust_content_created",
            agent="media",
            status="success",
            details={"content_type": content_type, "score": total_score, "market": target_market},
        )

        return content_data

    # ══════════════════════════════════════════════════════════════════
    #  5. CONTENT SCORING
    # ══════════════════════════════════════════════════════════════════

    def score_content(self, site: str, params: dict) -> dict:
        """
        Score content through the two-layer quality gate.

        Layer 1: Algorithmic (SEO, readability, safety) — free, instant.
        Layer 2: AI quality check (trust, buyer psychology) — Haiku, cheap.

        Parameters
        ----------
        site : str
            Target site.
        params : dict
            Required: ``content``, ``content_type``.
            Optional: ``target_keyword``, ``target_market``.

        Returns
        -------
        dict
            Complete scoring breakdown with verdict.
        """
        content = params.get("content", "")
        content_type = params.get("content_type", "product")
        target_keyword = params.get("target_keyword", "")
        target_market = params.get("target_market", "GLOBAL")

        if not content:
            return {"status": "failed", "error": "No content provided for scoring"}

        return self._score_content_internal(content, content_type, target_keyword, target_market)

    def _score_content_internal(
        self,
        content: str,
        content_type: str,
        target_keyword: str,
        target_market: str,
    ) -> dict:
        """
        Internal scoring engine — called by all generation methods.

        Layer 1: Algorithmic (0-100 normalised)
        Layer 2: AI via Haiku (trust + buyer psychology)
        Final: Weighted combination.
        """
        # ── Layer 1: Algorithmic scoring ──
        seo_score = self._score_seo(content, target_keyword, content_type)
        readability_score = self._score_readability(content)
        safety_score = self._score_safety(content)

        # Normalise to 0-100 each
        seo_normalised = round((seo_score / 40) * 100)
        readability_normalised = round((readability_score / 30) * 100)
        safety_normalised = round((safety_score / 30) * 100)

        algorithmic = (seo_normalised * 0.4) + (readability_normalised * 0.3) + (safety_normalised * 0.3)

        # ── Layer 2: AI quality check ──
        ai_trust = 70  # default if API unavailable
        ai_psychology = 70
        improvement_areas: List[str] = []
        ai_verdict = "queue"

        if self._api_available:
            ai_result = self._ai_quality_check(content, content_type, target_market)
            if ai_result:
                ai_trust = ai_result.get("trust_signal_score", 70)
                ai_psychology = ai_result.get("buyer_psychology_score", 70)
                improvement_areas = ai_result.get("improvement_areas", [])
                ai_verdict = ai_result.get("verdict", "queue")

        # ── Final score ──
        total = round(
            (algorithmic * 0.4) + (ai_trust * 0.35) + (ai_psychology * 0.25)
        )
        total = max(0, min(100, total))

        # Override verdict based on total score
        if total >= SCORE_THRESHOLD:
            verdict = "queue"
        elif total >= 50:
            verdict = "rewrite"
        else:
            verdict = "reject"

        # Safety override: if medical claims detected, always reject
        medical_claims = self._detect_medical_claims(content)
        if medical_claims:
            verdict = "reject"
            total = min(total, 30)
            improvement_areas.insert(0, f"MEDICAL CLAIMS DETECTED: {', '.join(medical_claims[:3])}")

        result = {
            "total_score": total,
            "seo_score": seo_normalised,
            "readability_score": readability_normalised,
            "safety_score": safety_normalised,
            "trust_signal_score": ai_trust,
            "buyer_psychology_score": ai_psychology,
            "algorithmic_raw": round(algorithmic),
            "verdict": verdict,
            "improvement_areas": improvement_areas,
            "passed": total >= SCORE_THRESHOLD,
            "medical_claims_found": medical_claims,
        }

        log.info(
            "Content scored  |  total=%d  |  seo=%d  |  read=%d  |  safe=%d  |  trust=%d  |  psych=%d  |  verdict=%s",
            total, seo_normalised, readability_normalised, safety_normalised,
            ai_trust, ai_psychology, verdict,
        )

        return result

    def _score_seo(self, content: str, keyword: str, content_type: str) -> int:
        """SEO scoring: 0-40 points."""
        score = 0

        if not keyword:
            return 20  # neutral score if no keyword to check

        keyword_lower = keyword.lower()
        content_lower = content.lower()

        # Keyword in first 100 characters: +10
        if keyword_lower in content_lower[:100]:
            score += 10

        # Keyword density 1-3%: +10
        density = self._calculate_keyword_density(content, keyword)
        if 0.5 <= density <= 3.0:
            score += 10
        elif density > 3.0:
            score += 3  # penalty for stuffing

        # Content length appropriate for type: +10
        word_count = self._count_words(content)
        length_targets = {
            "product": (150, 350),
            "blog": (800, 1800),
            "social": (100, 500),
            "trust": (300, 900),
        }
        min_len, max_len = length_targets.get(content_type, (100, 2000))
        if min_len <= word_count <= max_len:
            score += 10
        elif word_count >= min_len * 0.8:
            score += 5

        # No keyword stuffing (same phrase not repeated excessively): +10
        count = content_lower.count(keyword_lower)
        words = self._count_words(content)
        if words > 0 and (count / words * 100) < 4:
            score += 10

        return min(score, 40)

    def _score_readability(self, content: str) -> int:
        """Readability scoring: 0-30 points."""
        score = 0

        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if sentences:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_sentence_length < 25:
                score += 10
            elif avg_sentence_length < 30:
                score += 5

        # No paragraph > 150 words: +10
        paragraphs = content.split("\n\n")
        long_paragraphs = sum(1 for p in paragraphs if self._count_words(p) > 150)
        if long_paragraphs == 0:
            score += 10
        elif long_paragraphs <= 1:
            score += 5

        # Transition words present: +10
        content_lower = content.lower()
        transitions_found = sum(1 for tw in _TRANSITION_WORDS if tw in content_lower)
        if transitions_found >= 3:
            score += 10
        elif transitions_found >= 1:
            score += 5

        return min(score, 30)

    def _score_safety(self, content: str) -> int:
        """Safety scoring: 0-30 points."""
        score = 0
        content_lower = content.lower()

        # No medical claims: +15
        medical_claims = self._detect_medical_claims(content)
        if not medical_claims:
            score += 15
        else:
            score += 0  # hard zero for medical claims

        # No absolute claims: +10
        absolutes_found = sum(1 for ac in _ABSOLUTE_CLAIMS if ac.lower() in content_lower)
        if absolutes_found == 0:
            score += 10
        elif absolutes_found <= 1:
            score += 5

        # No spam triggers: +5
        spam_found = sum(1 for st in _SPAM_TRIGGERS if st.lower() in content_lower)
        if spam_found == 0:
            score += 5

        return min(score, 30)

    def _ai_quality_check(
        self,
        content: str,
        content_type: str,
        target_market: str,
    ) -> Optional[dict]:
        """
        Layer 2 AI quality check using Haiku (fast + cheap).

        Returns trust and buyer psychology scores with improvement areas.
        """
        truncated = content[:2000]

        user_prompt = (
            f"Score this {content_type} content on two dimensions:\n\n"
            f"Content:\n{truncated}\n\n"
            f"Target market: {target_market}\n"
            f"Company: Indian herbal products selling to international buyers\n\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "trust_signal_score": 0-100,\n'
            '  "buyer_psychology_score": 0-100,\n'
            '  "improvement_areas": ["area1", "area2"],\n'
            '  "verdict": "queue" or "rewrite" or "reject",\n'
            '  "reason": "one sentence explanation"\n'
            "}\n\n"
            "Trust signal score: Does this build credibility with skeptical international buyers?\n"
            "Buyer psychology score: Does this speak to real buyer desires/fears about buying herbs from India?"
        )

        raw = self._call_claude(
            system_prompt=SCORING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL_HAIKU,
            max_tokens=300,
            temperature=0.3,
        )

        if not raw:
            return None

        parsed = self._parse_json_from_text(raw)
        return parsed

    # ══════════════════════════════════════════════════════════════════
    #  6. HEROPOST EXPORT
    # ══════════════════════════════════════════════════════════════════

    def export_for_heropost(self, site: str, params: dict) -> dict:
        """
        Export queued content for HeroPost import.

        Loads content by ID, validates it's appropriate for export,
        formats for HeroPost, saves to the heropost queue, and
        notifies the owner via WhatsApp.

        Parameters
        ----------
        site : str
            Target site.
        params : dict
            Required: ``content_id``.
            Optional: ``scheduled_date``, ``platform``.

        Returns
        -------
        dict
            Export result with file path and notification status.
        """
        content_id = params.get("content_id", "")
        scheduled_date = params.get("scheduled_date", "")
        platform = params.get("platform", "both")

        if not content_id:
            return {"status": "failed", "error": "No content_id provided"}

        log.info("Exporting to HeroPost  |  content_id=%s", content_id)

        # Find content in index
        index = self._load_content_index()
        content_entry = None
        for entry in index:
            if entry.get("id") == content_id:
                content_entry = entry
                break

        if not content_entry:
            return {"status": "failed", "error": f"Content ID not found: {content_id}"}

        # Load full content file
        content_path = content_entry.get("file_path", "")
        if not content_path or not Path(content_path).exists():
            return {"status": "failed", "error": f"Content file not found: {content_path}"}

        try:
            full_content = json.loads(Path(content_path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return {"status": "failed", "error": f"Cannot read content file: {exc}"}

        # Validate status
        current_status = full_content.get("status", "")
        if current_status not in ("queued", "approved"):
            return {
                "status": "failed",
                "error": f"Content status is '{current_status}' — must be 'queued' or 'approved'",
            }

        # Build HeroPost export
        content_body = full_content.get("content", {})
        herb = full_content.get("herb", "herbal product")
        angle = full_content.get("angle", "wellness")
        slug = full_content.get("linked_product_slug", full_content.get("slug", herb.lower()))

        heropost_data = {
            "heropost_version": "1.0",
            "export_date": _utcnow_iso(),
            "content_id": content_id,
            "platform": platform,
            "caption": content_body.get("instagram", {}).get("caption", "") if isinstance(content_body, dict) else str(content_body)[:500],
            "hashtags": content_body.get("instagram", {}).get("first_comment_hashtags", "") if isinstance(content_body, dict) else "",
            "visual_brief": content_body.get("instagram", {}).get("visual_suggestion", "Create branded visual") if isinstance(content_body, dict) else "Create branded visual",
            "scheduled_for": scheduled_date or "",
            "falcon_score": full_content.get("total_score", 0),
            "product_link": f"https://falconherbs.com/product/{slug}",
            "status": "ready_for_heropost",
        }

        # Save to heropost queue
        filename = f"{_today_str()}_{content_id}.json"
        heropost_path = HEROPOST_DIR / filename
        self._write_json(heropost_path, heropost_data)

        # Update content status
        full_content["status"] = "exported_to_heropost"
        full_content["exported_at"] = _utcnow_iso()
        self._write_json(Path(content_path), full_content)

        # Update index
        for entry in index:
            if entry.get("id") == content_id:
                entry["status"] = "exported_to_heropost"
                entry["exported_at"] = _utcnow_iso()
                break
        self._write_json(INDEX_FILE, index)

        # Notify owner
        if self._approval:
            try:
                score = full_content.get("total_score", "?")
                self._approval.send_alert(
                    f"📝 Content ready for HeroPost!\n"
                    f"Platform: {platform.title()}\n"
                    f"Topic: {herb} — {angle}\n"
                    f"Score: {score}/100\n"
                    f"File: heropost_queue/{filename}\n"
                    "Open HeroPost to import and add visuals 🎨"
                )
            except Exception:
                pass

        log.log_action(
            action="heropost_export",
            agent="media",
            status="success",
            details={"content_id": content_id, "platform": platform, "file": filename},
        )

        return {
            "exported": True,
            "heropost_file": str(heropost_path),
            "content_id": content_id,
            "platform": platform,
            "status": "ready_for_heropost",
        }

    # ══════════════════════════════════════════════════════════════════
    #  7. CONTENT IDEAS
    # ══════════════════════════════════════════════════════════════════

    def generate_content_ideas(self, site: str, params: dict) -> dict:
        """
        Generate a content calendar of ideas using AI.

        Uses Haiku for cost efficiency. Returns specific, actionable
        ideas with keyword targeting and seasonal relevance.

        Parameters
        ----------
        site : str
            Target site.
        params : dict
            Optional: ``count``, ``content_type``, ``target_market``.

        Returns
        -------
        dict
            List of content ideas sorted by estimated opportunity.
        """
        if not self._api_available:
            return {"status": "skipped", "reason": "Anthropic API not configured"}

        count = min(params.get("count", 10), 20)
        content_type = params.get("content_type", "mixed")
        target_market = params.get("target_market", "GLOBAL")

        month_name = datetime.now(timezone.utc).strftime("%B %Y")

        log.info(
            "Generating content ideas  |  count=%d  |  type=%s  |  market=%s",
            count, content_type, target_market,
        )

        user_prompt = (
            f"Generate {count} content ideas for {target_market} market.\n"
            f"Content type: {content_type}\n"
            f"Current month: {month_name} (consider seasonal relevance)\n"
            f"Company: falconherbs.com — authentic Indian herbal products\n"
            f"Key products: Ashwagandha, Tulsi, Triphala, Brahmi, Neem, Shatavari, Moringa, Amla, Giloy, Haritaki\n\n"
            "For each idea return a JSON object with:\n"
            "{\n"
            '  "title": "specific article/post title",\n'
            '  "type": "blog" or "social" or "product",\n'
            '  "primary_keyword": "exact search phrase buyers type",\n'
            '  "search_volume": "high" or "medium" or "low",\n'
            '  "herb": "main herb featured",\n'
            '  "angle": "unique angle that differentiates from competitors",\n'
            f'  "market_relevance": "why this works for {target_market}",\n'
            '  "estimated_difficulty": "easy" or "medium" or "hard",\n'
            '  "seasonal_relevance": "why now or when to publish"\n'
            "}\n\n"
            "Return as a JSON array. Focus on search terms real buyers use."
        )

        raw = self._call_claude(
            system_prompt=IDEAS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL_HAIKU,
            max_tokens=2000,
            temperature=0.8,
        )

        if not raw:
            return {"status": "failed", "error": "Claude API returned empty response"}

        ideas = self._parse_json_from_text(raw)
        if not isinstance(ideas, list):
            ideas = [ideas] if ideas else []

        # Sort by opportunity: high volume + easy difficulty = top
        volume_rank = {"high": 3, "medium": 2, "low": 1}
        difficulty_rank = {"easy": 3, "medium": 2, "hard": 1}

        for idea in ideas:
            vol_score = volume_rank.get(idea.get("search_volume", "medium"), 2)
            diff_score = difficulty_rank.get(idea.get("estimated_difficulty", "medium"), 2)
            idea["opportunity_score"] = vol_score * 2 + diff_score

        ideas.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)

        # Save ideas
        ideas_filename = f"ideas_{_today_str()}.json"
        ideas_data = {
            "generated_at": _utcnow_iso(),
            "target_market": target_market,
            "content_type": content_type,
            "ideas": ideas,
        }
        self._write_json(QUEUE_DIR / ideas_filename, ideas_data)

        log.log_action(
            action="content_ideas_generated",
            agent="media",
            status="success",
            details={"count": len(ideas), "market": target_market},
        )

        return {
            "ideas": ideas,
            "count": len(ideas),
            "target_market": target_market,
            "saved_to": str(QUEUE_DIR / ideas_filename),
        }

    # ══════════════════════════════════════════════════════════════════
    #  8. SEASONAL CAMPAIGN
    # ══════════════════════════════════════════════════════════════════

    def create_seasonal_campaign(self, site: str, params: dict) -> dict:
        """
        Generate a complete mini content campaign.

        Creates a coherent package of blog posts, social posts, and
        product description updates with consistent messaging and
        cross-linking.

        Parameters
        ----------
        site : str
            Target site.
        params : dict
            Required: ``campaign_name``.
            Optional: ``target_market``, ``herbs``, ``duration_days``.

        Returns
        -------
        dict
            Campaign summary with all generated content and file paths.
        """
        if not self._api_available:
            return {"status": "skipped", "reason": "Anthropic API not configured"}

        campaign_name = params.get("campaign_name", "Seasonal Campaign")
        target_market = params.get("target_market", "GLOBAL")
        herbs = params.get("herbs", ["ashwagandha", "tulsi"])
        duration_days = params.get("duration_days", 14)

        log.info(
            "Creating campaign  |  name=%s  |  market=%s  |  herbs=%s",
            campaign_name, target_market, herbs,
        )

        # Create campaign directory
        campaign_slug = re.sub(r'[^a-z0-9]+', '-', campaign_name.lower()).strip('-')
        campaign_dir = QUEUE_DIR / "campaigns" / campaign_slug
        try:
            campaign_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"status": "failed", "error": f"Cannot create campaign dir: {exc}"}

        results: Dict[str, Any] = {
            "campaign_name": campaign_name,
            "target_market": target_market,
            "herbs": herbs,
            "duration_days": duration_days,
            "created_at": _utcnow_iso(),
            "content_pieces": [],
            "errors": [],
        }

        primary_herb = herbs[0] if herbs else "ashwagandha"
        secondary_herb = herbs[1] if len(herbs) > 1 else primary_herb

        # ── Blog post 1: Pillar content ──
        try:
            blog1 = self.write_blog_post(site, {
                "topic": f"Complete Guide to {primary_herb.title()} — Benefits, Uses, and Where to Buy",
                "herb": primary_herb,
                "target_market": target_market,
                "target_keyword": f"{primary_herb} benefits",
                "post_type": "educational",
                "word_count": 1500,
            })
            results["content_pieces"].append({"type": "blog_pillar", "id": blog1.get("id"), "score": blog1.get("total_score")})
        except Exception as exc:
            results["errors"].append(f"Blog pillar failed: {exc}")

        # ── Blog post 2: Supporting content ──
        try:
            blog2 = self.write_blog_post(site, {
                "topic": f"{primary_herb.title()} vs {secondary_herb.title()} — Which Is Right for You?",
                "herb": primary_herb,
                "target_market": target_market,
                "target_keyword": f"{primary_herb} vs {secondary_herb}",
                "post_type": "comparison",
                "word_count": 1000,
            })
            results["content_pieces"].append({"type": "blog_support", "id": blog2.get("id"), "score": blog2.get("total_score")})
        except Exception as exc:
            results["errors"].append(f"Blog support failed: {exc}")

        # ── Social posts (2 Instagram, 2 Facebook) ──
        social_angles = [
            ("morning routine", "instagram"),
            ("stress relief", "instagram"),
            ("immunity boost", "facebook"),
            ("authentic sourcing", "facebook"),
        ]

        for angle, platform in social_angles:
            try:
                social = self.write_social_post(site, {
                    "herb": primary_herb,
                    "angle": angle,
                    "platform": platform,
                    "target_market": target_market,
                    "linked_product_slug": primary_herb.lower(),
                })
                results["content_pieces"].append({
                    "type": f"social_{platform}",
                    "id": social.get("id"),
                    "angle": angle,
                })
            except Exception as exc:
                results["errors"].append(f"Social {platform} ({angle}) failed: {exc}")

        # ── Product descriptions (2 seasonal updates) ──
        for herb in herbs[:2]:
            try:
                prod = self.write_product_description(site, {
                    "product_name": f"{herb.title()} — {campaign_name} Special",
                    "product_slug": f"{herb.lower()}-{campaign_slug}",
                    "target_market": target_market,
                    "word_count": 250,
                })
                results["content_pieces"].append({
                    "type": "product_seasonal",
                    "id": prod.get("id"),
                    "herb": herb,
                    "score": prod.get("total_score"),
                })
            except Exception as exc:
                results["errors"].append(f"Product {herb} failed: {exc}")

        # ── Campaign brief ──
        brief = {
            "campaign": campaign_name,
            "market": target_market,
            "herbs": herbs,
            "duration": f"{duration_days} days",
            "messaging_strategy": (
                f"Position {', '.join(h.title() for h in herbs)} as premium authentic "
                f"Indian herbs for health-conscious buyers in {target_market}. "
                f"Lead with education, build trust through sourcing transparency, "
                f"close with confidence in international shipping."
            ),
            "content_pieces_planned": len(social_angles) + 4,
            "content_pieces_created": len(results["content_pieces"]),
            "errors_count": len(results["errors"]),
            "cross_linking_strategy": (
                "Blog pillar → Product pages. Social posts → Blog pillar. "
                "Blog support → Blog pillar. All → falconherbs.com."
            ),
        }
        results["brief"] = brief

        # Save campaign package
        self._write_json(campaign_dir / "campaign_summary.json", results)

        log.log_action(
            action="campaign_created",
            agent="media",
            status="success",
            details={
                "campaign": campaign_name,
                "pieces": len(results["content_pieces"]),
                "errors": len(results["errors"]),
            },
        )

        return results

    # ══════════════════════════════════════════════════════════════════
    #  9. QUEUE STATUS
    # ══════════════════════════════════════════════════════════════════

    def get_queue_status(self, site: str, params: dict) -> dict:
        """
        Get a complete picture of the content pipeline.

        Scans all queue directories and the content index to provide
        counts by type and status.

        Returns
        -------
        dict
            Pipeline status with counts, averages, and suggestions.
        """
        log.info("Getting content queue status")

        index = self._load_content_index()

        # Count by type and status
        queued: Dict[str, int] = {"products": 0, "blog": 0, "social": 0, "trust": 0, "total": 0}
        review_needed = 0
        exported = 0
        published = 0
        scores: List[int] = []

        now = datetime.now(timezone.utc)
        week_ago = (now - timedelta(days=7)).isoformat()
        week_created = 0
        week_approved = 0
        week_published = 0

        for entry in index:
            status = entry.get("status", "")
            ctype = entry.get("type", "")
            score = entry.get("total_score", 0)
            created = entry.get("created_at", "")

            if score and score > 0:
                scores.append(score)

            if status == "queued":
                if "product" in ctype:
                    queued["products"] += 1
                elif "blog" in ctype:
                    queued["blog"] += 1
                elif "social" in ctype:
                    queued["social"] += 1
                elif "trust" in ctype:
                    queued["trust"] += 1
                queued["total"] += 1
            elif status == "review":
                review_needed += 1
            elif status in ("exported_to_heropost",):
                exported += 1
            elif status == "published":
                published += 1

            # This week stats
            if created >= week_ago:
                week_created += 1
                if status in ("queued", "approved", "exported_to_heropost", "published"):
                    week_approved += 1
                if status == "published":
                    week_published += 1

        # HeroPost queue
        heropost_files: List[str] = []
        try:
            if HEROPOST_DIR.exists():
                heropost_files = [f.name for f in HEROPOST_DIR.glob("*.json")]
        except OSError:
            pass

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        # Suggest next content
        next_suggested = "product description — check profile goals"
        if queued["blog"] < 2:
            next_suggested = "blog post — Ashwagandha benefits for AU market"
        elif queued["social"] < 3:
            next_suggested = "social post — Tulsi wellness routine for Instagram"
        elif queued["products"] < 2:
            next_suggested = "product description — Triphala for UK market"

        result = {
            "queued": queued,
            "review_needed": review_needed,
            "exported_to_heropost": exported,
            "published": published,
            "total_content_pieces": len(index),
            "this_week": {
                "created": week_created,
                "approved": week_approved,
                "published": week_published,
            },
            "next_suggested": next_suggested,
            "heropost_queue": heropost_files[:20],
            "heropost_queue_count": len(heropost_files),
            "avg_score": avg_score,
            "session_api_spend": round(self._session_spend, 4),
            "session_api_calls": self._session_calls,
        }

        log.log_action(
            action="queue_status_checked",
            agent="media",
            status="success",
            details={"total": len(index), "queued": queued["total"], "review": review_needed},
        )

        return result

    # ══════════════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _call_claude(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = MODEL_SONNET,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> Optional[str]:
        """
        Call the fallback AI using the unified AI Client.

        Never raises — returns None on any failure.

        Parameters
        ----------
        system_prompt : str
            System context for the model.
        user_prompt : str
            The user message.
        model : str
            Ignored (uses standard AI_MODELS fallback).
        max_tokens : int
            Ignored (handles via standard call_ai).
        temperature : float
            Ignored (handles via standard call_ai).

        Returns
        -------
        str or None
            AI's response text, or None on failure.
        """
        from core.ai_client import call_ai
        
        log.info("Unified AI fallback call  |  media task")

        start = time.monotonic()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            raw = call_ai("fallback", messages)
            duration = time.monotonic() - start

            if raw.startswith("AI_ERROR:"):
                log.warning(
                    "AI fallback error  |  %.1fs  |  %s",
                    duration, raw,
                )
                return None

            content = raw.strip()

            self._session_calls += 1

            log.info(
                "AI fallback response  |  chars=%d  |  %.1fs",
                len(content), duration,
            )

            log.log_action(
                action="call_ai_fallback",
                agent="media",
                status="success",
                details={
                    "chars": len(content),
                    "duration_s": round(duration, 2),
                },
            )

            return content

        except Exception as exc:
            duration = time.monotonic() - start
            log.warning(
                "Fallback API error  |  %.1fs  |  %s",
                duration, exc,
            )
            return None

    def _save_content(self, content_data: dict, content_type: str) -> Optional[Path]:
        """
        Save content to the appropriate queue directory.

        Uses atomic writes (write to .tmp, rename to final) to prevent
        corruption. Updates the content index.

        Parameters
        ----------
        content_data : dict
            The content record to save.
        content_type : str
            One of: ``"product"``, ``"blog"``, ``"social"``, ``"trust"``.

        Returns
        -------
        Path or None
            The saved file path, or None on failure.
        """
        needs_review = content_data.get("needs_human_review", False)

        # Determine directory
        dir_map = {
            "product": PRODUCTS_REVIEW if needs_review else PRODUCTS_DIR,
            "blog": BLOG_REVIEW if needs_review else BLOG_DIR,
            "social": SOCIAL_DIR,
            "trust": TRUST_DIR,
        }
        target_dir = dir_map.get(content_type, QUEUE_DIR)

        # Generate filename
        slug = content_data.get("slug", content_data.get("herb", "content"))
        slug = re.sub(r'[^a-z0-9-]', '', slug.lower().replace(" ", "-"))[:30]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{content_type}_{slug}_{timestamp}.json"

        filepath = target_dir / filename

        # Validate path stays within DATA_DIR (directory traversal protection)
        try:
            resolved = filepath.resolve()
            if not str(resolved).startswith(str(DATA_DIR.resolve())):
                log.critical("DIRECTORY TRAVERSAL BLOCKED: %s", filepath)
                return None
        except Exception:
            return None

        # Atomic write
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            self._write_json(filepath, content_data)
        except Exception as exc:
            log.critical("Failed to save content: %s", exc)
            return None

        # Update content index
        index_entry = {
            "id": content_data.get("id", ""),
            "type": content_data.get("type", content_type),
            "status": content_data.get("status", "queued"),
            "total_score": content_data.get("total_score", 0),
            "file_path": str(filepath),
            "created_at": content_data.get("created_at", _utcnow_iso()),
            "site": content_data.get("site", "falconherbs.com"),
            "slug": content_data.get("slug", slug),
            "target_market": content_data.get("target_market", "GLOBAL"),
        }
        self._update_content_index(index_entry)

        log.info("Content saved  |  %s  |  score=%d  |  %s",
                 content_data.get("id", "?"),
                 content_data.get("total_score", 0),
                 filepath.name)

        return filepath

    def _load_content_index(self) -> List[dict]:
        """Load the content index from data/content_index.json."""
        try:
            if INDEX_FILE.exists():
                text = INDEX_FILE.read_text(encoding="utf-8")
                if text.strip():
                    data = json.loads(text)
                    if isinstance(data, list):
                        return data
            return []
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Content index load failed: %s", exc)
            return []

    def _update_content_index(self, content_entry: dict) -> None:
        """Append or update an entry in the content index."""
        try:
            index = self._load_content_index()

            # Check if ID already exists (update)
            content_id = content_entry.get("id", "")
            updated = False
            for i, entry in enumerate(index):
                if entry.get("id") == content_id and content_id:
                    index[i] = content_entry
                    updated = True
                    break

            if not updated:
                index.append(content_entry)

            self._write_json(INDEX_FILE, index)

        except Exception as exc:
            log.critical("Content index update failed: %s", exc)

    def _detect_medical_claims(self, text: str) -> List[str]:
        """
        Check for forbidden medical claim phrases.

        Returns list of found violations (empty = safe).
        """
        found: List[str] = []
        text_lower = text.lower()

        for claim in _FORBIDDEN_CLAIMS:
            if claim.lower() in text_lower:
                found.append(claim)

        return found

    def _calculate_keyword_density(self, text: str, keyword: str) -> float:
        """Calculate keyword density as a percentage (0.0 to 100.0)."""
        if not text or not keyword:
            return 0.0

        words = self._count_words(text)
        if words == 0:
            return 0.0

        keyword_lower = keyword.lower()
        text_lower = text.lower()

        # Count occurrences
        count = 0
        start = 0
        while True:
            idx = text_lower.find(keyword_lower, start)
            if idx == -1:
                break
            count += 1
            start = idx + 1

        keyword_words = len(keyword.split())
        return round((count * keyword_words / words) * 100, 2)

    @staticmethod
    def _count_words(text: str) -> int:
        """Accurate word count."""
        if not text:
            return 0
        return len(text.split())

    @staticmethod
    def _generate_content_id(content_type: str, slug: str) -> str:
        """Generate a unique content ID."""
        type_prefix = content_type[:4]
        slug_clean = re.sub(r'[^a-z0-9-]', '', slug.lower().replace(" ", "-"))[:20]
        return f"{type_prefix}_{slug_clean}_{_timestamp_hex()}"

    def _resolve_credential(self, value: str) -> str:
        """Resolve ``{{ENV:VAR}}`` placeholders from environment."""
        if isinstance(value, str) and value.startswith("{{ENV:"):
            var_name = value[6:-2]
            return os.environ.get(var_name, "")
        return value

    def _parse_blog_output(self, raw: str, herb: str) -> Tuple[str, dict]:
        """
        Parse Claude's blog output into article body and metadata JSON.

        The article comes first, followed by a JSON metadata block.
        """
        metadata: Dict[str, Any] = {
            "suggested_slug": f"{herb.lower()}-benefits-guide",
            "meta_description": f"Discover the benefits of {herb.title()} — traditional Ayurvedic herb for modern wellness.",
            "suggested_tags": [herb.lower(), "ayurveda", "herbal medicine"],
            "internal_link_suggestions": [f"{herb} product page"],
            "featured_snippet_target": f"What is {herb.title()}?",
        }

        # Try to find JSON block at the end
        article = raw
        json_match = re.search(r'\{[^{}]*"suggested_slug"[^{}]*\}', raw, re.DOTALL)

        if json_match:
            json_str = json_match.group()
            article = raw[:json_match.start()].strip()
            try:
                parsed_meta = json.loads(json_str)
                metadata.update(parsed_meta)
            except json.JSONDecodeError:
                pass

        # Also try after --- separator
        if "---" in raw:
            parts = raw.rsplit("---", 1)
            if len(parts) == 2:
                possible_article = parts[0].strip()
                possible_json = parts[1].strip()
                try:
                    parsed = json.loads(possible_json)
                    if isinstance(parsed, dict) and "suggested_slug" in parsed:
                        article = possible_article
                        metadata.update(parsed)
                except json.JSONDecodeError:
                    pass

        # Clean markdown artifacts from article
        article = article.rstrip("-").rstrip().rstrip("METADATA").rstrip()

        return article, metadata

    @staticmethod
    def _parse_json_from_text(text: str) -> Any:
        """Extract and parse JSON from text that may contain non-JSON content."""
        if not text:
            return None

        # Clean markdown fences
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        # Try direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try to find JSON array
        array_match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if array_match:
            try:
                return json.loads(array_match.group())
            except json.JSONDecodeError:
                pass

        # Try to find JSON object
        obj_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if obj_match:
            try:
                return json.loads(obj_match.group())
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        """Atomic JSON write: write to .tmp then rename."""
        tmp = path.with_suffix(".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps(data, indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(path)
        except OSError as exc:
            log.critical("JSON write failed  |  %s  |  %s", path, exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _route_create_content(self, site: str, params: dict) -> dict:
        """Route generic 'create_content' to the right method based on params."""
        ctype = params.get("content_type", params.get("type", ""))

        if ctype in ("product", "product_description"):
            return self.write_product_description(site, params)
        elif ctype in ("blog", "blog_post", "article"):
            return self.write_blog_post(site, params)
        elif ctype in ("social", "social_post", "instagram", "facebook"):
            return self.write_social_post(site, params)
        elif ctype in ("trust", "shipping", "about", "quality", "faq"):
            if ctype in ("shipping",):
                params["content_type"] = "shipping_page"
            elif ctype in ("about",):
                params["content_type"] = "about_us"
            elif ctype in ("quality",):
                params["content_type"] = "quality_page"
            elif ctype in ("faq",):
                params["content_type"] = "faq_page"
            return self.write_trust_content(site, params)
        else:
            return self.generate_content_ideas(site, params)

    def _handle_general_task(self, site: str, params: dict) -> dict:
        """Route general tasks by keyword matching in description."""
        desc = params.get("description", "").lower()

        if any(w in desc for w in ["product", "description"]):
            return self.write_product_description(site, params)
        elif any(w in desc for w in ["blog", "article", "post"]):
            return self.write_blog_post(site, params)
        elif any(w in desc for w in ["social", "instagram", "facebook"]):
            return self.write_social_post(site, params)
        elif any(w in desc for w in ["shipping", "about", "quality", "trust", "faq"]):
            return self.write_trust_content(site, params)
        elif any(w in desc for w in ["campaign", "seasonal"]):
            return self.create_seasonal_campaign(site, params)
        elif any(w in desc for w in ["idea", "calendar", "plan"]):
            return self.generate_content_ideas(site, params)
        else:
            return self.get_queue_status(site, params)

    @staticmethod
    def _build_result(
        task: str,
        site: str,
        status: str,
        data: dict,
        error: Optional[str] = None,
    ) -> dict:
        """Build standardised result dict for the Director."""
        return {
            "status": status,
            "task": task,
            "site": site,
            "data": data,
            "error": error,
            "timestamp": _utcnow_iso(),
            "agent": "media",
        }

    def __repr__(self) -> str:
        index = self._load_content_index()
        return (
            f"<MediaAgent  "
            f"api={'✅' if self._api_available else '❌'}  "
            f"content={len(index)}  "
            f"spend=${self._session_spend:.4f}  "
            f"calls={self._session_calls}>"
        )