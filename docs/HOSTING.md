# Hosting guide — GitHub Actions (free, no bot) or a 24/7 Discord bot on a free host

> **You don't need any of this to run Game-Express.** GitHub Actions (README → Setup) posts
> everything with webhooks and no bot token. This guide is for the **optional bot mode**: slash
> commands `/codes` `/schedule` `/status`, plus the same monitor loop running 24/7.

**Recommended combo:** GitHub Actions stays the **primary poster**. The bot runs as a
**warm standby**, set up like this:

```
INSTANCE_NAME=bot
INSTANCE_ROLE=standby
PEER_STATE_URL=https://raw.githubusercontent.com/<owner>/<repo>/main/state/state.json
```

With this setup:
- The bot answers slash commands from the Actions state.
- It posts nothing while Actions is healthy.
- It takes over automatically if Actions stops (see README → Redundancy). For that, set
  `HEARTBEAT_MINUTES=60` as a variable on the Actions repo.
- Hosts with an **ephemeral disk** (Koyeb, Render) are fine in this mode, because the state
  comes from GitHub.

Free-tier facts below were checked in September 2026. Providers change their plans, so confirm
on their pricing page.

| Host | Free? | Always on? | Disk | Notes |
|---|---|---|---|---|
| **Oracle Cloud Always Free** | ✅ forever | ✅ | persistent | ARM Ampere A1 (4 OCPU / 24 GB total). Signup approval can be hit-or-miss; a card is used for identity checks only |
| **Koyeb** (Hobby) | ✅ 1 service | ✅ (no sleep) | ephemeral | 512 MB. Great for standby mode |
| **Render** (free web service) | ✅ 750 h/mo | ❌ sleeps after 15 min idle | ephemeral | needs a free uptime pinger on `/healthz` |
| **Railway** | trial credit only | ✅ | volume | $5 one-time trial, then the Hobby plan ($5/mo) |
| Fly.io / Replit | ❌ / sleeps | — | — | Fly has no free tier for new accounts; Replit sleeps |

---

## Step 0 — Create the Discord bot (all hosts)

1. Go to <https://discord.com/developers/applications> and click **New Application** (for
   example "Game-Express").
2. Open **Bot**, click **Reset Token**, and copy it. This is your `DISCORD_BOT_TOKEN` (a
   secret; never commit it). No privileged intents are needed.
3. Open **General Information** and set **Terms of Service URL** and **Privacy Policy URL**:
   - `https://github.com/<owner>/<repo>/blob/main/TERMS_OF_SERVICE.md`
   - `https://github.com/<owner>/<repo>/blob/main/PRIVACY_POLICY.md`
4. Open **OAuth2 → URL Generator**:
   - Scopes: `bot` + `applications.commands`.
   - Bot permissions: none are required, because slash replies don't need channel permissions.
   - Open the generated URL and add the bot to your server.
5. Deploy with one of the options below. On start, the log shows `slash commands synced`.

---

## Option A — Oracle Cloud Always Free (best free 24/7)

1. Sign up at <https://www.oracle.com/cloud/free/>. Always Free resources are never charged.
2. Go to **Compute → Instances → Create instance**:
   - **Image**: Ubuntu 24.04 (or 22.04).
   - **Shape**: *Ampere* → `VM.Standard.A1.Flex` → 1 OCPU / 6 GB is plenty.
   - Add your SSH public key and click **Create**.
3. Connect:
   ```bash
   ssh ubuntu@<public-ip>
   ```
4. Install and download:
   ```bash
   sudo apt update && sudo apt install -y git python3-venv
   git clone https://github.com/<owner>/<repo>.git Game-Express && cd Game-Express
   python3 -m venv .venv && .venv/bin/pip install -r requirements-bot.txt
   ```
5. Configure:
   ```bash
   cp .env.example .env && nano .env
   ```
   Fill in `DISCORD_BOT_TOKEN`, the webhooks and `PING_ROLE_ID`. For standby mode, also set
   `INSTANCE_ROLE=standby` and `PEER_STATE_URL=…`.
6. Check the config:
   ```bash
   .venv/bin/python -m gamexpress validate
   .venv/bin/python -m gamexpress test-card --dry-run
   ```
7. Start it as a service:
   ```bash
   sudo cp deploy/game-express.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now game-express
   journalctl -u game-express -f          # live logs
   ```
8. To update later:
   ```bash
   git pull && .venv/bin/pip install -r requirements-bot.txt && sudo systemctl restart game-express
   ```

> Oracle can reclaim Always Free instances that sit almost completely idle for a long time.
> Watch for their e-mails. Converting the account to Pay-As-You-Go keeps free-tier usage at $0
> and is the usual community fix.

**Docker alternative on the same VM:**

```bash
sudo apt install -y docker.io docker-compose-v2
cp .env.example .env && nano .env
sudo docker compose -f deploy/docker-compose.yml up -d --build
```

---

## Option B — Koyeb (free, always on)

1. Sign up at <https://www.koyeb.com> (Hobby plan).
2. Go to **Create Service → GitHub → your repo**. Builder: **Dockerfile**.
3. Instance: **Free**. Region: any.
4. Set up the port and health check:
   - **Exposed port** `8000` (HTTP) with **health check path** `/healthz`.
   - Add the environment variable `PORT=8000`.
5. Add environment variables and secrets: `DISCORD_BOT_TOKEN`, `DISCORD_WEBHOOK_SCHEDULE`,
   `DISCORD_WEBHOOK_CODES`, `PING_ROLE_ID`, `INSTANCE_NAME=bot`, `INSTANCE_ROLE=standby`,
   `PEER_STATE_URL=…`.
6. Click **Deploy**. The logs should show `health endpoint listening` and `slash commands synced`.

---

## Option C — Render (free web service + keep-alive)

1. Go to <https://render.com>, then **New → Blueprint** and pick your repo. It reads
   `render.yaml`.
2. Fill in the prompted variables (`DISCORD_BOT_TOKEN`, webhooks, `PING_ROLE_ID`). Add
   `INSTANCE_ROLE=standby` + `PEER_STATE_URL` under *Environment*.
3. Deploy, then copy your URL, e.g. `https://game-express.onrender.com`.
4. Free services sleep after about 15 minutes without traffic. Create a free **HTTP monitor**
   (for example UptimeRobot) for `https://game-express.onrender.com/healthz` every **5
   minutes**.

---

## Option D — Railway (trial credit)

1. Go to <https://railway.com>, then **New Project → Deploy from GitHub repo**. The `Dockerfile`
   is detected.
2. In **Variables**, add the same variables as above.
3. In **Settings → Volumes**, mount a volume at `/app/state` so dedup persists (not needed in
   standby mode).
4. Deploy. Watch the credit usage: the trial is a one-time $5, then the Hobby plan applies.

---

## Option E — Any machine with Docker (home PC, Raspberry Pi, NAS)

```bash
git clone https://github.com/<owner>/<repo>.git Game-Express && cd Game-Express
cp .env.example .env    # fill it
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f
```

To run without a bot token (webhooks only, no slash commands), change the compose `command` to
`["python", "-m", "gamexpress", "loop"]`.

---

## Rules that prevent double posts

- **One active poster per set of channels.** Either Actions only, or Actions + bot in
  `standby`, or bot only with `ENABLED_FEATURES=schedule,codes` and Actions set to
  `ENABLED_FEATURES=none`.
- A **fresh disk** (redeploy on Koyeb, Render or Railway without a volume) makes the first run a
  **silent seed**. Old items are recorded, never re-posted.
- The bot's slash replies **never ping** anyone.
