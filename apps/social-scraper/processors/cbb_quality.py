"""Per-source data-quality validation for China Beige-Book-style sources.

Validates rows destined for the ``EconomicData`` table from:

* ``collectors/comtrade_mirror.py``  -> ``source = "comtrade_mirror"``
* ``collectors/cn_indicators.py``    -> ``source = "cn_indicators"``

The module is importable and runnable without a database; it accepts plain
dicts and returns JSON-serialisable reports.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ── Config paths (relative to project root) ──────────────────────────
_CATALOG_PATH = Path(__file__).resolve().parent.parent / "config" / "cn_hf_sources.json"


# ── Frequency helpers ────────────────────────────────────────────────

_FREQUENCY_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 91,
    "annual": 365,
    "yearly": 365,
}

_DEFAULT_FREQUENCY_DAYS = 30


def _frequency_to_days(freq: Optional[str]) -> int:
    """Map a catalog frequency string to an approximate number of days."""
    if not freq:
        return _DEFAULT_FREQUENCY_DAYS
    return _FREQUENCY_DAYS.get(str(freq).lower().strip(), _DEFAULT_FREQUENCY_DAYS)


# ── Date / value parsing helpers ─────────────────────────────────────

def _to_datetime(value: Any) -> Optional[datetime]:
    """Convert a raw date value to a timezone-aware UTC datetime."""
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        try:
            return datetime(int(value), 1, 1, tzinfo=timezone.utc)
        except (ValueError, OverflowError):
            return None

    s = str(value).strip()
    if not s:
        return None

    # ISO / pandas timestamp.
    try:
        parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass

    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def _is_numeric(value: Any) -> bool:
    """Return True if value is a finite int or float (bools are excluded)."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    s = str(value).strip().replace(",", "")
    if s.lower() in ("", ".", "-", "nd", "na", "n/a", "null", "none"):
        return False
    try:
        return math.isfinite(float(s))
    except ValueError:
        return False


# ── Schema helpers ───────────────────────────────────────────────────

def _check_schema(row: dict, idx: int) -> list[str]:
    """Return a list of human-readable schema errors for one row."""
    errors: list[str] = []
    required = ("source", "indicator", "date", "value")
    for field in required:
        if field not in row or row[field] is None or row[field] == "":
            errors.append(f"row {idx}: missing required field '{field}'")

    if "value" in row and not _is_numeric(row["value"]):
        errors.append(f"row {idx}: 'value' is not numeric ({row.get('value')!r})")

    if "date" in row:
        parsed_date = _to_datetime(row["date"])
        if parsed_date is None:
            errors.append(f"row {idx}: 'date' is not parseable ({row.get('date')!r})")

    return errors


def _load_cn_catalog() -> list[dict]:
    """Load the cn_indicators catalog from config/cn_hf_sources.json."""
    try:
        if _CATALOG_PATH.exists():
            data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("sources", []) or data.get("enabled_sources", []) or []
            if isinstance(data, list):
                return data
    except Exception:
        return []
    return []


# ── Source validators ────────────────────────────────────────────────

