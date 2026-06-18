# PALIMPSEST → China-Beige-Book-style Conditions Engine — Build Plan

## Goal
Reproduce China Beige Book's *philosophy and output*, not its survey moat:
1. **Independent ground-truth** that ignores official NBS stats (we use physical anchors instead of firm surveys).
2. **Sector × region** disaggregation as **diffusion indices** (% improving − % deteriorating).
3. **Flow over level** — emphasize change (momentum), not absolute snapshots.
4. **Divergence flag** — surface where independent data contradicts official claims (CBB's signature).
5. A periodic **"China Conditions Report"**.

What we explicitly DON'T copy: CBB's primary firm-survey network (unreplicable solo). Our
substitute is OSINT + un-fakeable physical anchors, with confidence scoring that is honest
about being noisier than surveys.

---

## Layer 1 — Independent data (the survey substitute)
All as `BaseCollector` subclasses → `EconomicData` table (`source_type="api"`).

| Collector | Source | Cost/reach | Feeds which sectors | Status |
|---|---|---|---|---|
| `comtrade_mirror.py` | UN Comtrade (partner-reported trade) | free API (key for higher limits); globally reachable | manufacturing, property (ore/cement/copper), tech (semiconductors HS85), agri (soybeans), commodities | **Phase 1** |
| `viirs_nightlights.py` | NASA Black Marble VNP46 | free | regional activity, property (new districts) | Phase 3 |
| `ais_ports.py` | aisstream.io websocket | free | transport/logistics, export tempo | Phase 3 |
| (existing) sentiment/DDTI | scraped articles | built | every sector (sentiment diffusion) | ✅ |

**Why Comtrade first:** partner customs data is collected *outside* China → un-massageable;
free; reachable from normal egress (unlike the Cloudflare-blocked censorship feeds). It is the
single most CBB-spirited dataset and the cleanest first build.

Comtrade specifics: pull monthly China (reporter=156) trade AND mirror (partners report China as
partner), by HS chapter. Key chapters → sectors: HS72/73 steel, HS25 cement, HS26 ores, HS74 copper
→ **property/construction**; HS84/85 machinery/electronics → **manufacturing/tech**; HS85 (8541/8542
semiconductors) → **tech**; HS12 oilseeds, HS10 cereals → **agriculture**; HS27 energy → **energy**.
Mirror gap (partner-reported China imports − China-reported exports) = a distortion signal.

---

## Layer 2 — Sector × region taxonomy  (`config/cbb_taxonomy.json`)
**Sectors (9):** manufacturing, property_construction, retail_consumer, services, agriculture,
mining_commodities, transport_logistics, finance_banking, technology.
**Regions (initial):** coastal_export (Guangdong, Jiangsu, Zhejiang, Shanghai, Fujian),
inland, northeast_rustbelt, national. (Region split comes mainly from nightlights + provincial
trade; mark coverage="partial" until then.)
**Firm-type (stretch axis):** SOE vs private — inferable later from filings/announcements; defer.

Each sector entry maps to: sentiment keywords (zh+en), the anchor series that proxy it, and an
optional official series for the divergence check.

---

## Layer 3 — Diffusion-index formula  (`processors/conditions_index.py`, pure core)
Per sector *s*, period *t* (monthly):

**Sentiment diffusion** (from sector-tagged articles with sentiment score ∈ [−1,1]; classify each
mention positive if score>+θ, negative if <−θ, else neutral; θ=0.15):
```
SD = 100 · (n_pos − n_neg) / max(1, n_pos + n_neg + n_neutral)        # range −100..+100
```

**Anchor signal** (for sectors with a physical proxy; g = period-over-period growth of the anchor
series, e.g. mirror-trade volume; k = reference scale ≈ 0.10):
```
AS = 100 · tanh(g / k)                                                # bounded −100..+100
```

**Blended conditions index** (weights sum to 1; if no anchor, w_anchor=0 and confidence drops):
```
D = w_sent · SD + w_anchor · AS         (default w_sent=0.4, w_anchor=0.6 when anchor exists)
```

**Momentum (flow, the CBB emphasis):**  `ΔD = D_t − D_{t−1}`

**Confidence:**  `C = f(n_mentions, anchor_available)` → low/med/high; reported with every cell.

**Divergence (CBB signature):** when an official series O exists,
```
Div = AS_independent − normalize(O_official)
```
Persistent Div<0 (official > independent) = suspected overstatement → flagged in the report.

All outputs are **−100..+100** so red↔green heatmaps and QoQ arrows render directly.

---

## Layer 4 — Storage (time-series)  (`storage/models.py`)
New `ConditionsIndexSnapshot`: (generated_at, period, sector, region, diffusion D, sentiment SD,
anchor AS, momentum ΔD, divergence, confidence, n_mentions, inputs JSONB). One row per
sector×region×period → native time-series (mirrors `ddti_index_snapshots`). Redis `cbb:latest`
for the live dashboard; disk JSON fallback like the DDTI pull.

---

## Layer 5 — Report generator  (`processors/conditions_report.py`, pattern = daily_digest.py)
Assemble the sector grid + anchors + divergence flags → `free_llm_router` → a CBB-style brief:
per-sector conditions, biggest movers (momentum), and an explicit "where official data looks
overstated" section. Periodic (monthly/quarterly). Stored + optionally emailed/Telegram'd.

---

## Layer 6 — Dashboard  (extend or sibling of ddti_dashboard.html)
Sector × region **conditions heatmap** (diffusion color scale, momentum arrows, confidence dots,
divergence ⚠ flags), plus a conditions time-series sparkline per sector from the snapshot history.
Same "Redacted Terminal" aesthetic; XSS-safe rendering (esc()/num(), whitelisted color scales).

---

## Build sequence & gates
- **Phase 1 — Comtrade mirror-trade collector** + taxonomy config. GATE: collector returns real
  partner-trade rows for ≥5 HS chapters from this egress.
- **Phase 2 — Conditions index** (pure formula + processor over sentiment, anchor optional) +
  storage model + a cold-start run. GATE: a sector grid renders with non-flat diffusion.
- **Phase 3 — More anchors** (nightlights, AIS) for regional + non-trade sectors.
- **Phase 4 — Conditions report** generator.
- **Phase 5 — Dashboard heatmap** + history sparklines.

## Honest limits
- No firm-level survey data — OSINT proxies are noisier; every cell ships a confidence score.
- Region/firm-type axes start thin (sentiment is rarely geotagged); grow with nightlights/filings.
- Divergence needs an official series to compare against; where absent, report independent-only.
- Comtrade lags weeks–months and is vintage-revised → carry vintage-aware timestamps, no look-ahead.
- HK re-exports / CIF-FOB asymmetries distort mirror-trade → use as a consensus signal, not gospel.
