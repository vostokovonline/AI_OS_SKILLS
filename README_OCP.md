# OCCP v1.0 — Open Capability Protocol

**Production-ready Skills Management System** with cryptographic verification, authority-based governance, and automated self-healing.

---

## Quick Start

```bash
# 1. Initialize full system (all 9 phases)
./startup.sh startup

# 2. Verify all components
./startup.sh verify

# 3. Register your first skill
ocp-cli registry register --manifest ./skill.yaml --signature ./sig.yaml
```

---

## System Status

✅ **Production Ready** — All 9 phases implemented (~13,700 lines)

| Phase | Component | Status |
|-------|-----------|--------|
| 1 | Authority & Signing | ✅ |
| 2 | Registry | ✅ |
| 3 | Executor | ✅ |
| 4 | MCP Integration | ✅ |
| 5 | Proposal Agents | ✅ |
| 6 | CI/CD Pipeline | ✅ |
| 7 | Observability | ✅ |
| 8 | Federation | ✅ |
| 9 | Automated Mitigation | ✅ |

---

## Architecture

```
Phase 1 (Authority) ──────────────────────────────────┐
                                                      │
Phase 2 (Registry) ─────────────────────────────────┐ │
                                                     ││
Phase 3 (Executor) ──────────────────────────────┐  ││
                                                  │  ││
Phase 4 (MCP Integration) ────────────────────┐ │  ││
                                               │ │  ││
Phase 6 (CI/CD) ──────────────────────────┐   │ │  ││
  Needs: Phase 1-4                        │   │ │  ││
                                           │   │ │  ││
Phase 7 (Observability) ───────────────┐ │   │ │  ││
  Needs: Phase 3-6                     │ │   │ │  ││
                                        │ │   │ │  ││
Phase 5 (Proposals) ─────────────────┐ │ │   │ │  ││
  Needs: Phase 3-4                   │ │ │   │ │  ││
                                      │ │ │   │ │  ││
Phase 8 (Federation) ──────────────┐ │ │ │   │ │  ││
  Needs: Phase 1-2, 5-7           │ │ │ │   │ │  ││
                                    │ │ │ │   │ │  ││
Phase 9 (Mitigation) ────────────┐ │ │ │ │   │ │  ││
  Needs: Phase 5-8              │ │ │ │ │   │ │  ││
                                 │ │ │ │ │   │ │  ││
                                 └─┴─┴─┴─┴───┴─┴──┴─┘
                                      COMPLETE
```

---

## Core Principles

1. **Cryptographic Verification** — Ed25519 signatures for all manifests
2. **Immutable Storage** — Append-only databases with full audit trail
3. **Read-Only Analytics** — Observers cannot modify system state
4. **Authority Approval Gates** — Manual approval for high-impact actions
5. **Fail-Fast Testing** — Stop on first test failure
6. **Reproducible Builds** — SHA256 hashing, deterministic artifacts
7. **Canary Deployment** — Gradual rollout with auto-rollback
8. **Push Artifacts / Pull Metrics** — Federation architecture
9. **Cascade Detection** — Multi-node violation correlation
10. **Emergency Protocols** — Graceful degradation
11. **Learning from Incidents** — Adaptive thresholds

---

## CLI Tools

### Core Operations
```bash
ocp-cli registry register --manifest <path> --signature <path>
ocp-cli execute <skill_id> --input '{...}'
```

### Proposal Agents
```bash
ocp-proposals detect --hours 24
ocp-proposals generate --min-confidence 0.7
ocp-proposals approve --proposal-id <id> --key <key>
```

### CI/CD Pipeline
```bash
ocp-cicd test --manifest <path> --signature <path>
ocp-cicd build --manifest <path> --code <path>
ocp-cicd deploy --artifact <tarball> --canary-percent 5
ocp-cicd pipeline --manifest <path> --signature <path> --code <path>
```

### Observability
```bash
ocp-obs collect --skill-id <id> --version <ver>
ocp-obs aggregate --time-window-sec 300
ocp-obs dashboard --output <path>
```

### Federation
```bash
ocp-fed propagate --skill-id <id> --version <ver> --nodes <list>
ocp-fed sync --remote-node-id <id> --direction bidirectional
ocp-fed health --check-interval-sec 60
```

### Automated Mitigation
```bash
ocp-mit detect --time-window-sec 300
ocp-mit remediate --incident <id>
ocp-mit emergency --level critical --reason <text>
ocp-mit learn --min-incidents 10
```

---

## Startup Commands

