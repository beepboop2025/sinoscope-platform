# DragonScope Enterprise Testing Suite

## Overview

This directory contains the comprehensive testing suite for DragonScope Enterprise, implementing a multi-layered testing strategy to ensure reliability, performance, and resilience of the platform.

## Testing Strategy

### Test Pyramid

```
        /\
       /  \
      / E2E \          (10%) - Critical user journeys
     /--------\
    /          \
   / Integration \      (30%) - Service interactions, DB, cache
  /--------------\
 /                \
/      Unit        \   (60%) - Business logic, functions, utilities
/--------------------\
```

### Coverage Requirements

| Layer | Minimum Coverage | Target Coverage |
|-------|-----------------|-----------------|
| Unit | 90% | 95% |
| Integration | 85% | 90% |
| E2E | Critical paths only | 100% of critical paths |
| Overall | 90% | 93% |

## Test Types

### 1. Unit Tests (`/unit/`)

Fast, isolated tests for individual components:
- **Business Logic**: Domain models, services, utilities
- **Validation**: Input/output validation, schema verification
- **Helpers**: Utility functions, formatters, transformers

**Characteristics:**
- No external dependencies (DB, cache, APIs)
- Mocked external services
- < 10ms per test
- Run in parallel

**Command:**
```bash
pytest tests/unit/ -v --cov=src --cov-report=html
```

### 2. Integration Tests (`/integration/`)

Tests for component interactions:
- **Service-to-Service**: API client integrations, service calls
- **Database**: Repository patterns, migrations, transactions
- **Cache**: Redis operations, caching strategies
- **Message Queue**: RabbitMQ/Kafka event publishing/consuming

**Characteristics:**
- Real dependencies in Docker containers
- Test data isolation per test
- 50-200ms per test
- Cleanup after each test

**Command:**
```bash
pytest tests/integration/ -v --integration
```

### 3. End-to-End Tests (`/e2e/`)

Full system tests simulating real user behavior:
- **User Journeys**: Complete workflows (signup → create project → analyze)
- **API Contracts**: Request/response validation against OpenAPI spec
- **WebSocket**: Real-time data streaming tests

**Characteristics:**
- Full application stack running
- Real browser for UI tests (Playwright)
- 1-5s per test
- Sequential execution

**Command:**
```bash
pytest tests/e2e/ -v --e2e
# or
playwright test tests/e2e/ui/
```

### 4. Load Tests (`/load/`)

Performance and scalability validation:
- **API Load**: HTTP endpoint stress testing
- **WebSocket Load**: Concurrent connection handling
- **Database Load**: Query performance under load

**Characteristics:**
- Simulates production load patterns
- Measures latency percentiles (p50, p95, p99)
- Identifies bottlenecks
- Run in staging environment

**Command:**
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

### 5. Chaos Engineering (`/chaos/`)

Resilience testing through controlled failures:
- **Network Chaos**: Latency, packet loss, partition
- **Service Chaos**: Random pod/container termination
- **Database Chaos**: Connection failures, failover testing
- **Resource Chaos**: CPU/memory exhaustion

**Characteristics:**
- Uses Chaos Mesh or similar tools
- Hypothesis-driven experiments
- Automatic rollback on safety violations
- Run during off-peak hours

**Command:**
```bash
chaos run tests/chaos/experiments/network-latency.yaml
```

## Test Environment

### Docker Compose Stack

```yaml
# See docker-compose.test.yml
services:
  - api: DragonScope API server (test config)
  - db: PostgreSQL 15 with test database
  - redis: Redis 7 for caching/tests
  - rabbitmq: Message queue for event tests
  - elasticsearch: Search index tests
  - minio: S3-compatible object storage
```

**Start test environment:**
```bash
docker-compose -f docker-compose.test.yml up -d
```

### Test Configuration

