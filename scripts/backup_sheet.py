#!/usr/bin/env python3
"""
backup_sheet.py — dump every tab to CSV and commit to git.

Run from a GitHub Action; the action commits any diff so we get a free
versioned history of the entire Sheet (Episodes + Story_State).

Cost: zero. We're already in a checked-out repo.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sheets

OUT_DIR = Path(__file__).resolve().parent.parent / "backups" / "sheets"


def dump_tab(name: str) -> None:
    ws = sheets._sheet().worksheet(name)
    rows = ws.get_all_values()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(rows)
    print(f"[backup] wrote {path} ({len(rows)} rows)")


def main() -> int:
    for tab in ("Episodes", "Story_State"):
        try:
            dump_tab(tab)
        except Exception as e:
            print(f"[backup] tab {tab} failed: {e}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
