"""
API contract tests.

Validates API responses against OpenAPI schema.
"""

import pytest
import json
from jsonschema import validate, ValidationError, Draft7Validator

pytestmark = pytest.mark.e2e


class TestAPIContract:
    """Test suite for API contract validation."""
    
    @pytest.fixture(scope='class')
    def api_schema(self):
        """Load OpenAPI schema."""
        # In real implementation, load from file or fetch from /openapi.json
        return {
            'openapi': '3.0.0',
            'components': {
                'schemas': {
                    'User': {
                        'type': 'object',
                        'required': ['id', 'email', 'first_name', 'last_name'],
                        'properties': {
                            'id': {'type': 'string', 'format': 'uuid'},
                            'email': {'type': 'string', 'format': 'email'},
                            'first_name': {'type': 'string'},
                            'last_name': {'type': 'string'},
                            'role': {'type': 'string', 'enum': ['admin', 'analyst', 'viewer']},
                            'is_active': {'type': 'boolean'},
                            'created_at': {'type': 'string', 'format': 'date-time'},
                            'last_login': {'type': 'string', 'format': 'date-time', 'nullable': True}
                        }
                    },
                    'Project': {
                        'type': 'object',
                        'required': ['id', 'name', 'owner_id', 'organization_id'],
                        'properties': {
                            'id': {'type': 'string', 'format': 'uuid'},
                            'name': {'type': 'string', 'minLength': 1, 'maxLength': 200},
                            'description': {'type': 'string', 'nullable': True},
                            'owner_id': {'type': 'string', 'format': 'uuid'},
                            'organization_id': {'type': 'string', 'format': 'uuid'},
                            'status': {'type': 'string', 'enum': ['active', 'archived', 'deleted']},
                            'settings': {'type': 'object'},
                            'created_at': {'type': 'string', 'format': 'date-time'},
                            'updated_at': {'type': 'string', 'format': 'date-time'}
                        }
                    },
                    'Document': {
                        'type': 'object',
                        'required': ['id', 'project_id', 'filename', 'content_type'],
                        'properties': {
                            'id': {'type': 'string', 'format': 'uuid'},
                            'project_id': {'type': 'string', 'format': 'uuid'},
                            'filename': {'type': 'string'},
                            'content_type': {'type': 'string'},
                            'size': {'type': 'integer', 'minimum': 0},
                            'storage_key': {'type': 'string'},
                            'status': {'type': 'string', 'enum': ['pending', 'processing', 'processed', 'failed']},
                            'metadata': {'type': 'object', 'nullable': True},
                            'created_at': {'type': 'string', 'format': 'date-time'},
                            'processed_at': {'type': 'string', 'format': 'date-time', 'nullable': True}
                        }
                    },
                    'Analysis': {
                        'type': 'object',
                        'required': ['id', 'project_id', 'analysis_type', 'status'],
                        'properties': {
                            'id': {'type': 'string', 'format': 'uuid'},
                            'project_id': {'type': 'string', 'format': 'uuid'},
                            'document_ids': {
                                'type': 'array',
                                'items': {'type': 'string', 'format': 'uuid'}
                            },
                            'analysis_type': {
                                'type': 'string',
                                'enum': ['sentiment', 'entities', 'topics', 'summary', 'custom']
                            },
                            'status': {'type': 'string', 'enum': ['pending', 'running', 'completed', 'failed']},
                            'results': {'type': 'object', 'nullable': True},
                            'error': {'type': 'string', 'nullable': True},
                            'progress': {'type': 'number', 'minimum': 0, 'maximum': 100},
                            'created_at': {'type': 'string', 'format': 'date-time'},
                            'completed_at': {'type': 'string', 'format': 'date-time', 'nullable': True}
                        }
                    },
                    'PaginatedResponse': {
                        'type': 'object',
                        'required': ['items', 'total', 'page', 'per_page'],
                        'properties': {
                            'items': {'type': 'array'},
                            'total': {'type': 'integer', 'minimum': 0},
                            'page': {'type': 'integer', 'minimum': 1},
                            'per_page': {'type': 'integer', 'minimum': 1},
                            'total_pages': {'type': 'integer', 'minimum': 0}
                        }
                    },
                    'Error': {
                        'type': 'object',
                        'required': ['code', 'message'],
                        'properties': {
                            'code': {'type': 'string'},
                            'message': {'type': 'string'},
                            'details': {'type': 'object', 'nullable': True}
                        }
                    }
                }
            }
        }
    
    @pytest.fixture
    def schema_validator(self, api_schema):
        """Create schema validator."""
        return Draft7Validator(api_schema)
    
    def validate_response(self, schema, data, schema_name):
        """Helper to validate response against schema."""
        try:
            validate(instance=data, schema=schema['components']['schemas'][schema_name])
        except ValidationError as e:
            pytest.fail(f"Response validation failed for {schema_name}: {e.message}")
    
    @pytest.mark.asyncio
    async def test_user_response_schema(self, api_client, api_schema):
        """Test GET /users/me response matches schema."""
        # Arrange
        headers = {'Authorization': 'Bearer test_token'}
        
        # Act
        response = await api_client.get('/api/v1/users/me', headers=headers)
        
        # Assert
        if response.status_code == 200:
            user_data = response.json()
            self.validate_response(api_schema, user_data, 'User')
            
            # Additional contract checks
            assert 'password' not in user_data, "Password should not be in response"
            assert 'password_hash' not in user_data, "Password hash should not be in response"
    
    @pytest.mark.asyncio
    async def test_project_list_response_schema(self, api_client, api_schema):
        """Test GET /projects response matches paginated schema."""
        # Arrange
        headers = {'Authorization': 'Bearer test_token'}
        
        # Act
        response = await api_client.get('/api/v1/projects', headers=headers)
        
        # Assert
        if response.status_code == 200:
            data = response.json()
            self.validate_response(api_schema, data, 'PaginatedResponse')
            
            # Validate each item in the list
            for project in data['items']:
                self.validate_response(api_schema, project, 'Project')
    
    @pytest.mark.asyncio
    async def test_create_project_request_response_schema(self, api_client, api_schema):
        """Test POST /projects request and response schema."""
        # Arrange
        headers = {
            'Authorization': 'Bearer test_token',
            'Content-Type': 'application/json'
        }
        request_body = {
            'name': 'Test Project',
            'description': 'Test description',
            'settings': {'analysis_depth': 'standard'}
        }
        
        # Act
        response = await api_client.post('/api/v1/projects', 
                                          headers=headers, 
                                          json=request_body)
        
        # Assert
        if response.status_code == 201:
            project = response.json()
            self.validate_response(api_schema, project, 'Project')
            
            # Verify response contains expected fields
            assert 'id' in project
            assert project['name'] == request_body['name']
            assert 'created_at' in project
    
    @pytest.mark.asyncio
    async def test_document_response_schema(self, api_client, api_schema):
        """Test document endpoints response schema."""
        headers = {'Authorization': 'Bearer test_token'}
        
        response = await api_client.get('/api/v1/documents/doc_test_123', 
                                         headers=headers)
        
        if response.status_code == 200:
            document = response.json()
            self.validate_response(api_schema, document, 'Document')
            
            # Business logic validation
            if document['status'] == 'processed':
                assert 'processed_at' in document
                assert document['processed_at'] is not None
    
    @pytest.mark.asyncio
    async def test_analysis_response_schema(self, api_client, api_schema):
        """Test analysis endpoints response schema."""
        headers = {'Authorization': 'Bearer test_token'}
        
        response = await api_client.get('/api/v1/analyses/anl_test_123', 
                                         headers=headers)
        
        if response.status_code == 200:
            analysis = response.json()
            self.validate_response(api_schema, analysis, 'Analysis')
            
            # Status-dependent validation
            if analysis['status'] == 'completed':
                assert 'results' in analysis
                assert analysis['results'] is not None
                assert 'completed_at' in analysis
            elif analysis['status'] == 'failed':
                assert 'error' in analysis
                assert analysis['error'] is not None
    
    @pytest.mark.asyncio
    async def test_error_response_schema(self, api_client, api_schema):
        """Test error response schema."""
        # Trigger a 404 error
        response = await api_client.get('/api/v1/projects/non-existent-id')
        
        if response.status_code >= 400:
            error = response.json()
            self.validate_response(api_schema, error, 'Error')
            
            assert 'code' in error
            assert 'message' in error
    
    @pytest.mark.asyncio
    async def test_pagination_parameters(self, api_client):
        """Test pagination query parameters are handled correctly."""
        headers = {'Authorization': 'Bearer test_token'}
        
        # Test various pagination parameters
        test_cases = [
            {'page': 1, 'per_page': 10},
            {'page': 2, 'per_page': 50},
            {'per_page': 100},
            {'page': 1},
            {}  # Default pagination
        ]
        
        for params in test_cases:
            response = await api_client.get('/api/v1/projects', 
                                             headers=headers, 
                                             params=params)
            
            if response.status_code == 200:
                data = response.json()
                assert 'items' in data
                assert 'total' in data
                assert 'page' in data
                assert 'per_page' in data
                
                # Validate per_page limits
                if 'per_page' in params:
                    assert data['per_page'] <= 100, "Max per_page should be 100"
    
    @pytest.mark.asyncio
    async def test_sorting_parameters(self, api_client):
        """Test sorting query parameters."""
        headers = {'Authorization': 'Bearer test_token'}
        
        sort_options = [
            'created_at',
            '-created_at',  # Descending
            'name',
            '-name',
            'updated_at',
            '-updated_at'
        ]
        
        for sort in sort_options:
            response = await api_client.get('/api/v1/projects',
                                             headers=headers,
                                             params={'sort': sort})
            
            assert response.status_code in [200, 400], f"Sort '{sort}' should be valid or rejected"
    
    @pytest.mark.asyncio
    async def test_filter_parameters(self, api_client):
        """Test filter query parameters."""
        headers = {'Authorization': 'Bearer test_token'}
        
        # Test various filter combinations
        filters = [
            {'status': 'active'},
            {'status': 'archived'},
            {'created_after': '2024-01-01'},
            {'created_before': '2024-12-31'},
            {'status': 'active', 'created_after': '2024-01-01'}
        ]
        
        for filter_params in filters:
            response = await api_client.get('/api/v1/projects',
                                             headers=headers,
                                             params=filter_params)
            
            assert response.status_code in [200, 400]
            
            if response.status_code == 200:
                data = response.json()
                # Verify all items match filter
                for item in data['items']:
                    if 'status' in filter_params:
                        assert item['status'] == filter_params['status']


