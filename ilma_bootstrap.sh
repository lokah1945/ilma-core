# [COMMON_LIB] Shared functions
source "/root/.hermes/profiles/ilma/bin/ilma_common_lib.sh"

#!/bin/bash
# =============================================================================
# ILMA Bootstrap Script
# =============================================================================
# Quick startup script for ILMA
# Verifies environment, loads configuration, shows system status
#
# Usage: ./ilma_bootstrap.sh [--fast] [--status-only]
# =============================================================================

set -e

ILMA_ROOT="/root/.hermes/profiles/ilma"
ILMA_CACHE="/root/.cache/ilma"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

FAST_MODE=false
STATUS_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fast|-f)
            FAST_MODE=true
            shift
            ;;
        --status-only|-s)
            STATUS_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--fast] [--status-only]"
            echo ""
            echo "Options:"
            echo "  --fast         Skip detailed checks"
            echo "  --status-only  Show status and exit"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# =============================================================================
# Banner
# =============================================================================

show_banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}║   ${NC}██████╗ ███████╗███████╗███████╗███████╗     █████╗       ${CYAN}║${NC}"
    echo -e "${CYAN}║   ${NC}██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝    ██╔══██╗      ${CYAN}║${NC}"
    echo -e "${CYAN}║   ${NC}██████╔╝█████╗  ███████╗█████╗  ███████╗    ███████║      ${CYAN}║${NC}"
    echo -e "${CYAN}║   ${NC}██╔══██╗██╔══╝  ╚════██║██╔══╝  ╚════██║    ██╔══██║      ${CYAN}║${NC}"
    echo -e "${CYAN}║   ${NC}██║  ██║███████╗███████║███████╗███████║    ██║  ██║      ${CYAN}║${NC}"
    echo -e "${CYAN}║   ${NC}╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚══════╝    ╚═╝  ╚═╝      ${CYAN}║${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}║   ${NC}Infinite Language Memory Agent - Unified System         ${CYAN}║${NC}"
    echo -e "${CYAN}║   ${NC}Version 1.0.0 | Build 2026-05-08                        ${CYAN}║${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# =============================================================================
# Environment Verification
# =============================================================================

verify_environment() {
    echo -e "${YELLOW}▶ Verifying environment...${NC}"
    
    local env_ok=true
    
    # Check Python
    if command -v python3 &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} Python: $(python3 --version 2>&1)"
    else
        echo -e "  ${RED}✗${NC} Python3 not found"
        env_ok=false
    fi
    
    # Check ILMA_ROOT
    if [ -d "$ILMA_ROOT" ]; then
        echo -e "  ${GREEN}✓${NC} ILMA_ROOT: $ILMA_ROOT"
    else
        echo -e "  ${RED}✗${NC} ILMA_ROOT not found: $ILMA_ROOT"
        env_ok=false
    fi
    
    # Check required directories
    for dir in "$ILMA_ROOT/skills" "$ILMA_CACHE"; do
        if [ -d "$dir" ]; then
            echo -e "  ${GREEN}✓${NC} Directory: $(basename $dir)"
        else
            echo -e "  ${RED}✗${NC} Directory missing: $dir"
            env_ok=false
        fi
    done
    
    if [ "$env_ok" = false ]; then
        echo ""
        echo -e "${RED}Environment verification failed!${NC}"
        exit 1
    fi
    
    echo -e "  ${GREEN}Environment OK${NC}"
}

# =============================================================================
# Configuration Loading
# =============================================================================

load_configuration() {
    echo ""
    echo -e "${YELLOW}▶ Loading configuration...${NC}"
    
    # Check for config files
    if [ -f "$ILMA_ROOT/config.yaml" ]; then
        echo -e "  ${GREEN}✓${NC} config.yaml found"
    else
        echo -e "  ${YELLOW}⚠${NC} config.yaml not found (optional)"
    fi
    
    # Check for env file
    if [ -f "$ILMA_ROOT/.env" ]; then
        echo -e "  ${GREEN}✓${NC} .env file found"
    else
        echo -e "  ${YELLOW}⚠${NC} .env file not found (optional)"
    fi
    
    # Set Python path
    export PYTHONPATH="$ILMA_ROOT:$PYTHONPATH"
    echo -e "  ${GREEN}✓${NC} PYTHONPATH configured"
    
    echo -e "  ${GREEN}Configuration loaded${NC}"
}

# =============================================================================
# Component Initialization
# =============================================================================

init_components() {
    echo ""
    echo -e "${YELLOW}▶ Initializing components...${NC}"
    
    python3 -c "
import sys
sys.path.insert(0, '$ILMA_ROOT')

components = []
missing = []

try:
    from ilma_orchestrator import ILMAOrchestrator
    components.append('orchestrator')
except ImportError:
    missing.append('orchestrator')

try:
    from ilma_router import route_to_provider
    components.append('router')
except ImportError:
    missing.append('router')

try:
    from ilma_capability_orchestrator import classify_task
    components.append('capability')
except ImportError:
    missing.append('capability')

print(f'  Available: {len(components)}/3')
for c in components:
    print(f'    - {c}: OK')
if missing:
    print(f'  Missing: {len(missing)}')
    for m in missing:
        print(f'    - {m}: NOT AVAILABLE')
"
    
    echo -e "  ${GREEN}Component initialization complete${NC}"
}

# =============================================================================
# Show System Status
# =============================================================================

show_status() {
    echo ""
    echo -e "${YELLOW}▶ System Status${NC}"
    echo "────────────────────────────────────────────────────────────"
    
    # Skill count
    skill_count=$(ls -1d "$ILMA_ROOT/skills"/*/ 2>/dev/null | wc -l | tr -d ' ')
    echo "  Skills:        $skill_count directories"
    
    # Evidence count
    evidence_count=$(ls -1 "$ILMA_CACHE/evidence"/*.json 2>/dev/null | wc -l | tr -d ' ')
    echo "  Evidence:      $evidence_count files"
    
    # Core files
    core_files=(
        "ilma_orchestrator.py"
        "ilma_router.py"
        "ilma_capability_orchestrator.py"
        "ilma_unified_system.py"
    )
    echo "  Core Scripts:"
    for f in "${core_files[@]}"; do
        if [ -f "$ILMA_ROOT/$f" ]; then
            echo -e "    ${GREEN}✓${NC} $f"
        else
            echo -e "    ${RED}✗${NC} $f"
        fi
    done
    
    echo "────────────────────────────────────────────────────────────"
}

# =============================================================================
# Ready Message
# =============================================================================

show_ready() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║   ${NC}ILMA is ready! Use the unified system to process input.    ${GREEN}║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Available commands:"
    echo "  python3 ilma_unified_system.py --status    Show system status"
    echo "  python3 ilma_unified_system.py --health    Check provider health"
    echo "  python3 ilma_unified_system.py --evidence  Show evidence statistics"
    echo "  python3 ilma_unified_system.py --learn     Show learning analysis"
    echo ""
    echo "Quick test:"
    echo "  python3 ilma_unified_system.py -i 'Hello ILMA'"
    echo ""
}

# =============================================================================
# Main
# =============================================================================

main() {
    show_banner
    
    if [ "$STATUS_ONLY" = true ]; then
        verify_environment
        show_status
        exit 0
    fi
    
    verify_environment
    load_configuration
    
    if [ "$FAST_MODE" = false ]; then
        init_components
    fi
    
    show_status
    show_ready
}

main
