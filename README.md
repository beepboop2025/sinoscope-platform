# SinoScope Platform

SinoScope is a monorepo of open-source tools for analyzing China-linked public data
across financial markets, information flows, and illicit-drug supply chains. The apps
share an emphasis on public sources, documented methods, and plain-language output.

> Aggregate, public-data tools for awareness, education, and research only.

## Apps

| App | What it does | Stack |
|---|---|---|
| [`apps/dragonscope`](apps/dragonscope) | China financial-market analytics dashboard (35 panels, in-browser SQL, ML signals) | React · Vite |
| [`apps/drug-observatory`](apps/drug-observatory) | Illicit-drug street prices + precursor flows, China/Myanmar focus, plain-English explainers | React · Vite · TypeScript |
| [`apps/social-scraper`](apps/social-scraper) | Multi-source public-data collection and analysis | Python |

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

Each app is self-contained. It keeps its own `package.json` and build, so you
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