### Full System Initialization
```bash
./startup.sh startup
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

### System Verification
```bash
./startup.sh verify
```

---

## Documentation

- **[OCCP_DEPLOYMENT_GUIDE.md](./OCCP_DEPLOYMENT_GUIDE.md)** — Comprehensive deployment guide
  - Quick start
  - Phase details (1-9)
  - Production workflow
  - Troubleshooting
  - CLI usage examples

- **[OCCP_ARCHITECTURE.md](./OCCP_ARCHITECTURE.md)** — Architecture overview
  - System architecture diagram
  - Dependency graph
  - Core principles (11)
  - Component details
  - Data models
  - Technology stack

- **[OCCP_FILE_INDEX.md](./OCCP_FILE_INDEX.md)** — Complete file index
  - All 52 files
  - Directory structure
  - CLI tools reference
  - Quick commands

---

## Phase Overview

### Phase 1: Authority & Signing
- Ed25519 key generation (4-level hierarchy)
- Manifest signing/verification
- Authority role management

### Phase 2: Registry
- PostgreSQL database
- Immutable artifact storage
- Skill registration CRUD

### Phase 3: Executor
- Sandboxed skill execution
- Resource limit enforcement
- RED metrics logging

### Phase 4: MCP Integration
- Model Context Protocol bridge
- Capability mapping
- MCP tool execution

### Phase 5: Proposal Agents
- Read-only metrics collection
- Pattern detection (unused, redundant, hotspots)
- Proposal generation
- Learning from decisions

### Phase 6: CI/CD Pipeline
- Fail-fast testing (manifest → contract → integration → E2E)
- Reproducible builds (SHA256, fixed mtime)
- Canary deployment (5% → 100%)
- Auto-rollback on violations
- Full pipeline orchestration

### Phase 7: Observability
- RED metrics collection (Rate, Errors, Duration P50/P95/P99)
- Multi-source aggregation (local + MCP + federation)
- Dashboard generation (graphs, tables, alerts)
- Health monitoring

### Phase 8: Federation
- Skill/proposal propagation
- Registry synchronization (bi-directional)
- Conflict resolution
- Node health monitoring
- Pull-only metrics aggregation

### Phase 9: Automated Mitigation
- Cascade detection (temporal, spatial, functional, cross-node)
- Auto-remediation with Authority approval
- Emergency protocols (WARNING, CRITICAL, SEVERE)
- Learning from incidents
- Adaptive thresholds

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

| Metric | Value |
|--------|-------|
| Total Phases | 9 |
| Code Lines | ~13,700 |
| Python Modules | 52 |
| CLI Tools | 6 |
| Databases | 6 |
| Architectural Principles | 11 |

---

## Production Workflow

### 1. Create Skill Manifest
```yaml
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
```

### 2. Sign Manifest
```bash
ocp-cli sign --manifest skill.yaml --key ocp/keys/operational.json
```

### 3. Register to Registry
```bash
ocp-cli registry register --manifest skill.yaml --signature skill.sig.yaml
```

### 4. Run CI/CD Pipeline
```bash
ocp-cicd pipeline --manifest skill.yaml --signature skill.sig.yaml --code ./
```

### 5. Monitor Deployment
```bash
ocp-obs dashboard --output dashboard.html
```

### 6. Propagate to Federation
```bash
ocp-fed propagate --skill-id web_research --version 1.0.0 --nodes node1,node2
```

---

## Troubleshooting

### System Won't Start
```bash
# Check logs
./startup.sh startup 2>&1 | tee startup.log

# Verify components
./startup.sh verify

# Reinitialize (WARNING: destroys data)
rm -rf ocp/keys/ ocp/*.db
./startup.sh startup
```

### Phase Fails to Initialize
```bash
# Initialize individual phase
./startup.sh phase<X>

# Check dependencies
./startup.sh verify
```

### Database Issues
```bash
# Check database files
ls -la ocp/core/registry/registry.db
ls -la ocp/proposal/proposals.db
ls -la ocp/cicd/cicd.db
ls -la ocp/observability/observability.db
ls -la ocp/federation/federation.db
ls -la ocp/mitigation/mitigation.db
```

---

## License

MIT License — See LICENSE file for details

---

## Support

For detailed documentation:
- `cat OCCP_DEPLOYMENT_GUIDE.md`
- `cat OCCP_ARCHITECTURE.md`
- `cat OCCP_FILE_INDEX.md`

---

**OCCP v1.0 — Production-Ready Skills Management System**

*All 9 phases implemented, tested, and documented*
