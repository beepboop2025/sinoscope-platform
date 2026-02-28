"""
Unit tests for utility functions.

Tests helpers, formatters, validators, and common utilities.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import hashlib
import re

pytestmark = pytest.mark.unit


class TestDateTimeUtils:
    """Tests for datetime utility functions."""
    
    def test_parse_iso_datetime(self):
        """Test parsing ISO format datetime strings."""
        from utils.datetime import parse_iso_datetime
        
        # Test with timezone
        result = parse_iso_datetime('2024-01-15T12:00:00+00:00')
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.tzinfo is not None
        
        # Test without timezone
        result = parse_iso_datetime('2024-01-15T12:00:00')
        assert result.year == 2024
        assert result.tzinfo is None
    
    def test_format_datetime_iso(self):
        """Test formatting datetime to ISO string."""
        from utils.datetime import format_datetime_iso
        
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = format_datetime_iso(dt)
        
        assert result == '2024-01-15T12:00:00+00:00'
    
    def test_convert_timezone(self):
        """Test timezone conversion."""
        from utils.datetime import convert_timezone
        import zoneinfo
        
        utc = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        est = convert_timezone(utc, 'America/New_York')
        
        assert est.hour == 7  # UTC-5 (EST)
        assert str(est.tzinfo) == 'America/New_York'
    
    def test_get_relative_time(self):
        """Test relative time formatting."""
        from utils.datetime import get_relative_time
        
        now = datetime.now(timezone.utc)
        
        assert get_relative_time(now) == 'just now'
        assert get_relative_time(now - timedelta(minutes=5)) == '5 minutes ago'
        assert get_relative_time(now - timedelta(hours=2)) == '2 hours ago'
        assert get_relative_time(now - timedelta(days=1)) == 'yesterday'
        assert get_relative_time(now - timedelta(days=5)) == '5 days ago'
    
    def test_truncate_to_midnight(self):
        """Test truncating datetime to midnight."""
        from utils.datetime import truncate_to_midnight
        
        dt = datetime(2024, 1, 15, 14, 30, 45, 123, tzinfo=timezone.utc)
        result = truncate_to_midnight(dt)
        
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0


class TestStringUtils:
    """Tests for string utility functions."""
    
    def test_slugify(self):
        """Test converting text to URL-friendly slug."""
        from utils.strings import slugify
        
        assert slugify('Hello World') == 'hello-world'
        assert slugify('Test 123') == 'test-123'
        assert slugify('Multiple   Spaces') == 'multiple-spaces'
        assert slugify('Special!@#Characters') == 'special-characters'
        assert slugify('UPPERCASE') == 'uppercase'
    
    def test_truncate(self):
        """Test string truncation."""
        from utils.strings import truncate
        
        text = 'This is a very long text that needs truncation'
        
        assert truncate(text, 20) == 'This is a very lo...'
        assert truncate(text, 100) == text  # No truncation needed
        assert truncate(text, 10, '---') == 'This is---'  # Custom suffix
    
    def test_camel_to_snake(self):
        """Test camelCase to snake_case conversion."""
        from utils.strings import camel_to_snake
        
        assert camel_to_snake('camelCase') == 'camel_case'
        assert camel_to_snake('PascalCase') == 'pascal_case'
        assert camel_to_snake('simple') == 'simple'
        assert camel_to_snake('HTTPResponse') == 'http_response'
    
    def test_snake_to_camel(self):
        """Test snake_case to camelCase conversion."""
        from utils.strings import snake_to_camel
        
        assert snake_to_camel('snake_case') == 'snakeCase'
        assert snake_to_camel('simple') == 'simple'
        assert snake_to_camel('multiple_word_case') == 'multipleWordCase'
    
    def test_remove_extra_whitespace(self):
        """Test removing extra whitespace."""
        from utils.strings import remove_extra_whitespace
        
        assert remove_extra_whitespace('  multiple   spaces  ') == 'multiple spaces'
        assert remove_extra_whitespace('\ttabs\tand\nnewlines') == 'tabs and newlines'
    
    def test_mask_sensitive_data(self):
        """Test masking sensitive data."""
        from utils.strings import mask_sensitive_data
        
        # Credit card
        assert mask_sensitive_data('1234567890123456', 'credit_card') == '************3456'
        
        # Email
        assert mask_sensitive_data('user@example.com', 'email') == 'u***@example.com'
        
        # Phone
        assert mask_sensitive_data('+1-555-123-4567', 'phone') == '***-***-4567'


class TestValidationUtils:
    """Tests for validation utility functions."""
    
    def test_validate_email(self):
        """Test email validation."""
        from utils.validation import validate_email
        
        # Valid emails
        assert validate_email('user@example.com') is True
        assert validate_email('first.last@sub.domain.co.uk') is True
        assert validate_email('user+tag@example.com') is True
        
        # Invalid emails
        assert validate_email('not-an-email') is False
        assert validate_email('@example.com') is False
        assert validate_email('user@') is False
        assert validate_email('') is False
    
    def test_validate_url(self):
        """Test URL validation."""
        from utils.validation import validate_url
        
        # Valid URLs
        assert validate_url('https://example.com') is True
        assert validate_url('http://localhost:3000') is True
        assert validate_url('ftp://files.example.com') is True
        
        # Invalid URLs
        assert validate_url('not-a-url') is False
        assert validate_url('http://') is False
    
    def test_validate_password_strength(self):
        """Test password strength validation."""
        from utils.validation import validate_password_strength
        
        # Strong passwords
        assert validate_password_strength('StrongPass123!') is True
        assert validate_password_strength('My$ecureP@ssw0rd') is True
        
        # Weak passwords
        assert validate_password_strength('123') is False  # Too short
        assert validate_password_strength('password') is False  # No numbers/special
        assert validate_password_strength('PASSWORD123') is False  # No lowercase
        assert validate_password_strength('password123') is False  # No uppercase
    
    def test_validate_uuid(self):
        """Test UUID validation."""
        from utils.validation import validate_uuid
        
        # Valid UUIDs
        assert validate_uuid('550e8400-e29b-41d4-a716-446655440000') is True
        assert validate_uuid('550E8400-E29B-41D4-A716-446655440000') is True  # Uppercase
        
        # Invalid UUIDs
        assert validate_uuid('not-a-uuid') is False
        assert validate_uuid('550e8400-e29b-41d4-a716') is False  # Too short
        assert validate_uuid('') is False
    
    def test_validate_phone_number(self):
        """Test phone number validation."""
        from utils.validation import validate_phone_number
        
        # Valid phone numbers
        assert validate_phone_number('+1-555-123-4567') is True
        assert validate_phone_number('+44 20 7946 0958') is True
        assert validate_phone_number('5551234567') is True
        
        # Invalid phone numbers
        assert validate_phone_number('123') is False  # Too short
        assert validate_phone_number('abc-def-ghij') is False  # Letters


class TestCryptoUtils:
    """Tests for cryptographic utility functions."""
    
    def test_hash_password(self):
        """Test password hashing."""
        from utils.crypto import hash_password, verify_password
        
        password = 'SecurePassword123!'
        hashed = hash_password(password)
        
        # Hash should be different from original
        assert hashed != password
        
        # Should verify correctly
        assert verify_password(password, hashed) is True
        
        # Wrong password should not verify
        assert verify_password('WrongPassword', hashed) is False
    
    def test_generate_secure_token(self):
        """Test secure token generation."""
        from utils.crypto import generate_secure_token
        
        token1 = generate_secure_token(32)
        token2 = generate_secure_token(32)
        
        # Should be URL-safe
        assert re.match(r'^[A-Za-z0-9_-]+$', token1)
        
        # Should be unique
        assert token1 != token2
        
        # Should be correct length
        # Base64 encoding makes it slightly longer than raw bytes
        assert len(token1) >= 32
    
    def test_encrypt_decrypt(self):
        """Test encryption and decryption."""
        from utils.crypto import encrypt, decrypt
        
        plaintext = 'Sensitive data to encrypt'
        key = hashlib.sha256(b'secret_key').digest()
        
        encrypted = encrypt(plaintext, key)
        decrypted = decrypt(encrypted, key)
        
        assert encrypted != plaintext
        assert decrypted == plaintext
    
    def test_generate_hmac(self):
        """Test HMAC generation."""
        from utils.crypto import generate_hmac, verify_hmac
        
        data = 'message to sign'
        key = 'secret_key'
        
        hmac = generate_hmac(data, key)
        
        # Should verify correctly
        assert verify_hmac(data, key, hmac) is True
        
        # Tampered data should fail
        assert verify_hmac('tampered', key, hmac) is False


class TestJSONUtils:
    """Tests for JSON utility functions."""
    
    def test_safe_json_loads(self):
        """Test safe JSON parsing."""
        from utils.json import safe_json_loads
        
        # Valid JSON
        assert safe_json_loads('{"key": "value"}') == {'key': 'value'}
        assert safe_json_loads('[1, 2, 3]') == [1, 2, 3]
        
        # Invalid JSON - returns default
        assert safe_json_loads('not json') is None
        assert safe_json_loads('not json', default={}) == {}
    
    def test_json_serializable_encoder(self):
        """Test custom JSON encoder."""
        from utils.json import JSONSerializableEncoder
        
        data = {
            'datetime': datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            'decimal': Decimal('99.99'),
            'set': {1, 2, 3},
            'bytes': b'hello'
        }
        
        result = json.loads(json.dumps(data, cls=JSONSerializableEncoder))
        
        assert result['datetime'] == '2024-01-15T12:00:00+00:00'
        assert result['decimal'] == '99.99'
        assert isinstance(result['set'], list)
        assert result['bytes'] == 'aGVsbG8='
    
    def test_pretty_print_json(self):
        """Test JSON pretty printing."""
        from utils.json import pretty_print_json
        
        data = {'key': 'value', 'nested': {'a': 1}}
        result = pretty_print_json(data)
        
        assert isinstance(result, str)
        assert '\n' in result  # Should have newlines
        assert '  ' in result  # Should have indentation


class TestMathUtils:
    """Tests for mathematical utility functions."""
    
    def test_round_decimal(self):
        """Test decimal rounding."""
        from utils.math import round_decimal
        
        assert round_decimal(3.14159, 2) == Decimal('3.14')
        assert round_decimal(2.5, 0) == Decimal('3')
        assert round_decimal(Decimal('99.999'), 1) == Decimal('100.0')
    
    def test_calculate_percentage(self):
        """Test percentage calculation."""
        from utils.math import calculate_percentage
        
        assert calculate_percentage(50, 100) == 50.0
        assert calculate_percentage(25, 200) == 12.5
        assert calculate_percentage(0, 100) == 0.0
        
        # Handle division by zero
        assert calculate_percentage(10, 0) == 0.0
    
    def test_clamp(self):
        """Test value clamping."""
        from utils.math import clamp
        
        assert clamp(5, 0, 10) == 5
        assert clamp(-5, 0, 10) == 0
        assert clamp(15, 0, 10) == 10
    
    def test_moving_average(self):
        """Test moving average calculation."""
        from utils.math import moving_average
        
        values = [1, 2, 3, 4, 5]
        
        result = moving_average(values, window=3)
        
        assert result == [2.0, 3.0, 4.0]  # Averages of [1,2,3], [2,3,4], [3,4,5]
    
    def test_normalize(self):
        """Test value normalization."""
        from utils.math import normalize
        
        values = [10, 20, 30, 40, 50]
        result = normalize(values)
        
        assert result[0] == 0.0
        assert result[-1] == 1.0
        assert all(0 <= r <= 1 for r in result)


classTestFileUtils:
    """Tests for file utility functions."""
    
    def test_get_file_extension(self):
        """Test file extension extraction."""
        from utils.files import get_file_extension
        
        assert get_file_extension('document.pdf') == 'pdf'
        assert get_file_extension('archive.tar.gz') == 'gz'
        assert get_file_extension('no_extension') == ''
    
    def test_safe_filename(self):
        """Test safe filename generation."""
        from utils.files import safe_filename
        
        assert safe_filename('My File.pdf') == 'my_file.pdf'
        assert safe_filename('../../../etc/passwd') == 'etc_passwd'
        assert safe_filename('file<>name:.txt') == 'file_name_.txt'
    
    def test_format_file_size(self):
        """Test file size formatting."""
        from utils.files import format_file_size
        
        assert format_file_size(512) == '512 B'
        assert format_file_size(1024) == '1.0 KB'
        assert format_file_size(1024 * 1024) == '1.0 MB'
        assert format_file_size(1024 * 1024 * 1024) == '1.0 GB'
    
    def test_guess_mime_type(self):
        """Test MIME type guessing."""
        from utils.files import guess_mime_type
        
        assert guess_mime_type('file.pdf') == 'application/pdf'
        assert guess_mime_type('image.jpg') == 'image/jpeg'
        assert guess_mime_type('data.json') == 'application/json'
        assert guess_mime_type('unknown.xyz') == 'application/octet-stream'


class TestAsyncUtils:
    """Tests for async utility functions."""
    
    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test async retry decorator on success."""
        from utils.async_utils import async_retry
        
        call_count = 0
        
        @async_retry(max_attempts=3, delay=0.1)
        async def always_succeeds():
            nonlocal call_count
            call_count += 1
            return 'success'
        
        result = await always_succeeds()
        
        assert result == 'success'
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_async_retry_eventual_success(self):
        """Test async retry with eventual success."""
        from utils.async_utils import async_retry
        
        call_count = 0
        
        @async_retry(max_attempts=3, delay=0.01)
        async def fails_then_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception('Temporary failure')
            return 'success'
        
        result = await fails_then_succeeds()
        
        assert result == 'success'
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_retry_exhausted(self):
        """Test async retry when all attempts fail."""
        from utils.async_utils import async_retry
        
        @async_retry(max_attempts=2, delay=0.01)
        async def always_fails():
            raise Exception('Persistent failure')
        
        with pytest.raises(Exception) as exc_info:
            await always_fails()
        
        assert 'Persistent failure' in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_gather_with_concurrency_limit(self):
        """Test gather with concurrency limit."""
        from utils.async_utils import gather_with_limit
        
        async def task(n):
            return n * 2
        
        tasks = [task(i) for i in range(10)]
        results = await gather_with_limit(tasks, limit=3)
        
        assert len(results) == 10
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
    
    @pytest.mark.asyncio
    async def test_timeout_handler(self):
        """Test timeout handler."""
        from utils.async_utils import with_timeout
        import asyncio
        
        @with_timeout(seconds=0.1)
        async def slow_task():
            await asyncio.sleep(1)
            return 'completed'
        
        with pytest.raises(TimeoutError):
            await slow_task()
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """Test rate limiter."""
        from utils.async_utils import RateLimiter
        import asyncio
        
        limiter = RateLimiter(max_calls=3, period=1.0)
        
        call_times = []
        
        async def tracked_task():
            async with limiter:
                call_times.append(asyncio.get_event_loop().time())
        
        # Execute 5 tasks (should take at least 1 second due to rate limit)
        start = asyncio.get_event_loop().time()
        await asyncio.gather(*[tracked_task() for _ in range(5)])
        elapsed = asyncio.get_event_loop().time() - start
        
        assert len(call_times) == 5
        # Should have taken more than 1 second for 5 calls with limit of 3
        assert elapsed >= 1.0


