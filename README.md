# Arjun's Money Diaries — Automated LinkedIn Content Engine

![Generate Episode](https://github.com/munshialok3/arjun-money-diaries/actions/workflows/generate.yml/badge.svg)
![Backup Sheet](https://github.com/munshialok3/arjun-money-diaries/actions/workflows/backup.yml/badge.svg)

A fully automated LinkedIn content pipeline for a serialised personal finance series. AI generates each episode, a quality gate validates it, you approve from Telegram with one word — it posts to LinkedIn, updates analytics, and queues the next episode. Runs indefinitely at $0/month.

**Live series** → [alok-munshi-portfolio.vercel.app/money-diaries](https://alok-munshi-portfolio.vercel.app/money-diaries)

---

## What it does

1. **Generates** — GitHub Actions cron triggers every day. Picks the next queued episode from Google Sheets, builds a structured prompt with story continuity and character state, calls Gemini 2.5 Flash (Groq Llama 3.3 70B as automatic fallback). Runs a quality check: word count, dialogue presence, hashtags, teaser line.
2. **Delivers** — Sends the draft to Telegram with full metadata: title, hook, concept, character, word count, QC label.
3. **Approves** — You reply with one word: `APPROVE`, `EDIT: [your version]`, `REGENERATE`, or `REJECT`. A Cloudflare Worker receives the message and triggers the approval workflow on GitHub.
4. **Posts** — Approved text posts to LinkedIn via UGC API. Sheet updates to `posted`. Concepts string refreshes across all queued episodes. Story state updates via a second LLM call.
5. **Tracks** — Daily watchdog fetches LinkedIn likes and comments and writes them back to the Sheet. 6-hourly reminders if an episode is stuck in `pending_approval`.
6. **Backs up** — Daily git commit of the full Sheet as CSV. Complete version history of every episode ever generated.

---

## Architecture

```
GitHub Actions (cron daily 08:00 IST)
  └── generate_episode.py
        ├── Google Sheets → next queued episode + story state + last 2 posted episodes
        ├── Gemini 2.5 Flash → episode draft (Groq Llama 3.3 70B fallback)
        ├── Quality check → word count / dialogue / hashtags / teaser
        ├── Google Sheets → save draft, mark pending_approval
        └── Telegram → send draft for review

You reply on Telegram (APPROVE / EDIT / REGENERATE / REJECT)
  └── Cloudflare Worker (arjun-approval.munshialok3.workers.dev)
        ├── Validates chat_id + webhook secret
        └── GitHub workflow_dispatch → approve.yml

GitHub Actions (approve.yml)
  └── handle_approval.py
        ├── APPROVE / EDIT → LinkedIn UGC API → post
        │     ├── Google Sheets → mark posted, save URL
        │     ├── Rebuild concepts string → update all queued episodes
        │     └── Gemini → update Story_State tab
        ├── REGENERATE → mark queued → re-trigger generate.yml
        └── REJECT → mark rejected

GitHub Actions (watchdog.yml)
  ├── Every 6h → Telegram reminder if pending_approval
  └── Daily 10:00 IST → LinkedIn API → sync likes/comments to Sheet

GitHub Actions (backup.yml)
  └── Daily 23:30 IST → Sheet → CSV → git commit
```

---

## Stack

| Layer | Tool |
|---|---|
| Orchestration | GitHub Actions |
| AI generation (primary) | Google Gemini 2.5 Flash |
| AI generation (fallback) | Groq Llama 3.3 70B |
| Webhook bridge | Cloudflare Workers |
| Approval channel | Telegram Bot API |
| Publishing | LinkedIn UGC API |
| Data store | Google Sheets |
| Secrets | GitHub Actions Secrets + Cloudflare Worker Secrets |
| Backups | Git (CSV snapshots) |
| Monthly cost | $0 |

---

## Repo structure

```
.github/workflows/
  generate.yml       # daily cron — generates next episode
  approve.yml        # triggered by Cloudflare Worker on Telegram reply
  watchdog.yml       # reminders + LinkedIn analytics sync
  backup.yml         # daily Sheet → CSV → git commit

scripts/
  generate_episode.py   # main generation orchestrator
  handle_approval.py    # approval routing (approve/edit/regen/reject)
  watchdog.py           # reminder + analytics modes
  backup_sheet.py       # Sheet → CSV dump
  prompts.py            # system prompt + user prompt assembly
  llm.py                # Gemini + Groq client with fallback + cache
  qc.py                 # quality check gate
  sheets.py             # Google Sheets read/write layer
  comms.py              # Telegram + LinkedIn API wrappers

cloudflare-worker/
  src/index.js       # Telegram webhook → GitHub workflow_dispatch bridge

backups/
  sheets/            # Episodes.csv + Story_State.csv (auto-committed daily)

docs/
  MIGRATION.md       # original Railway → GitHub Actions migration guide
  RUNBOOK.md         # ongoing operations
  RISKS.md           # failure modes and mitigations
  COST_ANALYSIS.md   # $0 cost breakdown
  TESTING_AND_ROLLBACK.md
```

---

## Want to run this for your own series?

### Prerequisites
- GitHub account (free)
- Google account (for Sheets + Gemini API key)
- Groq account (free)
- Cloudflare account (free)
- Telegram bot (via @BotFather)
- LinkedIn developer app (for UGC posting)

### Setup in 8 steps

**1. Fork this repo**

**2. Create a Google Sheet** with two tabs: `Episodes` and `Story_State`. See `backups/sheets/Episodes.csv` for the exact column schema.

**3. Create a Google service account**
- console.cloud.google.com → IAM → Service Accounts → Create
- Download the JSON key
- Share your Sheet with the service account email (Editor access)
- Enable the Google Sheets API on the project

**4. Get your free API keys**
- Gemini: https://aistudio.google.com/apikey
- Groq: https://console.groq.com/keys

**5. Add GitHub Secrets** (Settings → Secrets → Actions):

| Secret | Value |
|---|---|
| `GEMINI_API_KEY` | from step 4 |
| `GROQ_API_KEY` | from step 4 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | full JSON file contents |
| `SHEET_ID` | your Sheet ID from the URL |
| `TELEGRAM_BOT_TOKEN` | your bot token |
| `TELEGRAM_CHAT_ID` | your numeric chat ID |
| `LINKEDIN_ACCESS_TOKEN` | from LinkedIn developer app |
| `LINKEDIN_PERSON_URN` | `urn:li:person:YOUR_ID` |
| `EPISODES_PORTFOLIO_URL` | your public episodes page URL |

**6. Deploy the Cloudflare Worker**
```bash
cd cloudflare-worker
npm install -g wrangler
wrangler login
wrangler deploy
# Then set secrets:
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_WEBHOOK_SECRET
wrangler secret put GITHUB_TOKEN        # fine-grained PAT, Actions: Write
wrangler secret put AUTHORIZED_CHAT_ID
wrangler secret put GITHUB_OWNER
wrangler secret put GITHUB_REPO
```

**7. Point Telegram webhook at the Worker**
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://arjun-approval.<your-subdomain>.workers.dev","secret_token":"<TELEGRAM_WEBHOOK_SECRET>"}'
```

**8. Customise the series**
- Edit `scripts/prompts.py` — replace the system prompt with your own series bible, characters, and tone rules
- Add your episodes to the Sheet with `Status = queued`
- Trigger the first run: Actions → Generate Episode → Run workflow

---

## Approval commands

| Command | What happens |
|---|---|
| `APPROVE` | Posts draft as-is to LinkedIn |
| `EDIT: [full text]` | Posts your edited version |
| `REGENERATE` | Discards draft, generates a fresh one immediately |
| `REJECT` | Marks episode rejected, moves to next |

---

## Cost breakdown

Everything runs on free tiers. At 1 episode per day cadence you use roughly 2% of available quotas across all providers.

| Component | Free quota | Your usage |
|---|---|---|
| GitHub Actions | 2,000 min/mo (private) or unlimited (public) | ~30 min/mo |
| Gemini 2.5 Flash | ~1,500 req/day | ~1/day |
| Groq Llama 3.3 70B | 1,000 req/day | fallback only |
| Cloudflare Workers | 100,000 req/day | ~5/day |
| Google Sheets API | 60 req/min | ~10/day |
| **Total** | | **$0/month** |

---

## LinkedIn token rotation

LinkedIn access tokens expire every ~60 days. Update the GitHub secret when it does:

```bash
gh secret set LINKEDIN_ACCESS_TOKEN --repo <your-username>/arjun-money-diaries
```

---

Built by [Alok Munshi](https://alok-munshi-portfolio.vercel.app) · IIT Kharagpur '22 · Senior Growth Analyst at Eternal (Zomato)
