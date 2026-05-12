#!/usr/bin/env python3
"""
watchdog.py — monitoring and analytics.

Modes (controlled by --mode):
  reminder  → if any episode is pending_approval, ping Telegram.
              Runs every 6 hours via GitHub Actions.
  stuck     → alert if any episode is stuck at generating > 15 min.
              Runs every 6 hours alongside reminder.
  analytics → DISABLED. LinkedIn API does not grant social actions
              access to new apps. Track likes/comments manually on LinkedIn.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comms
import sheets


def reminder() -> int:
    pending = sheets.episodes_by_status("pending_approval")
    if not pending:
        return 0
    pending.sort(key=lambda r: float(r.get("Episode_No") or 1e9))
    ep = pending[0]
    msg = (
        f"⏰ REMINDER — Episode {ep.get('Episode_No')} is still waiting for "
        "your approval.\n\n"
        f"Title: {ep.get('Title', '')}\n"
        f"Concept: {ep.get('Concept', '')}\n"
        f"Word count: {ep.get('word_count', '')}\n"
        f"{ep.get('quality_passed', '')}\n\n"
        "Reply with:\n"
        "✅ APPROVE\n"
        "✏️ EDIT: [your version]\n"
        "🔄 REGENERATE\n"
        "❌ REJECT"
    )
    comms.telegram_send(msg)
    return 0


def stuck() -> int:
    stuck_eps = sheets.get_stuck_generating(threshold_minutes=15)
    if not stuck_eps:
        return 0
    for ep in stuck_eps:
        comms.telegram_send(
            f"🚨 Episode {ep.get('Episode_No')} is STUCK at Status=generating.\n"
            f"Title: {ep.get('Title', '')}\n"
            f"Generated_At: {ep.get('Generated_At', 'unknown')}\n\n"
            f"Check GitHub Actions logs. To unblock, manually set Status=queued in the Sheet."
        )
    return 0


def analytics() -> int:
    print("[watchdog] analytics: LinkedIn Social Actions API not available for this app.")
    print("[watchdog] Track likes/comments manually at linkedin.com.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["reminder", "stuck", "analytics"],
        required=True,
    )
    args = parser.parse_args()
    if args.mode == "reminder":
        return reminder()
    if args.mode == "stuck":
        return stuck()
    return analytics()


if __name__ == "__main__":
    sys.exit(main())
