"""
Unit tests for User Service.

Tests user management, authentication, and authorization logic.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestUserService:
    """Test suite for UserService business logic."""
    
    @pytest.fixture
    def user_service(self, mock_db_session):
        """Create a UserService instance with mocked dependencies."""
        from services.user_service import UserService
        return UserService(db_session=mock_db_session)
    
    @pytest.fixture
    def valid_user_data(self):
        """Provide valid user creation data."""
        return {
            'email': 'new.user@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'SecurePassword123!',
            'organization_id': 'org_test_001'
        }
    
    # =========================================================================
    # User Creation Tests
    # =========================================================================
    
    def test_create_user_success(self, user_service, valid_user_data, mock_db_session):
        """Test successful user creation with valid data."""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Act
        user = user_service.create_user(valid_user_data)
        
        # Assert
        assert user.email == valid_user_data['email']
        assert user.first_name == valid_user_data['first_name']
        assert user.last_name == valid_user_data['last_name']
        assert user.organization_id == valid_user_data['organization_id']
        assert user.is_active is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    def test_create_user_with_duplicate_email_raises_error(
        self, user_service, valid_user_data, mock_db_session, user_factory
    ):
        """Test that creating a user with duplicate email raises DuplicateEmailError."""
        # Arrange
        existing_user = Mock(**user_factory(email=valid_user_data['email']))
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_user
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:  # Replace with actual exception
            user_service.create_user(valid_user_data)
        
        assert 'already exists' in str(exc_info.value).lower() or 'duplicate' in str(exc_info.value).lower()
        mock_db_session.add.assert_not_called()
    
    def test_create_user_hashes_password(self, user_service, valid_user_data, mock_db_session):
        """Test that password is hashed before storage."""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        with patch('services.user_service.hash_password') as mock_hash:
            mock_hash.return_value = 'hashed_password_123'
            
            # Act
            user = user_service.create_user(valid_user_data)
            
            # Assert
            mock_hash.assert_called_once_with(valid_user_data['password'])
            assert user.password_hash == 'hashed_password_123'
    
    def test_create_user_invalid_email_raises_validation_error(
        self, user_service, valid_user_data
    ):
        """Test that invalid email format raises validation error."""
        # Arrange
        invalid_data = valid_user_data.copy()
        invalid_data['email'] = 'not-an-email'
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            user_service.create_user(invalid_data)
        
        assert 'email' in str(exc_info.value).lower()
    
    def test_create_user_weak_password_raises_validation_error(
        self, user_service, valid_user_data
    ):
        """Test that weak password raises validation error."""
        # Arrange
        weak_passwords = ['123', 'password', 'abc', 'short']
        
        for weak_pass in weak_passwords:
            invalid_data = valid_user_data.copy()
            invalid_data['password'] = weak_pass
            
            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                user_service.create_user(invalid_data)
            
            assert 'password' in str(exc_info.value).lower()
    
    # =========================================================================
    # User Retrieval Tests
    # =========================================================================
    
    def test_get_user_by_id_success(self, user_service, mock_db_session, user_factory):
        """Test retrieving user by ID."""
        # Arrange
        user_id = 'usr_test_001'
        expected_user = Mock(**user_factory(id=user_id))
        mock_db_session.get.return_value = expected_user
        
        # Act
        user = user_service.get_user_by_id(user_id)
        
        # Assert
        assert user is not None
        assert user.id == user_id
        mock_db_session.get.assert_called_once()
    
    def test_get_user_by_id_not_found_returns_none(self, user_service, mock_db_session):
        """Test that getting non-existent user returns None."""
        # Arrange
        mock_db_session.get.return_value = None
        
        # Act
        user = user_service.get_user_by_id('non-existent-id')
        
        # Assert
        assert user is None
    
    def test_get_user_by_email_success(self, user_service, mock_db_session, user_factory):
        """Test retrieving user by email."""
        # Arrange
        email = 'test@example.com'
        expected_user = Mock(**user_factory(email=email))
        mock_db_session.query.return_value.filter.return_value.first.return_value = expected_user
        
        # Act
        user = user_service.get_user_by_email(email)
        
        # Assert
        assert user is not None
        assert user.email == email
    
    # =========================================================================
    # User Update Tests
    # =========================================================================
    
    def test_update_user_success(self, user_service, mock_db_session, user_factory):
        """Test successful user update."""
        # Arrange
        user_id = 'usr_test_001'
        existing_user = Mock(**user_factory(id=user_id))
        mock_db_session.get.return_value = existing_user
        
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        
        # Act
        updated_user = user_service.update_user(user_id, update_data)
        
        # Assert
        assert updated_user.first_name == 'Updated'
        assert updated_user.last_name == 'Name'
        mock_db_session.commit.assert_called_once()
    
    def test_update_user_not_found_raises_error(self, user_service, mock_db_session):
        """Test updating non-existent user raises error."""
        # Arrange
        mock_db_session.get.return_value = None
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            user_service.update_user('non-existent-id', {'first_name': 'Test'})
        
        assert 'not found' in str(exc_info.value).lower()
    
    def test_update_user_email_to_existing_raises_error(
        self, user_service, mock_db_session, user_factory
    ):
        """Test updating email to another user's email raises error."""
        # Arrange
        user_id = 'usr_test_001'
        existing_user = Mock(**user_factory(id=user_id, email='original@example.com'))
        another_user = Mock(**user_factory(id='usr_test_002', email='taken@example.com'))
        
        mock_db_session.get.return_value = existing_user
        mock_db_session.query.return_value.filter.return_value.first.return_value = another_user
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            user_service.update_user(user_id, {'email': 'taken@example.com'})
        
        assert 'already exists' in str(exc_info.value).lower()
    
    # =========================================================================
    # User Deletion Tests
    # =========================================================================
    
    def test_delete_user_success(self, user_service, mock_db_session, user_factory):
        """Test successful user deletion (soft delete)."""
        # Arrange
        user_id = 'usr_test_001'
        existing_user = Mock(**user_factory(id=user_id, is_active=True))
        mock_db_session.get.return_value = existing_user
        
        # Act
        user_service.delete_user(user_id)
        
        # Assert
        assert existing_user.is_active is False
        assert existing_user.deleted_at is not None
        mock_db_session.commit.assert_called_once()
    
    def test_delete_user_permanent_success(self, user_service, mock_db_session, user_factory):
        """Test permanent user deletion."""
        # Arrange
        user_id = 'usr_test_001'
        existing_user = Mock(**user_factory(id=user_id))
        mock_db_session.get.return_value = existing_user
        
        # Act
        user_service.delete_user(user_id, permanent=True)
        
        # Assert
        mock_db_session.delete.assert_called_once_with(existing_user)
        mock_db_session.commit.assert_called_once()
    
    # =========================================================================
    # User Listing Tests
    # =========================================================================
    
    def test_list_users_pagination(self, user_service, mock_db_session):
        """Test user listing with pagination."""
        # Arrange
        mock_query = mock_db_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.count.return_value = 0
        
        # Act
        result = user_service.list_users(page=1, per_page=20)
        
        # Assert
        assert 'users' in result
        assert 'total' in result
        assert 'page' in result
        assert 'per_page' in result
        mock_query.offset.assert_called_once_with(0)  # (1-1) * 20
        mock_query.limit.assert_called_once_with(20)
    
    def test_list_users_filter_by_organization(self, user_service, mock_db_session):
        """Test filtering users by organization."""
        # Arrange
        org_id = 'org_test_001'
        mock_query = mock_db_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.count.return_value = 0
        
        # Act
        result = user_service.list_users(organization_id=org_id)
        
        # Assert
        # Verify filter was applied
        mock_query.filter.assert_called()


