"""Conversation Memory — Remembers context across messages"""

import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional

class ConversationMemory:
    """Remembers conversation context per user"""
    
    def __init__(self, max_messages: int = 20):
        self._conversations: Dict[str, List[Dict]] = defaultdict(list)
        self._context: Dict[str, Dict] = defaultdict(dict)
        self._max_messages = max_messages
    
    def add_message(self, user_id: str, role: str, content: str) -> None:
        """Add message to conversation history"""
        self._conversations[user_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last N messages
        if len(self._conversations[user_id]) > self._max_messages:
            self._conversations[user_id] = self._conversations[user_id][-self._max_messages:]
    
    def get_history(self, user_id: str, last_n: int = 10) -> List[Dict]:
        """Get recent conversation history"""
        return self._conversations[user_id][-last_n:]
    
    def get_history_text(self, user_id: str, last_n: int = 5) -> str:
        """Get conversation history as readable text"""
        history = self.get_history(user_id, last_n)
        if not history:
            return "No previous conversation."
        
        text = ""
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            text += f"{role}: {msg['content'][:150]}...\n" if len(msg['content']) > 150 else f"{role}: {msg['content']}\n"
        return text.strip()
    
    def set_context(self, user_id: str, key: str, value: Any) -> None:
        """Store context variable (like pending product name)"""
        self._context[user_id][key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_context(self, user_id: str, key: str) -> Optional[Any]:
        """Retrieve context variable"""
        ctx = self._context[user_id].get(key)
        return ctx["value"] if ctx else None
    
    def get_all_context(self, user_id: str) -> Dict:
        """Get all context for user"""
        return {k: v["value"] for k, v in self._context[user_id].items()}
    
    def clear_context(self, user_id: str) -> None:
        """Clear user context"""
        self._context[user_id] = {}
    
    def get_conversation_summary(self, user_id: str) -> str:
        """AI-friendly summary of recent conversation"""
        history = self.get_history_text(user_id, 5)
        context = self.get_all_context(user_id)
        
        summary = f"RECENT CONVERSATION:\n{history}\n"
        
        if context:
            summary += f"\nACTIVE CONTEXT:\n{json.dumps(context, indent=2)}\n"
        
        return summary

# Global instance
memory = ConversationMemory()
