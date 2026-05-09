"""Telegram + LinkedIn — thin wrappers, no business logic."""

from __future__ import annotations

import os

import requests


# ---------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------
def telegram_send(text: str, *, parse_mode: str | None = None) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    body = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        body["parse_mode"] = parse_mode
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json=body,
        timeout=20,
    )
    if not r.ok:
        # Don't crash the run if Telegram is flaky — just log.
        print(f"[telegram] send failed: {r.status_code} {r.text[:300]}")


# ---------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------
LINKEDIN_UGC_URL = "https://api.linkedin.com/v2/ugcPosts"


def linkedin_post(text_with_footer: str) -> dict:
    """POST to /v2/ugcPosts. Returns the JSON response."""
    token = os.environ["LINKEDIN_ACCESS_TOKEN"]
    urn = os.environ["LINKEDIN_PERSON_URN"]
    body = {
        "author": urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text_with_footer},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    r = requests.post(
        LINKEDIN_UGC_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"LinkedIn HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def linkedin_post_url(response: dict) -> str:
    """Derive a public post URL from the UGC response."""
    # Response includes "id" like "urn:li:share:7456926653705887744"
    share_urn = response.get("id") or ""
    if not share_urn:
        return ""
    return f"https://www.linkedin.com/feed/update/{share_urn}/"


def linkedin_fetch_social_actions(post_urn: str) -> dict:
    """GET /v2/socialActions/{urn} — likes & comments summary."""
    token = os.environ["LINKEDIN_ACCESS_TOKEN"]
    import urllib.parse as up

    encoded = up.quote(post_urn, safe="")
    r = requests.get(
        f"https://api.linkedin.com/v2/socialActions/{encoded}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
        },
        timeout=20,
    )
    if not r.ok:
        return {}
    return r.json()
