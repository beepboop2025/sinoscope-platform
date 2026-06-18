"""
Unit tests for Document Processor Service.

Tests document parsing, analysis preparation, and metadata extraction.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from io import BytesIO
import json

pytestmark = pytest.mark.unit


class TestDocumentProcessor:
    """Test suite for DocumentProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create a DocumentProcessor instance."""
        from services.document_processor import DocumentProcessor
        return DocumentProcessor()
    
    @pytest.fixture
    def sample_pdf_content(self):
        """Provide sample PDF content."""
        # Simulated PDF content
        return b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
    
    @pytest.fixture
    def sample_text_content(self):
        """Provide sample text content."""
        return b'This is a sample document for testing purposes.'
    
    # =========================================================================
    # Document Type Detection
    # =========================================================================
    
    def test_detect_pdf_document(self, processor, sample_pdf_content):
        """Test PDF document type detection."""
        # Act
        doc_type = processor.detect_document_type(sample_pdf_content)
        
        # Assert
        assert doc_type == 'application/pdf'
    
    def test_detect_text_document(self, processor, sample_text_content):
        """Test plain text document type detection."""
        # Act
        doc_type = processor.detect_document_type(sample_text_content)
        
        # Assert
        assert doc_type == 'text/plain'
    
    def test_detect_json_document(self, processor):
        """Test JSON document type detection."""
        # Arrange
        json_content = b'{"key": "value", "number": 123}'
        
        # Act
        doc_type = processor.detect_document_type(json_content)
        
        # Assert
        assert doc_type == 'application/json'
    
    def test_detect_csv_document(self, processor):
        """Test CSV document type detection."""
        # Arrange
        csv_content = b'name,age,city\nJohn,30,NYC\nJane,25,LA'
        
        # Act
        doc_type = processor.detect_document_type(csv_content)
        
        # Assert
        assert doc_type == 'text/csv'
    
    def test_detect_xml_document(self, processor):
        """Test XML document type detection."""
        # Arrange
        xml_content = b'<?xml version="1.0"?><root><item>value</item></root>'
        
        # Act
        doc_type = processor.detect_document_type(xml_content)
        
        # Assert
        assert doc_type == 'application/xml'
    
    def test_detect_unknown_document_type(self, processor):
        """Test handling of unknown document type."""
        # Arrange
        binary_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        
        # Act
        doc_type = processor.detect_document_type(binary_content)
        
        # Assert
        assert doc_type == 'application/octet-stream'
    
    # =========================================================================
    # Document Validation
    # =========================================================================
    
    def test_validate_document_size_within_limit(self, processor):
        """Test document validation within size limit."""
        # Arrange
        content = b'x' * (10 * 1024 * 1024)  # 10 MB
        
        # Act
        is_valid = processor.validate_document_size(content, max_size_mb=50)
        
        # Assert
        assert is_valid is True
    
    def test_validate_document_size_exceeds_limit(self, processor):
        """Test document validation fails when exceeding size limit."""
        # Arrange
        content = b'x' * (100 * 1024 * 1024)  # 100 MB
        
        # Act
        is_valid = processor.validate_document_size(content, max_size_mb=50)
        
        # Assert
        assert is_valid is False
    
    def test_validate_supported_format(self, processor):
        """Test validation of supported document format."""
        # Act
        is_valid = processor.validate_format('application/pdf')
        
        # Assert
        assert is_valid is True
    
    def test_validate_unsupported_format(self, processor):
        """Test validation rejects unsupported format."""
        # Act
        is_valid = processor.validate_format('application/x-executable')
        
        # Assert
        assert is_valid is False
    
    def test_validate_malicious_filename(self, processor):
        """Test validation rejects potentially malicious filenames."""
        # Arrange
        malicious_names = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32\\config\\sam',
            'file.php.jpg',
            'script.jsp',
            '<script>alert(1)</script>.pdf'
        ]
        
        # Act & Assert
        for name in malicious_names:
            is_valid = processor.validate_filename(name)
            assert is_valid is False, f"Expected {name} to be rejected"
    
    def test_validate_valid_filename(self, processor):
        """Test validation accepts valid filenames."""
        # Arrange
        valid_names = [
            'document.pdf',
            'my_file_123.docx',
            'report-2024.xlsx',
            'data_export.csv'
        ]
        
        # Act & Assert
        for name in valid_names:
            is_valid = processor.validate_filename(name)
            assert is_valid is True, f"Expected {name} to be accepted"
    
    # =========================================================================
    # Content Extraction
    # =========================================================================
    
    @patch('services.document_processor.PdfReader')
    def test_extract_text_from_pdf(self, mock_pdf_reader, processor, sample_pdf_content):
        """Test text extraction from PDF."""
        # Arrange
        mock_page = Mock()
        mock_page.extract_text.return_value = 'Extracted text from PDF'
        
        mock_reader = Mock()
        mock_reader.pages = [mock_page, mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        # Act
        text = processor.extract_text(sample_pdf_content, 'application/pdf')
        
        # Assert
        assert 'Extracted text from PDF' in text
        assert mock_pdf_reader.called
    
    def test_extract_text_from_plain_text(self, processor, sample_text_content):
        """Test text extraction from plain text."""
        # Act
        text = processor.extract_text(sample_text_content, 'text/plain')
        
        # Assert
        assert text == 'This is a sample document for testing purposes.'
    
    def test_extract_text_from_json(self, processor):
        """Test text extraction from JSON."""
        # Arrange
        json_content = b'{"title": "Test", "content": "Sample content"}'
        
        # Act
        text = processor.extract_text(json_content, 'application/json')
        
        # Assert
        assert 'title' in text
        assert 'Test' in text
    
    def test_extract_text_unsupported_type_raises_error(self, processor):
        """Test that unsupported document type raises error."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            processor.extract_text(b'content', 'application/unknown')
        
        assert 'unsupported' in str(exc_info.value).lower()
    
    # =========================================================================
    # Metadata Extraction
    # =========================================================================
    
    def test_extract_metadata_from_document(self, processor):
        """Test metadata extraction from document."""
        # Arrange
        content = b'This is a test document with some words for counting.'
        
        # Act
        metadata = processor.extract_metadata(content, 'text/plain')
        
        # Assert
        assert 'word_count' in metadata
        assert 'character_count' in metadata
        assert 'line_count' in metadata
        assert metadata['word_count'] == 10
    
    def test_extract_metadata_from_pdf(self, processor):
        """Test metadata extraction from PDF with specific properties."""
        # Arrange
        with patch('services.document_processor.PdfReader') as mock_reader:
            mock_doc = Mock()
            mock_doc.metadata = {
                '/Title': 'Test Document',
                '/Author': 'Test Author',
                '/CreationDate': 'D:20240115120000'
            }
            mock_reader.return_value = mock_doc
            
            content = b'%PDF-1.4...'
            
            # Act
            metadata = processor.extract_metadata(content, 'application/pdf')
            
            # Assert
            assert metadata.get('title') == 'Test Document'
            assert metadata.get('author') == 'Test Author'
    
    def test_detect_language(self, processor):
        """Test language detection from content."""
        # Arrange
        english_text = "This is an English document about machine learning."
        spanish_text = "Este es un documento en español sobre aprendizaje automático."
        
        # Act
        lang_en = processor.detect_language(english_text)
        lang_es = processor.detect_language(spanish_text)
        
        # Assert
        assert lang_en == 'en'
        assert lang_es == 'es'
    
    # =========================================================================
    # Content Chunking
    # =========================================================================
    
    def test_chunk_document_by_size(self, processor):
        """Test document chunking by character size."""
        # Arrange
        text = "Word " * 1000  # 5000 characters
        chunk_size = 1000
        
        # Act
        chunks = processor.chunk_document(text, chunk_size=chunk_size, overlap=100)
        
        # Assert
        assert len(chunks) > 1
        assert all(len(chunk) <= chunk_size + 100 for chunk in chunks)
    
    def test_chunk_document_by_paragraph(self, processor):
        """Test document chunking by paragraphs."""
        # Arrange
        text = "\n\n".join([f"Paragraph {i}" * 50 for i in range(10)])
        
        # Act
        chunks = processor.chunk_document(text, chunk_size=500, overlap=50)
        
        # Assert
        assert len(chunks) > 0
        # Verify overlap
        for i in range(len(chunks) - 1):
            overlap = set(chunks[i].split()) & set(chunks[i + 1].split())
            assert len(overlap) > 0
    
    def test_chunk_document_preserves_context(self, processor):
        """Test that chunking preserves sentence context."""
        # Arrange
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        
        # Act
        chunks = processor.chunk_document(text, chunk_size=30, overlap=10)
        
        # Assert
        # Each chunk should contain complete sentences
        for chunk in chunks:
            assert chunk.strip().endswith('.')
    
    # =========================================================================
    # Error Handling
    # =========================================================================
    
    def test_handle_corrupted_pdf(self, processor):
        """Test handling of corrupted PDF content."""
        # Arrange
        corrupted_content = b'%PDF-1.4\nINVALID CONTENT'
        
        with patch('services.document_processor.PdfReader') as mock_reader:
            mock_reader.side_effect = Exception('PDF is corrupted')
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                processor.extract_text(corrupted_content, 'application/pdf')
            
            assert 'corrupted' in str(exc_info.value).lower() or 'failed' in str(exc_info.value).lower()
    
    def test_handle_empty_document(self, processor):
        """Test handling of empty document."""
        # Arrange
        empty_content = b''
        
        # Act
        result = processor.extract_text(empty_content, 'text/plain')
        
        # Assert
        assert result == ''
    
    def test_handle_large_document_efficiently(self, processor):
        """Test efficient handling of large documents."""
        # Arrange
        large_content = b'Word ' * 100000  # ~500KB
        
        # Act - should complete without memory issues
        import time
        start = time.time()
        metadata = processor.extract_metadata(large_content, 'text/plain')
        elapsed = time.time() - start
        
        # Assert
        assert elapsed < 1.0  # Should complete in less than 1 second
        assert metadata['word_count'] == 100000
    
    # =========================================================================
    # Async Operations
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_async_process_document(self, processor):
        """Test async document processing."""
        # Arrange
        content = b'Test content for async processing'
        
        with patch.object(processor, 'extract_text', return_value='Extracted text'):
            # Act
            result = await processor.process_async(content, 'text/plain')
            
            # Assert
            assert result['text'] == 'Extracted text'
            assert 'metadata' in result
            assert 'chunks' in result
    
    @pytest.mark.asyncio
    async def test_async_batch_process(self, processor):
        """Test async batch processing of multiple documents."""
        # Arrange
        documents = [
            {'content': b'Doc 1', 'type': 'text/plain'},
            {'content': b'Doc 2', 'type': 'text/plain'},
            {'content': b'Doc 3', 'type': 'text/plain'}
        ]
        
        # Act
        results = await processor.batch_process_async(documents)
        
        # Assert
        assert len(results) == 3
        assert all('text' in r for r in results)
