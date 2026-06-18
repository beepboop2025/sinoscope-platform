# Deployment — choose your path when you ship

Nothing here is active by default. The app runs exactly as before until you
**pick one** of these paths. Each is self-contained and opt-in:

- The R2 object store is dormant (`USE_MINIO=false` → local filesystem).
- The AI cascade (`core/ai_complete.py`) isn't imported anywhere until you wire it.
- The production overlay is a separate file; your base `docker-compose.yml` is unchanged.

So you can ship locally today and choose a real deployment later without rework.

---

## Pick by your main constraint

| If you care most about… | Choose | Cost/mo | Real-time? | Status |
|---|---|---|---|---|
| **Zero budget, no servers** | Free serverless (GitHub Actions + Neon + Pages) | **$0** | scheduled, not live | 🔧 blueprint — ask to generate workflows |
| **Free *and* always-on full stack** | Oracle "Always Free" VM | **$0** | ✅ live | ✅ ready (use the VPS guide on an Oracle box) |
| **Shipping fast, no ops, browser-only** | Railway (managed PaaS) | ~$5–25 | ✅ live | ✅ ready |
| **Full control, cheapest always-on** | Self-managed VPS (Hetzner/DO) | ~$6–30 | ✅ live | ✅ ready |
| **Heavy data (100 GB–1 TB+/mo) + your own AI agent** | Heavy path (R2 + AI cascade) | ~$15–105 | ✅ live | ✅ ready |

## The paths

### 1. Free serverless — `$0`, no server  🔧 *blueprint*
Collectors run as **GitHub Actions cron** (free/unlimited on public repos), data
in **Neon** free Postgres, the PALIMPSEST dashboard published static to **GitHub
Pages**, backups to Google Drive. Best for: a live demo or periodic indices at
zero cost. Trade-off: scheduled, not continuously-listening.
**Status:** designed but the workflow files aren't generated yet — ask and I'll
add `.github/workflows/` + the snapshot injector.

### 2. Oracle "Always Free" VM — `$0`, always-on  ✅
A forever-free ARM VM (4 CPU / 24 GB / 200 GB) runs the **full** Docker stack
24/7 — even a local Ollama model for the AI agent. Follow the VPS guide below,
just on an Oracle box. Trade-off: card-to-verify signup, ARM capacity varies, you
admin a VM. **Guide:** [`DEPLOY.md`](DEPLOY.md).

### 3. Railway — managed, browser-only  ✅
Deploy every service from GitHub in the Railway dashboard; managed Postgres +
Redis; nightly Google Drive backups; nothing on your machine. Core 6 services
(~$10–15/mo) scale to the full stack.
**Guide:** [`railway/DEPLOY_RAILWAY.md`](railway/DEPLOY_RAILWAY.md) · configs in [`railway/`](railway/).

### 4. Self-managed VPS — full control  ✅
The full compose stack on your own box with data on an attached disk, `restart:
unless-stopped`, systemd boot survival, ports closed to localhost, nightly Google
Drive backups via rclone.
**Guide:** [`DEPLOY.md`](DEPLOY.md) · overlay [`docker-compose.prod.yml`](docker-compose.prod.yml).

### 5. Heavy data + your own AI agent  ✅
For 100 GB–1 TB+/mo: structured data in **Postgres**, heavy raw blobs in
**Cloudflare R2** (`$0` egress, lifecycle rules cap cost), analyzed by the
free→local→paid cascade (`core/ai_complete.py`: free-LLM router → Ollama →
Claude). Real cost math inside.
**Guide:** [`DEPLOY_HEAVY.md`](DEPLOY_HEAVY.md).

---

## These compose, not compete

The paths share building blocks — you can mix them as the product grows:

- **Start** free serverless or Railway → **graduate** to a VPS when you need
  always-on control → **add** the heavy R2 + AI layer when data scales. The R2
  store and AI cascade work under *any* of the always-on paths (Oracle, Railway,
  VPS), not just the heavy one.
- Backups (Google Drive via rclone) and the AI cascade are independent toggles
  you can switch on under any path.

## What activates what (opt-in switches)

| Capability | Turn on with | Off by default |
|---|---|---|
| Object store → Cloudflare R2/S3 | `USE_MINIO=true` + R2 vars | ✅ (filesystem) |
| Your AI agent cascade | call `core.ai_complete.ai_complete(...)` + set `AI_CASCADE` | ✅ (unused) |
| Paid AI fallback | `ANTHROPIC_API_KEY` + `AI_CLAUDE_MODEL` | ✅ (free tiers only) |
| Local AI (Ollama) | add the `ollama` service + `OLLAMA_URL` | ✅ |
| Production restart/volumes | `-f deploy/docker-compose.prod.yml` | ✅ (base compose) |
| Google Drive backups | `RCLONE_REMOTE` (+ rclone config) | ✅ (local only) |

See [`../.env.example`](../.env.example) for every switch.