class TestUserAuthentication:
    """Test suite for user authentication logic."""
    
    @pytest.fixture
    def auth_service(self, mock_db_session):
        """Create an AuthService instance with mocked dependencies."""
        from services.auth_service import AuthService
        return AuthService(db_session=mock_db_session)
    
    def test_authenticate_user_success(self, auth_service, mock_db_session, user_factory):
        """Test successful user authentication."""
        # Arrange
        email = 'test@example.com'
        password = 'CorrectPassword123!'
        
        user = Mock(**user_factory(email=email))
        user.verify_password = Mock(return_value=True)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = user
        
        # Act
        authenticated_user = auth_service.authenticate(email, password)
        
        # Assert
        assert authenticated_user is not None
        assert authenticated_user.email == email
        user.verify_password.assert_called_once_with(password)
    
    def test_authenticate_user_wrong_password(self, auth_service, mock_db_session, user_factory):
        """Test authentication with wrong password."""
        # Arrange
        email = 'test@example.com'
        password = 'WrongPassword!'
        
        user = Mock(**user_factory(email=email))
        user.verify_password = Mock(return_value=False)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = user
        
        # Act
        result = auth_service.authenticate(email, password)
        
        # Assert
        assert result is None
    
    def test_authenticate_user_not_found(self, auth_service, mock_db_session):
        """Test authentication for non-existent user."""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Act
        result = auth_service.authenticate('nonexistent@example.com', 'password')
        
        # Assert
        assert result is None
    
    def test_authenticate_inactive_user_raises_error(self, auth_service, mock_db_session, user_factory):
        """Test authentication for inactive user raises error."""
        # Arrange
        user = Mock(**user_factory(is_active=False))
        user.verify_password = Mock(return_value=True)
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = user
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            auth_service.authenticate('inactive@example.com', 'password')
        
        assert 'inactive' in str(exc_info.value).lower()


