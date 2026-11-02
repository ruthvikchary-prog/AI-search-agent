"""Groq configuration discovery and authenticated preflight checks."""

import os
from dataclasses import dataclass
from typing import List, Optional

import requests


GROQ_BASE_URL = "https://api.groq.com/openai/v1"
PREFERRED_MODELS = (
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
)


@dataclass(frozen=True)
class GroqPreflight:
    configured_model: str
    active_model: Optional[str]
    available_models: List[str]
    real_request_ok: bool
    reason: Optional[str] = None
    recommended_env_change: Optional[str] = None


def _api_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def list_models() -> List[str]:
    """Return model IDs visible to the authenticated Groq key."""
    key = _api_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    response = requests.get(
        f"{GROQ_BASE_URL}/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=20,
    )
    response.raise_for_status()
    return sorted(
        model.get("id", "")
        for model in response.json().get("data", [])
        if model.get("id")
    )


def test_chat_model(model: str) -> bool:
    """Send a minimal authenticated request and return whether it succeeded."""
    key = _api_key()
    if not key:
        return False
    response = requests.post(
        f"{GROQ_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with OK only."}],
            "max_tokens": 8,
            "temperature": 0,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        return False
    choices = response.json().get("choices", [])
    return bool(choices and choices[0].get("message", {}).get("content"))


def preflight() -> GroqPreflight:
    """Resolve and test a working model without modifying the .env file."""
    configured = os.getenv("GROQ_MODEL", "").strip()
    if not configured:
        configured = "qwen/qwen3.8-27b"
    try:
        available = list_models()
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        return GroqPreflight(
            configured_model=configured,
            active_model=None,
            available_models=[],
            real_request_ok=False,
            reason=f"{type(exc).__name__}: {exc}",
        )

    candidates = []
    for model in [configured, *PREFERRED_MODELS]:
        if model in available and model not in candidates:
            candidates.append(model)
    for model in candidates:
        if test_chat_model(model):
            recommendation = (
                f"GROQ_MODEL={model}" if model != configured else None
            )
            return GroqPreflight(
                configured_model=configured,
                active_model=model,
                available_models=available,
                real_request_ok=True,
                recommended_env_change=recommendation,
            )

    return GroqPreflight(
        configured_model=configured,
        active_model=None,
        available_models=available,
        real_request_ok=False,
        reason="No configured or preferred model passed the authenticated chat preflight.",
    )


def get_active_model() -> str:
    """Return the preflight-selected model for CrewAI."""
    active = os.getenv("GROQ_ACTIVE_MODEL", "").strip()
    if active:
        return active
    configured = os.getenv("GROQ_MODEL", "").strip()
    return configured or "qwen/qwen3.8-27b"


def disable_unsupported_cache_breakpoints() -> None:
    """Disable CrewAI prompt markers unsupported by Groq's chat endpoint."""
    try:
        import crewai.llms.cache as cache
    except ImportError:
        return
    if getattr(cache, "_groq_cache_compatibility_patch", False):
        return
    cache.mark_cache_breakpoint = lambda message: message
    cache._groq_cache_compatibility_patch = True
