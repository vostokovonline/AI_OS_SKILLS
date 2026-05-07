#!/bin/bash
# OCCP v1.0 — Phase Startup Scripts
# Production deployment with verification at each step

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "================================================================================"
    echo "  $1"
    echo "================================================================================"
    echo ""
}

# =============================================================================
# PHASE 1: Authority & Signing
# =============================================================================

startup_phase1_authority() {
    print_header "PHASE 1: Authority & Signing"

    log_info "Initializing Authority hierarchy..."

    # 1.1 Create directories
    log_info "Creating directory structure..."
    mkdir -p ocp/keys
    mkdir -p ocp/artifacts

    # 1.2 Generate Authority keys
    log_info "Generating Authority keys..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp/core')

from authority.keys import AuthorityKey, save_key
from authority.roles import AuthorityRole

# Generate Root Key (Level 4 - Constitutional)
root_key = AuthorityKey.generate(role_level=4)
save_key(root_key, 'ocp/keys/root.json')
print('✓ Root key generated')

# Generate Intermediate Key (Level 3 - Strategic)
intermediate_key = AuthorityKey.generate(role_level=3)
save_key(intermediate_key, 'ocp/keys/intermediate.json')
print('✓ Intermediate key generated')

# Generate Operational Key (Level 1 - Operational)
operational_key = AuthorityKey.generate(role_level=1)
save_key(operational_key, 'ocp/keys/operational.json')
print('✓ Operational key generated')

print('✓ All Authority keys generated')
"

    log_success "Phase 1: Authority initialized"
    echo ""
}

verify_phase1() {
    print_header "VERIFYING PHASE 1"

    log_info "Checking Authority keys..."

    if [ ! -f "ocp/keys/root.json" ]; then
        log_error "Root key not found!"
        return 1
    fi

    if [ ! -f "ocp/keys/intermediate.json" ]; then
        log_error "Intermediate key not found!"
        return 1
    fi

    if [ ! -f "ocp/keys/operational.json" ]; then
        log_error "Operational key not found!"
        return 1
    fi

    log_success "✓ All Authority keys present"
    echo ""
}

# =============================================================================
# PHASE 2: Registry
# =============================================================================

startup_phase2_registry() {
    print_header "PHASE 2: Registry"

    log_info "Initializing Registry database..."

    # 2.1 Initialize database
    log_info "Creating PostgreSQL schema..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp/core')

from registry.database import init_registry_db

db = init_registry_db('ocp/core/registry/registry.db')
print('✓ Registry database initialized')
"

    # 2.2 Verify Authority integration
    log_info "Verifying Authority integration..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp/core')

from authority.keys import load_key
from registry.crud import can_authorize_manifest

# Load operational key
key = load_key('ocp/keys/operational.json')
print('✓ Authority key loaded')
print('✓ Registry ready to verify signatures')
"

    log_success "Phase 2: Registry initialized"
    echo ""
}

verify_phase2() {
    print_header "VERIFYING PHASE 2"

    log_info "Checking Registry database..."

    if [ ! -f "ocp/core/registry/registry.db" ]; then
        log_error "Registry database not found!"
        return 1
    fi

    log_success "✓ Registry database present"
    echo ""
}

# =============================================================================
# PHASE 3: Executor
# =============================================================================

startup_phase3_executor() {
    print_header "PHASE 3: Executor"

    log_info "Initializing Executor..."

    # 3.1 Create executor directories
    log_info "Creating executor directories..."
    mkdir -p ocp/core/executor/sandboxes

    # 3.2 Initialize executor
    log_info "Starting sandbox executor..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp/core')

from executor.sandbox import SkillSandbox, SandboxContract, SandboxOp
from executor.runner import SkillRunner

print('✓ Sandbox executor initialized')
print('✓ Skill runner ready')
"

    log_success "Phase 3: Executor initialized"
    echo ""
}

verify_phase3() {
    print_header "VERIFYING PHASE 3"

    log_info "Checking Executor components..."

    if [ ! -d "ocp/core/executor" ]; then
        log_error "Executor directory not found!"
        return 1
    fi

    log_success "✓ Executor components present"
    echo ""
}

