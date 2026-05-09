# Approval Worker

Cloudflare Worker that bridges Telegram → GitHub Actions.

## One-time setup

```bash
npm i -g wrangler
wrangler login
cd cloudflare-worker

# Set secrets (each prompts for the value)
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_WEBHOOK_SECRET   # any long random string
wrangler secret put GITHUB_TOKEN              # fine-grained PAT, Actions: Write on the repo
wrangler secret put AUTHORIZED_CHAT_ID        # 959573065
wrangler secret put GITHUB_OWNER              # your-username
wrangler secret put GITHUB_REPO               # arjun-money-diaries

wrangler deploy
```

After deploy, the Worker URL looks like
`https://arjun-approval.<your-subdomain>.workers.dev`.

## Wire Telegram to it

```bash
TOKEN="<TELEGRAM_BOT_TOKEN>"
WEBHOOK_SECRET="<TELEGRAM_WEBHOOK_SECRET>"  # the same string you put as a secret
URL="https://arjun-approval.<your-subdomain>.workers.dev"

curl "https://api.telegram.org/bot${TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"${URL}\",\"secret_token\":\"${WEBHOOK_SECRET}\"}"
```

Verify:

```bash
curl "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```

## Test

Send `APPROVE` (or any of the other commands) to the bot from the
authorized account. You should see:
1. A "✅ Got it. Sent 'APPROVE' to GitHub..." reply within ~1s.
2. A new run on the **Handle Approval** workflow in the GitHub UI.

## Security model

- Telegram's `secret_token` header guarantees only Telegram (with the
  matching shared secret) can hit our Worker.
- The Worker rejects any chat ID that isn't yours.
- The GitHub PAT is fine-grained: scoped to one repo, Actions:Write only.
  No data exfil is possible even if the Worker were compromised.