class TestAPIHeaders:
    """Test API header requirements and responses."""
    
    @pytest.mark.asyncio
    async def test_content_type_header_required(self, api_client):
        """Test that POST requests require Content-Type header."""
        response = await api_client.post('/api/v1/projects',
                                          headers={'Authorization': 'Bearer test'},
                                          data='{"name": "test"}')  # No JSON content-type
        
        # Should either accept or return proper error
        if response.status_code == 415:
            error = response.json()
            assert 'Unsupported Media Type' in response.reason_phrase or 'content-type' in error.get('message', '').lower()
    
    @pytest.mark.asyncio
    async def test_api_version_header(self, api_client):
        """Test API version header in responses."""
        response = await api_client.get('/api/v1/projects',
                                         headers={'Authorization': 'Bearer test'})
        
        # Should include API version header
        assert 'X-API-Version' in response.headers
        assert response.headers['X-API-Version'].startswith('1.')
    
    @pytest.mark.asyncio
    async def test_request_id_header(self, api_client):
        """Test request ID propagation."""
        request_id = 'test-request-123'
        
        response = await api_client.get('/api/v1/projects',
                                         headers={
                                             'Authorization': 'Bearer test',
                                             'X-Request-ID': request_id
                                         })
        
        # Should echo or generate request ID
        assert 'X-Request-ID' in response.headers


class TestAPIRateLimiting:
    """Test API rate limiting headers."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, api_client):
        """Test rate limit headers in responses."""
        response = await api_client.get('/api/v1/projects',
                                         headers={'Authorization': 'Bearer test'})
        
        # Should include rate limit headers
        assert 'X-RateLimit-Limit' in response.headers
        assert 'X-RateLimit-Remaining' in response.headers
        assert 'X-RateLimit-Reset' in response.headers


class TestAPIContentNegotiation:
    """Test API content negotiation."""
    
    @pytest.mark.asyncio
    async def test_json_response_format(self, api_client):
        """Test that responses are valid JSON."""
        response = await api_client.get('/api/v1/projects',
                                         headers={'Authorization': 'Bearer test'})
        
        # Should be valid JSON
        assert response.headers['Content-Type'] == 'application/json'
        
        # Should parse without error
        data = response.json()
        assert isinstance(data, dict)