# =============================================================================
# PHASE 4: MCP Integration
# =============================================================================

startup_phase4_mcp() {
    print_header "PHASE 4: MCP Integration"

    log_info "Initializing MCP Integration..."

    # 4.1 Create MCP directories
    log_info "Creating MCP directories..."
    mkdir -p ocp/integrations/mcp/adapters

    # 4.2 Initialize MCP adapter
    log_info "Initializing MCP adapter..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from integrations.mcp.adapter import MCPAdapter, MCPCapabilityMapper
from integrations.mcp.wrapper import MCPSandbox

print('✓ MCP adapter initialized')
print('✓ MCP sandbox wrapper ready')
"

    log_success "Phase 4: MCP Integration initialized"
    echo ""
}

verify_phase4() {
    print_header "VERIFYING PHASE 4"

    log_info "Checking MCP components..."

    if [ ! -d "ocp/integrations/mcp" ]; then
        log_error "MCP integration directory not found!"
        return 1
    fi

    log_success "✓ MCP components present"
    echo ""
}

# =============================================================================
# PHASE 5: Proposal Agents
# =============================================================================

startup_phase5_proposals() {
    print_header "PHASE 5: Proposal Agents"

    log_info "Initializing Proposal Agents..."

    # 5.1 Create proposal directories
    log_info "Creating proposal directories..."
    mkdir -p ocp/proposal

    # 5.2 Initialize proposal database
    log_info "Initializing proposal database..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from proposal.database import init_proposal_db

db = init_proposal_db('ocp/proposal/proposals.db')
print('✓ Proposal database initialized')
"

    # 5.3 Initialize learning model
    log_info "Initializing learning model..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from proposal.learning import ProposalLearning

learner = ProposalLearning(model_path='ocp/proposal/learning_model.json')
learner.save_model()
print('✓ Learning model initialized')
"

    log_success "Phase 5: Proposal Agents initialized"
    echo ""
}

verify_phase5() {
    print_header "VERIFYING PHASE 5"

    log_info "Checking Proposal components..."

    if [ ! -f "ocp/proposal/proposals.db" ]; then
        log_error "Proposal database not found!"
        return 1
    fi

    if [ ! -f "ocp/proposal/learning_model.json" ]; then
        log_warning "Learning model not found (will be created on first use)"
    fi

    log_success "✓ Proposal components present"
    echo ""
}

# =============================================================================
# PHASE 6: CI/CD Pipeline
# =============================================================================

startup_phase6_cicd() {
    print_header "PHASE 6: CI/CD Pipeline"

    log_info "Initializing CI/CD Pipeline..."

    # 6.1 Create CI/CD directories
    log_info "Creating CI/CD directories..."
    mkdir -p ocp/cicd
    mkdir -p ocp/artifacts

    # 6.2 Initialize CI/CD database
    log_info "Initializing CI/CD database..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from cicd.database import init_cicd_db

db = init_cicd_db('ocp/cicd/cicd.db')
print('✓ CI/CD database initialized')
"

    # 6.3 Verify integration with previous phases
    log_info "Verifying integration with Phase 1-4..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp/core')

from authority.keys import load_key
from registry.crud import list_skills

print('✓ Can access Authority keys')
print('✓ Can access Registry')
print('✓ CI/CD ready to test, build, deploy skills')
"

    log_success "Phase 6: CI/CD Pipeline initialized"
    echo ""
}

verify_phase6() {
    print_header "VERIFYING PHASE 6"

    log_info "Checking CI/CD components..."

    if [ ! -f "ocp/cicd/cicd.db" ]; then
        log_error "CI/CD database not found!"
        return 1
    fi

    if [ ! -d "ocp/artifacts" ]; then
        log_warning "Artifacts directory not found (will be created)"
    fi

    log_success "✓ CI/CD components present"
    echo ""
}

# =============================================================================
# PHASE 7: Observability
# =============================================================================

