# OCCP v1.0 — Architecture Overview

## System Identity

**OCCP (Open Capability Protocol) v1.0**

Production-ready Skills Management System with cryptographic verification, authority-based governance, and automated self-healing.

**Implementation Status:** ✅ COMPLETE — All 9 phases production-ready

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OCCP v1.0 System                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    Phase 1: Authority & Signing                      │  │
│  │  Ed25519 Keys • 4-Level Hierarchy • Manifest Signing               │  │
│  └───────────────────────────┬─────────────────────────────────────────┘  │
│                              │                                              │
│  ┌───────────────────────────▼─────────────────────────────────────────┐  │
│  │                       Phase 2: Registry                              │  │
│  │  PostgreSQL • Immutable Storage • Signature Verification            │  │
│  └───────────────────────────┬─────────────────────────────────────────┘  │
│                              │                                              │
│  ┌───────────────────────────▼─────────────────────────────────────┐     │  │
│  │                    Phase 3: Executor                             │     │  │
│  │  SkillSandbox • Resource Limits • RED Metrics                   │     │  │
│  └───────────────────────────┬─────────────────────────────────────┘     │  │
│                              │                                             │  │
│  ┌───────────────────────────▼─────────────────────────────────────┐     │  │
│  │                  Phase 4: MCP Integration                        │     │  │
│  │  MCPAdapter • MCPSandbox • Capability Mapping                   │     │  │
│  └───────────────────────────┬─────────────────────────────────────┘     │  │
│                              │                                             │  │
│         ┌────────────────────┼────────────────────┐                        │  │
│         │                    │                    │                        │  │
│  ┌──────▼──────┐      ┌─────▼──────┐    ┌──────▼──────┐                 │  │
│  │  Phase 6:   │      │ Phase 7:   │    │  Phase 5:   │                 │  │
│  │   CI/CD     │      │Observability│    │  Proposals  │                 │  │
│  │ Test→Build  │      │RED Metrics  │    │Read-Only    │                 │  │
│  │→Canary→Prod │      │Aggregation  │    │Analytics    │                 │  │
│  └──────┬──────┘      └─────┬──────┘    └──────┬──────┘                 │  │
│         │                    │                    │                        │  │
│         └────────────────────┼────────────────────┘                        │  │
│                              │                                             │  │
│  ┌───────────────────────────▼─────────────────────────────────────┐     │  │
│  │                   Phase 8: Federation                            │     │  │
│  │  Skill Propagation • Registry Sync • Health Monitoring          │     │  │
│  └───────────────────────────┬─────────────────────────────────────┘     │  │
│                              │                                             │  │
│  ┌───────────────────────────▼─────────────────────────────────────┐     │  │
│  │                Phase 9: Automated Mitigation                     │     │  │
│  │  Cascade Detection • Auto-Remediation • Emergency Protocols     │     │  │
│  └──────────────────────────────────────────────────────────────────┘     │  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase Dependency Graph

```
P1 (Authority) ───────────────────────────────────────────┐
                                                         │
P2 (Registry) ─────────────────────────────────────────┐ │
                                                        ││
P3 (Executor) ──────────────────────────────────────┐  ││
                                                     │  ││
P4 (MCP) ────────────────────────────────────────┐  │  ││
                                                  │  │  ││
P6 (CI/CD) ───────────────────────────────────┐ │  │  ││
  Needs: P1-4                                │ │  │  ││
                                              │ │  │  ││
P7 (Observability) ────────────────────────┐ │ │  │  ││
  Needs: P3-6                             │ │ │  │  ││
                                            │ │ │  │  ││
P5 (Proposals) ──────────────────────────┐ │ │ │  │  ││
  Needs: P3-4                           │ │ │ │  │  ││
                                          │ │ │ │  │  ││
P8 (Federation) ──────────────────────┐ │ │ │ │  │  ││
  Needs: P1-2, 5-7                  │ │ │ │ │  │  ││
                                       │ │ │ │ │  │  ││
P9 (Mitigation) ───────────────────┐ │ │ │ │ │  │  ││
  Needs: P5-8                     │ │ │ │ │ │  │  ││
                                    │ │ │ │ │ │  │  ││
                                    └─┴─┴─┴─┴─┴──┴──┴─┘
                                      ALL PHASES
```

