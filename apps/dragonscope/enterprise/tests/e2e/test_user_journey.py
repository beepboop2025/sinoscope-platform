"""
End-to-end user journey tests.

Tests complete user workflows from signup to analysis.
"""

import pytest
import asyncio
from datetime import datetime, timezone

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestUserRegistrationJourney:
    """Test complete user registration workflow."""
    
    @pytest.fixture
    async def api_client(self, test_config):
        """Create authenticated API client."""
        import httpx
        async with httpx.AsyncClient(
            base_url=test_config['api_url'],
            timeout=30.0
        ) as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_complete_registration_flow(self, api_client):
        """Test user signup → email verification → login flow."""
        # Arrange
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        user_data = {
            'email': f'test_user_{timestamp}@dragonscope.test',
            'password': 'SecureTestPass123!',
            'first_name': 'Test',
            'last_name': 'User',
            'organization_name': f'Test Org {timestamp}'
        }
        
        # Step 1: User registration
        response = await api_client.post('/api/v1/auth/register', json=user_data)
        assert response.status_code == 201, f"Registration failed: {response.text}"
        
        user = response.json()
        assert user['email'] == user_data['email']
        assert 'id' in user
        assert 'password' not in user  # Password should not be returned
        user_id = user['id']
        
        # Step 2: Email verification (in real test, extract from email)
        # For E2E, we might use a test email API or mock
        verification_token = f"verify_{user_id}_{timestamp}"
        response = await api_client.post(
            f'/api/v1/auth/verify-email',
            json={'token': verification_token}
        )
        assert response.status_code == 200
        
        # Step 3: Login
        login_response = await api_client.post('/api/v1/auth/login', json={
            'email': user_data['email'],
            'password': user_data['password']
        })
        assert login_response.status_code == 200
        
        auth_data = login_response.json()
        assert 'access_token' in auth_data
        assert 'refresh_token' in auth_data
        
        # Step 4: Access protected resource
        headers = {'Authorization': f'Bearer {auth_data["access_token"]}'}
        profile_response = await api_client.get('/api/v1/users/me', headers=headers)
        assert profile_response.status_code == 200
        
        profile = profile_response.json()
        assert profile['email'] == user_data['email']
        assert profile['email_verified'] is True
    
    @pytest.mark.asyncio
    async def test_password_reset_flow(self, api_client):
        """Test forgot password → reset → login flow."""
        # Arrange - Create a user first
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        email = f'reset_test_{timestamp}@dragonscope.test'
        
        # Create user via API or directly in DB
        await api_client.post('/api/v1/auth/register', json={
            'email': email,
            'password': 'OriginalPassword123!',
            'first_name': 'Reset',
            'last_name': 'Test'
        })
        
        # Step 1: Request password reset
        response = await api_client.post('/api/v1/auth/forgot-password', json={
            'email': email
        })
        assert response.status_code in [200, 202]  # Accepted or OK
        
        # Step 2: Reset password with token (extracted from test email)
        reset_token = f"reset_token_for_{email}"
        new_password = 'NewSecurePassword456!'
        
        response = await api_client.post('/api/v1/auth/reset-password', json={
            'token': reset_token,
            'new_password': new_password
        })
        assert response.status_code == 200
        
        # Step 3: Login with new password
        login_response = await api_client.post('/api/v1/auth/login', json={
            'email': email,
            'password': new_password
        })
        assert login_response.status_code == 200
        
        # Step 4: Verify old password no longer works
        old_login = await api_client.post('/api/v1/auth/login', json={
            'email': email,
            'password': 'OriginalPassword123!'
        })
        assert old_login.status_code == 401


