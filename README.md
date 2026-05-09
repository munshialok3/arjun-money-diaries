# Arjun's Money Diaries — Free Architecture (post-Railway migration)

A zero-recurring-cost rebuild of the three n8n workflows that drive the
"Arjun's Money Diaries" LinkedIn series. n8n + Railway + Claude API
becomes GitHub Actions + Google Sheets + Gemini 2.5 Flash + Cloudflare
Workers, with Groq Llama-3.3-70B as fallback and a local Mac-cron path
as a second fallback.

**Target steady-state cost: $0/month** for the publishing cadence in
the workflow (1 episode every 48 hours = ~15 generations/month,
including regenerates).

## What replaces what

| Old (paid / temporary)                        | New (free, durable)                                 |
| --------------------------------------------- | --------------------------------------------------- |
| n8n on Railway (paid after credits expire)    | GitHub Actions (cron) + Cloudflare Worker (webhook) |
| Anthropic Claude Sonnet 4.5 API ($)           | Google Gemini 2.5 Flash (free) + Groq Llama 3.3 70B fallback |
| n8n built-in scheduler                        | GitHub Actions `schedule:` cron                     |
| n8n webhook endpoint on Railway URL           | Cloudflare Worker (100k req/day free, no cold start)|
| n8n credentials store                         | GitHub Actions Secrets + Worker Secrets             |
| n8n execution logs                            | GitHub Actions run logs + Worker tail logs          |
| Manual Railway upkeep                         | Nothing to maintain — both providers are stable     |

**Unchanged** (these were already free and working): Google Sheets as the
data store, Telegram bot for approvals, LinkedIn UGC API for posting.

## Architecture (text diagram)

```
                       ┌─────────────────────────────────────────────┐
                       │  GitHub repo: arjun-money-diaries (private) │
                       │                                             │
   cron (every 48h) ──▶│  .github/workflows/generate.yml             │
                       │     └─▶ scripts/generate_episode.py         │
                       │           1. Read next queued ep from Sheet │
                       │           2. Build prompt (same as before)  │
                       │           3. Call Gemini → Groq fallback    │
                       │           4. Quality check                  │
                       │           5. Write draft to Sheet           │
                       │           6. Telegram: send draft           │
                       └─────────────────────────────────────────────┘
                                          │
                                          ▼  Telegram message: APPROVE / EDIT: ... / REGENERATE / REJECT
                       ┌─────────────────────────────────────────────┐
                       │  Cloudflare Worker: arjun-approval          │
                       │     • Receives Telegram webhook             │
                       │     • Validates chat_id == 959573065        │
                       │     • Triggers GitHub workflow_dispatch     │
                       │       on .github/workflows/approve.yml      │
                       └─────────────────────────────────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────────────┐
                       │  .github/workflows/approve.yml              │
                       │     └─▶ scripts/handle_approval.py          │
                       │           APPROVE → post to LinkedIn        │
                       │                   → update Sheet POSTED     │
                       │                   → update concepts string  │
                       │                   → update story state      │
                       │           EDIT:   → use edited text, post   │
                       │           REGEN   → mark queued, re-trigger │
                       │           REJECT  → mark rejected           │
                       └─────────────────────────────────────────────┘

                       ┌─────────────────────────────────────────────┐
                       │  .github/workflows/watchdog.yml             │
                       │     • Schedule 1: every 6h →                │
                       │       remind if pending_approval > 6h       │
                       │     • Schedule 2: daily 10:00 IST →         │
                       │       fetch LinkedIn likes/comments         │
                       └─────────────────────────────────────────────┘

                       ┌─────────────────────────────────────────────┐
                       │  Google Sheet (unchanged)                   │
                       │     • Episodes tab                          │
                       │     • Story_State tab                       │
                       │     ↑ accessed via service-account JSON key │
                       └─────────────────────────────────────────────┘
```

## Why this stack (vs alternatives evaluated)

I considered every option in the brief. Decisions:

- **Self-hosted n8n on a free VM (Oracle Cloud, Fly.io, Render):**
  Rejected. Free tiers shrink unpredictably (Oracle has reclaimed
  "always-free" instances; Render free web services spin down and have
  no cron on free tier; Fly.io ended free allowances in 2024). Also —
  a 24/7 VM to run a job that fires once every 48h is wasteful.
- **Vercel Cron:** Free tier crons are at most daily on Hobby and
  function timeout is 10s/60s — too short for a generation flow. Out.
- **Cloudflare Workers cron only:** 30s wall-clock CPU on paid, ~10ms
  CPU on free. Would force splitting the generation into chunks. Use
  Workers only for the webhook (sub-second).
- **GitHub Actions for the scheduler + work:** Public repo gets
  unlimited free minutes (private gets 2,000/mo, plenty for our ~15
  runs/month at ~2 min each). Secrets store is solid. No cold-start
  surprise. Logs free. **Winner.**
- **Gemini 2.5 Flash as primary LLM:** ~250-1,500 RPD free, 1M context,
  no credit card. Quality on this kind of structured creative writing
  with a tight rubric is excellent — comparable to mid-tier Claude for
  this use case. Pro is gated to 50 RPD now, so Flash is the realistic
  pick.
- **Groq Llama 3.3 70B as fallback:** 1,000 RPD free, 30 RPM, instant
  failover if Gemini errors. Different vendor, different rate-limit
  bucket — true redundancy.
- **Local Mac as third fallback:** A `make generate` script you can
  run on your Mac if both APIs are down. Same code path.
- **Ollama / local LLMs:** Possible but a 70B model needs ~40GB RAM
  and minutes of generation per episode on Apple Silicon. Free-tier
  hosted APIs win on quality-per-effort here. Keep Ollama in pocket
  for the day a vendor changes terms.

## What you keep

- The Google Sheet schema, the Telegram bot, the LinkedIn app, and
  every prompt and quality rule. No content drift.
- The same approval words: `APPROVE` / `EDIT: ...` / `REGENERATE` /
  `REJECT`.
- Story state JSON updates after every successful post.

## What's improved

- **Prompts are versioned in git.** No more editing JS blobs inside
  n8n nodes.
- **Real diff history** on every change to the system prompt.
- **Built-in retry + multi-provider fallback** (Gemini → Groq).
- **Output cache** (sha256 of the prompt) so a regenerate-after-no-edit
  doesn't re-bill or re-spend rate-limit.
- **Daily Sheet backup** to git as CSV (free version control of your
  entire content history).
- **No always-on infra** — nothing can crash, get OOM-killed, or
  silently stop billing.

See `docs/MIGRATION.md` for the step-by-step. See `docs/RUNBOOK.md`
for ongoing operations.