class TestUserAuthorization:
    """Test suite for user authorization logic."""
    
    @pytest.fixture
    def authz_service(self):
        """Create an AuthorizationService instance."""
        from services.authz_service import AuthorizationService
        return AuthorizationService()
    
    def test_check_permission_admin_has_all_permissions(self, authz_service, user_factory):
        """Test that admin users have all permissions."""
        # Arrange
        admin_user = Mock(**user_factory(role='admin'))
        
        # Act & Assert
        assert authz_service.has_permission(admin_user, 'users.create') is True
        assert authz_service.has_permission(admin_user, 'users.delete') is True
        assert authz_service.has_permission(admin_user, 'projects.admin') is True
        assert authz_service.has_permission(admin_user, 'any.random.permission') is True
    
    def test_check_permission_analyst_limited_permissions(self, authz_service, user_factory):
        """Test that analyst users have limited permissions."""
        # Arrange
        analyst_user = Mock(**user_factory(role='analyst'))
        
        # Act & Assert
        assert authz_service.has_permission(analyst_user, 'projects.read') is True
        assert authz_service.has_permission(analyst_user, 'projects.write') is True
        assert authz_service.has_permission(analyst_user, 'users.create') is False
        assert authz_service.has_permission(analyst_user, 'admin.settings') is False
    
    def test_check_permission_viewer_read_only(self, authz_service, user_factory):
        """Test that viewer users have read-only permissions."""
        # Arrange
        viewer_user = Mock(**user_factory(role='viewer'))
        
        # Act & Assert
        assert authz_service.has_permission(viewer_user, 'projects.read') is True
        assert authz_service.has_permission(viewer_user, 'projects.write') is False
        assert authz_service.has_permission(viewer_user, 'documents.delete') is False


class TestAsyncUserOperations:
    """Test async user service operations."""
    
    @pytest.fixture
    def async_user_service(self, mock_db_session):
        """Create an AsyncUserService instance."""
        from services.user_service import AsyncUserService
        return AsyncUserService(db_session=mock_db_session)
    
    @pytest.mark.asyncio
    async def test_async_create_user(self, async_user_service, valid_user_data, mock_db_session):
        """Test async user creation."""
        # Arrange
        mock_db_session.execute = AsyncMock(return_value=None)
        
        # Act
        user = await async_user_service.create_user(valid_user_data)
        
        # Assert
        assert user is not None
        assert user.email == valid_user_data['email']
    
    @pytest.mark.asyncio
    async def test_async_get_user_by_email(self, async_user_service, mock_db_session, user_factory):
        """Test async user retrieval by email."""
        # Arrange
        email = 'test@example.com'
        expected_user_data = user_factory(email=email)
        mock_db_session.fetchrow = AsyncMock(return_value=expected_user_data)
        
        # Act
        user = await async_user_service.get_user_by_email(email)
        
        # Assert
        assert user is not None
        assert user['email'] == email
    
    @pytest.mark.asyncio
    async def test_send_welcome_email_async(self, async_user_service, mock_sendgrid):
        """Test async welcome email sending."""
        # Arrange
        user_data = {
            'email': 'newuser@example.com',
            'first_name': 'New'
        }
        
        # Act
        result = await async_user_service.send_welcome_email(user_data)
        
        # Assert
        assert result is True
