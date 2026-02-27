"""
Unit tests for Analysis Service.

Tests AI/ML analysis operations, sentiment analysis, and entity extraction.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
import json

pytestmark = pytest.mark.unit


class TestAnalysisService:
    """Test suite for AnalysisService."""
    
    @pytest.fixture
    def analysis_service(self, mock_db_session, mock_redis):
        """Create an AnalysisService instance with mocked dependencies."""
        from services.analysis_service import AnalysisService
        return AnalysisService(
            db_session=mock_db_session,
            cache=mock_redis
        )
    
    @pytest.fixture
    def sample_text(self):
        """Provide sample text for analysis."""
        return """
        DragonScope Enterprise provides excellent data analysis capabilities.
        The platform has transformed how our organization handles large datasets.
        Customer support is responsive and helpful.
        """
    
    # =========================================================================
    # Sentiment Analysis Tests
    # =========================================================================
    
    @patch('services.analysis_service.OpenAI')
    def test_sentiment_analysis_positive(self, mock_openai, analysis_service, sample_text):
        """Test positive sentiment analysis."""
        # Arrange
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(
                message=Mock(content=json.dumps({
                    'sentiment': 'positive',
                    'confidence': 0.92,
                    'scores': {'positive': 0.88, 'neutral': 0.10, 'negative': 0.02}
                }))
            )]
        )
        mock_openai.return_value = mock_client
        
        # Act
        result = analysis_service.analyze_sentiment(sample_text)
        
        # Assert
        assert result['sentiment'] == 'positive'
        assert result['confidence'] > 0.8
        assert 'scores' in result
    
    @patch('services.analysis_service.OpenAI')
    def test_sentiment_analysis_negative(self, mock_openai, analysis_service):
        """Test negative sentiment analysis."""
        # Arrange
        negative_text = "The service is terrible. Constant downtime and poor support."
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(
                message=Mock(content=json.dumps({
                    'sentiment': 'negative',
                    'confidence': 0.95,
                    'scores': {'positive': 0.02, 'neutral': 0.05, 'negative': 0.93}
                }))
            )]
        )
        mock_openai.return_value = mock_client
        
        # Act
        result = analysis_service.analyze_sentiment(negative_text)
        
        # Assert
        assert result['sentiment'] == 'negative'
        assert result['scores']['negative'] > 0.9
    
    def test_sentiment_analysis_caching(self, analysis_service, mock_redis, sample_text):
        """Test that sentiment analysis results are cached."""
        # Arrange
        cached_result = json.dumps({
            'sentiment': 'positive',
            'confidence': 0.90,
            'scores': {'positive': 0.90, 'neutral': 0.08, 'negative': 0.02}
        })
        mock_redis.get.return_value = cached_result
        
        # Act
        result = analysis_service.analyze_sentiment(sample_text)
        
        # Assert
        assert result['sentiment'] == 'positive'
        # Verify cache was checked
        mock_redis.get.assert_called_once()
    
    # =========================================================================
    # Entity Extraction Tests
    # =========================================================================
    
    @patch('services.analysis_service.OpenAI')
    def test_entity_extraction(self, mock_openai, analysis_service):
        """Test entity extraction from text."""
        # Arrange
        text = "Apple Inc. is planning to open a new office in Austin, Texas by January 2025."
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(
                message=Mock(content=json.dumps({
                    'entities': [
                        {'type': 'ORGANIZATION', 'text': 'Apple Inc.', 'start': 0, 'end': 10},
                        {'type': 'LOCATION', 'text': 'Austin, Texas', 'start': 51, 'end': 64},
                        {'type': 'DATE', 'text': 'January 2025', 'start': 68, 'end': 80}
                    ]
                }))
            )]
        )
        mock_openai.return_value = mock_client
        
        # Act
        result = analysis_service.extract_entities(text)
        
        # Assert
        assert len(result['entities']) == 3
        orgs = [e for e in result['entities'] if e['type'] == 'ORGANIZATION']
        assert len(orgs) == 1
        assert orgs[0]['text'] == 'Apple Inc.'
    
    def test_entity_extraction_empty_text(self, analysis_service):
        """Test entity extraction with empty text."""
        # Act
        result = analysis_service.extract_entities('')
        
        # Assert
        assert result['entities'] == []
    
    # =========================================================================
    # Topic Classification Tests
    # =========================================================================
    
    @patch('services.analysis_service.OpenAI')
    def test_topic_classification(self, mock_openai, analysis_service):
        """Test topic classification."""
        # Arrange
        text = "The stock market experienced significant volatility today."
        topics = ['finance', 'technology', 'sports', 'politics', 'health']
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(
                message=Mock(content=json.dumps({
                    'topics': [
                        {'topic': 'finance', 'confidence': 0.95},
                        {'topic': 'technology', 'confidence': 0.15}
                    ]
                }))
            )]
        )
        mock_openai.return_value = mock_client
        
        # Act
        result = analysis_service.classify_topics(text, topics)
        
        # Assert
        assert result['topics'][0]['topic'] == 'finance'
        assert result['topics'][0]['confidence'] > 0.9
    
    # =========================================================================
    # Summary Generation Tests
    # =========================================================================
    
    @patch('services.analysis_service.OpenAI')
    def test_generate_summary(self, mock_openai, analysis_service):
        """Test text summarization."""
        # Arrange
        long_text = " " * 5000  # Long text
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(
                message=Mock(content='This is a concise summary of the document.')
            )]
        )
        mock_openai.return_value = mock_client
        
        # Act
        result = analysis_service.generate_summary(long_text, max_length=100)
        
        # Assert
        assert 'summary' in result
        assert len(result['summary']) <= 100
    
    def test_generate_summary_short_text(self, analysis_service):
        """Test summarization of short text returns original."""
        # Arrange
        short_text = "This is already short."
        
        # Act
        result = analysis_service.generate_summary(short_text)
        
        # Assert
        assert result['summary'] == short_text
    
    # =========================================================================
    # Analysis Pipeline Tests
    # =========================================================================
    
    def test_analysis_pipeline(self, analysis_service):
        """Test complete analysis pipeline."""
        # Arrange
        document = {
            'id': 'doc_001',
            'text': 'Sample text for analysis',
            'metadata': {'source': 'test'}
        }
        
        with patch.object(analysis_service, 'analyze_sentiment') as mock_sentiment, \
             patch.object(analysis_service, 'extract_entities') as mock_entities, \
             patch.object(analysis_service, 'generate_summary') as mock_summary:
            
            mock_sentiment.return_value = {'sentiment': 'neutral', 'confidence': 0.8}
            mock_entities.return_value = {'entities': []}
            mock_summary.return_value = {'summary': 'Summary'}
            
            # Act
            result = analysis_service.run_pipeline(document)
            
            # Assert
            assert 'sentiment' in result
            assert 'entities' in result
            assert 'summary' in result
            assert result['document_id'] == 'doc_001'
    
    # =========================================================================
    # Async Analysis Tests
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_async_sentiment_analysis(self, analysis_service):
        """Test async sentiment analysis."""
        # Arrange
        text = "Great product!"
        
        with patch.object(analysis_service, 'analyze_sentiment') as mock_analyze:
            mock_analyze.return_value = {'sentiment': 'positive', 'confidence': 0.95}
            
            # Act
            result = await analysis_service.analyze_sentiment_async(text)
            
            # Assert
            assert result['sentiment'] == 'positive'
    
    @pytest.mark.asyncio
    async def test_async_batch_analysis(self, analysis_service):
        """Test async batch analysis of multiple texts."""
        # Arrange
        texts = ["Text 1", "Text 2", "Text 3"]
        
        with patch.object(analysis_service, 'analyze_sentiment_async') as mock_analyze:
            mock_analyze.side_effect = [
                {'sentiment': 'positive'},
                {'sentiment': 'negative'},
                {'sentiment': 'neutral'}
            ]
            
            # Act
            results = await analysis_service.batch_analyze_async(texts)
            
            # Assert
            assert len(results) == 3
            sentiments = [r['sentiment'] for r in results]
            assert 'positive' in sentiments
            assert 'negative' in sentiments
    
    # =========================================================================
    # Error Handling
    # =========================================================================
    
    @patch('services.analysis_service.OpenAI')
    def test_handle_api_timeout(self, mock_openai, analysis_service, sample_text):
        """Test handling of API timeout."""
        # Arrange
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = TimeoutError("API timeout")
        mock_openai.return_value = mock_client
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            analysis_service.analyze_sentiment(sample_text)
        
        assert 'timeout' in str(exc_info.value).lower() or 'unavailable' in str(exc_info.value).lower()
    
    @patch('services.analysis_service.OpenAI')
    def test_handle_rate_limit(self, mock_openai, analysis_service):
        """Test handling of rate limit errors."""
        # Arrange
        from openai import RateLimitError
        
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Rate limit exceeded",
            response=Mock(status_code=429),
            body=None
        )
        mock_openai.return_value = mock_client
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            analysis_service.extract_entities("test")
        
        assert 'rate limit' in str(exc_info.value).lower() or 'retry' in str(exc_info.value).lower()
    
    def test_handle_invalid_json_response(self, analysis_service):
        """Test handling of invalid JSON from AI service."""
        # Arrange
        with patch('services.analysis_service.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = Mock(
                choices=[Mock(message=Mock(content='Not valid JSON'))]
            )
            mock_openai.return_value = mock_client
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                analysis_service.analyze_sentiment("test")
            
            assert 'parse' in str(exc_info.value).lower() or 'invalid' in str(exc_info.value).lower()


class TestAnalysisResultStorage:
    """Test suite for analysis result storage."""
    
    @pytest.fixture
    def storage_service(self, mock_db_session):
        """Create storage service with mocked DB."""
        from services.analysis_service import AnalysisStorageService
        return AnalysisStorageService(db_session=mock_db_session)
    
    def test_save_analysis_result(self, storage_service, mock_db_session):
        """Test saving analysis results."""
        # Arrange
        analysis_data = {
            'document_id': 'doc_001',
            'project_id': 'prj_001',
            'analysis_type': 'sentiment',
            'results': {'sentiment': 'positive', 'confidence': 0.9},
            'created_at': datetime.now(timezone.utc)
        }
        
        # Act
        result = storage_service.save_analysis(analysis_data)
        
        # Assert
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        assert result.document_id == 'doc_001'
    
    def test_get_analysis_by_document(self, storage_service, mock_db_session):
        """Test retrieving analysis by document ID."""
        # Arrange
        doc_id = 'doc_001'
        expected_analysis = Mock(
            document_id=doc_id,
            analysis_type='sentiment',
            results={'sentiment': 'positive'}
        )
        mock_db_session.query.return_value.filter.return_value.all.return_value = [expected_analysis]
        
        # Act
        results = storage_service.get_analyses_by_document(doc_id)
        
        # Assert
        assert len(results) == 1
        assert results[0].document_id == doc_id
    
    def test_update_analysis_result(self, storage_service, mock_db_session):
        """Test updating existing analysis results."""
        # Arrange
        analysis_id = 'anl_001'
        existing = Mock(id=analysis_id, results={'old': 'data'})
        mock_db_session.get.return_value = existing
        
        update_data = {'results': {'new': 'data', 'updated': True}}
        
        # Act
        result = storage_service.update_analysis(analysis_id, update_data)
        
        # Assert
        assert result.results == {'new': 'data', 'updated': True}
        mock_db_session.commit.assert_called_once()
