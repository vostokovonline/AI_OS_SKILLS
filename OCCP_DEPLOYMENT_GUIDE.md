# OCCP v1.0 — Production Deployment Guide

## System Overview

OCCP (Open Capability Protocol) v1.0 is a production-ready Skills Management System with cryptographic verification, authority-based governance, and automated self-healing capabilities.

**Total Implementation:** 9 phases, ~10,700 lines of production code

---

## Quick Start

### Full System Initialization (Recommended)

```bash
# Initialize all 9 phases in dependency order
./startup.sh startup

# Verify all components
./startup.sh verify
```

### Individual Phase Initialization

```bash
./startup.sh phase1  # Authority & Signing
./startup.sh phase2  # Registry
./startup.sh phase3  # Executor
./startup.sh phase4  # MCP Integration
./startup.sh phase5  # Proposal Agents
./startup.sh phase6  # CI/CD Pipeline
./startup.sh phase7  # Observability
./startup.sh phase8  # Federation
./startup.sh phase9  # Automated Mitigation
```

---

## Phase Dependencies

```
Phase 1 (Authority) ─────────────────────────────────┐
                                                      │
Phase 2 (Registry) ─────────────────────────────────┐│
                                                     ││
Phase 3 (Executor) ─────────────────────────────┐   ││
                                                  │  ││
Phase 4 (MCP Integration) ────────────────────┐ │  ││
                                               │ │  ││
Phase 6 (CI/CD) ─────────────────────────────┐ │ │  ││
  Needs: Phase 1-4                          │ │ │  ││
                                             │ │ │  ││
Phase 7 (Observability) ──────────────────┐ │ │ │  ││
  Needs: Phase 3-6                       │ │ │ │  ││
                                          │ │ │ │  ││
Phase 5 (Proposal Agents) ─────────────┐ │ │ │ │  ││
  Needs: Phase 3-4                    │ │ │ │ │  ││
                                       │ │ │ │ │  ││
Phase 8 (Federation) ───────────────┐ │ │ │ │ │  ││
  Needs: Phase 1-2, 5-7            │ │ │ │ │ │  ││
                                    │ │ │ │ │ │  ││
Phase 9 (Automated Mitigation) ───┐ │ │ │ │ │ │  ││
  Needs: Phase 5-8               │ │ │ │ │ │ │  ││
                                  │ │ │ │ │ │ │  ││
                                  └─┴─┴─┴─┴─┴─┴──┴─┘
                                      ALL PHASES
```

---

## Phase Details

### Phase 1: Authority & Signing

**Purpose:** Cryptographic foundation

**Components:**
- Ed25519 key generation (4-level hierarchy)
- Manifest signing/verification
- Authority role management

**Initialization:**
```bash
./startup.sh phase1
```

**Artifacts Created:**
- `ocp/keys/root.json` (Level 4 - Constitutional)
- `ocp/keys/intermediate.json` (Level 3 - Strategic)
- `ocp/keys/operational.json` (Level 1 - Operational)

**Verification:**
```bash
[SUCCESS] ✓ All Authority keys present
```

---

### Phase 2: Registry

**Purpose:** Immutable artifact storage

**Components:**
- PostgreSQL database
- Skill registration CRUD
- Signature verification

**Initialization:**
```bash
./startup.sh phase2
```

**Artifacts Created:**
- `ocp/core/registry/registry.db`

**Verification:**
```bash
[SUCCESS] ✓ Registry database present
```

---

### Phase 3: Executor

**Purpose:** Sandboxed skill execution

**Components:**
- SkillSandbox (resource limits)
- SkillRunner (execution engine)
- RED metrics logging

**Initialization:**
```bash
./startup.sh phase3
```

**Artifacts Created:**
- `ocp/core/executor/sandboxes/` (directory)

**Verification:**
```bash
[SUCCESS] ✓ Executor components present
```

---

### Phase 4: MCP Integration

**Purpose:** Model Context Protocol bridge

**Components:**
- MCPAdapter (capability mapping)
- MCPSandbox (wrapper)

**Initialization:**
```bash
./startup.sh phase4
```

**Artifacts Created:**
- `ocp/integrations/mcp/adapters/` (directory)

**Verification:**
```bash
[SUCCESS] ✓ MCP components present
```

