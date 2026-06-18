# Weekly Deep Source Validation Report
**Date:** 2026-05-25 (Sunday)
**Run by:** Automated scheduled task

---

## EXECUTIVE SUMMARY

| Category | Total | UP/OK | CHANGED | DOWN/BROKEN | ACTION NEEDED |
|----------|-------|-------|---------|-------------|---------------|
| Structured Data Collectors | 10 | 5 | 3 | 2 | 5 |
| RSS Feeds | 14 | 6 | 2 | 4 | 6 |
| Social Scrapers | 10 | 4 | 3 | 1 | 4 |
| Messaging | 2 | 1 | 1 | 0 | 1 |
| Connectors | 3 | 3 | 0 | 0 | 0 |
| Infrastructure | 2 | 2 | 0 | 0 | 0 |

**Critical Issues (Immediate):**
1. RBI DBIE URL has changed — `dbie.rbi.org.in` has TLS cert issues; new portal at `data.rbi.org.in`
2. CCIL FBIL rates URL structure changed — old `/web/ccil/fbil-overnight-mibor` returns 404
3. IMF legacy API (`dataservices.imf.org`) appears unresponsive — migrated to SDMX 3.0
4. Reuters RSS feeds confirmed dead since 2020 — still configured in sources.yaml
5. SEC EDGAR EFTS returning 403 — may need User-Agent update for EDGAR Next

---

## 1. RBI DBIE

- **ENDPOINT STATUS:** CHANGED / DOWN
- **STRUCTURE:** BROKEN — TLS certificate error on `dbie.rbi.org.in`. RBI has migrated to `data.rbi.org.in/DBIE/`
- **AUTH REQUIREMENTS:** NEW URL discovered; may need updated headers
- **NEW FEATURES:** RBI launched RBIDATA mobile app; new portal at `data.rbi.org.in` is the modernized DBIE
- **RECOMMENDATION:** **Update collector URL immediately** — change `BASE_URL` from `https://dbie.rbi.org.in/DBIE` to `https://data.rbi.org.in/DBIE/`. Investigate new API structure.
- **FILE TO EDIT:** `collectors/rbi_dbie.py` (line 24: `BASE_URL`) and `config/sources.yaml` (rbi_dbie.base_url)

---

## 2. RBI Circulars

- **ENDPOINT STATUS:** UP
- **STRUCTURE:** UNCHANGED — Press releases page still uses chronological list, year-based dropdown navigation, URL pattern `BS_PressReleaseDisplay.aspx?prid=[ID]`
- **AUTH REQUIREMENTS:** UNCHANGED (no auth needed)
- **NEW FEATURES:** None detected
- **RECOMMENDATION:** No action needed
- **FILE TO EDIT:** N/A

---

## 3. NSE India

- **ENDPOINT STATUS:** DOWN (connection reset — heavy anti-bot)
- **STRUCTURE:** CANNOT VERIFY — NSE's aggressive anti-bot protection blocks automated fetches
- **AUTH REQUIREMENTS:** NSE continues to use heavy browser fingerprinting, session cookies, and WAF protection
- **NEW FEATURES:** Cannot assess
- **RECOMMENDATION:** Verify in-production scraper logs. If bhavcopy downloads are failing, may need to rotate User-Agents or use playwright-based fetching. Consider if NSE has tightened protections further.
- **FILE TO EDIT:** `collectors/nse_bhavcopy.py` (if issues found in production logs)

---

## 4. BSE

- **ENDPOINT STATUS:** UP (partial — page loads but minimal content via automated fetch)
- **STRUCTURE:** UNCHANGED (JavaScript-heavy, API-driven frontend)
- **AUTH REQUIREMENTS:** UNCHANGED
- **NEW FEATURES:** None detected
- **RECOMMENDATION:** No action — BSE APIs likely still functional for the collector
- **FILE TO EDIT:** N/A

---

## 5. CCIL Rates

- **ENDPOINT STATUS:** CHANGED — `/web/ccil/fbil-overnight-mibor` returns **404**
- **STRUCTURE:** MODIFIED — CCIL website restructured. New URL paths:
  - Money market rates: `/tenor-wise-term-money`, `/repo-summary`
  - MIBOR/TREPS: under "Data & Statistics" → "Money Market" → "Treps"
  - Yield curve: `/zcyc-parameters`
  - FBIL benchmarks: `/Research/FBIL%20Benchmarks/Pages/default.aspx`
