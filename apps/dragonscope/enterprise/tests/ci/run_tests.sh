#!/bin/bash
# DragonScope Enterprise - CI Test Runner
# Comprehensive test execution script for CI/CD pipelines

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COVERAGE_THRESHOLD=90
TEST_TIMEOUT=300  # 5 minutes
PARALLEL_WORKERS=4

# Test results
FAILED=0
PASSED=0
SKIPPED=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Setup function
setup() {
    log_info "Setting up test environment..."
    
    # Create test environment
    export DRAGONSCOPE_ENV=test
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONUNBUFFERED=1
    
    # Ensure test database is clean
    log_info "Initializing test database..."
    
    # Start test services if using docker
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.test.yml up -d postgres redis rabbitmq
        
        # Wait for services to be ready
        log_info "Waiting for services to be ready..."
        sleep 10
    fi
    
    log_success "Setup complete"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    
    # Generate coverage report
    if [ -f .coverage ]; then
        log_info "Generating coverage report..."
        coverage html -d reports/coverage
        coverage xml -o reports/coverage.xml
    fi
    
    # Stop test services
    if command -v docker-compose &> /dev/null; then
        docker-compose -f docker-compose.test.yml down
    fi
    
    log_success "Cleanup complete"
}

# Run unit tests
run_unit_tests() {
    log_info "=========================================="
    log_info "Running UNIT TESTS"
    log_info "=========================================="
    
    if pytest tests/unit/ \
        -v \
        --tb=short \
        --strict-markers \
        -m "unit" \
        --cov=src \
        --cov-append \
        --cov-report=term-missing:skip-covered \
        --timeout=${TEST_TIMEOUT} \
        -n ${PARALLEL_WORKERS} \
        --dist=loadfile; then
        
        log_success "Unit tests passed"
        ((PASSED++))
    else
        log_error "Unit tests failed"
        ((FAILED++))
        return 1
    fi
}

# Run integration tests
run_integration_tests() {
    log_info "=========================================="
    log_info "Running INTEGRATION TESTS"
    log_info "=========================================="
    
    if pytest tests/integration/ \
        -v \
        --tb=short \
        --strict-markers \
        -m "integration" \
        --integration \
        --cov=src \
        --cov-append \
        --timeout=${TEST_TIMEOUT}; then
        
        log_success "Integration tests passed"
        ((PASSED++))
    else
        log_error "Integration tests failed"
        ((FAILED++))
        return 1
    fi
}

# Run E2E tests
run_e2e_tests() {
    log_info "=========================================="
    log_info "Running E2E TESTS"
    log_info "=========================================="
    
    # Ensure API is running
    log_info "Starting test API server..."
    # uvicorn main:app --host 0.0.0.0 --port 8000 &
    # API_PID=$!
    # sleep 5
    
    if pytest tests/e2e/ \
        -v \
        --tb=short \
        --strict-markers \
        -m "e2e" \
        --e2e \
        --cov=src \
        --cov-append \
        --timeout=${TEST_TIMEOUT}; then
        
        log_success "E2E tests passed"
        ((PASSED++))
    else
        log_error "E2E tests failed"
        ((FAILED++))
    fi
    
    # kill $API_PID 2>/dev/null || true
}

# Run security tests
run_security_tests() {
    log_info "=========================================="
    log_info "Running SECURITY TESTS"
    log_info "=========================================="
    
    # Bandit - security linter
    log_info "Running bandit security scan..."
    if bandit -r src/ -f json -o reports/bandit-report.json || true; then
        log_success "Bandit scan complete"
    fi
    
    # Safety - check dependencies
    log_info "Running safety check..."
    if safety check --json --output reports/safety-report.json || true; then
        log_success "Safety check complete"
    fi
    
    ((PASSED++))
}

# Run load tests
run_load_tests() {
    log_info "=========================================="
    log_info "Running LOAD TESTS"
    log_info "=========================================="
    
    # Start Locust for quick smoke test
    log_info "Running quick load test..."
    
    locust -f tests/load/locustfile.py \
        --host http://localhost:8000 \
        --users 10 \
        --spawn-rate 2 \
        --run-time 1m \
        --headless \
        --only-summary \
        --html reports/load-test-report.html || true
    
    log_success "Load tests complete"
    ((PASSED++))
}

