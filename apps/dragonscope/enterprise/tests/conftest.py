"""
Global pytest configuration and shared fixtures for DragonScope Enterprise tests.
"""

import asyncio
import os
import sys
from typing import AsyncGenerator, Generator, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

import pytest
import pytest_asyncio

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# =============================================================================
# Session-scoped Fixtures
# =============================================================================

@pytest.fixture(scope='session')
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
def test_config():
    """Provide test configuration."""
    return {
        'database_url': os.getenv(
            'TEST_DATABASE_URL',
            'postgresql://test:test@localhost:5433/dragonscope_test'
        ),
        'redis_url': os.getenv(
            'TEST_REDIS_URL',
            'redis://localhost:6380/1'
        ),
        'rabbitmq_url': os.getenv(
            'TEST_RABBITMQ_URL',
            'amqp://guest:guest@localhost:5673/'
        ),
        'api_url': os.getenv(
            'TEST_API_URL',
            'http://localhost:8000'
        ),
        'elasticsearch_url': os.getenv(
            'TEST_ES_URL',
            'http://localhost:9201'
        ),
        'minio_endpoint': os.getenv(
            'TEST_MINIO_ENDPOINT',
            'localhost:9001'
        ),
    }


# =============================================================================
# Time-related Fixtures
# =============================================================================

@pytest.fixture
def frozen_time():
    """Provide a frozen datetime for deterministic tests."""
    fixed_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    with patch('datetime.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_time
        mock_dt.utcnow.return_value = fixed_time
        yield fixed_time


@pytest.fixture
def mock_timestamp():
    """Provide a mock timestamp."""
    return 1705310400.0  # 2024-01-15 12:00:00 UTC


# =============================================================================
# Mock Fixtures for External Services
# =============================================================================

@pytest.fixture
def mock_stripe():
    """Mock Stripe payment gateway."""
    with patch('services.payment.stripe') as mock:
        mock.Charge.create.return_value = {
            'id': 'ch_test_1234567890',
            'amount': 1000,
            'currency': 'usd',
            'status': 'succeeded',
            'receipt_url': 'https://pay.stripe.com/receipts/test'
        }
        mock.Customer.create.return_value = {
            'id': 'cus_test_1234567890',
            'email': 'test@example.com'
        }
        yield mock


@pytest.fixture
def mock_sendgrid():
    """Mock SendGrid email service."""
    with patch('services.email.SendGridAPIClient') as mock:
        mock_client = Mock()
        mock_client.send.return_value = Mock(status_code=202)
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def mock_s3_client():
    """Mock AWS S3/MinIO client."""
    with patch('boto3.client') as mock:
        mock_s3 = Mock()
        mock_s3.upload_file.return_value = None
        mock_s3.download_file.return_value = None
        mock_s3.generate_presigned_url.return_value = 'https://s3.test/bucket/file.pdf'
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'file1.pdf', 'Size': 1024},
                {'Key': 'file2.pdf', 'Size': 2048}
            ]
        }
        mock.return_value = mock_s3
        yield mock_s3


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch('redis.Redis') as mock:
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis.delete.return_value = 1
        mock_redis.exists.return_value = 1
        mock_redis.ttl.return_value = 3600
        mock_redis.expire.return_value = True
        mock_redis.pipeline.return_value = Mock(
            execute=Mock(return_value=[])
        )
        mock.return_value = mock_redis
        yield mock_redis


@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch client."""
    with patch('elasticsearch.Elasticsearch') as mock:
        mock_es = Mock()
        mock_es.index.return_value = {'_id': 'test_doc_id', 'result': 'created'}
        mock_es.search.return_value = {
            'hits': {
                'total': {'value': 1},
                'hits': [{'_id': '1', '_source': {'title': 'Test'}}]
            }
        }
        mock_es.delete.return_value = {'result': 'deleted'}
        mock_es.ping.return_value = True
        mock.return_value = mock_es
        yield mock_es


@pytest.fixture
def mock_rabbitmq():
    """Mock RabbitMQ connection and channel."""
    with patch('pika.BlockingConnection') as mock_conn:
        mock_channel = Mock()
        mock_channel.queue_declare.return_value = None
        mock_channel.basic_publish.return_value = None
        mock_channel.basic_consume.return_value = None
        mock_channel.close.return_value = None
        
        mock_connection = Mock()
        mock_connection.channel.return_value = mock_channel
        mock_connection.close.return_value = None
        mock_conn.return_value = mock_connection
        
        yield {
            'connection': mock_connection,
            'channel': mock_channel
        }


@pytest.fixture
def mock_http_client():
    """Mock HTTP client (aiohttp/httpx)."""
    with patch('httpx.AsyncClient') as mock:
        mock_client = AsyncMock()
        mock_client.get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={'data': 'test'}),
            text='{"data": "test"}'
        )
        mock_client.post.return_value = Mock(
            status_code=201,
            json=Mock(return_value={'id': '123', 'status': 'created'})
        )
        mock.return_value = mock_client
        yield mock_client


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest.fixture
def mock_jwt_token():
    """Provide a mock JWT token for testing."""
    return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.signature'


@pytest.fixture
def auth_headers(mock_jwt_token):
    """Provide authentication headers."""
    return {
        'Authorization': f'Bearer {mock_jwt_token}',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def mock_current_user():
    """Provide a mock authenticated user."""
    return {
        'id': 'user_123456789',
        'email': 'test@dragonscope.io',
        'role': 'admin',
        'organization_id': 'org_123456789',
        'permissions': ['read', 'write', 'delete', 'admin']
    }


# =============================================================================
# Database Fixtures (for integration tests)
# =============================================================================

@pytest_asyncio.fixture(scope='function')
async def db_connection(test_config):
    """
    Provide a database connection for integration tests.
    Creates a transaction that rolls back after the test.
    """
    # This is a placeholder - implement with actual DB driver
    # Example with asyncpg:
    # import asyncpg
    # conn = await asyncpg.connect(test_config['database_url'])
    # transaction = conn.transaction()
    # await transaction.start()
    # yield conn
    # await transaction.rollback()
    # await conn.close()
    
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchrow = AsyncMock(return_value={'id': 1})
    mock_conn.execute = AsyncMock(return_value='INSERT 1')
    yield mock_conn


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests."""
    session = Mock()
    session.query.return_value = session
    session.filter.return_value = session
    session.all.return_value = []
    session.first.return_value = None
    session.get.return_value = None
    session.add.return_value = None
    session.commit.return_value = None
    session.rollback.return_value = None
    session.refresh.return_value = None
    yield session


