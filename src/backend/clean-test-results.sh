#!/bin/bash

# ============================================================================
# Clean Test Results Script
# Removes test result files while preserving directory structure
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEST_RESULTS_DIR="$SCRIPT_DIR/test-results"

# Help message
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Clean test result files while preserving directory structure.

OPTIONS:
    -h, --help          Show this help message
    -a, --all           Clean all test results (default)
    -c, --coverage      Clean only coverage reports
    -r, --reports       Clean only test reports
    -l, --logs          Clean only logs
    -b, --benchmarks    Clean only benchmarks
    -d, --days DAYS     Clean files older than N days (default: clean all)
    -f, --force         Force cleanup without confirmation

EXAMPLES:
    # Clean all test results
    ./clean-test-results.sh

    # Clean only coverage reports
    ./clean-test-results.sh --coverage

    # Clean files older than 7 days
    ./clean-test-results.sh --days 7

    # Force clean all without confirmation
    ./clean-test-results.sh --all --force

DIRECTORIES:
    - coverage/     Coverage reports (HTML, XML)
    - reports/      Test execution reports (JUnit XML, HTML)
    - logs/         Test execution logs
    - benchmarks/   Performance benchmarks
    - artifacts/    Test artifacts (screenshots, data dumps)

EOF
}

# Parse arguments
CLEAN_TARGET="all"
DAYS=""
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -a|--all)
            CLEAN_TARGET="all"
            shift
            ;;
        -c|--coverage)
            CLEAN_TARGET="coverage"
            shift
            ;;
        -r|--reports)
            CLEAN_TARGET="reports"
            shift
            ;;
        -l|--logs)
            CLEAN_TARGET="logs"
            shift
            ;;
        -b|--benchmarks)
            CLEAN_TARGET="benchmarks"
            shift
            ;;
        -d|--days)
            DAYS="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check if test-results directory exists
if [ ! -d "$TEST_RESULTS_DIR" ]; then
    echo -e "${RED}Error: test-results directory not found at: $TEST_RESULTS_DIR${NC}"
    exit 1
fi

# Function to clean specific directory
clean_directory() {
    local dir="$1"
    local desc="$2"

    if [ ! -d "$TEST_RESULTS_DIR/$dir" ]; then
        echo -e "${YELLOW}Warning: Directory $dir does not exist, skipping...${NC}"
        return
    fi

    if [ -n "$DAYS" ]; then
        echo -e "${YELLOW}Cleaning $desc older than $DAYS days...${NC}"
        find "$TEST_RESULTS_DIR/$dir" -type f -not -name ".gitkeep" -mtime +$DAYS -delete
    else
        echo -e "${YELLOW}Cleaning all $desc...${NC}"
        find "$TEST_RESULTS_DIR/$dir" -type f -not -name ".gitkeep" -not -name "README.md" -delete
    fi

    echo -e "${GREEN}✓ Cleaned $desc${NC}"
}

# Build message based on options
if [ -n "$DAYS" ]; then
    MESSAGE="Clean test results older than $DAYS days"
else
    MESSAGE="Clean all test results"
fi

if [ "$CLEAN_TARGET" != "all" ]; then
    MESSAGE="$MESSAGE ($CLEAN_TARGET only)"
fi

# Confirmation prompt
if [ "$FORCE" = false ]; then
    echo -e "${YELLOW}$MESSAGE${NC}"
    echo -e "${YELLOW}Target: $TEST_RESULTS_DIR${NC}"
    echo ""
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Cleanup cancelled.${NC}"
        exit 0
    fi
fi

echo ""
echo -e "${GREEN}Starting cleanup...${NC}"
echo ""

# Clean based on target
case $CLEAN_TARGET in
    all)
        clean_directory "coverage" "coverage reports"
        clean_directory "reports" "test reports"
        clean_directory "logs" "test logs"
        clean_directory "benchmarks" "benchmarks"
        clean_directory "artifacts" "test artifacts"
        ;;
    coverage)
        clean_directory "coverage" "coverage reports"
        ;;
    reports)
        clean_directory "reports" "test reports"
        ;;
    logs)
        clean_directory "logs" "test logs"
        ;;
    benchmarks)
        clean_directory "benchmarks" "benchmarks"
        ;;
esac

# Summary
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Cleanup complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""

# Show disk usage
if command -v du &> /dev/null; then
    DISK_USAGE=$(du -sh "$TEST_RESULTS_DIR" 2>/dev/null | cut -f1)
    echo -e "Current test-results size: ${YELLOW}$DISK_USAGE${NC}"
fi

# Count remaining files
FILE_COUNT=$(find "$TEST_RESULTS_DIR" -type f -not -name ".gitkeep" -not -name "README.md" | wc -l)
echo -e "Remaining files: ${YELLOW}$FILE_COUNT${NC}"
echo ""

exit 0
