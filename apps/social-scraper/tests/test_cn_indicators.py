"""Unit tests for the cn_indicators collector.

All network calls and DB dependencies are mocked; tests run offline.
"""

import json
import math
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from collectors.cn_indicators import (
    CNIndicatorsCollector,
    _CUSTOM_PARSERS,
    _parse_chinadata_series,
    _parse_sse_freight,
)


# ── Helpers ─────────────────────────────────────────────────────────

def _mock_response(status_code: int = 200, json_data=None, text: str = ""):
    """Build an httpx-style async response mock.

    ``json()`` is synchronous on ``httpx.Response``, so a regular MagicMock is used.
    """
    resp = AsyncMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data if json_data is not None else {})
    resp.text = text
    return resp


def _http_client(responses: dict[str, AsyncMock]) -> AsyncMock:
    """AsyncMock client with a keyed get() side effect."""
    async def _get(url: str, **kwargs):
        return responses.get(url, _mock_response(status_code=404))

    client = AsyncMock()
    client.get = _get
    client.post = AsyncMock(return_value=_mock_response(status_code=405))
    client.aclose = AsyncMock()
    return client


# ── Custom parser unit tests ────────────────────────────────────────

def test_parse_sse_freight_composite_emits_current_and_prior():
    payload = {
        "data": {
            "currentDate": "2024-01-05",
            "lastDate": "2023-12-29",
            "lineDataList": [
                {
                    "dataItemTypeName": "CCFI_T",
                    "currentContent": 1000.5,
                    "lastContent": 990.0,
                    "properties": {"lineName_EN": "COMPOSITE INDEX"},
                },
                {
                    "dataItemTypeName": "ROUTE_EUROPE",
                    "currentContent": 1200.0,
                    "properties": {"lineName_EN": "EUROPE"},
                },
            ],
        }
    }
    rows = _parse_sse_freight(payload)
    assert len(rows) == 2
    assert rows[0] == {"date": "2024-01-05", "value": 1000.5, "line": "COMPOSITE"}
    assert rows[1] == {"date": "2023-12-29", "value": 990.0, "line": "COMPOSITE"}


def test_parse_sse_freight_fallback_to_first_line():
    payload = {
        "data": {
            "currentDate": "2024-01-05",
            "lineDataList": [
                {
                    "dataItemTypeName": "ROUTE_MED",
                    "currentContent": 850.0,
                    "properties": {"lineName_EN": "MEDITERRANEAN"},
                }
            ],
        }
    }
    rows = _parse_sse_freight(payload)
    assert len(rows) == 1
    assert rows[0]["line"] == "ROUTE_MED"


def test_parse_sse_freight_empty_payload():
    assert _parse_sse_freight(None) == []
    assert _parse_sse_freight({}) == []
    assert _parse_sse_freight({"data": {"lineDataList": []}}) == []


def test_parse_chinadata_series_exports_and_extra_metrics():
    payload = {
        "data": {
            "data": [
                {"date": "2024-01", "total": 100.0, "export": 60.0, "import": 40.0, "balance": 20.0},
                {"date": "2024-02", "total": 110.0, "export": 65.0, "import": 45.0, "balance": 20.0},
            ]
        }
    }
    rows = _parse_chinadata_series(payload)
    assert len(rows) == 2
    assert rows[0]["date"] == "2024-01"
    assert rows[0]["value"] == 60.0
    assert rows[0]["export"] == 60.0
    assert rows[0]["total"] == 100.0


def test_parse_chinadata_series_uses_value_key():
    payload = {
        "data": {
            "data": [
                {"date": "2024-01", "total": 100.0, "export": 60.0},
            ]
        }
    }
    rows = _parse_chinadata_series(payload, value_key="total")
    assert rows[0]["value"] == 100.0


def test_parse_chinadata_series_empty_and_malformed_rows():
    assert _parse_chinadata_series(None) == []
    assert _parse_chinadata_series({"data": {"data": []}}) == []
    assert _parse_chinadata_series({"data": {"data": ["not-a-dict"]}}) == []


