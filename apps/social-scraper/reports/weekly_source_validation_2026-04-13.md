# Weekly Deep Source Validation Report
**Date:** 2026-04-13 (Sunday)
**System:** social_scraper (econscraper)

---

## EXECUTIVE SUMMARY

**25 sources checked | 7 BROKEN | 6 DEGRADED | 12 HEALTHY**

### URGENT: Regulatory & Compliance Changes
- **NSE Static IP Mandate (April 1, 2026)** - All algo trading API keys without static IP binding have expired. Any automated data collection connected to NSE needs static IP compliance verification immediately.
- **RBI Data Protection Advisory (April 2026)** - New advisory directing all regulated entities (including NBFCs) to prioritize customer data protection and API security. Mandatory compliance.
- **RBI Digital Payment Authentication Framework (April 1, 2026)** - Risk-based authentication replacing SMS OTP-only approaches. Affects payment processing.
- **X/Twitter API now pay-per-use** - No free tier for new developers. $0.005/post read, $0.010/user profile. Budget impact for sentiment scraping.

### Critical Issues Requiring Immediate Action
1. **Reuters RSS feeds** - DEAD — `feeds.reuters.com` DNS no longer resolves. Replace URLs.
2. **FBIL/CCIL rates** - `fbil.org.in` returning ECONNREFUSED. Migrate to `ccilindia.com`. Critical for LiquiFi.
3. **Mastodon public timeline** - Now returns 422 without auth. Scraper needs token.
4. **RBI DBIE** - TLS cert broken on `dbie.rbi.org.in`. Portal migrated to `data.rbi.org.in` (SPA).
5. **data.gov.in** - All endpoints returning 403/404. API may be retired or migrated.
6. **IMF SDMX API** - `dataservices.imf.org` completely unreachable (TCP timeout). Portal rebuilt as Next.js app. API likely decommissioned.
7. **Moneycontrol RSS** - Feed FROZEN since April 2024. Serving stale cached data. Find new URL.

### Warnings (Degraded but Functional)
7. **SEC EDGAR EFTS** - 403 without proper User-Agent. Scraper has placeholder email.
8. **World Bank API** - Intermittent timeouts (slow/overloaded).
9. **ET Economy + ECB Press RSS** - Missing `<description>` tags in items. Parser needs fallback.
10. **RBI Press RSS** - Configured URL is HTML page, not RSS feed. Needs HTML scraper or new URL.
11. **arXiv q-fin RSS** - Empty on weekends by design (academic publishing schedule, not a bug).

---

## STRUCTURED DATA COLLECTORS

### 1. RBI DBIE (collectors/rbi_dbie.py)
- **ENDPOINT STATUS:** **DEGRADED** - `dbie.rbi.org.in` has **TLS certificate mismatch** (ERR_TLS_CERT_ALTNAME_INVALID). Portal appears to have migrated to `data.rbi.org.in`.
- **STRUCTURE:** **CHANGED** - New URL `data.rbi.org.in` is a heavy SPA (MapMyIndia API, Material Design) — no server-side data, requires headless browser (Playwright/Puppeteer) or discovery of underlying API endpoints.
- **AUTH REQUIREMENTS:** UNCHANGED - No login wall, but SPA architecture blocks simple HTTP scraping.
- **RECOMMENDATION:** Update BASE_URL to `data.rbi.org.in`. Fallback scraping of `PublicationsView.aspx` on `rbi.org.in` still works and is the most reliable path. Investigate `data.rbi.org.in` XHR endpoints for direct API access.
- **FILE TO EDIT:** collectors/rbi_dbie.py (update BASE_URL; optionally add headless browser support)

### 2. RBI Circulars (collectors/rbi_circulars.py)
- **ENDPOINT STATUS:** UP - rbi.org.in accessible
- **STRUCTURE:** UNCHANGED - Press releases, notifications, circulars pages accessible
- **AUTH REQUIREMENTS:** UNCHANGED
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

