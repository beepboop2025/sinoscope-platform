# 🛰️ Sinoscope Platform

A family of open-source tools for making **China-linked data legible** — markets,
information flows, and the illicit drug-trade supply chain. Each app is built on
shared principles (public data, transparent methods, plain-language output) and
lives in this monorepo so they evolve as one platform rather than scattered repos.

> Aggregate, public-data tools for awareness, education, and research only.

## Apps

| App | What it does | Stack |
|---|---|---|
| [`apps/dragonscope`](apps/dragonscope) | China financial-market analytics dashboard (35 panels, in-browser SQL, ML signals) | React · Vite |
| [`apps/drug-observatory`](apps/drug-observatory) | Illicit-drug street prices + precursor flows, China/Myanmar focus, plain-English explainers | React · Vite · TypeScript |
| [`apps/social-scraper`](apps/social-scraper) | Multi-source intelligence platform incl. the China latent-state intel engine | Python |

## Layout

```
sinoscope-platform/
  apps/
    dragonscope/        # React/TS market analytics
    drug-observatory/   # React/TS drug-trade explorer
    social-scraper/     # Python intelligence platform
  packages/             # shared code (reserved; e.g. free-llm-router)
  pnpm-workspace.yaml
```

Each app is **self-contained** — it keeps its own `package.json` / build, so you
can work on one without installing the others. The workspace config is opt-in for
when you want shared tooling.

## Working on an app

```bash
cd apps/drug-observatory && npm install && npm run dev
cd apps/dragonscope      && npm install && npm run dev
cd apps/social-scraper   && pip install -r requirements.txt   # see app README
```

## History

Each app was developed in its own repository; their full commit history is
preserved here via `git subtree`. The original standalone repos remain as archives.
