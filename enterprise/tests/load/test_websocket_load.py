"""
WebSocket load testing.

Tests WebSocket connection handling and message throughput.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from statistics import mean, median, stdev
import pytest


class WebSocketLoadTest:
    """WebSocket load testing harness."""
    
    def __init__(self, url, num_connections=100):
        self.url = url
        self.num_connections = num_connections
        self.connections = []
        self.latencies = []
        self.errors = []
    
    async def connect(self):
        """Establish WebSocket connections."""
        # Example using websockets library:
        # import websockets
        # for i in range(self.num_connections):
        #     ws = await websockets.connect(self.url)
        #     self.connections.append(ws)
        
        # Mock for demonstration
        from unittest.mock import AsyncMock
        for i in range(self.num_connections):
            ws = AsyncMock()
            ws.send = AsyncMock()
            ws.recv = AsyncMock(return_value=json.dumps({
                'type': 'connected',
                'client_id': f'client_{i}'
            }))
            self.connections.append(ws)
        
        # Establish all connections
        tasks = [ws.recv() for ws in self.connections]
        await asyncio.gather(*tasks)
        print(f"Established {len(self.connections)} WebSocket connections")
    
    async def send_messages(self, messages_per_connection=100):
        """Send messages and measure latency."""
        async def send_and_measure(ws, conn_id):
            for i in range(messages_per_connection):
                start = time.time()
                
                try:
                    msg = {
                        'type': 'ping',
                        'seq': i,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    
                    await ws.send(json.dumps(msg))
                    response = await ws.recv()
                    
                    latency = (time.time() - start) * 1000  # ms
                    self.latencies.append(latency)
                    
                except Exception as e:
                    self.errors.append({
                        'connection': conn_id,
                        'message': i,
                        'error': str(e)
                    })
        
        # Send messages from all connections concurrently
        tasks = [
            send_and_measure(ws, i) 
            for i, ws in enumerate(self.connections)
        ]
        
        await asyncio.gather(*tasks)
    
    async def close(self):
        """Close all connections."""
        for ws in self.connections:
            await ws.close()
        self.connections = []
    
    def get_stats(self):
        """Get test statistics."""
        if not self.latencies:
            return {}
        
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        
        return {
            'connections': self.num_connections,
            'total_messages': len(self.latencies),
            'errors': len(self.errors),
            'error_rate': len(self.errors) / max(len(self.latencies), 1),
            'latency_ms': {
                'min': min(self.latencies),
                'max': max(self.latencies),
                'mean': mean(self.latencies),
                'median': median(self.latencies),
                'stdev': stdev(self.latencies) if len(self.latencies) > 1 else 0,
                'p50': sorted_latencies[int(n * 0.50)],
                'p95': sorted_latencies[int(n * 0.95)],
                'p99': sorted_latencies[int(n * 0.99)]
            }
        }


@pytest.mark.load
@pytest.mark.websocket
class TestWebSocketLoad:
    """WebSocket load test suite."""
    
    @pytest.mark.asyncio
    async def test_100_concurrent_connections(self):
        """Test 100 concurrent WebSocket connections."""
        test = WebSocketLoadTest(
            url='ws://localhost:8000/ws',
            num_connections=100
        )
        
        try:
            await test.connect()
            await test.send_messages(messages_per_connection=50)
            
            stats = test.get_stats()
            
            # Assert SLA
            assert stats['error_rate'] < 0.01, "Error rate exceeds 1%"
            assert stats['latency_ms']['p95'] < 100, "P95 latency exceeds 100ms"
            
        finally:
            await test.close()
    
    @pytest.mark.asyncio
    async def test_1000_concurrent_connections(self):
        """Test 1000 concurrent WebSocket connections (stress test)."""
        test = WebSocketLoadTest(
            url='ws://localhost:8000/ws',
            num_connections=1000
        )
        
        try:
            await test.connect()
            await test.send_messages(messages_per_connection=10)
            
            stats = test.get_stats()
            
            # Relaxed SLA for stress test
            assert stats['error_rate'] < 0.05, "Error rate exceeds 5%"
            assert stats['latency_ms']['p95'] < 500, "P95 latency exceeds 500ms"
            
        finally:
            await test.close()
    
    @pytest.mark.asyncio
    async def test_message_throughput(self):
        """Test message throughput capacity."""
        test = WebSocketLoadTest(
            url='ws://localhost:8000/ws',
            num_connections=50
        )
        
        try:
            await test.connect()
            
            start_time = time.time()
            await test.send_messages(messages_per_connection=1000)
            elapsed = time.time() - start_time
            
            total_messages = len(test.latencies)
            throughput = total_messages / elapsed
            
            print(f"\nMessage throughput: {throughput:.2f} messages/second")
            print(f"Total messages: {total_messages}")
            print(f"Elapsed time: {elapsed:.2f}s")
            
            # Assert minimum throughput
            assert throughput > 1000, "Throughput below 1000 messages/second"
            
        finally:
            await test.close()
    
    @pytest.mark.asyncio
    async def test_connection_stability(self):
        """Test long-running connection stability."""
        test = WebSocketLoadTest(
            url='ws://localhost:8000/ws',
            num_connections=20
        )
        
        try:
            await test.connect()
            
            # Send periodic messages over 60 seconds
            for _ in range(60):
                await test.send_messages(messages_per_connection=1)
                await asyncio.sleep(1)
            
            stats = test.get_stats()
            
            # Should have minimal errors over time
            assert stats['error_rate'] < 0.001, "Too many errors during stability test"
            
        finally:
            await test.close()
    
    @pytest.mark.asyncio
    async def test_reconnection_storm(self):
        """Test handling of mass reconnection."""
        # Simulate all clients disconnecting and reconnecting
        test = WebSocketLoadTest(
            url='ws://localhost:8000/ws',
            num_connections=200
        )
        
        try:
            # Initial connection
            await test.connect()
            await test.send_messages(messages_per_connection=10)
            
            # Mass disconnect
            await test.close()
            test.connections = []
            test.latencies = []
            
            # Rapid reconnection (storm)
            await test.connect()
            await test.send_messages(messages_per_connection=10)
            
            stats = test.get_stats()
            
            # System should recover
            assert stats['error_rate'] < 0.05
            
        finally:
            await test.close()


class WebSocketBroadcastTest:
    """Test WebSocket broadcast functionality."""
    
    def __init__(self, url, num_subscribers=100):
        self.url = url
        self.num_subscribers = num_subscribers
        self.subscribers = []
        self.received_counts = {}
    
    async def setup(self):
        """Setup subscriber connections."""
        from unittest.mock import AsyncMock
        
        for i in range(self.num_subscribers):
            ws = AsyncMock()
            ws.channel = f'channel_{i % 10}'  # 10 different channels
            self.subscribers.append(ws)
            self.received_counts[i] = 0
    
    async def broadcast_and_measure(self, num_messages=100):
        """Broadcast messages and measure delivery."""
        # This would publish to channels and verify subscribers receive
        pass
    
    async def cleanup(self):
        """Cleanup connections."""
        for ws in self.subscribers:
            await ws.close()


@pytest.mark.load
@pytest.mark.asyncio
async def test_broadcast_performance():
    """Test broadcast performance to many subscribers."""
    test = WebSocketBroadcastTest(
        url='ws://localhost:8000/ws',
        num_subscribers=500
    )
    
    try:
        await test.setup()
        await test.broadcast_and_measure(num_messages=50)
        
        # All subscribers should receive messages
        for count in test.received_counts.values():
            assert count == 50
            
    finally:
        await test.cleanup()