# =============================================================================
# Test Data Factories
# =============================================================================

@pytest.fixture
def user_factory():
    """Factory for creating test user data."""
    def _factory(**overrides):
        defaults = {
            'id': 'usr_test_001',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'analyst',
            'is_active': True,
            'created_at': datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            'last_login': None,
            'organization_id': 'org_test_001'
        }
        defaults.update(overrides)
        return defaults
    return _factory


@pytest.fixture
def project_factory():
    """Factory for creating test project data."""
    def _factory(**overrides):
        defaults = {
            'id': 'prj_test_001',
            'name': 'Test Project',
            'description': 'A test project for analysis',
            'owner_id': 'usr_test_001',
            'organization_id': 'org_test_001',
            'status': 'active',
            'settings': {
                'analysis_depth': 'standard',
                'notifications_enabled': True
            },
            'created_at': datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            'updated_at': datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        }
        defaults.update(overrides)
        return defaults
    return _factory


@pytest.fixture
def document_factory():
    """Factory for creating test document data."""
    def _factory(**overrides):
        defaults = {
            'id': 'doc_test_001',
            'project_id': 'prj_test_001',
            'filename': 'test_document.pdf',
            'content_type': 'application/pdf',
            'size': 1024000,
            'storage_key': 'projects/prj_test_001/doc_test_001.pdf',
            'status': 'processed',
            'metadata': {
                'pages': 10,
                'word_count': 5000,
                'language': 'en'
            },
            'created_at': datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        }
        defaults.update(overrides)
        return defaults
    return _factory


@pytest.fixture
def analysis_result_factory():
    """Factory for creating test analysis result data."""
    def _factory(**overrides):
        defaults = {
            'id': 'anl_test_001',
            'project_id': 'prj_test_001',
            'document_id': 'doc_test_001',
            'analysis_type': 'sentiment',
            'status': 'completed',
            'results': {
                'sentiment': 'positive',
                'confidence': 0.92,
                'scores': {
                    'positive': 0.85,
                    'neutral': 0.10,
                    'negative': 0.05
                }
            },
            'created_at': datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            'completed_at': datetime(2024, 1, 15, 12, 1, 0, tzinfo=timezone.utc)
        }
        defaults.update(overrides)
        return defaults
    return _factory


# =============================================================================
# Assertion Helpers
# =============================================================================

@pytest.fixture
def assert_valid_uuid():
    """Helper to assert valid UUID format."""
    import uuid
    def _assert(value):
        try:
            uuid.UUID(str(value))
        except ValueError:
            pytest.fail(f"'{value}' is not a valid UUID")
    return _assert


@pytest.fixture
def assert_json_schema():
    """Helper to validate JSON schema."""
    from jsonschema import validate, ValidationError
    def _assert(data, schema):
        try:
            validate(instance=data, schema=schema)
        except ValidationError as e:
            pytest.fail(f"JSON schema validation failed: {e.message}")
    return _assert


@pytest.fixture
def assert_within_timeout():
    """Helper to assert operation completes within timeout."""
    import time
    def _assert(operation, timeout_seconds=5.0):
        start = time.time()
        result = operation()
        elapsed = time.time() - start
        assert elapsed < timeout_seconds, f"Operation took {elapsed}s, expected < {timeout_seconds}s"
        return result
    return _assert


# =============================================================================
# Cleanup Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Automatically clean up temporary files after each test."""
    import tempfile
    temp_files = []
    yield temp_files
    
    for filepath in temp_files:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass


# =============================================================================
# Test Categories
# =============================================================================

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers and options."""
    # Skip integration tests unless --integration flag is provided
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="need --integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
    
    # Skip e2e tests unless --e2e flag is provided
    if not config.getoption("--e2e"):
        skip_e2e = pytest.mark.skip(reason="need --e2e option to run")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--integration", action="store_true", default=False,
        help="run integration tests"
    )
    parser.addoption(
        "--e2e", action="store_true", default=False,
        help="run end-to-end tests"
    )
    parser.addoption(
        "--load", action="store_true", default=False,
        help="run load tests"
    )
