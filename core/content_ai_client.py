"""
Falcon Agency — Content AI Client
Wrapper that bridges call_ai() to ContentPipeline's
expected ai_client.generate(prompt) interface.

Uses NVIDIA NIM → Qwen 3 Next 80B (Media/Content)
                → DeepSeek V3 (Director/Strategist)
                → Llama 3.3 70B (Developer)

Cost: ₹0 (free NVIDIA NIM tier)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from config.keys import NVIDIA_API_KEY, NVIDIA_BASE_URL, AI_MODELS


class ContentAIClient:
    """
    AI client specifically tuned for content generation.
    
    Interface: client.generate(prompt) → str
    This is what ContentPipeline expects.
    
    Features:
    - Higher max_tokens (4096) for long blogs
    - Lower temperature (0.65) for focused, quality content
    - Automatic fallback from Llama → Qwen
    - Error handling that never crashes
    """
    
    def __init__(self):
        self.api_key = NVIDIA_API_KEY
        self.base_url = NVIDIA_BASE_URL
        # Strip provider prefix (nv:: or or::) — this client calls NVIDIA directly
        _raw_primary = AI_MODELS.get("content", "qwen/qwen3-next-80b-a3b-instruct")
        _raw_fallback = AI_MODELS.get("content_fallback", "meta/llama-3.3-70b-instruct")
        self.primary_model = _raw_primary.split("::", 1)[-1] if "::" in _raw_primary else _raw_primary
        self.fallback_model = _raw_fallback.split("::", 1)[-1] if "::" in _raw_fallback else _raw_fallback
        self.max_tokens = 4096   # Long-form content needs space
        self.temperature = 0.65  # Focused but creative
        self.timeout = 180       # 3 min — long content takes time
        
        if not self.api_key:
            print("⚠️ NVIDIA_API_KEY not set in .env!")
    
    def generate(self, prompt, max_tokens=None, temperature=None):
        """
        Generate content from a prompt.
        
        This is THE interface ContentPipeline uses:
            response = self.ai_client.generate(prompt)
        
        Args:
            prompt: The full prompt text
            max_tokens: Override default (4096)
            temperature: Override default (0.65)
        
        Returns:
            str: Generated content, or None on failure
        """
        tokens = max_tokens or self.max_tokens
        temp = temperature or self.temperature
        
        # Try primary model first
        result = self._call_model(
            model=self.primary_model,
            prompt=prompt,
            max_tokens=tokens,
            temperature=temp
        )
        
        if result and not result.startswith("AI_ERROR"):
            return result
        
        # Fallback to Qwen
        print(f"⚠️ Primary model ({self.primary_model}) failed: {result}")
        print(f"⚠️ Trying fallback ({self.fallback_model})...")
        result = self._call_model(
            model=self.fallback_model,
            prompt=prompt,
            max_tokens=tokens,
            temperature=temp
        )
        
        if result and not result.startswith("AI_ERROR"):
            return result
        
        print(f"❌ Both models failed. Returning None.")
        return None
    
    def _call_model(self, model, prompt, max_tokens, temperature):
        """Make actual API call to NVIDIA NIM"""
        try:
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a premium content writer for "
                                "Falcon Herbs, an authentic Ayurvedic "
                                "herbal products brand. Write high-quality, "
                                "SEO-optimized, health-claims-safe content. "
                                "Never use disease cure claims. Use "
                                "structure/function claims only."
                            )
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return content
            
        except requests.exceptions.Timeout:
            return f"AI_ERROR: Timeout after {self.timeout}s"
        except requests.exceptions.HTTPError as e:
            return f"AI_ERROR: HTTP {e.response.status_code} — {e.response.text[:200]}"
        except Exception as e:
            return f"AI_ERROR: {str(e)}"
    
    def test_connection(self):
        """Quick test to verify AI is working"""
        result = self.generate(
            "Write one sentence about Ashwagandha benefits in Ayurveda.",
            max_tokens=100,
            temperature=0.5
        )
        
        if result:
            return {
                "success": True,
                "model": self.primary_model,
                "response": result[:200],
                "message": "✅ AI client connected and working!"
            }
        return {
            "success": False,
            "error": "Both models failed to respond",
            "message": "❌ Check NVIDIA_API_KEY in .env"
        }


# ==================== TEST ====================

if __name__ == "__main__":
    print("🧪 Testing Content AI Client")
    print("=" * 50)
    
    client = ContentAIClient()
    print(f"Primary model: {client.primary_model}")
    print(f"Fallback model: {client.fallback_model}")
    print(f"Max tokens: {client.max_tokens}")
    
    # Test connection
    print("\n📡 Testing connection...")
    test = client.test_connection()
    
    if test["success"]:
        print(f"✅ {test['message']}")
        print(f"📝 Response: {test['response']}")
    else:
        print(f"❌ {test['message']}")
        print(f"   Error: {test.get('error', 'Unknown')}")
    
    # If connected, test a short blog generation
    if test["success"]:
        print("\n📝 Testing short content generation...")
        result = client.generate(
            "Write a 100-word paragraph about the traditional "
            "Ayurvedic uses of Turmeric. Use health-safe language only. "
            "Do not make disease cure claims.",
            max_tokens=300
        )
        if result:
            print(f"✅ Content generated ({len(result)} chars)")
            print(f"Preview: {result[:300]}...")
        else:
            print("❌ Content generation failed")
    
    print("\n✅ Content AI Client test complete!")
