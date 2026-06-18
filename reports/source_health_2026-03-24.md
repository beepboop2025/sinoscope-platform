# Social Scraper — Daily Source Health Report
**Date:** 2026-03-24

---

## STRUCTURED DATA COLLECTORS

### Indian Economy
🟢 **RBI Website** — Accessible, exchange rates updated March 23, circulars current (March 2026)
🟡 **RBI DBIE** — Redirected to `data.rbi.org.in/DBIE/` (301 from old `dbie.rbi.org.in`). SPA loads dynamically — content not verifiable via static fetch but redirect has been in place since June 2024. Verify scraper uses new URL.
🟡 **NSE India** — Timeout on fetch (aggressive bot blocking). Site likely operational but scraper must handle anti-bot measures (cookies, headers, rate limits).
🟢 **BSE India** — Accessible. Corporate announcements, market data, IPO sections all present. Angular SPA with dynamic content loading.
🟢 **CCIL** — Accessible. Money Market, G-Sec, Forex, Derivatives sections present. Data loads dynamically via AJAX.
🟢 **SEBI** — Accessible. "What's New" section with recent announcements visible.
🟢 **data.gov.in** — Accessible (page loads). No specific API deprecation notices found for 2026.

### US & International
🟢 **FRED** — Accessible. No deprecation notices for v1 API.
🟡 **FRED API v2** — New API version launched Nov 2025 (bulk observations in JSON/XML). No v1 sunset date announced yet, but monitor for migration timeline.
🟢 **World Bank API** — Working. Returns valid JSON for India GDP indicator (latest data point: 2025, value null — expected lag for annual GDP).
🟢 **IMF Data** — Accessible. Home page reorganized with Data Explorer navigation. IFS/DOT/BOP may require navigating through Data Explorer rather than direct links.

---

## NEWS & RSS FEEDS

🟢 **CNBC RSS** — Valid RSS 2.0, 28 articles, last build March 23, 2026
🟢 **CoinDesk RSS** — Valid RSS 2.0, 27 items, last updated March 23, 2026
🟢 **arXiv q-fin RSS** — Valid XML, 18 recent papers (March 23, 2026)
🟢 **Federal Reserve Press RSS** — Valid XML, latest entry March 20 (FOMC statement March 18)
🟢 **ECB Press RSS** — Valid, last updated March 23, 2026
🔴 **Reuters RSS** — Feeds officially deprecated since June 2020. Some workarounds have stopped working as of March 2026. Needs third-party RSS generator or direct web scraping.
🟡 **Economic Times RSS** — Blocked by fetch tool (bot protection). Verify scraper has proper headers/cookies.
🟡 **Livemint RSS** — Blocked by fetch tool. Same concern as ET.
🟡 **Moneycontrol RSS** — Blocked by fetch tool. Same concern.
🟡 **Financial Times RSS** — Not checked (typically paywalled). Verify subscription-based access still works.
🟢 **RBI Press RSS** — RBI website accessible, press releases current.

---

## SOCIAL SCRAPERS

🟡 **Reddit** — Blocked by fetch tool (bot protection). API access significantly tightened in 2026: approval harder to get since Jan 2026, free tier limited to 100 QPM, paid at $0.24/1K calls. Verify OAuth tokens and rate limits.
🟢 **Hacker News** — API fully operational. Firebase API returns valid JSON. Website accessible with current stories.
🟡 **YouTube** — Data API v3 still current, no full deprecation planned. Some features deprecated: `relatedToVideoId`, `commentThreads.update`, `comments.markAsSpam`. Verify your queries don't use deprecated endpoints.
🟢 **Mastodon** — Platform operational. Transitioning to European non-profit structure with new paid hosting model. Federation still functioning.
🟡 **GitHub** — New REST API version 2026-03-10 released. Breaking changes include: removed `merge_commit_sha` from PR responses, removed singular `assignee` field, changed workflow dispatch response. Old version 2022-11-28 still supported 24+ months. Verify API version header in scraper.
🔴 **SEC EDGAR** — `cgi-bin/browse-edgar` returned **403 Forbidden**. EFTS search also returned 403. EDGAR Next migration ongoing with beta environment. Forms 3/4/5 changes effective March 18, 2026. **Check if scraper needs updated User-Agent or new API endpoints.**
🟡 **Discord** — Permission changes Feb 23, 2026 (PIN_MESSAGES split). Voice API requires E2EE (DAVE) support since March 1. Verify bot permissions and DAVE compliance.
🟡 **Dark Web/Tor** — Not directly verifiable. Manual check recommended.
🟡 **Twitter/X** — Official API starts at $42K/year. Pay-per-use beta launched Nov 2025. Scraping landscape shifted to specialized proxy services. Verify current access method still functional.

---

## MESSAGING CHANNELS

🟡 **Telegram** — Not directly verifiable via fetch tool. Manual check recommended for channel activity.
🟡 **Twitter/X** — See above. Query-based scraping increasingly difficult.

---

## CONNECTORS

🟡 **DragonScope** — Not reachable via public web (likely internal API). Manual verification needed.
🟡 **LiquiFi** — Not reachable via public web (likely internal API). Manual verification needed.

---

## IMMEDIATE ACTION NEEDED

1. **🔴 SEC EDGAR** — Both `cgi-bin/browse-edgar` and EFTS returned 403. The SEC has been migrating to EDGAR Next with new API endpoints. Check `~/social_scraper/scrapers/sec_edgar/` — update User-Agent to comply with SEC requirements (`User-Agent: CompanyName admin@email.com`). Consider migrating to `api.edgarfiling.sec.gov` or `data.sec.gov` endpoints.

2. **🔴 Reuters RSS** — Officially dead since 2020, workarounds failing. In `~/social_scraper/config/sources.yaml`, either:
   - Replace with a third-party RSS generator service (e.g., rss.app)
   - Switch to direct web scraping of reuters.com
   - Use Reuters API if you have a commercial license

## WATCH LIST

- **FRED API v2** — Monitor for v1 sunset announcement. Consider proactive migration.
- **Reddit API** — Tighter approvals since Jan 2026. If scraper breaks, may need to re-apply or switch to paid tier.
- **GitHub API** — New version 2026-03-10 has breaking changes. Current version safe for 24+ months but plan migration.
- **Discord** — E2EE (DAVE) requirement for voice since March 1. Permission splits may affect bot.
- **NSE India / ET / Livemint / Moneycontrol** — Aggressive bot blocking detected. Ensure scrapers use proper browser headers, cookie management, and rate limiting.
- **SEC EDGAR** — Forms 3/4/5 schema changes effective March 18, 2026 (new Country and Foreign Trading Symbol fields). Update parsers if scraping insider trading data.
- **Twitter/X** — Monitor pay-per-use beta pricing. Current scraping approach may need periodic refreshing.

## CONNECTOR STATUS

- **DragonScope**: Unable to verify externally — requires internal network check
- **LiquiFi**: Unable to verify externally — requires internal network check

## NEW OPPORTUNITIES

- **FRED API v2**: Bulk observation downloads for all series in a release — could significantly speed up US macro data collection
- **SEC EDGAR API Toolkit**: New `api.edgarfiling.sec.gov` development toolkit available — modern REST API replacing legacy CGI interface
- **Mastodon Paid Hosting**: Mastodon offering enterprise services — could provide more reliable access for financial community monitoring
- **arXiv q-fin**: Strong signal source — 18 papers today including LLM-based stock prediction and Indian market survivorship bias studies
