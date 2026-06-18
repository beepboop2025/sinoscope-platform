# Social Scraper — Daily Source Health Report
**Date:** 2026-04-09

---

## STRUCTURED DATA COLLECTORS

### Indian Economy
🟢 **RBI Website** — Accessible. Updated April 8, 2026. Exchange rates, monetary policy statements current.
🔴 **RBI DBIE** — TLS certificate error on `dbie.rbi.org.in` (ERR_TLS_CERT_ALTNAME_INVALID). New domain `data.rbi.org.in/DBIE/` loads an Angular SPA but blocks automation (right-click disabled, F12 blocked). **Config still uses old URL. STILL UNFIXED from March 23 report.**
🟡 **NSE India** — Timeout on fetch (aggressive anti-bot). Likely operational but requires browser-level scraping.
🟢 **BSE India** — Accessible. Corporate announcements, market data, IPO, derivatives sections present. Angular SPA with dynamic content.
🟢 **CCIL** — Accessible. MIBOR, TREPS, CP/CD rates sections present. FBIL reference rates not on homepage (may require subpage navigation). Sovereign yield curve available as "ZCYC" under Value Added section.
🟢 **SEBI** — Accessible. Department directory and recent materials visible. Latest content dated late 2025/early 2026.
🔴 **data.gov.in** — **403 Forbidden**. API access blocked. No specific deprecation notice found, but access is currently denied.

### US & International
🟡 **FRED** — Homepage returned 403 (bot blocking), but API itself likely operational. No deprecation notices for FRED API v1. No v1 sunset date yet.
🟢 **World Bank API** — Working. Returns valid JSON. Latest India GDP entry: 2025 (value null — expected annual lag).
🟡 **IMF Data** — 403 on `data.imf.org` homepage. Legacy portal retired Nov 5, 2025. New portal may block automated access. IFS/DOT/BOP datasets available through Data Explorer.

---

## NEWS & RSS FEEDS

🟢 **Federal Reserve Press RSS** — Valid XML, latest entry April 8, 2026 (FOMC Minutes from March 17-18)
🟢 **arXiv q-fin RSS** — Valid XML, 18 papers, latest April 8, 2026
🟢 **CNBC RSS** — Likely operational (was fine on March 24)
🟢 **CoinDesk RSS** — Likely operational
🟢 **ECB Press RSS** — Likely operational
🔴 **Reuters RSS** — Dead since 2020. `feeds.reuters.com` unreachable. **STILL UNFIXED from March 24 report.**
🟡 **Economic Times / Livemint / Moneycontrol RSS** — Bot-blocked on fetch. Scraper needs proper headers/cookies.
🟡 **Financial Times RSS** — Paywalled. Manual verification needed.
🟢 **RBI Press RSS** — RBI website accessible, press releases current.

---

## SOCIAL SCRAPERS

🟡 **Reddit** — API approval significantly harder since Jan 2026. Rate limits: 60 req/min with OAuth, 10 without. Free tier capped at 100 QPM. Anti-AI/scraping terms tightened.
🟢 **Hacker News** — Fully operational. Firebase API returns valid JSON. Website accessible.
🟡 **YouTube** — Data API v3 stable, no full deprecation. Deprecated: `relatedToVideoId`, `commentThreads.update`, `comments.markAsSpam`. Verify queries.
🟡 **GitHub** — REST API v2026-03-10 released with breaking changes: `merge_commit_sha` removed from PRs, singular `assignee` removed. Old v2022-11-28 supported 24+ months. Security org fields deprecated April 21, 2026.
🔴 **SEC EDGAR** — `cgi-bin/browse-edgar` still 403. `data.sec.gov` submissions endpoint also 403. **Persistent issue since March 24. Scraper is broken.**
🟡 **Discord** — PIN_MESSAGES permission split effective Feb 23. E2EE (DAVE) required for voice since March 1. Verify bot compliance.
🟡 **Mastodon** — Operational. Transitioning to European non-profit structure.
🟡 **Twitter/X** — Official API $42K+/year. Pay-per-use beta from Nov 2025. $15K liquidated damages clause for >1M posts/day unauthorized scraping. High-risk for scraping approaches.
🟡 **Dark Web/Tor** — Not verifiable remotely. Manual check needed.