def validate_comtrade(rows: list[dict], now: Optional[datetime] = None, freshness_days: int = 7) -> dict:
    """Validate a batch of ``comtrade_mirror`` rows.

    Checks:
    * Required fields: ``source``, ``indicator``, ``date``, ``value``.
    * ``value`` is numeric and finite.
    * ``date`` is parseable.
    * Freshness: the most recent ``collected_at`` (or ``date`` if absent)
      is within ``freshness_days`` of ``now``.

    Returns a JSON-serialisable report dict.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    schema_errors: list[str] = []
    bad_rows = 0

    for idx, row in enumerate(rows):
        row_errors = _check_schema(row, idx)
        if row_errors:
            schema_errors.extend(row_errors)
            bad_rows += 1

    schema_ok = len(rows) == 0 or bad_rows == 0

    # Freshness is driven by the most recent collection time if available,
    # otherwise by the most recent observation date.  This matches the
    # comtrade_mirror schedule (every 6 hours) while still tolerating
    # monthly observation dates.
    latest_collected_at: Optional[datetime] = None
    latest_date: Optional[datetime] = None
    for row in rows:
        if "collected_at" in row:
            ts = _to_datetime(row["collected_at"])
            if ts is not None and (latest_collected_at is None or ts > latest_collected_at):
                latest_collected_at = ts
        if "date" in row:
            d = _to_datetime(row["date"])
            if d is not None and (latest_date is None or d > latest_date):
                latest_date = d

    freshness_timestamp = latest_collected_at if latest_collected_at is not None else latest_date

    if freshness_timestamp is None:
        freshness_age_days = None
        freshness_ok = len(rows) == 0  # Empty batch is trivially fresh.
    else:
        age = now - freshness_timestamp
        freshness_age_days = age.total_seconds() / 86400.0
        freshness_ok = freshness_age_days <= freshness_days

    return {
        "source": "comtrade_mirror",
        "row_count": len(rows),
        "schema_valid": schema_ok,
        "schema_errors": schema_errors,
        "bad_rows": bad_rows,
        "freshness_valid": freshness_ok,
        "freshness_threshold_days": freshness_days,
        "freshness_age_days": freshness_age_days,
        "latest_timestamp": freshness_timestamp.isoformat() if freshness_timestamp else None,
    }


def validate_cn_indicators(
    rows: list[dict],
    catalog: Optional[list[dict]] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Validate a batch of ``cn_indicators`` rows.

    Rows are grouped by ``indicator``.  For each indicator the catalog is
    consulted for ``frequency``; freshness is checked so that the latest
    observation is not older than ``frequency * 2``.

    ``catalog`` should be the list of source dicts from
    ``config/cn_hf_sources.json``.  If omitted, the file is loaded on disk;
    if it is unavailable an empty catalog is used and every indicator is
    reported as ``catalog_missing``.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if catalog is None:
        catalog = _load_cn_catalog()

    freq_by_indicator = {
        item.get("key", item.get("indicator")): item.get("frequency", "unknown")
        for item in catalog
    }

    # Group rows by indicator.
    grouped: dict[str, list[dict]] = defaultdict(list)
    schema_errors: list[str] = []
    bad_rows = 0

    for idx, row in enumerate(rows):
        schema_row_errors = _check_schema(row, idx)
        if schema_row_errors:
            schema_errors.extend(schema_row_errors)
            bad_rows += 1
        indicator = str(row.get("indicator", "__unknown__"))
        grouped[indicator].append(row)

    schema_ok = len(rows) == 0 or bad_rows == 0

    indicator_reports: dict[str, dict] = {}
    overall_freshness_ok = True

    for indicator, group_rows in grouped.items():
        latest_date: Optional[datetime] = None
        for row in group_rows:
            d = _to_datetime(row.get("date"))
            if d is not None and (latest_date is None or d > latest_date):
                latest_date = d

        freq = freq_by_indicator.get(indicator, "unknown")
        freq_days = _frequency_to_days(freq)
        threshold_days = freq_days * 2

        if latest_date is None:
            age_days = None
            fresh = False
        else:
            age = now - latest_date
            age_days = age.total_seconds() / 86400.0
            fresh = age_days <= threshold_days

        if not fresh:
            overall_freshness_ok = False

        indicator_reports[indicator] = {
            "row_count": len(group_rows),
            "catalog_frequency": freq,
            "freshness_threshold_days": threshold_days,
            "freshness_age_days": age_days,
            "latest_date": latest_date.isoformat() if latest_date else None,
            "freshness_valid": fresh,
            "catalog_missing": indicator not in freq_by_indicator,
        }

    freshness_ok = len(rows) == 0 or overall_freshness_ok

    return {
        "source": "cn_indicators",
        "row_count": len(rows),
        "schema_valid": schema_ok,
        "schema_errors": schema_errors,
        "bad_rows": bad_rows,
        "freshness_valid": freshness_ok,
        "indicators": indicator_reports,
    }


# ── Overall runner ───────────────────────────────────────────────────

def run_quality_report(rows: list[dict], now: Optional[datetime] = None) -> dict:
    """Run quality validation on a mixed list of EconomicData rows.

    Rows are routed by their ``source`` field.  The report contains an
    overall status plus per-source sub-reports from the dedicated validators.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    comtrade_rows = [r for r in rows if r.get("source") == "comtrade_mirror"]
    cn_rows = [r for r in rows if r.get("source") == "cn_indicators"]
    other_rows = [r for r in rows if r.get("source") not in ("comtrade_mirror", "cn_indicators")]

    catalog = _load_cn_catalog()

    comtrade_report = validate_comtrade(comtrade_rows, now=now)
    cn_report = validate_cn_indicators(cn_rows, catalog=catalog, now=now)

    reports = {}
    if comtrade_rows or any(r.get("source") == "comtrade_mirror" for r in rows):
        reports["comtrade_mirror"] = comtrade_report
    if cn_rows or any(r.get("source") == "cn_indicators" for r in rows):
        reports["cn_indicators"] = cn_report

    # Overall status.
    flags = []
    for rep in reports.values():
        if not rep.get("schema_valid"):
            flags.append("schema_error")
        if not rep.get("freshness_valid"):
            flags.append("stale")

    if not reports:
        status = "empty"
    elif "schema_error" in flags:
        status = "fail"
    elif "stale" in flags:
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "generated_at": now.isoformat(),
        "total_rows": len(rows),
        "row_counts": {
            "comtrade_mirror": len(comtrade_rows),
            "cn_indicators": len(cn_rows),
            "other": len(other_rows),
        },
        "sources": reports,
    }


