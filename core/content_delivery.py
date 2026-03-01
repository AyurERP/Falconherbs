# core/content_delivery.py
"""
Smart Content Delivery - sends content via WhatsApp in the right format based on size.

Tier 1: DIRECT (< 1500 chars)
  → Send as single WhatsApp text message

Tier 2: CHUNKED (1500 - 4000 chars)  
  → Split into chunks, send as numbered messages: "📄 Part 1/3", "📄 Part 2/3", "📄 Part 3/3"
  → Split on paragraph boundaries, not mid-sentence
  → 1 second delay between chunks

Tier 3: LINK (> 4000 chars)
  → For blog drafts: Send WordPress draft preview link
  → For product rewrites: Save to local staging file, send summary + "Bhai, full draft dekho: [link]"
  → For scan reports: Save as text file on VPS, generate temporary download link OR send as WhatsApp document
"""

import os
import time
from datetime import datetime

def _send_msg(text, metadata=None):
    from core.whatsapp import WhatsAppNotifier
    import os
    recipient = os.getenv("WHATSAPP_RECIPIENT", "919916322917")
    reply_to = metadata.get("reply_to") if metadata else None
    notifier = WhatsAppNotifier()
    return notifier.send_message(text, reply_to=reply_to)


class ContentDelivery:
    
    TIER1_LIMIT = 1500   # chars
    TIER2_LIMIT = 4000   # chars
    CHUNK_SIZE = 1400    # chars per chunk (with buffer for headers)
    STAGING_DIR = "data/staging"
    
    def __init__(self):
        os.makedirs(self.STAGING_DIR, exist_ok=True)
    
    def deliver(self, content: str, content_type: str = "general", metadata: dict = None):
        """
        Main entry point. Decides tier and delivers accordingly.
        
        content_type: "blog_draft", "product_rewrite", "scan_report", "general"
        metadata: optional dict with wp_draft_id, product_id, etc.
        """
        length = len(content)
        
        if length <= self.TIER1_LIMIT:
            return self._deliver_direct(content, metadata=metadata)
        elif length <= self.TIER2_LIMIT:
            return self._deliver_chunked(content, metadata=metadata)
        else:
            return self._deliver_link(content, content_type, metadata)
    
    def _deliver_direct(self, content: str, metadata: dict = None):
        """Tier 1: Send as single message"""
        msg_id = _send_msg(content, metadata=metadata)
        return {"method": "direct", "messages_sent": 1, "message_id": msg_id}
    
    def _deliver_chunked(self, content: str, metadata: dict = None):
        """Tier 2: Split into chunks on paragraph boundaries"""
        chunks = self._smart_split(content, self.CHUNK_SIZE)
        total = len(chunks)
        
        last_id = None
        for i, chunk in enumerate(chunks):
            header = f"📄 Part {i+1}/{total}\n\n"
            last_id = _send_msg(header + chunk, metadata=metadata)
            if i < total - 1:
                time.sleep(1)  # Rate limit buffer

        return {"method": "chunked", "messages_sent": total, "message_id": last_id}
    
    def _deliver_link(self, content: str, content_type: str, metadata: dict = None):
        """Tier 3: Send link or document based on content type"""
        metadata = metadata or {}
        
        if content_type == "blog_draft" and metadata.get("wp_draft_id"):
            # Blog already exists as WP draft — send preview link
            draft_id = metadata["wp_draft_id"]
            preview_url = f"https://www.falconherbs.com/?p={draft_id}&preview=true"
            summary = self._generate_summary(content, max_chars=500)
            msg = f"📝 Blog Draft Ready\n\n{summary}\n\n🔗 Full draft: {preview_url}\n\nBhai, review karke bolo — publish karun?"
            _send_msg(msg, metadata=metadata)
            return {"method": "link", "type": "wp_preview", "draft_id": draft_id}
        
        elif content_type == "product_rewrite":
            # Save to staging, send summary
            product_id = metadata.get("product_id", "unknown")
            filename = f"product_{product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.STAGING_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            summary = self._generate_summary(content, max_chars=500)
            msg = f"✏️ Product Rewrite Ready (ID: {product_id})\n\n{summary}\n\n📁 Full draft saved: {filename}\n\nBhai, approve karo toh apply kar deta hun."
            _send_msg(msg, metadata=metadata)
            return {"method": "link", "type": "staging_file", "filepath": filepath}
        
        else:
            # General large content — save as file AND send as document
            from core.whatsapp import WhatsAppNotifier
            filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.STAGING_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            summary = self._generate_summary(content, max_chars=800)
            _send_msg(f"📊 Report ready. File bhej raha hoon...", metadata=metadata)
            
            wa = WhatsAppNotifier()
            reply_to = metadata.get("reply_to") if metadata else None
            wa.send_document(filepath, caption=summary[:200], filename=filename, reply_to=reply_to)
            
            return {"method": "document", "type": "file", "filepath": filepath}
    
    def _smart_split(self, text: str, max_size: int) -> list:
        """Split text on paragraph boundaries, not mid-sentence"""
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_size:
                current_chunk += ("\n\n" + para if current_chunk else para)
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # If single paragraph > max_size, split on sentences
                if len(para) > max_size:
                    sentences = para.replace('. ', '.\n').split('\n')
                    sub_chunk = ""
                    for sent in sentences:
                        if len(sub_chunk) + len(sent) + 1 <= max_size:
                            sub_chunk += (" " + sent if sub_chunk else sent)
                        else:
                            if sub_chunk:
                                chunks.append(sub_chunk.strip())
                            sub_chunk = sent
                    if sub_chunk:
                        current_chunk = sub_chunk
                    else:
                        current_chunk = ""
                else:
                    current_chunk = para
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]
    
    def _generate_summary(self, content: str, max_chars: int = 500) -> str:
        """Extract first N chars as summary, ending at sentence boundary"""
        if len(content) <= max_chars:
            return content
        
        truncated = content[:max_chars]
        # Find last sentence boundary
        for sep in ['. ', '.\n', '!\n', '?\n']:
            last_sep = truncated.rfind(sep)
            if last_sep > max_chars * 0.5:  # At least half the max
                return truncated[:last_sep + 1] + "\n\n..."
        
        return truncated.strip() + "..."

# Singleton instance
content_delivery = ContentDelivery()
