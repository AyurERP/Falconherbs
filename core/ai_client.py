"""
core/ai_client.py — Multi-Provider AI Client for Falcon Agency
==============================================================

Single entry-point for all AI calls across every agent.
Routes to the correct provider based on model prefix in AI_MODELS:

    "or::<model>"  →  OpenRouter  (100+ models, many free)
    "nv::<model>"  →  NVIDIA NIM  (fast hosted inference)
    No prefix      →  NVIDIA NIM  (legacy compat)

Usage:
    from core.ai_client import call_ai

    # Simple call
    reply = call_ai("commander", [{"role": "user", "content": "hello"}])

    # With system prompt override (director brain uses this)
    reply = call_ai("director", messages, system_prompt="You are...")
"""

import os
import requests
import json
from pathlib import Path
from config.keys import (
    NVIDIA_API_KEY,  NVIDIA_BASE_URL,
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL,
    AI_MODELS,
)
from core.logger import log

# ── SPEND TRACKING ──────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPEND_FILE = DATA_DIR / "spend.json"

def is_budget_safe() -> bool:
    """Check if we are within the monthly limit set in spend.json"""
    if not SPEND_FILE.exists():
        return True
    try:
        with open(SPEND_FILE, "r") as f:
            data = json.load(f)
            # Default limit $50 if not set, for safety
            limit = data.get("monthly_limit", 50.0)
            total = data.get("monthly_total", 0.0)
            if total >= limit:
                return False
            return True
    except Exception:
        return True # Fallback to allowed if file corrupted


# ─── Provider dispatch ────────────────────────────────────────────────────────

def _call_nvidia(model: str, messages: list, timeout: int,
                  max_tokens: int = 4096) -> str:
    """Call NVIDIA NIM inference endpoint."""
    resp = requests.post(
        NVIDIA_BASE_URL,
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
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


def _call_openrouter(model: str, messages: list, timeout: int,
                      max_tokens: int = 4096) -> str:
    """Call OpenRouter (OpenAI-compatible API, 100+ models)."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set in .env")

    resp = requests.post(
        OPENROUTER_BASE_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://falconagency.duckdns.org",
            "X-Title": "Falcon Agency AI Director",
        },
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


def _call_anthropic(model: str, messages: list, timeout: int,
                    max_tokens: int = 4096) -> str:
    """
    Call Anthropic Claude API.

    ⚠️  Anthropic API is NOT OpenAI-compatible:
    - System prompt is a top-level param, not a message role
    - Requires 'anthropic-version' header
    - Response format: content[0].text (not choices[0].message.content)
    - max_tokens is REQUIRED (no default)
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")

    # Extract system message if present (Anthropic needs it separately)
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
        e.g. "commander", "director", "media", "fallback"
    messages : list
        OpenAI-format message list.
        e.g. [{"role": "user", "content": "hello"}]
        If you also pass system_prompt, it is prepended automatically.
    system_prompt : str | None
        Optional system prompt. If provided, it is inserted as the first
        message (role="system") before any existing messages.
    timeout : int
        Request timeout in seconds. Default 120.
    max_tokens : int
        Maximum tokens in reply. Default 4096.

    Returns
    -------
    str
        The model's reply text, or "AI_ERROR: <details>" on failure.
    """
    if not is_budget_safe():
        msg = "❌ AI_ERROR: Monthly budget limit hit! Check data/spend.json"
        log.error(msg)
        return msg

    model_str = AI_MODELS.get(role, AI_MODELS["fallback"])

    # ── Parse provider prefix ──────────────────────────────────────────────
    if model_str.startswith("or::"):
        provider = "openrouter"
        model = model_str[4:]
    elif model_str.startswith("nv::"):
        provider = "nvidia"
        model = model_str[4:]
    elif model_str.startswith("cl::"):
        provider = "anthropic"
        model = model_str[4:]
    else:
        # Legacy: no prefix → NVIDIA
        provider = "nvidia"
        model = model_str

    # ── Inject system prompt ──────────────────────────────────────────
    if system_prompt:
        # Prepend system message; remove any existing system messages to
        # avoid prompt confusion.
        filtered = [m for m in messages if m.get("role") != "system"]
        messages = [{"role": "system", "content": system_prompt}] + filtered

    # ── Dispatch with retry ──────────────────────────────────────────
    import time as _time

    last_err = None
    for attempt in range(1, 3):  # 2 attempts on same provider
        try:
            if provider == "openrouter":
                result = _call_openrouter(model, messages, timeout, max_tokens)
            elif provider == "anthropic":
                result = _call_anthropic(model, messages, timeout, max_tokens)
            else:
                result = _call_nvidia(model, messages, timeout, max_tokens)

            log.info(
                "AI call OK  |  role=%s  provider=%s  model=%s  chars=%d  attempt=%d",
                role, provider, model, len(result), attempt,
            )
            return result

        except Exception as exc:
            last_err = exc
            if attempt < 2:
                log.info(
                    "AI call attempt %d failed, retrying in 2s  |  role=%s  err=%s",
                    attempt, role, str(exc)[:80],
                )
                _time.sleep(2)
            else:
                log.warning(
                    "AI call FAILED after %d attempts  |  role=%s  provider=%s  model=%s  err=%s",
                    attempt, role, provider, model, exc,
                )

    # ── Cross-provider fallback ────────────────────────────────────────────
    # Claude down → fallback to NVIDIA
    if provider == "anthropic" and NVIDIA_API_KEY:
        try:
            nvidia_fallback = "meta/llama-3.3-70b-instruct"
            log.info("Claude failed, falling back to NVIDIA model=%s", nvidia_fallback)
            result = _call_nvidia(nvidia_fallback, messages, timeout, max_tokens)
            log.info("NVIDIA fallback OK after Claude failure  |  chars=%d", len(result))
            return result
        except Exception as exc2:
            log.warning("NVIDIA fallback also failed: %s", exc2)

    # NVIDIA down → fallback to Claude Haiku (if key available)
    elif provider == "nvidia" and ANTHROPIC_API_KEY:
        try:
            claude_fallback = "claude-3-5-haiku-20241022"
            log.info("NVIDIA failed, falling back to Claude model=%s", claude_fallback)
            result = _call_anthropic(claude_fallback, messages, timeout, max_tokens)
            log.info("Claude fallback OK after NVIDIA failure  |  chars=%d", len(result))
            return result
        except Exception as exc2:
            log.warning("Claude fallback also failed: %s", exc2)

    # OpenRouter → NVIDIA fallback
    elif provider == "openrouter" and NVIDIA_API_KEY:
        try:
            nvidia_fallback = "meta/llama-3.3-70b-instruct"
            log.info("Cross-provider retry on NVIDIA NIM with model=%s", nvidia_fallback)
            result = _call_nvidia(nvidia_fallback, messages, timeout, max_tokens)
            log.info("NVIDIA cross-provider fallback OK  |  chars=%d", len(result))
            return result
        except Exception as exc2:
            log.warning("NVIDIA cross-provider fallback also failed: %s", exc2)

    return f"AI_ERROR: {str(last_err)}"
