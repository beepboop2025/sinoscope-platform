from app.schemas.common import PaginatedResponse, ErrorResponse
from app.schemas.user import UserResponse, UserSync, PreferencesUpdate, PreferencesResponse
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
    HoldingCreate,
    HoldingResponse,
)
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistResponse,
    WatchlistItemCreate,
    WatchlistItemResponse,
)
from app.schemas.alert import AlertCreate, AlertUpdate, AlertResponse
from app.schemas.market_data import MarketDataResponse
from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse
