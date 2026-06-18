# Deploying PALIMPSEST / Social Scraper 24/7 on a VPS

This runbook takes you from a blank Linux VPS to the full stack running
continuously, with **live data on an attached disk** and **nightly backups to
Google Drive**.

Target: any Ubuntu/Debian VPS (Hetzner, DigitalOcean, Linode, etc.).
Recommended size: **2 vCPU / 4 GB RAM / 40 GB disk** minimum — the stack runs
Postgres, Redis, Kafka, MinIO, Tor, and several Celery workers. 8 GB is
comfortable if you run the NLP models.

---

## 0. The two data targets at a glance

| Data | Lives on | How |
|---|---|---|
| Postgres (TimescaleDB), Redis AOF, MinIO objects | **Attached disk** at `${DATA_DRIVE}` | bind-mounted volumes (prod overlay) |
| App snapshots (`data/cbb`, `data/ddti`) | **Attached disk** (in the repo checkout) + Google Drive | tarred nightly |
| Nightly DB dump + data archive | **Google Drive** | `backup` service → rclone |

---

## 1. Provision the VPS and attach a disk

Create the VM, then attach a block volume (DigitalOcean Volume / Hetzner Volume).
Mount it — assuming it appears as `/dev/sdb`:

```bash
sudo mkfs.ext4 -F /dev/sdb                       # ONLY if the volume is new/empty
sudo mkdir -p /mnt/data
echo '/dev/sdb /mnt/data ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab
sudo mount -a
df -h /mnt/data                                  # confirm it's mounted
```

> No separate volume? You can point `DATA_DRIVE` at any path on the root disk
> (e.g. `/opt/palimpsest-data`). You still get the bind-mount layout and Drive
> backups; you just don't get a physically separate disk.

Create the data subdirectories the stack expects:

```bash
sudo mkdir -p /mnt/data/{postgres,redis,minio,backups}
sudo chown -R "$USER":"$USER" /mnt/data
```

## 2. Install Docker + Compose

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER" && newgrp docker
sudo systemctl enable --now docker        # <-- enables containers to come back after reboot
```

## 3. Clone and configure

```bash
sudo mkdir -p /opt/social-scraper && sudo chown "$USER":"$USER" /opt/social-scraper
git clone https://github.com/beepboop2025/social-scraper.git /opt/social-scraper
cd /opt/social-scraper
cp .env.example .env
```

Edit `.env` and set at minimum:

```ini
POSTGRES_PASSWORD=<a-strong-password>
DATA_DRIVE=/mnt/data
TZ=Asia/Kolkata

# Google Drive backups (configured in step 4)
RCLONE_REMOTE=gdrive:PALIMPSEST/backups
RCLONE_CONFIG_DIR=/home/<youruser>/.config/rclone
BACKUP_HOUR=2                 # 02:00 local time
LOCAL_RETENTION_DAYS=7
REMOTE_RETENTION_DAYS=30
BACKUP_INCLUDE_MINIO=0        # set 1 to also push raw object store (can be large)

# plus whatever source API keys you want live (FRED_API_KEY, GITHUB_TOKEN, ...)
```

## 4. Connect Google Drive (rclone, one-time)

rclone is how a headless server talks to Google Drive. Configure it once:

```bash
sudo apt-get update && sudo apt-get install -y rclone   # or: curl https://rclone.org/install.sh | sudo bash
rclone config
#  n) New remote
#  name> gdrive
#  Storage> drive
#  client_id/secret> (blank is fine to start)
#  scope> 1  (full access)  — or 2 for drive.file
#  Use auto config> N   (headless!)  → it prints a URL
#     run `rclone authorize "drive"` on your LAPTOP, paste the token back
#  Configure as team drive> N
```

Verify and pre-create the target folder:

```bash
rclone mkdir gdrive:PALIMPSEST/backups
rclone lsd gdrive:PALIMPSEST           # should list the backups folder
```

Make sure `RCLONE_CONFIG_DIR` in `.env` points at the dir holding `rclone.conf`
(`rclone config file` prints the path — usually `~/.config/rclone`).

## 5. Launch the stack

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml ps
```

Initialize the database (first run only):

```bash
docker compose exec api python scripts/init_db.py
docker compose exec api alembic upgrade head
```

The `beat` service now drives 24/7 collection from `config/sources.yaml`; the
`backup` service runs an immediate baseline backup, then nightly at `BACKUP_HOUR`.

## 6. Survive reboots

Containers already carry `restart: unless-stopped`, and `systemctl enable docker`
brings them back after a reboot. For an explicit, config-refreshing boot start
(useful after `git pull`), install the systemd unit:

```bash
sudo cp deploy/palimpsest.service /etc/systemd/system/palimpsest.service
sudo sed -i "s#/opt/social-scraper#$PWD#; s/^User=.*/User=$USER/" /etc/systemd/system/palimpsest.service
sudo systemctl daemon-reload
sudo systemctl enable --now palimpsest.service
```

## 7. Access the dashboards (ports are bound to 127.0.0.1 — not public)

The prod overlay binds all ports to localhost. Reach them from your laptop via
an SSH tunnel:

```bash
ssh -L 8000:127.0.0.1:8000 -L 5555:127.0.0.1:5555 <user>@<vps-ip>
# then open http://localhost:8000  (API + /api/v4/ddti/app)
#           http://localhost:5555  (Flower — Celery monitoring)
```

For a permanent public URL, put Caddy or nginx in front of `:8000` with TLS and
open only 80/443 in your firewall (`ufw allow 80,443/tcp`). Keep 5432/6379/9092
closed.

---

## Operating it

```bash
# health + logs
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml logs -f beat worker
docker compose exec api make health

# trigger a backup right now (also pushes to Drive)
docker compose run --rm backup /usr/local/bin/backup.sh /backups

# confirm backups landed in Drive
rclone ls gdrive:PALIMPSEST/backups

# restore a DB dump
gunzip -c /mnt/data/backups/econscraper_db_<ts>.sql.gz | \
  docker compose exec -T postgres psql -U scraper econscraper
```

## Updating

```bash
cd /opt/social-scraper && git pull
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
```

## What's where

- **Live DB / cache / objects** → `${DATA_DRIVE}/{postgres,redis,minio}`
- **Local backup archives** → `${DATA_DRIVE}/backups` (kept `LOCAL_RETENTION_DAYS`)
- **Off-box backups** → `gdrive:PALIMPSEST/backups` (kept `REMOTE_RETENTION_DAYS`)
- **Schedule** → `config/sources.yaml` (per-source frequency) → `core/scheduler.py`
