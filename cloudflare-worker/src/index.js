/**
 * arjun-approval-worker
 *
 * Receives Telegram webhook → validates the message → triggers the
 * `approve.yml` workflow on GitHub via workflow_dispatch.
 *
 * Why a Worker (vs hitting the GitHub API from a Telegram bot host):
 *   - We need a public HTTPS URL Telegram can POST to.
 *   - Cloudflare Workers free tier = 100k req/day. We use ~5/day max.
 *   - Sub-millisecond cold start; no spin-up like Render.
 *   - No always-on VM to babysit.
 *
 * Secrets (set with `wrangler secret put <NAME>`):
 *   TELEGRAM_BOT_TOKEN          — same bot token as before
 *   TELEGRAM_WEBHOOK_SECRET     — Telegram-provided header secret
 *                                  (set when calling setWebhook)
 *   GITHUB_TOKEN                — fine-grained PAT, scoped to this repo,
 *                                  with "Actions: Write" permission
 *   AUTHORIZED_CHAT_ID          — "959573065" (your chat ID)
 *   GITHUB_OWNER                — your GitHub username/org
 *   GITHUB_REPO                 — "arjun-money-diaries"
 *
 * Deploy:
 *   npm i -g wrangler
 *   wrangler login
 *   cd cloudflare-worker
 *   wrangler deploy
 *
 * Wire up the Telegram webhook (one-time):
 *   curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
 *     -H "Content-Type: application/json" \
 *     -d '{"url":"https://arjun-approval.<your-subdomain>.workers.dev/",
 *          "secret_token":"<TELEGRAM_WEBHOOK_SECRET value>"}'
 */

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    // Telegram sends this header if you set secret_token on setWebhook.
    const tg_secret = request.headers.get("x-telegram-bot-api-secret-token");
    if (tg_secret !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("forbidden", { status: 403 });
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return new Response("bad json", { status: 400 });
    }

    const msg = payload?.message;
    if (!msg) return new Response("no message", { status: 200 });
    if (String(msg.chat?.id) !== String(env.AUTHORIZED_CHAT_ID)) {
      return new Response("unauthorized chat", { status: 200 });
    }

    const text = (msg.text || "").trim();
    const upper = text.toUpperCase();
    const valid =
      upper === "APPROVE" ||
      upper === "REJECT" ||
      upper === "REGENERATE" ||
      upper.startsWith("EDIT:");

    if (!valid) {
      // Silently ignore non-command messages.
      return new Response("ignored", { status: 200 });
    }

    // For EDIT we send the full original text (with "EDIT:" prefix
    // stripped on the Python side). For others, action == upper-case
    // canonical.
    const action = upper.startsWith("EDIT:") ? "EDIT" : upper;
    const editBody = upper.startsWith("EDIT:") ? text.slice(5).trim() : "";

    // Fire the GitHub workflow_dispatch.
    const dispatchUrl =
      `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}` +
      `/actions/workflows/approve.yml/dispatches`;

    const ghBody = {
      ref: "main",
      inputs: {
        action: action,
        text: editBody,
      },
    };

    const ghResp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "arjun-approval-worker",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(ghBody),
    });

    // Confirm to the user no matter what — fast feedback.
    await fetch(
      `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: msg.chat.id,
          text: ghResp.ok
            ? `✅ Got it. Sent '${action}' to GitHub. Watch for the run.`
            : `🚨 Could not dispatch GitHub workflow: HTTP ${ghResp.status}`,
        }),
      },
    );

    return new Response(ghResp.ok ? "dispatched" : "dispatch failed", {
      status: ghResp.ok ? 200 : 502,
    });
  },
};