### 3. NSE Bhavcopy (collectors/nse_bhavcopy.py)
- **ENDPOINT STATUS:** UP (with anti-bot measures)
- **STRUCTURE:** UNCHANGED - API endpoints respond after cookie prefetch
- **AUTH REQUIREMENTS:** UNCHANGED - Session cookies from homepage required
- **NEW FEATURES:** None detected
- **⚠️ NSE STATIC IP MANDATE (April 1, 2026):** All algo trading API keys without static IP binding have expired. IPv4 only (no IPv6), max 2 IPs (primary+secondary), must be registered with broker. Verify data collection server IPs are compliant.
- **RECOMMENDATION:** **VERIFY** static IP compliance for production server. Cookie prefetch pattern still works for data scraping, but any order/algo API integration is affected.
- **FILE TO EDIT:** collectors/nse_bhavcopy.py (verify; may need config for static IP)

### 4. BSE API (collectors/bse_api.py)
- **ENDPOINT STATUS:** SLOW - api.bseindia.com times out intermittently
- **STRUCTURE:** UNCHANGED - API endpoint patterns unchanged
- **AUTH REQUIREMENTS:** UNCHANGED - Referer header still required
- **RECOMMENDATION:** Consider adding retry with backoff for timeout resilience
- **FILE TO EDIT:** collectors/bse_api.py (optional improvement)

### 5. CCIL/FBIL Rates (collectors/ccil_rates.py)
- **ENDPOINT STATUS:** **SPLIT** - `ccilindia.com` is UP (ZCYC rates, MIBOR-OIS, bond/forex/derivatives data under Data & Statistics). `fbil.org.in` is **DOWN** (ECONNREFUSED confirmed). FBIL sub-pages on CCIL also timed out.
- **STRUCTURE:** CCIL has yield curve data, MIBOR data, government securities, forex data accessible from its Data & Statistics section. FBIL reference rates (MIBOR benchmarks, TREPS) are NOT directly on CCIL homepage — FBIL is a separate entity whose domain is down.
- **AUTH REQUIREMENTS:** CCIL public content accessible without auth. Sign-in exists for member portal.
- **RECOMMENDATION:** **MIGRATE** collector to source MIBOR/ZCYC data from `ccilindia.com/web/ccil/` Data & Statistics pages instead of `fbil.org.in`. Critical for LiquiFi connector (MIBOR, TREPS, yield curve, CP/CD rates).
- **FILE TO EDIT:** collectors/ccil_rates.py (replace FBIL_URL with CCIL data pages; add CCIL ZCYC endpoint)

### 6. FRED API (collectors/fred_api.py)
- **ENDPOINT STATUS:** UP - API responds correctly with valid API key
- **STRUCTURE:** UNCHANGED - JSON response format stable
- **AUTH REQUIREMENTS:** UNCHANGED - API key required (DEMO_KEY returns 403 as expected)
- **NEW FEATURES:** **FRED API v2 (Nov 2025)** - Bulk retrieval of observations for all series in any release with full history in JSON/XML. ALFRED archival content no longer saveable (Jan 5, 2026).
- **RECOMMENDATION:** **UPGRADE** to FRED API v2 bulk retrieval for efficient macro data pulls (FEDFUNDS, DGS10, SOFR, etc.). Significant efficiency gain for treasury analysis.
- **FILE TO EDIT:** collectors/fred_api.py (add v2 bulk retrieval endpoint support)

### 7. SEBI Circulars (collectors/sebi_circulars.py)
- **ENDPOINT STATUS:** UP (partially) - Homepage and Enforcement section load. **Circulars-specific listing page times out repeatedly.**
- **STRUCTURE:** UNCHANGED - URL pattern `HomeAction.do?doListing=yes&sid=[section]&ssid=[subsection]`. Confirmed: sid=1 (Legal Framework), sid=2 (Enforcement, 54K+ records, 25/page pagination). Legal document pattern: `/legal/[type]/[month-year]/[title]_[id].html`.
- **AUTH REQUIREMENTS:** UNCHANGED - Public documents accessible. SI Portal requires login.
- **RECOMMENDATION:** Increase HTTP timeout to 90s+. Add retry logic specifically for circulars listing. Consider scraping from the Legal Framework section (sid=1) as an alternative path.
- **FILE TO EDIT:** collectors/sebi_circulars.py (timeout 90s, retry logic)