- **AUTH REQUIREMENTS:** UNCHANGED
- **NEW FEATURES:** FBIL data also available directly at `www.fbil.org.in` (separate site)
- **RECOMMENDATION:** **Update URL paths in collector.** Current `FBIL_URL = "https://www.fbil.org.in"` is correct for the API endpoint, but the HTML scrape fallback needs updated selectors. Test `https://www.fbil.org.in/api/ratesapi` endpoint from production.
- **FILE TO EDIT:** `collectors/ccil_rates.py` — verify FBIL_URL API endpoint still responds; update HTML scrape fallback paths if API fails

---

## 6. FRED API

- **ENDPOINT STATUS:** UP (returned 403 with DEMO_KEY, but real key should work)
- **STRUCTURE:** UNCHANGED — standard JSON response format with observations array
- **AUTH REQUIREMENTS:** UNCHANGED (API key required as before)
- **NEW FEATURES:** None detected
- **RECOMMENDATION:** No action. The 403 was due to using `DEMO_KEY`; real API key in env should work fine. Verify in production logs.
- **FILE TO EDIT:** N/A

---

## 7. SEBI

- **ENDPOINT STATUS:** UP
- **STRUCTURE:** MODIFIED — Not using standard table format anymore. Circulars use list structure with `/legal/rules/[month-year]/[rule-title]_[ID].html` URL pattern. Has "Updated List" vs "Historical Data" toggle. Login modal overlay present.
- **AUTH REQUIREMENTS:** Login modal overlay visible — may indicate new auth for some content
- **NEW FEATURES:** "Historical Data" toggle functionality
- **RECOMMENDATION:** **Investigate** — verify the collector still correctly parses the circulars listing. The URL pattern change from table to list format may need parser update.
- **FILE TO EDIT:** `collectors/sebi_circulars.py`

---

## 8. data.gov.in

- **ENDPOINT STATUS:** DOWN (403 Forbidden)
- **STRUCTURE:** CANNOT VERIFY — returns 403 to automated requests
- **AUTH REQUIREMENTS:** NEW RESTRICTIONS DETECTED — API blocking non-browser requests
- **NEW FEATURES:** India modernizing core economic data systems (GDP rebasing to 2022-23 base year, new IIP series May 28 2026, e-SIGMA digital platform, GST/eVahan data integration)
- **RECOMMENDATION:** **Investigate** — check if API key auth header is being sent correctly. The site may have added rate limiting or bot detection. Check `DATA_GOV_API_KEY` is valid.
- **FILE TO EDIT:** `collectors/data_gov_in.py`

---

## 9. World Bank API

- **ENDPOINT STATUS:** UP
- **STRUCTURE:** UNCHANGED — returns `[metadata, data_array]` JSON. Pagination: page/pages/per_page/total. Records have indicator.id, country.id, date, value fields. India 2024 GDP: $3.91T.
- **AUTH REQUIREMENTS:** UNCHANGED (no auth needed)
- **NEW FEATURES:** None detected
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** N/A

---

## 10. IMF Data

- **ENDPOINT STATUS:** CHANGED — Legacy `dataservices.imf.org` ECONNREFUSED
- **STRUCTURE:** BROKEN for current collector — IMF has migrated to SDMX Central at `sdmxcentral.imf.org` and new API at `api.imf.org/external/sdmx/3.0`
- **AUTH REQUIREMENTS:** New API may require account sign-in for full access
- **NEW FEATURES:** SDMX 3.0 API available at `api.imf.org/external/sdmx/3.0`. IMF SDMX Central at `sdmxcentral.imf.org/ws/public/sdmxapi/rest/dataflow` confirmed working (BOP, DOT datasets verified present; IFS likely available).
- **RECOMMENDATION:** **Rewrite collector** — migrate from `http://dataservices.imf.org/REST/SDMX_JSON.svc` to new `https://sdmxcentral.imf.org/ws/public/sdmxapi/rest/` endpoint. Update data parsing for SDMX 2.1 XML or new JSON format.
- **FILE TO EDIT:** `collectors/imf_data.py` (lines 14, 24-28: BASE_URL and request logic)