# ── Synthetic fixtures / CLI ─────────────────────────────────────────

def _synthetic_rows() -> list[dict]:
    """Return a small set of offline fixture rows for manual testing."""
    now = datetime.now(timezone.utc)

    comtrade_fresh = {
        "source": "comtrade_mirror",
        "indicator": "trade_X_84",
        "date": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        "value": 1_200_000.0,
        "collected_at": now,
        "extra_data": {"hs": "84", "flow": "X", "view": "reported"},
    }
    comtrade_stale = {
        "source": "comtrade_mirror",
        "indicator": "trade_M_85",
        "date": now.replace(year=now.year - 1, day=1, hour=0, minute=0, second=0, microsecond=0),
        "value": 800_000.0,
        "collected_at": now.replace(year=now.year - 1),
        "extra_data": {"hs": "85", "flow": "M", "view": "reported"},
    }
    cn_fresh = {
        "source": "cn_indicators",
        "indicator": "ccfi",
        "date": now,
        "value": 1234.5,
        "collected_at": now,
        "extra_data": {"sector": "transport_logistics", "frequency": "weekly"},
    }
    cn_stale = {
        "source": "cn_indicators",
        "indicator": "bdi",
        "date": now.replace(day=1) if now.day > 5 else now.replace(month=now.month - 1 or 12, day=1),
        "value": 1500.0,
        "collected_at": now,
        "extra_data": {"sector": "transport_logistics", "frequency": "daily"},
    }
    cn_bad_value = {
        "source": "cn_indicators",
        "indicator": "macro_customs",
        "date": now.replace(day=1),
        "value": "not_a_number",
        "collected_at": now,
    }
    return [comtrade_fresh, comtrade_stale, cn_fresh, cn_stale, cn_bad_value]


def _load_sample_data() -> list[dict]:
    """Try to load real EconomicData-shaped rows from data/cbb/, else return fixtures."""
    sample_dir = Path(__file__).resolve().parent.parent / "data" / "cbb"
    candidates = [
        sample_dir / "economic_data.jsonl",
        sample_dir / "rows.jsonl",
    ]
    for path in candidates:
        if path.exists():
            try:
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if rows:
                    return rows
            except Exception:
                continue
    return _synthetic_rows()


if __name__ == "__main__":
    import json as _json

    rows = _load_sample_data()
    report = run_quality_report(rows)
    print(_json.dumps(report, indent=2, default=str))