### 8. data.gov.in (collectors/data_gov_in.py)
- **ENDPOINT STATUS:** **DOWN/BLOCKED** - All endpoints returning 403 Forbidden or 404. Main domain, catalog page, search page, and API subdomain (`api.data.gov.in`) all reject non-browser requests.
- **STRUCTURE:** UNKNOWN - Cannot verify; API subdomain returns 404 suggesting possible API restructuring or retirement.
- **AUTH REQUIREMENTS:** Cannot be determined. Historically required API key registration.
- **RECOMMENDATION:** **INVESTIGATE URGENTLY** - Test from server with browser-like headers. If still blocked, check if API has been restructured under new endpoints (e.g., `apisetu.gov.in`). May need to deprioritize or mark as broken.
- **FILE TO EDIT:** collectors/data_gov_in.py (headers + possible URL migration)

### 9. World Bank API (collectors/world_bank.py)
- **ENDPOINT STATUS:** DEGRADED - Intermittent timeouts (60s+)
- **STRUCTURE:** UNCHANGED when accessible - JSON format with paginated arrays
- **AUTH REQUIREMENTS:** UNCHANGED - No auth needed
- **RECOMMENDATION:** Increase timeout to 90s; add retry with exponential backoff
- **FILE TO EDIT:** collectors/world_bank.py (timeout/retry improvement)

### 10. IMF Data (collectors/imf_data.py)
- **ENDPOINT STATUS:** **DOWN** - `dataservices.imf.org` SDMX REST API is unreachable. DNS resolves (134.113.242.23) but TCP connection times out on port 443. Tested with 10s, 15s, 60s, 90s timeouts — all fail. Dataflow endpoint also dead.
- **STRUCTURE:** CANNOT VERIFY - No response received from any endpoint.
- **AUTH REQUIREMENTS:** Historically none. Cannot verify current state.
- **PORTAL:** `data.imf.org` is accessible (HTTP 200) but has been rebuilt as a **Next.js application** — suggesting platform migration. Old SDMX API may be decommissioned.
- **NOTE:** Collector uses HTTP (not HTTPS) for a now-dead endpoint — both issues need fixing.
- **RECOMMENDATION:** **INVESTIGATE NEW IMF API** - The old `dataservices.imf.org/REST/SDMX_JSON.svc/` path appears decommissioned. Check IMF developer docs for replacement API (likely under `data.imf.org` or new SDMX endpoint). This is a **breaking change**.
- **FILE TO EDIT:** collectors/imf_data.py (new BASE_URL needed — old endpoint is dead)

---

## RSS FEEDS (collectors/rss_feeds.py)

| # | Feed | Status | Items | Structure | Issue |
|---|------|--------|-------|-----------|-------|
| 1 | reuters_business | **BROKEN** | 0 | DNS dead | `feeds.reuters.com` no longer resolves. Dead since 2020. |
| 2 | reuters_markets | **BROKEN** | 0 | DNS dead | Same — entire domain is defunct |
| 3 | et_economy | UP | 49 | title, link, guid, pubDate | **Missing `<description>`** in items (only channel-level) |
| 4 | et_markets | UP | 50 | title, description, link, enclosure, guid, pubDate | Full structure with images |
| 5 | mint_economy | UP | 35 | title, description, link, guid, pubDate, media:content | Healthy (CDATA wrapping) |
| 6 | mint_markets | UP | 35 | title, description, link, guid, pubDate, media:content | Healthy |
| 7 | moneycontrol | **STALE** | 15 | title, description, link, guid, pubDate | **FROZEN since April 2024.** lastBuildDate=Aug 2024. ISO-8859-1 encoding. |
| 8 | rbi_press | **WARNING** | N/A | **HTML, not RSS** | ASPX page, not a feed. `/Scripts/rss.aspx` also HTML. Needs HTML scraper. |
| 9 | fed_press | UP | 20 | title, link, guid, description, category, pubDate | Excellent — includes `<category>` tags |
| 10 | ecb_press | UP | 15 | title, link, guid, pubDate | **Missing `<description>`** in items. Some links to PDFs. Double-slash URLs. |
| 11 | coindesk | UP | 25 | title, description, link, guid, pubDate, media:content, dc:creator, content:encoded | Healthy — rich feed, TTL=5min. (403 only from some tools) |
| 12 | cnbc | UP | 25 | title, description, link, guid, pubDate + custom metadata namespace | Healthy — TTL=60min |
| 13 | ft_markets | UP | 25 | title, description, link, guid, pubDate | Healthy — redirects to stream URL. TTL=15min. |
| 14 | arxiv_qfin | UP | 15 | title, description (abstract), link, guid, category, dc:creator, arxiv:announce_type | Healthy — **empty on weekends by design** (academic publishing schedule) |

