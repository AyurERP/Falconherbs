import requests
from config.keys import NVIDIA_API_KEY, NVIDIA_BASE_URL, AI_MODELS

def call_ai(role: str, messages: list, timeout: int = 120) -> str:
    """
    role: 'commander' | 'director' | 'developer' | 'fallback'
    messages: [{"role": "user", "content": "..."}]
    """
    model = AI_MODELS.get(role, AI_MODELS["fallback"])
    
    try:
        response = requests.post(
            NVIDIA_BASE_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096
            },
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI_ERROR: {str(e)}"
