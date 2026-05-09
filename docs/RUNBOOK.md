# Runbook

How to operate, monitor, and recover the system. Bookmarkable.

## Daily / weekly checks (≈ 1 minute total)

- [ ] Did this week's posts go out? Check LinkedIn or the Sheet's
      `Posted_Date` column.
- [ ] Skim recent **Generate Episode** runs at
      `https://github.com/<you>/arjun-money-diaries/actions`.
      Green = healthy. Red on a single run is usually a transient
      LLM hiccup; the Sheet auto-resets to `queued`.

## Adding a new season / new episodes

1. Open the Sheet → Episodes tab.
2. Add a row per episode with: `Episode_No`, `Title`, `Concept`,
   `Hook_Line`, `Supporting_Character`, `Difficulty_Tier`,
   `Status=queued`. Leave the rest blank — the system fills them in.
3. The next cron run picks up the lowest-numbered queued row.

## Editing the system prompt

1. Edit `scripts/prompts.py` — the `SYSTEM_PROMPT` constant.
2. Commit & push. Next run uses the new prompt.
3. Diff visible forever in `git log -p scripts/prompts.py`.

## Forcing a generation right now

Workflow `Generate Episode` → "Run workflow" button (top right) → main
branch → Run.

Useful when: testing prompt changes, regenerating ahead of schedule,
or after a queued episode was added.

## Forcing approval / regenerate / reject without Telegram

Workflow `Handle Approval` → "Run workflow" → fill `action` and `text`
inputs → Run.

`text` only matters for `EDIT:` action; for the body content paste the
final text you want posted (without the `EDIT:` prefix).

## Rotating the LinkedIn access token

LinkedIn UGC tokens expire every ~60 days. When posts start failing
with 401:

1. https://www.linkedin.com/developers/apps → your app → Auth → OAuth
   2.0 tools → Generate token.
2. Required scope: `w_member_social` (and `r_liteprofile` if regenerating).
3. Update the `LINKEDIN_ACCESS_TOKEN` secret in GitHub.
4. Re-run last failed `Handle Approval` run.

(Long-term option: implement OAuth refresh-token flow. Not done here
because it adds a moving part to a system that has 1 token rotation
every 2 months.)

## Rotating the Gemini / Groq keys

Gemini and Groq don't expire keys but you should rotate yearly.

1. Create a new key on the provider's console.
2. Update the GitHub secret.
3. Delete the old key on the provider.

## When Gemini hits the daily limit

Symptom: `Generate Episode` log says `[llm] Gemini failed: HTTP 429
... Quota exceeded`. Then it tries Groq. If Groq also fails, the run
exits 2 and the Sheet row resets to `queued`. Next cron tick retries.

Realistic likelihood of hitting it: extremely low. You generate ~1
episode every 48h. Even Gemini's tightest limit (50 RPD on Pro) is
50× your usage. We use Flash, which gives 250-1,500 RPD.

## When LinkedIn returns 4xx on posting

Common causes:
- Token expired → see "Rotating the LinkedIn access token".
- Duplicate post detected (LinkedIn rejects identical re-posts) → edit
  the text slightly via `EDIT:` and resubmit.
- Account flagged → manual review.

## When Telegram doesn't deliver the draft

Run `Watchdog & Analytics` → mode=`reminder` to re-poke. If the bot
itself is the issue, regenerate its token via @BotFather and update
`TELEGRAM_BOT_TOKEN` secret + the `wrangler secret put TELEGRAM_BOT_TOKEN`
on the Worker side.

## When the Cloudflare Worker is down

Cloudflare's free tier doesn't promise uptime SLAs but in practice it's
4-nines+. If it's truly down:

- You can still trigger `Handle Approval` from the GitHub UI manually.
- The Telegram → Worker webhook is the only path the Worker is on; nothing
  else depends on it.

## When the entire system is on fire

The fallback path runs on your Mac:

```bash
cd ~/code/arjun-money-diaries
source .venv/bin/activate
set -a; source .env; set +a
python scripts/generate_episode.py
# review the Telegram message it sends
python scripts/handle_approval.py    # uses APPROVAL_ACTION/TEXT env vars
```

Or even simpler — write the post yourself in 10 minutes and post
manually. The system is to save time, not to lock you in.

## Where to look first when something is wrong

1. **GitHub Actions tab.** Last failed run's logs almost always tell
   you exactly what happened.
2. **Sheet.** What's the current `Status` of the affected episode?
3. **`backups/sheets/Episodes.csv`** in git → previous day's snapshot
   if you suspect bad data overwrote good.
4. **Cloudflare Workers dashboard → arjun-approval → Logs** for
   approval flow issues.
