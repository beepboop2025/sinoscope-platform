# Heavy data + your own AI agent, 24/7

For **100 GB–1 TB+/month** of collection, continuous analysis by your own AI
agent, and durable storage. This is the "real infrastructure" path — it needs a
persistent box plus object storage. Here's exactly where data lives, how the AI
agent runs, and what it costs.

---

## Architecture

```
  collectors (24/7, Celery beat+workers)
        │
        ├──► structured records ──►  Postgres        (indices, metadata, parsed rows)
        │                            on the box / managed
        │
        └──► heavy raw blobs    ──►  Cloudflare R2    (HTML, PDFs, media, full dumps)
                                     S3-compatible, $0 egress
        ▼
  AI agent  (core/ai_complete.py cascade: free router → local Ollama → paid Claude)
        │   reads fresh records + raw blobs, writes analysis back to Postgres
        ▼
  dashboards / digests / Telegram alerts
```

**Two stores, by data kind** — the single most important decision:

| Data | Where | Why |
|---|---|---|
| Structured / queryable (indices, parsed records, AI analysis output) | **Postgres** | needs SQL, joins, pgvector search; small relative to raw |
| Heavy raw blobs (the 100 GB–1 TB+) | **Cloudflare R2** | object storage, **$0.015/GB-mo, zero egress**, scales infinitely |

Your code already supports this: `storage/raw_store.py` writes to any
S3-compatible store. Set `USE_MINIO=true` + the R2 vars (below) and raw payloads
stream to R2 instead of local disk — no code change.

---

## 1. Object storage — Cloudflare R2 (browser, ~5 min)

1. **dash.cloudflare.com → R2 → Create bucket** → name `palimpsest-raw`.
2. **R2 → Manage API Tokens → Create** (Object Read & Write). Note the
   **Access Key ID**, **Secret**, and your **account ID**.
3. Put these in `.env` (already scaffolded in `.env.example`):
   ```ini
   USE_MINIO=true
   MINIO_ENDPOINT=<account_id>.r2.cloudflarestorage.com
   MINIO_ACCESS_KEY=<access_key_id>
   MINIO_SECRET_KEY=<secret>
   MINIO_BUCKET=palimpsest-raw
   MINIO_SECURE=true
   MINIO_REGION=auto
   ```
4. **Cost control = lifecycle rules.** In R2 → bucket → Settings → Object
   lifecycle, add a rule to **expire raw objects after N days** (e.g. 90). Raw is
   for reprocessing; the *derived* analysis lives in Postgres forever. This caps
   storage cost no matter how heavy ingestion gets (see cost math below).

> Alternatives with the same vars: Backblaze B2, AWS S3, Wasabi. R2 wins on
> $0 egress — critical when your AI agent re-reads raw blobs repeatedly.

## 2. Your AI agent — free → local → paid cascade

`core/ai_complete.py` gives every processor (and your own agent) one call with a
three-tier "free now, paid if needed" policy:

```python
from core.ai_complete import ai_complete
analysis = ai_complete(context_prompt, task_type="briefing", max_tokens=1024)
```

Order is set by `AI_CASCADE` (default `router,ollama,claude`):

1. **router** — `free_llm_router` (free-tier failover, $0). Already wired in.
2. **ollama** — local model on the box ($0 API, private). Set `OLLAMA_URL`.
3. **claude** — paid fallback, only when the free tiers fail. `ANTHROPIC_API_KEY`
   + `AI_CLAUDE_MODEL` (default Haiku — cheap).

So the bulk of analysis runs free/local; Claude only catches the overflow. To run
Ollama on the box, add it to the stack (it has an ARM/amd64 image):

```yaml
# add to deploy/docker-compose.prod.yml
  ollama:
    image: ollama/ollama:latest
    volumes: [ "${DATA_DRIVE:-/mnt/data}/ollama:/root/.ollama" ]
    restart: unless-stopped
# then set OLLAMA_URL=http://ollama:11434 on the worker, and once up:
#   docker compose exec ollama ollama pull llama3
```

## 3. Compute — pick the box

| Option | Specs | Monthly | Notes |
|---|---|---|---|
| **Oracle Always Free** | 4 ARM CPU / 24 GB / 200 GB | **$0** | runs full stack + Ollama; raw → R2 (box disk too small for 1 TB+). Card-to-verify, ARM capacity varies. |
| **Hetzner CPX41** | 8 vCPU / 16 GB / 240 GB | **~€30** | comfortable for heavy scraping + local AI; simplest. |
| **Hetzner + managed PG** | + Neon/Supabase paid | +$20–25 | if you'd rather not run Postgres yourself. |

Deploy with the compose stack + systemd already in this repo —
**[`deploy/DEPLOY.md`](DEPLOY.md)** (VPS) covers disk mount, boot survival, and
backups. The only change for heavy mode is the R2 + AI env above; Postgres,
Redis, beat, workers are unchanged. (At 1 TB+/month the box disk holds only
Postgres + the working set — **all bulk raw goes to R2**, so a 200 GB box is fine.)

---

## How much — real cost math for your scale (100 GB–1 TB+/mo)

Storage is the lever, and it depends on **retention**, not just ingestion:

| Ingest | Retention (R2 lifecycle) | Peak stored | R2 storage/mo |
|---|---|---|---|
| 100 GB/mo | 6 months | ~600 GB | **~$9** |
| 1 TB/mo | 3 months | ~3 TB | **~$45** |
| 1 TB/mo | 12 months | ~12 TB | ~$180 |
| 1 TB/mo | 30 days | ~1 TB | **~$15** |

Plus: R2 write ops ~$4.50/million objects (modest); **R2 egress = $0**.

**Realistic monthly totals:**

| Setup | Compute | Storage (R2, 3-mo retention) | AI | **Total** |
|---|---|---|---|---|
| **Frugal** | Oracle Free $0 | ~$15–45 | router+Ollama $0 | **~$15–45** |
| **Reliable** | Hetzner CPX41 ~$30 | ~$15–45 | Haiku fallback ~$10–30 | **~$55–105** |

The cost is **dominated by how much raw you keep**, not compute or AI — because
the cascade keeps AI mostly free/local and R2 has no egress fees. Set an R2
lifecycle rule and the bill is predictable regardless of how hard you scrape.

---

## Summary

- **Where the data lives:** structured → **Postgres**; heavy raw → **Cloudflare R2** (with a lifecycle rule to cap cost).
- **Your AI agent:** `core/ai_complete.py` — free `free_llm_router` / local Ollama by default, paid Claude only as fallback.
- **24/7:** the existing compose + systemd stack on an Oracle Free or Hetzner box.
- **Cost:** ~**$15–45/mo** frugal (Oracle + R2 + free/local AI), ~**$55–105/mo** reliable (Hetzner + R2 + Haiku). Driven by raw retention.
