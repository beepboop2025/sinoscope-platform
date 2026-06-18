"""China Economic Conditions Engine — conditions index processor.

Implements a pure, offline-testable diffusion index that blends three
independent signals for each sector/month:

1. Reported trade value (China customs / UN Comtrade reporter==156).
2. Mirror trade value (partner-reported flows involving China).
3. Chinese high-frequency indicators (BDI, CCFI, SCFI, etc.).
4. Sentiment diffusion from news/social mentions.

The public core is `compute_conditions(...)`.  The `ConditionsIndexProcessor`
wraps it as a Celery-task-style aggregate processor that reads from PostgreSQL
and publishes the latest result to Redis (`cbb:latest`).
"""

import json
import logging
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.base_processor import BaseProcessor

logger = logging.getLogger(__name__)

_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "config" / "cbb_taxonomy.json"

# Tunable index parameters
ANCHOR_TANH_SCALE = 0.10          # growth rate that maps to ~76% of saturation
SENTIMENT_POS_THRESHOLD = 0.15
SENTIMENT_NEG_THRESHOLD = -0.15
TRADE_WEIGHT = 0.6
SENTIMENT_WEIGHT = 0.4
HIGH_CONFIDENCE_MENTIONS = 30
MED_CONFIDENCE_MENTIONS = 10


