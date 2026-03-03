"""
core/ai_client.py — Multi-Provider AI Client for Falcon Agency
==============================================================

Single entry-point for all AI calls across every agent.
Routes to the correct provider based on model prefix in AI_MODELS:

    "gm::<model>"  →  Google Gemini Direct (FREE 1M TPD, 15 RPM, no 429s)
    "or::<model>"  →  OpenRouter  (100+ models, many free)
    "nv::<model>"  →  NVIDIA NIM  (fast hosted inference)
    "cl::<model>"  →  Anthropic Claude (long-context, high quality)
    "ds::<model>"  →  DeepSeek Direct (cheapest coder, $0.14/1M)
    "px::<model>"  →  Perplexity Sonar (live web search, AEO)
    "gh::<model>"  →  GitHub Models (FREE Azure-hosted, 10 RPM)
    No prefix      →  NVIDIA NIM (legacy compat)

Fallback chain (when primary fails):
    gm:: native FREE → gh:: free → or:: → nv:: reliable → ds:: cheap

Usage:
    from core.ai_client import call_ai

    reply = call_ai("commander", [{"role": "user", "content": "hello"}])
    reply = call_ai("developer", messages, system_prompt="You are...")
"""

import os
import time as _time
import requests
from config.keys import (
    NVIDIA_API_KEY,  NVIDIA_BASE_URL,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    PERPLEXITY_API_KEY, PERPLEXITY_BASE_URL,
    GEMINI_API_KEY, GEMINI_BASE_URL,
    GITHUB_BASE_URL,
    AI_MODELS,
)
from core.logger import log


# ─── Provider helpers ──────────────────────────────────────────────────────────

def _openai_compat_call(base_url: str, api_key: str, model: str,
                         messages: list, timeout: int, max_tokens: int,
                         extra_headers: dict = None) -> str:
    """Generic OpenAI-compatible POST. Used by OpenRouter, DeepSeek, GitHub, Perplexity."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    resp = requests.post(
        base_url,
        headers=headers,
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ─── Individual providers ──────────────────────────────────────────────────────

def _call_gemini(model: str, messages: list, timeout: int, max_tokens: int = 4096) -> str:
    """
    Google Gemini — DIRECT native API. FREE 1M tokens/day, 15 RPM.
    OpenAI-compatible endpoint. NO shared rate limits (unlike OpenRouter).
    Models: gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    return _openai_compat_call(
        GEMINI_BASE_URL, GEMINI_API_KEY, model, messages, timeout, max_tokens
    )


def _call_nvidia(model: str, messages: list, timeout: int, max_tokens: int = 4096) -> str:
    """NVIDIA NIM — reliable hosted inference."""
    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY not set")
    return _openai_compat_call(NVIDIA_BASE_URL, NVIDIA_API_KEY, model, messages, timeout, max_tokens)


