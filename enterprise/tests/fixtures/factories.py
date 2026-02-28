"""
Test data factories for DragonScope Enterprise.

Uses factory_boy pattern for generating test data.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import random
import string


class Factory:
    """Base factory class."""
    
    _model = dict
    
    @classmethod
    def build(cls, **overrides) -> Dict[str, Any]:
        """Build a single instance without saving."""
        data = cls._defaults()
        data.update(overrides)
        return data
    
    @classmethod
    def build_batch(cls, size: int, **overrides) -> List[Dict[str, Any]]:
        """Build multiple instances."""
        return [cls.build(**overrides) for _ in range(size)]
    
    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        """Return default values. Override in subclasses."""
        return {}
    
    @staticmethod
    def _uuid() -> str:
        """Generate a UUID string."""
        return str(uuid.uuid4())
    
    @staticmethod
    def _timestamp() -> datetime:
        """Generate current timestamp."""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def _random_string(length: int = 10) -> str:
        """Generate random string."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    @staticmethod
    def _random_email() -> str:
        """Generate random email."""
        return f"test_{Factory._random_string(8)}@example.com"


class UserFactory(Factory):
    """Factory for User model."""
    
    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        return {
            'id': cls._uuid(),
            'email': cls._random_email(),
            'first_name': 'Test',
            'last_name': 'User',
            'password_hash': 'hashed_password_placeholder',
            'role': random.choice(['admin', 'analyst', 'viewer']),
            'is_active': True,
            'email_verified': True,
            'organization_id': cls._uuid(),
            'created_at': cls._timestamp(),
            'updated_at': cls._timestamp(),
            'last_login': None,
            'avatar_url': None,
            'preferences': {
                'theme': 'light',
                'notifications': True,
                'language': 'en'
            }
        }
    
    @classmethod
    def admin(cls, **overrides):
        """Create an admin user."""
        return cls.build(role='admin', **overrides)
    
    @classmethod
    def analyst(cls, **overrides):
        """Create an analyst user."""
        return cls.build(role='analyst', **overrides)
    
    @classmethod
    def viewer(cls, **overrides):
        """Create a viewer user."""
        return cls.build(role='viewer', **overrides)
    
    @classmethod
    def inactive(cls, **overrides):
        """Create an inactive user."""
        return cls.build(is_active=False, **overrides)


class OrganizationFactory(Factory):
    """Factory for Organization model."""
    
    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        return {
            'id': cls._uuid(),
            'name': f'Test Organization {cls._random_string(5)}',
            'slug': f'test-org-{cls._random_string(5)}',
            'description': 'Test organization for testing',
            'plan': random.choice(['free', 'starter', 'professional', 'enterprise']),
            'settings': {
                'allowed_domains': [],
                'sso_enabled': False,
                'mfa_required': False
            },
            'billing_email': cls._random_email(),
            'created_at': cls._timestamp(),
            'updated_at': cls._timestamp()
        }


class ProjectFactory(Factory):
    """Factory for Project model."""
    
    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        return {
            'id': cls._uuid(),
            'name': f'Test Project {cls._random_string(5)}',
            'description': 'A test project for analysis',
            'owner_id': cls._uuid(),
            'organization_id': cls._uuid(),
            'status': random.choice(['active', 'archived']),
            'settings': {
                'analysis_depth': random.choice(['basic', 'standard', 'comprehensive']),
                'notifications_enabled': True,
                'auto_process': True,
                'allowed_file_types': ['pdf', 'docx', 'txt', 'csv']
            },
            'tags': ['test', 'demo'],
            'document_count': 0,
            'analysis_count': 0,
            'created_at': cls._timestamp(),
            'updated_at': cls._timestamp(),
            'archived_at': None
        }
    
    @classmethod
    def active(cls, **overrides):
        """Create an active project."""
        return cls.build(status='active', **overrides)
    
    @classmethod
    def archived(cls, **overrides):
        """Create an archived project."""
        return cls.build(
            status='archived',
            archived_at=cls._timestamp(),
            **overrides
        )


class DocumentFactory(Factory):
    """Factory for Document model."""
    
    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        return {
            'id': cls._uuid(),
            'project_id': cls._uuid(),
            'filename': f'document_{cls._random_string(5)}.pdf',
            'original_filename': 'original_document.pdf',
            'content_type': 'application/pdf',
            'size': random.randint(1024, 104857600),  # 1KB to 100MB
            'storage_key': f'projects/{cls._uuid()}/{cls._uuid()}.pdf',
            'status': random.choice(['pending', 'processing', 'processed', 'failed']),
            'metadata': {
                'pages': random.randint(1, 100),
                'word_count': random.randint(100, 50000),
                'language': random.choice(['en', 'es', 'fr', 'de']),
                'extracted_text_length': random.randint(1000, 100000)
            },
            'processing_error': None,
            'created_at': cls._timestamp(),
            'processed_at': None,
            'uploaded_by': cls._uuid()
        }
    
    @classmethod
    def processed(cls, **overrides):
        """Create a processed document."""
        return cls.build(
            status='processed',
            processed_at=cls._timestamp(),
            **overrides
        )
    
    @classmethod
    def failed(cls, error='Processing failed', **overrides):
        """Create a failed document."""
        return cls.build(
            status='failed',
            processing_error=error,
            **overrides
        )


