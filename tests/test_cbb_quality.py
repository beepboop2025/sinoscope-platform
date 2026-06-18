"""Offline tests for the CBB per-source quality validator."""

from datetime import datetime, timedelta, timezone

import pytest

from processors.cbb_quality import (
    _frequency_to_days,
    _is_numeric,
    _to_datetime,
    run_quality_report,
    validate_cn_indicators,
    validate_comtrade,
)


# ── Helpers ─────────────────────────────────────────────────────────

def _dt(days_offset: float = 0.0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days_offset)


# ── Low-level helper tests ──────────────────────────────────────────

def test_to_datetime_parses_iso_and_variants():
    assert _to_datetime("2024-03-15") == datetime(2024, 3, 15, tzinfo=timezone.utc)
    assert _to_datetime("2024-03") == datetime(2024, 3, 1, tzinfo=timezone.utc)
    assert _to_datetime("2024") == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert _to_datetime("2024-03-15T12:00:00Z") == datetime(
        2024, 3, 15, 12, 0, tzinfo=timezone.utc
    )
    assert _to_datetime(datetime(2024, 3, 15, tzinfo=timezone.utc)) == datetime(
        2024, 3, 15, tzinfo=timezone.utc
    )
    assert _to_datetime("not-a-date") is None


def test_is_numeric_rejects_bools_and_strings():
    assert _is_numeric(1.5) is True
    assert _is_numeric(42) is True
    assert _is_numeric("1,234.5") is True
    assert _is_numeric(True) is False
    assert _is_numeric("n/a") is False
    assert _is_numeric(float("nan")) is False


def test_frequency_to_days():
    assert _frequency_to_days("daily") == 1
    assert _frequency_to_days("weekly") == 7
    assert _frequency_to_days("monthly") == 30
    assert _frequency_to_days("annual") == 365
    assert _frequency_to_days("unknown") == 30
    assert _frequency_to_days(None) == 30


# ── validate_comtrade tests ─────────────────────────────────────────

def test_validate_comtrade_passes_fresh_rows():
    now = _dt()
    rows = [
        {
            "source": "comtrade_mirror",
            "indicator": "trade_X_84",
            "date": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            "value": 1_000_000.0,
            "collected_at": now,
        }
    ]
    report = validate_comtrade(rows, now=now)
    assert report["schema_valid"] is True
    assert report["freshness_valid"] is True
    assert report["bad_rows"] == 0


def test_validate_comtrade_detects_stale_collected_at():
    now = _dt()
    rows = [
        {
            "source": "comtrade_mirror",
            "indicator": "trade_X_84",
            "date": now.replace(day=1),
            "value": 1_000_000.0,
            "collected_at": now - timedelta(days=10),
        }
    ]
    report = validate_comtrade(rows, now=now)
    assert report["freshness_valid"] is False
    assert report["freshness_age_days"] > 7


def test_validate_comtrade_reports_schema_errors():
    now = _dt()
    rows = [
        {"source": "comtrade_mirror", "indicator": "trade_X_84", "date": now, "value": "bad"},
        {"source": "comtrade_mirror", "indicator": "trade_M_85", "date": "not-a-date", "value": 100.0},
        {"source": "comtrade_mirror", "indicator": "trade_M_85"},  # missing date/value
    ]
    report = validate_comtrade(rows, now=now)
    assert report["schema_valid"] is False
    assert report["bad_rows"] == 3
    assert any("not numeric" in e for e in report["schema_errors"])
    assert any("not parseable" in e for e in report["schema_errors"])


def test_validate_comtrade_empty_is_trivially_ok():
    now = _dt()
    report = validate_comtrade([], now=now)
    assert report["schema_valid"] is True
    assert report["freshness_valid"] is True
    assert report["row_count"] == 0


# ── validate_cn_indicators tests ────────────────────────────────────

def test_validate_cn_indicators_fresh_and_stale():
    now = _dt()
    catalog = [
        {"key": "ccfi", "frequency": "weekly"},
        {"key": "bdi", "frequency": "daily"},
    ]
    rows = [
        {"source": "cn_indicators", "indicator": "ccfi", "date": now, "value": 1000.0},
        {
            "source": "cn_indicators",
            "indicator": "bdi",
            "date": now - timedelta(days=5),
            "value": 1500.0,
        },
    ]
    report = validate_cn_indicators(rows, catalog=catalog, now=now)
    assert report["schema_valid"] is True
    assert report["indicators"]["ccfi"]["freshness_valid"] is True
    assert report["indicators"]["bdi"]["freshness_valid"] is False
    assert report["freshness_valid"] is False
    assert report["indicators"]["ccfi"]["freshness_threshold_days"] == 14
    assert report["indicators"]["bdi"]["freshness_threshold_days"] == 2


def test_validate_cn_indicators_missing_catalog():
    now = _dt()
    rows = [
        {"source": "cn_indicators", "indicator": "new_indicator", "date": now, "value": 1.0},
    ]
    report = validate_cn_indicators(rows, catalog=[], now=now)
    assert report["indicators"]["new_indicator"]["catalog_missing"] is True
    assert report["indicators"]["new_indicator"]["catalog_frequency"] == "unknown"


def test_validate_cn_indicators_schema_error():
    now = _dt()
    catalog = [{"key": "ccfi", "frequency": "weekly"}]
    rows = [
        {"source": "cn_indicators", "indicator": "ccfi", "date": now, "value": None},
    ]
    report = validate_cn_indicators(rows, catalog=catalog, now=now)
    assert report["schema_valid"] is False
    assert report["bad_rows"] == 1


# ── run_quality_report tests ────────────────────────────────────────

def test_run_quality_report_routes_and_overall_ok():
    now = _dt()
    rows = [
        {"source": "comtrade_mirror", "indicator": "trade_X_84", "date": now, "value": 1.0},
        {"source": "cn_indicators", "indicator": "ccfi", "date": now, "value": 1.0},
    ]
    report = run_quality_report(rows, now=now)
    assert report["status"] == "ok"
    assert report["row_counts"]["comtrade_mirror"] == 1
    assert report["row_counts"]["cn_indicators"] == 1
    assert "comtrade_mirror" in report["sources"]
    assert "cn_indicators" in report["sources"]


def test_run_quality_report_overall_fail_on_schema_error():
    now = _dt()
    rows = [
        {"source": "comtrade_mirror", "indicator": "trade_X_84", "date": now, "value": "bad"},
    ]
    report = run_quality_report(rows, now=now)
    assert report["status"] == "fail"


def test_run_quality_report_overall_degraded_on_stale():
    now = _dt()
    rows = [
        {
            "source": "comtrade_mirror",
            "indicator": "trade_X_84",
            "date": now,
            "value": 1.0,
            "collected_at": now - timedelta(days=10),
        },
    ]
    report = run_quality_report(rows, now=now)
    assert report["status"] == "degraded"
