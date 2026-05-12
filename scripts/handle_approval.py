#!/usr/bin/env python3
"""
handle_approval.py — invoked by GitHub workflow_dispatch.

The Cloudflare Worker validates the Telegram message and dispatches
this workflow with two inputs:
  - action: APPROVE | EDIT | REGENERATE | REJECT
  - text: the original Telegram text (for EDIT, contains the user's edit)

Steps mirror the n8n approval branch:
  APPROVE   → read pending episode, post to LinkedIn with footer URL,
              mark POSTED, update concepts string for all queued,
              call LLM to update Story_State.
  EDIT      → same, but use user's edited text instead of the draft.
  REGENERATE → mark queued (the next cron run picks it up), notify.
  REJECT    → mark rejected, notify.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comms
import llm
import prompts
import sheets


def find_pending_episode() -> dict | None:
    pending = sheets.episodes_by_status("pending_approval")
    if not pending:
        return None
    pending.sort(key=lambda r: float(r.get("Episode_No") or 1e9))
    return pending[0]


def strip_markdown_quick(s: str) -> str:
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    return s.strip()


def do_approve(final_text: str, ep: dict) -> int:
    ep_no = ep["Episode_No"]
    portfolio = os.environ.get(
        "EPISODES_PORTFOLIO_URL",
        "https://alok-munshi-portfolio.vercel.app/money-diaries",
    )
    text_to_post = final_text + f"\n\n📚 Read all past episodes: {portfolio}"

    try:
        resp = comms.linkedin_post(text_to_post)
        post_url = comms.linkedin_post_url(resp)
    except Exception as e:
        traceback.print_exc()
        comms.telegram_send(f"🚨 LinkedIn post FAILED for Episode {ep_no}: {e}")
        return 2

    try:
        sheets.mark_posted(ep_no, post_url)
    except Exception as e:
        traceback.print_exc()
        comms.telegram_send(
            f"⚠️ Posted to LinkedIn ({post_url}) but Sheet update failed: {e}"
        )
        # Don't bail — we still want to update concepts and story state.

    # Update concepts string for all remaining queued rows.
    try:
        concepts_string = sheets.build_concepts_string()
        sheets.update_concepts_for_all_queued(concepts_string)
    except Exception as e:
        traceback.print_exc()
        comms.telegram_send(f"⚠️ Concepts update failed: {e}")

    # Update story state via LLM.
    try:
        story_rows = sheets.get_story_state()
        sys_msg = prompts.STORY_STATE_SYSTEM
        user_msg = prompts.build_story_state_user_prompt(
            ep_no, final_text, story_rows
        )
        text, provider = llm.generate(sys_msg, user_msg, max_tokens=400)

        # Parse JSON array — handle wrapped or trailing text from LLM.
        updates = None
        try:
            updates = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\[.*\]", text, re.S)
            if m:
                try:
                    updates = json.loads(m.group(0))
                except json.JSONDecodeError:
                    updates = None

        if updates:
            sheets.upsert_story_state_rows(updates)
            print(f"[approve] story state: updated {len(updates)} character(s)")
        else:
            # Alert explicitly — silent failure was the bug.
            comms.telegram_send(
                f"⚠️ Story state NOT updated for Episode {ep_no} — "
                f"LLM returned unparseable JSON.\nRaw: {text[:300]}"
            )

    except Exception as e:
        traceback.print_exc()
        comms.telegram_send(f"⚠️ Story state update failed (post still went out): {e}")

    comms.telegram_send(
        f"✅ Episode {ep_no} POSTED.\n{post_url}\n\nNext episode in 2 days."
    )
    return 0


def do_regenerate(ep: dict) -> int:
    ep_no = ep["Episode_No"]
    try:
        sheets.mark_status(ep_no, "queued")
    except Exception as e:
        comms.telegram_send(f"🚨 Could not requeue Episode {ep_no}: {e}")
        return 2
    comms.telegram_send(
        f"🔄 Episode {ep_no} requeued. Run the workflow_dispatch on "
        "generate.yml or wait for the next scheduled run."
    )
    return 0


def do_reject(ep: dict) -> int:
    ep_no = ep["Episode_No"]
    try:
        sheets.mark_status(ep_no, "rejected")
    except Exception as e:
        comms.telegram_send(f"🚨 Could not mark Episode {ep_no} rejected: {e}")
        return 2
    comms.telegram_send(f"❌ Episode {ep_no} REJECTED.")
    return 0


def main() -> int:
    action_raw = os.environ.get("APPROVAL_ACTION", "").strip()
    text_raw = os.environ.get("APPROVAL_TEXT", "")

    upper = action_raw.upper()

    # EDIT: the Cloudflare Worker already strips the "EDIT:" prefix and passes
    # only the body as APPROVAL_TEXT. So text_raw IS the post body — no slicing.
    if upper.startswith("EDIT:") or upper == "EDIT":
        action = "APPROVE"
        final_text = strip_markdown_quick(text_raw)
    elif upper == "APPROVE":
        action = "APPROVE"
        final_text = None  # will use draft from sheet
    elif upper == "REGENERATE":
        action = "REGENERATE"
        final_text = None
    elif upper == "REJECT":
        action = "REJECT"
        final_text = None
    else:
        comms.telegram_send(f"🚨 Unknown approval action: {action_raw!r}")
        return 2

    ep = find_pending_episode()
    if not ep:
        comms.telegram_send(
            "🚨 No pending_approval episode found. Maybe already handled?"
        )
        return 0

    if action == "APPROVE":
        if final_text is None:
            final_text = strip_markdown_quick(ep.get("post_text", ""))
        if not final_text:
            comms.telegram_send(
                f"🚨 Episode {ep.get('Episode_No')} has empty post_text."
            )
            return 2
        return do_approve(final_text, ep)
    if action == "REGENERATE":
        return do_regenerate(ep)
    if action == "REJECT":
        return do_reject(ep)
    return 2


if __name__ == "__main__":
    sys.exit(main())