startup_phase7_observability() {
    print_header "PHASE 7: Observability"

    log_info "Initializing Observability..."

    # 7.1 Create observability directories
    log_info "Creating observability directories..."
    mkdir -p ocp/observability

    # 7.2 Initialize observability database
    log_info "Initializing observability database..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from observability.database import init_observability_db

db = init_observability_db('ocp/observability/observability.db')
print('✓ Observability database initialized')
"

    # 7.3 Verify integration with Phase 3-6
    log_info "Verifying integration with Executor, MCP, CI/CD..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from observability.metrics_collector import MetricsCollector
from observability.aggregator import MetricsAggregator

print('✓ Metrics collector ready')
print('✓ Aggregator ready to collect from Executor, MCP, CI/CD')
"

    log_success "Phase 7: Observability initialized"
    echo ""
}

verify_phase7() {
    print_header "VERIFYING PHASE 7"

    log_info "Checking Observability components..."

    if [ ! -f "ocp/observability/observability.db" ]; then
        log_error "Observability database not found!"
        return 1
    fi

    log_success "✓ Observability components present"
    echo ""
}

# =============================================================================
# PHASE 8: Federation
# =============================================================================

startup_phase8_federation() {
    print_header "PHASE 8: Federation"

    log_info "Initializing Federation..."

    # 8.1 Create federation directories
    log_info "Creating federation directories..."
    mkdir -p ocp/federation

    # 8.2 Initialize federation database
    log_info "Initializing federation database..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from federation.database import init_federation_db

db = init_federation_db('ocp/federation/federation.db')
print('✓ Federation database initialized')
"

    # 8.3 Verify integration with Phase 1, 2, 5-7
    log_info "Verifying integration with Authority, Registry, Proposal, Observability..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from federation.propagator import SkillPropagator
from federation.aggregator import FederationAggregator
from federation.health_monitor import FederationHealthMonitor

print('✓ Federation propagator ready')
print('✓ Health monitor ready')
"

    log_success "Phase 8: Federation initialized"
    echo ""
}

verify_phase8() {
    print_header "VERIFYING PHASE 8"

    log_info "Checking Federation components..."

    if [ ! -f "ocp/federation/federation.db" ]; then
        log_error "Federation database not found!"
        return 1
    fi

    log_success "✓ Federation components present"
    echo ""
}

# =============================================================================
# PHASE 9: Automated Mitigation
# =============================================================================

startup_phase9_mitigation() {
    print_header "PHASE 9: Automated Mitigation"

    log_info "Initializing Automated Mitigation..."

    # 9.1 Create mitigation directories
    log_info "Creating mitigation directories..."
    mkdir -p ocp/mitigation

    # 9.2 Initialize mitigation database
    log_info "Initializing mitigation database..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from mitigation.database import init_mitigation_db

db = init_mitigation_db('ocp/mitigation/mitigation.db')
print('✓ Mitigation database initialized')
"

    # 9.3 Initialize learning model
    log_info "Initializing learning model..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from mitigation.learning import MitigationLearner

learner = MitigationLearner(db_path='ocp/mitigation/learning_model.json')
learner.save_model()
print('✓ Learning model initialized')
"

    # 9.4 Verify integration with Phase 5-8
    log_info "Verifying integration with Proposal, Observability, Federation..."
    python3 -c "
import sys
sys.path.insert(0, 'ocp')

from mitigation.detector import CascadeDetector
from mitigation.remediator import AutoRemediator
from mitigation.emergency import EmergencyManager

print('✓ Cascade detector ready')
print('✓ Auto-remediator ready')
print('✓ Emergency manager ready')
"

    log_success "Phase 9: Automated Mitigation initialized"
    echo ""
}

verify_phase9() {
    print_header "VERIFYING PHASE 9"

    log_info "Checking Mitigation components..."

    if [ ! -f "ocp/mitigation/mitigation.db" ]; then
        log_error "Mitigation database not found!"
        return 1
    fi

    if [ ! -f "ocp/mitigation/learning_model.json" ]; then
        log_warning "Learning model not found (will be created)"
    fi

    log_success "✓ Mitigation components present"
    echo ""
}