---

## Core Principles

### 1. Cryptographic Verification

**Ed25519 Signatures**
- All manifests signed by Authority
- Non-repudiable authorship
- Tamper-evident artifacts

**Authority Hierarchy (4 Levels)**
- Level 4: Constitutional (root keys)
- Level 3: Strategic (intermediate keys)
- Level 2: Tactical (operational keys)
- Level 1: Operational (execution keys)

### 2. Immutable Storage

**Append-Only Databases**
- All operations logged with timestamps
- No updates to historical records
- Full audit trail

**Artifact Registry**
- PostgreSQL with SQLAlchemy
- SHA256 content addressing
- Version-controlled skill storage

### 3. Read-Only Analytics

**Proposal Agents (Phase 5)**
- Observe system behavior
- Detect patterns (unused capabilities, redundancy)
- Generate proposals (cannot execute)

**Observability (Phase 7)**
- RED metrics collection (Rate, Errors, Duration)
- Multi-source aggregation (local + MCP + federation)
- Dashboards and alerts (no write access)

### 4. Authority Approval Gates

**CI/CD Promotion (Phase 6)**
- Canary deployment requires manual approval
- Auto-rollback on violations
- Manual gate for production promotion

**Mitigation Actions (Phase 9)**
- High-impact actions require Authority approval
- Emergency protocols require Authority declaration
- All approvals audited

### 5. Fail-Fast Testing

**Test Suite (Phase 6)**
1. Manifest validation
2. Contract validation
3. Integration tests
4. E2E tests

**Stop on First Failure**
- Prevents bad artifacts from proceeding
- Saves computation time
- Clear failure indication

### 6. Reproducible Builds

**Deterministic Artifacts (Phase 6)**
- SHA256 hashing
- Fixed mtime (1609459200)
- Sorted file names
- Exclude volatile data (.git, __pycache__)

### 7. Canary Deployment

**Gradual Rollout (Phase 6)**
- 5% → 25% → 50% → 100%
- Health checks between stages
- Auto-promote on health
- Auto-rollback on degradation

### 8. Push Artifacts / Pull Metrics

**Federation Architecture (Phase 8)**
- Push: Skills, proposals, revocations (signed)
- Pull: Metrics, health, replication status (read-only)
- Nodes cannot modify others' data

### 9. Cascade Detection

**Multi-Node Correlation (Phase 9)**
- Temporal patterns (time-based clustering)
- Spatial patterns (location-based)
- Functional patterns (capability-based)
- Cross-node patterns (federation-wide)

### 10. Emergency Protocols

**Graceful Degradation (Phase 9)**
- WARNING: Alert only
- CRITICAL: Isolate affected components
- SEVERE: Emergency shutdown of affected nodes
- Keep non-affected skills running

### 11. Learning from Incidents

**Adaptive Thresholds (Phase 9)**
- Track action effectiveness
- Recovery time analysis
- Severity outcome correlation
- Generate improvement proposals

---

## Component Details

### Phase 1: Authority & Signing

**Purpose:** Cryptographic foundation

**Key Classes:**
- `AuthorityKey` — Ed25519 key generation
- `AuthorityRole` — Role definition (1-4)
- `ManifestSigner` — Sign manifests
- `SignatureVerifier` — Verify signatures

**Operations:**
- Generate keys (role-specific)
- Sign manifests (canonical JSON + Ed25519)
- Verify signatures (before registration)
- Check authority levels (approval gates)

### Phase 2: Registry

**Purpose:** Immutable artifact storage

**Key Classes:**
- `RegistryDatabase` — PostgreSQL manager
- `SkillRegistry` — Skill CRUD operations
- `ArtifactStorage` — Artifact storage
- `ManifestVerifier` — Signature verification

**Operations:**
- Register skill (manifest + signature)
- Retrieve skill (by ID/version)
- List skills (by author/capability)
- Verify manifest (before storage)

### Phase 3: Executor

**Purpose:** Sandboxed skill execution

**Key Classes:**
- `SkillSandbox` — Resource-limited execution
- `SkillRunner` — Execution engine
- `ExecutionContract` — Resource limits
- `ExecutionMetrics` — RED logging

**Operations:**
- Execute skill (sandboxed)
- Enforce contracts (time, memory, tokens)
- Log metrics (rate, errors, duration)
- Violate on contract breach

### Phase 4: MCP Integration

**Purpose:** Model Context Protocol bridge

**Key Classes:**
- `MCPAdapter` — Capability mapping
- `MCPSandbox` — Wrapper for MCP tools
- `MCPCapabilityMapper` — Map capabilities
- `MCPIntegration` — Integration manager

**Operations:**
- Connect to MCP servers
- Map capabilities to skills
- Execute MCP tools (sandboxed)
- Log execution metrics

### Phase 5: Proposal Agents

**Purpose:** Read-only analytics & suggestions

**Key Classes:**
- `MetricsObserver` — RED metrics collector
- `PatternDetector` — Pattern detection
- `ProposalGenerator` — Proposal generation
- `ProposalLearning` — Learn from decisions

**Operations:**
- Observe skill usage (read-only)
- Detect patterns (unused, redundant, hotspots)
- Generate proposals (for Authority)
- Learn from approve/reject (improve accuracy)

**Proposal Types:**
- `REMOVE_CAPABILITY` — Remove unused capability
- `MERGE_SKILLS` — Merge redundant skills
- `TIGHTEN_CONTRACT` — Tighten resource limits
- `RELAX_CONTRACT` — Relax resource limits
- `DEPRECATE_SKILL` — Deprecate obsolete skill

### Phase 6: CI/CD Pipeline

**Purpose:** Automated testing & deployment

**Key Classes:**
- `SkillTester` — Fail-fast test suite
- `SkillBuilder` — Reproducible builder
- `CanaryDeployer` — Gradual rollout
- `RollbackManager` — Auto-rollback
- `SkillPipeline` — Full orchestration

**Operations:**
- Test skills (manifest → contract → integration → E2E)
- Build artifacts (reproducible tarballs)
- Deploy canary (5% → 100%)
- Monitor health (auto-promote/rollback)
- Rollback on violations (automatic)

**Pipeline Stages:**
1. `VALIDATING` — Manifest validation
2. `TESTING` — Running test suite
3. `BUILDING` — Creating artifact
4. `DEPLOYING_CANARY` — Gradual rollout
5. `MONITORING` — Health checks
6. `PROMOTING` — To stable
7. `ROLLING_BACK` — On degradation

### Phase 7: Observability

**Purpose:** Metrics collection & dashboards

**Key Classes:**
- `MetricsCollector` — RED metrics collection
- `MetricsAggregator` — Multi-source aggregation
- `FederatedAggregator` — Federation-wide
- `Dashboard` — Dashboard generation

**Operations:**
- Collect RED metrics (per skill)
- Aggregate metrics (all sources)
- Generate dashboards (graphs, tables)
- Check alerts (threshold-based)

**RED Metrics:**
- **Rate:** Requests per second
- **Errors:** Error rate (errors / total)
- **Duration:** P50, P95, P99 latency

**Alert Types:**
- `HIGH_ERROR_RATE` — Error rate > threshold
- `HIGH_LATENCY` — P95 > threshold
- `LOW_SUCCESS_RATE` — Success rate < threshold
- `VIOLATION_RATE_HIGH` — Violations > threshold

### Phase 8: Federation

**Purpose:** Multi-node skill propagation

**Key Classes:**
- `SkillPropagator` — Skill/proposal propagation
- `RegistrySyncer` — Registry synchronization
- `FederationAggregator` — Metrics aggregation
- `FederationHealthMonitor` — Node health

**Operations:**
- Propagate skills (push to nodes)
- Sync registries (bi-directional)
- Aggregate metrics (pull-only)
- Monitor health (uptime, latency)

**Sync Directions:**
- `PUSH` — Local → Remote
- `PULL` — Remote → Local
- `BIDIRECTIONAL` — Both ways

**Conflict Resolution:**
- `LOCAL_WINS` — Keep local version
- `REMOTE_WINS` — Keep remote version
- `MANUAL` — Require manual resolution

### Phase 9: Automated Mitigation

**Purpose:** Self-healing & incident response

**Key Classes:**
- `CascadeDetector` — Cascade detection
- `AutoRemediator` — Remediation orchestration
- `EmergencyManager` — Emergency protocols
- `MitigationLearner` — Incident learning

**Operations:**
- Detect cascades (multi-node violations)
- Generate remediation plans (with approval)
- Execute remediation (if approved)
- Declare emergency (Authority only)
- Learn from incidents (improve response)

**Cascade Patterns:**
- `TEMPORAL` — Time-based clustering
- `SPATIAL` — Location-based clustering
- `FUNCTIONAL` — Capability-based clustering
- `CROSS_NODE` — Federation-wide

**Remediation Actions:**
- `RESTART_SKILL` — Restart skill
- `ROLLBACK_VERSION` — Rollback to previous version
- `DISABLE_SKILL` — Disable skill
- `ISOLATE_NODE` — Isolate node from federation

**Emergency Levels:**
- `WARNING` — Alert only
- `CRITICAL` — Isolate affected components
- `SEVERE` — Emergency shutdown

---

## Data Models

### Core Entities

**SkillManifest**
```yaml
skill:
  name: str
  version: str
  author: str
  capabilities: List[str]
  contracts: Dict[str, Any]
  signature: str (Ed25519)
```

**ExecutionRecord**
```python
{
  "execution_id": UUID,
  "skill_id": str,
  "version": str,
  "status": "passed" | "failed" | "violated",
  "duration_ms": int,
  "violations": List[str],
  "timestamp": datetime
}
```

**REDMetrics**
```python
{
  "request_rate": float,  # requests/sec
  "error_rate": float,     # 0.0-1.0
  "duration_p50_ms": int,
  "duration_p95_ms": int,
  "duration_p99_ms": int,
  "violation_rate": float  # 0.0-1.0
}
```

**Proposal**
```python
{
  "proposal_id": UUID,
  "proposal_type": "REMOVE_CAPABILITY" | "MERGE_SKILLS" | ...,
  "confidence": float,     # 0.0-1.0
  "rationale": str,
  "changes": List[Dict],
  "status": "pending" | "approved" | "rejected"
}
```

**RemediationPlan**
```python
{
  "plan_id": UUID,
  "incident_id": UUID,
  "actions": List[Dict],
  "severity": "low" | "medium" | "high" | "critical",
  "requires_approval": bool,
  "status": "pending" | "approved" | "executed"
}
```

---

## CLI Tools

### ocp-cli — Core Operations

```bash
ocp-cli registry register --manifest <path> --signature <path>
ocp-cli execute <skill_id> --input '{...}'
```

### ocp-proposals — Proposal Agents

```bash
ocp-proposals detect --hours 24
ocp-proposals generate --min-confidence 0.7
ocp-proposals approve --proposal-id <id> --key <key>
```

### ocp-cicd — CI/CD Pipeline

```bash
ocp-cicd test --manifest <path> --signature <path>
ocp-cicd build --manifest <path> --code <path>
ocp-cicd deploy --artifact <tarball> --canary-percent 5
ocp-cicd monitor --deployment <id>
```

### ocp-obs — Observability

