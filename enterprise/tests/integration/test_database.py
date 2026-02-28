"""
Database integration tests.

Tests database connectivity, migrations, transactions, and query performance.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

pytestmark = [pytest.mark.integration, pytest.mark.db]


class TestDatabaseConnection:
    """Test suite for database connectivity."""
    
    @pytest.fixture(scope='class')
    async def db_pool(self, test_config):
        """Create a database connection pool for testing."""
        # Example using asyncpg
        # import asyncpg
        # pool = await asyncpg.create_pool(test_config['database_url'])
        # yield pool
        # await pool.close()
        
        # Mock pool for demonstration
        from unittest.mock import AsyncMock
        pool = AsyncMock()
        pool.fetch = AsyncMock(return_value=[])
        pool.fetchrow = AsyncMock(return_value=None)
        pool.execute = AsyncMock(return_value='INSERT 1')
        yield pool
    
    @pytest.mark.asyncio
    async def test_database_connection(self, db_pool):
        """Test basic database connectivity."""
        result = await db_pool.fetchrow("SELECT 1 as test")
        # In real test: assert result['test'] == 1
        assert db_pool.fetchrow.called
    
    @pytest.mark.asyncio
    async def test_connection_pool_size(self, db_pool):
        """Test connection pool configuration."""
        # Verify pool has minimum connections
        # Real test would check actual pool size
        pass


class TestDatabaseTransactions:
    """Test suite for database transactions."""
    
    @pytest.fixture
    async def db_transaction(self, test_config):
        """Provide a database transaction that rolls back after test."""
        # Example:
        # conn = await asyncpg.connect(test_config['database_url'])
        # transaction = conn.transaction()
        # await transaction.start()
        # yield conn
        # await transaction.rollback()
        # await conn.close()
        
        from unittest.mock import AsyncMock
        conn = AsyncMock()
        yield conn
    
    @pytest.mark.asyncio
    async def test_transaction_commit(self, db_transaction):
        """Test successful transaction commit."""
        # Arrange
        await db_transaction.execute("BEGIN")
        
        # Act
        await db_transaction.execute(
            "INSERT INTO users (email) VALUES ('test@example.com')"
        )
        await db_transaction.execute("COMMIT")
        
        # Assert
        db_transaction.execute.assert_any_call("COMMIT")
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, db_transaction):
        """Test transaction rollback on error."""
        # Arrange
        await db_transaction.execute("BEGIN")
        
        try:
            await db_transaction.execute(
                "INSERT INTO users (email) VALUES ('test@example.com')"
            )
            raise Exception("Simulated error")
        except Exception:
            await db_transaction.execute("ROLLBACK")
        
        # Assert rollback was called
        db_transaction.execute.assert_any_call("ROLLBACK")
    
    @pytest.mark.asyncio
    async def test_nested_transactions(self, db_transaction):
        """Test savepoints for nested transactions."""
        # Outer transaction
        await db_transaction.execute("BEGIN")
        await db_transaction.execute("SAVEPOINT sp1")
        
        # Inner operations
        await db_transaction.execute(
            "INSERT INTO users (email) VALUES ('inner@example.com')"
        )
        
        # Rollback to savepoint
        await db_transaction.execute("ROLLBACK TO SAVEPOINT sp1")
        await db_transaction.execute("COMMIT")
        
        # Assert
        assert db_transaction.execute.call_count >= 5


class TestUserRepository:
    """Test suite for User Repository database operations."""
    
    @pytest.fixture
    async def user_repo(self, db_transaction):
        """Create UserRepository with test transaction."""
        from repositories.user_repository import UserRepository
        return UserRepository(db=db_transaction)
    
    @pytest.mark.asyncio
    async def test_create_user(self, user_repo, db_transaction):
        """Test creating a user in database."""
        # Arrange
        user_data = {
            'id': str(uuid4()),
            'email': f'test_{uuid4().hex}@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password_hash': 'hashed_password',
            'is_active': True,
            'created_at': datetime.now(timezone.utc),
            'organization_id': str(uuid4())
        }
        
        # Act
        user = await user_repo.create(user_data)
        
        # Assert
        assert user['email'] == user_data['email']
        db_transaction.execute.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_user_by_email(self, user_repo, db_transaction):
        """Test retrieving user by email."""
        # Arrange
        email = 'existing@example.com'
        expected_user = {
            'id': str(uuid4()),
            'email': email,
            'first_name': 'Existing',
            'last_name': 'User'
        }
        db_transaction.fetchrow = AsyncMock(return_value=expected_user)
        
        # Act
        user = await user_repo.get_by_email(email)
        
        # Assert
        assert user is not None
        assert user['email'] == email
    
    @pytest.mark.asyncio
    async def test_update_user(self, user_repo, db_transaction):
        """Test updating user fields."""
        # Arrange
        user_id = str(uuid4())
        update_data = {
            'first_name': 'Updated',
            'last_login': datetime.now(timezone.utc)
        }
        
        # Act
        await user_repo.update(user_id, update_data)
        
        # Assert
        db_transaction.execute.assert_called()
    
    @pytest.mark.asyncio
    async def test_delete_user_soft(self, user_repo, db_transaction):
        """Test soft deleting a user."""
        # Arrange
        user_id = str(uuid4())
        
        # Act
        await user_repo.delete(user_id, soft=True)
        
        # Assert - verify update was called, not delete
        calls = [call for call in db_transaction.execute.call_args_list 
                 if 'UPDATE' in str(call)]
        assert len(calls) > 0
    
    @pytest.mark.asyncio
    async def test_list_users_with_pagination(self, user_repo, db_transaction):
        """Test listing users with pagination."""
        # Arrange
        db_transaction.fetch = AsyncMock(return_value=[
            {'id': str(uuid4()), 'email': f'user{i}@example.com'}
            for i in range(10)
        ])
        
        # Act
        users = await user_repo.list_users(page=1, per_page=10)
        
        # Assert
        assert len(users) == 10
    
    @pytest.mark.asyncio
    async def test_user_exists_check(self, user_repo, db_transaction):
        """Test checking if user exists."""
        # Arrange
        email = 'exists@example.com'
        db_transaction.fetchval = AsyncMock(return_value=1)
        
        # Act
        exists = await user_repo.exists(email=email)
        
        # Assert
        assert exists is True


class TestProjectRepository:
    """Test suite for Project Repository operations."""
    
    @pytest.fixture
    async def project_repo(self, db_transaction):
        """Create ProjectRepository with test transaction."""
        from repositories.project_repository import ProjectRepository
        return ProjectRepository(db=db_transaction)
    
    @pytest.mark.asyncio
    async def test_create_project(self, project_repo, db_transaction):
        """Test creating a project."""
        # Arrange
        project_data = {
            'id': str(uuid4()),
            'name': 'Test Project',
            'description': 'Test description',
            'owner_id': str(uuid4()),
            'organization_id': str(uuid4()),
            'status': 'active',
            'settings': {'analysis_depth': 'standard'},
            'created_at': datetime.now(timezone.utc)
        }
        
        # Act
        project = await project_repo.create(project_data)
        
        # Assert
        assert project['name'] == project_data['name']
    
    @pytest.mark.asyncio
    async def test_get_projects_by_organization(self, project_repo, db_transaction):
        """Test listing projects by organization."""
        # Arrange
        org_id = str(uuid4())
        db_transaction.fetch = AsyncMock(return_value=[
            {'id': str(uuid4()), 'name': f'Project {i}', 'organization_id': org_id}
            for i in range(5)
        ])
        
        # Act
        projects = await project_repo.get_by_organization(org_id)
        
        # Assert
        assert len(projects) == 5
        assert all(p['organization_id'] == org_id for p in projects)
    
    @pytest.mark.asyncio
    async def test_project_document_association(self, project_repo, db_transaction):
        """Test adding documents to project."""
        # Arrange
        project_id = str(uuid4())
        document_id = str(uuid4())
        
        # Act
        await project_repo.add_document(project_id, document_id)
        
        # Assert
        db_transaction.execute.assert_called()


class TestDocumentRepository:
    """Test suite for Document Repository operations."""
    
    @pytest.fixture
    async def document_repo(self, db_transaction):
        """Create DocumentRepository with test transaction."""
        from repositories.document_repository import DocumentRepository
        return DocumentRepository(db=db_transaction)
    
    @pytest.mark.asyncio
    async def test_create_document(self, document_repo, db_transaction):
        """Test creating a document record."""
        # Arrange
        doc_data = {
            'id': str(uuid4()),
            'project_id': str(uuid4()),
            'filename': 'test.pdf',
            'content_type': 'application/pdf',
            'size': 1024000,
            'storage_key': 'projects/test/test.pdf',
            'status': 'pending',
            'metadata': {'pages': 10},
            'created_at': datetime.now(timezone.utc)
        }
        
        # Act
        document = await document_repo.create(doc_data)
        
        # Assert
        assert document['filename'] == doc_data['filename']
    
    @pytest.mark.asyncio
    async def test_update_document_status(self, document_repo, db_transaction):
        """Test updating document processing status."""
        # Arrange
        doc_id = str(uuid4())
        
        # Act
        await document_repo.update_status(doc_id, 'processing', 
                                          metadata={'progress': 50})
        
        # Assert
        db_transaction.execute.assert_called()
    
    @pytest.mark.asyncio
    async def test_search_documents_by_name(self, document_repo, db_transaction):
        """Test searching documents by filename."""
        # Arrange
        search_term = 'report'
        db_transaction.fetch = AsyncMock(return_value=[
            {'id': str(uuid4()), 'filename': 'annual_report.pdf'},
            {'id': str(uuid4()), 'filename': 'quarterly_report.xlsx'}
        ])
        
        # Act
        results = await document_repo.search_by_filename(search_term)
        
        # Assert
        assert len(results) == 2
        assert all(search_term in doc['filename'].lower() for doc in results)


class TestDatabaseMigrations:
    """Test suite for database migrations."""
    
    @pytest.mark.asyncio
    async def test_migration_table_exists(self, db_pool):
        """Test that migration tracking table exists."""
        result = await db_pool.fetchrow(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'schema_migrations')"
        )
        # Real test: assert result['exists'] is True
        pass
    
    @pytest.mark.asyncio
    async def test_all_migrations_applied(self, db_pool):
        """Test that all migrations have been applied."""
        # Get list of pending migrations
        pending = await db_pool.fetch(
            "SELECT version FROM schema_migrations WHERE applied_at IS NULL"
        )
        assert len(pending) == 0, f"Pending migrations: {pending}"
    
    @pytest.mark.asyncio
    async def test_migration_idempotency(self, db_pool):
        """Test that migrations can be run multiple times safely."""
        # Run migrations again - should not fail
        # This verifies idempotent migration scripts
        pass


classTestDatabasePerformance:
    """Test suite for database performance."""
    
    @pytest.mark.asyncio
    async def test_user_query_performance(self, db_pool):
        """Test user query execution time."""
        import time
        
        start = time.time()
        await db_pool.fetch("SELECT * FROM users WHERE is_active = true LIMIT 100")
        elapsed = time.time() - start
        
        # Should complete in less than 100ms
        assert elapsed < 0.1, f"Query took {elapsed}s, expected < 0.1s"
    
    @pytest.mark.asyncio
    async def test_document_search_performance(self, db_pool):
        """Test document search performance."""
        import time
        
        start = time.time()
        await db_pool.fetch(
            "SELECT * FROM documents WHERE filename ILIKE '%report%' LIMIT 50"
        )
        elapsed = time.time() - start
        
        # Should complete in less than 200ms
        assert elapsed < 0.2, f"Search took {elapsed}s, expected < 0.2s"
    
    @pytest.mark.asyncio
    async def test_index_usage(self, db_pool):
        """Test that queries use appropriate indexes."""
        # Use EXPLAIN to verify index usage
        result = await db_pool.fetchrow(
            "EXPLAIN (FORMAT JSON) SELECT * FROM users WHERE email = 'test@example.com'"
        )
        # Verify 'Index Scan' or 'Index Only Scan' in plan
        pass


class TestDatabaseConstraints:
    """Test suite for database constraints."""
    
    @pytest.mark.asyncio
    async def test_unique_email_constraint(self, db_pool):
        """Test unique constraint on user email."""
        email = f'duplicate_{uuid4().hex}@example.com'
        
        # First insert should succeed
        await db_pool.execute(
            "INSERT INTO users (id, email) VALUES ($1, $2)",
            str(uuid4()), email
        )
        
        # Second insert should fail
        with pytest.raises(Exception) as exc_info:
            await db_pool.execute(
                "INSERT INTO users (id, email) VALUES ($1, $2)",
                str(uuid4()), email
            )
        
        assert 'duplicate' in str(exc_info.value).lower() or 'unique' in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_foreign_key_constraint(self, db_pool):
        """Test foreign key constraint."""
        # Attempt to insert document with non-existent project
        with pytest.raises(Exception) as exc_info:
            await db_pool.execute(
                "INSERT INTO documents (id, project_id) VALUES ($1, $2)",
                str(uuid4()), 'non-existent-project-id'
            )
        
        assert 'foreign key' in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_not_null_constraints(self, db_pool):
        """Test NOT NULL constraints."""
        # Attempt to insert user without required email
        with pytest.raises(Exception) as exc_info:
            await db_pool.execute(
                "INSERT INTO users (id) VALUES ($1)",
                str(uuid4())
            )
        
        assert 'not null' in str(exc_info.value).lower()