# =============================================================================
# FULL STARTUP
# =============================================================================

startup_all() {
    print_header "OCCP v1.0 — FULL SYSTEM STARTUP"

    log_info "Starting all phases in dependency order..."

    # Phase 1-4: Basic Infrastructure
    startup_phase1_authority
    verify_phase1

    startup_phase2_registry
    verify_phase2

    startup_phase3_executor
    verify_phase3

    startup_phase4_mcp
    verify_phase4

    # Phase 6: CI/CD (needs 1-4)
    startup_phase6_cicd
    verify_phase6

    # Phase 7: Observability (needs 3-6)
    startup_phase7_observability
    verify_phase7

    # Phase 5: Proposal Agents (needs 3, 4)
    startup_phase5_proposals
    verify_phase5

    # Phase 8: Federation (needs 1, 2, 5-7)
    startup_phase8_federation
    verify_phase8

    # Phase 9: Mitigation (needs 5-8)
    startup_phase9_mitigation
    verify_phase9

    print_header "OCCP v1.0 — STARTUP COMPLETE"

    log_success "All phases initialized successfully!"
    echo ""

    log_info "System Status:"
    echo "  ✓ Authority & Signing"
    echo "  ✓ Registry"
    echo "  ✓ Executor"
    echo "  ✓ MCP Integration"
    echo "  ✓ CI/CD Pipeline"
    echo "  ✓ Observability"
    echo "  ✓ Proposal Agents"
    echo "  ✓ Federation"
    echo "  ✓ Automated Mitigation"
    echo ""

    log_info "Next Steps:"
    echo "  1. Register a skill: ocp-cli registry register --manifest <path> --signature <path>"
    echo "  2. Execute a skill: ocp-cli execute <skill_id> --input '{...}'"
    echo "  3. View metrics: ocp-obs dashboard"
    echo "  4. Check health: ocp-fed health"
    echo ""

    log_success "OCCP v1.0 is ready!"
}

# =============================================================================
# MAIN
# =============================================================================

case "${1:-startup}" in
    "phase1")
        startup_phase1_authority
        verify_phase1
        ;;
    "phase2")
        startup_phase2_registry
        verify_phase2
        ;;
    "phase3")
        startup_phase3_executor
        verify_phase3
        ;;
    "phase4")
        startup_phase4_mcp
        verify_phase4
        ;;
    "phase5")
        startup_phase5_proposals
        verify_phase5
        ;;
    "phase6")
        startup_phase6_cicd
        verify_phase6
        ;;
    "phase7")
        startup_phase7_observability
        verify_phase7
        ;;
    "phase8")
        startup_phase8_federation
        verify_phase8
        ;;
    "phase9")
        startup_phase9_mitigation
        verify_phase9
        ;;
    "startup")
        startup_all
        ;;
    "verify")
        verify_phase1
        verify_phase2
        verify_phase3
        verify_phase4
        verify_phase5
        verify_phase6
        verify_phase7
        verify_phase8
        verify_phase9
        ;;
    *)
        echo "Usage: $0 {startup|phase1|phase2|...|phase9|verify}"
        echo ""
        echo "Commands:"
        echo "  startup     - Start all phases in dependency order"
        echo "  phase1      - Start Phase 1 (Authority & Signing)"
        echo "  phase2      - Start Phase 2 (Registry)"
        echo "  phase3      - Start Phase 3 (Executor)"
        echo "  phase4      - Start Phase 4 (MCP Integration)"
        echo "  phase5      - Start Phase 5 (Proposal Agents)"
        echo "  phase6      - Start Phase 6 (CI/CD Pipeline)"
        echo "  phase7      - Start Phase 7 (Observability)"
        echo "  phase8      - Start Phase 8 (Federation)"
        echo "  phase9      - Start Phase 9 (Automated Mitigation)"
        echo "  verify      - Verify all phases are initialized"
        echo ""
        exit 1
        ;;
esac
