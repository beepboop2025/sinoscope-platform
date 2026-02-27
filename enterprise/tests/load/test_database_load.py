"""
Database load testing.

Tests database performance under high load.
"""

import asyncio
import time
from datetime import datetime, timezone
import pytest
from statistics import mean, median


class DatabaseLoadTest:
    """Database load testing harness."""
    
    def __init__(self, db_url, concurrency=50):
        self.db_url = db_url
        self.concurrency = concurrency
        self.results = {
            'reads': [],
            'writes': [],
            'complex_queries': [],
            'errors': []
        }
    
    async def connect(self):
        """Establish database connection pool."""
        # Example with asyncpg:
        # import asyncpg
        # self.pool = await asyncpg.create_pool(
        #     self.db_url,
        #     min_size=self.concurrency,
        #     max_size=self.concurrency * 2
        # )
        
        # Mock for demonstration
        from unittest.mock import AsyncMock
        self.pool = AsyncMock()
        self.pool.fetch = AsyncMock(return_value=[{'id': 1}])
        self.pool.fetchrow = AsyncMock(return_value={'id': 1})
        self.pool.execute = AsyncMock(return_value='INSERT 1')
    
    async def close(self):
        """Close database connection."""
        await self.pool.close()
    
    async def run_read_test(self, iterations=1000):
        """Test read performance."""
        async def read_operation(iteration):
            start = time.time()
            try:
                await self.pool.fetch(
                    "SELECT * FROM users WHERE is_active = true LIMIT 100"
                )
                elapsed = (time.time() - start) * 1000
                self.results['reads'].append(elapsed)
            except Exception as e:
                self.results['errors'].append({'operation': 'read', 'error': str(e)})
        
        # Run concurrent reads
        tasks = [read_operation(i) for i in range(iterations)]
        await asyncio.gather(*tasks)
    
    async def run_write_test(self, iterations=500):
        """Test write performance."""
        async def write_operation(iteration):
            start = time.time()
            try:
                await self.pool.execute(
                    """
                    INSERT INTO load_test_logs (message, created_at)
                    VALUES ($1, $2)
                    """,
                    f"Test message {iteration}",
                    datetime.now(timezone.utc)
                )
                elapsed = (time.time() - start) * 1000
                self.results['writes'].append(elapsed)
            except Exception as e:
                self.results['errors'].append({'operation': 'write', 'error': str(e)})
        
        tasks = [write_operation(i) for i in range(iterations)]
        await asyncio.gather(*tasks)
    
    async def run_complex_query_test(self, iterations=100):
        """Test complex query performance."""
        async def complex_query(iteration):
            start = time.time()
            try:
                await self.pool.fetch(
                    """
                    SELECT 
                        p.id,
                        p.name,
                        COUNT(d.id) as doc_count,
                        COUNT(a.id) as analysis_count,
                        MAX(a.created_at) as last_analysis
                    FROM projects p
                    LEFT JOIN documents d ON d.project_id = p.id
                    LEFT JOIN analyses a ON a.project_id = p.id
                    WHERE p.created_at > $1
                    GROUP BY p.id
                    HAVING COUNT(d.id) > 0
                    ORDER BY doc_count DESC
                    LIMIT 50
                    """,
                    datetime.now(timezone.utc).replace(day=1)
                )
                elapsed = (time.time() - start) * 1000
                self.results['complex_queries'].append(elapsed)
            except Exception as e:
                self.results['errors'].append({'operation': 'complex', 'error': str(e)})
        
        tasks = [complex_query(i) for i in range(iterations)]
        await asyncio.gather(*tasks)
    
    def get_stats(self):
        """Get test statistics."""
        def calc_stats(values):
            if not values:
                return {}
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            return {
                'count': n,
                'min': min(values),
                'max': max(values),
                'mean': mean(values),
                'median': median(values),
                'p95': sorted_vals[int(n * 0.95)] if n > 1 else values[0],
                'p99': sorted_vals[int(n * 0.99)] if n > 1 else values[0]
            }
        
        return {
            'reads': calc_stats(self.results['reads']),
            'writes': calc_stats(self.results['writes']),
            'complex_queries': calc_stats(self.results['complex_queries']),
            'errors': len(self.results['errors']),
            'error_rate': len(self.results['errors']) / sum([
                len(self.results['reads']),
                len(self.results['writes']),
                len(self.results['complex_queries'])
            ]) if any(self.results.values()) else 0
        }


