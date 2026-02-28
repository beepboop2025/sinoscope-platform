"""
DragonScope Load Test
=====================
Simulates 500 concurrent users hitting API endpoints.

Usage:
    locust -f tests/load/locustfile.py --host=http://localhost:3456
    # Then open http://localhost:8089 to configure and start the test.

    # Headless mode (500 users, 50 users/sec spawn rate, 5 min run):
    locust -f tests/load/locustfile.py \
        --host=http://localhost:3456 \
        --users=500 \
        --spawn-rate=50 \
        --run-time=5m \
        --headless
"""
import os

from locust import HttpUser, between, task


class DragonScopeUser(HttpUser):
    """Simulates a typical DragonScope dashboard user."""

    wait_time = between(1, 5)

    def on_start(self):
        """Set up auth headers for all requests."""
        self.token = os.environ.get("LOAD_TEST_TOKEN", "test-bearer-token")
        self.client.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        })

    # ── Health check (highest weight - monitoring probes) ──────────
    @task(10)
    def health_check(self):
        self.client.get("/api/health", name="/api/health")

    # ── Data endpoints (medium weight - dashboard data) ────────────
    @task(5)
    def get_crypto_data(self):
        self.client.get("/api/data/crypto", name="/api/data/crypto")

    @task(5)
    def get_forex_data(self):
        self.client.get("/api/data/forex", name="/api/data/forex")

    # ── Portfolio (lower weight - authenticated feature) ───────────
    @task(3)
    def get_portfolios(self):
        self.client.get("/api/portfolios", name="/api/portfolios")

    # ── Quant analytics (lowest weight - expensive computation) ────
    @task(1)
    def get_yield_curves(self):
        self.client.get("/api/quant/yield-curves", name="/api/quant/yield-curves")
