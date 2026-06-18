"""Unit tests for processors/conditions_report.py.

All network and database dependencies are mocked so tests run offline.
"""

import json
import sys
from datetime import date, datetime, timezone
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from processors.conditions_report import ConditionsReportGenerator


def _async_return(value):
    """Return a callable that yields *value* when awaited via asyncio.run()."""
    async def _coro(**kwargs):
        return value
    return _coro


# Inject lightweight stand-ins for optional dependencies that are imported
# inside methods, so patches below resolve without installing them.
if "free_llm_router" not in sys.modules:
    sys.modules["free_llm_router"] = ModuleType("free_llm_router")
sys.modules["free_llm_router"].FreeLLMRouter = MagicMock()

if "redis" not in sys.modules:
    sys.modules["redis"] = ModuleType("redis")
sys.modules["redis"].from_url = MagicMock()

if "anthropic" not in sys.modules:
    sys.modules["anthropic"] = ModuleType("anthropic")
sys.modules["anthropic"].Anthropic = MagicMock()


@pytest.fixture
def gen() -> ConditionsReportGenerator:
    return ConditionsReportGenerator({"llm_model": "claude-test", "ollama_model": "phi-test"})


@pytest.fixture
def sample_sectors():
    return [
        {
            "sector": "electronics_machinery",
            "region": "coastal_export",
            "period": "2024-05",
            "D": 18.5,
            "SD": 12.0,
            "AS": 22.0,
            "momentum": 4.2,
            "mirror_gap": -8.3,
            "confidence": "high",
            "n_mentions": 42,
            "inputs": {
                "reported_value": 120_000_000_000.0,
                "mirror_value": 110_000_000_000.0,
                "anchor_source": "trade",
            },
        },
        {
            "sector": "property_construction",
            "region": "national",
            "period": "2024-05",
            "D": -22.1,
            "SD": -18.5,
            "AS": -25.0,
            "momentum": -6.7,
            "mirror_gap": None,
            "confidence": "med",
            "n_mentions": 18,
            "inputs": {"anchor_source": "cn_hf:bdi"},
        },
    ]


class TestBuildPrompt:
    """Context-assembly and formatting helpers."""

    def test_prompt_includes_generated_at_and_sector_count(self, gen, sample_sectors):
        prompt = gen._build_prompt(sample_sectors, "2024-05-31T12:00:00Z")
        assert "2024-05-31T12:00:00Z" in prompt
        assert "Sectors covered: 2" in prompt

    def test_prompt_includes_sector_data(self, gen, sample_sectors):
        prompt = gen._build_prompt(sample_sectors, None)
        assert "Sector: electronics_machinery" in prompt
        assert "Diffusion D=18.50" in prompt
        assert "Mirror gap=-8.30%" in prompt

    def test_prompt_omits_mirror_when_none(self, gen, sample_sectors):
        prompt = gen._build_prompt(sample_sectors, None)
        assert "Sector: property_construction" in prompt
        # The None sector should not render a Mirror gap line.
        prop_tail = prompt.split("Sector: property_construction")[1]
        next_sector = prop_tail.split("Sector:")[0]
        assert "Mirror gap" not in next_sector

    def test_prompt_handles_empty_sectors(self, gen):
        prompt = gen._build_prompt([], None)
        assert "Sectors covered: 0" in prompt
        assert "--- Sector data ---" in prompt


