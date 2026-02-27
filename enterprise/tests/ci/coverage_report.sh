#!/bin/bash
# DragonScope Enterprise - Coverage Report Generator
# Generates detailed coverage reports for CI/CD

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

REPORTS_DIR="reports"
COVERAGE_DIR="${REPORTS_DIR}/coverage"

# Ensure reports directory exists
mkdir -p ${COVERAGE_DIR}

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

# Generate coverage report
generate_coverage() {
    log_info "Generating coverage reports..."
    
    # Combine coverage data if parallel execution
    if [ -f .coverage.* ]; then
        log_info "Combining parallel coverage data..."
        coverage combine
    fi
    
    # Generate HTML report
    log_info "Generating HTML report..."
    coverage html --directory=${COVERAGE_DIR} --skip-covered
    
    # Generate XML report for CI integration
    log_info "Generating XML report..."
    coverage xml -o ${REPORTS_DIR}/coverage.xml
    
    # Generate JSON report
    log_info "Generating JSON report..."
    coverage json -o ${REPORTS_DIR}/coverage.json
    
    # Generate annotated source
    log_info "Generating annotated source..."
    coverage annotate -d ${COVERAGE_DIR}/annotated
    
    log_success "Coverage reports generated"
}

# Analyze coverage
analyze_coverage() {
    log_info "Analyzing coverage..."
    
    # Get coverage percentage
    COVERAGE_PCT=$(coverage report | tail -1 | awk '{print $4}' | sed 's/%//')
    
    log_info "Overall coverage: ${COVERAGE_PCT}%"
    
    # Check coverage by module
    log_info "Coverage by module:"
    coverage report --skip-covered | grep -E "^src/" | while read line; do
        echo "  ${line}"
    done
    
    # Find files with low coverage
    log_info "Files with < 90% coverage:"
    coverage report | awk '$4 < 90 && /^src\// {print "  " $1 ": " $4}'
    
    # Missing lines report
    log_info "Generating missing lines report..."
    coverage report --show-missing > ${REPORTS_DIR}/missing-lines.txt
}

# Generate badge
generate_badge() {
    log_info "Generating coverage badge..."
    
    COVERAGE_PCT=$(coverage report | tail -1 | awk '{print $4}' | sed 's/%//')
    
    # Determine badge color
    if (( $(echo "$COVERAGE_PCT >= 90" | bc -l) )); then
        COLOR="brightgreen"
    elif (( $(echo "$COVERAGE_PCT >= 80" | bc -l) )); then
        COLOR="green"
    elif (( $(echo "$COVERAGE_PCT >= 70" | bc -l) )); then
        COLOR="yellow"
    elif (( $(echo "$COVERAGE_PCT >= 60" | bc -l) )); then
        COLOR="orange"
    else
        COLOR="red"
    fi
    
    # Generate SVG badge (simplified)
    cat > ${REPORTS_DIR}/coverage-badge.svg << EOF
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="a">
    <rect width="100" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#a)">
    <path fill="#555" d="M0 0h60v20H0z"/>
    <path fill="${COLOR}" d="M60 0h40v20H60z"/>
    <path fill="url(#b)" d="M0 0h100v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="30" y="15" fill="#010101" fill-opacity=".3">coverage</text>
    <text x="30" y="14">coverage</text>
    <text x="80" y="15" fill="#010101" fill-opacity=".3">${COVERAGE_PCT}%</text>
    <text x="80" y="14">${COVERAGE_PCT}%</text>
  </g>
</svg>
EOF
    
    log_success "Badge generated: ${REPORTS_DIR}/coverage-badge.svg"
}

# Upload to external service (optional)
upload_coverage() {
    local service=$1
    
    case $service in
        codecov)
            log_info "Uploading to Codecov..."
            if command -v codecov &> /dev/null; then
                codecov -f ${REPORTS_DIR}/coverage.xml
            else
                log_warn "Codecov not installed"
            fi
            ;;
        coveralls)
            log_info "Uploading to Coveralls..."
            if command -v coveralls &> /dev/null; then
                coveralls
            else
                log_warn "Coveralls not installed"
            fi
            ;;
        codacy)
            log_info "Uploading to Codacy..."
            if [ -n "${CODACY_PROJECT_TOKEN:-}" ]; then
                bash <(curl -Ls https://coverage.codacy.com/get.sh) report \
                    -r ${REPORTS_DIR}/coverage.xml
            else
                log_warn "CODACY_PROJECT_TOKEN not set"
            fi
            ;;
        *)
            log_error "Unknown service: $service"
            ;;
    esac
}

# Compare with baseline
compare_baseline() {
    local baseline_file=".coverage.baseline"
    
    if [ ! -f "$baseline_file" ]; then
        log_warn "No baseline coverage file found"
        return
    fi
    
    log_info "Comparing with baseline..."
    
    # Compare coverage percentages
    BASELINE_PCT=$(cat $baseline_file)
    CURRENT_PCT=$(coverage report | tail -1 | awk '{print $4}' | sed 's/%//')
    
    DIFF=$(echo "$CURRENT_PCT - $BASELINE_PCT" | bc)
    
    if (( $(echo "$DIFF >= 0" | bc -l) )); then
        log_success "Coverage improved by ${DIFF}%"
    else
        log_warn "Coverage decreased by ${DIFF}%"
    fi
}

# Main
main() {
    log_info "========================================"
    log_info "DragonScope Coverage Report Generator"
    log_info "========================================"
    
    generate_coverage
    analyze_coverage
    generate_badge
    
    # Upload if specified
    for service in "$@"; do
        upload_coverage $service
    done
    
    # Compare with baseline if exists
    compare_baseline
    
    log_success "Coverage report generation complete!"
    log_info "Reports available in: ${REPORTS_DIR}/"
    log_info "  - ${COVERAGE_DIR}/index.html - HTML report"
    log_info "  - ${REPORTS_DIR}/coverage.xml - XML report"
    log_info "  - ${REPORTS_DIR}/coverage.json - JSON report"
    log_info "  - ${REPORTS_DIR}/missing-lines.txt - Missing lines"
    log_info "  - ${REPORTS_DIR}/coverage-badge.svg - Coverage badge"
}

main "$@"
