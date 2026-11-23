# Automatic Cloudflare Publisher deployment

The publisher source is `cloudflare/daily-drops-publisher-worker.js`. Its workflow is `.github/workflows/deploy-cloudflare-publisher.yml`.

## One-time GitHub setup

In GitHub → repository → Settings → Secrets and variables → Actions:

**Repository secrets**
- `CLOUDFLARE_API_TOKEN`: Create a Cloudflare API token restricted to this account, with Workers Scripts Edit and D1 Edit permissions as needed for deploying the existing Worker. Do not paste it in code or chat.
- `CLOUDFLARE_ACCOUNT_ID`: The account ID of the existing Worker.

**Repository variable**
- `CLOUDFLARE_D1_DATABASE_ID`: UUID of the **existing** D1 database currently bound to the Worker as `DB`. Find it in Cloudflare → D1 → your database. Do not create a new database.

The workflow skips deployment with a notice until all three values exist. It deploys to the existing `daily-drops-publisher` Worker, keeps environment variables, and checks `/api/health` afterward.

**Keep** the existing `PUBLISH_SECRET` Worker secret. Never store it in a public file or replace the database. Confirm the database binding is still named `DB` after the first deployment.

Once configured, editing `cloudflare/daily-drops-publisher-worker.js` on `main` triggers deployment automatically. You can also run **Deploy Daily Drops Cloudflare Publisher** from the Actions tab.

The GitHub Pages publishing workflow is separate. This Cloudflare workflow does not deploy the public site.

## Troubleshooting

- Workflow says skipped: one or more GitHub settings are missing.
- Worker deployment fails: check token scope, account ID, database UUID, and whether the existing Worker is in the same Cloudflare account.
- Health check fails: verify the D1 binding `DB`, database schema, and Worker deployment logs.
- If the first automatic deployment changes a configuration unexpectedly, use Cloudflare's deployment rollback and inspect the GitHub Actions logs.

No credentials or database identifiers belong in the repository.

## Posted deals → follower shop + Telegram (optional secrets)

The private page `https://daily-drops-publisher.alcorn224.workers.dev/posted` (same publishing secret) marks a deal as
posted. It is saved in D1 table `posted_deals` (created automatically), listed publicly at `/api/posted` for the shop's
"Just posted on Facebook" section, and sent once to Telegram when these repository secrets exist:

- `TELEGRAM_BOT_TOKEN`: token from @BotFather.
- `TELEGRAM_CHAT_ID`: `@channelusername` or the numeric chat id (e.g. `-100…`). The bot must be an admin of the channel/group.

Optional Facebook auto-sync (reads the Page's own posts every 30 minutes; off unless both are set):

- `FB_PAGE_ID`: numeric Page id.
- `FB_PAGE_TOKEN`: long-lived Page access token with `pages_read_engagement` and `pages_read_user_content`.

The deploy workflow copies each secret to the Worker without printing it. After adding or changing one, run
**Deploy Daily Drops Cloudflare Publisher** from the Actions tab.
