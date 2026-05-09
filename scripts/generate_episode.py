#!/usr/bin/env python3
"""
generate_episode.py — runs once per cron trigger.

Steps (mirror of the n8n main workflow's first half):
  1. Read next queued episode from Sheet.
  2. If none, send Telegram "no episodes" alert and exit.
  3. Mark Status=generating.
  4. Read all posted episodes + Story_State for context.
  5. Build prompt.
  6. Call LLM (Gemini → Groq fallback).
  7. Quality check.
  8. If QC failed: alert + reset Status=queued, exit 1.
  9. Save draft to Sheet, send Telegram approval message.

Exit codes:
  0  — draft sent for approval, or no episode queued (both are healthy)
  1  — QC failed (recoverable; Sheet is reset to queued)
  2  — unrecoverable error (LLM totally down, Sheet unreachable, etc.)
"""

from __future__ import annotations

import os
import sys
import traceback

# allow running as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comms
import llm
import prompts
import qc
import sheets


def main() -> int:
    try:
        ep = sheets.next_queued_episode()
    except Exception as e:
        traceback.print_exc()
        comms.telegram_send(f"🚨 generate_episode: cannot read Sheet: {e}")
        return 2

    if not ep:
        comms.telegram_send("📭 No episodes queued. Add a row with Status=queued to continue.")
        return 0

    ep_no = ep.get("Episode_No")
    title = ep.get("Title", "")
    hook = ep.get("Hook_Line", "")
    concept = ep.get("Concept", "")
    char = ep.get("Supporting_Character", "")
    tier_override = ep.get("Difficulty_Tier") or None
    concepts_used = ep.get("Concepts_Used_So_Far") or ""

    try:
        ep_no_int = int(float(ep_no))
    except (TypeError, ValueError):
        comms.telegram_send(f"🚨 Bad Episode_No: {ep_no!r}")
        return 2

    print(f"[generate] Picked Episode {ep_no_int}: {title}")

    # --- Mark as generating early so the watchdog doesn't double-pick.
    try:
        sheets.mark_status(ep_no, "generating")
    except Exception as e:
        traceback.print_exc()
        comms.telegram_send(f"🚨 Could not mark Episode {ep_no_int} generating: {e}")
        return 2

    # --- Build prompt context.
    posted = sheets.episodes_by_status("posted")
    story_rows = sheets.get_story_state()

    tier_label = prompts.tier_label_for(ep_no_int, tier_override)
    system_prompt = prompts.build_full_system_prompt(
        ep_no_int, tier_override, posted, story_rows
    )
    user_prompt = prompts.build_user_prompt(
        ep_no_int, title, hook, char, concept, tier_label, concepts_used
    )

    # --- LLM call with fallback.
    try:
        raw_text, provider = llm.generate(system_prompt, user_prompt, max_tokens=1500)
        print(f"[generate] LLM provider used: {provider}")
    except Exception as e:
        traceback.print_exc()
        # Reset to queued so the next run can retry.
        try:
            sheets.mark_status(ep_no, "queued")
        except Exception:
            pass
        comms.telegram_send(f"🚨 Both LLMs failed for Episode {ep_no_int}: {e}")
        return 2

    # --- QC.
    try:
        qcr = qc.quality_check(raw_text)
    except Exception as e:
        traceback.print_exc()
        try:
            sheets.mark_status(ep_no, "queued")
        except Exception:
            pass
        comms.telegram_send(f"🚨 QC threw an error for Episode {ep_no_int}: {e}")
        return 2

    if not qcr["quality_passed"]:
        # Reset to queued; alert.
        try:
            sheets.mark_status(ep_no, "queued")
        except Exception:
            pass
        comms.telegram_send(
            f"❌ QC FAILED for Episode {ep_no_int} — {qcr['warnings']}\n"
            f"Provider: {provider}\nWord count: {qcr['word_count']}\n"
            f"Will retry on next scheduled run."
        )
        return 1

    # --- Save draft.
    try:
        sheets.save_draft(
            ep_no,
            post_text=qcr["post_text"],
            word_count=qcr["word_count"],
            has_dialogue=qcr["has_dialogue"],
            has_hashtags=qcr["has_hashtags"],
            has_teaser=qcr["has_teaser"],
            quality_passed=qcr["quality_passed"],
            quality_label=qcr["quality_label"],
        )
    except Exception as e:
        traceback.print_exc()
        comms.telegram_send(f"🚨 Could not save draft for Episode {ep_no_int}: {e}")
        return 2

    warn_line = f"⚠️ {qcr['warnings']}" if qcr["warnings"] else ""
    msg = (
        f"📝 Episode {ep_no_int} Draft Ready\n\n"
        f"{qcr['quality_label']}\n"
        f"Provider: {provider}\n"
        f"Word count: {qcr['word_count']} / 220-280\n"
        f"Title: {title}\n"
        f"Hook: {hook}\n"
        f"Concept: {concept}\n"
        f"Character: {char}\n"
        f"Tier: {tier_label}\n"
        f"{warn_line}\n\n"
        "---\n"
        f"{qcr['post_text']}\n"
        "---\n\n"
        "Reply with:\n"
        "APPROVE — post as-is\n"
        "EDIT: [your full post] — post your version\n"
        "REGENERATE — get a fresh draft\n"
        "REJECT — skip this episode"
    )
    comms.telegram_send(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
