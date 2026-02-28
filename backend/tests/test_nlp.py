"""Tests for the NLP pipeline — sentiment, entities, summarization, briefings."""

import json

import pytest
import pytest_asyncio

from app.services.nlp_engine import NlpEngine


# ── Unit tests — NlpEngine ────────────────────────────────────────────────────

@pytest.fixture
def engine():
    return NlpEngine()


class TestSentiment:
    def test_positive_text(self, engine):
        result = engine.analyze_sentiment(
            "Markets rally as profits surge and growth exceeds expectations."
        )
        assert result.score > 0
        assert result.label == "positive"

    def test_negative_text(self, engine):
        result = engine.analyze_sentiment(
            "Stocks crash amid recession fears and massive sell-off."
        )
        assert result.score < 0
        assert result.label == "negative"

    def test_neutral_text(self, engine):
        result = engine.analyze_sentiment(
            "The meeting was held on Tuesday."
        )
        assert result.label == "neutral"
        assert result.score == 0.0

    def test_empty_text(self, engine):
        result = engine.analyze_sentiment("")
        assert result.score == 0.0
        assert result.label == "neutral"

    def test_mixed_sentiment(self, engine):
        result = engine.analyze_sentiment(
            "Despite strong growth, the company faces significant risk from the recession."
        )
        # Should have a score somewhere between -1 and 1
        assert -1.0 <= result.score <= 1.0

    def test_score_range(self, engine):
        result = engine.analyze_sentiment("bullish bullish bullish bullish")
        assert result.score <= 1.0
        result = engine.analyze_sentiment("crash crash crash crash")
        assert result.score >= -1.0


class TestEntityExtraction:
    def test_ticker_extraction(self, engine):
        entities = engine.extract_entities("Investors bought $AAPL and $MSFT today.")
        tickers = [e for e in entities if e.entity_type == "ticker"]
        ticker_texts = {e.text for e in tickers}
        assert "$AAPL" in ticker_texts
        assert "$MSFT" in ticker_texts

    def test_monetary_extraction(self, engine):
        entities = engine.extract_entities("The deal was worth $4.5 billion.")
        monetary = [e for e in entities if e.entity_type == "monetary"]
        assert len(monetary) >= 1
        assert any("4.5" in e.text for e in monetary)

    def test_percentage_extraction(self, engine):
        entities = engine.extract_entities("Revenue grew 15.3% year-over-year.")
        pcts = [e for e in entities if e.entity_type == "percentage"]
        assert len(pcts) >= 1
        assert any("15.3" in e.text for e in pcts)

    def test_organization_extraction(self, engine):
        entities = engine.extract_entities("Apple announced a new product line today.")
        orgs = [e for e in entities if e.entity_type == "organization"]
        org_names = {e.text for e in orgs}
        assert "Apple" in org_names

    def test_date_extraction(self, engine):
        entities = engine.extract_entities("The report was filed on Jan 15, 2025.")
        dates = [e for e in entities if e.entity_type == "date"]
        assert len(dates) >= 1

    def test_empty_text(self, engine):
        entities = engine.extract_entities("")
        assert entities == []

    def test_no_duplicates(self, engine):
        entities = engine.extract_entities("$AAPL went up. $AAPL again.")
        tickers = [e for e in entities if e.entity_type == "ticker"]
        assert len(tickers) == 1


class TestSummarization:
    def test_basic_summarize(self, engine):
        text = (
            "Apple reported record revenue in Q4 2024. "
            "The company saw strong growth in services and wearables. "
            "iPhone sales exceeded analyst expectations. "
            "Mac revenue declined slightly due to product cycle timing. "
            "The board approved a $100 billion share buyback program. "
            "CEO Tim Cook highlighted the company's AI investments."
        )
        summary = engine.summarize(text, max_sentences=3)
        assert len(summary) > 0
        assert len(summary) < len(text)

    def test_short_text_unchanged(self, engine):
        text = "Markets rallied today."
        summary = engine.summarize(text)
        assert summary == text

    def test_empty_text(self, engine):
        summary = engine.summarize("")
        assert summary == ""


class TestTopicExtraction:
    def test_basic_topics(self, engine):
        text = (
            "Artificial intelligence and machine learning are transforming "
            "the semiconductor industry. NVIDIA's GPU technology powers most "
            "deep learning workloads. The company's revenue from data center "
            "chips has grown exponentially."
        )
        topics = engine.extract_topics(text, max_topics=5)
        assert len(topics) > 0
        assert len(topics) <= 5

    def test_empty_text(self, engine):
        topics = engine.extract_topics("")
        assert topics == []


class TestFakeNewsDetection:
    def test_normal_text(self, engine):
        signals = engine.detect_fake_news_signals(
            "Apple reported quarterly earnings that beat analyst expectations."
        )
        assert signals["credibility_score"] >= 0.8
        assert signals["all_caps_ratio"] < 0.3

    def test_suspicious_text(self, engine):
        signals = engine.detect_fake_news_signals(
            "BREAKING: YOU WON'T BELIEVE THIS! GUARANTEED 100% RETURNS! ACT NOW!"
        )
        assert signals["credibility_score"] < 1.0
        assert len(signals["flags"]) > 0
        assert signals["exclamation_density"] > 0

    def test_empty_text(self, engine):
        signals = engine.detect_fake_news_signals("")
        assert signals["credibility_score"] == 1.0


class TestBriefingGeneration:
    def test_generate_briefing_with_docs(self, engine):
        docs = [
            {
                "title": "Markets Rally on Strong Jobs Data",
                "content": "Stocks surged today as employment numbers exceeded expectations. Growth outlook remains bullish.",
                "source": "news",
            },
            {
                "title": "Apple Beats Earnings Estimates",
                "content": "Apple reported record profits, beating analyst expectations. Strong growth in services.",
                "source": "news",
                "entities_json": json.dumps([{"text": "Apple", "entity_type": "organization"}]),
            },
        ]
        briefing = engine.generate_briefing(docs)
        assert "summary" in briefing
        assert "market_mood" in briefing
        assert "key_events_json" in briefing
        assert briefing["market_mood"] in ("bullish", "bearish", "neutral")

    def test_generate_briefing_empty(self, engine):
        briefing = engine.generate_briefing([])
        assert briefing["market_mood"] == "neutral"


# ── Integration tests — API endpoints ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_endpoint(client):
    resp = await client.post(
        "/api/nlp/analyze",
        json={
            "text": "$AAPL surged 5% on strong earnings, beating expectations.",
            "operations": ["sentiment", "entities", "summarize", "topics"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("sentiment") is not None
    assert data["sentiment"]["label"] in ("positive", "negative", "neutral")
    assert data.get("entities") is not None
    assert data.get("summary") is not None
    assert data.get("topics") is not None


@pytest.mark.asyncio
async def test_analyze_sentiment_only(client):
    resp = await client.post(
        "/api/nlp/analyze",
        json={
            "text": "The market crashed today.",
            "operations": ["sentiment"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("sentiment") is not None
    assert data["sentiment"]["label"] == "negative"
    assert data.get("entities") is None


@pytest.mark.asyncio
async def test_documents_list_empty(client):
    resp = await client.get("/api/nlp/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_document_not_found(client):
    resp = await client.get("/api/nlp/documents/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_briefings_list_empty(client):
    resp = await client.get("/api/nlp/briefings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_latest_briefing_not_found(client):
    resp = await client.get("/api/nlp/briefings/latest")
    assert resp.status_code == 404