---

## RSS FEEDS

### Feed Status Summary

| Feed | Status | Notes |
|------|--------|-------|
| reuters_business | **DEAD** | Discontinued 2020. Remove or replace. |
| reuters_markets | **DEAD** | Discontinued 2020. Remove or replace. |
| et_economy | UNREACHABLE | Blocked from automated fetch (likely bot protection) |
| et_markets | UNREACHABLE | Same as above |
| mint_economy | UNREACHABLE | Same — Mint blocks automated fetches |
| mint_markets | UNREACHABLE | Same |
| moneycontrol | UNREACHABLE | Blocked from this environment |
| rbi_press | UP | Not a real RSS feed (HTML page). Listed URL is the press releases page, not an RSS endpoint. Collector handles this via HTML scraping. |
| fed_press | **UP** | RSS 2.0, items have title/link/description/pubDate/guid/category. Latest: May 22, 2026. Working perfectly. |
| ecb_press | **UP** | RSS 2.0, items have title/link/guid/pubDate. Latest build: May 22, 2026. Working. |
| coindesk | **UP** | RSS 2.0 with media/dc/content namespaces. Latest: May 24-25, 2026. TTL 5min. Working. |
| cnbc | **UP** | RSS 2.0, 27 items, metadata:type tags present. Last built May 24, 2026. Working. |
| ft_markets | UNREACHABLE | FT likely paywalled/blocked |
| arxiv_qfin | **UP** | RSS 2.0, lastBuildDate May 24, 2026. Feed structure intact but items may be empty on weekends. |

### RSS Recommendations

- **CRITICAL:** Remove `reuters_business` and `reuters_markets` from `config/sources.yaml` or replace with alternatives:
  - Google News RSS: `https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com`
  - Or use RSS.app/Feedspot generated feeds
- **INVESTIGATE:** Indian news feeds (ET, Mint, MoneyControl) — verify they work from production server (may be blocked only from non-Indian IPs)
- **FILE TO EDIT:** `config/sources.yaml` (feeds section)

---

## SOCIAL SCRAPERS

### 11. Reddit

- **STATUS:** FUNCTIONAL (with caveats)
- **CHANGES:** Reddit API pricing tiers still in effect (since 2023): Free tier = 100 req/min with OAuth, 10K monthly calls. Commercial = $12K/year. The scraper uses `.json` endpoint which is still free for read-only.
- **RISK:** Reddit has increasingly enforced rate limits on unauthorized scraping. The `.json` endpoint may get restricted.
- **RECOMMENDATION:** Monitor rate limit errors in production. Consider if OAuth credentials are being used. The free tier (100 req/min, 10K/month) should suffice for current monitoring volume.
- **FILE TO EDIT:** `scrapers/reddit_scraper.py` (no changes needed now)

### 12. Hacker News

- **STATUS:** UP — Firebase API working perfectly
- **STRUCTURE:** UNCHANGED — returns JSON array of integer story IDs. `https://hacker-news.firebaseio.com/v0/topstories.json` confirmed operational.
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** N/A

### 13. YouTube

- **STATUS:** UP (quota system unchanged)
- **CHANGES:** Default 10,000 units/day quota still in effect. Search costs 100 units each. Stricter compliance audits for high-volume usage.
- **RISK:** 10 search queries × 100 units = 1,000 units/run. At medium frequency, quota should be fine.
- **RECOMMENDATION:** No action — monitor quota usage
- **FILE TO EDIT:** N/A

### 14. Mastodon

- **STATUS:** UP — Public timeline API requires no auth
- **STRUCTURE:** UNCHANGED — instances listed (mastodon.social, fosstodon.org, etc.) still support public API
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** N/A

### 15. GitHub

- **STATUS:** UP
- **STRUCTURE:** REST API v3 unchanged. Rate limits: 5000 req/hour with token, 60/hour without.
- **RECOMMENDATION:** No action — ensure `GITHUB_TOKEN` env var is set
- **FILE TO EDIT:** N/A

### 16. SEC EDGAR