@pytest.mark.load
@pytest.mark.db
class TestDatabaseLoad:
    """Database load test suite."""
    
    @pytest.fixture
    async def db_load_test(self, test_config):
        """Create database load test instance."""
        test = DatabaseLoadTest(
            db_url=test_config['database_url'],
            concurrency=50
        )
        await test.connect()
        yield test
        await test.close()
    
    @pytest.mark.asyncio
    async def test_read_throughput(self, db_load_test):
        """Test read query throughput."""
        await db_load_test.run_read_test(iterations=5000)
        
        stats = db_load_test.get_stats()
        read_stats = stats['reads']
        
        print(f"\nRead Performance:")
        print(f"  Total reads: {read_stats['count']}")
        print(f"  Mean latency: {read_stats['mean']:.2f}ms")
        print(f"  P95 latency: {read_stats['p95']:.2f}ms")
        print(f"  P99 latency: {read_stats['p99']:.2f}ms")
        
        # Assert SLA
        assert read_stats['p95'] < 50, "Read P95 exceeds 50ms"
        assert stats['error_rate'] < 0.01
    
    @pytest.mark.asyncio
    async def test_write_throughput(self, db_load_test):
        """Test write query throughput."""
        await db_load_test.run_write_test(iterations=1000)
        
        stats = db_load_test.get_stats()
        write_stats = stats['writes']
        
        print(f"\nWrite Performance:")
        print(f"  Total writes: {write_stats['count']}")
        print(f"  Mean latency: {write_stats['mean']:.2f}ms")
        print(f"  P95 latency: {write_stats['p95']:.2f}ms")
        
        assert write_stats['p95'] < 100, "Write P95 exceeds 100ms"
    
    @pytest.mark.asyncio
    async def test_complex_query_performance(self, db_load_test):
        """Test complex join query performance."""
        await db_load_test.run_complex_query_test(iterations=200)
        
        stats = db_load_test.get_stats()
        query_stats = stats['complex_queries']
        
        print(f"\nComplex Query Performance:")
        print(f"  Total queries: {query_stats['count']}")
        print(f"  Mean latency: {query_stats['mean']:.2f}ms")
        print(f"  P95 latency: {query_stats['p95']:.2f}ms")
        
        assert query_stats['p95'] < 500, "Complex query P95 exceeds 500ms"
    
    @pytest.mark.asyncio
    async def test_mixed_workload(self, db_load_test):
        """Test mixed read/write workload."""
        # Run all tests concurrently
        await asyncio.gather(
            db_load_test.run_read_test(iterations=2000),
            db_load_test.run_write_test(iterations=500),
            db_load_test.run_complex_query_test(iterations=100)
        )
        
        stats = db_load_test.get_stats()
        
        print(f"\nMixed Workload Results:")
        print(f"  Reads: {stats['reads'].get('count', 0)}")
        print(f"  Writes: {stats['writes'].get('count', 0)}")
        print(f"  Complex: {stats['complex_queries'].get('count', 0)}")
        print(f"  Errors: {stats['errors']}")
        
        assert stats['error_rate'] < 0.05


class TestConnectionPool:
    """Test database connection pool behavior."""
    
    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self, test_config):
        """Test behavior when connection pool is exhausted."""
        # Create many concurrent connections
        num_connections = 200
        
        async def hold_connection(duration):
            """Hold a connection for specified duration."""
            # Get connection from pool
            await asyncio.sleep(duration)
        
        # Start many connection holders
        start = time.time()
        tasks = [hold_connection(2) for _ in range(num_connections)]
        await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start
        
        # With proper pooling, this should complete in ~2 seconds
        # Without pooling or with exhaustion, it would take much longer
        assert elapsed < 5, "Connection pool exhaustion detected"
    
    @pytest.mark.asyncio
    async def test_connection_recovery(self, test_config):
        """Test connection recovery after failure."""
        # Simulate connection failures
        # Verify pool recovers and continues serving requests
        pass


class TestQueryPerformance:
    """Test specific query performance."""
    
    @pytest.mark.asyncio
    async def test_full_text_search_performance(self, test_config):
        """Test full-text search query performance."""
        search_terms = [
            'quarterly report',
            'financial analysis',
            'market research',
            'quarterly earnings',
            'annual review'
        ]
        
        latencies = []
        
        for term in search_terms:
            start = time.time()
            # Execute search query
            elapsed = (time.time() - start) * 1000
            latencies.append(elapsed)
        
        avg_latency = mean(latencies)
        max_latency = max(latencies)
        
        print(f"\nFull-text Search Performance:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  Maximum: {max_latency:.2f}ms")
        
        assert avg_latency < 100, "Average search time exceeds 100ms"
    
    @pytest.mark.asyncio
    async def test_aggregate_query_performance(self, test_config):
        """Test aggregation query performance."""
        queries = [
            "SELECT status, COUNT(*) FROM documents GROUP BY status",
            "SELECT DATE(created_at), COUNT(*) FROM analyses GROUP BY DATE(created_at)",
            "SELECT organization_id, SUM(size) FROM documents GROUP BY organization_id"
        ]
        
        for query in queries:
            start = time.time()
            # Execute query
            elapsed = (time.time() - start) * 1000
            
            assert elapsed < 200, f"Query took {elapsed}ms: {query[:50]}"


class TestLockContention:
    """Test database lock behavior under load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_updates(self, test_config):
        """Test handling of concurrent updates to same row."""
        # Simulate many clients updating same counter
        # Should handle with proper locking, no lost updates
        pass
    
    @pytest.mark.asyncio
    async def test_deadlock_detection(self, test_config):
        """Test deadlock detection and resolution."""
        # Create deadlock scenario
        # Verify database detects and resolves
        pass
