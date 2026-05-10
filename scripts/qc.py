"""Quality check — verbatim port of the n8n Quality Check node."""

from __future__ import annotations

import re

WORD_SPLIT_RE = re.compile(r"[ \t\n]+")
MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
MD_ITALIC_RE = re.compile(r"\*([^*]+)\*")
MD_BOLD_UNDERSCORE_RE = re.compile(r"__([^_]+)__")
MD_ITALIC_UNDERSCORE_RE = re.compile(r"_([^_]+)_")


def strip_markdown(text: str) -> str:
    text = MD_BOLD_RE.sub(r"\1", text)
    text = MD_ITALIC_RE.sub(r"\1", text)
    text = MD_BOLD_UNDERSCORE_RE.sub(r"\1", text)
    text = MD_ITALIC_UNDERSCORE_RE.sub(r"\1", text)
    return text.strip()


def quality_check(raw_text: str) -> dict:
    """Mirror of the n8n quality-check JS, exact thresholds preserved.

    Returns a dict with everything the workflow downstream needs.
    """
    if not raw_text or not raw_text.strip():
        raise RuntimeError("LLM returned empty text")

    post_text = strip_markdown(raw_text)
    words = [w for w in WORD_SPLIT_RE.split(post_text) if w]
    word_count = len(words)

    has_hashtags = "#PersonalFinance" in post_text
    lower = post_text.lower()
    has_teaser = "dropping in 2 days" in lower or "follow for episode" in lower
    has_dialogue = '"' in post_text or '\u201c' in post_text or '\u2018' in post_text or "'" in post_text
    word_count_ok = 180 <= word_count <= 350

    quality_passed = has_hashtags and has_teaser and has_dialogue and word_count_ok

    warnings: list[str] = []
    if word_count < 220 or word_count > 280:
        warnings.append(f"Word count {word_count} (target 220-280)")
    if not has_dialogue:
        warnings.append("No dialogue detected")
    if not has_hashtags:
        warnings.append("Missing hashtags")
    if not has_teaser:
        warnings.append("Missing teaser line")

    if quality_passed:
        label = "✅ QC Passed" if not warnings else "⚠️ QC Passed with warnings"
    else:
        label = "❌ QC Failed"

    return {
        "post_text": post_text,
        "word_count": word_count,
        "has_dialogue": has_dialogue,
        "has_hashtags": has_hashtags,
        "has_teaser": has_teaser,
        "quality_passed": quality_passed,
        "quality_label": label,
        "warnings": " | ".join(warnings),
    }
