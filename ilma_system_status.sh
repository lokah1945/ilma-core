# [COMMON_LIB] Shared functions
source "/root/.hermes/profiles/ilma/bin/ilma_common_lib.sh"

#!/bin/bash
# =============================================================================
# ILMA System Status Check
# =============================================================================
# Health check script for ILMA components
# Verifies Python files compile, data files exist, evidence directory
# Reports component status
#
# Usage: ./ilma_system_status.sh [--verbose] [--json]
# =============================================================================

set -e

ILMA_ROOT="/root/.hermes/profiles/ilma"
ILMA_CACHE="/root/.cache/ilma"
EVIDENCE_DIR="$ILMA_CACHE/evidence"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VERBOSE=false
JSON_OUTPUT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --json|-j)
            JSON_OUTPUT=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--verbose] [--json]"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo "============================================================"
    echo "  ILMA SYSTEM STATUS CHECK"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================================"
}

print_section() {
    echo ""
    echo "────────────────────────────────────────────────────────────"
    echo "  $1"
    echo "────────────────────────────────────────────────────────────"
}

check_status() {
    local status=$1
    local message=$2
    if [ "$status" = "OK" ] || [ "$status" = "0" ]; then
        echo -e "${GREEN}✓${NC} $message"
        return 0
    else
        echo -e "${RED}✗${NC} $message"
        return 1
    fi
}

check_warning() {
    local message=$1
    echo -e "${YELLOW}⚠${NC} $message"
}

info() {
    local message=$1
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}ℹ${NC} $message"
    fi
}

# =============================================================================
# Component Checks
# =============================================================================

check_python_file() {
    local file=$1
    local name=$(basename "$file")
    
    if [ ! -f "$file" ]; then
        check_status "FAIL" "$name: File not found"
        return 1
    fi
    
    # Check Python syntax
    if python3 -m py_compile "$file" 2>/dev/null; then
        check_status "OK" "$name: Python syntax valid"
        return 0
    else
        check_status "FAIL" "$name: Python syntax error"
        return 1
    fi
}

check_data_file() {
    local file=$1
    local name=$(basename "$file")
    
    if [ ! -f "$file" ]; then
        check_status "FAIL" "$name: File not found"
        return 1
    fi
    
    local size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
    if [ "$size" -gt 0 ]; then
        check_status "OK" "$name: exists ($size bytes)"
        return 0
    else
        check_warning "$name: File is empty"
        return 1
    fi
}

check_directory() {
    local dir=$1
    local name=$(basename "$dir")
    local writable=${2:-false}
    
    if [ ! -d "$dir" ]; then
        check_status "FAIL" "$name: Directory not found"
        return 1
    fi
    
    if [ "$writable" = true ]; then
        if [ -w "$dir" ]; then
            check_status "OK" "$name: exists and writable"
            return 0
        else
            check_status "FAIL" "$name: exists but not writable"
            return 1
        fi
    else
        check_status "OK" "$name: exists"
        return 0
    fi
}