class TestDocumentAnalysisJourney:
    """Test complete document upload and analysis workflow."""
    
    @pytest.fixture
    async def authenticated_client(self, api_client):
        """Create authenticated client for testing."""
        # Login and return client with auth headers
        response = await api_client.post('/api/v1/auth/login', json={
            'email': 'e2e_test@dragonscope.test',
            'password': 'TestPassword123!'
        })
        
        token = response.json()['access_token']
        api_client.headers['Authorization'] = f'Bearer {token}'
        return api_client
    
    @pytest.mark.asyncio
    async def test_upload_document_and_analyze(self, authenticated_client):
        """Test upload → process → analyze → view results flow."""
        client = authenticated_client
        
        # Step 1: Create a project
        project_data = {
            'name': f'E2E Test Project {datetime.now().strftime("%Y%m%d%H%M%S")}',
            'description': 'Test project for E2E document analysis',
            'settings': {
                'analysis_depth': 'comprehensive',
                'enable_sentiment': True,
                'enable_entity_extraction': True
            }
        }
        
        response = await client.post('/api/v1/projects', json=project_data)
        assert response.status_code == 201
        
        project = response.json()
        project_id = project['id']
        
        # Step 2: Upload a document
        import io
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        
        files = {'file': ('test_document.pdf', io.BytesIO(pdf_content), 'application/pdf')}
        response = await client.post(
            f'/api/v1/projects/{project_id}/documents',
            files=files
        )
        assert response.status_code == 201
        
        document = response.json()
        document_id = document['id']
        assert document['status'] == 'pending'
        
        # Step 3: Wait for document processing
        max_attempts = 30
        for attempt in range(max_attempts):
            response = await client.get(f'/api/v1/documents/{document_id}')
            doc = response.json()
            
            if doc['status'] == 'processed':
                break
            elif doc['status'] == 'failed':
                pytest.fail(f"Document processing failed: {doc.get('error')}")
            
            await asyncio.sleep(2)
        else:
            pytest.fail("Document processing timeout")
        
        # Step 4: Request analysis
        analysis_request = {
            'document_ids': [document_id],
            'analysis_types': ['sentiment', 'entities', 'summary'],
            'options': {
                'language': 'en',
                'confidence_threshold': 0.8
            }
        }
        
        response = await client.post(
            f'/api/v1/projects/{project_id}/analyses',
            json=analysis_request
        )
        assert response.status_code == 202  # Accepted
        
        analysis = response.json()
        analysis_id = analysis['id']
        
        # Step 5: Wait for analysis completion
        for attempt in range(60):
            response = await client.get(f'/api/v1/analyses/{analysis_id}')
            analysis = response.json()
            
            if analysis['status'] == 'completed':
                break
            elif analysis['status'] == 'failed':
                pytest.fail(f"Analysis failed: {analysis.get('error')}")
            
            await asyncio.sleep(2)
        else:
            pytest.fail("Analysis timeout")
        
        # Step 6: Retrieve and verify results
        response = await client.get(f'/api/v1/analyses/{analysis_id}/results')
        assert response.status_code == 200
        
        results = response.json()
        assert 'sentiment' in results
        assert 'entities' in results
        assert 'summary' in results
    
    @pytest.mark.asyncio
    async def test_batch_document_upload(self, authenticated_client):
        """Test uploading multiple documents at once."""
        client = authenticated_client
        
        # Create project
        response = await client.post('/api/v1/projects', json={
            'name': f'Batch Upload Test {datetime.now().strftime("%Y%m%d%H%M%S")}'
        })
        project_id = response.json()['id']
        
        # Upload multiple documents
        import io
        documents = [
            ('doc1.pdf', b'%PDF-1.4...1', 'application/pdf'),
            ('doc2.pdf', b'%PDF-1.4...2', 'application/pdf'),
            ('doc3.txt', b'Text content', 'text/plain'),
        ]
        
        upload_ids = []
        for filename, content, mime in documents:
            files = {'file': (filename, io.BytesIO(content), mime)}
            response = await client.post(
                f'/api/v1/projects/{project_id}/documents',
                files=files
            )
            assert response.status_code == 201
            upload_ids.append(response.json()['id'])
        
        # Verify all documents are in project
        response = await client.get(f'/api/v1/projects/{project_id}/documents')
        docs = response.json()['items']
        
        assert len(docs) == 3
        assert all(d['id'] in upload_ids for d in docs)


