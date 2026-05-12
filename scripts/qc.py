"""Quality check for Arjun's Money Diaries episodes."""

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
    """
    Word count tiers:
      < 200        → hard fail
      200-219      → alert + pass
      220-239      → warning + pass
      240-300      → ideal (clean pass)
      301-319      → warning + pass
      320-339      → alert + pass
      340+         → hard fail
    """
    if not raw_text or not raw_text.strip():
        raise RuntimeError("LLM returned empty text")

    post_text = strip_markdown(raw_text)
    words = [w for w in WORD_SPLIT_RE.split(post_text) if w]
    word_count = len(words)

    # --- Word count tier ---
    if word_count < 200 or word_count >= 340:
        word_count_ok = False
        word_count_severity = "fail"
    elif 200 <= word_count <= 219:
        word_count_ok = True
        word_count_severity = "alert"
    elif 220 <= word_count <= 239:
        word_count_ok = True
        word_count_severity = "warning"
    elif 240 <= word_count <= 300:
        word_count_ok = True
        word_count_severity = "ok"
    elif 301 <= word_count <= 319:
        word_count_ok = True
        word_count_severity = "warning"
    elif 320 <= word_count <= 339:
        word_count_ok = True
        word_count_severity = "alert"
    else:
        word_count_ok = False
        word_count_severity = "fail"

    # --- Content checks ---
    has_hashtags = "#PersonalFinance" in post_text
    lower = post_text.lower()
    has_teaser = "dropping in 2 days" in lower or "follow for episode" in lower
    has_dialogue = bool(re.search(r'["\u201c][^"\u201d]{5,}["\u201d]', post_text))
    has_correct_opener = bool(re.match(r'Episode \d+\s*\|', post_text))
    has_dollar_before_digit = bool(re.search(r'\$\d', post_text))
    has_non_indian_instruments = bool(re.search(r'401k|IRA\b|Roth IRA|S&P 500|NASDAQ', post_text, re.IGNORECASE))
    has_rs_prefix = bool(re.search(r'\bRs\.\s*\d|\bINR\s*\d', post_text))

    quality_passed = (
        has_hashtags
        and has_teaser
        and has_dialogue
        and has_correct_opener
        and word_count_ok
        and not has_dollar_before_digit
        and not has_non_indian_instruments
        and not has_rs_prefix
    )

    # --- Build warnings list ---
    warnings: list[str] = []

    if word_count_severity == "fail":
        if word_count < 200:
            warnings.append(f"🚨 Word count {word_count} — BELOW 200, hard fail")
        else:
            warnings.append(f"🚨 Word count {word_count} — ABOVE 340, hard fail")
    elif word_count_severity == "alert":
        warnings.append(f"🚨 Word count {word_count} — outside 220-320 (target 240-300)")
    elif word_count_severity == "warning":
        warnings.append(f"⚠️ Word count {word_count} — outside 240-300 (target range)")

    if not has_correct_opener:
        warnings.append("Missing opener — must start with 'Episode N |'")
    if not has_dialogue:
        warnings.append("No dialogue detected")
    if not has_hashtags:
        warnings.append("Missing hashtags")
    if not has_teaser:
        warnings.append("Missing teaser line")
    if has_dollar_before_digit:
        warnings.append("Dollar sign before digit — use ₹ instead")
    if has_rs_prefix:
        warnings.append("Rs./INR prefix detected — use ₹ instead")
    if has_non_indian_instruments:
        warnings.append("Non-Indian instrument detected (401k/IRA/S&P 500/Roth)")

    # --- Label ---
    if not quality_passed:
        label = "❌ QC Failed"
    elif any("🚨" in w for w in warnings):
        label = "🚨 QC Passed with alerts"
    elif warnings:
        label = "⚠️ QC Passed with warnings"
    else:
        label = "✅ QC Passed"

    return {
        "post_text": post_text,
        "word_count": word_count,
        "word_count_severity": word_count_severity,
        "has_dialogue": has_dialogue,
        "has_hashtags": has_hashtags,
        "has_teaser": has_teaser,
        "has_correct_opener": has_correct_opener,
        "quality_passed": quality_passed,
        "quality_label": label,
        "warnings": " | ".join(warnings),
    }