count_skills() {
    local skills_dir="$ILMA_ROOT/skills"
    if [ -d "$skills_dir" ]; then
        ls -1d "$skills_dir"/*/ 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

get_python_version() {
    python3 --version 2>&1 | cut -d' ' -f2
}

# =============================================================================
# Main Status Check
# =============================================================================

main() {
    local errors=0
    local warnings=0
    local total_checks=0
    
    print_header
    
    # -----------------------------------------------------------------------------
    # Section: Environment
    # -----------------------------------------------------------------------------
    print_section "ENVIRONMENT"
    
    info "Checking Python installation..."
    total_checks=$((total_checks + 1))
    if command -v python3 &> /dev/null; then
        check_status "OK" "Python: $(get_python_version)"
    else
        check_status "FAIL" "Python3 not found"
        errors=$((errors + 1))
    fi
    
    info "Checking ILMA_ROOT..."
    total_checks=$((total_checks + 1))
    if [ -d "$ILMA_ROOT" ]; then
        check_status "OK" "ILMA_ROOT: $ILMA_ROOT"
    else
        check_status "FAIL" "ILMA_ROOT not found: $ILMA_ROOT"
        errors=$((errors + 1))
    fi
    
    # -----------------------------------------------------------------------------
    # Section: Core Scripts
    # -----------------------------------------------------------------------------
    print_section "CORE SCRIPTS"
    
    core_scripts=(
        "$ILMA_ROOT/ilma_orchestrator.py"
        "$ILMA_ROOT/ilma_router.py"
        "$ILMA_ROOT/ilma_capability_orchestrator.py"
        "$ILMA_ROOT/ilma_unified_system.py"
    )
    
    for script in "${core_scripts[@]}"; do
        total_checks=$((total_checks + 1))
        if ! check_python_file "$script"; then
            errors=$((errors + 1))
        fi
    done
    
    # -----------------------------------------------------------------------------
    # Section: Data Files
    # -----------------------------------------------------------------------------
    print_section "DATA FILES"
    
    data_files=(
        "$ILMA_ROOT/ilma_intent_routing.json"
        "$ILMA_ROOT/channel_directory.json"
        "$ILMA_ROOT/gateway_state.json"
    )
    
    for file in "${data_files[@]}"; do
        total_checks=$((total_checks + 1))
        if ! check_data_file "$file"; then
            warnings=$((warnings + 1))
        fi
    done
    
    # Check ILMA_MODEL_DB.json (expected to be missing)
    total_checks=$((total_checks + 1))
    if [ -f "$ILMA_ROOT/ILMA_MODEL_DB.json" ]; then
        check_status "OK" "ILMA_MODEL_DB.json: exists"
    else
        check_warning "ILMA_MODEL_DB.json: File not found (optional)"
    fi
    
    # -----------------------------------------------------------------------------
    # Section: Directories
    # -----------------------------------------------------------------------------
    print_section "DIRECTORIES"
    
    directories=(
        "$ILMA_ROOT/skills:false"
        "$ILMA_ROOT/logs:false"
        "$ILMA_CACHE:true"
        "$EVIDENCE_DIR:true"
    )
    
    for dir_info in "${directories[@]}"; do
        IFS=':' read -r dir writable <<< "$dir_info"
        total_checks=$((total_checks + 1))
        if ! check_directory "$dir" "$writable"; then
            errors=$((errors + 1))
        fi
    done
    
    # -----------------------------------------------------------------------------
    # Section: Skills
    # -----------------------------------------------------------------------------
    print_section "SKILLS"
    
    total_checks=$((total_checks + 1))
    skill_count=$(count_skills)
    if [ "$skill_count" -gt 0 ]; then
        check_status "OK" "Skill directories: $skill_count found"
    else
        check_status "FAIL" "Skill directories: None found"
        errors=$((errors + 1))
    fi
    
    info "Sample skills:"
    if [ -d "$ILMA_ROOT/skills" ]; then
        ls -1 "$ILMA_ROOT/skills" 2>/dev/null | head -5 | while read -r skill; do
            info "  - $skill"
        done
    fi
    
    # -----------------------------------------------------------------------------
    # Section: Evidence System
    # -----------------------------------------------------------------------------
    print_section "EVIDENCE SYSTEM"
    
    total_checks=$((total_checks + 1))
    if [ -d "$EVIDENCE_DIR" ]; then
        evidence_count=$(ls -1 "$EVIDENCE_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
        check_status "OK" "Evidence files: $evidence_count"
    else
        check_status "FAIL" "Evidence directory not found"
        errors=$((errors + 1))
    fi
    
    # -----------------------------------------------------------------------------
    # Section: Component Import Test
    # -----------------------------------------------------------------------------
    print_section "COMPONENT IMPORTS"
    
    total_checks=$((total_checks + 1))
    echo -n "  Testing imports... "
    if python3 -c "
import sys
sys.path.insert(0, '$ILMA_ROOT')
try:
    from ilma_orchestrator import orchestrate
    from ilma_router import route_to_provider
    from ilma_capability_orchestrator import classify_task
    print('OK')
except ImportError as e:
    print(f'FAIL: {e}')
    sys.exit(1)
" 2>/dev/null; then
        check_status "OK" "All core components importable"
    else
        check_status "FAIL" "Some components failed to import"
        warnings=$((warnings + 1))
    fi
    
    # -----------------------------------------------------------------------------
    # Section: Documentation
    # -----------------------------------------------------------------------------
    print_section "DOCUMENTATION"
    
    docs=(
        "$ILMA_ROOT/ilma_body_map.md"
        "$ILMA_ROOT/ilma_constitution.md"
        "$ILMA_ROOT/ilma_runtime_guide.md"
        "$ILMA_ROOT/ilma_soul.md"
    )
    
    for doc in "${docs[@]}"; do
        total_checks=$((total_checks + 1))
        if ! check_data_file "$doc"; then
            warnings=$((warnings + 1))
        fi
    done
    
    # -----------------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------------
    print_section "SUMMARY"
    
    echo ""
    echo -e "  Total checks: $total_checks"
    echo -e "  ${GREEN}Passed: $((total_checks - errors - warnings))${NC}"
    echo -e "  ${YELLOW}Warnings: $warnings${NC}"
    echo -e "  ${RED}Errors: $errors${NC}"
    
    if [ $errors -eq 0 ]; then
        echo ""
        echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
        echo -e "  System Status: ${GREEN}HEALTHY${NC}"
        echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
        exit 0
    else
        echo ""
        echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
        echo -e "  System Status: ${RED}UNHEALTHY${NC}"
        echo -e "${RED}════════════════════════════════════════════════════════════${NC}"
        exit 1
    fi
}

# Run main
main
