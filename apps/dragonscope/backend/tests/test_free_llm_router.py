"""
Pure-logic tests for the ``free_llm_router`` failover package.

Everything here runs with NO network, NO API keys, NO external services:
  * the token bucket and circuit breaker take an injected ``monotonic`` clock,
    so time-based behaviour is driven by a deterministic fake clock;
  * the router's provider ordering, tier resolution, rate-limit gating and
    failover loop are exercised with fake providers + a monkeypatched ``_call``
    so the actual HTTP round-trip is never made.

These tests pin real behaviour (atomic check-and-take, single-probe half-open,
quota/circuit gating, failover semantics) — not "it imports".
"""

import asyncio

import pytest

from free_llm_router import (
    AllProvidersFailed,
    CircuitBreaker,
    FreeLLMRouter,
    Provider,
    ProviderStats,
    REGISTRY,
    State,
    TASK_TIER,
    TokenBucket,
    available_providers,
    default_order,
)


# ---------------------------------------------------------------------------
# Fake monotonic clock — advance time by hand, deterministically.
# ---------------------------------------------------------------------------
class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_provider(name="p", *, rpm=30, rpd=None, priority=10, tiers=None):
    return Provider(
        name=name,
        base_url=f"https://example.test/{name}/v1",
        api_key_env=f"{name.upper()}_KEY",
        models=tiers if tiers is not None else {"fast": "f-model", "smart": "s-model"},
        rpm=rpm,
        rpd=rpd,
        priority=priority,
    )


# ===========================================================================
# TokenBucket
# ===========================================================================
class TestTokenBucket:
    @pytest.mark.asyncio
    async def test_starts_full_and_drains_one_per_acquire(self):
        clock = FakeClock()
        b = TokenBucket(rpm=3, monotonic=clock)
        # 3 tokens to start, no time passing -> exactly 3 acquires succeed.
        assert await b.try_acquire() is True
        assert await b.try_acquire() is True
        assert await b.try_acquire() is True
        assert await b.try_acquire() is False  # bucket empty

    @pytest.mark.asyncio
    async def test_refill_is_proportional_to_elapsed_time(self):
        clock = FakeClock()
        b = TokenBucket(rpm=60, monotonic=clock)  # 1 token/sec refill
        # Drain everything.
        for _ in range(60):
            assert await b.try_acquire() is True
        assert await b.try_acquire() is False
        # Advance 2 seconds -> ~2 tokens back.
        clock.advance(2.0)
        assert await b.try_acquire() is True
        assert await b.try_acquire() is True
        assert await b.try_acquire() is False

    @pytest.mark.asyncio
    async def test_refill_never_exceeds_capacity(self):
        clock = FakeClock()
        b = TokenBucket(rpm=5, monotonic=clock)
        clock.advance(10_000)  # huge idle period
        # Capacity is 5: only 5 acquires should ever succeed back-to-back.
        succeeded = 0
        for _ in range(20):
            if await b.try_acquire():
                succeeded += 1
        assert succeeded == 5

    @pytest.mark.asyncio
    async def test_seconds_until_token_zero_when_available(self):
        clock = FakeClock()
        b = TokenBucket(rpm=30, monotonic=clock)
        assert await b.seconds_until_token() == 0.0

    @pytest.mark.asyncio
    async def test_seconds_until_token_estimates_wait_when_empty(self):
        clock = FakeClock()
        b = TokenBucket(rpm=60, monotonic=clock)  # 1 token/sec
        for _ in range(60):
            await b.try_acquire()
        # Empty now; need 1 full token => ~1 second.
        wait = await b.seconds_until_token()
        assert wait == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.asyncio
    async def test_rpm_floor_of_one(self):
        # rpm <= 0 must not divide-by-zero or deadlock; floored to 1.
        clock = FakeClock()
        b = TokenBucket(rpm=0, monotonic=clock)
        assert await b.try_acquire() is True
        assert await b.try_acquire() is False

    @pytest.mark.asyncio
    async def test_day_count_tracks_only_successful_acquires(self):
        clock = FakeClock()
        b = TokenBucket(rpm=2, monotonic=clock)
        await b.try_acquire()
        await b.try_acquire()
        await b.try_acquire()  # fails — bucket empty
        assert b.day_count == 2  # the failed acquire did not increment
        b.reset_day()
        assert b.day_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_acquire_is_atomic_no_oversell(self):
        # The documented TOCTOU bug: two coroutines both seeing the last token.
        # With one token, exactly one of N concurrent acquirers may win.
        clock = FakeClock()
        b = TokenBucket(rpm=1, monotonic=clock)
        results = await asyncio.gather(*[b.try_acquire() for _ in range(50)])
        assert sum(results) == 1