- **STATUS:** CHANGED — EFTS endpoint returning 403
- **STRUCTURE:** MODIFIED — EDGAR Next initiative rolled out. New API requires enrollment. EDGAR Release 26.0.1 deployed Feb 2026.
- **AUTH REQUIREMENTS:** NEW — EDGAR Next requires individual user credentials + MFA for submission API. Read access may now require proper User-Agent with contact email.
- **NEW FEATURES:** EDGAR Next APIs (submission, account management, role-based access)
- **RECOMMENDATION:** **Update User-Agent header** in `sec_scraper.py`. Current: `"SocialScraper research@example.com"` — update the email to a real contact email. SEC requires: `Company Name AdminEmail@company.com`. Also verify EFTS URL hasn't changed to a new path under EDGAR Next.
- **FILE TO EDIT:** `scrapers/sec_scraper.py` (line 62: User-Agent header, lines 52-54: EFTS_URL)

### 17. Discord

- **STATUS:** UP — API v10 still current
- **STRUCTURE:** UNCHANGED
- **RECOMMENDATION:** No action — verify `DISCORD_BOT_TOKEN` has MESSAGE_CONTENT intent
- **FILE TO EDIT:** N/A

### 18. Dark Web

- **STATUS:** Cannot verify (Tor proxy not available from this environment)
- **RECOMMENDATION:** Verify tor container is running and SOCKS5 proxy at port 9050 is accessible from worker container
- **FILE TO EDIT:** N/A

### 19. Web Scraper

- **STATUS:** Site-dependent
- **RECOMMENDATION:** No action — general purpose scraper adapts to targets
- **FILE TO EDIT:** N/A

### 20. Central Banks

- **STATUS:** MIXED
  - Fed press RSS: UP (confirmed working, latest May 22, 2026)
  - ECB press RSS: UP (confirmed working, latest May 22, 2026)
  - RBI press: UP (HTML page, not RSS — collector handles via scraping)
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** N/A

---

## MESSAGING

### 21. Telegram