class TestGenerateReport:
    """LLM routing and fallback report generation."""

    def test_free_llm_router_success(self, gen, sample_sectors):
        with patch("free_llm_router.FreeLLMRouter") as mock_router:
            mock_router.return_value.chat_completion = _async_return({"text": "LLM report body"})
            prompt = gen._build_prompt(sample_sectors, None)
            report = gen._generate_report(prompt, sample_sectors, None)
            assert report == "LLM report body"

    def test_free_llm_router_empty_falls_back(self, gen, sample_sectors):
        with patch("free_llm_router.FreeLLMRouter") as mock_router:
            mock_router.return_value.chat_completion = _async_return({"text": ""})
            # No Anthropic key, and mock Ollama failure so rule-based stub runs.
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
                with patch("processors.conditions_report.httpx.post", side_effect=Exception("down")):
                    prompt = gen._build_prompt(sample_sectors, None)
                    report = gen._generate_report(prompt, sample_sectors, "2024-05-31")
                    assert "# China Economic Conditions Briefing" in report
                    assert "electronics_machinery" in report

    def test_anthropic_success(self, gen, sample_sectors):
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="Claude report")]
        with patch("free_llm_router.FreeLLMRouter") as mock_router:
            mock_router.side_effect = Exception("no router")
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
                with patch("anthropic.Anthropic") as mock_anthropic_cls:
                    mock_anthropic_cls.return_value.messages.create.return_value = mock_msg
                    prompt = gen._build_prompt(sample_sectors, None)
                    report = gen._generate_report(prompt, sample_sectors, None)
                    assert report == "Claude report"

    def test_ollama_success(self, gen, sample_sectors):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Ollama report"}
        with patch("free_llm_router.FreeLLMRouter") as mock_router:
            mock_router.side_effect = Exception("no router")
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
                with patch("processors.conditions_report.httpx.post", return_value=mock_resp):
                    prompt = gen._build_prompt(sample_sectors, None)
                    report = gen._generate_report(prompt, sample_sectors, None)
                    assert report == "Ollama report"


class TestRuleBasedReport:
    """Deterministic fallback report formatting."""

    def test_rule_based_header(self, gen, sample_sectors):
        report = gen._rule_based_report(sample_sectors, "2024-05-31T12:00:00Z")
        assert "# China Economic Conditions Briefing" in report
        assert "2024-05-31T12:00:00Z" in report

    def test_rule_based_sorts_by_absolute_momentum(self, gen):
        sectors = [
            {"sector": "a", "momentum": 1.0, "D": 0.0, "confidence": "low"},
            {"sector": "b", "momentum": -9.0, "D": 5.0, "confidence": "med"},
            {"sector": "c", "momentum": 3.0, "D": -2.0, "confidence": "high"},
        ]
        report = gen._rule_based_report(sectors, None)
        # Biggest mover should be b because abs(-9) is largest.
        movers = report.split("## Biggest movers")[1]
        first_mover = movers.strip().splitlines()[0]
        assert "b" in first_mover
        assert "momentum -9.00" in first_mover

    def test_rule_based_arrows(self, gen):
        sectors = [
            {"sector": "up", "momentum": 1.0, "D": 0.0, "confidence": "low"},
            {"sector": "down", "momentum": -1.0, "D": 0.0, "confidence": "low"},
            {"sector": "flat", "momentum": 0.0, "D": 0.0, "confidence": "low"},
        ]
        report = gen._rule_based_report(sectors, None)
        assert "▲ improving" in report
        assert "▼ weakening" in report
        assert "▬ stable" in report

    def test_rule_based_empty_sectors(self, gen):
        report = gen._rule_based_report([], None)
        assert "# China Economic Conditions Briefing" in report
        assert "## Biggest movers" not in report
        assert "Cross-source triangulation" in report


class TestWriteReport:
    """Report file I/O helpers."""

    def test_write_report_creates_dated_and_latest_files(self, gen, tmp_path, sample_sectors):
        with patch("processors.conditions_report._REPORT_DIR", tmp_path):
            today = date(2024, 5, 31)
            report_text = "# Test report"
            report_path, latest_path = gen._write_report(report_text, today)
            assert report_path.exists()
            assert latest_path.exists()
            assert report_path.read_text(encoding="utf-8") == report_text
            assert latest_path.read_text(encoding="utf-8") == report_text
            assert report_path.name == "2024-05-31.md"
            assert latest_path.name == "latest.md"