class TestCacheUtils:
    """Tests for cache utility functions."""
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        from utils.cache import generate_cache_key
        
        # Simple key
        key1 = generate_cache_key('users', 'list')
        assert isinstance(key1, str)
        
        # With parameters
        key2 = generate_cache_key('users', 'get', user_id=123)
        assert '123' in key2
        
        # Different params = different keys
        key3 = generate_cache_key('users', 'get', user_id=456)
        assert key2 != key3
        
        # Same params = same key
        key4 = generate_cache_key('users', 'get', user_id=123)
        assert key2 == key4
    
    def test_cache_ttl_calculator(self):
        """Test cache TTL calculation."""
        from utils.cache import calculate_ttl
        
        # Static data - long TTL
        assert calculate_ttl(data_type='static') == 3600
        
        # Dynamic data - shorter TTL
        assert calculate_ttl(data_type='dynamic') == 300
        
        # User data - medium TTL
        assert calculate_ttl(data_type='user') == 600
    
    @pytest.mark.asyncio
    async def test_async_cache_decorator(self):
        """Test async cache decorator."""
        from utils.cache import async_cache
        
        call_count = 0
        cache = {}
        
        @async_cache(cache=cache, ttl=60)
        async def expensive_operation(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call - executes
        result1 = await expensive_operation(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call with same arg - from cache
        result2 = await expensive_operation(5)
        assert result2 == 10
        assert call_count == 1  # Not called again
        
        # Different arg - executes
        result3 = await expensive_operation(10)
        assert result3 == 20
        assert call_count == 2