def _call_openrouter(model: str, messages: list, timeout: int, max_tokens: int = 4096) -> str:
    """OpenRouter — 200+ models, many free tiers."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return _openai_compat_call(
        OPENROUTER_BASE_URL, OPENROUTER_API_KEY, model, messages, timeout, max_tokens,
        extra_headers={
            "HTTP-Referer": "https://falconagency.duckdns.org",
            "X-Title": "Falcon Agency AI Director",
        }
    )


def _call_anthropic(model: str, messages: list, timeout: int, max_tokens: int = 4096) -> str:
    """
    Anthropic Claude — NOT OpenAI-compatible.
    System prompt is a top-level param, response is content[0].text.
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    system_text = ""
    user_messages = []
    for m in messages:
        if m.get("role") == "system":
            system_text = m.get("content", "")
        else:
            user_messages.append({"role": m["role"], "content": m["content"]})

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": user_messages,
        "temperature": 0.7,
    }
    if system_text:
        payload["system"] = system_text

    resp = requests.post(
        ANTHROPIC_BASE_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _call_deepseek(model: str, messages: list, timeout: int, max_tokens: int = 4096) -> str:
    """
    DeepSeek Direct API — cheapest coder ($0.14/1M tokens).
    OpenAI-compatible. Best for coding tasks.
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    return _openai_compat_call(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        DEEPSEEK_API_KEY, model, messages, timeout, max_tokens
    )


def _call_perplexity(model: str, messages: list, timeout: int, max_tokens: int = 4096) -> str:
    """
    Perplexity Sonar — live web search built-in.
    OpenAI-compatible. Best for AEO brand queries + competitor research.
    """
    if not PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY not set")
    return _openai_compat_call(
        f"{PERPLEXITY_BASE_URL}/chat/completions",
        PERPLEXITY_API_KEY, model, messages, timeout, max_tokens
    )


def _call_github(model: str, messages: list, timeout: int, max_tokens: int = 4096) -> str:
    """
    GitHub Models (Azure AI) — 100% FREE, 10 RPM limit.
    Models: gpt-4o, Phi-4, DeepSeek-V3, jamba-1.5-large, Phi-4-multimodal.
    Use as first-try free fallback.
    """
    # GitHub requires separate PAT per model family
    model_lower = model.lower()
    if "gpt" in model_lower or "openai" in model_lower:
        token = os.getenv("GITHUB_PAT_GPT4O", "")
    elif "deepseek" in model_lower:
        token = os.getenv("GITHUB_PAT_DEEPSEEK", "")
    elif "phi-4-multimodal" in model_lower or "phi4mm" in model_lower:
        token = os.getenv("GITHUB_PAT_PHI4MM", "")
    elif "phi" in model_lower:
        token = os.getenv("GITHUB_PAT_PHI4", "")
    elif "jamba" in model_lower:
        token = os.getenv("GITHUB_PAT_JAMBA", "")
    else:
        # Default: GPT-4o PAT
        token = os.getenv("GITHUB_PAT_GPT4O", "")

    if not token:
        raise RuntimeError(f"No GITHUB_PAT set for model={model}")

    return _openai_compat_call(
        f"{GITHUB_BASE_URL}/chat/completions",
        token, model, messages, timeout, max_tokens
    )


# ─── Public interface ─────────────────────────────────────────────────────────

def call_ai(
    role: str,
    messages: list,
    system_prompt: str | None = None,
    timeout: int = 120,
    max_tokens: int = 4096,
) -> str:
    """
    Call the AI model assigned to a given role.

    Parameters
    ----------
    role : str
        Agent role key — maps to AI_MODELS dict.
        e.g. "commander", "director", "developer", "aeo"
    messages : list
        OpenAI-format message list.
    system_prompt : str | None
        Optional system prompt — prepended as role="system".
    timeout : int
        Request timeout in seconds. Default 120.
    max_tokens : int
        Max tokens in reply. Default 4096.

    Returns
    -------
    str
        Model reply, or "AI_ERROR: <details>" on total failure.

    Provider prefix map:
        or:: → OpenRouter   (Gemini Flash FREE, GPT-4o, etc.)
        nv:: → NVIDIA NIM   (reliable, fast)
        cl:: → Anthropic    (Claude Sonnet/Haiku)
        ds:: → DeepSeek     (cheapest coder)
        px:: → Perplexity   (live web search)
        gh:: → GitHub Models (100% FREE, 10 RPM)
    """
    model_str = AI_MODELS.get(role, AI_MODELS["fallback"])

    # ── Parse provider prefix ──────────────────────────────────────────────
    if model_str.startswith("gm::"):
        provider, model = "gemini", model_str[4:]
    elif model_str.startswith("or::"):
        provider, model = "openrouter", model_str[4:]
    elif model_str.startswith("nv::"):
        provider, model = "nvidia", model_str[4:]
    elif model_str.startswith("cl::"):
        provider, model = "anthropic", model_str[4:]
    elif model_str.startswith("ds::"):
        provider, model = "deepseek", model_str[4:]
    elif model_str.startswith("px::"):
        provider, model = "perplexity", model_str[4:]
    elif model_str.startswith("gh::"):
        provider, model = "github", model_str[4:]
    else:
        provider, model = "nvidia", model_str  # legacy: no prefix → NVIDIA

    # ── Inject system prompt ────────────────────────────────────────────────
    if system_prompt:
        filtered = [m for m in messages if m.get("role") != "system"]
        messages = [{"role": "system", "content": system_prompt}] + filtered

    # ── Dispatch map ────────────────────────────────────────────────────────
    _dispatch = {
        "gemini":     _call_gemini,
        "openrouter": _call_openrouter,
        "nvidia":     _call_nvidia,
        "anthropic":  _call_anthropic,
        "deepseek":   _call_deepseek,
        "perplexity": _call_perplexity,
        "github":     _call_github,
    }
    call_fn = _dispatch.get(provider, _call_nvidia)

    # ── Primary call with 2 retries ─────────────────────────────────────────
    last_err = None
    for attempt in range(1, 3):
        try:
            result = call_fn(model, messages, timeout, max_tokens)
            log.info(
                "AI OK | role=%s provider=%s model=%s chars=%d attempt=%d",
                role, provider, model, len(result), attempt,
            )
            return result
        except Exception as exc:
            last_err = exc
            if attempt < 2:
                log.info("AI attempt %d failed, retry 2s | role=%s err=%s",
                         attempt, role, str(exc)[:80])
                _time.sleep(2)
            else:
                log.warning("AI FAILED %d attempts | role=%s provider=%s err=%s",
                            attempt, role, provider, exc)

    # ── Smart fallback chain ────────────────────────────────────────────────
    # Strategy: free first, then cheap, then reliable
    fallback_chain = _build_fallback_chain(provider)

    for fb_provider, fb_model in fallback_chain:
        fb_fn = _dispatch.get(fb_provider)
        if not fb_fn:
            continue
        try:
            log.info("AI fallback → %s/%s | role=%s original=%s",
                     fb_provider, fb_model, role, provider)
            result = fb_fn(fb_model, messages, timeout, max_tokens)
            log.info("AI fallback OK | provider=%s chars=%d", fb_provider, len(result))
            return result
        except Exception as fb_err:
            log.warning("AI fallback %s failed: %s", fb_provider, str(fb_err)[:80])

    return f"AI_ERROR: {str(last_err)}"


def _build_fallback_chain(failed_provider: str) -> list:
    """
    Returns ordered list of (provider, model) fallbacks to try.
    Strategy: gm:: native FREE → gh:: free → or:: → nv:: → ds:: cheap
    Skip the provider that already failed.
    """
    # Preferred fallback order — optimized for VPS (GEMINI + NVIDIA always available)
    chain = [
        ("gemini",     "gemini-2.0-flash"),             # Native FREE, 1M TPD
        ("github",     "gpt-4o"),                       # FREE Azure-hosted
        ("openrouter", "google/gemini-2.0-flash-001"),  # OR free tier
        ("nvidia",     "meta/llama-3.3-70b-instruct"),  # Reliable paid
        ("deepseek",   "deepseek-chat"),                # Cheap
        ("anthropic",  "claude-3-5-haiku-20241022"),    # Premium last
    ]

    # Check which provider keys are actually available
    available = {
        "gemini":     bool(os.getenv("GEMINI_API_KEY")),
        "github":     bool(os.getenv("GITHUB_PAT_GPT4O")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        "deepseek":   bool(os.getenv("DEEPSEEK_API_KEY")),
        "nvidia":     bool(os.getenv("NVIDIA_API_KEY")),
        "anthropic":  bool(os.getenv("ANTHROPIC_API_KEY")),
        "perplexity": bool(os.getenv("PERPLEXITY_API_KEY")),
    }

    return [
        (p, m) for p, m in chain
        if p != failed_provider and available.get(p, False)
    ]