### RSS Feed Actions Required:
- **REPLACE** reuters_business and reuters_markets URLs — domain `feeds.reuters.com` is completely dead (DNS failure)
- **FIX** moneycontrol feed — frozen since April 2024, serving stale cached data. Find new RSS URL or switch to web scraping.
- **FIX** rbi_press URL — this is an HTML page, not RSS. Switch to HTML scraper or find actual RSS endpoint.
- **HANDLE** et_economy and ecb_press missing `<description>` gracefully in parser (use title as fallback)
- **NOTE** coindesk is actually healthy (25 items) — earlier 403 was tool-specific, not a real block
- **NOTE** arxiv_qfin is empty on weekends by design, not intermittent

**FILE TO EDIT:** config/sources.yaml (Reuters URLs, moneycontrol URL), collectors/rss_feeds.py (description fallback for et_economy/ecb_press, rbi_press HTML handling)

---

## SOCIAL SCRAPERS

### 11. Reddit (scrapers/reddit_scraper.py)
- **ENDPOINT STATUS:** UP - .json endpoint works from servers (blocked by some CDN tools)
- **STRUCTURE:** UNCHANGED - data.children array with post objects
- **AUTH REQUIREMENTS:** UNCHANGED for .json endpoint. **Official API pricing:** Standard tier $12K/year (100 req/min), Enterprise $50K-$500K+. r/all is being deprecated (Reddit shifting to algorithmic discovery).
- **RECOMMENDATION:** Continue using .json endpoint (free, no API key). Monitor for any restrictions on unauthenticated access. Note r/all deprecation may affect subreddit discovery.
- **FILE TO EDIT:** None (monitor only)

### 12. Hacker News (scrapers/hackernews_scraper.py)
- **ENDPOINT STATUS:** UP - Firebase API fully functional
- **STRUCTURE:** UNCHANGED - topstories.json returns 500 IDs, newstories works
- **AUTH REQUIREMENTS:** UNCHANGED - No auth needed
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

### 13. YouTube (scrapers/youtube_scraper.py)
- **ENDPOINT STATUS:** UP - Data API v3 responds (auth error without key = expected)
- **STRUCTURE:** UNCHANGED
- **AUTH REQUIREMENTS:** UNCHANGED - API key required, quota applies
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

### 14. Mastodon (scrapers/mastodon_scraper.py)
- **ENDPOINT STATUS:** **BROKEN** - `/api/v1/timelines/public` returns 422 "Unprocessable Entity"
- **STRUCTURE:** CHANGED - mastodon.social now requires authentication for public timeline
- **AUTH REQUIREMENTS:** **NEW RESTRICTION** - Authentication token now required for `/timelines/public`
- **WORKAROUND AVAILABLE:** `/api/v1/trends/statuses` works WITHOUT auth (HTTP 200). Returns trending statuses with full structure (id, content, account, stats, quotes). Instance is v4.6.0-nightly with 3.2M users.
- **RECOMMENDATION:** **QUICK FIX:** Switch to `/api/v1/trends/statuses` endpoint (no auth needed, returns trending content). **FULL FIX:** Add OAuth token support for `/timelines/public` access. Can use both: trends for immediate data, public timeline for comprehensive coverage with auth.
- **FILE TO EDIT:** scrapers/mastodon_scraper.py (switch default endpoint to trends/statuses; add optional OAuth token for public timeline)

