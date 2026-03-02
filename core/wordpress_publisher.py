"""
WordPress Publisher — Auto-publish blog posts via WP REST API
with WhatsApp approval gate.

Flow:
  1. AI generates blog → saved as JSON draft
  2. "publish karo" → Bot sends preview on WhatsApp
  3. User says "haan" or "approve" → publishes to WordPress
  4. Published URL sent back on WhatsApp
"""

import os
import re
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# WordPress credentials (WP admin for REST API — not cPanel)
WP_SITE_URL = os.getenv("WP_SITE_URL", "https://falconherbs.com")
WP_USER = os.getenv("FALCONHERBS_WP_USER") or os.getenv("FALCONHERBS_CPANEL_USER", "falconherbs")
WP_APP_PASSWORD = (
    os.getenv("FALCONHERBS_WP_APP_PASSWORD")
    or os.getenv("FALCONHERBS_WP_PASSWORD", "")
)

# Drafts directory
DRAFTS_DIR = Path(__file__).parent.parent / "data" / "content" / "drafts"
PUBLISHED_DIR = Path(__file__).parent.parent / "data" / "content" / "published"
APPROVED_DIR = Path(__file__).parent.parent / "data" / "content" / "approved"


class WordPressPublisher:
    """Publish content to WordPress via REST API."""
    
    def __init__(self):
        self.site_url = WP_SITE_URL.rstrip("/")
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.auth = (WP_USER, WP_APP_PASSWORD)
        PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
        APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    
    def _api_request(self, method: str, endpoint: str, 
                     data: dict = None, timeout: int = 30) -> dict:
        """Make authenticated WP REST API request."""
        url = f"{self.api_base}/{endpoint}"
        try:
            if method == "GET":
                r = requests.get(url, auth=self.auth, timeout=timeout)
            elif method == "POST":
                r = requests.post(url, auth=self.auth, json=data, timeout=timeout)
            elif method == "PUT":
                r = requests.put(url, auth=self.auth, json=data, timeout=timeout)
            else:
                return {"success": False, "error": f"Unknown method: {method}"}
            
            if r.status_code in (200, 201):
                return {"success": True, "data": r.json()}
            else:
                return {
                    "success": False, 
                    "error": f"HTTP {r.status_code}: {r.text[:200]}"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_connection(self) -> dict:
        """Test WordPress REST API connection."""
        result = self._api_request("GET", "posts?per_page=1")
        if result["success"]:
            return {
                "success": True,
                "message": f"WordPress API connected: {self.site_url}"
            }
        return result
    
    # ═══════════════════════════════════════════════
    #  DRAFT MANAGEMENT
    # ═══════════════════════════════════════════════
    
    def list_drafts(self) -> str:
        """List all pending draft blog posts."""
        drafts = []
        if not DRAFTS_DIR.exists():
            return "📂 No drafts folder found."
        
        for f in sorted(DRAFTS_DIR.glob("blog_*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                status = data.get("status", "unknown")
                topic = data.get("topic", "Untitled")
                created = data.get("created_at", "")[:10]
                word_count = len(data.get("content", "").split())
                
                icon = {"needs_review": "📝", "approved": "✅", 
                        "published": "📤", "rejected": "❌"}.get(status, "❓")
                drafts.append(f"{icon} *{topic}*\n   {status} | {word_count} words | {created}\n   📎 {f.name}")
            except (OSError, json.JSONDecodeError, ValueError, KeyError):
                continue
        
        if not drafts:
            return "📂 No blog drafts found.\n\nGenerate one with:\n\"blog likh about [topic]\""
        
        header = f"📝 *BLOG DRAFTS ({len(drafts)})*\n{'─' * 25}\n"
        return header + "\n\n".join(drafts[:10])
    
    def get_draft_preview(self, draft_name: str = None) -> dict:
        """Get WhatsApp-friendly preview of a draft."""
        draft_file = self._find_draft(draft_name)
        if not draft_file:
            return {
                "success": False,
                "error": "Draft nahi mila. 'drafts dikhao' bol ke list dekho."
            }
        
        try:
            data = json.loads(draft_file.read_text(encoding="utf-8"))
            content = data.get("content", "")
            topic = data.get("topic", "Untitled")
            keyword = data.get("target_keyword", "N/A")
            word_count = len(content.split())
            safe = data.get("safety_check", {}).get("is_safe", "unchecked")
            
            # Extract meta from HTML content
            meta_title = self._extract_tag(content, "meta_title") or topic
            meta_desc = self._extract_tag(content, "meta_description") or ""
            slug = self._extract_tag(content, "slug") or ""
            
            # Get first 200 chars of text content
            text_preview = re.sub(r'<[^>]+>', '', content)[:300].strip()
            
            preview = f"""📄 *BLOG PREVIEW*
{'─' * 25}
📌 *{meta_title}*
🔗 Slug: /{slug}
🔑 Keyword: {keyword}
📊 Words: {word_count}
🏥 Safety: {'✅ Safe' if safe else '⚠️ Needs Review'}

📖 Preview:
_{text_preview}..._

{'─' * 25}
✅ \"publish karo\" — WordPress pe publish
✏️ \"edit karo\" — Changes batao
❌ \"reject karo\" — Draft delete"""
            
            return {
                "success": True,
                "preview": preview,
                "draft_file": str(draft_file),
                "topic": topic
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _find_draft(self, name: str = None) -> Optional[Path]:
        """Find a draft file by name or return latest."""
        if not DRAFTS_DIR.exists():
            return None
        
        if name:
            # Try exact match
            exact = DRAFTS_DIR / name
            if exact.exists():
                return exact
            # Try partial match
            for f in DRAFTS_DIR.glob("blog_*.json"):
                if name.lower() in f.name.lower():
                    return f
        
        # Return latest draft
        drafts = sorted(DRAFTS_DIR.glob("blog_*.json"), 
                       key=lambda p: p.stat().st_mtime, reverse=True)
        return drafts[0] if drafts else None
    
    def _extract_tag(self, html: str, tag: str) -> str:
        """Extract content from custom tags like <meta_title>."""
        match = re.search(rf'<{tag}>(.*?)</{tag}>', html, re.DOTALL)
        return match.group(1).strip() if match else ""
    
    # ═══════════════════════════════════════════════
    #  PUBLISH TO WORDPRESS
    # ═══════════════════════════════════════════════
    
    def publish_draft(self, draft_name: str = None, 
                      as_draft: bool = False) -> dict:
        """
        Publish a blog draft to WordPress.
        
        Args:
            draft_name: Filename or partial match. None = latest.
            as_draft: If True, creates as WP draft (not published).
        """
        draft_file = self._find_draft(draft_name)
        if not draft_file:
            return {
                "success": False,
                "error": "Draft nahi mila. 'drafts dikhao' bol ke dekho."
            }
        
        try:
            data = json.loads(draft_file.read_text(encoding="utf-8"))
            content = data.get("content", "")
            
            # Extract meta from HTML
            title = self._extract_tag(content, "meta_title") or data.get("topic", "Untitled")
            meta_desc = self._extract_tag(content, "meta_description") or ""
            slug = self._extract_tag(content, "slug") or ""
            
            # Clean content — remove meta tags from body
            clean_content = content
            for tag in ["meta_title", "meta_description", "slug"]:
                clean_content = re.sub(
                    rf'<{tag}>.*?</{tag}>\s*', '', clean_content, flags=re.DOTALL
                )
            clean_content = clean_content.strip()
            
            # Replace product link placeholders
            clean_content = clean_content.replace(
                "[PRODUCT_LINK]", f"{self.site_url}/shop/"
            )
            clean_content = clean_content.replace(
                "[INTERNAL_LINK]", f"{self.site_url}/blog/"
            )
            
            # Build WP post data
            wp_data = {
                "title": title,
                "content": clean_content,
                "status": "draft" if as_draft else "publish",
                "slug": slug,
                "excerpt": meta_desc,
                "categories": [],
                "tags": [],
                "meta": {
                    "_yoast_wpseo_metadesc": meta_desc,
                    "_yoast_wpseo_focuskw": data.get("target_keyword", ""),
                }
            }
            
            # Publish via WP REST API
            result = self._api_request("POST", "posts", wp_data)
            
            if result["success"]:
                post = result["data"]
                post_url = post.get("link", f"{self.site_url}/?p={post['id']}")
                post_id = post.get("id")
                
                # Move draft to published folder
                published_file = PUBLISHED_DIR / draft_file.name
                data["status"] = "published"
                data["published_at"] = datetime.now().isoformat()
                data["wp_post_id"] = post_id
                data["wp_url"] = post_url
                published_file.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                draft_file.unlink()  # Remove from drafts
                
                status_label = "DRAFT" if as_draft else "PUBLISHED"
                return {
                    "success": True,
                    "message": f"""✅ *BLOG {status_label}!*
{'─' * 25}
📌 {title}
🔗 {post_url}
🆔 Post ID: {post_id}
📊 {len(clean_content.split())} words

{'📝 Status: WordPress Draft — review in wp-admin' if as_draft else '🌐 LIVE on website!'}""",
                    "post_url": post_url,
                    "post_id": post_id
                }
            else:
                return {
                    "success": False,
                    "error": f"WP API error: {result['error']}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def approve_draft(self, draft_name: str = None) -> dict:
        """Mark a draft as approved (ready for publishing)."""
        draft_file = self._find_draft(draft_name)
        if not draft_file:
            return {"success": False, "error": "Draft nahi mila."}
        
        try:
            data = json.loads(draft_file.read_text(encoding="utf-8"))
            data["status"] = "approved"
            data["approved_at"] = datetime.now().isoformat()
            
            # Move to approved folder
            approved_file = APPROVED_DIR / draft_file.name
            approved_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            draft_file.unlink()
            
            return {
                "success": True,
                "message": f"✅ Draft approved: *{data.get('topic')}*\n\n\"publish karo\" bol ke WordPress pe publish karo."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def reject_draft(self, draft_name: str = None) -> dict:
        """Reject and delete a draft."""
        draft_file = self._find_draft(draft_name)
        if not draft_file:
            return {"success": False, "error": "Draft nahi mila."}
        
        try:
            data = json.loads(draft_file.read_text(encoding="utf-8"))
            topic = data.get("topic", "Untitled")
            draft_file.unlink()
            return {
                "success": True,
                "message": f"❌ Draft rejected: *{topic}*\nFile deleted."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# Global instance
wp_publisher = WordPressPublisher()