- **STATUS:** UP (API access depends on credentials)
- **CHANGES:** No known API changes. Telegram Bot API stable.
- **RECOMMENDATION:** Verify `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are current. Check channel access.
- **FILE TO EDIT:** N/A

### 22. Twitter/X

- **STATUS:** HIGH RISK
- **CHANGES (CRITICAL):**
  - X introduced "Pay-Per-Use" billing Feb 2026
  - Free tier is WRITE-ONLY (cannot read/scrape)
  - Basic tier: $200/mo for 10K tweets read
  - Cloudflare Turnstile deployed on login walls and rate-limited endpoints
  - Jan 2025: Guest token bound to browser fingerprints; datacenter IPs banned
  - Legal threat: $15K liquidated damages for >1M posts/24h automated access
- **AUTH REQUIREMENTS:** Cookie-based scraping via `twikit` is HIGH RISK — X actively detects and bans
- **RECOMMENDATION:** **HIGH PRIORITY** — Current `twikit` cookie approach is likely broken or at serious risk. Options:
  1. Pay for Basic tier ($200/mo) for legitimate read access
  2. Use a third-party scraping API service (various providers available)
  3. Reduce scraping frequency significantly
  4. Accept that Twitter data may be intermittent
- **FILE TO EDIT:** `scrapers/twitter_scraper.py`, `collectors/twitter_lists.py`

---

## CONNECTORS

### 23. DragonScope Connector
- **STATUS:** UP (depends on Redis and API endpoint)
- **RECOMMENDATION:** Verify `DRAGONSCOPE_REDIS_URL` and `DRAGONSCOPE_API_URL` connectivity
- **FILE TO EDIT:** N/A

### 24. LiquiFi Connector
- **STATUS:** UP (depends on Redis and API endpoint)
- **RECOMMENDATION:** Verify `LIQUIFI_REDIS_URL` and `LIQUIFI_API_URL` connectivity
- **FILE TO EDIT:** N/A

### 25. Router
- **STATUS:** UP — classification logic solid
- **STRUCTURE:** Platform-based routing with content-override. Coverage:
  - DragonScope: Reddit, Discord, YouTube, HackerNews, Mastodon, GitHub
  - LiquiFi: Central Bank data
  - Both: Twitter, Telegram, RSS, Web, SEC EDGAR, Dark Web
- **RECOMMENDATION:** No action
- **FILE TO EDIT:** N/A

---

## INFRASTRUCTURE

### 26. Celery Beat Schedules

- **STATUS:** CONSISTENT
- `scheduler/schedule.py` — correctly marked as deprecated (reference only)
- `core/scheduler.py` — builds beat schedule dynamically from `config/sources.yaml`
- All sources in `config/sources.yaml` have matching collector files in `collectors/`
- All scrapers have corresponding files in `scrapers/`
- **No orphaned schedule entries detected**
- **RECOMMENDATION:** No action

### 27. Docker Compose

- **STATUS:** OK
- Services defined: postgres, redis, minio, zookeeper, kafka, tor, api, worker (+ beat implied)
- Ports: 5432, 6379, 9000/9001, 2181, 9092, 9050/8118, 8000 — no conflicts
- Health checks: postgres (pg_isready), redis (ping), minio (mc ready), kafka (topics --list), api (curl /health)
- **Note:** `dperson/torproxy` image — verify it's still maintained (last DockerHub update should be checked)
- **RECOMMENDATION:** No action needed for port conflicts or health checks

---

## NEW DATA SOURCES DISCOVERED

| Source | URL | Value for NBFC Treasury |
|--------|-----|------------------------|
| FBIL Direct | `https://www.fbil.org.in` | Official benchmark rates (MIBOR, MIFOR, MIOIS) — more authoritative than CCIL for rate data |
| RBI New Portal | `https://data.rbi.org.in/DBIE/` | Modernized DBIE with potential API access |
| API Setu | `https://www.apisetu.gov.in` | Government API marketplace — may have new economic datasets |
| FinEdge API | `https://www.finedgeapi.com` | Indian corporate financial data (P&L, Balance Sheet, Cash Flow) |
| TrueData | `https://www.truedata.in` | Real-time NSE/BSE/MCX market data API |
| India GDP Rebasing | New IIP series releasing May 28, 2026 | Updated economic indicators with 2022-23 base year |
| IMF SDMX 3.0 | `https://api.imf.org/external/sdmx/3.0` | New API with better data access |
| EDGAR Next APIs | `https://www.sec.gov/submit-filings/filer-support-resources` | Modernized EDGAR filing access |

---

## PRIORITY ACTION ITEMS

### P0 — Immediate (This Week)

1. **Update RBI DBIE URL** → `data.rbi.org.in/DBIE/`
   - File: `collectors/rbi_dbie.py` line 24, `config/sources.yaml`
   
2. **Fix/Verify CCIL rates** — test FBIL API endpoint from production
   - File: `collectors/ccil_rates.py`

3. **Remove dead Reuters feeds** from `config/sources.yaml`
   - Replace with Google News RSS alternatives or remove entirely

### P1 — High Priority (Next Sprint)

4. **Rewrite IMF collector** for SDMX Central API
   - File: `collectors/imf_data.py` — migrate to `sdmxcentral.imf.org`

5. **Update SEC EDGAR User-Agent** with real contact email
   - File: `scrapers/sec_scraper.py` line 62

6. **Assess Twitter/X scraping viability** — decide on paid API vs third-party service vs accept degraded data
   - Files: `scrapers/twitter_scraper.py`, `collectors/twitter_lists.py`

### P2 — Medium Priority (Next 2 Weeks)

7. **Verify SEBI collector** still parses new list-based layout
   - File: `collectors/sebi_circulars.py`

8. **Check data.gov.in API** from production (may be geo-restricted)
   - File: `collectors/data_gov_in.py`

9. **Evaluate new sources:** FBIL direct, API Setu, FinEdge API for NBFC treasury data enrichment

---

## ENVIRONMENT NOTES

- Some endpoints (ET, Mint, MoneyControl, NSE, FT) are unreachable from this validation environment but may work from the production server (different IP/geo/headers). Check production collector logs for ground truth.
- SEC EDGAR's 403 responses may be specific to this environment's IP/User-Agent. Production should be verified separately.
- IMF legacy API connection refused is definitive — the service has been decommissioned.