def test_custom_parsers_registry_keys():
    assert set(_CUSTOM_PARSERS.keys()) == {"ccfi", "scfi", "macro_customs"}


# ── Normalization unit tests ────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        (2024, datetime(2024, 1, 1, tzinfo=timezone.utc)),
        (2024.0, datetime(2024, 1, 1, tzinfo=timezone.utc)),
        # ISO date-only strings parse as *naive* datetimes; documented edge case.
        ("2024-03-15", datetime(2024, 3, 15)),
        ("2024-03", datetime(2024, 3, 1, tzinfo=timezone.utc)),
        ("2024", datetime(2024, 1, 1, tzinfo=timezone.utc)),
        ("2024/03/15", datetime(2024, 3, 15, tzinfo=timezone.utc)),
        ("15-03-2024", datetime(2024, 3, 15, tzinfo=timezone.utc)),
        ("2024-03-15T08:30:00Z", datetime(2024, 3, 15, 8, 30, tzinfo=timezone.utc)),
        (datetime(2024, 3, 15, 8, 30), datetime(2024, 3, 15, 8, 30, tzinfo=timezone.utc)),
        (datetime(2024, 3, 15, 8, 30, tzinfo=timezone.utc), datetime(2024, 3, 15, 8, 30, tzinfo=timezone.utc)),
        ("not-a-date", None),
        (float("inf"), None),
        (True, None),  # bool is int subclass; should be rejected by iso/int paths
    ],
)
def test_normalize_date(raw, expected):
    assert CNIndicatorsCollector._normalize_date(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        (True, None),
        (False, None),
        (42, 42.0),
        (-3.5, -3.5),
        ("1,234.56", 1234.56),
        ("  78.9  ", 78.9),
        ("", None),
        (".", None),
        ("-", None),
        ("nd", None),
        ("NA", None),
        ("n/a", None),
        ("null", None),
        ("None", None),
        (float("nan"), None),
        (float("inf"), None),
        ("abc", None),
    ],
)
def test_normalize_value(raw, expected):
    result = CNIndicatorsCollector._normalize_value(raw)
    if expected is None:
        assert result is None
    elif math.isnan(expected):
        assert result is None
    else:
        assert result == expected


# ── Nested path helper ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "data,path,expected",
    [
        ({"a": {"b": 1}}, "a.b", 1),
        ({"a": [{"b": 2}]}, "a.0.b", 2),
        ({"a": [10, 20]}, "a.1", 20),
        ({"a": {"b": 1}}, "a.c", None),
        ({"a": {"b": 1}}, "a.b.c", None),
        ({"a": {"b": 1}}, "x", None),
        ([{"a": 1}], "0.a", 1),
        ({"a": {"b": 1}}, None, {"a": {"b": 1}}),
        ({"a": {"b": 1}}, "", {"a": {"b": 1}}),
    ],
)
def test_get_nested(data, path, expected):
    assert CNIndicatorsCollector._get_nested(data, path) == expected


# ── Source normalization and catalog loading ────────────────────────

def test_normalize_source_maps_access_method():
    src = {"key": "k", "access_method": "todo"}
    norm = CNIndicatorsCollector._normalize_source(src)
    assert norm["access"] == "todo"
    assert norm["method"] == "GET"
    assert norm["parser"] == "json"
    assert norm["date_field"] == "date"
    assert norm["value_field"] == "value"


def test_load_catalog_reads_dict_and_list(tmp_path):
    dict_catalog = tmp_path / "cn_hf_sources.json"
    dict_catalog.write_text(json.dumps({"sources": [{"key": "x"}]}))
    with patch("collectors.cn_indicators._CATALOG_PATH", dict_catalog):
        assert CNIndicatorsCollector._load_catalog() == [{"key": "x"}]

    list_catalog = tmp_path / "list_sources.json"
    list_catalog.write_text(json.dumps([{"key": "y"}]))
    with patch("collectors.cn_indicators._CATALOG_PATH", list_catalog):
        assert CNIndicatorsCollector._load_catalog() == [{"key": "y"}]


