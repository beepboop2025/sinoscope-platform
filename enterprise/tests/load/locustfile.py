"""
Locust load testing configuration for DragonScope Enterprise.

Run with: locust -f tests/load/locustfile.py --host=http://localhost:8000
"""

import random
import json
from datetime import datetime, timezone
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


class DragonScopeUser(HttpUser):
    """Simulated DragonScope Enterprise user."""
    
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    
    def on_start(self):
        """Called when a user starts."""
        self.login()
        self.projects = []
    
    def login(self):
        """Authenticate and store token."""
        response = self.client.post('/api/v1/auth/login', json={
            'email': f'loadtest_user_{self.user_id}@dragonscope.test',
            'password': 'LoadTestPass123!'
        })
        
        if response.status_code == 200:
            self.token = response.json()['access_token']
            self.headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
        else:
            # Create user if doesn't exist
            self.register()
    
    def register(self):
        """Register a new test user."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        response = self.client.post('/api/v1/auth/register', json={
            'email': f'loadtest_user_{self.user_id}@dragonscope.test',
            'password': 'LoadTestPass123!',
            'first_name': 'Load',
            'last_name': f'Test{self.user_id}',
            'organization_name': f'Load Test Org {self.user_id}'
        })
        
        if response.status_code == 201:
            # Login after registration
            self.login()
    
    # =========================================================================
    # API Tasks (Weight: 40% - Most common operations)
    # =========================================================================
    
    @task(10)
    def get_projects(self):
        """Load test: List user's projects."""
        self.client.get('/api/v1/projects', headers=self.headers)
    
    @task(8)
    def get_project_details(self):
        """Load test: Get specific project details.""""
        if self.projects:
            project_id = random.choice(self.projects)
            self.client.get(f'/api/v1/projects/{project_id}', headers=self.headers)
        else:
            # Fetch projects first
            response = self.client.get('/api/v1/projects', headers=self.headers)
            if response.status_code == 200:
                self.projects = [p['id'] for p in response.json().get('items', [])]
    
    @task(6)
    def get_documents(self):
        """Load test: List documents in a project."""
        if self.projects:
            project_id = random.choice(self.projects)
            self.client.get(
                f'/api/v1/projects/{project_id}/documents',
                headers=self.headers,
                params={'page': random.randint(1, 5), 'per_page': 20}
            )
    
    @task(5)
    def search_documents(self):
        """Load test: Search across documents."""
        search_terms = ['quarterly', 'report', 'financial', 'analysis', 'data', 'review']
        
        self.client.post('/api/v1/search', 
                         headers=self.headers,
                         json={
                             'query': random.choice(search_terms),
                             'page': 1,
                             'per_page': 20
                         })
    
    @task(4)
    def get_user_profile(self):
        """Load test: Get current user profile."""
        self.client.get('/api/v1/users/me', headers=self.headers)
    
    @task(3)
    def get_notifications(self):
        """Load test: Get user notifications."""
        self.client.get('/api/v1/notifications', 
                        headers=self.headers,
                        params={'unread_only': random.choice([True, False])})
    
    @task(2)
    def get_analyses(self):
        """Load test: List analyses."""
        if self.projects:
            project_id = random.choice(self.projects)
            self.client.get(
                f'/api/v1/projects/{project_id}/analyses',
                headers=self.headers
            )
    
    # =========================================================================
    # Write Tasks (Weight: 20% - Less frequent modifications)
    # =========================================================================
    
    @task(3)
    def create_project(self):
        """Load test: Create a new project."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        response = self.client.post('/api/v1/projects',
                                    headers=self.headers,
                                    json={
                                        'name': f'Load Test Project {timestamp}',
                                        'description': 'Created during load test',
                                        'settings': {
                                            'analysis_depth': random.choice(['basic', 'standard', 'comprehensive'])
                                        }
                                    })
        
        if response.status_code == 201:
            project_id = response.json()['id']
            self.projects.append(project_id)
    
    @task(2)
    def update_project(self):
        """Load test: Update project settings."""
        if self.projects:
            project_id = random.choice(self.projects)
            self.client.patch(f'/api/v1/projects/{project_id}',
                              headers=self.headers,
                              json={
                                  'description': f'Updated at {datetime.now().isoformat()}',
                                  'settings': {'notifications_enabled': random.choice([True, False])}
                              })
    
    @task(2)
    def create_analysis(self):
        """Load test: Create a new analysis request."""
        if self.projects:
            project_id = random.choice(self.projects)
            self.client.post(f'/api/v1/projects/{project_id}/analyses',
                             headers=self.headers,
                             json={
                                 'analysis_types': random.sample(
                                     ['sentiment', 'entities', 'topics', 'summary'],
                                     k=random.randint(1, 3)
                                 ),
                                 'options': {
                                     'confidence_threshold': random.uniform(0.7, 0.95)
                                 }
                             })
    
    @task(1)
    def mark_notification_read(self):
        """Load test: Mark notifications as read."""
        self.client.post('/api/v1/notifications/mark-read',
                         headers=self.headers,
                         json={'notification_ids': []})  # Mark all as read
    
    # =========================================================================
    # File Upload Tasks (Weight: 10% - Heavy operations)
    # =========================================================================
    
    @task(1)
    def upload_small_document(self):
        """Load test: Upload a small document."""
        if self.projects:
            project_id = random.choice(self.projects)
            
            # Create a small PDF-like content
            content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
            
            files = {'file': ('test_document.pdf', content, 'application/pdf')}
            
            self.client.post(f'/api/v1/projects/{project_id}/documents',
                             headers={'Authorization': self.headers['Authorization']},
                             files=files)
    
    # =========================================================================
    # Rare Tasks (Weight: 5% - Infrequent operations)
    # =========================================================================
    
    @task(1)
    def get_billing_info(self):
        """Load test: Get billing information."""
        self.client.get('/api/v1/billing/subscription', headers=self.headers)
    
    @task(1)
    def get_usage_stats(self):
        """Load test: Get usage statistics."""
        self.client.get('/api/v1/billing/usage', headers=self.headers)
    
    def on_stop(self):
        """Called when a user stops."""
        # Cleanup if needed
        pass


class HeavyUser(HttpUser):
    """Heavy user performing intensive operations."""
    
    wait_time = between(0.5, 2)
    weight = 1  # 1 heavy user for every 10 regular users
    
    def on_start(self):
        """Setup for heavy user."""
        # Login as admin/power user
        response = self.client.post('/api/v1/auth/login', json={
            'email': 'heavy_user@dragonscope.test',
            'password': 'HeavyLoadPass123!'
        })
        
        if response.status_code == 200:
            self.token = response.json()['access_token']
            self.headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
    
    @task(5)
    def batch_operations(self):
        """Perform batch operations."""
        # Create multiple projects
        for i in range(5):
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
            self.client.post('/api/v1/projects',
                             headers=self.headers,
                             json={
                                 'name': f'Heavy Batch Project {timestamp}-{i}',
                                 'description': 'Batch created'
                             })
    
    @task(3)
    def complex_search(self):
        """Perform complex search with aggregations."""
        self.client.post('/api/v1/search',
                         headers=self.headers,
                         json={
                             'query': 'financial report',
                             'filters': {
                                 'date_from': '2024-01-01',
                                 'date_to': '2024-12-31',
                                 'document_type': 'pdf'
                             },
                             'aggregations': ['by_month', 'by_project', 'by_type'],
                             'sort': 'relevance'
                         })
    
    @task(2)
    def export_data(self):
        """Trigger data export."""
        self.client.post('/api/v1/exports',
                         headers=self.headers,
                         json={
                             'format': random.choice(['csv', 'json', 'xlsx']),
                             'entity_type': random.choice(['projects', 'documents', 'analyses'])
                         })


class APIUser(HttpUser):
    """API-only user for programmatic access simulation."""
    
    wait_time = between(0.1, 1)  # Very fast API calls
    weight = 2
    
    def on_start(self):
        """Setup API client."""
        response = self.client.post('/api/v1/auth/login', json={
            'email': 'api_client@dragonscope.test',
            'password': 'ApiClientPass123!'
        })
        
        if response.status_code == 200:
            self.token = response.json()['access_token']
            self.headers = {'Authorization': f'Bearer {self.token}'}
    
    @task(10)
    def api_get_health(self):
        """Health check endpoint."""
        self.client.get('/api/v1/health')
    
    @task(5)
    def api_get_metrics(self):
        """Get system metrics."""
        self.client.get('/api/v1/metrics', headers=self.headers)
    
    @task(5)
    def api_list_webhooks(self):
        """List webhooks."""
        self.client.get('/api/v1/webhooks', headers=self.headers)


# =========================================================================
# Custom Events and Statistics
# =========================================================================

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, 
               response, context, exception, **kwargs):
    """Custom request handler for additional metrics."""
    if exception:
        # Log errors for analysis
        print(f"Request failed: {name} - {exception}")


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Generate summary report when test completes."""
    if isinstance(environment.runner, MasterRunner):
        print("\n" + "=" * 60)
        print("LOAD TEST SUMMARY")
        print("=" * 60)
        
        stats = environment.runner.stats
        
        print(f"\nTotal Requests: {stats.total.num_requests}")
        print(f"Failed Requests: {stats.total.num_failures}")
        print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
        print(f"95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
        print(f"99th Percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
        print(f"RPS: {stats.total.total_rps:.2f}")
        
        # Check SLA compliance
        p95 = stats.total.get_response_time_percentile(0.95)
        if p95 > 500:  # 500ms SLA
            print("\nWARNING: 95th percentile exceeds 500ms SLA!")
        
        if stats.total.num_failures / max(stats.total.num_requests, 1) > 0.01:
            print("\nWARNING: Failure rate exceeds 1%!")


# =========================================================================
# Load Test Scenarios
# =========================================================================

class SteadyLoadShape:
    """Steady load shape for sustained testing."""
    
    def tick(self):
        """Return user count for this tick."""
        # Run 100 users for 10 minutes
        return (100, 100)  # (spawn_rate, user_count)


class SpikeTestShape:
    """Spike test load shape."""
    
    def tick(self):
        """Simulate traffic spike."""
        import time
        run_time = time.time() - self.start_time if hasattr(self, 'start_time') else 0
        
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()
        
        run_time = time.time() - self.start_time
        
        # Normal load for 2 minutes
        if run_time < 120:
            return (10, 50)
        # Spike to 500 users
        elif run_time < 180:
            return (100, 500)
        # Back to normal
        else:
            return (10, 50)


class RampUpShape:
    """Gradual ramp-up load shape."""
    
    def tick(self):
        """Gradually increase users."""
        import time
        
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()
        
        run_time = time.time() - self.start_time
        
        # Ramp up over 5 minutes
        if run_time < 300:
            user_count = int((run_time / 300) * 200)
            return (10, max(user_count, 1))
        else:
            return (10, 200)
