"""Unit tests for processors/conditions_index.py.

All DB and network dependencies are mocked; tests run offline.
"""

import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from processors.conditions_index import (
    ConditionsIndexProcessor,
    _latest_complete_month,
    _load_taxonomy,
    _norm_dt,
    _period_str,
    _prev_month,
    compute_conditions,
)


SIMPLE_TAXONOMY = {
    "sectors": {
        "electronics": {
            "hs_codes": ["85"],
            "cn_hf_sources": ["bdi"],
            "region": "coastal_export",
        }
    }
}


def _dt(*args, tz=timezone.utc):
    return datetime(*args, tzinfo=tz)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def test_norm_dt_handles_naive_and_aware():
    naive = datetime(2024, 5, 15, 10, 0, 0)
    assert _norm_dt(naive) == datetime(2024, 5, 15, 10, 0, 0, tzinfo=timezone.utc)
    aware = datetime(2024, 5, 15, 10, 0, 0, tzinfo=timezone.utc)
    assert _norm_dt(aware) == aware
    assert _norm_dt(None) is None


def test_latest_complete_month_and_prev_month():
    # June 15 -> latest complete month is May
    assert _latest_complete_month(_dt(2024, 6, 15)) == (2024, 5)
    assert _prev_month(2024, 5) == (2024, 4)
    assert _prev_month(2024, 1) == (2023, 12)
    # June 1 at 00:00 is not complete (last instant of June not reached)
    assert _latest_complete_month(_dt(2024, 6, 1)) == (2024, 5)
    # July 1 00:00 -> June is complete
    assert _latest_complete_month(_dt(2024, 7, 1)) == (2024, 6)


def test_period_str():
    assert _period_str(2024, 5) == "2024-05"


# ---------------------------------------------------------------------------
# Core diffusion math: SD / AS / D
# ---------------------------------------------------------------------------

