"""Unit tests for the UN Comtrade mirror collector.

All network calls are mocked; tests run offline.
"""

import math
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from collectors.comtrade_mirror import ComtradeMirrorCollector
from core.exceptions import RateLimitError


# ── Inline fixtures / helpers ────────────────────────────────────────


def _make_collector(config=None):
    """Return a collector with an AsyncClient mocked at the base class."""
    cfg = config or {}
    with patch("core.base_collector.httpx.AsyncClient") as mock_client:
        mock_client.return_value = MagicMock(is_closed=False)
        collector = ComtradeMirrorCollector(cfg)
        # Tests that call _fetch directly assign a fresh mock _http below.
        return collector


def _raw_record(
    *,
    flow="M",
    period=202401,
    cmd_code="8412",
    primary_value=1234.5,
    net_weight=100.0,
    reporter_code=156,
    partner_code=0,
    mirror_reporter=None,
    original_flow=None,
):
    rec = {
        "flowCode": flow,
        "period": period,
        "cmdCode": cmd_code,
        "primaryValue": primary_value,
        "netWgt": net_weight,
        "reporterCode": reporter_code,
        "partnerCode": partner_code,
    }
    if mirror_reporter:
        rec["_mirror_reporter"] = mirror_reporter
    if original_flow:
        rec["_original_flow"] = original_flow
    return rec


def _async_http(responses):
    """Build a mock AsyncClient whose .get() returns responses in order.

    `responses` is an iterable of (status_code, json_body, headers_dict)
    triples. `json_body` may be None to simulate a non-JSON response.
    """
    seq = list(responses)
    calls = {"count": 0}

    async def _get(url, params=None, headers=None):
        idx = calls["count"]
        calls["count"] += 1
        status, body, hdrs = seq[idx] if idx < len(seq) else (200, None, {})
        resp = MagicMock()
        resp.status_code = status
        resp.url = url
        resp.headers = hdrs or {}
        if body is None:
            resp.json = MagicMock(side_effect=ValueError("not json"))
        else:
            resp.json = MagicMock(return_value=body)
        return resp

    http = MagicMock()
    http.get = AsyncMock(side_effect=_get)
    http.aclose = AsyncMock()
    return http


# ── parse() and _parse_record ────────────────────────────────────────


@pytest.mark.asyncio
async def test_parse_row_shape_reported():
    collector = _make_collector()
    raw = [_raw_record(flow="M", period=202403, cmd_code="8501", primary_value=999.0)]
    df = await collector.parse(raw)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["indicator"] == "trade_M_85"
    assert row["date"] == datetime(2024, 3, 1, tzinfo=timezone.utc)
    assert math.isclose(row["value"], 999.0)
    assert row["unit"] == "USD"

    meta = row["metadata"]
    assert meta["hs"] == "85"
    assert meta["flow"] == "M"
    assert meta["reporter"] == 156
    assert meta["partner"] == 0
    assert meta["period"] == "202403"
    assert meta["view"] == "reported"


@pytest.mark.asyncio
async def test_parse_mirror_flow_inversion():
    collector = _make_collector()
    # Partner reports an import from China (flow=M); we store it as China export.
    raw = [
        _raw_record(
            flow="M",
            period=202402,
            cmd_code="7308",
            primary_value=5000.0,
            reporter_code=842,
            partner_code=156,
        )
    ]
    df = await collector.parse(raw)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["indicator"] == "trade_X_73_mirror"
    assert row["metadata"]["flow"] == "X"
    assert row["metadata"]["original_flow"] == "M"
    assert row["metadata"]["view"] == "mirror"
    assert row["metadata"]["reporter"] == 0


@pytest.mark.asyncio
async def test_parse_aggregates_sub_commodity_rows():
    """Sub-commodity rows (HS6) under the same HS2 chapter are aggregated."""
    collector = _make_collector()
    raw = [
        _raw_record(period=202401, cmd_code="8412", primary_value=100.0, net_weight=10.0),
        _raw_record(period=202401, cmd_code="8499", primary_value=200.0, net_weight=20.0),
    ]
    df = await collector.parse(raw)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["indicator"] == "trade_M_84"
    assert math.isclose(row["value"], 300.0)
    assert math.isclose(row["metadata"]["netWeight"], 30.0)


@pytest.mark.asyncio
async def test_parse_skips_malformed_records():
    collector = _make_collector()
    raw = [
        _raw_record(period=202401, cmd_code="8412", primary_value=100.0),
        {"flowCode": "M", "period": "bad", "cmdCode": "8412", "primaryValue": 200.0},
        _raw_record(period=202401, cmd_code="8412", primary_value="nope"),
        {},
    ]
    df = await collector.parse(raw)
    assert len(df) == 1
    assert math.isclose(df.iloc[0]["value"], 100.0)