### 15. GitHub (scrapers/github_scraper.py)
- **ENDPOINT STATUS:** UP - API working, 60 req/hr unauthenticated
- **STRUCTURE:** UNCHANGED
- **AUTH REQUIREMENTS:** UNCHANGED - Token optional but recommended for higher limits
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

### 16. SEC EDGAR (scrapers/sec_scraper.py)
- **ENDPOINT STATUS:** **DEGRADED** - EFTS returns 403 without proper User-Agent
- **STRUCTURE:** UNCHANGED - But new `data.sec.gov` REST API available alongside EFTS
- **AUTH REQUIREMENTS:** **STRICTER** - SEC now enforces User-Agent header with real email
- **NEW FEATURES:** EDGAR Release 26.1 (March 2026) added operational status indicators for degraded service. EDGAR Release 26.0.1 (Feb 2026) updated submission notifications. `data.sec.gov` REST APIs remain free, keyless, JSON — only need User-Agent.
- **RECOMMENDATION:** **UPDATE User-Agent** - Replace `research@example.com` with a real email. Consider adding `data.sec.gov` as supplementary source.
- **FILE TO EDIT:** scrapers/sec_scraper.py (line 61: update User-Agent email)

### 17. Discord (scrapers/discord_scraper.py)
- **ENDPOINT STATUS:** UP - API v10 is current
- **STRUCTURE:** MINOR CHANGES - PIN_MESSAGES split from MANAGE_MESSAGES (Feb 23, 2026). DAVE E2E encryption mandatory for voice/video (March 1, 2026).
- **AUTH REQUIREMENTS:** UNCHANGED - Bot token + MESSAGE_CONTENT intent required. Check if bot permissions need updating for PIN_MESSAGES split.
- **RECOMMENDATION:** Verify bot permissions after PIN_MESSAGES/MANAGE_MESSAGES split. Voice/video not relevant for text scraping.
- **FILE TO EDIT:** scrapers/discord_scraper.py (check permission flags if using pinning)

### 18. Dark Web (scrapers/darkweb_scraper.py)
- **ENDPOINT STATUS:** DEPENDS ON TOR - Cannot verify externally (needs SOCKS5 proxy)
- **STRUCTURE:** N/A - Varies by .onion site
- **AUTH REQUIREMENTS:** UNCHANGED - Tor proxy required
- **RECOMMENDATION:** Test from Docker container with Tor proxy running
- **FILE TO EDIT:** None

### 19. Web Scraper (scrapers/web_scraper.py)
- **ENDPOINT STATUS:** UP - General web targets accessible
- **STRUCTURE:** UNCHANGED
- **AUTH REQUIREMENTS:** UNCHANGED
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

### 20. Central Banks (scrapers/centralbank_scraper.py)
- **ENDPOINT STATUS:** UP - Fed RSS confirmed working, RBI pages accessible
- **STRUCTURE:** UNCHANGED - Standard RSS/HTML scraping
- **AUTH REQUIREMENTS:** UNCHANGED
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

---

## MESSAGING

### 21. Telegram (collectors/telegram_channels.py)
- **ENDPOINT STATUS:** REQUIRES CREDENTIALS - Cannot verify without api_id/api_hash
- **STRUCTURE:** N/A
- **AUTH REQUIREMENTS:** UNCHANGED - Telethon/Pyrogram with API credentials
- **RECOMMENDATION:** Verify from running instance
- **FILE TO EDIT:** None

