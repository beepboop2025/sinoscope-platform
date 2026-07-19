# Deploy PALIMPSEST / Social Scraper on Railway — 100% browser, zero local

Nothing runs on your laptop. You click through the **railway.app** dashboard;
Railway builds each service straight from your GitHub repo. Live data sits on
Railway volumes + managed Postgres; nightly backups go to **Google Drive**.

> **Service tiers.** Start with the 6 **core** services (~$10–15/mo) for full
> 24/7 collection + the PALIMPSEST dashboards + Drive backups. Add the
> **optional** services later — none are required to run.

| Tier | Service | Source / image | Notes |
|---|---|---|---|
| core | **Postgres** | image `timescale/timescaledb-ha:pg16` | TimescaleDB + pgvector bundled |
| core | **Redis** | Railway Redis database | Celery broker + cache |
| core | **api** | repo `Dockerfile` | FastAPI + dashboards |
| core | **worker** | repo `Dockerfile` | collectors + processors (Celery) |
| core | **beat** | repo `Dockerfile` | the 24/7 scheduler |
| core | **backup** | repo `deploy/Dockerfile.backup` | nightly cron → Google Drive |
| optional | nlp-worker | repo `Dockerfile` | dedicated NLP queue |
| optional | flower | repo `Dockerfile` | Celery monitoring UI |
| optional | kafka (Redpanda) | image `redpandadata/redpanda` | advanced pipeline (Kafka-wire) |
| optional | tor | image `dperson/torproxy` | dark-web sources |

MinIO is **not needed** — raw storage falls back to the filesystem (`USE_MINIO=false`),
so it lives on the worker's volume and is reproducible.

---

## Step 1 — Mint a Google Drive token without a laptop (Google Cloud Shell)

rclone needs a Drive credential. Generate it in the browser using **Google Cloud
Shell** (free, no install):

1. Open **https://shell.cloud.google.com** (sign in with the Google account that
   owns the Drive).
2. In the shell, run:
   ```bash
   rclone config
   #  n) New remote
   #  name> gdrive
   #  Storage> drive
   #  client_id> (Enter, blank)
   #  client_secret> (Enter, blank)
   #  scope> 1   (full access)
   #  Edit advanced config> n
   #  Use web browser to automatically authenticate> y
   #     Cloud Shell opens the Google consent screen in your browser → Allow
   #  Configure as Shared Drive> n
   #  y) Yes this is OK
   ```
3. Create the target folder and export the config as a one-line secret:
   ```bash
   rclone mkdir gdrive:PALIMPSEST/backups
   base64 -w0 ~/.config/rclone/rclone.conf ; echo
   ```
4. **Copy that base64 string** — it's your `RCLONE_CONF_BASE64` secret for Railway.

## Step 2 — Create the Railway project

1. Sign in at **https://railway.app** with GitHub.
2. **New Project → Deploy from GitHub repo →** pick `beepboop2025/sinoscope-platform`.
   Railway creates a first service from the repo — rename it **api** (Settings →
   Service name). This app lives in a subdirectory of the monorepo, so set
   **Settings → Root Directory** to `apps/social-scraper` (do this for every
   repo-based service below, so the `Dockerfile` and `deploy/railway/*.json`
   paths resolve).

## Step 3 — Add the databases (managed)

1. **New → Database → Add Redis.** Railway provisions it and exposes `REDIS_URL`.
2. **New → Empty Service → Deploy from Docker Image →** `timescale/timescaledb-ha:pg16`.
   Name it **Postgres**. Then:
   - **Variables:** `POSTGRES_USER=scraper`, `POSTGRES_PASSWORD=<strong-pw>`,
     `POSTGRES_DB=econscraper`.
   - **Settings → Volumes → Add Volume**, mount path `/home/postgres/pgdata`.
   - (Private networking gives it the hostname `postgres.railway.internal`.)

## Step 4 — Configure each repo service

For **api**, **worker**, **beat** (and optional **nlp-worker**, **flower**),
create a service from the repo (**New → GitHub Repo →** same repo) and in
**Settings**:

