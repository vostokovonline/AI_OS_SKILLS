# OCCP v1.0 — Complete File Index

## Core System (Phases 1-4)

### Phase 1: Authority & Signing
```
ocp/core/authority/
├── __init__.py
├── keys.py              — Ed25519 key generation
├── roles.py             — Authority role definitions
└── signer.py            — Manifest signing
```

### Phase 2: Registry
```
ocp/core/registry/
├── __init__.py
├── database.py          — PostgreSQL manager
├── crud.py              — Skill CRUD operations
└── verifier.py          — Signature verification
```

### Phase 3: Executor
```
ocp/core/executor/
├── __init__.py
├── sandbox.py           — SkillSandbox (resource limits)
└── runner.py            — SkillRunner (execution engine)
```

### Phase 4: MCP Integration
```
ocp/integrations/mcp/
├── __init__.py
├── adapter.py           — MCPAdapter
└── wrapper.py           — MCPSandbox
```

---

## Advanced Features (Phases 5-9)

### Phase 5: Proposal Agents
```
ocp/proposal/
├── __init__.py           — Module exports
├── observer.py           — MetricsObserver (read-only)
├── detector.py           — PatternDetector
├── generator.py          — ProposalGenerator
├── learning.py           — ProposalLearning
├── models.py             — Database models
├── database.py           — Database manager
└── cli.py                — ocp-proposals CLI
```

**Total:** ~2,000 lines

### Phase 6: CI/CD Pipeline
```
ocp/cicd/
├── __init__.py           — Module exports
├── testing.py            — SkillTester (fail-fast)
├── builder.py            — SkillBuilder (reproducible)
├── canary.py             — CanaryDeployer
├── rollback.py           — RollbackManager
├── pipeline.py           — SkillPipeline (orchestrator)
├── models.py             — Database models
├── database.py           — Database manager
└── cli.py                — ocp-cicd CLI
```

**Total:** ~2,600 lines

### Phase 7: Observability
```
ocp/observability/
├── __init__.py           — Module exports
├── metrics_collector.py  — MetricsCollector (RED)
├── aggregator.py         — MetricsAggregator
├── dashboard.py          — Dashboard generator
├── models.py             — Database models
├── database.py           — Database manager
└── cli.py                — ocp-obs CLI
```

**Total:** ~1,600 lines

### Phase 8: Federation
```
ocp/federation/
├── __init__.py           — Module exports
├── propagator.py         — SkillPropagator
├── aggregator.py         — FederationAggregator
├── registry_sync.py      — RegistrySyncer
├── health_monitor.py     — FederationHealthMonitor
├── models.py             — Database models
├── database.py           — Database manager
└── cli.py                — ocp-fed CLI
```

**Total:** ~2,100 lines

### Phase 9: Automated Mitigation
```
ocp/mitigation/
├── __init__.py           — Module exports
├── detector.py           — CascadeDetector
├── remediator.py         — AutoRemediator
├── emergency.py          — EmergencyManager
├── learning.py           — MitigationLearner
├── models.py             — Database models
├── database.py           — Database manager
└── cli.py                — ocp-mit CLI
```

**Total:** ~2,400 lines

---

## Deployment & Documentation

### Root Directory
```
/home/onor/ai_os_final/
├── startup.sh                 — Production startup script
├── OCCP_DEPLOYMENT_GUIDE.md   — Comprehensive deployment guide
├── OCCP_ARCHITECTURE.md       — Architecture overview
└── OCCP_FILE_INDEX.md         — This file
```

### Artifacts & Keys
```
ocp/
├── keys/                      — Authority keys (generated on startup)
│   ├── root.json              — Level 4 (Constitutional)
│   ├── intermediate.json      — Level 3 (Strategic)
│   └── operational.json       — Level 1 (Operational)
└── artifacts/                 — CI/CD build outputs
```

### Databases (Generated on Startup)
```
ocp/core/registry/registry.db
ocp/proposal/proposals.db
ocp/cicd/cicd.db
ocp/observability/observability.db
ocp/federation/federation.db
ocp/mitigation/mitigation.db
```

---

## CLI Tools

### Core CLI
```
ocp-cli (via ocp/core/cli.py)
  — registry register
  — execute
```

### Proposal Agents CLI
```
ocp-proposals (via ocp/proposal/cli.py)
  — detect
  — generate
  — approve
  — reject
  — history
```

### CI/CD CLI
```
ocp-cicd (via ocp/cicd/cli.py)
  — test
  — build
  — deploy
  — monitor
  — promote
  — rollback
  — pipeline
```

### Observability CLI
```
ocp-obs (via ocp/observability/cli.py)
  — collect
  — aggregate
  — dashboard
  — health
```

### Federation CLI
```
ocp-fed (via ocp/federation/cli.py)
  — propagate
  — sync
  — health
  — status
```

### Mitigation CLI
```
ocp-mit (via ocp/mitigation/cli.py)
  — detect
  — remediate
  — emergency
  — history
  — learn
  — approve
  — reject
  — resolve-emergency
```

---

## Quick Reference

### Start System
```bash
./startup.sh startup
```

### Verify System
```bash
./startup.sh verify
```

### Register Skill
```bash
ocp-cli registry register --manifest ./skill.yaml --signature ./sig.yaml
```

### Run CI/CD Pipeline
```bash
ocp-cicd pipeline --manifest ./skill.yaml --signature ./sig.yaml --code ./
```

### View Metrics
```bash
ocp-obs dashboard --output ./dashboard.html
```

---

## File Count Summary

```
Phase 1-4:  ~12 files (infrastructure)
Phase 5:     8 files (proposal agents)
Phase 6:     9 files (CI/CD)
Phase 7:     7 files (observability)
Phase 8:     8 files (federation)
Phase 9:     8 files (mitigation)
────────────────────────────────────
Total:      52 files

Documentation:
  - OCCP_DEPLOYMENT_GUIDE.md
  - OCCP_ARCHITECTURE.md
  - OCCP_FILE_INDEX.md

Scripts:
  - startup.sh

Databases: 6 (generated on startup)
Keys: 3 (generated on startup)
Artifacts: N/A (generated by CI/CD)
```

---

**OCCP v1.0 — Complete System**