# ===========================================================================
# CircuitBreaker
# ===========================================================================
class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_starts_closed_and_allows(self):
        cb = CircuitBreaker(monotonic=FakeClock())
        assert cb.state is State.CLOSED
        assert await cb.allow() is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(monotonic=FakeClock(), failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state is State.CLOSED  # 2 < 3
        await cb.record_failure()
        assert cb.state is State.OPEN
        assert await cb.allow() is False  # rejects fast while open

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        cb = CircuitBreaker(monotonic=FakeClock(), failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()  # resets the counter
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state is State.CLOSED  # only 2 since reset

    @pytest.mark.asyncio
    async def test_half_open_after_cooldown_then_closes_on_probe_success(self):
        clock = FakeClock()
        cb = CircuitBreaker(monotonic=clock, failure_threshold=1, cooldown_sec=30.0)
        await cb.record_failure()  # -> OPEN
        assert cb.state is State.OPEN
        # Before cooldown: still rejected.
        clock.advance(29.0)
        assert await cb.allow() is False
        # After cooldown: one probe permitted, state goes HALF_OPEN.
        clock.advance(2.0)
        assert await cb.allow() is True
        assert cb.state is State.HALF_OPEN
        await cb.record_success()
        assert cb.state is State.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_reopens_on_probe_failure_and_restarts_cooldown(self):
        clock = FakeClock()
        cb = CircuitBreaker(monotonic=clock, failure_threshold=1, cooldown_sec=30.0)
        await cb.record_failure()  # OPEN
        clock.advance(31.0)
        assert await cb.allow() is True  # HALF_OPEN probe
        await cb.record_failure()  # probe fails -> back to OPEN, cooldown restarts
        assert cb.state is State.OPEN
        # Cooldown clock restarted: 10s later still closed-off.
        clock.advance(10.0)
        assert await cb.allow() is False

    @pytest.mark.asyncio
    async def test_half_open_allows_only_one_probe(self):
        # The oscillation bug: many probes rushing a still-broken provider.
        clock = FakeClock()
        cb = CircuitBreaker(monotonic=clock, failure_threshold=1, cooldown_sec=10.0)
        await cb.record_failure()  # OPEN
        clock.advance(11.0)
        # Fire many concurrent allow() checks — exactly ONE probe may pass.
        results = await asyncio.gather(*[cb.allow() for _ in range(20)])
        assert sum(1 for r in results if r) == 1


# ===========================================================================
# Provider registry / model resolution
# ===========================================================================
class TestProviders:
    def test_registry_priorities_unique_and_ordered(self):
        prios = [p.priority for p in REGISTRY]
        assert len(prios) == len(set(prios)), "priorities must be unique tie-breakers"

    def test_every_registry_provider_offers_both_tiers(self):
        for p in REGISTRY:
            assert p.model_for("fast"), f"{p.name} missing fast model"
            assert p.model_for("smart"), f"{p.name} missing smart model"

    def test_model_for_unknown_tier_is_none(self):
        p = make_provider()
        assert p.model_for("nonexistent") is None

    def test_api_key_reads_from_environment(self, monkeypatch):
        p = make_provider(name="zz")
        monkeypatch.delenv("ZZ_KEY", raising=False)
        assert p.api_key is None
        monkeypatch.setenv("ZZ_KEY", "secret-123")
        assert p.api_key == "secret-123"

    def test_empty_env_var_treated_as_no_key(self, monkeypatch):
        p = make_provider(name="zz")
        monkeypatch.setenv("ZZ_KEY", "")  # empty string -> falsy -> None
        assert p.api_key is None

    def test_available_providers_filters_by_key_presence(self, monkeypatch):
        # Clear every registry key, then set exactly one.
        for p in REGISTRY:
            monkeypatch.delenv(p.api_key_env, raising=False)
        assert available_providers() == []
        target = REGISTRY[0]
        monkeypatch.setenv(target.api_key_env, "k")
        avail = available_providers()
        assert [p.name for p in avail] == [target.name]


# ===========================================================================
# Default ordering policy + tier mapping
# ===========================================================================
def _stats_for(provider, **kw):
    return ProviderStats(
        provider=provider,
        circuit_state=kw.get("circuit_state", "closed"),
        tokens_available=kw.get("tokens_available", True),
        day_count=kw.get("day_count", 0),
        day_limit=kw.get("day_limit", provider.rpd),
        last_latency_ms=kw.get("last_latency_ms", 0.0),
    )


class TestOrderingAndTiers:
    def test_default_order_sorts_by_priority_ascending(self):
        a = make_provider(name="a", priority=50)
        b = make_provider(name="b", priority=10)
        c = make_provider(name="c", priority=30)
        # Pass in deliberately-unsorted stats.
        ordered = default_order([_stats_for(a), _stats_for(b), _stats_for(c)])
        assert [p.name for p in ordered] == ["b", "c", "a"]

    def test_default_order_is_stable_and_total(self):
        provs = [make_provider(name=f"p{i}", priority=i) for i in (3, 1, 2)]
        ordered = default_order([_stats_for(p) for p in provs])
        assert [p.priority for p in ordered] == [1, 2, 3]
        assert len(ordered) == 3

    def test_task_tier_maps_fast_and_smart_buckets(self):
        assert TASK_TIER["classification"] == "fast"
        assert TASK_TIER["sentiment"] == "fast"
        assert TASK_TIER["summarization"] == "smart"
        assert TASK_TIER["advisory"] == "smart"

    def test_unknown_task_type_falls_through_to_smart_default(self):
        # Router uses TASK_TIER.get(task_type, "smart").
        assert TASK_TIER.get("totally-unknown", "smart") == "smart"


# ===========================================================================
# Router failover loop — _call monkeypatched so NO network happens.
# ===========================================================================
def _result(provider_name, text="ok"):
    return {
        "text": text,
        "model": "m",
        "provider": provider_name,
        "tokens": {"prompt": 1, "completion": 1, "total": 2},
        "latency_ms": 12.0,
        "cost_usd": 0.0,
    }


class TestRouterFailover:
    @pytest.mark.asyncio
    async def test_uses_highest_priority_provider_first(self):
        clock = FakeClock()
        lo = make_provider(name="lo", priority=10)
        hi = make_provider(name="hi", priority=50)
        router = FreeLLMRouter([hi, lo], monotonic=clock)

        async def fake_call(provider, model, messages, temperature, max_tokens):
            return _result(provider.name)

        router._call = fake_call
        res = await router.chat_completion([{"role": "user", "content": "hi"}], tier="fast")
        assert res["provider"] == "lo"  # lower priority number preferred

    @pytest.mark.asyncio
    async def test_fails_over_to_next_provider_on_error(self):
        clock = FakeClock()
        first = make_provider(name="first", priority=10)
        second = make_provider(name="second", priority=20)
        router = FreeLLMRouter([first, second], monotonic=clock)

        calls = []

        async def fake_call(provider, model, messages, temperature, max_tokens):
            calls.append(provider.name)
            if provider.name == "first":
                raise RuntimeError("boom")
            return _result(provider.name)

        router._call = fake_call
        res = await router.chat_completion([{"role": "user", "content": "x"}], tier="smart")
        assert res["provider"] == "second"
        assert calls == ["first", "second"]  # tried first, then failed over

    @pytest.mark.asyncio
    async def test_all_providers_failing_raises_aggregate_error(self):
        clock = FakeClock()
        a = make_provider(name="a", priority=10)
        b = make_provider(name="b", priority=20)
        router = FreeLLMRouter([a, b], monotonic=clock)

        async def fake_call(provider, model, messages, temperature, max_tokens):
            raise RuntimeError("nope-" + provider.name)

        router._call = fake_call
        with pytest.raises(AllProvidersFailed) as exc:
            await router.chat_completion([{"role": "user", "content": "x"}], tier="fast")
        # Aggregate error names what was attempted and the last underlying error.
        assert "a" in str(exc.value) and "b" in str(exc.value)
        assert "nope-b" in str(exc.value)

    @pytest.mark.asyncio
    async def test_provider_missing_tier_model_is_skipped(self):
        clock = FakeClock()
        # 'fastonly' has no smart model; router must skip it for a smart request.
        fastonly = make_provider(name="fastonly", priority=10, tiers={"fast": "f"})
        full = make_provider(name="full", priority=20)
        router = FreeLLMRouter([fastonly, full], monotonic=clock)

        async def fake_call(provider, model, messages, temperature, max_tokens):
            return _result(provider.name)

        router._call = fake_call
        res = await router.chat_completion([{"role": "user", "content": "x"}], tier="smart")
        assert res["provider"] == "full"

    @pytest.mark.asyncio
    async def test_daily_quota_exhausted_provider_is_skipped(self):
        clock = FakeClock()
        capped = make_provider(name="capped", priority=10, rpd=1)
        backup = make_provider(name="backup", priority=20)
        router = FreeLLMRouter([capped, backup], monotonic=clock)

        async def fake_call(provider, model, messages, temperature, max_tokens):
            return _result(provider.name)

        router._call = fake_call
        # First request consumes capped's single daily token.
        r1 = await router.chat_completion([{"role": "user", "content": "1"}], tier="fast")
        assert r1["provider"] == "capped"
        # Second request: capped at day limit -> must fail over to backup.
        r2 = await router.chat_completion([{"role": "user", "content": "2"}], tier="fast")
        assert r2["provider"] == "backup"

    @pytest.mark.asyncio
    async def test_rate_limited_minute_skips_to_next_provider(self):
        clock = FakeClock()
        # rpm=1 -> only one request per minute before refill.
        burst = make_provider(name="burst", priority=10, rpm=1)
        backup = make_provider(name="backup", priority=20, rpm=30)
        router = FreeLLMRouter([burst, backup], monotonic=clock)

        async def fake_call(provider, model, messages, temperature, max_tokens):
            return _result(provider.name)

        router._call = fake_call
        r1 = await router.chat_completion([{"role": "user", "content": "1"}], tier="fast")
        r2 = await router.chat_completion([{"role": "user", "content": "2"}], tier="fast")
        assert r1["provider"] == "burst"      # used burst's one token
        assert r2["provider"] == "backup"     # burst rate-limited this minute

    @pytest.mark.asyncio
    async def test_open_circuit_provider_is_skipped(self):
        clock = FakeClock()
        flaky = make_provider(name="flaky", priority=10)
        backup = make_provider(name="backup", priority=20)
        router = FreeLLMRouter([flaky, backup], monotonic=clock)

        async def fake_call(provider, model, messages, temperature, max_tokens):
            if provider.name == "flaky":
                raise RuntimeError("die")
            return _result(provider.name)

        router._call = fake_call
        # Default failure_threshold is 3 — drive flaky's breaker open.
        for _ in range(3):
            await router.chat_completion([{"role": "user", "content": "x"}], tier="fast")
        assert router._breakers["flaky"].state is State.OPEN
        # Next call: flaky's circuit open -> goes straight to backup without calling it.
        called = []

        async def tracking_call(provider, model, messages, temperature, max_tokens):
            called.append(provider.name)
            return _result(provider.name)

        router._call = tracking_call
        res = await router.chat_completion([{"role": "user", "content": "x"}], tier="fast")
        assert res["provider"] == "backup"
        assert "flaky" not in called  # open circuit short-circuited it

    @pytest.mark.asyncio
    async def test_successful_call_records_latency_for_ordering(self):
        clock = FakeClock()
        p = make_provider(name="p", priority=10)
        router = FreeLLMRouter([p], monotonic=clock)

        async def fake_call(provider, model, messages, temperature, max_tokens):
            return _result(provider.name, text="hello")

        router._call = fake_call
        await router.chat_completion([{"role": "user", "content": "x"}], tier="fast")
        assert router._last_latency["p"] == 12.0

    @pytest.mark.asyncio
    async def test_task_type_resolves_tier_when_tier_not_given(self):
        clock = FakeClock()
        # 'fastonly' only has a fast model; a 'classification' task -> fast tier,
        # so it should be picked instead of being skipped.
        fastonly = make_provider(name="fastonly", priority=10, tiers={"fast": "f"})
        router = FreeLLMRouter([fastonly], monotonic=clock)
        seen = {}

        async def fake_call(provider, model, messages, temperature, max_tokens):
            seen["model"] = model
            return _result(provider.name)

        router._call = fake_call
        res = await router.chat_completion(
            [{"role": "user", "content": "x"}], task_type="classification"
        )
        assert res["provider"] == "fastonly"
        assert seen["model"] == "f"


class TestQuickClassify:
    @pytest.mark.asyncio
    async def test_returns_matching_category_from_model_text(self):
        clock = FakeClock()
        router = FreeLLMRouter([make_provider(name="p")], monotonic=clock)

        async def fake_completion(messages, **kwargs):
            return {"text": "  BULLISH  "}

        router.chat_completion = fake_completion
        out = await router.quick_classify("stonks go up", ["bullish", "bearish", "neutral"])
        assert out == "bullish"

    @pytest.mark.asyncio
    async def test_falls_back_to_first_category_when_no_match(self):
        clock = FakeClock()
        router = FreeLLMRouter([make_provider(name="p")], monotonic=clock)

        async def fake_completion(messages, **kwargs):
            return {"text": "completely unrelated gibberish"}

        router.chat_completion = fake_completion
        out = await router.quick_classify("???", ["bullish", "bearish"])
        assert out == "bullish"  # first category is the documented default
