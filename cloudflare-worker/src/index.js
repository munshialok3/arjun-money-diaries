/**
 * arjun-approval-worker
 *
 * Receives Telegram webhook → validates the message → triggers the
 * appropriate GitHub workflow via workflow_dispatch.
 *
 * Commands:
 *   APPROVE    → triggers approve.yml with action=APPROVE
 *   EDIT: ...  → triggers approve.yml with action=EDIT + text body
 *   REGENERATE → triggers approve.yml with action=REGENERATE
 *   REJECT     → triggers approve.yml with action=REJECT
 *   RUN        → triggers generate.yml (generate next queued episode)
 *
 * Secrets (set with `wrangler secret put <NAME>`):
 *   TELEGRAM_BOT_TOKEN          — bot token
 *   TELEGRAM_WEBHOOK_SECRET     — secret set when calling setWebhook
 *   GITHUB_TOKEN                — fine-grained PAT, Actions: Write
 *   AUTHORIZED_CHAT_ID          — your numeric chat ID
 *   GITHUB_OWNER                — your GitHub username/org
 *   GITHUB_REPO                 — "arjun-money-diaries"
 */

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

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
      upper === "RUN" ||
      upper.startsWith("EDIT:");

    if (!valid) {
      return new Response("ignored", { status: 200 });
    }

    const action = upper.startsWith("EDIT:") ? "EDIT" : upper;
    const editBody = upper.startsWith("EDIT:") ? text.slice(5).trim() : "";

    // RUN triggers generate.yml, everything else triggers approve.yml
    const workflowFile = upper === "RUN" ? "generate.yml" : "approve.yml";

    const dispatchUrl =
      `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}` +
      `/actions/workflows/${workflowFile}/dispatches`;

    const ghBody = upper === "RUN"
      ? { ref: "main" }
      : { ref: "main", inputs: { action: action, text: editBody } };

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

    const confirmText = ghResp.ok
      ? upper === "RUN"
        ? `🚀 Generating next episode. Draft will arrive in ~60 seconds.`
        : `✅ Got it. Sent '${action}' to GitHub. Watch for the run.`
      : `🚨 Could not dispatch GitHub workflow: HTTP ${ghResp.status}`;

    await fetch(
      `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: msg.chat.id,
          text: confirmText,
        }),
      },
    );

    return new Response(ghResp.ok ? "dispatched" : "dispatch failed", {
      status: ghResp.ok ? 200 : 502,
    });
  },
};