class TestCollaborationJourney:
    """Test multi-user collaboration workflows."""
    
    @pytest.mark.asyncio
    async def test_invite_team_member(self, authenticated_client):
        """Test inviting and managing team members."""
        client = authenticated_client
        
        # Get current user's organization
        response = await client.get('/api/v1/users/me')
        org_id = response.json()['organization_id']
        
        # Create invitation
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        invite_data = {
            'email': f'invited_{timestamp}@dragonscope.test',
            'role': 'analyst',
            'message': 'Join our team!'
        }
        
        response = await client.post(
            f'/api/v1/organizations/{org_id}/invitations',
            json=invite_data
        )
        assert response.status_code == 201
        
        invitation = response.json()
        assert invitation['email'] == invite_data['email']
        assert invitation['role'] == invite_data['role']
        
        # List pending invitations
        response = await client.get(f'/api/v1/organizations/{org_id}/invitations')
        invitations = response.json()['items']
        assert any(i['email'] == invite_data['email'] for i in invitations)
    
    @pytest.mark.asyncio
    async def test_share_project_with_team(self, authenticated_client):
        """Test sharing project with team members."""
        client = authenticated_client
        
        # Create project
        response = await client.post('/api/v1/projects', json={
            'name': f'Shared Project {datetime.now().strftime("%Y%m%d%H%M%S")}'
        })
        project_id = response.json()['id']
        
        # Add member with specific permissions
        share_data = {
            'user_email': 'teammate@dragonscope.test',
            'permission': 'write'
        }
        
        response = await client.post(
            f'/api/v1/projects/{project_id}/members',
            json=share_data
        )
        assert response.status_code == 200
        
        # Verify member can access project (as that user)
        # This would require second authenticated client


class TestBillingJourney:
    """Test billing and subscription workflows."""
    
    @pytest.mark.asyncio
    async def test_subscription_upgrade(self, authenticated_client):
        """Test upgrading subscription plan."""
        client = authenticated_client
        
        # Get current subscription
        response = await client.get('/api/v1/billing/subscription')
        current = response.json()
        
        # Upgrade to pro plan
        upgrade_data = {
            'plan_id': 'pro_monthly',
            'payment_method_id': 'pm_test_123'
        }
        
        response = await client.post('/api/v1/billing/subscribe', json=upgrade_data)
        assert response.status_code in [200, 201]
        
        subscription = response.json()
        assert subscription['status'] == 'active'
        assert subscription['plan_id'] == upgrade_data['plan_id']
    
    @pytest.mark.asyncio
    async def test_usage_tracking(self, authenticated_client):
        """Test usage tracking and limits."""
        client = authenticated_client
        
        response = await client.get('/api/v1/billing/usage')
        assert response.status_code == 200
        
        usage = response.json()
        assert 'documents_processed' in usage
        assert 'analyses_run' in usage
        assert 'storage_used_bytes' in usage
        assert 'limits' in usage


class TestNotificationJourney:
    """Test notification delivery workflows."""
    
    @pytest.mark.asyncio
    async def test_analysis_completion_notification(self, authenticated_client):
        """Test receiving notification when analysis completes."""
        client = authenticated_client
        
        # Configure notification preferences
        prefs = {
            'email_notifications': True,
            'push_notifications': True,
            'events': ['analysis.completed', 'document.processed']
        }
        
        response = await client.put('/api/v1/users/me/notifications', json=prefs)
        assert response.status_code == 200
        
        # Start an analysis
        # (Implementation would create project, upload doc, start analysis)
        
        # Wait for notification
        # In real E2E test, check email API or WebSocket for notification
        
        # Verify notification received
        response = await client.get('/api/v1/notifications')
        notifications = response.json()['items']
        
        # Should have notification about analysis
        analysis_notifications = [
            n for n in notifications 
            if n['type'] == 'analysis.completed'
        ]
        assert len(analysis_notifications) > 0


class TestSearchJourney:
    """Test search functionality across documents."""
    
    @pytest.mark.asyncio
    async def test_full_text_search(self, authenticated_client):
        """Test searching across all accessible documents."""
        client = authenticated_client
        
        # Search for term
        search_query = {
            'query': 'quarterly report',
            'filters': {
                'date_from': '2024-01-01',
                'date_to': '2024-12-31'
            },
            'sort': 'relevance'
        }
        
        response = await client.post('/api/v1/search', json=search_query)
        assert response.status_code == 200
        
        results = response.json()
        assert 'hits' in results
        assert 'total' in results
        assert 'facets' in results
        
        # Verify search results have highlights
        for hit in results['hits']:
            assert 'highlight' in hit
            assert 'score' in hit
    
    @pytest.mark.asyncio
    async def test_advanced_filters_search(self, authenticated_client):
        """Test search with advanced filters."""
        client = authenticated_client
        
        search_query = {
            'query': 'financial',
            'filters': {
                'project_id': 'specific-project-id',
                'document_type': 'pdf',
                'size_min': 1024,
                'size_max': 10485760
            },
            'aggregations': ['by_month', 'by_type', 'by_project']
        }
        
        response = await client.post('/api/v1/search', json=search_query)
        assert response.status_code == 200
        
        results = response.json()
        assert 'aggregations' in results
        assert 'by_month' in results['aggregations']