class AnalysisFactory(Factory):
    """Factory for Analysis model."""
    
    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        return {
            'id': cls._uuid(),
            'project_id': cls._uuid(),
            'document_ids': [cls._uuid() for _ in range(random.randint(1, 5))],
            'analysis_type': random.choice(['sentiment', 'entities', 'topics', 'summary', 'custom']),
            'status': random.choice(['pending', 'running', 'completed', 'failed']),
            'progress': 0,
            'options': {
                'language': 'en',
                'confidence_threshold': 0.8,
                'max_entities': 100
            },
            'results': None,
            'error': None,
            'processing_time_ms': None,
            'created_at': cls._timestamp(),
            'started_at': None,
            'completed_at': None,
            'created_by': cls._uuid()
        }
    
    @classmethod
    def completed(cls, **overrides):
        """Create a completed analysis with results."""
        analysis_type = overrides.get('analysis_type', 'sentiment')
        
        results = {
            'sentiment': {
                'overall': 'positive',
                'confidence': 0.92,
                'scores': {
                    'positive': 0.85,
                    'neutral': 0.10,
                    'negative': 0.05
                }
            },
            'entities': [
                {'text': 'DragonScope', 'type': 'ORG', 'confidence': 0.95},
                {'text': 'John Doe', 'type': 'PERSON', 'confidence': 0.88}
            ],
            'summary': 'This is a generated summary of the document analysis.'
        }
        
        return cls.build(
            status='completed',
            progress=100,
            results=results.get(analysis_type, results),
            processing_time_ms=random.randint(1000, 30000),
            started_at=cls._timestamp(),
            completed_at=cls._timestamp(),
            **overrides
        )


class WebhookFactory(Factory):
    """Factory for Webhook model."""
    
    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        return {
            'id': cls._uuid(),
            'organization_id': cls._uuid(),
            'url': 'https://example.com/webhook',
            'events': ['analysis.completed', 'document.processed'],
            'secret': cls._random_string(32),
            'is_active': True,
            'created_at': cls._timestamp(),
            'updated_at': cls._timestamp()
        }


class APIKeyFactory(Factory):
    """Factory for API Key model."""
    
    @classmethod
    def _defaults(cls) -> Dict[str, Any]:
        return {
            'id': cls._uuid(),
            'organization_id': cls._uuid(),
            'name': f'API Key {cls._random_string(5)}',
            'key_prefix': cls._random_string(8),
            'scopes': ['read', 'write'],
            'is_active': True,
            'last_used_at': None,
            'expires_at': None,
            'created_at': cls._timestamp()
        }


# =========================================================================
# Fixtures for common test scenarios
# =========================================================================

class ScenarioFactory:
    """Factory for creating complex test scenarios."""
    
    @staticmethod
    def create_organization_with_users(num_users: int = 3) -> Dict[str, Any]:
        """Create an organization with multiple users."""
        org = OrganizationFactory.build()
        users = UserFactory.build_batch(num_users, organization_id=org['id'])
        
        # Make first user admin
        users[0]['role'] = 'admin'
        
        return {
            'organization': org,
            'users': users
        }
    
    @staticmethod
    def create_project_with_documents(
        num_documents: int = 5,
        doc_status: str = 'processed'
    ) -> Dict[str, Any]:
        """Create a project with documents."""
        project = ProjectFactory.build()
        
        documents = []
        for i in range(num_documents):
            if doc_status == 'processed':
                doc = DocumentFactory.processed(
                    project_id=project['id'],
                    filename=f'doc_{i}.pdf'
                )
            else:
                doc = DocumentFactory.build(
                    project_id=project['id'],
                    status=doc_status,
                    filename=f'doc_{i}.pdf'
                )
            documents.append(doc)
        
        project['document_count'] = len(documents)
        
        return {
            'project': project,
            'documents': documents
        }
    
    @staticmethod
    def create_analysis_pipeline() -> Dict[str, Any]:
        """Create a complete analysis pipeline scenario."""
        # Create project with documents
        scenario = ScenarioFactory.create_project_with_documents(
            num_documents=3,
            doc_status='processed'
        )
        
        # Create analyses
        analyses = []
        for analysis_type in ['sentiment', 'entities', 'summary']:
            analysis = AnalysisFactory.completed(
                project_id=scenario['project']['id'],
                document_ids=[d['id'] for d in scenario['documents']],
                analysis_type=analysis_type
            )
            analyses.append(analysis)
        
        scenario['project']['analysis_count'] = len(analyses)
        scenario['analyses'] = analyses
        
        return scenario
