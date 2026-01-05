#!/usr/bin/env bash
#
# Pre-PR Validation Script for Siglent-Oscilloscope
# Simple bash version for quick checks
#
# Usage:
#   bash scripts/pre_pr_check.sh
#   bash scripts/pre_pr_check.sh --fast
#   bash scripts/pre_pr_check.sh --fix

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Flags
FAST_MODE=false
AUTO_FIX=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --fast)
            FAST_MODE=true
            ;;
        --fix)
            AUTO_FIX=true
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--fast] [--fix]"
            exit 1
            ;;
    esac
done

# Helper functions
print_header() {
    echo -e "\n${BOLD}${CYAN}=====================================================================${NC}"
    echo -e "${BOLD}${CYAN}$1${NC}"
    echo -e "${BOLD}${CYAN}=====================================================================${NC}\n"
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Track failures
FAILURES=0

run_check() {
    local check_name=$1
    shift

    if "$@"; then
        print_success "$check_name PASSED"
        return 0
    else
        print_error "$check_name FAILED"
        FAILURES=$((FAILURES + 1))
        return 1
    fi
}

# Main checks
print_header "🔍 Pre-PR Validation Check"
echo "Fast mode: $FAST_MODE"
echo "Auto-fix: $AUTO_FIX"
echo ""

# 1. Code Formatting
print_step "Checking code formatting (Black)..."
if [ "$AUTO_FIX" = true ]; then
    black --line-length 100 siglent/ tests/ examples/ && print_success "Code formatted" || FAILURES=$((FAILURES + 1))
else
    black --check --line-length 100 siglent/ tests/ examples/ && print_success "Formatting OK" || {
        print_error "Formatting issues found"
        print_warning "  Run: black --line-length 100 siglent/ tests/ examples/"
        FAILURES=$((FAILURES + 1))
    }
fi

# 2. Import Sorting (optional)
print_step "Checking import sorting (isort)..."
if command -v isort &> /dev/null; then
    if [ "$AUTO_FIX" = true ]; then
        isort --profile black --line-length 100 siglent/ tests/ examples/ && print_success "Imports sorted" || print_warning "isort had issues"
    else
        isort --check-only --profile black --line-length 100 siglent/ tests/ examples/ && print_success "Imports OK" || print_warning "Import order issues (non-critical)"
    fi
else
    print_warning "isort not installed (optional)"
fi

# 3. Linting
print_step "Running linter (flake8)..."
run_check "Linting" flake8 siglent/ --max-line-length=100 --extend-ignore=E203,W503

# 4. Tests
if [ "$FAST_MODE" = false ]; then
    print_step "Running tests..."
    run_check "Tests" pytest tests/ -v

    print_step "Checking coverage..."
    pytest tests/ --cov=siglent --cov-report=term-missing -q && print_success "Coverage OK" || print_warning "Coverage check had issues"
else
    print_step "Running quick tests..."
    run_check "Quick Tests" pytest tests/ -x -q
fi

# 5. Package Build
if [ "$FAST_MODE" = false ]; then
    print_step "Validating package build..."
    python -m build > /dev/null 2>&1 && twine check dist/* > /dev/null 2>&1 && print_success "Build OK" || {
        print_error "Build validation failed"
        FAILURES=$((FAILURES + 1))
    }
fi

# Summary
print_header "📊 Summary"

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}${BOLD}🎉 All checks passed! Ready to create PR.${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}❌ $FAILURES check(s) failed. Please fix issues before creating PR.${NC}"
    echo -e "\n${YELLOW}Tips:${NC}"
    echo "  - Run with --fix to auto-fix formatting issues"
    echo "  - Run with --fast for quicker iteration"
    exit 1
fi
