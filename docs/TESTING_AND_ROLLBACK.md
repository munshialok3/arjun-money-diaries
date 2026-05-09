# Testing & Rollback

## Pre-cutover testing (before disabling old n8n)

- [ ] **Local generation** — run `python scripts/generate_episode.py`
      from your Mac with `.env` set. Telegram draft arrives. Sheet
      row updates correctly.
- [ ] **GitHub generation** — `Generate Episode` workflow_dispatch.
      Same expectations as local.
- [ ] **Quality check parity** — pick a previously-generated episode
      (e.g. Episode 3's `post_text`) and feed it through `qc.py`
      manually:
      ```python
      from scripts.qc import quality_check
      print(quality_check(open('test_post.txt').read()))
      ```
      Expect: same `quality_label` as the Sheet's `quality_passed`
      column showed previously.
- [ ] **Approval — APPROVE**. Trigger `Handle Approval` with
      action=APPROVE. LinkedIn post appears. Sheet `Status=posted`.
      `Concepts_Used_So_Far` updates on remaining queued rows.
      Story_State updates.
- [ ] **Approval — EDIT** with custom text. Trigger with
      action=`EDIT: <full edited text>`. Verify the edited text is
      what hit LinkedIn (not the draft).
- [ ] **Approval — REGENERATE.** Status flips to `queued`,
      `generate.yml` is auto-fired, new draft arrives.
- [ ] **Approval — REJECT.** Status flips to `rejected`. No LinkedIn
      activity.
- [ ] **Telegram → Worker → GitHub.** Send `APPROVE` from the
      authorized account. Worker confirms within 1s. GitHub run
      starts within 1-2s.
- [ ] **Telegram from unauthorized account.** Worker rejects (silent).
- [ ] **Telegram with garbage text** (e.g. "lol"). Worker silently
      ignores, no GitHub run.
- [ ] **Watchdog reminder.** With one episode in `pending_approval`,
      run `Watchdog & Analytics` mode=reminder. Telegram message
      arrives.
- [ ] **Watchdog analytics.** Run mode=analytics. Sheet `Likes` and
      `Comments` update for posted episodes.
- [ ] **Backup workflow.** Run `Backup Sheet` manually. New commit
      with `backups/sheets/Episodes.csv` and `Story_State.csv` lands
      in `main`.

## Quality regression check

This is the one that matters: does Gemini Flash (or Groq) match the
voice that Claude Sonnet 4.5 was producing?

Procedure:
1. Pick 2-3 already-posted episodes. Note their `Concept`, `Hook_Line`,
   `Supporting_Character`, `Difficulty_Tier`.
2. In the Sheet, set Status of those episodes back to `queued`
   temporarily.
3. Workflow_dispatch `generate.yml`.
4. Compare the new draft to the original `post_text` on:
   - Voice consistency (Arjun's self-deprecating tone, Rohit's
     phone-calculator move, Vikram's reserved style, Dev's optimism)
   - Adherence to skeleton (Episode header, hook, scene, concept,
     teaser, hashtags, follow-line)
   - Word count (should land in 220-280)
   - No markdown bleed-through
5. If 2 of 3 are clearly close in quality, ship it. If most are
   disappointing, see "Quality fallback" below.

**Reset after testing**: change those episodes' Status back to
`posted` and restore the `post_text`/`Post_URL` from the
`backups/sheets/Episodes.csv` (or your most recent CSV backup
before the test).

## Quality fallback (if Gemini quality lags)

In rough order of effort:

1. **Switch primary model in `scripts/llm.py`.** Replace
   `GEMINI_MODEL = "gemini-2.5-flash"` with `gemini-2.5-pro`. The Pro
   model is gated to ~50-100 RPD on free tier — plenty for a once-per-2-days
   workflow, just not for higher cadences. Will need a new key with
   "billing enabled but free tier" sometimes — check current docs.
2. **Try `llama-3.3-70b-versatile` as primary** (swap order in
   `generate()`). Groq is faster than Gemini and very strong on
   structured creative tasks.
3. **Use OpenRouter free models** as a third provider. Add a `call_openrouter`
   in `llm.py` and try `meta-llama/llama-3.3-70b-instruct:free` or
   `deepseek/deepseek-chat-v3.1:free` (verify availability — the free
   list rotates).
4. **As a last resort, keep paying for Claude.** Anthropic has a
   light "build with Claude" tier that's $5 minimum spend. The current
   workflow does ~30 generations/month at maybe $0.10 each = ~$3/mo.
   Cheap; not zero. Prompt structure already works as-is — just
   restore the original API call inside `llm.py` as `call_claude` and
   put it first in the chain.

## Rollback to n8n

If something goes wrong post-cutover:

1. Re-enable both n8n workflows in Railway. Toggle to "Active".
2. Re-create the Telegram webhook to point at the n8n webhook URL:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://n8n-production-335d.up.railway.app/webhook/telegram-trigger"
   ```
   (Or whatever the n8n Telegram trigger registered.)
3. The old Anthropic key is revoked from Step 0 — generate a fresh one,
   update n8n's HTTP Request nodes.
4. The old LinkedIn token is rotated — update n8n's HTTP Request nodes.

The old system goes back to working in 5 minutes. **Keep Railway
billing active for 1-2 weeks** as a real fallback before deleting the
service.

## Long-term scalability options (only if needed)

| If…                                                         | Then…                                                                     |
| ----------------------------------------------------------- | ------------------------------------------------------------------------- |
| Cadence becomes daily (not every 48h)                       | No change needed. GitHub Actions free tier still trivially handles it.    |
| You're generating > 100 episodes/month                       | Gemini Flash still fits free tier. Groq still fits. No change needed.    |
| You want self-hosted-only (no third-party LLM trust)        | Add Ollama on your Mac, route via `tailscale serve` or ngrok. Runs only when Mac is up; CI script falls back to it last. |
| Multiple writers / collaboration                            | Switch from Sheet to Supabase free tier. Adds a row-level UI.            |
| Going viral, needs retry/queue                              | Add GitHub Actions matrix or a Cloudflare Queue. Both still free at small scale. |