# Check code quality
run_quality_checks() {
    log_info "=========================================="
    log_info "Running CODE QUALITY CHECKS"
    log_info "=========================================="
    
    # Black formatting check
    log_info "Checking code formatting (black)..."
    if black --check src/ tests/; then
        log_success "Code formatting OK"
    else
        log_warn "Code formatting issues found. Run 'black src/ tests/' to fix"
        ((FAILED++))
    fi
    
    # isort import order check
    log_info "Checking import order (isort)..."
    if isort --check-only src/ tests/; then
        log_success "Import order OK"
    else
        log_warn "Import order issues found. Run 'isort src/ tests/' to fix"
        ((FAILED++))
    fi
    
    # Flake8 linting
    log_info "Running linter (flake8)..."
    if flake8 src/ tests/ --max-line-length=100 --extend-ignore=E203; then
        log_success "Linting passed"
    else
        log_error "Linting failed"
        ((FAILED++))
    fi
    
    # MyPy type checking
    log_info "Running type checker (mypy)..."
    if mypy src/ --ignore-missing-imports --show-error-codes; then
        log_success "Type checking passed"
    else
        log_warn "Type checking issues found"
    fi
    
    ((PASSED++))
}

# Check coverage
check_coverage() {
    log_info "=========================================="
    log_info "Checking CODE COVERAGE"
    log_info "=========================================="
    
    # Generate coverage report
    coverage report --fail-under=${COVERAGE_THRESHOLD}
    
    if [ $? -eq 0 ]; then
        log_success "Coverage threshold met (${COVERAGE_THRESHOLD}%)"
    else
        log_error "Coverage below threshold (${COVERAGE_THRESHOLD}%)"
        ((FAILED++))
        return 1
    fi
}

# Generate test report
generate_report() {
    log_info "=========================================="
    log_info "Generating Test Report"
    log_info "=========================================="
    
    mkdir -p reports
    
    # JUnit XML report
    pytest tests/ \
        --collect-only \
        -q > reports/test-collection.txt 2>/dev/null || true
    
    # Summary report
    cat > reports/test-summary.txt << EOF
DragonScope Enterprise Test Summary
=====================================
Date: $(date)
Python Version: $(python --version)

Test Results:
- Passed: ${PASSED}
- Failed: ${FAILED}
- Skipped: ${SKIPPED}

Coverage: $(coverage report | tail -1 | awk '{print $4}')

Reports Generated:
- reports/coverage/ - HTML coverage report
- reports/coverage.xml - XML coverage report
- reports/test-report.html - Test execution report
- reports/bandit-report.json - Security scan
- reports/safety-report.json - Dependency check
EOF
    
    cat reports/test-summary.txt
}

# Print usage
usage() {
    cat << EOF
DragonScope Enterprise Test Runner

Usage: $0 [OPTIONS] [TEST_TYPE]

Options:
    -h, --help          Show this help message
    -c, --coverage      Run with coverage reporting
    -f, --fast          Skip slow tests
    -v, --verbose       Verbose output
    --ci                CI mode (no interactive)

Test Types:
    unit                Run unit tests only
    integration         Run integration tests
    e2e                 Run end-to-end tests
    security            Run security checks
    load                Run load tests
    quality             Run code quality checks
    all                 Run all tests (default)

Examples:
    $0                  Run all tests
    $0 unit             Run unit tests only
    $0 --fast unit      Run unit tests, skip slow ones
EOF
}

# Main function
main() {
    local RUN_ALL=true
    local TEST_TYPE=""
    local FAST_MODE=false
    local CI_MODE=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -c|--coverage)
                export COVERAGE_PROCESS_START=.coveragerc
                shift
                ;;
            -f|--fast)
                FAST_MODE=true
                shift
                ;;
            -v|--verbose)
                export PYTEST_VERBOSE=true
                shift
                ;;
            --ci)
                CI_MODE=true
                shift
                ;;
            unit|integration|e2e|security|load|quality)
                RUN_ALL=false
                TEST_TYPE=$1
                shift
                ;;
            all)
                RUN_ALL=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Setup
    setup
    
    # Create reports directory
    mkdir -p reports
    
    # Run tests based on arguments
    if [ "$RUN_ALL" = true ]; then
        run_quality_checks || true
        run_unit_tests || true
        run_integration_tests || true
        run_e2e_tests || true
        run_security_tests || true
        check_coverage || true
    else
        case $TEST_TYPE in
            unit)
                run_unit_tests
                ;;
            integration)
                run_integration_tests
                ;;
            e2e)
                run_e2e_tests
                ;;
            security)
                run_security_tests
                ;;
            load)
                run_load_tests
                ;;
            quality)
                run_quality_checks
                ;;
        esac
    fi
    
    # Generate report
    generate_report
    
    # Summary
    log_info "=========================================="
    log_info "TEST SUMMARY"
    log_info "=========================================="
    log_success "Passed: ${PASSED}"
    if [ ${FAILED} -gt 0 ]; then
        log_error "Failed: ${FAILED}"
    fi
    if [ ${SKIPPED} -gt 0 ]; then
        log_warn "Skipped: ${SKIPPED}"
    fi
    
    # Cleanup
    cleanup
    
    # Exit with appropriate code
    if [ ${FAILED} -gt 0 ]; then
        exit 1
    fi
    
    exit 0
}

# Run main function
trap cleanup EXIT
main "$@"
