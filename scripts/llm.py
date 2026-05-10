"""
LLM client with multi-provider fallback and a prompt-hash cache.

Order of attempts:
  1. Gemini 2.5 Flash (free tier — generous TPM, ~250-1500 RPD)
  2. Groq llama-3.3-70b-versatile (free tier — 1000 RPD, 30 RPM)
  3. Raise; caller decides what to do (Telegram alert + queue back).

Cache:
  We hash (system + user) prompt and store outputs in
  backups/llm_cache/<sha256>.json. Useful if a regenerate request
  comes in for an unchanged input (rare but possible) and as forensic
  evidence when an episode looks weird.

Why no OpenRouter / HuggingFace / Together: their free tiers shift
constantly. Groq + Gemini come from different vendors with strong
free-tier track records. If one breaks, the other carries.

Outputs are returned as plain strings; the caller does QC.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

import requests


# ---------------------------------------------------------------------
# Cache (optional, opportunistic)
# ---------------------------------------------------------------------
CACHE_DIR = Path(__file__).resolve().parent.parent / "backups" / "llm_cache"


def _cache_key(system: str, user: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(b"\x00")
    h.update(system.encode())
    h.update(b"\x00")
    h.update(user.encode())
    return h.hexdigest()


def _cache_get(key: str) -> Optional[str]:
    p = CACHE_DIR / f"{key}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())["text"]
    except Exception:
        return None


def _cache_put(key: str, text: str, meta: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"text": text, "meta": meta, "ts": time.time()}
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------
# Gemini 2.5 Flash
# ---------------------------------------------------------------------
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


def call_gemini(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.85,
            "topP": 0.95,
            "maxOutputTokens": max_tokens,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    r = requests.post(
        f"{GEMINI_URL}?key={api_key}",
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=90,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini malformed response: {data}") from e


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
# Public entry points
# ---------------------------------------------------------------------
def generate(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1500,
    use_cache: bool = False,
) -> tuple[str, str]:
    """
    Returns (text, provider_used). provider_used is "gemini" or "groq".
    """
    # Cache lookup is keyed on the model AND prompts so a Groq retry
    # doesn't return a Gemini answer.
    if use_cache:
        for model in (GEMINI_MODEL, GROQ_MODEL):
            cached = _cache_get(_cache_key(system_prompt, user_prompt, model))
            if cached:
                return cached, model.split("-")[0]

    last_err: Exception | None = None
    try:
        text = call_gemini(system_prompt, user_prompt, max_tokens=max_tokens)
        _cache_put(
            _cache_key(system_prompt, user_prompt, GEMINI_MODEL),
            text,
            {"provider": "gemini", "model": GEMINI_MODEL},
        )
        return text, "gemini"
    except Exception as e:
        last_err = e
        print(f"[llm] Gemini failed: {e}. Falling back to Groq.")

    try:
        text = call_groq(system_prompt, user_prompt, max_tokens=max_tokens)
        _cache_put(
            _cache_key(system_prompt, user_prompt, GROQ_MODEL),
            text,
            {"provider": "groq", "model": GROQ_MODEL},
        )
        return text, "groq"
    except Exception as e:
        raise RuntimeError(
            f"Both LLM providers failed. Gemini: {last_err} | Groq: {e}"
        ) from e
