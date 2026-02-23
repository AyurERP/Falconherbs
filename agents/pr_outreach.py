import logging
import yaml
import re
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.logger import log

logger = logging.getLogger("PROutreach")

class PROutreach:
    """
    Agent for finding YouTube influencers and generating personalized pitches.
    """

    def __init__(self, llm_caller=None, config_path="config/clients/falconherbs.yaml"):
        """
        Args:
            llm_caller: Function that takes (prompt, model) and returns string.
            config_path: Path to the client YAML config.
        """
        self.llm_caller = llm_caller
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        outreach_cfg = self.config.get("outreach", {})
        self.api_key = outreach_cfg.get("youtube_api_key", "")
        self.min_subs = outreach_cfg.get("min_subscribers", 5000)
        self.max_results = outreach_cfg.get("max_results", 8)
        
        self.youtube = None
        if self.api_key and self.api_key != "YOUR_KEY_HERE":
            try:
                self.youtube = build("youtube", "v3", developerKey=self.api_key)
            except Exception as e:
                log.error(f"Failed to initialize YouTube API: {e}")

    def _load_config(self):
        """Load configuration from YAML"""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            return {}
        except Exception as e:
            log.error(f"Error loading PROutreach config: {e}")
            return {}

    def find_influencers(self, topic: str, max_results: int = 8) -> list:
        """
        Search YouTube for relevant influencers.
        """
        if not self.youtube:
            if self.api_key == "YOUR_KEY_HERE" or not self.api_key:
                return {"error": "YouTube API key not configured. Please add it to falconherbs.yaml", "type": "config_missing"}
            return {"error": "YouTube API client not initialized.", "type": "init_failed"}

        try:
            # 1. Search for channels
            search_query = f"ayurvedic {topic}"
            search_response = self.youtube.search().list(
                q=search_query,
                type="channel",
                part="id,snippet",
                maxResults=max_results * 2 # Get more to allow for filtering
            ).execute()

            channel_ids = [item["id"]["channelId"] for item in search_response.get("items", [])]
            if not channel_ids:
                return []

            # 2. Get channel statistics and branding settings
            channels_response = self.youtube.channels().list(
                id=",".join(channel_ids),
                part="snippet,statistics,brandingSettings"
            ).execute()

            influencers = []
            for item in channels_response.get("items", []):
                snippet = item.get("snippet", {})
                name = snippet.get("title", "")
                stats = item.get("statistics", {})
                branding = item.get("brandingSettings", {})
                
                subs = int(stats.get("subscriberCount", 0))
                
                # Filter by subscriber count
                if subs < self.min_subs:
                    continue
                
                # Brand filter — pass full channel_data dict
                channel_data = {
                    "title": name,
                    "description": snippet.get("description", ""),
                    "subscriberCount": subs
                }
                if self._is_likely_brand(channel_data):
                    continue

                # 3. Get recent videos for relevance and personalization
                videos_response = self.youtube.search().list(
                    channelId=item["id"],
                    part="snippet",
                    order="date",
                    type="video",
                    maxResults=3
                ).execute()
                
                recent_videos = [v["snippet"]["title"] for v in videos_response.get("items", [])]
                
                # Check for email in description (API doesn't give email)
                desc = snippet.get("description", "")
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', desc)
                email = email_match.group(0) if email_match else None

                # Calculate relevance score (1-10)
                # Matches topic in title or description or video titles
                score = 5
                if topic.lower() in name.lower(): score += 2
                if topic.lower() in desc.lower(): score += 2
                if any(topic.lower() in v.lower() for v in recent_videos): score += 1
                score = min(score, 10)

                influencers.append({
                    "name": name,
                    "subscribers": self._format_subs(subs),
                    "sub_count": subs, # For internal sorting
                    "recent_videos": recent_videos,
                    "channel_url": f"https://www.youtube.com/channel/{item['id']}",
                    "email": email,
                    "relevance_score": score
                })

            # Sort by relevance_score DESC, then sub_count DESC
            influencers.sort(key=lambda x: (x["relevance_score"], x["sub_count"]), reverse=True)
            
            return influencers[:max_results]

        except HttpError as e:
            if e.resp.status == 403:
                return {"error": "YouTube API quota exceeded. Please try again tomorrow.", "type": "quota_exceeded"}
            return {"error": f"YouTube API Error: {e}", "type": "api_error"}
        except Exception as e:
            return {"error": f"Search failed: {e}", "type": "unknown"}

    def _format_subs(self, count: int) -> str:
        """Format subscriber count like '125K'"""
        if count >= 1000000:
            return f"{count / 1000000:.1f}M"
        if count >= 1000:
            return f"{count / 1000:.1f}K"
        return str(count)

    def generate_pitch(self, influencer: dict, product: dict = None) -> str:
        """
        Generate a personalized pitch email via LLM.
        """
        if not self.llm_caller:
            return "No LLM caller provided. Cannot generate pitch."

        product_info = product or {
            "name": "Falcon Herbs Premium range",
            "focus": self.config.get("outreach", {}).get("product_focus", "Ayurvedic wellness")
        }
        
        recent_vids = ", ".join([f'"{v}"' for v in influencer.get("recent_videos", [])])
        one_vid = influencer.get("recent_videos", ["one of your latest uploads"])[0]

        prompt = f"""You are a founder of an Ayurvedic brand. 
Write a personalized pitch email to a YouTube creator.

Creator Name: {influencer['name']}
Recent Videos: {recent_vids}
Specific Video to reference: "{one_vid}"

Our Product: {product_info['name']} ({product_info['focus']})

Guidelines:
1. Tone: founder-to-creator, human, genuine, and brief.
2. Position as product gifting/collaboration, NOT a paid promotion.
3. Reference the specific video "{one_vid}" naturally.
4. Maximum 150 words.
5. Format: Include a Subject line and the Email Body.
6. Do NOT use placeholders like [Your Name], just write the text.
7. Focus on a shared passion for Ayurvedic wellness.

Output only the Subject and Body."""

        return self.llm_caller(prompt, "qwen")

    def format_whatsapp_result(self, influencers: list) -> str:
        """
        Format the search results for WhatsApp.
        """
        if not influencers:
            return "∅ No influencers found for this topic. Try a broader term."
            
        if isinstance(influencers, dict) and "error" in influencers:
            if influencers["type"] == "quota_exceeded":
                return f"⚠️ *YouTube Quota Exceeded*\n\n{influencers['error']}"
            return f"❌ *Error searching influencers*\n\n{influencers['error']}"

        lines = ["🎥 *TOP YOUTUBE CREATORS*", "─────────────"]
        
        for i, inf in enumerate(influencers[:5], 1):
            email_status = f"📧 {inf['email']}" if inf['email'] else "📩 DM on YouTube"
            lines.append(f"{i}. *{inf['name']}* ({inf['subscribers']} subs)")
            lines.append(f"   ⭐ Relevance: {inf['relevance_score']}/10")
            lines.append(f"   {email_status}")
            lines.append(f"   🎬 _Recent:_ {inf['recent_videos'][0] if inf['recent_videos'] else 'No videos'}")
            lines.append("")

        lines.append("─────────────")
        lines.append("Reply with a number (1-5) to generate a personalized pitch for that creator.")
        
        return "\n".join(lines)

    def _is_likely_brand(self, channel_data: dict) -> bool:
        """
        Detect corporate/brand channels. Returns True = filter out.
        Keeps individual creators, removes corporate accounts.
        """
        name = channel_data.get("title", "").lower()
        description = channel_data.get("description", "").lower()
        subscriber_count = int(channel_data.get("subscriberCount", 0))

        # Signal 1: Hard corporate keywords in name
        corporate_keywords = [
            "pvt ltd", "pvt. ltd", "private limited",
            "inc.", " inc ", "corporation", "corp.",
            "enterprise", "enterprises", "official channel",
            "official page", " company", " co."
        ]
        if any(kw in name for kw in corporate_keywords):
            return True

        # Signal 2: Known large Ayurvedic brands
        known_brands = [
            "patanjali", "himalaya", "dabur", "baidyanath",
            "zandu", "hamdard", "charak", "kerala ayurveda",
            "kama ayurveda", "forest essentials", "biotique"
        ]
        if any(brand in name for brand in known_brands):
            return True

        # Signal 3: Business signals in description
        business_signals = [
            "our company", "our brand", "we manufacture",
            "buy now", "shop now",
            "established in 19", "established in 20",
            "gst no", "cin no", "iso certified"
        ]
        if any(signal in description for signal in business_signals):
            return True

        # Signal 4: Large following + impersonal description
        personal_pronouns = [
            "i am", "i'm", "my journey", "my story",
            "main hoon", "mera naam", "myself"
        ]
        if subscriber_count > 500000:
            if not any(p in description for p in personal_pronouns):
                return True

        return False