def _norm_dt(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to UTC; treat naive datetimes as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _month_key(dt: datetime) -> tuple:
    dt = _norm_dt(dt)
    return (dt.year, dt.month)


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _prev_month(year: int, month: int) -> tuple:
    if month == 1:
        return (year - 1, 12)
    return (year, month - 1)


def _is_complete_month(year: int, month: int, now: datetime) -> bool:
    """True when the last instant of ``year/month`` is at or before ``now``."""
    now = _norm_dt(now)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
    return end <= now


def _latest_complete_month(now: datetime) -> tuple:
    """Calendar-based latest complete month at or before ``now``."""
    now = _norm_dt(now)
    y, m = now.year, now.month
    if _is_complete_month(y, m, now):
        return (y, m)
    return _prev_month(y, m)


def _period_str(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _load_taxonomy(path: Optional[Path] = None) -> dict:
    """Load CBB taxonomy from disk; return an empty skeleton on failure."""
    path = path or _TAXONOMY_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[ConditionsIndex] taxonomy load failed: {e}")
        return {"sectors": {}}


def compute_conditions(trade_series, cn_indicators, sentiment_mentions, taxonomy, now):
    """Pure computation core for the China Economic Conditions index.

    Parameters
    ----------
    trade_series:
        List of dicts with keys ``date``, ``flow`` (M|X), ``hs``,
        ``value``, ``reporter``, ``partner``.
    cn_indicators:
        List of dicts with keys ``date``, ``indicator``, ``value``.
    sentiment_mentions:
        List of dicts with keys ``date``, ``sector``, ``score``.
    taxonomy:
        Dict loaded from ``config/cbb_taxonomy.json``.
    now:
        Datetime anchor.  The latest complete month ≤ ``now`` and the previous
        month are used for momentum.

    Returns
    -------
    List of per-sector result dicts (see spec for field definitions).
    """
    sectors = taxonomy.get("sectors", {})
    if not sectors:
        return []

    now = _norm_dt(now)
    latest = _latest_complete_month(now)
    previous = _prev_month(*latest)

    # Map HS codes → sectors (a code may belong to multiple sectors).
    hs_to_sectors: dict[str, list[str]] = defaultdict(list)
    for sector_key, sector in sectors.items():
        for hs in sector.get("hs_codes", []):
            hs_to_sectors[str(hs)].append(sector_key)

    # Aggregate reported / mirror trade by (sector, month).
    reported: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
    mirror: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
    for rec in trade_series:
        dt = _norm_dt(rec.get("date"))
        if dt is None:
            continue
        m = _month_key(dt)
        hs = str(rec.get("hs", ""))
        val = rec.get("value")
        if val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        reporter = rec.get("reporter")
        partner = rec.get("partner")
        for sector in hs_to_sectors.get(hs, []):
            if str(reporter) == "156":
                reported[sector][m] += val
            if str(partner) == "156":
                mirror[sector][m] += val

    # Aggregate CN high-frequency indicators by (month, indicator key).
    ind_by_month: dict[tuple, dict[str, float]] = {}
    for i in cn_indicators:
        dt = _norm_dt(i.get("date"))
        if dt is None:
            continue
        m = _month_key(dt)
        key = i.get("indicator", "")
        val = i.get("value")
        if val is None or not key:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        inner = ind_by_month.setdefault(m, {})
        inner[key] = inner.get(key, 0.0) + val

    # Aggregate sentiment mentions by (sector, month).
    mentions_by_sector_month: dict[str, dict[tuple, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for mention in sentiment_mentions:
        dt = _norm_dt(mention.get("date"))
        if dt is None:
            continue
        m = _month_key(dt)
        sector = mention.get("sector", "")
        score = mention.get("score", 0.0)
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0
        mentions_by_sector_month[sector][m].append(score)

    results = []
    for sector_key in sorted(sectors.keys()):
        sector = sectors[sector_key]
        region = sector.get("region", "national")
        hf_sources = sector.get("cn_hf_sources", []) or []

        month_metrics = {}
        for m in (latest, previous):
            prev_m = _prev_month(*m)

            # --- Anchor: reported trade first, then CN HF fallback ---
            g = None
            anchor_source = None
            if m in reported[sector_key] and prev_m in reported[sector_key]:
                cur_val = reported[sector_key][m]
                prev_val = reported[sector_key][prev_m]
                g = (cur_val - prev_val) / max(1.0, abs(prev_val))
                anchor_source = "trade"
            else:
                cur_ind = ind_by_month.get(m, {})
                prev_ind = ind_by_month.get(prev_m, {})
                for src in hf_sources:
                    if src in cur_ind and src in prev_ind:
                        cur_val = cur_ind[src]
                        prev_val = prev_ind[src]
                        g = (cur_val - prev_val) / max(1.0, abs(prev_val))
                        anchor_source = f"cn_hf:{src}"
                        break

            anchor_available = g is not None
            as_value = 100.0 * math.tanh(g / ANCHOR_TANH_SCALE) if anchor_available else 0.0

            # --- Sentiment diffusion ---
            scores = mentions_by_sector_month.get(sector_key, {}).get(m, [])
            pos = sum(1 for s in scores if s > SENTIMENT_POS_THRESHOLD)
            neg = sum(1 for s in scores if s < SENTIMENT_NEG_THRESHOLD)
            neutral = len(scores) - pos - neg
            sd = 100.0 * (pos - neg) / max(1, pos + neg + neutral)

            # --- Blended diffusion ---
            if anchor_available:
                d = SENTIMENT_WEIGHT * sd + TRADE_WEIGHT * as_value
            else:
                d = float(sd)

            month_metrics[m] = {
                "D": d,
                "SD": sd,
                "AS": as_value,
                "reported_value": reported[sector_key].get(m),
                "mirror_value": mirror[sector_key].get(m),
                "anchor_growth": g,
                "anchor_source": anchor_source,
                "pos": pos,
                "neg": neg,
                "neutral": neutral,
            }

        latest_metrics = month_metrics[latest]
        prev_metrics = month_metrics.get(previous, {})
        d_latest = latest_metrics["D"]
        sd_latest = latest_metrics["SD"]
        as_latest = latest_metrics["AS"]
        momentum = d_latest - prev_metrics.get("D", 0.0) if previous in month_metrics else 0.0
        n_mentions = latest_metrics["pos"] + latest_metrics["neg"] + latest_metrics["neutral"]

        # --- Mirror gap ---
        rpt = latest_metrics["reported_value"]
        mir = latest_metrics["mirror_value"]
        if rpt is not None and mir is not None:
            mirror_gap = 100.0 * (mir - rpt) / max(1.0, abs(rpt))
        else:
            mirror_gap = None

        # --- Confidence ---
        anchor_available = latest_metrics["anchor_growth"] is not None
        if n_mentions >= HIGH_CONFIDENCE_MENTIONS and anchor_available:
            confidence = "high"
        elif n_mentions >= MED_CONFIDENCE_MENTIONS or anchor_available:
            confidence = "med"
        else:
            confidence = "low"

        results.append({
            "sector": sector_key,
            "region": region,
            "period": _period_str(*latest),
            "D": round(d_latest, 4),
            "SD": round(sd_latest, 4),
            "AS": round(as_latest, 4),
            "momentum": round(momentum, 4),
            "mirror_gap": round(mirror_gap, 4) if mirror_gap is not None else None,
            "confidence": confidence,
            "n_mentions": n_mentions,
            "inputs": {
                "reported_value": latest_metrics["reported_value"],
                "mirror_value": latest_metrics["mirror_value"],
                "anchor_growth": latest_metrics["anchor_growth"],
                "anchor_source": latest_metrics["anchor_source"],
                "pos": latest_metrics["pos"],
                "neg": latest_metrics["neg"],
                "neutral": latest_metrics["neutral"],
            },
        })

    return results


def _build_inputs_from_db(now: datetime):
    """Query PostgreSQL and build the in-memory inputs for ``compute_conditions``.

    Returns a tuple ``(trade_series, cn_indicators, sentiment_mentions, taxonomy)``.
    Each list may be empty on database or parsing errors.
    """
    trade_series = []
    cn_indicators = []
    sentiment_mentions = []

    try:
        from api.database import SessionLocal
        from storage.models import EconomicData, SentimentScore
    except Exception as e:
        logger.warning(f"[ConditionsIndex] DB imports unavailable: {e}")
        return trade_series, cn_indicators, sentiment_mentions, _load_taxonomy()

    db = SessionLocal()
    try:
        econ_cutoff = now - timedelta(days=90)
        econ_rows = (
            db.query(EconomicData)
            .filter(
                EconomicData.source.in_(["comtrade_mirror", "cn_indicators"]),
                EconomicData.collected_at >= econ_cutoff,
            )
            .all()
        )
        for row in econ_rows:
            try:
                if row.source == "comtrade_mirror":
                    # indicator format: trade_{flow}_{hs}
                    parts = (row.indicator or "").split("_")
                    if len(parts) == 3 and parts[0] == "trade":
                        _, flow, hs = parts
                    else:
                        continue
                    meta = row.extra_data or {}
                    trade_series.append({
                        "date": row.date,
                        "flow": flow,
                        "hs": hs,
                        "value": float(row.value) if row.value is not None else None,
                        "reporter": meta.get("reporter"),
                        "partner": meta.get("partner"),
                        "net_weight": meta.get("netWeight"),
                    })
                elif row.source == "cn_indicators":
                    cn_indicators.append({
                        "date": row.date,
                        "indicator": row.indicator,
                        "value": float(row.value) if row.value is not None else None,
                    })
            except Exception as e:
                logger.warning(f"[ConditionsIndex] skipping row {row.id}: {e}")
                continue

        sent_cutoff = now - timedelta(days=30)
        sent_rows = (
            db.query(SentimentScore)
            .filter(SentimentScore.created_at >= sent_cutoff)
            .all()
        )
        for row in sent_rows:
            sector_scores = row.sector_scores or {}
            for sector_key in sector_scores.keys():
                sentiment_mentions.append({
                    "date": row.created_at,
                    "sector": sector_key,
                    "score": float(row.overall) if row.overall is not None else 0.0,
                })
    except Exception as e:
        logger.error(f"[ConditionsIndex] DB query failed: {e}")
    finally:
        db.close()

    return trade_series, cn_indicators, sentiment_mentions, _load_taxonomy()


class ConditionsIndexProcessor(BaseProcessor):
    """Aggregate processor: DB inputs → conditions index → Redis + snapshot rows."""

    name = "conditions_index"

    def process_one(self, article: dict) -> dict:
        return {"status": "use_run"}

    def run(self) -> dict:
        now = datetime.now(timezone.utc)
        trade_series, cn_indicators, sentiment_mentions, taxonomy = _build_inputs_from_db(now)

        try:
            results = compute_conditions(
                trade_series, cn_indicators, sentiment_mentions, taxonomy, now
            )
        except Exception as e:
            logger.error(f"[ConditionsIndex] compute failed: {e}")
            return {"status": "error", "error": str(e)}

        # Publish to Redis
        try:
            import redis
            payload = {
                "generated_at": now.isoformat(),
                "period": _period_str(*_latest_complete_month(now)),
                "sectors": results,
            }
            r = redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True
            )
            r.set("cbb:latest", json.dumps(payload, ensure_ascii=False), ex=7200)
            r.close()
        except Exception as e:
            logger.warning(f"[ConditionsIndex] Redis publish failed: {e}")

        # Persist snapshots
        try:
            from api.database import SessionLocal
            from storage.models import ConditionsIndexSnapshot

            db = SessionLocal()
            try:
                for res in results:
                    snap = ConditionsIndexSnapshot(
                        generated_at=now,
                        period=res.get("period"),
                        sector=res.get("sector"),
                        region=res.get("region"),
                        diffusion=res.get("D", 0.0),
                        sentiment=res.get("SD", 0.0),
                        anchor=res.get("AS", 0.0),
                        momentum=res.get("momentum", 0.0),
                        mirror_gap=res.get("mirror_gap"),
                        confidence=res.get("confidence", "low"),
                        n_mentions=res.get("n_mentions", 0),
                        inputs=res.get("inputs", {}),
                    )
                    db.add(snap)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[ConditionsIndex] snapshot persist failed: {e}")

        logger.info(f"[ConditionsIndex] computed {len(results)} sectors")
        return {
            "status": "success",
            "sectors": len(results),
            "period": _period_str(*_latest_complete_month(now)),
            "generated_at": now.isoformat(),
        }


if __name__ == "__main__":
    # Offline self-test: 2–3 synthetic months across electronics, autos, steel.
    taxonomy = {
        "sectors": {
            "electronics": {
                "hs_codes": ["85"],
                "cn_hf_sources": ["bdi"],
                "region": "coastal_export",
            },
            "autos": {
                "hs_codes": ["87"],
                "cn_hf_sources": ["ccfi"],
                "region": "coastal_export",
            },
            "steel": {
                "hs_codes": ["72"],
                "cn_hf_sources": [],
                "region": "northeast",
            },
        }
    }

    base = datetime(2024, 6, 1, tzinfo=timezone.utc)  # latest complete month = May 2024

    trade_series = [
        # March 2024 baseline
        {"date": datetime(2024, 3, 1, tzinfo=timezone.utc), "flow": "X", "hs": "85", "value": 850.0, "reporter": 156, "partner": 0},
        {"date": datetime(2024, 3, 1, tzinfo=timezone.utc), "flow": "X", "hs": "87", "value": 460.0, "reporter": 156, "partner": 0},
        {"date": datetime(2024, 3, 1, tzinfo=timezone.utc), "flow": "X", "hs": "72", "value": 320.0, "reporter": 156, "partner": 0},
        # April 2024 previous month
        {"date": datetime(2024, 4, 1, tzinfo=timezone.utc), "flow": "X", "hs": "85", "value": 900.0, "reporter": 156, "partner": 0},
        {"date": datetime(2024, 4, 1, tzinfo=timezone.utc), "flow": "X", "hs": "87", "value": 480.0, "reporter": 156, "partner": 0},
        {"date": datetime(2024, 4, 1, tzinfo=timezone.utc), "flow": "X", "hs": "72", "value": 310.0, "reporter": 156, "partner": 0},
        {"date": datetime(2024, 4, 1, tzinfo=timezone.utc), "flow": "M", "hs": "85", "value": 920.0, "reporter": 0, "partner": 156},
        # May 2024 latest month
        {"date": datetime(2024, 5, 1, tzinfo=timezone.utc), "flow": "X", "hs": "85", "value": 1000.0, "reporter": 156, "partner": 0},
        {"date": datetime(2024, 5, 1, tzinfo=timezone.utc), "flow": "X", "hs": "87", "value": 500.0, "reporter": 156, "partner": 0},
        {"date": datetime(2024, 5, 1, tzinfo=timezone.utc), "flow": "X", "hs": "72", "value": 300.0, "reporter": 156, "partner": 0},
        {"date": datetime(2024, 5, 1, tzinfo=timezone.utc), "flow": "M", "hs": "85", "value": 1050.0, "reporter": 0, "partner": 156},
    ]

    cn_indicators = [
        {"date": datetime(2024, 4, 1, tzinfo=timezone.utc), "indicator": "bdi", "value": 1750.0},
        {"date": datetime(2024, 5, 1, tzinfo=timezone.utc), "indicator": "bdi", "value": 1800.0},
        {"date": datetime(2024, 4, 1, tzinfo=timezone.utc), "indicator": "ccfi", "value": 880.0},
        {"date": datetime(2024, 5, 1, tzinfo=timezone.utc), "indicator": "ccfi", "value": 900.0},
    ]

    sentiment_mentions = [
        # April
        {"date": datetime(2024, 4, 5, tzinfo=timezone.utc), "sector": "electronics", "score": 0.20},
        {"date": datetime(2024, 4, 6, tzinfo=timezone.utc), "sector": "electronics", "score": -0.05},
        {"date": datetime(2024, 4, 7, tzinfo=timezone.utc), "sector": "autos", "score": 0.30},
        {"date": datetime(2024, 4, 8, tzinfo=timezone.utc), "sector": "steel", "score": -0.25},
        # May
        {"date": datetime(2024, 5, 5, tzinfo=timezone.utc), "sector": "electronics", "score": 0.35},
        {"date": datetime(2024, 5, 6, tzinfo=timezone.utc), "sector": "electronics", "score": 0.10},
        {"date": datetime(2024, 5, 7, tzinfo=timezone.utc), "sector": "electronics", "score": -0.20},
        {"date": datetime(2024, 5, 8, tzinfo=timezone.utc), "sector": "autos", "score": 0.25},
        {"date": datetime(2024, 5, 9, tzinfo=timezone.utc), "sector": "autos", "score": 0.05},
        {"date": datetime(2024, 5, 10, tzinfo=timezone.utc), "sector": "steel", "score": -0.10},
    ]

    results = compute_conditions(trade_series, cn_indicators, sentiment_mentions, taxonomy, base)

    print("\nChina Economic Conditions Index (offline self-test)")
    print("=" * 95)
    print(f"{'Sector':<14} {'Region':<16} {'Period':<8} {'D':>8} {'SD':>8} {'AS':>8} {'Mom':>7} {'Gap':>8} {'Conf':>5} {'N':>4}")
    print("-" * 95)
    for r in results:
        gap = f"{r['mirror_gap']:.1f}" if r["mirror_gap"] is not None else "-"
        mom_arrow = "▲" if r["momentum"] > 0.5 else ("▼" if r["momentum"] < -0.5 else "▬")
        print(
            f"{r['sector']:<14} {r['region']:<16} {r['period']:<8} "
            f"{r['D']:>8.2f} {r['SD']:>8.2f} {r['AS']:>8.2f} "
            f"{mom_arrow} {r['momentum']:>5.2f} {gap:>8} {r['confidence']:>5} {r['n_mentions']:>4}"
        )
    print("=" * 95)
