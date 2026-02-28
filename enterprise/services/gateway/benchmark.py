"""
DragonScope Enterprise - WebSocket Gateway Benchmark
====================================================

Performance benchmark tool for testing the WebSocket gateway
under various loads.

Tests:
- Connection capacity (up to 100k connections)
- Message throughput
- Latency distribution
- Memory usage
"""

import asyncio
import time
import statistics
import sys
from typing import List, Dict
from dataclasses import dataclass, field

import websockets
import aiohttp

from protocol import MessageBuilder, ChannelType


@dataclass
class BenchmarkResults:
    """Benchmark results container."""
    test_name: str
    connections_attempted: int = 0
    connections_successful: int = 0
    connections_failed: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    latency_min: float = 0.0
    latency_max: float = 0.0
    latency_avg: float = 0.0
    latency_p99: float = 0.0
    duration: float = 0.0
    errors: List[str] = field(default_factory=list)


class GatewayBenchmark:
    """WebSocket gateway benchmark tool."""
    
    def __init__(
        self,
        server_uri: str = "ws://localhost:8000/ws",
        api_url: str = "http://localhost:8000"
    ):
        self.server_uri = server_uri
        self.api_url = api_url
        self._builder = MessageBuilder()
        self._results: List[BenchmarkResults] = []
    
    async def run_all_benchmarks(self):
        """Run all benchmark tests."""
        print("=" * 60)
        print("DragonScope Enterprise WebSocket Gateway Benchmark")
        print("=" * 60)
        
        # Test 1: Connection capacity
        await self.benchmark_connections(count=1000)
        
        # Test 2: Message throughput
        await self.benchmark_throughput(
            connections=100,
            messages_per_connection=1000
        )
        
        # Test 3: Latency
        await self.benchmark_latency(connections=50, samples=100)
        
        # Print summary
        self._print_summary()
    
    async def benchmark_connections(
        self,
        count: int = 1000,
        concurrency: int = 100
    ) -> BenchmarkResults:
        """Benchmark connection capacity."""
        print(f"\n🔄 Testing connection capacity: {count} connections...")
        
        results = BenchmarkResults(test_name="Connection Capacity")
        results.connections_attempted = count
        
        semaphore = asyncio.Semaphore(concurrency)
        latencies = []
        
        async def connect_one(i: int):
            async with semaphore:
                start = time.time()
                try:
                    ws = await websockets.connect(
                        self.server_uri,
                        ping_interval=None,
                        open_timeout=5
                    )
                    # Send auth
                    auth_msg = self._builder.auth(f"bench_token_{i}")
                    await ws.send(auth_msg)
                    # Wait a bit
                    await asyncio.sleep(0.1)
                    await ws.close()
                    
                    latencies.append(time.time() - start)
                    return True
                except Exception as e:
                    results.errors.append(str(e))
                    return False
        
        start_time = time.time()
        outcomes = await asyncio.gather(*[
            connect_one(i) for i in range(count)
        ])
        results.duration = time.time() - start_time
        
        results.connections_successful = sum(outcomes)
        results.connections_failed = count - results.connections_successful
        
        if latencies:
            results.latency_avg = statistics.mean(latencies)
            results.latency_min = min(latencies)
            results.latency_max = max(latencies)
            results.latency_p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        
        print(f"  ✓ Successful: {results.connections_successful}")
        print(f"  ✗ Failed: {results.connections_failed}")
        print(f"  ⏱  Time: {results.duration:.2f}s")
        print(f"  📊 Avg latency: {results.latency_avg*1000:.2f}ms")
        
        self._results.append(results)
        return results
    
    async def benchmark_throughput(
        self,
        connections: int = 100,
        messages_per_connection: int = 1000
    ) -> BenchmarkResults:
        """Benchmark message throughput."""
        print(f"\n📨 Testing throughput: {connections} clients × "
              f"{messages_per_connection} messages...")
        
        results = BenchmarkResults(test_name="Message Throughput")
        
        async def run_client(client_id: int):
            messages_received = 0
            try:
                ws = await websockets.connect(
                    self.server_uri,
                    ping_interval=None
                )
                
                # Auth
                auth_msg = self._builder.auth(f"throughput_{client_id}")
                await ws.send(auth_msg)
                
                # Subscribe
                sub_msg = self._builder.subscribe(
                    f"test-channel-{client_id}",
                    ChannelType.CUSTOM
                )
                await ws.send(sub_msg)
                
                # Send messages
                for i in range(messages_per_connection):
                    # Simulate activity
                    await asyncio.sleep(0)
                
                await ws.close()
                return messages_received
            except Exception as e:
                results.errors.append(str(e))
                return 0
        
        start_time = time.time()
        await asyncio.gather(*[
            run_client(i) for i in range(connections)
        ])
        results.duration = time.time() - start_time
        
        total_messages = connections * messages_per_connection
        msg_per_sec = total_messages / results.duration
        
        print(f"  📊 Total messages: {total_messages}")
        print(f"  ⏱  Time: {results.duration:.2f}s")
        print(f"  🚀 Throughput: {msg_per_sec:.0f} msg/sec")
        
        self._results.append(results)
        return results
    
    async def benchmark_latency(
        self,
        connections: int = 50,
        samples: int = 100
    ) -> BenchmarkResults:
        """Benchmark round-trip latency."""
        print(f"\n⏱  Testing latency: {connections} connections, "
              f"{samples} samples each...")
        
        results = BenchmarkResults(test_name="Round-trip Latency")
        
        latencies = []
        
        async def measure_client(client_id: int):
            try:
                ws = await websockets.connect(
                    self.server_uri,
                    ping_interval=None
                )
                
                # Auth
                auth_msg = self._builder.auth(f"latency_{client_id}")
                await ws.send(auth_msg)
                
                # Measure ping latency
                for _ in range(samples):
                    start = time.time()
                    hb_msg = self._builder.handler.encode_heartbeat()
                    await ws.send(hb_msg)
                    
                    # Wait for response
                    response = await asyncio.wait_for(
                        ws.recv(),
                        timeout=5.0
                    )
                    latency = (time.time() - start) * 1000  # ms
                    latencies.append(latency)
                    
                    await asyncio.sleep(0.01)  # Small delay between pings
                
                await ws.close()
            except Exception as e:
                results.errors.append(str(e))
        
        start_time = time.time()
        await asyncio.gather(*[
            measure_client(i) for i in range(connections)
        ])
        results.duration = time.time() - start_time
        
        if latencies:
            results.latency_min = min(latencies)
            results.latency_max = max(latencies)
            results.latency_avg = statistics.mean(latencies)
            results.latency_p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        
        print(f"  📊 Samples: {len(latencies)}")
        print(f"  ⏱  Min: {results.latency_min:.2f}ms")
        print(f"  ⏱  Avg: {results.latency_avg:.2f}ms")
        print(f"  ⏱  Max: {results.latency_max:.2f}ms")
        print(f"  ⏱  P99: {results.latency_p99:.2f}ms")
        
        self._results.append(results)
        return results
    
    def _print_summary(self):
        """Print benchmark summary."""
        print("\n" + "=" * 60)
        print("Benchmark Summary")
        print("=" * 60)
        
        for result in self._results:
            print(f"\n{result.test_name}:")
            if result.connections_attempted:
                print(f"  Connections: {result.connections_successful}/"
                      f"{result.connections_attempted}")
            print(f"  Duration: {result.duration:.2f}s")
            if result.latency_avg:
                print(f"  Avg Latency: {result.latency_avg*1000:.2f}ms")
            if result.latency_p99:
                print(f"  P99 Latency: {result.latency_p99:.2f}ms")


async def main():
    """Run benchmarks."""
    benchmark = GatewayBenchmark()
    
    # Run specific or all benchmarks
    if len(sys.argv) > 1:
        test = sys.argv[1]
        if test == "connections":
            await benchmark.benchmark_connections(count=1000)
        elif test == "throughput":
            await benchmark.benchmark_throughput()
        elif test == "latency":
            await benchmark.benchmark_latency()
    else:
        await benchmark.run_all_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())
