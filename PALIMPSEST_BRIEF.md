# PALIMPSEST-II / DDTI — Project Brief (for Kimi)

You are collaborating with Claude Code on this app. Here's what it is and where you can help.

## What the app is
A **latent-state China-intelligence engine** built as an extension of `social_scraper`
(a Python collector → processor → API platform). It treats "what's really happening in
China" as a hidden state estimated from many biased sensors. The flagship module is the
**DDTI (Deletion-Differential Threat Index)**: *treat the censor as a sensor* — what the
regime deletes, how fast, and how selectively reveals what it fears.

## Architecture (existing patterns — match them)
- **Collectors** (`collectors/*.py`, subclass `core.base_collector.BaseCollector`):
  `collect() → parse() → validate()`. Registered in `config/sources.yaml`, scheduled by Celery Beat.
- **Processors** (`processors/*.py`, subclass `core.base_processor.BaseProcessor`): NLP/aggregation over collected Articles.
- **Storage**: Postgres (`storage/models.py`), Redis (live cache), disk (`data/`).
- **API**: FastAPI (`api/main.py`, routes in `api/routes/`).
- **Free LLM**: `free_llm_router` is wired for translation/synthesis.

## DDTI pieces already built
- `collectors/ddti_probe.py` — pulls China Digital Times deletion feeds.
- `processors/ddti_index.py` — `compute_selectivity_novelty()` ranks censored terms by
  **threat = attention (time-decayed frequency) × novelty (burst / first-appearance)**.
  `extract_terms()` pulls quoted spans + an English gazetteer + the Chinese finance lexicon + tags.
- `processors/zh_finance.py` + `config/zh_finance_lexicon.json` — Chinese finance/policy lexicon (you built this earlier) + negation-aware hawkish/dovish/sector detection.
- `dashboards/ddti_dashboard.html` — "Redacted Intelligence Terminal" UI.
- `scripts/ddti_live_pull.py` — pulls real CDT data, stores a disk time-series.

## Current constraint (why your help matters)
From normal egress only CDT's English root feed is reachable; the richer **Chinese**
deletion feeds (CDT Chinese, Weibo, FreeWeibo) are Cloudflare-blocked and await a proxy.
When that proxy lands, the pipeline will ingest **Chinese** censored text — and our term
extraction has no Chinese *censorship* vocabulary yet (only finance terms + English entities).

## Where you (Kimi) can help — Chinese-language layers
1. **Chinese censorship / sensitive-terms gazetteer** (most valuable now) — euphemisms and
   deletion-trigger phrases that evade filters: June-4 euphemisms (八平方, 占中…), leadership
   euphemisms, protest/dissent slang, economic-distress slang, 润学/emigration, censorship-meta.
2. Mapping CDT English topic tags ↔ canonical Chinese threat categories.
3. Reviewing Chinese sentiment edge cases (negation, sarcasm) in `processors/zh_finance.py`.

Output structured data (JSON) Claude will review and integrate. Claude owns the code/architecture;
you own the Chinese-language knowledge. Do not endanger sources — public/aggregated terms only.