---

### Phase 5: Proposal Agents

**Purpose:** Read-only analytics & optimization suggestions

**Components:**
- MetricsObserver (RED collection)
- PatternDetector (unused capabilities, redundancy)
- ProposalGenerator (suggestions for Authority)
- ProposalLearning (improve from decisions)

**Initialization:**
```bash
./startup.sh phase5
```

**Artifacts Created:**
- `ocp/proposal/proposals.db`
- `ocp/proposal/learning_model.json`

**CLI Usage:**
```bash
ocp-proposals detect --hours 24
ocp-proposals generate --min-confidence 0.7
ocp-proposals history --days 7
```

**Verification:**
```bash
[SUCCESS] ✓ Proposal components present
```

---

### Phase 6: CI/CD Pipeline

**Purpose:** Automated testing & deployment

**Components:**
- SkillTester (fail-fast: manifest → contract → integration → E2E)
- SkillBuilder (reproducible tarballs with SHA256)
- CanaryDeployer (gradual rollout: 5% → 25% → 50% → 100%)
- RollbackManager (auto-rollback on violations)
- SkillPipeline (orchestration)

**Initialization:**
```bash
./startup.sh phase6
```

**Artifacts Created:**
- `ocp/cicd/cicd.db`
- `ocp/artifacts/` (build outputs)

**CLI Usage:**
```bash
# Full pipeline
ocp-cicd pipeline --manifest ./skill.yaml --signature ./sig.yaml --code ./

# Individual stages
ocp-cicd test --manifest ./skill.yaml --signature ./sig.yaml
ocp-cicd build --manifest ./skill.yaml --code ./
ocp-cicd deploy --artifact ./skill-v1.0.0.tar.gz --canary-percent 5
```

**Verification:**
```bash
[SUCCESS] ✓ CI/CD components present
```

---

### Phase 7: Observability

**Purpose:** Metrics collection & dashboards

**Components:**
- MetricsCollector (RED: Rate, Errors, Duration P50/P95/P99)
- MetricsAggregator (multi-source: local + MCP + federation)
- Dashboard (graphs, alerts, recommendations)

**Initialization:**
```bash
./startup.sh phase7
```

**Artifacts Created:**
- `ocp/observability/observability.db`

**CLI Usage:**
```bash
ocp-obs collect --skill-id web_research --version 1.0.0
ocp-obs aggregate --time-window-sec 300
ocp-obs dashboard --output ./dashboard.html
```

**Verification:**
```bash
[SUCCESS] ✓ Observability components present
```

---

### Phase 8: Federation

**Purpose:** Multi-node skill propagation

**Components:**
- SkillPropagator (push skills/proposals to nodes)
- RegistrySyncer (bi-directional sync with conflict resolution)
- FederationAggregator (pull-only metrics aggregation)
- HealthMonitor (node uptime, latency, alerts)

**Initialization:**
```bash
./startup.sh phase8
```

**Artifacts Created:**
- `ocp/federation/federation.db`

**CLI Usage:**
```bash
ocp-fed propagate --skill-id web_research --version 1.0.0 --nodes node1,node2
ocp-fed sync --remote-node-id node1 --direction bidirectional
ocp-fed health --check-interval-sec 60
```

**Verification:**
```bash
[SUCCESS] ✓ Federation components present
```

---

### Phase 9: Automated Mitigation

**Purpose:** Self-healing & incident response

**Components:**
- CascadeDetector (multi-node violation correlation)
- AutoRemediator (remediation plans with Authority approval)
- EmergencyManager (protocols: WARNING → CRITICAL → SEVERE)
- MitigationLearner (adaptive thresholds from incidents)

**Initialization:**
```bash
./startup.sh phase9
```

**Artifacts Created:**
- `ocp/mitigation/mitigation.db`
- `ocp/mitigation/learning_model.json`

**CLI Usage:**
```bash
# Detection
ocp-mit detect --time-window-sec 300

# Remediation (requires Authority approval)
ocp-mit remediate --incident <id> --auto-execute

# Emergency protocols
ocp-mit emergency --level critical --reason "Cascade failure detected" --nodes node1,node2

# Learning
ocp-mit learn --min-incidents 10
```

**Verification:**
```bash
[SUCCESS] ✓ Mitigation components present
```

---

## System Verification

### Full Verification

```bash
./startup.sh verify
```

**Expected Output:**
```
================================================================================
VERIFYING PHASE 1
================================================================================
[INFO] Checking Authority keys...
[SUCCESS] ✓ All Authority keys present

================================================================================
VERIFYING PHASE 2
================================================================================
[INFO] Checking Registry database...
[SUCCESS] ✓ Registry database present

... (all phases)

================================================================================
OCCP v1.0 — ALL SYSTEMS OPERATIONAL
================================================================================
```

### Component Health Checks

```bash
# Authority keys
ls -la ocp/keys/

# Registry
python3 -c "from ocp.core.registry.database import init_registry_db; print('✓ OK')"

# Executor
python3 -c "from ocp.core.executor.sandbox import SkillSandbox; print('✓ OK')"

# Proposal Agents
ocp-proposals detect --hours 1

# CI/CD
ocp-cicd test --manifest ./test.yaml --signature ./test.sig.yaml

# Observability
ocp-obs aggregate --time-window-sec 60

# Federation
ocp-fed health

# Mitigation
ocp-mit detect
```

---

## Production Workflow

### 1. Register a New Skill

```bash
# 1. Create skill manifest
cat > skill_manifest.yaml <<EOF
skill:
  name: web_research
  version: 1.0.0
  author: authority
  capabilities:
    - web_search
    - content_extraction
  contracts:
    max_execution_time_seconds: 30
    max_memory_mb: 256
EOF

# 2. Sign manifest
ocp-cli sign --manifest skill_manifest.yaml --key ocp/keys/operational.json

# 3. Register to registry
ocp-cli registry register --manifest skill_manifest.yaml --signature skill_manifest.sig.yaml
```

### 2. CI/CD Pipeline

```bash
# 1. Test
ocp-cicd test --manifest skill_manifest.yaml --signature skill_manifest.sig.yaml

# 2. Build
ocp-cicd build --manifest skill_manifest.yaml --signature skill_manifest.sig.yaml --code ./

# 3. Deploy canary (5% traffic)
ocp-cicd deploy --artifact skill-1.0.0.tar.gz --canary-percent 5

# 4. Monitor canary (auto-promotes if healthy, auto-rolls back if not)
ocp-cicd monitor --deployment <deployment-id>
```

### 3. Observability

```bash
# Collect RED metrics
ocp-obs collect --skill-id web_research --version 1.0.0

# Aggregate across all sources
ocp-obs aggregate --time-window-sec 300

# Generate dashboard
ocp-obs dashboard --output dashboard.html --include-graphs --include-alerts
```

### 4. Federation

```bash
# Propagate skill to other nodes
ocp-fed propagate --skill-id web_research --version 1.0.0 --nodes node1,node2,node3

# Sync registry with remote node
ocp-fed sync --remote-node-id node1 --direction bidirectional --conflict-resolution local_wins

# Check node health
ocp-fed health --alert-threshold-failures 3
```

### 5. Incident Response

```bash
# Detect cascades
ocp-mit detect --time-window-sec 300

# If cascade detected, declare emergency
ocp-mit emergency --level critical --reason "Cascade failure in web_research" --skills web_research --nodes node1,node2

# Generate remediation plan
ocp-mit remediate --incident <incident-id>

# Approve remediation (Authority only)
ocp-mit approve --plan-id <plan-id> --key operational --rationale "Approved after review"

# Learn from incident
ocp-mit learn --min-incidents 10
```

---

## Architecture Principles

### Enforced Guarantees

✓ **Read-Only Analytics**
  - Proposal Agents cannot modify system state
  - Observability collects metrics without side effects
  - Federation pulls metrics (cannot push modifications)

✓ **Authority Approval Gates**
  - CI/CD promotion requires manual approval
  - High-impact remediation actions require Authority approval
  - Emergency protocols require Authority declaration

✓ **Immutable Audit Trail**
  - All databases use append-only storage
  - All operations logged with timestamps
  - Ed25519 signatures provide non-repudiation

✓ **Fail-Fast Testing**
  - CI/CD stops on first test failure
  - Manifest validation before contract tests
  - Integration tests before E2E tests

