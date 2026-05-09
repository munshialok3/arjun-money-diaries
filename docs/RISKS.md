# Reliability Risks & Mitigations

A frank list of failure modes in the new architecture and what
softens each one.

## High-likelihood, low-impact

### LLM rate-limit hit on a given day
- **Symptom**: `Generate Episode` fails one run with HTTP 429.
- **Mitigation**: Multi-provider fallback (Gemini → Groq) means both
  must be down simultaneously to fail. If both fail, the Sheet auto-resets
  to `queued` and the next 24h cron tick retries.
- **Real probability at your cadence**: <0.1%.

### Quality variance between Gemini Flash and Claude Sonnet 4.5
- **Symptom**: an episode lands in QC-warning territory more often,
  or voice drifts subtly.
- **Mitigation**: Same prompts; same QC gate; you still review every
  draft on Telegram before it posts. Worst case: you `REGENERATE` or
  `EDIT:` and post.
- **Long-term**: see Testing doc → "Quality fallback".

### Telegram webhook briefly missing a delivery
- **Symptom**: you reply `APPROVE` but no GitHub run starts.
- **Mitigation**: 6-hourly watchdog reminds you of `pending_approval`
  episodes. You can also dispatch `Handle Approval` manually.
- **Telegram retries failed deliveries** for 24h, so transient Worker
  cold starts (~ms) won't cause loss.

## Medium-likelihood, medium-impact

### LinkedIn access token expires
- **Symptom**: `Handle Approval` fails on the post step with HTTP 401.
- **Mitigation**: 60-day expiry is documented in the runbook. Set a
  calendar reminder for day 50 (every 60 days).
- **Long-term option**: implement OAuth refresh-token flow. Adds ~50
  lines of code; not done because token rotation is so infrequent.

### Google Sheets API quota or downtime
- **Symptom**: workflow fails on Sheet read/write.
- **Mitigation**: gspread retries on transient failures. Quota at our
  usage is ~1% of the per-user limit, so quota errors are ~impossible.
  Daily CSV backup gives you a recovery point if data is corrupted.

### Cloudflare Worker outage
- **Symptom**: Telegram replies don't trigger GitHub.
- **Mitigation**: Manual workflow_dispatch from the GitHub UI is
  always available.
- **Cloudflare uptime track record is multi-9.**

## Low-likelihood, high-impact

### Free tier policy change at Gemini or Groq
- **Symptom**: HTTP 402 Payment Required errors, or the model is
  removed.
- **Mitigation**: Two providers reduce single-vendor risk. Adding a
  third is a 30-line change in `llm.py`. Worst case, you fall back to
  paying $3-5/mo for Claude — exactly where you started, no migration
  needed.

### LinkedIn API changes / suspends app
- **Symptom**: posts stop working entirely.
- **Mitigation**: System still generates drafts to Telegram. You
  manually paste to LinkedIn until the API issue clears. **This is the
  same risk you had with n8n.**

### Sheet accidentally edited / deleted
- **Symptom**: episodes data lost.
- **Mitigation**:
  - Daily CSV backup → git, with full version history.
  - Google Sheets has its own version history (File → Version history).
  - `Story_State.csv` and `Episodes.csv` in `backups/sheets/` can be
    re-imported via Google Sheets' "Import → Replace data".

### GitHub Actions outage
- **Symptom**: scheduled run misses.
- **Mitigation**: Local Mac fallback (`python scripts/generate_episode.py`).
  GitHub uptime is multi-9.

## Things you should do now to harden further

- [ ] Add a calendar reminder for day-50 LinkedIn token rotation.
- [ ] Periodically (monthly) verify the Backup workflow ran:
      `git log --oneline -- backups/sheets/`.
- [ ] Save the GitHub Actions secrets list somewhere (1Password, Bitwarden)
      so you can rebuild from scratch if your account is compromised.
- [ ] Pin the gspread / google-auth versions (already done in
      `requirements.txt`) and renew once a quarter.

## Things you don't need to worry about

- "Will the credits run out?" — Free tiers, not credits.
- "Will Railway shut me down?" — You're off Railway.
- "Will n8n upgrade break me?" — You're off n8n.
- "Will the Anthropic bill spike?" — You're off Claude.
- "Will the cron drift?" — GitHub Actions cron has been stable for years.
- "Will I forget how this works?" — Read RUNBOOK.md. It's deliberately
  short.
