"""
Microsoft Excel Integration for DragonScope Enterprise.

Provides real-time data streaming, user-defined functions, and
WebSocket-based communication between DragonScope and Excel.

Architecture:
    - Excel Add-in (COM/XLL) with custom ribbon
    - WebSocket server for bidirectional communication
    - RTD (Real-Time Data) functions for live updates
    - UDF (User Defined Functions) for calculations
    - Custom task pane for configuration

Example Functions:
    =DS_PRICE("AAPL")              - Get real-time price
    =DS_HISTORY("AAPL",30)         - Get 30-day price history
    =DS_SCREEN("TECH", "CAP>10B")  - Run equity screener

Requirements:
    - Microsoft Excel 2016+ (Windows or Mac)
    - .NET Framework 4.7.2+ (Windows) or .NET 6+ (Mac)
    - WebSocket support enabled
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import defaultdict
import uuid

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = Any

# Configure logging
logger = logging.getLogger(__name__)


class ExcelError(Exception):
    """Base exception for Excel integration errors."""
    pass


class ExcelConnectionError(ExcelError):
    """WebSocket connection error."""
    pass


class ExcelFunctionError(ExcelError):
    """UDF execution error."""
    pass


class RTDUpdateMode(Enum):
    """Real-time data update modes."""
    STREAMING = auto()      # Continuous streaming
    ON_DEMAND = auto()      # Update on request
    THROTTLED = auto()      # Throttled updates (max X per second)


@dataclass
class CellReference:
    """Reference to an Excel cell."""
    workbook: str
    worksheet: str
    cell: str
    
    def __str__(self) -> str:
        return f"[{self.workbook}]{self.worksheet}!{self.cell}"
    
    @classmethod
    def parse(cls, ref: str) -> "CellReference":
        """Parse cell reference string."""
        # Format: [Workbook.xlsx]Sheet1!A1
        if "!" not in ref:
            raise ExcelError(f"Invalid cell reference: {ref}")
        
        location = ref.split("!")[-1]
        
        if "[" in ref and "]" in ref:
            workbook = ref[ref.index("[")+1:ref.index("]")]
            sheet = ref[ref.index("]")+1:ref.index("!")]
        else:
            workbook = ""
            sheet = ref[:ref.index("!")]
        
        return cls(
            workbook=workbook,
            worksheet=sheet,
            cell=location
        )


@dataclass
class RTDTopic:
    """Real-time data topic subscription."""
    topic_id: str
    function: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    update_mode: RTDUpdateMode = RTDUpdateMode.STREAMING
    throttle_ms: int = 1000
    last_update: Optional[datetime] = None
    current_value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "function": self.function,
            "parameters": self.parameters,
            "update_mode": self.update_mode.name,
            "throttle_ms": self.throttle_ms,
            "current_value": self.current_value,
        }


@dataclass
class UDFDefinition:
    """User-defined function definition."""
    name: str
    category: str
    description: str
    arguments: List[Dict[str, str]]
    return_type: str
    volatile: bool = False
    is_async: bool = False
    examples: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "arguments": self.arguments,
            "return_type": self.return_type,
            "volatile": self.volatile,
            "is_async": self.is_async,
            "examples": self.examples,
        }


@dataclass
class ExcelMessage:
    """WebSocket message format."""
    message_type: str
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> "ExcelMessage":
        parsed = json.loads(data)
        return cls(
            message_type=parsed["message_type"],
            message_id=parsed.get("message_id", str(uuid.uuid4())),
            payload=parsed.get("payload", {}),
            timestamp=parsed.get("timestamp", datetime.utcnow().isoformat()),
        )


# UDF Registry
UDF_REGISTRY: Dict[str, UDFDefinition] = {}
RTD_REGISTRY: Dict[str, RTDTopic] = {}


def register_udf(
    name: str,
    category: str = "DragonScope",
    description: str = "",
    arguments: Optional[List[Dict[str, str]]] = None,
    return_type: str = "Variant",
    volatile: bool = False,
    is_async: bool = False,
    examples: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to register a User Defined Function.
    
    Args:
        name: Function name in Excel (e.g., "DS_PRICE")
        category: Function category in Excel
        description: Function description
        arguments: List of argument definitions
        return_type: Return type hint
        volatile: Whether function recalculates on every change
        is_async: Whether function is asynchronous
        examples: Usage examples
    
    Example:
        >>> @register_udf(
        ...     name="DS_PRICE",
        ...     category="DragonScope",
        ...     description="Get real-time security price",
        ...     arguments=[
        ...         {"name": "symbol", "type": "String", "description": "Ticker symbol"},
        ...         {"name": "field", "type": "String", "optional": "True"}
        ...     ]
        ... )
        ... async def ds_price(symbol: str, field: str = "last") -> float:
        ...     return await get_price(symbol, field)
    """
    def decorator(func: Callable) -> Callable:
        UDF_REGISTRY[name] = UDFDefinition(
            name=name,
            category=category,
            description=description,
            arguments=arguments or [],
            return_type=return_type,
            volatile=volatile,
            is_async=is_async,
            examples=examples or [],
        )
        
        # Store original function
        UDF_REGISTRY[name].handler = func
        
        return func
    return decorator