@pytest.mark.asyncio
async def test_parse_empty_input():
    collector = _make_collector()
    df = await collector.parse([])
    assert df.empty


# ── _fetch error handling ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_returns_dataset_on_success():
    collector = _make_collector()
    collector._http = _async_http([(200, {"dataset": [{"id": 1}]}, {})])

    result = await collector._fetch("http://example.com", {}, {})
    assert result == [{"id": 1}]


@pytest.mark.asyncio
async def test_fetch_handles_http_error():
    collector = _make_collector()
    collector._http = _async_http([(500, None, {})])

    result = await collector._fetch("http://example.com", {}, {})
    assert result == []


@pytest.mark.asyncio
async def test_fetch_handles_non_json_response():
    collector = _make_collector()
    collector._http = _async_http([(200, None, {})])

    result = await collector._fetch("http://example.com", {}, {})
    assert result == []


@pytest.mark.asyncio
async def test_fetch_raises_rate_limit_on_429():
    collector = _make_collector()
    collector._http = _async_http([(429, {"error": "too many"}, {"Retry-After": "30"})])

    with pytest.raises(RateLimitError) as exc:
        await collector._fetch("http://example.com", {}, {})
    assert exc.value.retry_after == 30


@pytest.mark.asyncio
async def test_fetch_graceful_on_request_exception():
    collector = _make_collector()
    collector._http = MagicMock()
    collector._http.get = AsyncMock(side_effect=ConnectionError("no route"))

    result = await collector._fetch("http://example.com", {}, {})
    assert result == []


# ── collect() integration ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_gathers_reported_and_mirror_records():
    """collect() should assemble records from both the reported and mirror loops."""
    collector = _make_collector({"recent_months": 1, "partner_reporters": [842]})

    reported_payload = {
        "dataset": [
            _raw_record(flow="M", period="202401", cmd_code="8412", primary_value=100.0),
        ]
    }
    mirror_payload = {
        "dataset": [
            _raw_record(
                flow="M",
                period="202401",
                cmd_code="8412",
                primary_value=50.0,
                reporter_code=842,
                partner_code=156,
            ),
        ]
    }
    # 2 flows * 1 period = 2 reported calls, then 2 flows * 1 period * 1 partner = 2 mirror calls.
    collector._http = _async_http(
        [
            (200, reported_payload, {}),
            (200, reported_payload, {}),
            (200, mirror_payload, {}),
            (200, mirror_payload, {}),
        ]
    )

    records = await collector.collect()
    # Each mirrored record is tagged, not duplicated; we just check non-empty.
    assert len(records) == 4
    mirror_records = [r for r in records if r.get("_mirror_reporter")]
    assert len(mirror_records) == 2


@pytest.mark.asyncio
async def test_collect_empty_responses_graceful():
    collector = _make_collector({"recent_months": 1, "partner_reporters": [842]})
    collector._http = _async_http([(200, {"dataset": []}, {})] * 4)

    records = await collector.collect()
    assert records == []


@pytest.mark.asyncio
async def test_collect_stops_on_rate_limit():
    collector = _make_collector({"recent_months": 2, "partner_reporters": [842]})
    collector._http = _async_http(
        [
            (429, {"error": "rate"}, {"Retry-After": "10"}),
        ]
    )

    records = await collector.collect()
    assert records == []


# ── validate() ───────────────────────────────────────────────────────


def test_validate_empty_dataframe():
    import pandas as pd

    collector = _make_collector()
    assert collector.validate(pd.DataFrame()) is True


def test_validate_missing_columns_raises():
    import pandas as pd

    collector = _make_collector()
    with pytest.raises(Exception):
        collector.validate(pd.DataFrame({"value": [1]}))


# ── Internal helpers ─────────────────────────────────────────────────


def test_period_to_date():
    collector = _make_collector()
    assert collector._period_to_date(202405) == datetime(
        2024, 5, 1, tzinfo=timezone.utc
    )


def test_periods_shape():
    collector = _make_collector()
    periods = collector._periods(3)
    assert len(periods) == 3
    assert all(len(p) == 6 for p in periods)


def test_endpoint():
    collector = _make_collector()
    url = collector._endpoint("202401", 156)
    assert url.endswith("C/M/HS/202401/156")


def test_params_includes_desc():
    collector = _make_collector()
    params = collector._params(flow="X", partner=0, cmd_code="84,85")
    assert params["flowCode"] == "X"
    assert params["partnerCode"] == "0"
    assert params["cmdCode"] == "84,85"
    assert params["includeDesc"] == "True"
