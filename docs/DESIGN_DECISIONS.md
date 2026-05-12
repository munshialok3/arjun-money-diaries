# Design Decisions

Why the system is built the way it is. Every major architectural choice documented with the reasoning, the alternatives considered, and the trade-offs accepted.

---

## 1. Google Sheets as the state store (not a database)

**Decision:** Use Google Sheets as the single source of truth for all episode state, drafts, QC results, and story state.

**Why:**
- Zero setup, zero cost, zero maintenance
- Human-readable and directly editable — you can manually fix a stuck episode in 10 seconds by changing a cell
- Built-in version history (File → Version history) as a secondary recovery layer
- gspread makes it as easy to use as a database for this scale (44 rows)
- No schema migrations, no connection pooling, no backups to configure separately

**Alternatives considered:**
- Supabase (Postgres) — adds cost, requires migrations, overkill for 44 rows
- SQLite in the repo — not accessible from multiple workflow runs without locking issues
- Airtable — similar to Sheets but adds another vendor dependency

**Trade-offs accepted:**
- No atomic transactions — mitigated by GitHub Actions concurrency groups which prevent parallel runs
- API rate limits — at our usage (~10 reads/day) we use less than 1% of the free quota
- Not queryable with SQL — not needed at this scale

---

## 2. GitHub Actions as the orchestrator (not n8n, Railway, or a server)

**Decision:** Run all automation as GitHub Actions workflows triggered by cron and workflow_dispatch.

**Why:**
- Free for public repos — unlimited minutes
- No server to maintain, patch, or monitor
- Workflow runs are logged, versioned, and visible in the GitHub UI
- Secrets management is built in
- The entire system lives in one repo — code, config, and execution history together
- Rollback is a git revert

**Alternatives considered:**
- n8n on Railway — was the original stack. Migrated away because Railway costs ~$10/month, n8n upgrades break workflows, and the visual editor makes version control painful
- Cron on a VPS — requires a running server, SSH access, and manual monitoring
- AWS Lambda + EventBridge — significant setup overhead for a personal project

**Trade-offs accepted:**
- GitHub Actions cron has 2-4 hour delays during peak times — accepted, this is not a time-critical system
- Cold start adds ~30-60 seconds per run — fine for a system where the LLM call takes 30-60 seconds anyway
- Dependent on GitHub uptime — mitigated by the local Mac fallback documented in RUNBOOK.md

---

## 3. Cloudflare Worker as the webhook bridge (not a server or ngrok)

**Decision:** Use a Cloudflare Worker to receive Telegram webhooks and translate them into GitHub workflow_dispatch calls.

**Why:**
- Free tier: 100,000 requests/day — we use ~5/day
- Zero cold start penalty for Workers (V8 isolates, not containers)
- Globally distributed — Telegram can always reach it
- No server to maintain
- Keeps the GitHub token out of Telegram's reach — the Worker holds it, not the bot

**Alternatives considered:**
- GitHub Actions webhook endpoint — GitHub doesn't expose one for external webhooks
- A small Flask server on Railway — costs money, requires uptime monitoring
- Telegram polling (instead of webhook) — requires a constantly running process

**Trade-offs accepted:**
- One more system with its own secrets to manage
- Cloudflare Worker logs are separate from GitHub Actions logs — slightly harder to debug the full flow

---

## 4. Claude Sonnet 4.5 as primary, Groq Llama 3.3 70B as fallback

**Decision:** Pay for Claude as the primary model. Use Groq's free tier as an automatic fallback.

**Why Claude primary:**
- Significantly better at maintaining consistent voice, character dynamics, and story continuity across episodes
- Follows the structured POST SKELETON reliably
- Better at the word count constraint with temperature tuning
- The $2-4/month cost is justified by the quality difference

**Why Groq fallback (not another paid model):**
- Groq's free tier gives 1,000 requests/day — more than enough for fallback use
- Llama 3.3 70B is a capable model for structured creative writing
- Cost: $0
- If Claude is down, Groq keeps the pipeline running with acceptable quality
- You still review every draft before it posts — quality variance is caught by the human gate

**Alternatives considered:**
- Gemini Flash as primary — was the original plan, switched to Claude for quality
- OpenAI GPT-4o — similar cost to Claude, no meaningful quality advantage for this use case
- Local model (Ollama) — not feasible in GitHub Actions environment

