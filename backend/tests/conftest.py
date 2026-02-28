"""Shared test fixtures — async SQLite + mock Redis + auth override."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.middleware.auth import AuthUser, require_auth
from app.redis import get_redis

# ---------------------------------------------------------------------------
# Async SQLite engine (tests only — no Postgres needed)
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------
_redis_store: dict[str, str] = {}


def _make_mock_redis():
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.get = AsyncMock(side_effect=lambda k: _redis_store.get(k))
    mock.set = AsyncMock(side_effect=lambda k, v, **kw: _redis_store.__setitem__(k, v))
    mock.delete = AsyncMock(side_effect=lambda *keys: [_redis_store.pop(k, None) for k in keys])
    mock.publish = AsyncMock(return_value=0)
    mock.scan = AsyncMock(return_value=(0, []))
    return mock


# ---------------------------------------------------------------------------
# Auth override — stable test user
# ---------------------------------------------------------------------------
TEST_USER_ID = "test-user-id-0001"
TEST_CLERK_ID = "test-clerk-id"
TEST_EMAIL = "test@example.com"


async def _override_require_auth():
    return AuthUser(user_id=TEST_USER_ID, clerk_id=TEST_CLERK_ID, email=TEST_EMAIL)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def db_session():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession):
    """Insert a test User + UserPreference row so FK constraints are satisfied."""
    from app.models.user import User, UserPreference

    user = User(id=TEST_USER_ID, clerk_id=TEST_CLERK_ID, email=TEST_EMAIL)
    db_session.add(user)
    await db_session.flush()
    prefs = UserPreference(user_id=user.id)
    db_session.add(prefs)
    await db_session.commit()
    return user


@pytest.fixture
def mock_redis():
    _redis_store.clear()
    return _make_mock_redis()


@pytest_asyncio.fixture
async def client(mock_redis):
    """Async test client with all dependency overrides."""
    from app.main import app

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[require_auth] = _override_require_auth
    app.dependency_overrides[get_redis] = lambda: mock_redis

    # Patch module-level get_redis used by routes/health.py and services/cache.py
    import app.redis as redis_mod
    original = redis_mod.redis_client
    redis_mod.redis_client = mock_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    redis_mod.redis_client = original
    app.dependency_overrides.clear()