class TestEscapeMarkdown:
    """Telegram MarkdownV2 escaping."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("hello_world", "hello\\_world"),
            ("**bold**", "\\*\\*bold\\*\\*"),
            ("# title", "\\# title"),
            ("a | b", "a \\| b"),
        ],
    )
    def test_escape_markdown(self, gen, text, expected):
        assert gen._escape_markdown(text) == expected


class TestSendTelegram:
    """Telegram notification helper."""

    def test_send_telegram_skips_without_config(self, gen):
        with patch.dict("os.environ", {}, clear=True):
            with patch("processors.conditions_report.httpx.post") as mock_post:
                gen._send_telegram("report")
                mock_post.assert_not_called()

    def test_send_telegram_posts_with_config(self, gen):
        env = {"TELEGRAM_BOT_TOKEN": "bot123", "TELEGRAM_ALERT_CHAT_ID": "chat456"}
        with patch.dict("os.environ", env, clear=False):
            with patch("processors.conditions_report.httpx.post") as mock_post:
                gen._send_telegram("# Report")
                mock_post.assert_called_once()
                args, kwargs = mock_post.call_args
                assert "bot123/sendMessage" in args[0]
                assert kwargs["json"]["chat_id"] == "chat456"
                assert "parse_mode" in kwargs["json"]


class TestLoadLatestIndex:
    """Redis / DB fallback for loading the latest conditions index."""

    def test_load_latest_index_from_redis(self, gen):
        payload = {
            "generated_at": "2024-05-31T12:00:00Z",
            "sectors": [{"sector": "steel", "D": 5.0}],
        }
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(payload)
        with patch("redis.from_url", return_value=mock_redis):
            result = gen._load_latest_index(MagicMock())
            assert result["generated_at"] == "2024-05-31T12:00:00Z"
            assert result["sectors"][0]["sector"] == "steel"
            mock_redis.close.assert_called_once()

    def test_load_latest_index_redis_empty_falls_back_to_db(self, gen):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        row = MagicMock()
        row.sector = "steel"
        row.region = "national"
        row.period = "2024-05"
        row.diffusion = 5.0
        row.sentiment = 2.0
        row.anchor = 8.0
        row.momentum = 1.0
        row.mirror_gap = -3.0
        row.confidence = "med"
        row.n_mentions = 7
        row.inputs = {"reported_value": 100}
        row.generated_at = datetime(2024, 5, 31, 12, 0, 0, tzinfo=timezone.utc)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]

        with patch("redis.from_url", return_value=mock_redis):
            result = gen._load_latest_index(mock_db)
            assert result["generated_at"] == "2024-05-31T12:00:00+00:00"
            assert len(result["sectors"]) == 1
            sector = result["sectors"][0]
            assert sector["sector"] == "steel"
            assert sector["D"] == 5.0
            assert sector["mirror_gap"] == -3.0

    def test_load_latest_index_returns_empty_when_no_data(self, gen):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        with patch("redis.from_url", return_value=mock_redis):
            result = gen._load_latest_index(mock_db)
            assert result == {}


class TestRun:
    """End-to-end run() orchestration with mocked dependencies."""

    def test_run_success(self, gen, sample_sectors, tmp_path):
        payload = {
            "generated_at": "2024-05-31T12:00:00Z",
            "sectors": sample_sectors,
        }
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(payload)

        mock_db = MagicMock()
        mock_session_local = MagicMock(return_value=mock_db)

        mock_digest_cls = MagicMock()

        with patch("redis.from_url", return_value=mock_redis):
            with patch("api.database.SessionLocal", mock_session_local):
                with patch("storage.models.DailyDigest", mock_digest_cls):
                    with patch("free_llm_router.FreeLLMRouter") as mock_router:
                        mock_router.return_value.chat_completion = _async_return(
                            {"text": "LLM generated report"}
                        )
                        with patch("processors.conditions_report._REPORT_DIR", tmp_path):
                            result = gen.run()

        assert result["status"] == "success"
        assert result["sectors"] == 2
        assert result["report_length"] == len("LLM generated report")
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    def test_run_no_data_returns_no_data(self, gen):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_session_local = MagicMock(return_value=mock_db)

        with patch("redis.from_url", return_value=mock_redis):
            with patch("api.database.SessionLocal", mock_session_local):
                result = gen.run()

        assert result["status"] == "no_data"
        mock_db.close.assert_called_once()

    def test_run_error_rolls_back_and_returns_error(self, gen, sample_sectors):
        payload = {
            "generated_at": "2024-05-31T12:00:00Z",
            "sectors": sample_sectors,
        }
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(payload)
        mock_db = MagicMock()
        mock_session_local = MagicMock(return_value=mock_db)

        with patch("redis.from_url", return_value=mock_redis):
            with patch("api.database.SessionLocal", mock_session_local):
                # Force an exception during prompt building.
                with patch.object(gen, "_build_prompt", side_effect=ValueError("boom")):
                    result = gen.run()

        assert result["status"] == "error"
        assert "boom" in result["error"]
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()