### 22. Twitter/X (collectors/twitter_lists.py)
- **ENDPOINT STATUS:** UNCERTAIN - Cookie-based scraping fragile; X continues tightening
- **STRUCTURE:** LIKELY CHANGED - X regularly changes page structure
- **AUTH REQUIREMENTS:** **MAJOR CHANGE** - X shifted to pay-per-use model (Feb 6, 2026). No free tier for new developers. Reading a post: $0.005, user profile: $0.010, creating post: $0.010. 24h deduplication window. 2M post-read/month cap before Enterprise required. Legacy free tier users get $10 voucher then move to pay-as-you-go.
- **COST ESTIMATE:** At 10K posts/day = ~$1,500/month. Consider cost-benefit for sentiment scraping.
- **RECOMMENDATION:** **EVALUATE BUDGET** - Cookie scraping remains the free path but is fragile. If moving to official API, budget for pay-per-use costs. Consider reducing scrape frequency or filtering to treasury-relevant content only.
- **FILE TO EDIT:** collectors/twitter_lists.py (verify cookie auth; if migrating to API, add billing config)

---

## CONNECTORS

### 23. DragonScope Connector (connectors/dragonscope.py)
- **CODE STATUS:** HEALTHY
- **STRUCTURE:** Well-architected with Redis primary + API fallback
- **CATEGORIES:** reddit_posts, news, github_repos, sec_filings all mapped
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

### 24. LiquiFi Connector (connectors/liquifi.py)
- **CODE STATUS:** HEALTHY
- **STRUCTURE:** Good treasury keyword scoring with boundary-matching for short keywords
- **RATE PATTERNS:** Properly validates ranges (repo 0-15%, MIBOR 0-20%, USDINR 40-150)
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

### 25. Router (connectors/router.py)
- **CODE STATUS:** HEALTHY
- **LOGIC:** Platform-based routing with treasury-score content override
- **CATEGORIES COVERED:** All 13 platforms mapped to DRAGONSCOPE/LIQUIFI/BOTH
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** None

---

## INFRASTRUCTURE

### 26. Celery Beat Schedules
- **scheduler/schedule.py** - DEPRECATED (correctly marked, imports are no-op)
- **core/scheduler.py** - CANONICAL source, dynamically builds from sources.yaml
- **config/sources.yaml** - 15 YAML-driven collectors defined
- **Social scraper schedules** - 13 additional hard-coded in core/scheduler.py

**Verification Results:**
| Schedule Entry | Task Function | Scraper/Collector File | Status |
|---------------|---------------|----------------------|--------|
| collect-rbi_dbie | core.tasks.run_collector | collectors/rbi_dbie.py | OK |
| collect-rbi_circulars | core.tasks.run_collector | collectors/rbi_circulars.py | OK |
| collect-fred_api | core.tasks.run_collector | collectors/fred_api.py | OK |
| collect-nse_bhavcopy | core.tasks.run_collector | collectors/nse_bhavcopy.py | OK |
| collect-bse_api | core.tasks.run_collector | collectors/bse_api.py | OK |
| collect-ccil_rates | core.tasks.run_collector | collectors/ccil_rates.py | OK |
| collect-data_gov_in | core.tasks.run_collector | collectors/data_gov_in.py | OK |
| collect-sebi_circulars | core.tasks.run_collector | collectors/sebi_circulars.py | OK |
| collect-world_bank | core.tasks.run_collector | collectors/world_bank.py | OK |
| collect-imf_data | core.tasks.run_collector | collectors/imf_data.py | OK |
| collect-rss_feeds | core.tasks.run_collector | collectors/rss_feeds.py | OK |
| collect-telegram_channels | core.tasks.run_collector | collectors/telegram_channels.py | OK |
| collect-twitter_lists | core.tasks.run_collector | collectors/twitter_lists.py | OK |
| scrape-reddit | core.tasks.scrape_reddit | scrapers/reddit_scraper.py | OK |
| scrape-twitter | core.tasks.scrape_twitter | scrapers/twitter_scraper.py | OK |
| scrape-hackernews | core.tasks.scrape_hackernews | scrapers/hackernews_scraper.py | OK |
| scrape-youtube | core.tasks.scrape_youtube | scrapers/youtube_scraper.py | OK |
| scrape-rss-financial | core.tasks.scrape_rss_financial | scrapers/rss_scraper.py | OK |
| scrape-central-banks | core.tasks.scrape_central_banks | scrapers/centralbank_scraper.py | OK |
| scrape-sec | core.tasks.scrape_sec | scrapers/sec_scraper.py | OK |
| scrape-github | core.tasks.scrape_github | scrapers/github_scraper.py | OK |
| scrape-mastodon | core.tasks.scrape_mastodon | scrapers/mastodon_scraper.py | OK |
| scrape-darkweb | core.tasks.scrape_darkweb | scrapers/darkweb_scraper.py | OK |
| scrape-web | core.tasks.scrape_web | scrapers/web_scraper.py | OK |
| scrape-discord | core.tasks.scrape_discord | scrapers/discord_scraper.py | OK |