def test_load_catalog_missing_file_returns_empty(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with patch("collectors.cn_indicators._CATALOG_PATH", missing):
        assert CNIndicatorsCollector._load_catalog() == []


# ── Collection flow (async) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_skips_todo_sources(caplog):
    caplog.set_level("INFO")
    collector = CNIndicatorsCollector(
        {"enabled_sources": [{"key": "bdi", "access": "todo", "note": "needs scraper"}]}
    )
    collector._http = _http_client({})
    records = await collector.collect()
    assert records == []
    assert "TODO: bdi" in caplog.text


@pytest.mark.asyncio
async def test_collect_open_json_with_nested_path():
    url = "https://api.worldbank.org/v2/country/CHN/indicator/NY.GDP.MKTP.CD"
    collector = CNIndicatorsCollector(
        {
            "enabled_sources": [
                {
                    "key": "wb_chn_gdp",
                    "name_en": "World Bank China GDP",
                    "name_zh": "世界银行中国GDP",
                    "url": url,
                    "access": "open_json",
                    "parser": "json",
                    "json_path": "1",
                    "date_field": "date",
                    "value_field": "value",
                    "unit": "USD",
                    "sector": "macro",
                    "frequency": "annual",
                }
            ]
        }
    )
    collector._http = _http_client(
        {
            url: _mock_response(
                json_data=[{"indicator": {"id": "NY.GDP.MKTP.CD"}}, [{"date": 2022, "value": 17963.2}, {"date": 2021, "value": 17734.1}]]
            )
        }
    )
    records = await collector.collect()
    assert len(records) == 2
    assert records[0]["key"] == "wb_chn_gdp"
    assert records[0]["value"] == 17963.2
    assert records[0]["date"] == datetime(2022, 1, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_collect_open_json_with_custom_parser():
    url = "https://en.sse.net.cn/currentIndex?indexName=ccfi"
    collector = CNIndicatorsCollector(
        {
            "enabled_sources": [
                {
                    "key": "ccfi",
                    "name_en": "CCFI",
                    "name_zh": "中国出口集装箱运价指数",
                    "url": url,
                    "access": "open_json",
                    "parser": "json",
                    "date_field": "date",
                    "value_field": "value",
                    "unit": "points",
                    "sector": "transport_logistics",
                    "frequency": "weekly",
                }
            ]
        }
    )
    collector._http = _http_client(
        {
            url: _mock_response(
                json_data={
                    "data": {
                        "currentDate": "2024-01-05",
                        "lastDate": "2023-12-29",
                        "lineDataList": [
                            {
                                "dataItemTypeName": "CCFI_T",
                                "currentContent": 1000.0,
                                "lastContent": 990.0,
                                "properties": {"lineName_EN": "COMPOSITE INDEX"},
                            }
                        ],
                    }
                }
            )
        }
    )
    records = await collector.collect()
    assert len(records) == 2
    assert {r["date"] for r in records} == {datetime(2024, 1, 5), datetime(2023, 12, 29)}
    assert all(r["key"] == "ccfi" for r in records)


@pytest.mark.asyncio
async def test_collect_csv_parser():
    url = "https://example.com/data.csv"
    collector = CNIndicatorsCollector(
        {
            "enabled_sources": [
                {
                    "key": "csv_demo",
                    "name_en": "CSV Demo",
                    "name_zh": "CSV演示",
                    "url": url,
                    "access": "open_csv",
                    "parser": "csv",
                    "date_field": "date",
                    "value_field": "value",
                    "unit": "",
                    "sector": "macro",
                    "frequency": "daily",
                }
            ]
        }
    )
    collector._http = _http_client({url: _mock_response(text="date,value\n2024-03-15,123.45\n2024-03-16,130.00")})
    records = await collector.collect()
    assert len(records) == 2
    # Date-only CSV strings are parsed as naive datetimes by the current pipeline.
    assert records[0]["date"] == datetime(2024, 3, 15)
    assert records[0]["value"] == 123.45


@pytest.mark.asyncio
async def test_collect_non_200_returns_empty(caplog):
    url = "https://example.com/bad"
    collector = CNIndicatorsCollector(
        {
            "enabled_sources": [
                {
                    "key": "bad_source",
                    "name_en": "Bad Source",
                    "name_zh": "坏源",
                    "url": url,
                    "access": "open_json",
                    "parser": "json",
                    "date_field": "date",
                    "value_field": "value",
                    "unit": "",
                    "sector": "macro",
                    "frequency": "daily",
                }
            ]
        }
    )
    collector._http = _http_client({url: _mock_response(status_code=500)})
    records = await collector.collect()
    assert records == []
    assert "non-200 status 500" in caplog.text


@pytest.mark.asyncio
async def test_collect_fetch_exception_is_graceful(caplog):
    collector = CNIndicatorsCollector(
        {
            "enabled_sources": [
                {
                    "key": "explode",
                    "name_en": "Explode",
                    "name_zh": "爆炸",
                    "url": "https://example.com/x",
                    "access": "open_json",
                    "parser": "json",
                    "date_field": "date",
                    "value_field": "value",
                    "unit": "",
                    "sector": "macro",
                    "frequency": "daily",
                }
            ]
        }
    )

    async def boom(*args, **kwargs):
        raise RuntimeError("network down")

    client = AsyncMock()
    client.get = boom
    client.aclose = AsyncMock()
    collector._http = client
    records = await collector.collect()
    assert records == []
    assert "fetch/parse failed" in caplog.text


@pytest.mark.asyncio
async def test_collect_ignores_non_dict_observations():
    url = "https://example.com/list"
    collector = CNIndicatorsCollector(
        {
            "enabled_sources": [
                {
                    "key": "listy",
                    "name_en": "Listy",
                    "name_zh": "列表",
                    "url": url,
                    "access": "open_json",
                    "parser": "json",
                    "date_field": "date",
                    "value_field": "value",
                    "unit": "",
                    "sector": "macro",
                    "frequency": "daily",
                }
            ]
        }
    )
    collector._http = _http_client(
        {url: _mock_response(json_data=[{"date": "2024-01-01", "value": 1}, "bad", {"date": "2024-01-02", "value": None}])}
    )
    records = await collector.collect()
    assert len(records) == 1
    assert records[0]["date"] == datetime(2024, 1, 1)


# ── Parse / validate ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_shapes_dataframe():
    raw = [
        {
            "key": "ccfi",
            "date": datetime(2024, 1, 5, tzinfo=timezone.utc),
            "value": 1000.0,
            "unit": "points",
            "sector": "transport_logistics",
            "frequency": "weekly",
            "source_name_zh": "中国出口集装箱运价指数",
            "source_name_en": "CCFI",
            "url": "https://en.sse.net.cn/currentIndex?indexName=ccfi",
            "access": "open_json",
            "metadata_extra": {"line": "COMPOSITE"},
        }
    ]
    collector = CNIndicatorsCollector({"enabled_sources": []})
    df = await collector.parse(raw)
    assert list(df.columns) == ["indicator", "date", "value", "unit", "metadata"]
    assert df.iloc[0]["indicator"] == "ccfi"
    assert df.iloc[0]["metadata"]["sector"] == "transport_logistics"


def test_validate_requires_columns():
    collector = CNIndicatorsCollector({"enabled_sources": []})
    good = pd.DataFrame({"indicator": ["x"], "date": [datetime.now(timezone.utc)], "value": [1.0]})
    assert collector.validate(good) is True

    bad = pd.DataFrame({"indicator": ["x"], "value": [1.0]})
    from core.exceptions import SchemaChangedError

    with pytest.raises(SchemaChangedError):
        collector.validate(bad)