| Environment | Database | Coverage | Parallel |
|-------------|----------|----------|----------|
| `test` | In-memory/Container | Enabled | Yes |
| `ci` | Container | Enabled | Yes |
| `local` | Local Docker | Optional | Yes |
| `staging` | Staging instance | No | No |

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Unit Tests
        run: pytest tests/unit/ --cov=src --cov-fail-under=90

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
      redis:
        image: redis:7
    steps:
      - name: Run Integration Tests
        run: pytest tests/integration/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    steps:
      - name: Run E2E Tests
        run: pytest tests/e2e/ -v --e2e
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: pytest-unit
      name: Unit Tests
      entry: pytest tests/unit/ -q
      language: system
      pass_filenames: false
```

## Directory Structure

```
tests/
├── README.md                 # This file
├── conftest.py              # Shared pytest fixtures
├── pytest.ini              # Pytest configuration
├── docker-compose.test.yml # Test environment
├── fixtures/               # Test data and mocks
│   ├── data/              # JSON/YAML test data
│   ├── mocks/             # Mock implementations
│   └── factories.py       # Test data factories
├── unit/                  # Unit tests
│   ├── test_services.py
│   ├── test_models.py
│   └── test_utils.py
├── integration/           # Integration tests
│   ├── test_database.py
│   ├── test_cache.py
│   └── test_messaging.py
├── e2e/                   # End-to-end tests
│   ├── test_api.py
│   ├── test_websocket.py
│   └── ui/               # Playwright UI tests
├── load/                 # Load tests
│   ├── locustfile.py
│   └── scenarios/
├── chaos/                # Chaos experiments
│   ├── experiments/
│   └── scripts/
└── ci/                   # CI/CD scripts
    ├── run_tests.sh
    └── coverage_report.sh
```

## Best Practices

### 1. Test Naming
```python
# Good: Descriptive and follows pattern
def test_user_service_raises_error_when_email_already_exists():
    pass

# Bad: Vague or implementation-focused
def test_user_service_1():
    pass
```

### 2. Test Isolation
```python
# Use fixtures for setup/teardown
@pytest.fixture
def db_session():
    session = create_test_session()
    yield session
    session.rollback()
    session.close()
```

### 3. Mocking External Services
```python
# Mock at the boundary
@pytest.fixture
def mock_payment_gateway():
    with patch('services.payment.StripeClient') as mock:
        mock.return_value.charge.return_value = {'id': 'ch_123'}
        yield mock
```

### 4. Assertions
```python
# Prefer explicit assertions
assert response.status_code == 201
assert user.email == "test@example.com"

# Use helpers for complex assertions
assert_json_schema(response.json(), UserSchema)
```

## Running Tests

### Quick Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_services.py -v

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Run specific test class/method
pytest tests/unit/test_services.py::TestUserService::test_create_user -v

# Run tests matching pattern
pytest -k "test_user" -v

# Run with debugging
pytest --pdb -x  # Stop on first failure, enter debugger

# Run parallel (requires pytest-xdist)
pytest -n auto
```

### Environment Variables

```bash
# Set test environment
export DRAGONSCOPE_ENV=test

# Enable debug logging
export DEBUG_TESTS=1

# Set test database URL
export TEST_DATABASE_URL=postgresql://test:test@localhost:5433/dragonscope_test

# Disable coverage for faster local runs
export SKIP_COVERAGE=1
```

## Troubleshooting

### Common Issues

1. **Database locked errors**: Ensure test transactions are properly rolled back
2. **Port conflicts**: Check if test containers are already running
3. **Import errors**: Verify PYTHONPATH includes the src directory
4. **Async warnings**: Use `pytest-asyncio` mode = auto in pytest.ini

### Debug Mode

```bash
# Enable verbose output
pytest -vvs --tb=long

# Show local variables on failure
pytest --showlocals

# Capture logs
pytest --log-cli-level=DEBUG
```

## Contributing

When adding new tests:
1. Follow the existing naming conventions
2. Add fixtures to `conftest.py` if reusable
3. Update this README if adding new test types
4. Ensure tests pass in CI before submitting PR

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Locust Load Testing](https://docs.locust.io/)
- [Playwright E2E](https://playwright.dev/)
- [Chaos Engineering Principles](https://principlesofchaos.org/)