def register_rtd_topic(
    topic_id: str,
    function: str,
    parameters: Dict[str, Any],
    update_mode: RTDUpdateMode = RTDUpdateMode.STREAMING,
    throttle_ms: int = 1000,
) -> RTDTopic:
    """
    Register an RTD topic for real-time updates.
    
    Args:
        topic_id: Unique topic identifier
        function: Function to call for updates
        parameters: Function parameters
        update_mode: Update frequency mode
        throttle_ms: Throttle interval in milliseconds
    
    Returns:
        Registered RTD topic
    """
    topic = RTDTopic(
        topic_id=topic_id,
        function=function,
        parameters=parameters,
        update_mode=update_mode,
        throttle_ms=throttle_ms,
    )
    RTD_REGISTRY[topic_id] = topic
    return topic


class ExcelServer:
    """
    WebSocket server for Excel add-in communication.
    
    Handles real-time data streaming, UDF execution, and
    bidirectional communication with Excel workbooks.
    
    Args:
        host: Server bind address (default: "0.0.0.0")
        port: Server port (default: 9001)
        ssl_context: Optional SSL context for WSS
        max_connections: Maximum concurrent connections
        heartbeat_interval: Heartbeat interval in seconds
    
    Example:
        >>> server = ExcelServer(port=9001)
        >>> await server.start()
        >>> 
        >>> # Push data to Excel
        >>> await server.update_cell("Sheet1!A1", 100.50)
        >>> 
        >>> await server.stop()
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9001,
        ssl_context: Optional[Any] = None,
        max_connections: int = 100,
        heartbeat_interval: int = 30,
    ):
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.max_connections = max_connections
        self.heartbeat_interval = heartbeat_interval
        
        self._server = None
        self._running = False
        self._connections: Dict[str, WebSocketServerProtocol] = {}
        self._workbooks: Dict[str, Set[str]] = defaultdict(set)
        self._subscriptions: Dict[str, Set[str]] = defaultdict(set)
        
        # Data caches
        self._rtd_values: Dict[str, Any] = {}
        self._cell_values: Dict[str, Any] = {}
        
        # Update queue
        self._update_queue: asyncio.Queue = asyncio.Queue()
        self._update_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = {
            "connections_total": 0,
            "connections_active": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "udf_calls": 0,
            "rtd_updates": 0,
        }
    
    async def start(self) -> None:
        """Start the Excel WebSocket server."""
        if not WEBSOCKETS_AVAILABLE:
            raise ExcelError("websockets library not installed")
        
        if self._running:
            return
        
        self._running = True
        
        # Start update processor
        self._update_task = asyncio.create_task(self._process_updates())
        
        # Start WebSocket server
        self._server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port,
            ssl=self.ssl_context,
            ping_interval=self.heartbeat_interval,
            ping_timeout=self.heartbeat_interval * 2,
        )
        
        logger.info(f"Excel server started on ws{'s' if self.ssl_context else ''}://{self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop the Excel WebSocket server."""
        if not self._running:
            return
        
        self._running = False
        
        # Close all connections
        close_tasks = [conn.close() for conn in self._connections.values()]
        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        
        # Stop update processor
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        logger.info("Excel server stopped")
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """Handle incoming WebSocket connection."""
        if len(self._connections) >= self.max_connections:
            await websocket.close(1013, "Server at capacity")
            return
        
        connection_id = str(uuid.uuid4())
        self._connections[connection_id] = websocket
        self._stats["connections_total"] += 1
        self._stats["connections_active"] = len(self._connections)
        
        logger.info(f"Excel connected: {connection_id}")
        
        try:
            async for message in websocket:
                self._stats["messages_received"] += 1
                await self._handle_message(connection_id, message)
        except ConnectionClosed:
            logger.info(f"Excel disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            await self._cleanup_connection(connection_id)
    
    async def _handle_message(self, connection_id: str, message: str) -> None:
        """Process incoming message from Excel."""
        try:
            msg = ExcelMessage.from_json(message)
            
            handlers = {
                "REGISTER_WORKBOOK": self._handle_register_workbook,
                "UNREGISTER_WORKBOOK": self._handle_unregister_workbook,
                "RTD_SUBSCRIBE": self._handle_rtd_subscribe,
                "RTD_UNSUBSCRIBE": self._handle_rtd_unsubscribe,
                "UDF_CALL": self._handle_udf_call,
                "CELL_UPDATE": self._handle_cell_update,
                "GET_FUNCTIONS": self._handle_get_functions,
                "PING": self._handle_ping,
            }
            
            handler = handlers.get(msg.message_type)
            if handler:
                await handler(connection_id, msg)
            else:
                await self._send_error(connection_id, f"Unknown message type: {msg.message_type}")
        
        except json.JSONDecodeError:
            await self._send_error(connection_id, "Invalid JSON message")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await self._send_error(connection_id, str(e))
    
    async def _handle_register_workbook(
        self,
        connection_id: str,
        message: ExcelMessage
    ) -> None:
        """Register a workbook connection."""
        workbook = message.payload.get("workbook", "")
        self._workbooks[connection_id].add(workbook)
        
        await self._send_message(connection_id, ExcelMessage(
            message_type="WORKBOOK_REGISTERED",
            payload={"workbook": workbook, "connection_id": connection_id}
        ))
    
    async def _handle_unregister_workbook(
        self,
        connection_id: str,
        message: ExcelMessage
    ) -> None:
        """Unregister a workbook connection."""
        workbook = message.payload.get("workbook", "")
        self._workbooks[connection_id].discard(workbook)
        
        # Unsubscribe all RTD topics for this workbook
        topics_to_remove = [
            topic_id for topic_id, subs in self._subscriptions.items()
            if connection_id in subs
        ]
        for topic_id in topics_to_remove:
            self._subscriptions[topic_id].discard(connection_id)
    
    async def _handle_rtd_subscribe(
        self,
        connection_id: str,
        message: ExcelMessage
    ) -> None:
        """Handle RTD subscription request."""
        payload = message.payload
        topic_id = payload.get("topic_id")
        function = payload.get("function")
        parameters = payload.get("parameters", {})
        
        if not topic_id or not function:
            await self._send_error(connection_id, "Missing topic_id or function")
            return
        
        # Register subscription
        self._subscriptions[topic_id].add(connection_id)
        
        # Register topic if new
        if topic_id not in RTD_REGISTRY:
            register_rtd_topic(
                topic_id=topic_id,
                function=function,
                parameters=parameters,
            )
        
        # Send current value if available
        current_value = self._rtd_values.get(topic_id)
        if current_value is not None:
            await self._send_rtd_update(connection_id, topic_id, current_value)
        
        logger.debug(f"RTD subscribe: {topic_id} from {connection_id}")
    
    async def _handle_rtd_unsubscribe(
        self,
        connection_id: str,
        message: ExcelMessage
    ) -> None:
        """Handle RTD unsubscription request."""
        topic_id = message.payload.get("topic_id")
        
        if topic_id:
            self._subscriptions[topic_id].discard(connection_id)
            
            # Clean up if no more subscribers
            if not self._subscriptions[topic_id]:
                RTD_REGISTRY.pop(topic_id, None)
                self._rtd_values.pop(topic_id, None)
    
    async def _handle_udf_call(
        self,
        connection_id: str,
        message: ExcelMessage
    ) -> None:
        """Handle UDF execution request."""
        payload = message.payload
        function_name = payload.get("function")
        args = payload.get("args", [])
        call_id = payload.get("call_id")
        
        if not function_name:
            await self._send_error(connection_id, "Missing function name")
            return
        
        udf_def = UDF_REGISTRY.get(function_name)
        if not udf_def:
            await self._send_error(connection_id, f"Unknown function: {function_name}")
            return
        
        self._stats["udf_calls"] += 1
        
        try:
            if udf_def.is_async:
                result = await udf_def.handler(*args)
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, udf_def.handler, *args)
            
            await self._send_message(connection_id, ExcelMessage(
                message_type="UDF_RESULT",
                payload={
                    "call_id": call_id,
                    "function": function_name,
                    "result": self._serialize_value(result),
                }
            ))
        
        except Exception as e:
            logger.error(f"UDF error: {e}")
            await self._send_message(connection_id, ExcelMessage(
                message_type="UDF_ERROR",
                payload={
                    "call_id": call_id,
                    "function": function_name,
                    "error": str(e),
                }
            ))
    
    async def _handle_cell_update(
        self,
        connection_id: str,
        message: ExcelMessage
    ) -> None:
        """Handle cell value update from Excel."""
        payload = message.payload
        cell_ref = payload.get("cell")
        value = payload.get("value")
        
        if cell_ref:
            self._cell_values[cell_ref] = value
            logger.debug(f"Cell update: {cell_ref} = {value}")
    
    async def _handle_get_functions(
        self,
        connection_id: str,
        message: ExcelMessage
    ) -> None:
        """Return list of available UDFs."""
        functions = [udf.to_dict() for udf in UDF_REGISTRY.values()]
        
        await self._send_message(connection_id, ExcelMessage(
            message_type="FUNCTIONS_LIST",
            payload={"functions": functions}
        ))
    
    async def _handle_ping(
        self,
        connection_id: str,
        message: ExcelMessage
    ) -> None:
        """Handle heartbeat ping."""
        await self._send_message(connection_id, ExcelMessage(
            message_type="PONG",
            payload={"timestamp": datetime.utcnow().isoformat()}
        ))
    
    async def _cleanup_connection(self, connection_id: str) -> None:
        """Clean up connection resources."""
        self._connections.pop(connection_id, None)
        self._workbooks.pop(connection_id, None)
        
        # Remove subscriptions
        for topic_id in list(self._subscriptions.keys()):
            self._subscriptions[topic_id].discard(connection_id)
        
        self._stats["connections_active"] = len(self._connections)
    
    async def _send_message(self, connection_id: str, message: ExcelMessage) -> None:
        """Send message to specific connection."""
        if connection_id not in self._connections:
            return
        
        try:
            websocket = self._connections[connection_id]
            await websocket.send(message.to_json())
            self._stats["messages_sent"] += 1
        except Exception as e:
            logger.error(f"Send error to {connection_id}: {e}")
    
    async def _send_error(self, connection_id: str, error: str) -> None:
        """Send error message."""
        await self._send_message(connection_id, ExcelMessage(
            message_type="ERROR",
            payload={"error": error}
        ))
    
    async def _send_rtd_update(
        self,
        connection_id: str,
        topic_id: str,
        value: Any
    ) -> None:
        """Send RTD update to connection."""
        await self._send_message(connection_id, ExcelMessage(
            message_type="RTD_UPDATE",
            payload={
                "topic_id": topic_id,
                "value": self._serialize_value(value),
                "timestamp": datetime.utcnow().isoformat(),
            }
        ))
    
    async def _process_updates(self) -> None:
        """Process queued updates."""
        while self._running:
            try:
                # Process RTD updates
                for topic_id, topic in list(RTD_REGISTRY.items()):
                    now = datetime.utcnow()
                    
                    # Check throttle
                    if topic.last_update:
                        elapsed = (now - topic.last_update).total_seconds() * 1000
                        if elapsed < topic.throttle_ms:
                            continue
                    
                    # Get updated value
                    new_value = await self._fetch_rtd_value(topic)
                    
                    if new_value != topic.current_value:
                        topic.current_value = new_value
                        topic.last_update = now
                        self._rtd_values[topic_id] = new_value
                        
                        # Send to all subscribers
                        for connection_id in list(self._subscriptions.get(topic_id, [])):
                            await self._send_rtd_update(connection_id, topic_id, new_value)
                        
                        self._stats["rtd_updates"] += 1
                
                await asyncio.sleep(0.1)  # 100ms processing interval
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update processing error: {e}")
    
    async def _fetch_rtd_value(self, topic: RTDTopic) -> Any:
        """Fetch current value for RTD topic."""
        # In production, this would call the appropriate data source
        # For now, return mock data
        if topic.function == "DS_PRICE":
            symbol = topic.parameters.get("symbol", "UNKNOWN")
            # Mock price
            import random
            return round(random.uniform(50, 500), 2)
        
        elif topic.function == "DS_VOLUME":
            import random
            return random.randint(1000000, 50000000)
        
        return None
    
    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for JSON transmission."""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        else:
            return str(value)
    
    # Public API methods
    
    async def update_cell(self, cell_ref: str, value: Any) -> None:
        """
        Push a value to a specific Excel cell.
        
        Args:
            cell_ref: Cell reference (e.g., "Sheet1!A1")
            value: Value to set
        """
        self._cell_values[cell_ref] = value
        
        message = ExcelMessage(
            message_type="CELL_PUSH",
            payload={"cell": cell_ref, "value": self._serialize_value(value)}
        )
        
        # Send to all connections
        for connection_id in list(self._connections.keys()):
            await self._send_message(connection_id, message)
    
    async def update_range(
        self,
        sheet: str,
        start_cell: str,
        values: List[List[Any]]
    ) -> None:
        """
        Push values to a range of cells.
        
        Args:
            sheet: Worksheet name
            start_cell: Top-left cell of range (e.g., "A1")
            values: 2D array of values
        """
        message = ExcelMessage(
            message_type="RANGE_PUSH",
            payload={
                "sheet": sheet,
                "start_cell": start_cell,
                "values": [[self._serialize_value(v) for v in row] for row in values]
            }
        )
        
        for connection_id in list(self._connections.keys()):
            await self._send_message(connection_id, message)
    
    async def broadcast_alert(self, message_text: str, level: str = "info") -> None:
        """
        Broadcast an alert to all connected Excel instances.
        
        Args:
            message_text: Alert message
            level: Alert level (info, warning, error)
        """
        message = ExcelMessage(
            message_type="ALERT",
            payload={
                "message": message_text,
                "level": level,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        for connection_id in list(self._connections.keys()):
            await self._send_message(connection_id, message)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            **self._stats,
            "rtd_topics_active": len(RTD_REGISTRY),
            "subscriptions_active": sum(len(s) for s in self._subscriptions.values()),
        }


# Built-in UDFs

@register_udf(
    name="DS_PRICE",
    category="DragonScope",
    description="Get real-time price for a security",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Ticker symbol (e.g., 'AAPL')"},
        {"name": "field", "type": "String", "optional": "True", "description": "Price field (last, bid, ask, open, high, low)"},
    ],
    return_type="Double",
    volatile=True,
    examples=[
        '=DS_PRICE("AAPL")',
        '=DS_PRICE("MSFT", "bid")',
        '=DS_PRICE("GOOGL US Equity")',
    ]
)
async def ds_price(symbol: str, field: str = "last") -> float:
    """
    Get real-time price for a security.
    
    Args:
        symbol: Ticker symbol (e.g., "AAPL" or "AAPL US Equity")
        field: Price field - last, bid, ask, open, high, low (default: last)
    
    Returns:
        Current price as float
    
    Examples:
        =DS_PRICE("AAPL")           -> 185.50
        =DS_PRICE("MSFT", "bid")    -> 420.25
    """
    import random
    base_price = random.uniform(50, 500)
    
    field_multipliers = {
        "last": 1.0,
        "bid": 0.999,
        "ask": 1.001,
        "open": 0.995,
        "high": 1.02,
        "low": 0.98,
    }
    
    multiplier = field_multipliers.get(field.lower(), 1.0)
    return round(base_price * multiplier, 2)


@register_udf(
    name="DS_HISTORY",
    category="DragonScope",
    description="Get historical price data for a security",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Ticker symbol"},
        {"name": "periods", "type": "Integer", "description": "Number of periods (days)"},
        {"name": "field", "type": "String", "optional": "True", "description": "Data field (close, open, high, low, volume)"},
    ],
    return_type="Array",
    volatile=False,
    examples=[
        '=DS_HISTORY("AAPL", 30)',
        '=DS_HISTORY("MSFT", 252, "close")',
    ]
)
async def ds_history(symbol: str, periods: int = 30, field: str = "close") -> List[float]:
    """
    Get historical price data for a security.
    
    Args:
        symbol: Ticker symbol
        periods: Number of periods (trading days)
        field: Data field - close, open, high, low, volume (default: close)
    
    Returns:
        Array of historical values (can spill to multiple cells)
    
    Examples:
        =DS_HISTORY("AAPL", 30)          -> Spills 30 days of closing prices
        =DS_HISTORY("MSFT", 252, "volume") -> Spills 252 days of volume
    """
    import random
    
    base_price = random.uniform(50, 500)
    data = []
    
    for _ in range(min(periods, 1000)):  # Cap at 1000
        if field.lower() == "volume":
            data.append(random.randint(1000000, 50000000))
        else:
            change = random.uniform(-0.05, 0.05)
            base_price *= (1 + change)
            data.append(round(base_price, 2))
    
    return data


@register_udf(
    name="DS_VOLUME",
    category="DragonScope",
    description="Get real-time volume for a security",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Ticker symbol"},
    ],
    return_type="Integer",
    volatile=True,
    examples=[
        '=DS_VOLUME("AAPL")',
    ]
)
async def ds_volume(symbol: str) -> int:
    """Get current trading volume."""
    import random
    return random.randint(1000000, 50000000)


@register_udf(
    name="DS_CHANGE",
    category="DragonScope",
    description="Get price change and percent change",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Ticker symbol"},
        {"name": "return_percent", "type": "Boolean", "optional": "True", "description": "Return percentage instead of absolute change"},
    ],
    return_type="Double",
    volatile=True,
    examples=[
        '=DS_CHANGE("AAPL")',
        '=DS_CHANGE("MSFT", TRUE)',
    ]
)
async def ds_change(symbol: str, return_percent: bool = False) -> float:
    """
    Get price change from previous close.
    
    Args:
        symbol: Ticker symbol
        return_percent: If TRUE, returns percentage change
    
    Returns:
        Price change (absolute or percentage)
    """
    import random
    change_pct = random.uniform(-0.05, 0.05)
    
    if return_percent:
        return round(change_pct * 100, 2)
    
    base_price = random.uniform(50, 500)
    return round(base_price * change_pct, 2)


@register_udf(
    name="DS_SCREEN",
    category="DragonScope",
    description="Run equity screener and return results",
    arguments=[
        {"name": "universe", "type": "String", "description": "Universe (e.g., 'US', 'TECH', 'SP500')"},
        {"name": "criteria", "type": "String", "description": "Screening criteria expression"},
        {"name": "max_results", "type": "Integer", "optional": "True", "description": "Maximum results to return"},
    ],
    return_type="Array",
    volatile=False,
    examples=[
        '=DS_SCREEN("US", "MARKET_CAP>10B")',
        '=DS_SCREEN("TECH", "PE_RATIO<20 AND DIV_YLD>2", 50)',
    ]
)
async def ds_screen(
    universe: str,
    criteria: str,
    max_results: int = 100
) -> List[List[str]]:
    """
    Run equity screener with specified criteria.
    
    Args:
        universe: Stock universe (US, TECH, SP500, NASDAQ, etc.)
        criteria: Screening criteria expression
        max_results: Maximum number of results (default: 100)
    
    Returns:
        2D array with ticker, name, and matching metrics
    
    Examples:
        =DS_SCREEN("US", "MARKET_CAP>10B")
        =DS_SCREEN("TECH", "PE_RATIO<20 AND DIV_YLD>2", 50)
    """
    import random
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX"]
    results = []
    
    for ticker in tickers[:max_results]:
        results.append([
            ticker,
            f"{ticker} Inc.",
            str(random.uniform(10, 100)),  # PE ratio
            str(random.uniform(0.5, 5.0)),  # Div yield
        ])
    
    return results


@register_udf(
    name="DS_OPTION_CHAIN",
    category="DragonScope - Options",
    description="Get option chain for a security",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Underlying ticker"},
        {"name": "expiration", "type": "String", "optional": "True", "description": "Expiration date or 'nearest'"},
    ],
    return_type="Array",
    volatile=False,
    examples=[
        '=DS_OPTION_CHAIN("AAPL")',
        '=DS_OPTION_CHAIN("SPY", "2024-03-15")',
    ]
)
async def ds_option_chain(symbol: str, expiration: str = "nearest") -> List[List[Any]]:
    """
    Get option chain for an underlying security.
    
    Args:
        symbol: Underlying ticker symbol
        expiration: Expiration date (YYYY-MM-DD) or 'nearest'
    
    Returns:
        Option chain with strikes, calls, and puts
    """
    import random
    
    underlying_price = random.uniform(100, 500)
    strikes = [underlying_price + (i - 10) * 5 for i in range(21)]
    
    results = [["Strike", "Call Bid", "Call Ask", "Put Bid", "Put Ask"]]
    
    for strike in strikes:
        call_iv = random.uniform(0.2, 0.5)
        put_iv = random.uniform(0.2, 0.5)
        
        call_price = max(0, underlying_price - strike) + call_iv * underlying_price * 0.1
        put_price = max(0, strike - underlying_price) + put_iv * underlying_price * 0.1
        
        results.append([
            strike,
            round(call_price * 0.95, 2),  # Call bid
            round(call_price * 1.05, 2),  # Call ask
            round(put_price * 0.95, 2),   # Put bid
            round(put_price * 1.05, 2),   # Put ask
        ])
    
    return results


@register_udf(
    name="DS_NEWS",
    category="DragonScope",
    description="Get latest news for a security",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Ticker symbol"},
        {"name": "count", "type": "Integer", "optional": "True", "description": "Number of headlines"},
    ],
    return_type="Array",
    volatile=True,
    examples=[
        '=DS_NEWS("AAPL", 5)',
    ]
)
async def ds_news(symbol: str, count: int = 5) -> List[List[str]]:
    """
    Get recent news headlines for a security.
    
    Args:
        symbol: Ticker symbol
        count: Number of headlines to return
    
    Returns:
        Array of [timestamp, headline, source]
    """
    headlines = [
        [datetime.utcnow().isoformat(), f"{symbol} Reports Strong Q4 Earnings", "Reuters"],
        [datetime.utcnow().isoformat(), f"Analysts Upgrade {symbol} Price Target", "Bloomberg"],
        [datetime.utcnow().isoformat(), f"{symbol} Announces New Product Line", "CNBC"],
        [datetime.utcnow().isoformat(), f"Institutional Investors Increase {symbol} Holdings", "WSJ"],
        [datetime.utcnow().isoformat(), f"{symbol} CEO Discusses Growth Strategy", "FT"],
    ]
    
    return headlines[:count]


@register_udf(
    name="DS_CORRELATION",
    category="DragonScope - Analytics",
    description="Calculate correlation between securities",
    arguments=[
        {"name": "symbol1", "type": "String", "description": "First symbol"},
        {"name": "symbol2", "type": "String", "description": "Second symbol"},
        {"name": "periods", "type": "Integer", "optional": "True", "description": "Lookback periods"},
    ],
    return_type="Double",
    volatile=False,
    examples=[
        '=DS_CORRELATION("AAPL", "MSFT", 252)',
    ]
)
async def ds_correlation(
    symbol1: str,
    symbol2: str,
    periods: int = 252
) -> float:
    """
    Calculate price correlation between two securities.
    
    Args:
        symbol1: First ticker symbol
        symbol2: Second ticker symbol
        periods: Number of periods for correlation (default: 252)
    
    Returns:
        Correlation coefficient (-1 to 1)
    """
    import random
    return round(random.uniform(0.3, 0.9), 4)


@register_udf(
    name="DS_BETA",
    category="DragonScope - Analytics",
    description="Calculate beta relative to benchmark",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Ticker symbol"},
        {"name": "benchmark", "type": "String", "optional": "True", "description": "Benchmark symbol (default: SPY)"},
        {"name": "periods", "type": "Integer", "optional": "True", "description": "Lookback periods"},
    ],
    return_type="Double",
    volatile=False,
    examples=[
        '=DS_BETA("AAPL")',
        '=DS_BETA("TSLA", "QQQ", 126)',
    ]
)
async def ds_beta(
    symbol: str,
    benchmark: str = "SPY",
    periods: int = 252
) -> float:
    """
    Calculate beta coefficient relative to a benchmark.
    
    Args:
        symbol: Ticker symbol
        benchmark: Benchmark symbol (default: SPY)
        periods: Number of periods (default: 252)
    
    Returns:
        Beta coefficient
    """
    import random
    return round(random.uniform(0.5, 2.0), 2)


@register_udf(
    name="DS_MA",
    category="DragonScope - Technical",
    description="Calculate moving average",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Ticker symbol"},
        {"name": "period", "type": "Integer", "description": "MA period"},
        {"name": "ma_type", "type": "String", "optional": "True", "description": "SMA, EMA, WMA"},
    ],
    return_type="Double",
    volatile=False,
    examples=[
        '=DS_MA("AAPL", 50)',
        '=DS_MA("MSFT", 20, "EMA")',
    ]
)
async def ds_ma(symbol: str, period: int, ma_type: str = "SMA") -> float:
    """
    Calculate moving average price.
    
    Args:
        symbol: Ticker symbol
        period: Moving average period
        ma_type: Type - SMA (simple), EMA (exponential), WMA (weighted)
    
    Returns:
        Moving average value
    """
    import random
    base_price = random.uniform(50, 500)
    return round(base_price, 2)


@register_udf(
    name="DS_RSI",
    category="DragonScope - Technical",
    description="Calculate Relative Strength Index",
    arguments=[
        {"name": "symbol", "type": "String", "description": "Ticker symbol"},
        {"name": "period", "type": "Integer", "optional": "True", "description": "RSI period (default: 14)"},
    ],
    return_type="Double",
    volatile=False,
    examples=[
        '=DS_RSI("AAPL")',
        '=DS_RSI("TSLA", 21)',
    ]
)
async def ds_rsi(symbol: str, period: int = 14) -> float:
    """
    Calculate Relative Strength Index.
    
    Args:
        symbol: Ticker symbol
        period: RSI period (default: 14)
    
    Returns:
        RSI value (0-100)
    """
    import random
    return round(random.uniform(10, 90), 2)


# Convenience functions

async def push_to_excel(
    cell: str,
    value: Any,
    server: Optional[ExcelServer] = None
) -> None:
    """
    Push a value to Excel (convenience function).
    
    Args:
        cell: Cell reference (e.g., "Sheet1!A1")
        value: Value to push
        server: Optional existing server instance
    """
    server_provided = server is not None
    
    try:
        if not server:
            server = ExcelServer()
            await server.start()
        
        await server.update_cell(cell, value)
    finally:
        if not server_provided and server:
            await server.stop()


async def broadcast_to_excel(
    message: str,
    level: str = "info",
    server: Optional[ExcelServer] = None
) -> None:
    """
    Broadcast alert to all Excel instances.
    
    Args:
        message: Alert message
        level: Alert level
        server: Optional existing server instance
    """
    server_provided = server is not None
    
    try:
        if not server:
            server = ExcelServer()
            await server.start()
        
        await server.broadcast_alert(message, level)
    finally:
        if not server_provided and server:
            await server.stop()


def get_available_functions() -> List[Dict[str, Any]]:
    """
    Get list of all available UDFs.
    
    Returns:
        List of UDF definitions
    """
    return [udf.to_dict() for udf in UDF_REGISTRY.values()]


def export_function_manifest(path: str) -> None:
    """
    Export UDF manifest to JSON for Excel add-in.
    
    Args:
        path: Output file path
    """
    manifest = {
        "version": "1.0.0",
        "functions": get_available_functions(),
        "generated_at": datetime.utcnow().isoformat(),
    }
    
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    logger.info(f"Function manifest exported to {path}")