**Trade-offs accepted:**
- ~$2-4/month ongoing cost for Claude
- Groq fallback produces slightly different voice — mitigated by human review gate
- Both providers down simultaneously = no generation that day (Sheet resets to queued, retries next run)

---

## 5. Telegram as the approval channel (not email, Slack, or a web UI)

**Decision:** Send drafts to Telegram and receive approval commands via Telegram messages.

**Why:**
- Always on your phone — you see the draft the moment it's ready
- Reply from anywhere with one word
- Bot API is free and reliable
- No app to build or maintain
- Telegram delivers webhook events reliably with 24h retry on failure

**Alternatives considered:**
- Email — no structured reply parsing, no quick approval UX
- Slack — requires a Slack workspace, overkill for a one-person system
- A web dashboard with approve/reject buttons — significant build effort, requires hosting
- GitHub Actions manual approval gates — not mobile-friendly, not real-time

**Trade-offs accepted:**
- Telegram bot token is another secret to manage and rotate
- If the bot is compromised, someone could trigger posts — mitigated by AUTHORIZED_CHAT_ID validation in the Worker

---

## 6. No database for LLM output caching

**Decision:** Remove the LLM response cache. Every generation makes a live API call.

**Why:**
- The cache key included the full system prompt, which changes every episode (continuity block contains previous episode text)
- Cache hit rate in production: 0% — the hash never matched across runs
- Dead code adds maintenance burden and writes junk files to the repo
- REGENERATE intentionally wants a fresh draft — caching would defeat the purpose

**Trade-off accepted:**
- Every REGENERATE costs a full API call (~$0.05-0.10)
- At our cadence, this is negligible

---

## 7. Tiered QC gate (not a binary pass/fail)

**Decision:** Implement word count as a tiered system (fail / alert / warning / ideal / warning / alert / fail) rather than a hard binary threshold.

**Why:**
- A binary 220-260 gate was causing too many false failures — Claude often produces 265-280 word episodes that are high quality
- The human reviews every draft anyway — the gate's job is to flag, not to be the final arbiter
- Alerts (200-219, 320-339) pass but notify — you decide if the quality justifies posting
- Hard fails (below 200, above 340) are genuine problems — too short to be coherent, too long for LinkedIn

**Trade-offs accepted:**
- More complex QC logic — justified by more accurate filtering
- Alert/warning distinction requires you to read the QC label — small overhead in the approval Telegram message

---

## 8. Story state via LLM (not manual tracking)

**Decision:** After each approved post, call Claude again to update the Story_State sheet with each character's current situation.

**Why:**
- Manual tracking across 44 episodes would be error-prone and tedious
- The LLM reads the episode text and extracts what changed for each character
- This state is then injected into the system prompt for future episodes — closing the continuity loop
- Cost: ~$0.01-0.02 per episode (small JSON extraction task)

**Alternatives considered:**
- Manual updates to Story_State — too much operational overhead
- Regex/rule-based extraction — too brittle for natural language episode text
- No story state at all — would cause continuity errors by episode 10+

**Trade-offs accepted:**
- LLM occasionally returns malformed JSON — handled with fallback parsing and explicit Telegram alert
- Story state is 2-3 sentences per character — intentionally brief to keep the context window manageable

---

## 9. Daily cron with generation gate (not a true 48h cron)

**Decision:** Run the generate workflow daily but add a gate that skips generation if a `pending_approval` episode exists.

**Why:**
- GitHub Actions doesn't support "every 48 hours" natively
- Running daily and skipping is cleaner than trying to track the last run date
- The gate also protects against double-generation if you forget to respond to a draft
- Gives flexibility — if you want to post more frequently, just approve faster

**Trade-offs accepted:**
- The workflow runs and exits silently every day even when skipping — uses ~1 minute of Actions time, completely free on a public repo
- The gate reads the Sheet on every run — one extra API call per day, negligible

---

## 10. Public GitHub repository

**Decision:** Keep the repo public.

**Why:**
- Unlimited Actions minutes (vs 2,000/month for private)
- Portfolio visibility — the code is the portfolio piece
- No secrets in the code — all sensitive values are in GitHub Secrets or Cloudflare Worker secrets

**Trade-offs accepted:**
- GitHub Actions input values (APPROVE/REJECT/REGENERATE commands) are visible in run logs
- The system prompt and episode metadata are public — acceptable for a personal content project
- Anyone can see the repo structure and fork it — intentional, this is meant to be reusable
