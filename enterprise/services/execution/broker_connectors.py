"""
DragonScope Enterprise - Broker Connectors

Unified interface for connecting to multiple brokerages and exchanges.
Supports equities, options, futures, and cryptocurrencies.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, AsyncIterator, Union
import aiohttp
import websockets


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS & DATA CLASSES
# ============================================================================

class AssetClass(Enum):
    EQUITY = "equity"
    OPTION = "option"
    FUTURE = "future"
    FOREX = "forex"
    CRYPTO = "crypto"


class BrokerStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


@dataclass
class BrokerConfig:
    """Configuration for broker connection."""
    name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    passphrase: Optional[str] = None  # For Coinbase
    base_url: Optional[str] = None
    websocket_url: Optional[str] = None
    paper_trading: bool = True
    timeout_seconds: int = 30
    max_retries: int = 3
    rate_limit_per_second: int = 100


@dataclass
class OrderRequest:
    """Standardized order request."""
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    order_type: str  # "market", "limit", "stop", "stop_limit"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"  # "day", "gtc", "ioc", "fok"
    client_order_id: Optional[str] = None
    extended_hours: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.quantity,
            "type": self.order_type,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force,
            "client_order_id": self.client_order_id,
            "extended_hours": self.extended_hours
        }


@dataclass
class OrderResponse:
    """Standardized order response."""
    success: bool
    broker_order_id: Optional[str] = None
    status: str = "pending"
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_response: Optional[Dict] = None


@dataclass
class Fill:
    """Fill/execution report."""
    fill_id: str
    broker_order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0
    venue: Optional[str] = None


@dataclass
class Position:
    """Position information."""
    symbol: str
    quantity: float
    market_value: float
    average_entry_price: float
    current_price: float
    unrealized_pnl: float
    asset_class: AssetClass = AssetClass.EQUITY


@dataclass
class Account:
    """Account information."""
    account_id: str
    buying_power: float
    cash: float
    equity: float
    day_trading_buying_power: Optional[float] = None
    maintenance_margin: Optional[float] = None


@dataclass
class MarketData:
    """Market data snapshot."""
    symbol: str
    bid: float
    ask: float
    last_price: float
    last_size: float
    volume: float
    timestamp: datetime


# ============================================================================
# ABSTRACT BROKER CONNECTOR
# ============================================================================

class AbstractBrokerConnector(ABC):
    """
    Abstract base class for broker connectors.
    
    Provides unified interface for:
    - Order submission and management
    - Position tracking
    - Market data streaming
    - Account information
    """
    
    def __init__(self, config: BrokerConfig):
        self.config = config
        self.status = BrokerStatus.DISCONNECTED
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        
        # Event callbacks
        self.fill_callbacks: List[Callable[[Fill], Any]] = []
        self.order_update_callbacks: List[Callable[[Dict], Any]] = []
        self.market_data_callbacks: List[Callable[[MarketData], Any]] = []
        
        # Internal state
        self._rate_limiter = asyncio.Semaphore(config.rate_limit_per_second)
        self._reconnect_task: Optional[asyncio.Task] = None
        self._should_reconnect = True
        
        logger.info(f"Initialized {self.__class__.__name__} for {config.name}")
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to broker."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection to broker."""
        pass
    
    @abstractmethod
    async def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit an order to the broker."""
        pass
    
    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> OrderResponse:
        """Cancel an existing order."""
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        broker_order_id: str,
        quantity: Optional[float] = None,
        limit_price: Optional[float] = None
    ) -> OrderResponse:
        """Modify an existing order."""
        pass
    
    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get status of an order."""
        pass
    
    @abstractmethod
    async def list_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List orders."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get current positions."""
        pass
    
    @abstractmethod
    async def get_account(self) -> Account:
        """Get account information."""
        pass
    
    @abstractmethod
    async def stream_market_data(
        self,
        symbols: List[str]
    ) -> AsyncIterator[MarketData]:
        """Stream real-time market data."""
        pass
    
    @abstractmethod
    async def stream_fills(self) -> AsyncIterator[Fill]:
        """Stream real-time fill notifications."""
        pass
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with rate limiting and retry logic."""
        if not self.session:
            raise RuntimeError("Not connected")
        
        url = f"{self.config.base_url}{endpoint}"
        
        async with self._rate_limiter:
            for attempt in range(self.config.max_retries):
                try:
                    async with self.session.request(
                        method=method,
                        url=url,
                        json=data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                    ) as response:
                        if response.status == 429:  # Rate limited
                            retry_after = int(response.headers.get("Retry-After", 1))
                            logger.warning(f"Rate limited, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue
                        
                        response.raise_for_status()
                        return await response.json()
                        
                except aiohttp.ClientError as e:
                    logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise
        
        raise RuntimeError("Max retries exceeded")
    
    def subscribe_fills(self, callback: Callable[[Fill], Any]):
        """Subscribe to fill notifications."""
        self.fill_callbacks.append(callback)
    
    def subscribe_order_updates(self, callback: Callable[[Dict], Any]):
        """Subscribe to order updates."""
        self.order_update_callbacks.append(callback)
    
    def subscribe_market_data(self, callback: Callable[[MarketData], Any]):
        """Subscribe to market data."""
        self.market_data_callbacks.append(callback)
    
    async def _notify_fill(self, fill: Fill):
        """Notify fill subscribers."""
        for callback in self.fill_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(fill)
                else:
                    callback(fill)
            except Exception as e:
                logger.error(f"Fill callback error: {e}")
    
    def _generate_client_order_id(self) -> str:
        """Generate unique client order ID."""
        return f"DS_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{id(self)}"


# ============================================================================
# ALPACA CONNECTOR
# ============================================================================

class AlpacaConnector(AbstractBrokerConnector):
    """
    Alpaca Markets connector for US equities.
    Supports both paper and live trading.
    """
    
    BASE_URL_LIVE = "https://api.alpaca.markets"
    BASE_URL_PAPER = "https://paper-api.alpaca.markets"
    WS_URL_LIVE = "wss://stream.data.alpaca.markets/v2/iex"
    WS_URL_PAPER = "wss://stream.data.alpaca.markets/v2/test"
    
    def __init__(self, config: BrokerConfig):
        if config.paper_trading:
            config.base_url = self.BASE_URL_PAPER
            config.websocket_url = self.WS_URL_PAPER
        else:
            config.base_url = self.BASE_URL_LIVE
            config.websocket_url = self.WS_URL_LIVE
        super().__init__(config)
        self._ws_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            self.status = BrokerStatus.CONNECTING
            self.session = aiohttp.ClientSession()
            await self.get_account()
            self.status = BrokerStatus.AUTHENTICATED
            logger.info(f"Connected to Alpaca ({'paper' if self.config.paper_trading else 'live'})")
            self._ws_task = asyncio.create_task(self._websocket_handler())
            return True
        except Exception as e:
            self.status = BrokerStatus.ERROR
            logger.error(f"Failed to connect to Alpaca: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Alpaca."""
        self._should_reconnect = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self.ws_connection:
            await self.ws_connection.close()
        if self.session:
            await self.session.close()
        self.status = BrokerStatus.DISCONNECTED
        logger.info("Disconnected from Alpaca")
    
    async def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit order to Alpaca."""
        headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.api_secret
        }
        payload = {
            "symbol": order.symbol.upper(),
            "qty": str(order.quantity),
            "side": order.side,
            "type": order.order_type,
            "time_in_force": order.time_in_force,
            "client_order_id": order.client_order_id or self._generate_client_order_id()
        }
        if order.limit_price:
            payload["limit_price"] = str(order.limit_price)
        if order.stop_price:
            payload["stop_price"] = str(order.stop_price)
        try:
            response = await self._make_request("POST", "/v2/orders", data=payload, headers=headers)
            return OrderResponse(
                success=True,
                broker_order_id=response.get("id"),
                status=response.get("status", "pending"),
                filled_quantity=float(response.get("filled_qty", 0)),
                filled_price=float(response.get("filled_avg_price")) if response.get("filled_avg_price") else None,
                raw_response=response
            )
        except Exception as e:
            return OrderResponse(success=False, message=str(e))
    
    async def cancel_order(self, broker_order_id: str) -> OrderResponse:
        """Cancel order on Alpaca."""
        headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.api_secret
        }
        try:
            await self._make_request("DELETE", f"/v2/orders/{broker_order_id}", headers=headers)
            return OrderResponse(success=True, broker_order_id=broker_order_id, status="cancelled")
        except Exception as e:
            return OrderResponse(success=False, broker_order_id=broker_order_id, message=str(e))
    
    async def modify_order(
        self,
        broker_order_id: str,
        quantity: Optional[float] = None,
        limit_price: Optional[float] = None
    ) -> OrderResponse:
        """Modify order on Alpaca (cancel and replace)."""
        existing = await self.get_order_status(broker_order_id)
        if not existing:
            return OrderResponse(success=False, message="Order not found")
        cancel_result = await self.cancel_order(broker_order_id)
        if not cancel_result.success:
            return cancel_result
        new_order = OrderRequest(
            symbol=existing.get("symbol"),
            side=existing.get("side"),
            quantity=quantity or float(existing.get("qty", 0)),
            order_type=existing.get("type", "market"),
            limit_price=limit_price or (float(existing.get("limit_price")) if existing.get("limit_price") else None),
            time_in_force=existing.get("time_in_force", "day")
        )
        return await self.submit_order(new_order)
    
    async def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get order status from Alpaca."""
        headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.api_secret
        }
        return await self._make_request("GET", f"/v2/orders/{broker_order_id}", headers=headers)
    
    async def list_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List orders from Alpaca."""
        headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.api_secret
        }
        params = f"?limit={limit}"
        if status:
            params += f"&status={status}"
        return await self._make_request("GET", f"/v2/orders{params}", headers=headers)
    
    async def get_positions(self) -> List[Position]:
        """Get positions from Alpaca."""
        headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.api_secret
        }
        response = await self._make_request("GET", "/v2/positions", headers=headers)
        positions = []
        for pos in response:
            positions.append(Position(
                symbol=pos.get("symbol"),
                quantity=float(pos.get("qty", 0)),
                market_value=float(pos.get("market_value", 0)),
                average_entry_price=float(pos.get("avg_entry_price", 0)),
                current_price=float(pos.get("current_price", 0)),
                unrealized_pnl=float(pos.get("unrealized_pl", 0)),
                asset_class=AssetClass.EQUITY
            ))
        return positions
    
    async def get_account(self) -> Account:
        """Get account from Alpaca."""
        headers = {
            "APCA-API-KEY-ID": self.config.api_key,
            "APCA-API-SECRET-KEY": self.config.api_secret
        }
        response = await self._make_request("GET", "/v2/account", headers=headers)
        return Account(
            account_id=response.get("id"),
            buying_power=float(response.get("buying_power", 0)),
            cash=float(response.get("cash", 0)),
            equity=float(response.get("equity", 0)),
            day_trading_buying_power=float(response.get("daytrading_buying_power")) if response.get("daytrading_buying_power") else None,
            maintenance_margin=float(response.get("maintenance_margin")) if response.get("maintenance_margin") else None
        )
    
    async def stream_market_data(self, symbols: List[str]) -> AsyncIterator[MarketData]:
        """Stream market data from Alpaca."""
        raise NotImplementedError("Use WebSocket handler for streaming")
    
    async def stream_fills(self) -> AsyncIterator[Fill]:
        """Stream fills from Alpaca."""
        raise NotImplementedError("Use WebSocket handler for streaming")
    
    async def _websocket_handler(self):
        """Handle WebSocket connection for streaming data."""
        while self._should_reconnect:
            try:
                async with websockets.connect(
                    self.config.websocket_url,
                    extra_headers={
                        "APCA-API-KEY-ID": self.config.api_key,
                        "APCA-API-SECRET-KEY": self.config.api_secret
                    }
                ) as ws:
                    self.ws_connection = ws
                    logger.info("WebSocket connected")
                    auth_msg = {
                        "action": "auth",
                        "key": self.config.api_key,
                        "secret": self.config.api_secret
                    }
                    await ws.send(json.dumps(auth_msg))
                    async for message in ws:
                        await self._handle_ws_message(json.loads(message))
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if self._should_reconnect:
                    await asyncio.sleep(5)
    
    async def _handle_ws_message(self, message: List[Dict]):
        """Handle WebSocket message."""
        for msg in message:
            msg_type = msg.get("T")
            if msg_type == "t":  # Trade
                market_data = MarketData(
                    symbol=msg.get("S"),
                    bid=msg.get("p", 0),
                    ask=msg.get("p", 0),
                    last_price=msg.get("p", 0),
                    last_size=msg.get("s", 0),
                    volume=msg.get("v", 0),
                    timestamp=datetime.utcnow()
                )
                for callback in self.market_data_callbacks:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(market_data)
                    else:
                        callback(market_data)
            elif msg_type == "fill":
                fill = Fill(
                    fill_id=msg.get("i", ""),
                    broker_order_id=msg.get("order_id", ""),
                    symbol=msg.get("S", ""),
                    side=msg.get("side", ""),
                    quantity=float(msg.get("qty", 0)),
                    price=float(msg.get("p", 0)),
                    timestamp=datetime.utcnow()
                )
                await self._notify_fill(fill)


# ============================================================================
# INTERACTIVE BROKERS CONNECTOR
# ============================================================================

class InteractiveBrokersConnector(AbstractBrokerConnector):
    """
    Interactive Brokers connector using IB Gateway/REST API.
    Supports equities, options, futures, and forex.
    """
    
    def __init__(self, config: BrokerConfig):
        if not config.base_url:
            config.base_url = "http://localhost:5000"  # IB Gateway REST
        super().__init__(config)
        self._next_order_id = 1
        self._pending_orders: Dict[int, str] = {}
    
    async def connect(self) -> bool:
        """Connect to Interactive Brokers."""
        try:
            self.status = BrokerStatus.CONNECTING
            self.session = aiohttp.ClientSession()
            response = await self._make_request("GET", "/portal/sso/validate")
            if response.get("authenticated"):
                self.status = BrokerStatus.AUTHENTICATED
                logger.info("Connected to Interactive Brokers")
                return True
            else:
                self.status = BrokerStatus.ERROR
                return False
        except Exception as e:
            self.status = BrokerStatus.ERROR
            logger.error(f"Failed to connect to IB: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Interactive Brokers."""
        if self.session:
            await self.session.close()
        self.status = BrokerStatus.DISCONNECTED
        logger.info("Disconnected from Interactive Brokers")
    
    async def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit order to Interactive Brokers."""
        ib_order_type = self._map_order_type(order.order_type)
        payload = {
            "conid": await self._get_conid(order.symbol),
            "orderType": ib_order_type,
            "side": order.side.upper(),
            "quantity": order.quantity,
            "tif": self._map_tif(order.time_in_force),
            "outsideRTH": order.extended_hours
        }
        if order.limit_price:
            payload["price"] = order.limit_price
        if order.stop_price:
            payload["auxPrice"] = order.stop_price
        try:
            response = await self._make_request("POST", "/iserver/account/{accountId}/orders", data=payload)
            return OrderResponse(
                success=True,
                broker_order_id=str(response.get("order_id")),
                status="submitted",
                raw_response=response
            )
        except Exception as e:
            return OrderResponse(success=False, message=str(e))
    
    async def cancel_order(self, broker_order_id: str) -> OrderResponse:
        """Cancel order on Interactive Brokers."""
        try:
            await self._make_request("DELETE", f"/iserver/account/{{accountId}}/order/{broker_order_id}")
            return OrderResponse(success=True, broker_order_id=broker_order_id, status="cancelled")
        except Exception as e:
            return OrderResponse(success=False, broker_order_id=broker_order_id, message=str(e))
    
    async def modify_order(
        self,
        broker_order_id: str,
        quantity: Optional[float] = None,
        limit_price: Optional[float] = None
    ) -> OrderResponse:
        """Modify order on Interactive Brokers."""
        payload = {}
        if quantity:
            payload["quantity"] = quantity
        if limit_price:
            payload["price"] = limit_price
        try:
            response = await self._make_request("POST", f"/iserver/account/{{accountId}}/order/{broker_order_id}", data=payload)
            return OrderResponse(success=True, broker_order_id=broker_order_id, raw_response=response)
        except Exception as e:
            return OrderResponse(success=False, broker_order_id=broker_order_id, message=str(e))
    
    async def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get order status from Interactive Brokers."""
        orders = await self.list_orders()
        for order in orders:
            if str(order.get("orderId")) == broker_order_id:
                return order
        return {}
    
    async def list_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List orders from Interactive Brokers."""
        response = await self._make_request("GET", "/iserver/account/orders")
        return response.get("orders", [])
    
    async def get_positions(self) -> List[Position]:
        """Get positions from Interactive Brokers."""
        response = await self._make_request("GET", "/portfolio/{accountId}/positions")
        positions = []
        for pos in response:
            positions.append(Position(
                symbol=pos.get("contractDesc", pos.get("symbol")),
                quantity=float(pos.get("position", 0)),
                market_value=float(pos.get("mktValue", 0)),
                average_entry_price=float(pos.get("avgCost", 0)),
                current_price=float(pos.get("mktPrice", 0)),
                unrealized_pnl=float(pos.get("unrealizedPnl", 0)),
                asset_class=self._map_asset_class(pos.get("assetClass"))
            ))
        return positions
    
    async def get_account(self) -> Account:
        """Get account from Interactive Brokers."""
        response = await self._make_request("GET", "/portfolio/{accountId}/summary")
        return Account(
            account_id=response.get("accountId", ""),
            buying_power=float(response.get("buying-power", {}).get("amount", 0)),
            cash=float(response.get("totalcashvalue", {}).get("amount", 0)),
            equity=float(response.get("equitywithloanvalue", {}).get("amount", 0)),
            day_trading_buying_power=float(response.get("daytradesremaining", 0)),
            maintenance_margin=float(response.get("maintenancemarginreq", {}).get("amount", 0))
        )
    
    async def stream_market_data(self, symbols: List[str]) -> AsyncIterator[MarketData]:
        """Stream market data from Interactive Brokers."""
        for symbol in symbols:
            conid = await self._get_conid(symbol)
            await self._make_request("POST", "/iserver/marketdata/snapshot", data={"conids": [conid], "fields": ["31", "83", "84", "85", "86"]})
        while True:
            await asyncio.sleep(1)
    
    async def stream_fills(self) -> AsyncIterator[Fill]:
        """Stream fills from Interactive Brokers."""
        while True:
            await asyncio.sleep(1)
    
    async def _get_conid(self, symbol: str) -> int:
        """Get contract ID for symbol."""
        response = await self._make_request("GET", f"/iserver/secdef/search?symbol={symbol}&name=false")
        if response and len(response) > 0:
            return response[0].get("conid")
        raise ValueError(f"Could not find contract for {symbol}")
    
    def _map_order_type(self, order_type: str) -> str:
        """Map standardized order type to IB format."""
        mapping = {
            "market": "MKT",
            "limit": "LMT",
            "stop": "STP",
            "stop_limit": "STP LMT",
            "trailing_stop": "TRAIL"
        }
        return mapping.get(order_type, "MKT")
    
    def _map_tif(self, tif: str) -> str:
        """Map time in force to IB format."""
        mapping = {
            "day": "DAY",
            "gtc": "GTC",
            "ioc": "IOC",
            "fok": "FOK"
        }
        return mapping.get(tif, "DAY")
    
    def _map_asset_class(self, asset_class: str) -> AssetClass:
        """Map IB asset class to enum."""
        mapping = {
            "STK": AssetClass.EQUITY,
            "OPT": AssetClass.OPTION,
            "FUT": AssetClass.FUTURE,
            "CASH": AssetClass.FOREX
        }
        return mapping.get(asset_class, AssetClass.EQUITY)


# ============================================================================
# COINBASE PRO CONNECTOR
# ============================================================================

class CoinbaseProConnector(AbstractBrokerConnector):
    """
    Coinbase Pro connector for cryptocurrency trading.
    """
    
    BASE_URL = "https://api.exchange.coinbase.com"
    WS_URL = "wss://ws-feed.exchange.coinbase.com"
    
    def __init__(self, config: BrokerConfig):
        if not config.base_url:
            config.base_url = self.BASE_URL
        super().__init__(config)
        self._ws_task: Optional[asyncio.Task] = None
    
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """Generate Coinbase API signature."""
        message = timestamp + method.upper() + path + body
        signature = hmac.new(
            base64.b64decode(self.config.api_secret),
            message.encode(),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode()
    
    async def connect(self) -> bool:
        """Connect to Coinbase Pro."""
        try:
            self.status = BrokerStatus.CONNECTING
            self.session = aiohttp.ClientSession()
            await self.get_account()
            self.status = BrokerStatus.AUTHENTICATED
            logger.info("Connected to Coinbase Pro")
            self._ws_task = asyncio.create_task(self._websocket_handler())
            return True
        except Exception as e:
            self.status = BrokerStatus.ERROR
            logger.error(f"Failed to connect to Coinbase: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Coinbase Pro."""
        self._should_reconnect = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self.ws_connection:
            await self.ws_connection.close()
        if self.session:
            await self.session.close()
        self.status = BrokerStatus.DISCONNECTED
        logger.info("Disconnected from Coinbase Pro")
    
    async def submit_order(self, order: OrderRequest) -> OrderResponse:
        """Submit order to Coinbase Pro."""
        product_id = f"{order.symbol.upper()}-USD"
        timestamp = str(int(datetime.utcnow().timestamp()))
        payload = {
            "product_id": product_id,
            "side": order.side,
            "type": order.order_type,
            "size": str(order.quantity)
        }
        if order.order_type == "limit":
            payload["price"] = str(order.limit_price)
            payload["time_in_force"] = order.time_in_force.upper()
        if order.stop_price:
            payload["stop"] = "loss" if order.side == "sell" else "entry"
            payload["stop_price"] = str(order.stop_price)
        body = json.dumps(payload)
        signature = self._generate_signature(timestamp, "POST", "/orders", body)
        headers = {
            "CB-ACCESS-KEY": self.config.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.config.passphrase or "",
            "Content-Type": "application/json"
        }
        try:
            response = await self._make_request("POST", "/orders", data=payload, headers=headers)
            return OrderResponse(
                success=True,
                broker_order_id=response.get("id"),
                status=response.get("status", "pending"),
                filled_quantity=float(response.get("filled_size", 0)),
                filled_price=float(response.get("executed_value", 0)) / float(response.get("filled_size", 1)) if response.get("filled_size") else None,
                raw_response=response
            )
        except Exception as e:
            return OrderResponse(success=False, message=str(e))
    
    async def cancel_order(self, broker_order_id: str) -> OrderResponse:
        """Cancel order on Coinbase Pro."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        signature = self._generate_signature(timestamp, "DELETE", f"/orders/{broker_order_id}")
        headers = {
            "CB-ACCESS-KEY": self.config.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.config.passphrase or ""
        }
        try:
            await self._make_request("DELETE", f"/orders/{broker_order_id}", headers=headers)
            return OrderResponse(success=True, broker_order_id=broker_order_id, status="cancelled")
        except Exception as e:
            return OrderResponse(success=False, broker_order_id=broker_order_id, message=str(e))
    
    async def modify_order(
        self,
        broker_order_id: str,
        quantity: Optional[float] = None,
        limit_price: Optional[float] = None
    ) -> OrderResponse:
        """Modify order on Coinbase Pro (cancel and replace)."""
        return await self.cancel_order(broker_order_id)
    
    async def get_order_status(self, broker_order_id: str) -> Dict[str, Any]:
        """Get order status from Coinbase Pro."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        signature = self._generate_signature(timestamp, "GET", f"/orders/{broker_order_id}")
        headers = {
            "CB-ACCESS-KEY": self.config.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.config.passphrase or ""
        }
        return await self._make_request("GET", f"/orders/{broker_order_id}", headers=headers)
    
    async def list_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List orders from Coinbase Pro."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        path = f"/orders?limit={limit}"
        if status:
            path += f"&status={status}"
        signature = self._generate_signature(timestamp, "GET", path)
        headers = {
            "CB-ACCESS-KEY": self.config.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.config.passphrase or ""
        }
        return await self._make_request("GET", path, headers=headers)
    
    async def get_positions(self) -> List[Position]:
        """Get positions from Coinbase Pro."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        signature = self._generate_signature(timestamp, "GET", "/accounts")
        headers = {
            "CB-ACCESS-KEY": self.config.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.config.passphrase or ""
        }
        response = await self._make_request("GET", "/accounts", headers=headers)
        positions = []
        for account in response:
            currency = account.get("currency")
            balance = float(account.get("balance", 0))
            if balance > 0 and currency != "USD":
                positions.append(Position(
                    symbol=currency,
                    quantity=balance,
                    market_value=float(account.get("available", 0)),
                    average_entry_price=0.0,
                    current_price=0.0,
                    unrealized_pnl=0.0,
                    asset_class=AssetClass.CRYPTO
                ))
        return positions
    
    async def get_account(self) -> Account:
        """Get account from Coinbase Pro."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        signature = self._generate_signature(timestamp, "GET", "/accounts")
        headers = {
            "CB-ACCESS-KEY": self.config.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-ACCESS-PASSPHRASE": self.config.passphrase or ""
        }
        response = await self._make_request("GET", "/accounts", headers=headers)
        total_cash = sum(float(acc.get("available", 0)) for acc in response if acc.get("currency") == "USD")
        total_equity = sum(float(acc.get("balance", 0)) for acc in response)
        return Account(
            account_id="coinbase_pro",
            buying_power=total_cash,
            cash=total_cash,
            equity=total_equity
        )
    
    async def stream_market_data(self, symbols: List[str]) -> AsyncIterator[MarketData]:
        """Stream market data from Coinbase Pro."""
        raise NotImplementedError("Use WebSocket handler for streaming")
    
    async def stream_fills(self) -> AsyncIterator[Fill]:
        """Stream fills from Coinbase Pro."""
        raise NotImplementedError("Use WebSocket handler for streaming")
    
    async def _websocket_handler(self):
        """Handle WebSocket connection for streaming data."""
        timestamp = str(int(datetime.utcnow().timestamp()))
        signature = self._generate_signature(timestamp, "GET", "/users/self/verify")
        while self._should_reconnect:
            try:
                async with websockets.connect(self.WS_URL) as ws:
                    self.ws_connection = ws
                    logger.info("Coinbase WebSocket connected")
                    # Subscribe to channels
                    subscribe_msg = {
                        "type": "subscribe",
                        "product_ids": ["BTC-USD", "ETH-USD"],
                        "channels": ["heartbeat", "ticker", "matches", "user"],
                        "signature": signature,
                        "key": self.config.api_key,
                        "passphrase": self.config.passphrase or "",
                        "timestamp": timestamp
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    async for message in ws:
                        await self._handle_ws_message(json.loads(message))
            except Exception as e:
                logger.error(f"Coinbase WebSocket error: {e}")
                if self._should_reconnect:
                    await asyncio.sleep(5)
    
    async def _handle_ws_message(self, msg: Dict):
        """Handle WebSocket message."""
        msg_type = msg.get("type")
        if msg_type == "match":
            market_data = MarketData(
                symbol=msg.get("product_id", "").replace("-USD", ""),
                bid=float(msg.get("price", 0)),
                ask=float(msg.get("price", 0)),
                last_price=float(msg.get("price", 0)),
                last_size=float(msg.get("size", 0)),
                volume=0.0,
                timestamp=datetime.utcnow()
            )
            for callback in self.market_data_callbacks:
                if asyncio.iscoroutinefunction(callback):
                    await callback(market_data)
                else:
                    callback(market_data)
        elif msg_type == "fill" or msg.get("user_id"):
            fill = Fill(
                fill_id=msg.get("trade_id", ""),
                broker_order_id=msg.get("order_id", ""),
                symbol=msg.get("product_id", "").replace("-USD", ""),
                side=msg.get("side", ""),
                quantity=float(msg.get("size", 0)),
                price=float(msg.get("price", 0)),
                timestamp=datetime.utcnow(),
                commission=float(msg.get("fee", 0))
            )
            await self._notify_fill(fill)


# ============================================================================
# BROKER FACTORY
# ============================================================================

class BrokerConnectorFactory:
    """Factory for creating broker connectors."""
    
    CONNECTORS = {
        "alpaca": AlpacaConnector,
        "interactive_brokers": InteractiveBrokersConnector,
        "ib": InteractiveBrokersConnector,
        "coinbase_pro": CoinbaseProConnector,
        "coinbase": CoinbaseProConnector,
    }
    
    @classmethod
    def create(cls, broker_name: str, config: BrokerConfig) -> AbstractBrokerConnector:
        """
        Create a broker connector instance.
        
        Args:
            broker_name: Name of the broker (alpaca, interactive_brokers, coinbase_pro)
            config: Broker configuration
        
        Returns:
            AbstractBrokerConnector instance
        """
        connector_class = cls.CONNECTORS.get(broker_name.lower())
        if not connector_class:
            raise ValueError(f"Unknown broker: {broker_name}. Available: {list(cls.CONNECTORS.keys())}")
        return connector_class(config)
    
    @classmethod
    def list_connectors(cls) -> List[str]:
        """List available connector names."""
        return list(cls.CONNECTORS.keys())


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def example():
    """Example usage of broker connectors."""
    
    # Create Alpaca connector
    alpaca_config = BrokerConfig(
        name="alpaca_paper",
        api_key="YOUR_API_KEY",
        api_secret="YOUR_SECRET_KEY",
        paper_trading=True
    )
    
    alpaca = BrokerConnectorFactory.create("alpaca", alpaca_config)
    
    # Connect
    connected = await alpaca.connect()
    print(f"Alpaca connected: {connected}")
    
    # Get account info
    if connected:
        account = await alpaca.get_account()
        print(f"Account: ${account.equity:,.2f}")
        
        # Submit order
        order = OrderRequest(
            symbol="AAPL",
            side="buy",
            quantity=10,
            order_type="market"
        )
        response = await alpaca.submit_order(order)
        print(f"Order submitted: {response.broker_order_id}")
        
        # Get positions
        positions = await alpaca.get_positions()
        for pos in positions:
            print(f"Position: {pos.symbol} = {pos.quantity}")
    
    await alpaca.disconnect()


if __name__ == "__main__":
    asyncio.run(example())