- **Config-as-code path:** point to the matching file, e.g. `deploy/railway/worker.json`
  (these set the build + start command + restart policy). *Or* skip the file and
  paste the start command into **Settings → Deploy → Custom Start Command** —
  the commands are listed in each `deploy/railway/*.json`.
- **worker only → Settings → Volumes → Add Volume**, mount path `/app/data`
  (persists raw data + CBB/DDTI snapshots across redeploys).

### Shared variables (api, worker, beat, nlp-worker)

Set these on each (Railway **Shared Variables** at the project level is easiest —
define once, reference everywhere):

```ini
DATABASE_URL=postgresql://scraper:<strong-pw>@postgres.railway.internal:5432/econscraper
REDIS_URL=${{Redis.REDIS_URL}}
RAW_DATA_DIR=/app/data/raw
USE_MINIO=false
TZ=Asia/Kolkata
# any source API keys you want live:
FRED_API_KEY=...
GITHUB_TOKEN=...
# ...see .env.example for the full list
```

`beat` only strictly needs `REDIS_URL`. `api` and `flower` get `$PORT`
automatically from Railway (the start commands already use it).

## Step 5 — Add the backup cron (→ Google Drive)

1. **New → GitHub Repo →** same repo. Name it **backup**.
2. **Settings → Config-as-code path:** `deploy/railway/backup.json`
   (builds `deploy/Dockerfile.backup`, sets cron `0 2 * * *`, restart `NEVER`).
   Adjust the cron in that file if you want a different time (UTC).
3. **Variables:**
   ```ini
   BACKUP_RUN_ONCE=1
   DATABASE_URL=postgresql://scraper:<strong-pw>@postgres.railway.internal:5432/econscraper
   RCLONE_REMOTE=gdrive:PALIMPSEST/backups
   RCLONE_CONF_BASE64=<the base64 string from Step 1>
   REMOTE_RETENTION_DAYS=30
   ```
   On each scheduled run it does `pg_dump | gzip` and `rclone copy`s the dump to
   Drive, then exits. (The DB is your system of record; CBB/DDTI disk snapshots
   live on the worker volume and are re-pullable.)

## Step 6 — Initialize the database (one time)

After **Postgres**, **api**, and **worker** are deployed, run the schema setup
once. Easiest: temporarily set **api → Custom Start Command** to

```
sh -c "alembic upgrade head; python scripts/init_db.py; uvicorn api.main:app --host 0.0.0.0 --port $PORT"
```

Deploy once (it migrates, then serves), then revert to the plain uvicorn command
(or leave it — both steps are idempotent).

## Step 7 — Go live

- **api → Settings → Networking → Generate Domain** → you get a public HTTPS URL.
  Open `https://<your-app>.up.railway.app/` and `…/api/v4/ddti/app` for the
  PALIMPSEST terminal.
- **beat** + **worker** are now collecting 24/7 on the `config/sources.yaml`
  schedule. Confirm in each service's **Deploy Logs**.
- **backup** runs tonight at the cron time; trigger a test now with the service's
  **⋯ → Run** (or temporarily set the cron a few minutes ahead). Verify with
  `rclone ls gdrive:PALIMPSEST/backups` back in Cloud Shell.

---

## Cost & scaling notes

- Core 6 services on Railway's usage-based pricing land around **$10–15/mo** at
  this workload; adding nlp-worker/flower/kafka/tor pushes toward **$20–30**.
- Scale a queue by bumping **worker** replicas (Settings → Replicas) or
  `--concurrency`. Keep **beat at exactly 1 replica** — multiple schedulers would
  double-fire tasks (already pinned via `numReplicas: 1`).
- To add **Kafka** later: New → Docker Image → `redpandadata/redpanda:latest`
  (Kafka-wire-compatible, single container), set `KAFKA_BOOTSTRAP_SERVERS` on the
  workers to its private address.
- Want raw object payloads in Drive too? Set `BACKUP_INCLUDE_MINIO=1` and mount
  the worker volume — or move object storage to Cloudflare R2 (S3-compatible) and
  point `MINIO_ENDPOINT` at it with `USE_MINIO=true`.

## Updating

Push to `main` → Railway auto-redeploys every service watching the repo. No
laptop, no manual steps.
