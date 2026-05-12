"""
LLM client — Claude Sonnet 4.5 primary, Groq Llama 3.3 70B fallback.

Claude is significantly better at maintaining the Arjun's Money Diaries
voice, character dynamics, and story continuity. Groq is kept as an
automatic fallback in case of Claude API errors or rate limits.

Cost estimate at 1 episode/day cadence:
  ~15 generations/month × ~4k input tokens × ~800 output tokens
  ≈ $2-4/month on Claude Sonnet 4.5
"""

from __future__ import annotations

import os

import requests


# ---------------------------------------------------------------------
# Claude Sonnet 4.5 (primary)
# ---------------------------------------------------------------------
CLAUDE_MODEL = "claude-sonnet-4-5"
CLAUDE_URL = "https://api.anthropic.com/v1/messages"


def call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.85,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }
    r = requests.post(
        CLAUDE_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=90,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Claude HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    try:
        return data["content"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Claude malformed response: {data}") from e


# ---------------------------------------------------------------------
# Groq Llama 3.3 70B (fallback)
# ---------------------------------------------------------------------
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def call_groq(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    body = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.85,
        "top_p": 0.95,
        "max_tokens": max_tokens,
    }
    r = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=90,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Groq HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Groq malformed response: {data}") from e


# ---------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------
def generate(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1500,
) -> tuple[str, str]:
    """
    Returns (text, provider_used). provider_used is 'claude' or 'groq'.
    Tries Claude first, falls back to Groq on any error.
    """
    last_err: Exception | None = None

    # Primary: Claude
    try:
        text = call_claude(system_prompt, user_prompt, max_tokens=max_tokens)
        return text, "claude"
    except Exception as e:
        last_err = e
        print(f"[llm] Claude failed: {type(e).__name__}: {e}. Falling back to Groq.")

    # Fallback: Groq
    try:
        text = call_groq(system_prompt, user_prompt, max_tokens=max_tokens)
        return text, "groq"
    except Exception as e:
        raise RuntimeError(
            f"Both LLM providers failed. Claude: {last_err} | Groq: {e}"
        ) from e
