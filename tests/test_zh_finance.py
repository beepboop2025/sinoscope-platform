"""Tests for processors.zh_finance.

Covers:
- lexicon loading (cache, missing file, invalid JSON)
- detect_chinese_policy_and_sectors: negation flips, substring matching,
  sector counts, threshold logic, and empty inputs.
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from processors.zh_finance import detect_chinese_policy_and_sectors, load_lexicon


@pytest.fixture
def lexicon():
    """Small inline lexicon for deterministic tests."""
    return {
        "hawkish_keywords": ["加息", "加息周期", "收紧", "紧缩"],
        "dovish_keywords": ["降息", "降准", "宽松", "刺激"],
        "sector_keywords": {
            "banking": ["银行", "银行股"],
            "markets": ["股市", "大盘"],
            "tech": ["科技", "AI"],
        },
    }


class TestLoadLexicon:
    def test_loads_valid_lexicon(self, tmp_path, caplog):
        """load_lexicon returns the parsed JSON and logs success."""
        lex_path = tmp_path / "zh_finance_lexicon.json"
        payload = {"hawkish_keywords": ["加息"], "dovish_keywords": [], "sector_keywords": {}}
        lex_path.write_text(json.dumps(payload), encoding="utf-8")

        with caplog.at_level(logging.INFO):
            with patch("processors.zh_finance._LEXICON_PATH", lex_path):
                load_lexicon.cache_clear()
                result = load_lexicon()

        assert result == payload
        assert "Loaded lexicon" in caplog.text

    def test_missing_file_returns_empty_dict(self, tmp_path, caplog):
        """A missing lexicon file yields {} and a warning."""
        missing = tmp_path / "does_not_exist.json"

        with caplog.at_level(logging.WARNING):
            with patch("processors.zh_finance._LEXICON_PATH", missing):
                load_lexicon.cache_clear()
                result = load_lexicon()

        assert result == {}
        assert "Lexicon not found" in caplog.text

    def test_invalid_json_returns_empty_dict(self, tmp_path, caplog):
        """Invalid JSON yields {} and an error."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")

        with caplog.at_level(logging.ERROR):
            with patch("processors.zh_finance._LEXICON_PATH", bad):
                load_lexicon.cache_clear()
                result = load_lexicon()

        assert result == {}
        assert "invalid JSON" in caplog.text


class TestDetectChinesePolicyAndSectors:
    def test_basic_hawkish(self, lexicon):
        """Direct hawkish keywords above threshold are detected."""
        text = "加息周期，货币紧缩"
        result = detect_chinese_policy_and_sectors(text, lexicon)
        assert result["policy_direction"] == "hawkish"

    def test_basic_dovish(self, lexicon):
        """Direct dovish keywords above threshold are detected."""
        text = "降准降息，流动性宽松"  # "降息" matches dovish, "降准" matches, "宽松" matches
        result = detect_chinese_policy_and_sectors(text, lexicon)
        assert result["policy_direction"] == "dovish"

    def test_negation_flips_hawkish_to_dovish(self, lexicon):
        """不加息 / 尚未加息 are not hawkish and instead boost dovish."""
        # Two negated hawkish signals give dovish_total >= 2.
        text = "我们不加息，央行尚未加息"
        result = detect_chinese_policy_and_sectors(text, lexicon)
        assert result["policy_direction"] == "dovish"
        assert result["sectors"] == {}

    def test_negation_flips_dovish_to_hawkish(self, lexicon):
        """不降息 is not dovish and instead boosts hawkish."""
        text = "不会降息，难以宽松"
        result = detect_chinese_policy_and_sectors(text, lexicon)
        # Two negated dovish signals -> hawkish_total >= 2, dovish_total = 0.
        assert result["policy_direction"] == "hawkish"

    def test_threshold_requires_two_net_hits(self, lexicon):
        """A single non-negated keyword is not enough to declare a direction."""
        assert detect_chinese_policy_and_sectors("加息", lexicon)["policy_direction"] == "neutral"
        assert detect_chinese_policy_and_sectors("降息", lexicon)["policy_direction"] == "neutral"

    def test_substring_matching_in_chinese(self, lexicon):
        """Keywords match as substrings; no \b boundary semantics are used."""
        # "加息周期" contains "加息" as a substring.
        text = "加息周期启动"
        result = detect_chinese_policy_and_sectors(text, lexicon)
        # "加息" and "加息周期" are both matched -> 2 hawkish hits.
        assert result["policy_direction"] == "hawkish"

    def test_overlapping_keyword_matches_counted(self, lexicon):
        """Overlapping sector keyword matches are each counted."""
        # "银行银行股" matches "银行" twice (positions 0 and 2) and "银行股" once (position 0).
        text = "银行银行股上涨"
        result = detect_chinese_policy_and_sectors(text, lexicon)
        assert result["sectors"]["banking"]["mentions"] == 3

    def test_sector_counts_multiple_sectors(self, lexicon):
        """Multiple sectors can be detected and counted independently."""
        text = "银行、股市、科技板块全线走强"
        result = detect_chinese_policy_and_sectors(text, lexicon)
        assert result["sectors"] == {
            "banking": {"mentions": 1},
            "markets": {"mentions": 1},
            "tech": {"mentions": 1},
        }

    def test_empty_text_returns_neutral(self, lexicon):
        """Empty/whitespace input is neutral with no sectors."""
        assert detect_chinese_policy_and_sectors("", lexicon) == {
            "policy_direction": "neutral",
            "sectors": {},
        }
        assert detect_chinese_policy_and_sectors("   ", lexicon) == {
            "policy_direction": "neutral",
            "sectors": {},
        }

    def test_empty_keyword_is_ignored(self, lexicon):
        """Empty-string keywords must not cause spurious matches."""
        broken = {
            "hawkish_keywords": ["加息", ""],
            "dovish_keywords": ["降息", ""],
            "sector_keywords": {"banking": ["", "银行"]},
        }
        text = "银行降息"
        result = detect_chinese_policy_and_sectors(text, broken)
        assert result["sectors"]["banking"]["mentions"] == 1

    def test_tie_returns_neutral(self, lexicon):
        """Equal hawkish and dovish totals fall back to neutral."""
        # One hawkish hit and one negated hawkish -> hawkish_total=1, dovish_total=1.
        text = "加息，但不加息"
        result = detect_chinese_policy_and_sectors(text, lexicon)
        assert result["policy_direction"] == "neutral"