✓ **Reproducible Builds**
  - SHA256 hashing for all artifacts
  - Fixed mtime for reproducibility
  - Deterministic tarball creation

✓ **Canary Deployment**
  - Gradual rollout (5% → 25% → 50% → 100%)
  - Auto-promote on health metrics
  - Auto-rollback on degradation

✓ **Push Artifacts / Pull Metrics**
  - Nodes cannot modify others' metrics
  - Federation aggregates read-only
  - Skills/proposals pushed with signatures

✓ **Cascade Detection**
  - Multi-node violation correlation
  - Temporal, spatial, functional patterns
  - Severity scoring based on impact

✓ **Emergency Protocols**
  - Graceful degradation
  - Isolate failed components
  - Keep non-affected skills running

✓ **Learning from Incidents**
  - Track action effectiveness
  - Adaptive threshold adjustment
  - Generate proposals for improvement

---

## Troubleshooting

### Phase 1 Fails: Keys Not Generated

```bash
# Check Python cryptography dependencies
pip3 install ed25519 fastecdsa canonicaljson

# Manually generate keys
python3 -c "
from ocp.core.authority.keys import AuthorityKey, save_key
root = AuthorityKey.generate(role_level=4)
save_key(root, 'ocp/keys/root.json')
print('✓ Root key generated')
"
```

### Phase 2 Fails: Database Not Created

```bash
# Check SQLAlchemy
pip3 install sqlalchemy psycopg2-binary

# Manual initialization
python3 -c "
from ocp.core.registry.database import init_registry_db
db = init_registry_db('ocp/core/registry/registry.db')
print('✓ Database initialized')
"
```

### Phase 6 Fails: CI/CD Integration

```bash
# Verify Phase 1-4 are initialized
./startup.sh verify

# Check Authority key access
ls -la ocp/keys/operational.json

# Verify Registry connection
python3 -c "from ocp.core.registry.crud import list_skills; print(list_skills())"
```

### Phase 9 Fails: Mitigation Dependencies

```bash
# Verify Phase 5-8 are initialized
./startup.sh verify

# Check proposal database
ls -la ocp/proposal/proposals.db

# Check federation database
ls -la ocp/federation/federation.db
```

### General Issues

```bash
# Check all phase status
./startup.sh verify

# View logs
./startup.sh startup 2>&1 | tee startup.log

# Reset and reinitialize (WARNING: destroys all data)
rm -rf ocp/keys/ ocp/*.db
./startup.sh startup
```

---

## System Statistics

### Code Volume (Phases 5-9)

| Phase | Lines of Code | Components |
|-------|---------------|------------|
| Proposal Agents | ~2,000 | 6 modules |
| CI/CD Pipeline | ~2,600 | 7 modules |
| Observability | ~1,600 | 5 modules |
| Federation | ~2,100 | 6 modules |
| Automated Mitigation | ~2,400 | 7 modules |
| **Total** | **~10,700** | **31 modules** |

### Technology Stack

- **Cryptography:** Ed25519 (signing), SHA256 (hashing)
- **Database:** PostgreSQL + SQLAlchemy
- **Async:** asyncio (all CLI tools)
- **CLI:** argparse (all CLIs)
- **Logging:** Color-coded bash output

---

## Next Steps After Deployment

1. **Register First Skill**
   ```bash
   ocp-cli registry register --manifest ./skill.yaml --signature ./sig.yaml
   ```

2. **Run CI/CD Pipeline**
   ```bash
   ocp-cicd pipeline --manifest ./skill.yaml --signature ./sig.yaml --code ./
   ```

3. **Monitor Metrics**
   ```bash
   ocp-obs dashboard --output ./dashboard.html
   ```

4. **Setup Federation**
   ```bash
   ocp-fed sync --remote-node-id node1 --direction bidirectional
   ```

5. **Test Mitigation**
   ```bash
   ocp-mit detect
   ```

---

## Support

For issues or questions:
- Check phase logs: `./startup.sh phaseX`
- Run verification: `./startup.sh verify`
- Review component docs in module headers

---

**OCCP v1.0 — Production-Ready Skills Management System**

*Total Implementation: 9 phases, ~10,700 lines, full audit trail, self-healing capabilities*