**No orphaned schedule entries.** All tasks have corresponding files and functions.
**No missing schedules.** All scrapers/collectors have schedule entries.

### 27. Docker Compose
- **Services:** 10 defined (postgres, redis, minio, zookeeper, kafka, tor, api, worker, beat, nlp-worker, flower)
- **Port conflicts:** NONE - All ports unique (5432, 6379, 9000, 9001, 2181, 9092, 9050, 8118, 8000, 5555)
- **Health checks:** postgres, redis, minio, kafka, api all have health checks
- **Missing health checks:** tor (restart: unless-stopped only), beat, nlp-worker, flower
- **RECOMMENDATION:** Add health checks for beat and nlp-worker services
- **FILE TO EDIT:** docker-compose.yml (optional - add health checks)

---

## NEW DATA SOURCES & API CHANGES

### Regulatory & Compliance Changes (NBFC Treasury)
| # | Change | Effective | Impact | Action |
|---|--------|-----------|--------|--------|
| 1 | **NSE Static IP Mandate** | April 1, 2026 | All algo API keys without static IP binding expired. IPv4 only, 2 IPs max. | Verify server IPs registered with broker |
| 2 | **RBI Data Protection Advisory** | April 2026 | All regulated entities must prioritize API security and data handling compliance | Review scraper data handling practices |
| 3 | **RBI Digital Payment Auth Framework** | April 1, 2026 | Risk-based authentication replacing SMS OTP-only | Update any payment auth integrations |
| 4 | **RBI Governance Overhaul** | January 2026 | Data security/privacy policies need formal governance approval | Ensure policy documentation is current |

### API Pricing & Access Changes
| # | Platform | Change | Cost Impact |
|---|----------|--------|-------------|
| 5 | **X/Twitter** | Pay-per-use model (Feb 6, 2026). No free tier. $0.005/post read, $0.010/profile. 2M reads/month cap. | ~$1,500/month at 10K posts/day |
| 6 | **Reddit** | Standard tier $12K/year. r/all being deprecated. | Free .json endpoint still works |
| 7 | **YouTube** | No changes. 10K units/day quota unchanged. | No impact |
| 8 | **Discord** | PIN_MESSAGES split from MANAGE_MESSAGES (Feb 23, 2026). DAVE E2E encryption for voice (March 1, 2026). | Bot permission audit needed |

### API Updates & New Features
| # | Source | Update | Benefit |
|---|--------|--------|---------|
| 9 | **FRED API v2** | Bulk retrieval of all series in a release (Nov 2025). JSON/XML. | Major efficiency gain for macro data |
| 10 | **SEC EDGAR 26.1** | New operational status indicators (March 2026). data.sec.gov REST API free/keyless. | Better monitoring, new data source |
| 11 | **Reuters RSS** | Fully dead. Workarounds failed March 2026. | Replace with alternatives |
| 12 | **Mastodon** | mastodon.social now requires auth for public timeline. | Add auth token |
| 13 | **CoinDesk** | Cloudflare bot protection blocks RSS. | Switch feed URL or add headers |
| 14 | **RBI DPIP** | Digital Payments Intelligence Platform — AI-powered transaction analysis. | Monitor for data access opportunities |