def test_diffusion_math_with_trade_anchor():
    """D = 0.4*SD + 0.6*AS when an anchor is available."""
    now = _dt(2024, 6, 15)
    trade = [
        # April (previous)
        {"date": _dt(2024, 4, 1), "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
        # May (latest) - 10% growth
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": 110.0, "reporter": 156, "partner": 0},
    ]
    # 2 positive, 1 negative, 1 neutral -> SD = 100*(2-1)/4 = 25
    mentions = [
        {"date": _dt(2024, 5, 1), "sector": "electronics", "score": 0.20},
        {"date": _dt(2024, 5, 2), "sector": "electronics", "score": 0.25},
        {"date": _dt(2024, 5, 3), "sector": "electronics", "score": -0.20},
        {"date": _dt(2024, 5, 4), "sector": "electronics", "score": 0.05},
    ]
    results = compute_conditions(trade, [], mentions, SIMPLE_TAXONOMY, now)
    assert len(results) == 1
    r = results[0]
    expected_sd = 25.0
    expected_as = 100.0 * math.tanh(0.10 / 0.10)
    expected_d = 0.4 * expected_sd + 0.6 * expected_as
    assert r["SD"] == pytest.approx(expected_sd, 0.001)
    assert r["AS"] == pytest.approx(expected_as, 0.001)
    assert r["D"] == pytest.approx(expected_d, 0.001)


def test_diffusion_math_with_hf_anchor_fallback():
    """When trade anchor is missing, the processor falls back to CN HF indicators."""
    now = _dt(2024, 6, 15)
    indicators = [
        {"date": _dt(2024, 4, 1), "indicator": "bdi", "value": 1000.0},
        {"date": _dt(2024, 5, 1), "indicator": "bdi", "value": 1100.0},
    ]
    mentions = [
        {"date": _dt(2024, 5, 1), "sector": "electronics", "score": 0.20},
    ]
    results = compute_conditions([], indicators, mentions, SIMPLE_TAXONOMY, now)
    r = results[0]
    assert r["inputs"]["anchor_source"] == "cn_hf:bdi"
    expected_as = 100.0 * math.tanh(0.10 / 0.10)
    assert r["AS"] == pytest.approx(expected_as, 0.001)


# ---------------------------------------------------------------------------
# Momentum
# ---------------------------------------------------------------------------

def test_momentum_is_latest_minus_previous():
    now = _dt(2024, 6, 15)
    trade = [
        {"date": _dt(2024, 3, 1), "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
        {"date": _dt(2024, 4, 1), "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": 110.0, "reporter": 156, "partner": 0},
    ]
    mentions = [
        {"date": _dt(2024, 4, 1), "sector": "electronics", "score": 0.0},
        {"date": _dt(2024, 5, 1), "sector": "electronics", "score": 0.0},
    ]
    results = compute_conditions(trade, [], mentions, SIMPLE_TAXONOMY, now)
    r = results[0]
    assert r["momentum"] == pytest.approx(r["D"] - 0.0, 0.001)


def test_momentum_zero_when_unchanged():
    """When latest and previous diffusion are identical, momentum is zero."""
    now = _dt(2024, 6, 15)
    trade = [
        {"date": _dt(2024, 3, 1), "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
        {"date": _dt(2024, 4, 1), "flow": "X", "hs": "85", "value": 110.0, "reporter": 156, "partner": 0},
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": 121.0, "reporter": 156, "partner": 0},
    ]
    # Same sentiment composition for both months -> same SD, and same AS (same growth)
    mentions = [
        {"date": _dt(2024, 4, 1), "sector": "electronics", "score": 0.20},
        {"date": _dt(2024, 4, 2), "sector": "electronics", "score": -0.20},
        {"date": _dt(2024, 5, 1), "sector": "electronics", "score": 0.20},
        {"date": _dt(2024, 5, 2), "sector": "electronics", "score": -0.20},
    ]
    results = compute_conditions(trade, [], mentions, SIMPLE_TAXONOMY, now)
    r = results[0]
    # Both months have 10% growth and identical sentiment -> D equal -> momentum 0
    assert r["momentum"] == pytest.approx(0.0, 0.001)


# ---------------------------------------------------------------------------
# Mirror gap
# ---------------------------------------------------------------------------

def test_mirror_gap_calculation():
    now = _dt(2024, 6, 15)
    trade = [
        # Reported exports
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
        # Partner-reported imports from China (mirror flow)
        {"date": _dt(2024, 5, 1), "flow": "M", "hs": "85", "value": 120.0, "reporter": 0, "partner": 156},
    ]
    results = compute_conditions(trade, [], [], SIMPLE_TAXONOMY, now)
    r = results[0]
    assert r["mirror_gap"] == pytest.approx(20.0, 0.001)


def test_mirror_gap_none_when_missing():
    now = _dt(2024, 6, 15)
    trade = [
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
    ]
    results = compute_conditions(trade, [], [], SIMPLE_TAXONOMY, now)
    assert results[0]["mirror_gap"] is None


# ---------------------------------------------------------------------------
# Confidence tiers
# ---------------------------------------------------------------------------

def test_confidence_high_with_anchor_and_many_mentions():
    now = _dt(2024, 6, 15)
    trade = [
        {"date": _dt(2024, 4, 1), "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": 110.0, "reporter": 156, "partner": 0},
    ]
    mentions = [
        {"date": _dt(2024, 5, 1), "sector": "electronics", "score": 0.20}
        for _ in range(30)
    ]
    results = compute_conditions(trade, [], mentions, SIMPLE_TAXONOMY, now)
    assert results[0]["confidence"] == "high"


def test_confidence_med_with_anchor_but_few_mentions():
    now = _dt(2024, 6, 15)
    trade = [
        {"date": _dt(2024, 4, 1), "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": 110.0, "reporter": 156, "partner": 0},
    ]
    mentions = [
        {"date": _dt(2024, 5, 1), "sector": "electronics", "score": 0.20}
        for _ in range(5)
    ]
    results = compute_conditions(trade, [], mentions, SIMPLE_TAXONOMY, now)
    assert results[0]["confidence"] == "med"


def test_confidence_med_without_anchor_but_many_mentions():
    now = _dt(2024, 6, 15)
    mentions = [
        {"date": _dt(2024, 5, 1), "sector": "electronics", "score": 0.20}
        for _ in range(15)
    ]
    results = compute_conditions([], [], mentions, SIMPLE_TAXONOMY, now)
    assert results[0]["confidence"] == "med"


def test_confidence_low_without_anchor_and_few_mentions():
    now = _dt(2024, 6, 15)
    mentions = [
        {"date": _dt(2024, 5, 1), "sector": "electronics", "score": 0.20}
        for _ in range(3)
    ]
    results = compute_conditions([], [], mentions, SIMPLE_TAXONOMY, now)
    assert results[0]["confidence"] == "low"


# ---------------------------------------------------------------------------
# Empty / degenerate inputs
# ---------------------------------------------------------------------------

def test_empty_taxonomy_returns_empty():
    now = _dt(2024, 6, 15)
    assert compute_conditions([], [], [], {"sectors": {}}, now) == []


def test_empty_inputs_with_taxonomy_returns_zeroed_sectors():
    now = _dt(2024, 6, 15)
    results = compute_conditions([], [], [], SIMPLE_TAXONOMY, now)
    assert len(results) == 1
    r = results[0]
    assert r["D"] == 0.0
    assert r["SD"] == 0.0
    assert r["AS"] == 0.0
    assert r["momentum"] == 0.0
    assert r["mirror_gap"] is None
    assert r["confidence"] == "low"
    assert r["n_mentions"] == 0


def test_missing_values_skipped_gracefully():
    now = _dt(2024, 6, 15)
    trade = [
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": None, "reporter": 156, "partner": 0},
        {"date": None, "flow": "X", "hs": "85", "value": 100.0, "reporter": 156, "partner": 0},
        {"date": _dt(2024, 5, 1), "flow": "X", "hs": "85", "value": "not-a-number", "reporter": 156, "partner": 0},
    ]
    results = compute_conditions(trade, [], [], SIMPLE_TAXONOMY, now)
    assert results[0]["n_mentions"] == 0
    assert results[0]["confidence"] == "low"


# ---------------------------------------------------------------------------
# Processor wiring (DB + Redis mocked)
# ---------------------------------------------------------------------------

def test_conditions_index_processor_run_publishes_to_redis_and_persists_snapshot():
    now = _dt(2024, 6, 15)
    fake_result = {
        "sector": "electronics",
        "region": "coastal_export",
        "period": "2024-05",
        "D": 10.0,
        "SD": 5.0,
        "AS": 12.5,
        "momentum": 1.0,
        "mirror_gap": None,
        "confidence": "med",
        "n_mentions": 15,
        "inputs": {},
    }

    mock_redis = MagicMock()
    mock_redis_module = MagicMock()
    mock_redis_module.from_url.return_value = mock_redis

    mock_db = MagicMock()
    mock_session_local = MagicMock(return_value=mock_db)
    mock_api_database = MagicMock()
    mock_api_database.SessionLocal = mock_session_local

    mock_snapshot_class = MagicMock()
    mock_storage_models = MagicMock()
    mock_storage_models.ConditionsIndexSnapshot = mock_snapshot_class

    with patch(
        "processors.conditions_index._build_inputs_from_db",
        return_value=([], [], [], SIMPLE_TAXONOMY),
    ), patch(
        "processors.conditions_index.compute_conditions", return_value=[fake_result]
    ), patch(
        "processors.conditions_index._latest_complete_month", return_value=(2024, 5)
    ), patch.dict(
        sys.modules,
        {
            "redis": mock_redis_module,
            "api.database": mock_api_database,
            "storage.models": mock_storage_models,
        },
    ):
        proc = ConditionsIndexProcessor()
        result = proc.run()

        assert result["status"] == "success"
        assert result["sectors"] == 1
        assert result["period"] == "2024-05"
        mock_redis.set.assert_called_once()
        mock_redis.close.assert_called_once()
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()


def test_conditions_index_processor_run_survives_compute_error():
    with patch(
        "processors.conditions_index._build_inputs_from_db",
        return_value=([], [], [], SIMPLE_TAXONOMY),
    ), patch(
        "processors.conditions_index.compute_conditions",
        side_effect=ValueError("boom"),
    ):
        proc = ConditionsIndexProcessor()
        result = proc.run()
        assert result["status"] == "error"
        assert "boom" in result["error"]


def test_process_one_returns_use_run():
    proc = ConditionsIndexProcessor()
    assert proc.process_one({}) == {"status": "use_run"}


# ---------------------------------------------------------------------------
# Offline self-test path
# ---------------------------------------------------------------------------

def test_offline_self_test_path_runs_cleanly():
    """Execute the module's __main__ block via subprocess and verify output."""
    proc = subprocess.run(
        [sys.executable, "-m", "processors.conditions_index"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "China Economic Conditions Index (offline self-test)" in proc.stdout
    # All three sectors should be printed.
    assert "electronics" in proc.stdout
    assert "autos" in proc.stdout
    assert "steel" in proc.stdout


def test_load_taxonomy_missing_path_returns_skeleton():
    assert _load_taxonomy(Path("/does/not/exist.json")) == {"sectors": {}}
