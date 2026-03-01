# core/rewrite_staging.py
"""
Product Rewrite Staging System

Flow:
1. Health scanner finds violations in a product
2. Health rewriter generates new description
3. Save rewrite to staging (NOT directly to WooCommerce)
4. Send preview to owner via WhatsApp (using content_delivery)
5. Owner reviews: "approve product 1234" or "reject product 1234"
6. If approved → push to WooCommerce via integration_bridge
7. If rejected → discard or re-generate

Staging storage: data/staging/rewrites/
Format: JSON file per product
"""

import os
import json
from datetime import datetime

class RewriteStaging:
    
    STAGING_DIR = "data/staging/rewrites"
    INDEX_FILE = "data/staging/rewrites/index.json"
    
    def __init__(self):
        os.makedirs(self.STAGING_DIR, exist_ok=True)
        self.index = self._load_index()
    
    def _load_index(self) -> dict:
        if os.path.exists(self.INDEX_FILE):
            try:
                with open(self.INDEX_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"pending": [], "approved": [], "rejected": []}
    
    def _save_index(self):
        with open(self.INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2)
    
    def stage_rewrite(self, product_id: int, product_name: str, 
                      old_description: str, new_description: str,
                      violations_found: list) -> dict:
        """Save a rewrite to staging for approval"""
        
        entry = {
            "product_id": product_id,
            "product_name": product_name,
            "old_description": old_description,
            "new_description": new_description,
            "violations_found": violations_found,
            "staged_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        # Save individual file
        filename = f"rewrite_{product_id}.json"
        filepath = os.path.join(self.STAGING_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entry, f, indent=2)
        
        # Update index
        if product_id not in self.index.get("pending", []):
            if "pending" not in self.index:
                self.index["pending"] = []
            self.index["pending"].append(product_id)
        self._save_index()
        
        return entry
    
    def get_pending(self) -> list:
        """Get all pending rewrites"""
        return self.index.get("pending", [])
    
    def get_rewrite(self, product_id: int) -> dict:
        """Get a specific rewrite"""
        filepath = os.path.join(self.STAGING_DIR, f"rewrite_{product_id}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def approve(self, product_id: int) -> bool:
        """Mark rewrite as approved"""
        entry = self.get_rewrite(product_id)
        if not entry:
            return False
        
        entry["status"] = "approved"
        entry["approved_at"] = datetime.now().isoformat()
        
        filepath = os.path.join(self.STAGING_DIR, f"rewrite_{product_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entry, f, indent=2)
        
        if product_id in self.index.get("pending", []):
            self.index["pending"].remove(product_id)
        if product_id not in self.index.get("approved", []):
            if "approved" not in self.index:
                self.index["approved"] = []
            self.index["approved"].append(product_id)
        self._save_index()
        
        return True
    
    def reject(self, product_id: int) -> bool:
        """Mark rewrite as rejected"""
        entry = self.get_rewrite(product_id)
        if not entry:
            return False
        
        entry["status"] = "rejected"
        entry["rejected_at"] = datetime.now().isoformat()
        
        filepath = os.path.join(self.STAGING_DIR, f"rewrite_{product_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entry, f, indent=2)
        
        if product_id in self.index.get("pending", []):
            self.index["pending"].remove(product_id)
        if product_id not in self.index.get("rejected", []):
            if "rejected" not in self.index:
                self.index["rejected"] = []
            self.index["rejected"].append(product_id)
        self._save_index()
        
        return True
    
    def get_summary(self) -> str:
        """Quick status for WhatsApp"""
        p = len(self.index.get("pending", []))
        a = len(self.index.get("approved", []))
        r = len(self.index.get("rejected", []))
        return f"📋 Rewrites: {p} pending | {a} approved | {r} rejected"

# Singleton
rewrite_staging = RewriteStaging()