---

## MESSAGING CHANNELS

🟡 **Telegram** — Not verifiable via fetch. Manual check recommended.
🟡 **Twitter/X** — See above. Cookie-based scraping increasingly fragile.

---

## CONNECTORS

🟡 **DragonScope** — Internal API, not publicly reachable. Manual verification needed.
🟡 **LiquiFi** — Internal API, not publicly reachable. Manual verification needed.

---

## IMMEDIATE ACTION NEEDED

1. **🔴 RBI DBIE (PERSISTENT — unfixed since March 23)**
   - TLS cert invalid on old URL, new portal blocks automation
   - Files to update:
     - `~/social_scraper/config/sources.yaml:8` — change `base_url` to `https://data.rbi.org.in/DBIE`
     - `~/social_scraper/collectors/rbi_dbie.py:22` — update `BASE_URL`
     - `~/social_scraper/run_collectors.py:58` — update hardcoded URL
     - `~/social_scraper/monitoring/health/source_health_checker.py:99,542` — update check URLs
     - `~/social_scraper/monitoring/health/structure_validator.py:198` — update validation URL
     - `~/social_scraper/monitoring/health/baselines/rbi_dbie.json:2` — update baseline URL
   - **WARNING**: New portal is Angular SPA with anti-automation. Collector may need Playwright/Selenium or API reverse-engineering.

2. **🔴 SEC EDGAR (PERSISTENT — unfixed since March 24)**
   - Both `cgi-bin/browse-edgar` AND `data.sec.gov` returning 403
   - Files: `~/social_scraper/scrapers/sec_scraper.py:53,140`
   - Fix: Set User-Agent to `"CompanyName admin@email.com"` per SEC requirements. Migrate to `efts.sec.gov/LATEST/` or `data.sec.gov` with proper headers.

3. **🔴 data.gov.in — NEW BREAKAGE**
   - API returning 403 Forbidden (was working on March 24)
   - File: `~/social_scraper/collectors/data_gov_in.py`
   - Check if API key is still valid. May need re-registration or new auth mechanism.

4. **🔴 Reuters RSS (PERSISTENT — unfixed since March 24)**
   - `feeds.reuters.com` completely unreachable
   - File: `~/social_scraper/config/sources.yaml:127-130` — remove or replace reuters feeds
   - Options: third-party RSS generator, direct scraping, or commercial Reuters API

## WATCH LIST

- **FRED API** — Homepage 403 (bot blocking), API key-based access likely still fine. Monitor.
- **IMF Data** — New portal may require updated access patterns. Check `~/social_scraper/collectors/imf_data.py`.
- **Reddit** — Approval harder since Jan 2026. If tokens expire, re-approval may fail.
- **GitHub API** — v2026-03-10 breaking changes. Org security fields deprecated April 21. Plan migration.
- **Discord** — Permission splits and E2EE changes. Verify bot in `~/social_scraper/scrapers/discord_scraper.py`.
- **Twitter/X** — $15K damages clause for unauthorized bulk access. Reassess legal risk.
- **NSE / ET / Livemint / Moneycontrol** — Persistent bot blocking. Need browser-level scraping.

## CONNECTOR STATUS

- **DragonScope**: Cannot verify externally — internal network check required
- **LiquiFi**: Cannot verify externally — internal network check required

## NEW OPPORTUNITIES

- **RBI CIMS Integration**: RBI's new Centralised Information Management System (CIMS) launched with DBIE — may offer more structured API access than the old portal
- **SEC EDGAR API Toolkit**: `api.edgarfiling.sec.gov` development toolkit available as modern REST replacement for legacy CGI
- **GitHub REST API v2026-03-10**: New features alongside breaking changes — review for useful additions
- **FRED API v2**: Bulk observation downloads for all series in a release — significant speed improvement for US macro data collection
