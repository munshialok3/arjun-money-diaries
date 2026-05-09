# Migration Plan

A step-by-step migration from n8n-on-Railway to GitHub Actions + a
Cloudflare Worker. Total time: ~2 hours, mostly waiting for tokens.

## ⚠️ Step 0 — Rotate exposed credentials FIRST

Your uploaded n8n JSON files contain plaintext:
- An Anthropic API key (`sk-ant-api03-Sc3U4...`)
- A LinkedIn access token (`AQWDGwK_J6N...`)
- The webhook shared secret (`arjun-v2-secret-2025`)

Before doing anything else:

1. **Anthropic key** — log in to console.anthropic.com → Settings → API
   Keys → revoke that key. (You won't need a new one; we're moving off
   Claude.) If your Railway-hosted n8n is still running, this also
   instantly stops any further $ charge from anywhere using it.
2. **LinkedIn token** — at linkedin.com/developers, regenerate the
   access token for the app. We'll put the new one into GitHub Secrets.
3. **Webhook secret** — the new system uses Cloudflare's
   `secret_token` header, so the old `arjun-v2-secret-2025` is dead.

You can keep the same Telegram bot token unless you want to be extra
cautious — but rotating it via @BotFather (`/revoke`) is a one-minute job.

## Step 1 — Get the free LLM API keys

1. **Gemini**: https://aistudio.google.com/apikey → "Create API key" →
   choose any Google Cloud project (or let it auto-create one). No
   credit card needed. Save as `GEMINI_API_KEY`.
2. **Groq**: https://console.groq.com/keys → "Create API Key". Save as
   `GROQ_API_KEY`.

## Step 2 — Create the Google service account

The current setup uses your personal OAuth which is a hassle to manage
in CI. A service account is cleaner:

1. https://console.cloud.google.com/iam-admin/serviceaccounts → choose
   any project → **Create service account** → name it
   `arjun-money-diaries`.
2. Skip role assignment (we'll grant access on the Sheet directly).
3. **Keys → Add Key → Create new key → JSON.** Download. This is the
   secret you'll paste into GitHub.
4. Open the Google Sheet → **Share** → paste the service account's
   email (looks like `arjun-money-diaries@<project>.iam.gserviceaccount.com`)
   → **Editor** → Send.

## Step 3 — Create the GitHub repo

```bash
# from your Mac
cd ~/code   # or wherever
mkdir arjun-money-diaries && cd arjun-money-diaries
# copy in everything from this package
git init -b main
git add .
git commit -m "initial migration scaffold"
gh repo create arjun-money-diaries --private --source=. --push
```

(If `gh` isn't installed: `brew install gh` then `gh auth login`.)

## Step 4 — Add GitHub Secrets

At https://github.com/<you>/arjun-money-diaries/settings/secrets/actions
add these one by one (Repository secrets, not Environment):

| Name                            | Value                                                                |
| ------------------------------- | -------------------------------------------------------------------- |
| `GEMINI_API_KEY`                | from Step 1                                                          |
| `GROQ_API_KEY`                  | from Step 1                                                          |
| `GOOGLE_SERVICE_ACCOUNT_JSON`   | paste the entire JSON file contents                                  |
| `SHEET_ID`                      | `1vsJkdHva1TFpm0JyXFxek16J3PxkZgfGHMhL_Lu5EF8`                       |
| `TELEGRAM_BOT_TOKEN`            | bot token (same as before, or rotated)                               |
| `TELEGRAM_CHAT_ID`              | `959573065`                                                          |
| `LINKEDIN_ACCESS_TOKEN`         | rotated from Step 0                                                  |
| `LINKEDIN_PERSON_URN`           | `urn:li:person:qGqiI6OZqF`                                           |
| `EPISODES_PORTFOLIO_URL`        | `https://alok-munshi-portfolio.vercel.app/money-diaries`             |

## Step 5 — Smoke-test from your Mac (optional but recommended)

```bash
cd arjun-money-diaries
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in the values
set -a; source .env; set +a
python scripts/generate_episode.py
```

You should get a Telegram message with a draft. The Sheet's Episode 4
should have flipped from `pending_approval` → `generating` →
`pending_approval` again with new draft text.

If it works locally, push and the same code runs in GitHub Actions.

## Step 6 — Deploy the Cloudflare Worker

See `cloudflare-worker/README.md`. After deploy, you'll have a URL like
`https://arjun-approval.<sub>.workers.dev`.

Set a Telegram webhook pointing at it (one curl, in the Worker README).

## Step 7 — Disable the old n8n workflows

1. Open Railway → your n8n project → toggle each workflow to
   "Inactive". Don't delete yet — keep them as a fallback for 1-2 weeks.
2. Optionally pause/delete the Railway service after a successful
   migration. (You can revive the n8n workflows from the JSON files at
   any time, since you have copies.)

## Step 8 — Verify end-to-end

1. In the Sheet, check that Episode 4 (the currently-pending one) is
   `pending_approval` with a draft.
2. Manually trigger `Handle Approval` workflow with action=`APPROVE`
   from the GitHub UI to test posting. (Or message the bot.)
3. Confirm: LinkedIn post appears, Sheet row flips to `posted`,
   `Concepts_Used_So_Far` updates on remaining queued rows, Story_State
   updates.
4. Run **Watchdog & Analytics** workflow manually with `mode=analytics`
   to confirm LinkedIn likes/comments fetch still works.

## Step 9 — Wait one cron cycle

Within 24 hours the **Generate Episode** workflow runs at 02:30 UTC.
Confirm it picks up the next queued episode (Episode 5).

## Migration checklist (printable)

- [ ] Step 0 — Anthropic key revoked
- [ ] Step 0 — LinkedIn token regenerated
- [ ] Step 0 — n8n webhook URL no longer reachable from outside
- [ ] Step 1 — Gemini API key created
- [ ] Step 1 — Groq API key created
- [ ] Step 2 — Google service account created
- [ ] Step 2 — Service account added to Sheet as Editor
- [ ] Step 3 — GitHub repo created & code pushed
- [ ] Step 4 — All 9 secrets added to GitHub
- [ ] Step 5 — Local smoke test passed (optional)
- [ ] Step 6 — Cloudflare Worker deployed
- [ ] Step 6 — Telegram webhook pointed at Worker URL
- [ ] Step 6 — Telegram webhook confirmed via `getWebhookInfo`
- [ ] Step 7 — Old n8n workflows toggled inactive
- [ ] Step 8 — APPROVE flow tested end-to-end
- [ ] Step 8 — Analytics flow tested
- [ ] Step 9 — First scheduled run succeeded
