from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dragonscope:dragonscope@localhost:5432/dragonscope"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Server
    API_PORT: int = 3456
    DEBUG: bool = False
    CORS_ORIGINS: str = "http://localhost:5174,http://127.0.0.1:5174,http://localhost:3456,http://127.0.0.1:3456"

    # Clerk Auth
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = "https://api.clerk.dev/v1/jwks"

    # API Keys (for collector)
    FRED_API_KEY: str = ""
    ALPHA_VANTAGE_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""
    FMP_API_KEY: str = ""
    GNEWS_API_KEY: str = ""
    NEWSDATA_API_KEY: str = ""
    NEWSAPI_API_KEY: str = ""
    WORLD_NEWS_API_KEY: str = ""

    # TimescaleDB
    TIMESCALE_ENABLED: bool = True
    TIMESCALE_RETENTION_DAYS: int = 90
    TIMESCALE_COMPRESSION_AFTER_DAYS: int = 7

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 200

    # Collector
    DATA_DIR: str = ""  # Fallback JSON data dir (server/data)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
