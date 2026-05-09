# Cost Analysis

## Steady-state monthly cost: $0.00

Assumptions: 1 episode every 48h = ~15 episodes/month + a few
regenerates = ~20 total generations + 1 story-state update each.

| Component                     | Free quota                                    | Your usage     | Cost  |
| ----------------------------- | --------------------------------------------- | -------------- | ----- |
| GitHub Actions (private repo) | 2,000 min/mo                                  | ~30 min/mo     | $0    |
| GitHub Actions (public repo)  | unlimited                                     | n/a            | $0    |
| GitHub repo storage           | unlimited                                     | <1 GB          | $0    |
| Cloudflare Workers            | 100,000 req/day                               | ~5/day         | $0    |
| Gemini 2.5 Flash              | 250 RPD (Pro) or 1,500 RPD (Flash)            | ~1/day         | $0    |
| Groq Llama 3.3 70B (fallback) | 1,000 RPD, 30 RPM                             | rare fallback  | $0    |
| Google Sheets API             | 60 reads/min/user, 60 writes/min/user         | ~10/day        | $0    |
| Telegram Bot API              | unlimited (fair use)                          | ~5 msg/day     | $0    |
| LinkedIn API (UGC posts)      | App rate limit (high)                         | ~15/mo         | $0    |
| **Total**                     |                                               |                | **$0**|

## Capacity headroom (how much room before you'd need to pay)

If you were posting **5x more** (one episode every 9 hours instead of
every 48h):

- GitHub Actions: ~150 min/mo, still well under 2,000 free.
- Gemini Flash: ~150 generations/mo. Still inside free tier.
- Groq: only used as fallback. Still trivially within 1,000 RPD.
- Workers: still <50 req/day on the webhook side.

**Verdict**: ~10x your current cadence still costs $0.

## What was paid before

| Component                 | Old cost           |
| ------------------------- | ------------------ |
| Railway hosting (n8n)     | ~$5/mo after credits expire |
| Claude Sonnet 4.5 API     | ~$3-5/mo (15 episodes × ~30k input tokens × Sonnet pricing) |
| **Total before**          | **~$8-10/mo**      |

So this saves ~$100-120/year while improving observability (git
history of prompts, GitHub Actions logs) and reliability (multi-LLM
fallback, no always-on container that can drift).

## Optional paid upgrades (only if worth it)

| Upgrade                                                     | Cost       | When it's worth it                                   |
| ----------------------------------------------------------- | ---------- | ---------------------------------------------------- |
| Anthropic Claude API (back to original)                     | ~$3-5/mo   | Only if Gemini + Groq quality is unacceptable for the voice. Test first (see Testing doc). |
| Cloudflare Workers Paid                                     | $5/mo      | Never needed for this workload.                      |
| GitHub Pro                                                  | $4/mo      | If you ever hit the 2k Actions minutes cap (you won't). |
| Supabase Pro (if migrating off Sheets to a real DB)         | $25/mo     | Only if multiple writers / non-spreadsheet UI matter. |

None of the above is recommended now.