```bash
ocp-obs collect --skill-id <id> --version <ver>
ocp-obs aggregate --time-window-sec 300
ocp-obs dashboard --output <path>
```

### ocp-fed — Federation

```bash
ocp-fed propagate --skill-id <id> --version <ver> --nodes <list>
ocp-fed sync --remote-node-id <id> --direction bidirectional
ocp-fed health --check-interval-sec 60
```

### ocp-mit — Automated Mitigation

```bash
ocp-mit detect --time-window-sec 300
ocp-mit remediate --incident <id>
ocp-mit emergency --level critical --reason <text>
ocp-mit learn --min-incidents 10
```

---

## Startup Sequence

### Full Initialization

```bash
./startup.sh startup
```

**Execution Order:**
1. Phase 1: Authority keys generation
2. Phase 2: Registry initialization
3. Phase 3: Executor setup
4. Phase 4: MCP integration
5. Phase 6: CI/CD pipeline (needs 1-4)
6. Phase 7: Observability (needs 3-6)
7. Phase 5: Proposal agents (needs 3-4)
8. Phase 8: Federation (needs 1-2, 5-7)
9. Phase 9: Mitigation (needs 5-8)

### Verification

```bash
./startup.sh verify
```

Checks all components and reports status.

---

## Technology Stack

- **Cryptography:** Ed25519, SHA256
- **Database:** PostgreSQL + SQLAlchemy
- **Async:** asyncio (Python 3.7+)
- **CLI:** argparse
- **Serialization:** Canonical JSON (sorted keys)
- **Logging:** Color-coded bash output

---

## Statistics

### Implementation Scale

| Metric | Value |
|--------|-------|
| Total Phases | 9 |
| Total Code Lines | ~10,700 |
| Python Modules | 31 |
| CLI Tools | 6 |
| Databases | 6 |
| Architecture Principles | 11 |

### Phase Breakdown

| Phase | Lines | Modules | CLI |
|-------|-------|---------|-----|
| 1. Authority | ~800 | 3 | ocp-cli |
| 2. Registry | ~600 | 4 | (included) |
| 3. Executor | ~900 | 3 | (included) |
| 4. MCP | ~700 | 2 | (included) |
| 5. Proposals | ~2,000 | 6 | ocp-proposals |
| 6. CI/CD | ~2,600 | 7 | ocp-cicd |
| 7. Observability | ~1,600 | 5 | ocp-obs |
| 8. Federation | ~2,100 | 6 | ocp-fed |
| 9. Mitigation | ~2,400 | 7 | ocp-mit |

---

## Production Checklist

### Pre-Deployment

- [ ] Python 3.7+ installed
- [ ] PostgreSQL running
- [ ] Required packages: `ed25519`, `sqlalchemy`, `psycopg2-binary`
- [ ] Authority key generation secure
- [ ] Database backup configured

### Deployment

- [ ] Run `./startup.sh startup`
- [ ] Run `./startup.sh verify`
- [ ] Register test skill
- [ ] Run CI/CD pipeline
- [ ] Check observability dashboard

### Post-Deployment

- [ ] Monitor RED metrics
- [ ] Check federation health
- [ ] Review proposal agent suggestions
- [ ] Test mitigation detection
- [ ] Document emergency procedures

---

## Future Extensions

Potential enhancements for OCCP v2.0:

1. **Skill Marketplace** — Distributed skill exchange
2. **Dynamic Contracts** — Runtime contract adjustment
3. **Multi-Cloud Federation** — Cross-cloud deployment
4. **AI-Based Detection** — ML-powered pattern detection
5. **GraphQL API** — Alternative to REST
6. **WebAssembly Support** — WASM skill execution
7. **Zero-Knowledge Proofs** — Privacy-preserving verification
8. **Tokenomics** — Incentive mechanism for skill sharing

---

**OCCP v1.0 — Production-Ready**

*All 9 phases implemented, tested, and documented*
