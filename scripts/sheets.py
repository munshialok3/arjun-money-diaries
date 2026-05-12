"""
Google Sheets data layer.

We use gspread + a service-account JSON. The service-account email
must be added as Editor on the spreadsheet (it has its own email like
something@your-project.iam.gserviceaccount.com).

Schemas are exactly as today:

  Episodes columns:
    Episode_No, Title, Concept, Hook_Line, Supporting_Character,
    Difficulty_Tier, Status, Post_URL, Likes, Comments, Posted_Date,
    Concepts_Used_So_Far, post_text, word_count, has_dialogue,
    has_hashtags, has_teaser, quality_passed, Generated_At

  Story_State columns:
    Character, Current_State, Last_Updated_Episode

Status values used (unchanged):
  queued, generating, pending_approval, posted, rejected
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import gspread
from google.oauth2.service_account import Credentials


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Singleton client and sheet — avoids re-authenticating on every call.
_CLIENT: gspread.Client | None = None
_SPREADSHEET = None


def _client() -> gspread.Client:
    global _CLIENT
    if _CLIENT is None:
        raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not raw:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is required")
        if raw.lstrip().startswith("{"):
            info = json.loads(raw)
        else:
            with open(raw) as f:
                info = json.load(f)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        _CLIENT = gspread.authorize(creds)
    return _CLIENT


def _sheet():
    global _SPREADSHEET
    if _SPREADSHEET is None:
        sheet_id = os.environ["SHEET_ID"]
        _SPREADSHEET = _client().open_by_key(sheet_id)
    return _SPREADSHEET


def get_worksheet(name: str):
    """Public accessor for a named worksheet."""
    return _sheet().worksheet(name)


# ---------------------------------------------------------------------
# Episodes tab
# ---------------------------------------------------------------------
def all_episodes() -> list[dict[str, Any]]:
    ws = get_worksheet("Episodes")
    return ws.get_all_records()


def episodes_by_status(status: str) -> list[dict[str, Any]]:
    return [
        e
        for e in all_episodes()
        if str(e.get("Status", "")).strip().lower() == status.lower()
    ]


def next_queued_episode() -> dict[str, Any] | None:
    """Return the first row with Status == queued (lowest Episode_No)."""
    queued = episodes_by_status("queued")
    if not queued:
        return None
    queued.sort(key=lambda r: float(r.get("Episode_No") or 1e9))
    return queued[0]


def get_stuck_generating(threshold_minutes: int = 15) -> list[dict[str, Any]]:
    """Return episodes stuck at Status=generating for longer than threshold_minutes.
    Uses the Generated_At column (UTC ISO timestamp) to determine age."""
    generating = episodes_by_status("generating")
    if not generating:
        return []
    stuck = []
    now = datetime.now(timezone.utc)
    for ep in generating:
        ts_raw = str(ep.get("Generated_At") or "").strip()
        if not ts_raw:
            # No timestamp — conservatively treat as stuck.
            stuck.append(ep)
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_minutes = (now - ts).total_seconds() / 60
            if age_minutes > threshold_minutes:
                stuck.append(ep)
        except ValueError:
            # Unparseable timestamp — treat as stuck.
            stuck.append(ep)
    return stuck


def update_episode_fields(episode_no: float | int, fields: dict[str, Any]) -> None:
    """Update one or more cells on the row whose Episode_No matches."""
    ws = get_worksheet("Episodes")
    headers = ws.row_values(1)
    col = headers.index("Episode_No") + 1
    cell = ws.find(str(int(float(episode_no))), in_column=col)
    if cell is None:
        cell = ws.find(str(float(episode_no)), in_column=col)
    if cell is None:
        raise RuntimeError(f"Episode_No {episode_no} not found in sheet")
    row = cell.row
    updates = []
    for k, v in fields.items():
        if k not in headers:
            raise RuntimeError(f"Unknown column: {k}")
        c = headers.index(k) + 1
        updates.append({
            "range": gspread.utils.rowcol_to_a1(row, c),
            "values": [[v if v is not None else ""]],
        })
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")


def mark_status(episode_no: float | int, status: str) -> None:
    """Mark episode status. If marking as 'generating', also stamp Generated_At."""
    fields: dict[str, Any] = {"Status": status}
    if status == "generating":
        fields["Generated_At"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    update_episode_fields(episode_no, fields)


def save_draft(
    episode_no: float | int,
    *,
    post_text: str,
    word_count: int,
    has_dialogue: bool,
    has_hashtags: bool,
    has_teaser: bool,
    quality_passed: bool,
    quality_label: str,
) -> None:
    """Write the draft + QC results, set Status=pending_approval."""
    update_episode_fields(
        episode_no,
        {
            "Status": "pending_approval",
            "post_text": post_text,
            "word_count": word_count,
            "has_dialogue": "TRUE" if has_dialogue else "FALSE",
            "has_hashtags": "TRUE" if has_hashtags else "FALSE",
            "has_teaser": "TRUE" if has_teaser else "FALSE",
            "quality_passed": quality_label,
        },
    )


def mark_posted(episode_no: float | int, post_url: str) -> None:
    update_episode_fields(
        episode_no,
        {
            "Status": "posted",
            "Post_URL": post_url,
            "Posted_Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
    )


def update_concepts_for_all_queued(concepts_string: str) -> None:
    """Sets Concepts_Used_So_Far on every queued row."""
    ws = get_worksheet("Episodes")
    headers = ws.row_values(1)
    col_status = headers.index("Status") + 1
    col_concepts = headers.index("Concepts_Used_So_Far") + 1
    rows = ws.get_all_values()
    updates = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= col_status and row[col_status - 1].strip().lower() == "queued":
            updates.append({
                "range": gspread.utils.rowcol_to_a1(i, col_concepts),
                "values": [[concepts_string]],
            })
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")


def build_concepts_string() -> str:
    """Comma-joined list of concepts from posted episodes (chronological)."""
    posted = episodes_by_status("posted")
    posted.sort(key=lambda r: float(r.get("Episode_No") or 0))
    return ", ".join(c for c in (str(p.get("Concept") or "").strip() for p in posted) if c)


# ---------------------------------------------------------------------
# Story_State tab
# ---------------------------------------------------------------------
def get_story_state() -> list[dict[str, Any]]:
    ws = get_worksheet("Story_State")
    return ws.get_all_records()


def upsert_story_state_rows(updates: list[dict[str, Any]]) -> None:
    """updates: [{Character, Current_State, Last_Updated_Episode}, ...]
    Upserts by Character (case-insensitive)."""
    ws = get_worksheet("Story_State")
    headers = ws.row_values(1)
    rows = ws.get_all_values()
    char_col = headers.index("Character")
    state_col = headers.index("Current_State")
    ep_col = headers.index("Last_Updated_Episode")

    char_to_row = {}
    for i, row in enumerate(rows[1:], start=2):
        if len(row) > char_col and row[char_col].strip():
            char_to_row[row[char_col].strip().lower()] = i

    batch = []
    appends = []
    for u in updates:
        c = (u.get("Character") or "").strip()
        if not c:
            continue
        s = u.get("Current_State", "")
        e = str(u.get("Last_Updated_Episode", ""))
        key = c.lower()
        if key in char_to_row:
            r = char_to_row[key]
            batch.append({
                "range": gspread.utils.rowcol_to_a1(r, state_col + 1),
                "values": [[s]],
            })
            batch.append({
                "range": gspread.utils.rowcol_to_a1(r, ep_col + 1),
                "values": [[e]],
            })
        else:
            appends.append([c, s, e])
    if batch:
        ws.batch_update(batch, value_input_option="USER_ENTERED")
    if appends:
        ws.append_rows(appends, value_input_option="USER_ENTERED")