### Potential New Data Sources for NBFC Treasury
| # | Source | Type | Relevance |
|---|--------|------|-----------|
| 1 | **Breeze API** (ICICIdirect) | Free Indian market data, historical OHLC, streaming | HIGH — direct NSE/BSE data, no cost |
| 2 | **GitHub NSE/BSE API** (0xramm) | Free REST API via Yahoo Finance backend, no key needed | HIGH — backup for NSE/BSE data |
| 3 | **NaBFID** | Infrastructure financing DFI data | MEDIUM — relevant to bond/credit markets |
| 4 | **RBI KLEMS** | Productivity/growth database | MEDIUM — macro indicators |
| 5 | **NPCI** | UPI transaction statistics | MEDIUM — digital payment flow signals |
| 6 | **IBBI** | Insolvency/bankruptcy data | MEDIUM — corporate health signals |
| 7 | **data.sec.gov** | Free SEC RESTful JSON API | MEDIUM — supplements EFTS search |
| 8 | **Upstox API** | Free market data (may have expired March 31, 2026) | LOW — verify availability |

---

## PRIORITY ACTION ITEMS

### P0 - URGENT: Compliance & Broken Sources (This Week)
| # | Issue | File | Action |
|---|-------|------|--------|
| 1 | **NSE Static IP Mandate** (April 1 deadline PASSED) | Infrastructure | Verify production server IPs registered with broker; IPv4 only |
| 2 | **RBI Data Protection Advisory** (April 2026) | All collectors | Review API security and data handling for NBFC compliance |
| 3 | FBIL down (ECONNREFUSED) | collectors/ccil_rates.py | Migrate to `ccilindia.com` Data & Statistics for MIBOR/ZCYC data |
| 4 | **RBI DBIE TLS cert broken** | collectors/rbi_dbie.py | Update BASE_URL to `data.rbi.org.in`; investigate SPA API endpoints |
| 5 | **data.gov.in fully blocked** (403/404 all endpoints) | collectors/data_gov_in.py | Test with browser headers; check if API migrated to `apisetu.gov.in` |
| 6 | Reuters RSS dead | config/sources.yaml | Replace with RSS.app proxies or switch to web scraping |
| 7 | Mastodon needs auth | scrapers/mastodon_scraper.py | **Quick fix:** switch to `/api/v1/trends/statuses` (no auth). Full fix: add OAuth token. |
| 8 | SEC User-Agent placeholder | scrapers/sec_scraper.py:61 | Replace `research@example.com` with real email |
| 9 | **IMF SDMX API dead** (TCP timeout) | collectors/imf_data.py | Find replacement API — old `dataservices.imf.org` decommissioned. Check `data.imf.org` docs. |

### P1 - Fix This Month
| # | Issue | File | Action |
|---|-------|------|--------|
| 10 | **X/Twitter cost planning** | collectors/twitter_lists.py | Evaluate pay-per-use API vs cookie scraping; budget if migrating |
| 11 | **FRED API v2 upgrade** | collectors/fred_api.py | Add v2 bulk retrieval for efficient macro data pulls |
| 12 | **Moneycontrol RSS frozen** (since April 2024) | config/sources.yaml | Find new RSS URL or switch to web scraping |
| 13 | **RBI Press not RSS** (HTML page) | config/sources.yaml, collectors/rss_feeds.py | Switch to HTML scraper or find actual RSS endpoint |
| 14 | ET Economy + ECB no descriptions | collectors/rss_feeds.py | Handle missing `<description>` gracefully (use title fallback) |
| 15 | Discord permission split | scrapers/discord_scraper.py | Verify bot permissions for PIN_MESSAGES change |

### P2 - Nice to Have / New Sources
| # | Issue | File | Action |
|---|-------|------|--------|
| 14 | World Bank timeouts | collectors/world_bank.py | Add retry with backoff, increase timeout |
| 15 | SEBI slow pages | collectors/sebi_circulars.py | Increase timeout to 60s |
| 16 | Docker health checks | docker-compose.yml | Add checks for beat/nlp-worker |
| 17 | SEC data.sec.gov API | scrapers/sec_scraper.py | Add as supplementary data source |
| 18 | Breeze API integration | NEW collector | Free NSE/BSE data — evaluate as backup source |
| 19 | Upstox API check | N/A | Verify if free access extended past March 31, 2026 |
| 20 | RBI DPIP monitoring | N/A | Watch for public data access when platform launches |

---

*Report generated by automated weekly validation task.*
*Next validation: 2026-04-20*
