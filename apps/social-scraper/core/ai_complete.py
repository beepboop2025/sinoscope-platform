"""Unified AI completion with a free → local → paid cascade.

One call, three tiers tried in order (configurable via the AI_CASCADE env):

  1. router  — free_llm_router (free-tier LLM failover, $0)
  2. ollama  — local model via OLLAMA_URL (no API cost, private)
  3. claude  — Anthropic Claude (paid fallback, reliable)

This is the "free now, paid if needed" policy expressed once, so every
processor / your own AI agent can call `ai_complete(...)` instead of
re-implementing the cascade (as processors/conditions_report.py did inline).

Usage:
    from core.ai_complete import ai_complete
    text = ai_complete("Summarize today's China censorship signal:\\n" + context,
                       task_type="briefing", max_tokens=1024)

Env:
    AI_CASCADE        comma list / order, default "router,ollama,claude"
    OLLAMA_URL        e.g. http://localhost:11434  (enables the ollama tier)
    OLLAMA_MODEL      default "llama3"
    ANTHROPIC_API_KEY enables the claude tier
    AI_CLAUDE_MODEL   default "claude-haiku-4-5-20251001" (cheap; bump for depth)
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class AllAITiersFailed(RuntimeError):
    """Raised when every configured AI tier failed (or none were available)."""


def _try_router(prompt: str, task_type: str, temperature: float, max_tokens: int) -> str | None:
    from free_llm_router import FreeLLMRouter

    router = FreeLLMRouter()
    result = asyncio.run(
        router.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    )
    return (result.get("text") or "").strip() or None


def _try_ollama(prompt: str, temperature: float, max_tokens: int) -> str | None:
    url = os.getenv("OLLAMA_URL")
    if not url:
        return None
    import httpx

    model = os.getenv("OLLAMA_MODEL", "llama3")
    resp = httpx.post(
        f"{url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return (resp.json().get("message", {}).get("content") or "").strip() or None


def _try_claude(prompt: str, temperature: float, max_tokens: int) -> str | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    model = os.getenv("AI_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return (message.content[0].text or "").strip() or None


def ai_complete(
    prompt: str,
    *,
    task_type: str = "general",
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """Run the prompt through the free → local → paid cascade; return the first
    non-empty completion. Raises AllAITiersFailed if every tier fails."""
    order = [t.strip() for t in os.getenv("AI_CASCADE", "router,ollama,claude").split(",") if t.strip()]
    tiers = {
        "router": lambda: _try_router(prompt, task_type, temperature, max_tokens),
        "ollama": lambda: _try_ollama(prompt, temperature, max_tokens),
        "claude": lambda: _try_claude(prompt, temperature, max_tokens),
    }

    errors = []
    for name in order:
        fn = tiers.get(name)
        if fn is None:
            continue
        try:
            text = fn()
            if text:
                logger.info("[ai_complete] tier '%s' succeeded", name)
                return text
            logger.debug("[ai_complete] tier '%s' returned empty / unavailable", name)
        except Exception as e:  # noqa: BLE001 — best-effort cascade
            logger.warning("[ai_complete] tier '%s' failed: %s", name, e)
            errors.append(f"{name}: {e}")

    raise AllAITiersFailed("; ".join(errors) or f"no usable AI tiers in AI_CASCADE={order}")
