# OCCP v1.0 — Immediate Next Steps (Week 1)

**Focus:** Production stability & operational excellence

---

## 🎯 Week 1 Priorities (Feb 5-12, 2026)

### Day 1-2: Production Monitoring Setup

**Goal:** Full observability & alerting

```bash
# 1. Setup RED metrics collection
ocp-obs collect --all-skills --time-window-sec 300

# 2. Configure alerting
# Create alert configuration: ocp/alerts/rules.yaml
cat > ocp/alerts/rules.yaml <<EOF
alerts:
  - name: high_error_rate
    condition: error_rate > 0.01
    severity: critical
    action: notify

  - name: high_latency
    condition: duration_p95_ms > 1000
    severity: warning
    action: notify
EOF

# 3. Create daily dashboard
ocp-obs dashboard --output daily_report.html --include-graphs
```

**Deliverables:**
- [ ] RED metrics baseline established
- [ ] Alert rules configured
- [ ] Daily health dashboard operational
- [ ] On-call rotation defined

**Owner:** DevOps | **Effort:** 8 hours

---

### Day 3: Database Backup Strategy

**Goal:** Automated, reliable backups

```bash
# 1. Create backup script
cat > scripts/backup_databases.sh <<'SCRIPT'
#!/bin/bash
BACKUP_DIR="/backup/ocp/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

for db in registry proposals cicd observability federation mitigation; do
  db_path="ocp/*/$(echo $db | sed 's/mitigation$/mitigation\//').db"
  cp $db_path "$BACKUP_DIR/"
done

# Upload to S3/GCS
aws s3 sync "$BACKUP_DIR" s3://ocp-backups/$(date +%Y%m%d)/

# Keep last 30 days only
find /backup/ocp/ -mtime +30 -delete
SCRIPT

chmod +x scripts/backup_databases.sh

# 2. Schedule cron job
crontab -e
# Add: 0 * * * * /home/onor/ai_os_final/scripts/backup_databases.sh

# 3. Test restore
# Create restore procedure in docs/operations/restore.md
```

**Deliverables:**
- [ ] Hourly automated backups
- [ ] Offsite backup storage (S3/GCS)
- [ ] Restore procedure documented
- [ ] Restore tested successfully

**Owner:** DevOps | **Effort:** 4 hours

---

### Day 4: CLI Usability Improvements

**Goal:** Better developer experience

```bash
# 1. Add bash completion
cat > scripts/generate_completion.sh <<'SCRIPT'
#!/bin/bash
# Generate completion for all CLI tools
for cli in ocp-proposals ocp-cicd ocp-obs ocp-fed ocp-mit; do
  $cli --completion-bash > /etc/bash_completion.d/$cli
done
SCRIPT

# 2. Improve error messages
# Update all CLI tools to provide:
# - Clear error description
# - Suggested fix
# - Documentation link
# - Example command

# Example in ocp/cicd/cli.py:
class BuildError(Exception):
    def __str__(self):
        return """
❌ Build Failed: {reason}

Possible fixes:
  1. Check manifest syntax: ocp-cicd validate --manifest {manifest}
  2. Verify dependencies: ocp-cicd check-deps --code {code_path}
  3. Review logs: ocp-cicd logs --build {build_id}

Documentation: https://docs.ocp.dev/cicd/troubleshooting
        """
```

**Deliverables:**
- [ ] Bash completion for all CLIs
- [ ] Improved error messages
- [ ] Helpful suggestions for common errors
- [ ] Quick reference card

**Owner:** Core Team | **Effort:** 6 hours

---

### Day 5: Unit Tests for Phases 1-4

**Goal:** Test coverage for critical infrastructure

```python
# tests/test_authority.py
import pytest
from ocp.core.authority.keys import AuthorityKey, save_key, load_key

def test_key_generation():
    """Test Ed25519 key generation"""
    key = AuthorityKey.generate(role_level=4)
    assert key.role_level == 4
    assert key.key_id is not None
    assert key.public_key is not None
    assert key.secret_key is not None

def test_key_persistence():
    """Test key save/load"""
    key = AuthorityKey.generate(role_level=1)
    save_key(key, '/tmp/test_key.json')
    loaded = load_key('/tmp/test_key.json')
    assert loaded.key_id == key.key_id
    assert loaded.public_key == key.public_key

# tests/test_registry.py
def test_skill_registration():
    """Test skill registration"""
    from ocp.core.registry.crud import SkillRegistry
    registry = SkillRegistry(db_session=None)

    manifest = {
        "skill": {
            "name": "test_skill",
            "version": "1.0.0",
            "author": "test"
        }
    }

    skill_id = registry.register_skill(manifest, "test_signature")
    assert skill_id == "test_skill:1.0.0"

# Run tests
pytest tests/ -v --cov=ocp/core --cov-report=html
```

**Deliverables:**
- [ ] Unit tests for Authority (10+ tests)
- [ ] Unit tests for Registry (15+ tests)
- [ ] Unit tests for Executor (10+ tests)
- [ ] Unit tests for MCP (5+ tests)
- [ ] 80%+ code coverage

**Owner:** QA | **Effort:** 8 hours

---

### Day 6-7: Documentation & Quick Start Guide

**Goal:** Enable new users to get started quickly

```bash
# 1. Create quick start tutorial
cat > docs/QUICKSTART.md <<'EOF'
# OCCP v1.0 — 5-Minute Quick Start

## Step 1: System Check (1 min)
./startup.sh verify

Expected output: ✓ All phases operational

## Step 2: Create Your First Skill (2 min)
cat > my_skill.yaml <<EOF
skill:
  name: hello_world
  version: 1.0.0
  author: your_name
  capabilities:
    - greet
  contracts:
    max_execution_time_seconds: 10
    max_memory_mb: 128
EOF

## Step 3: Register Skill (1 min)
ocp-cli registry register \
  --manifest my_skill.yaml \
  --signature my_skill.sig.yaml

## Step 4: Deploy via CI/CD (1 min)
ocp-cicd pipeline \
  --manifest my_skill.yaml \
  --signature my_skill.sig.yaml \
  --code ./

✅ Your skill is now deployed!
EOF

# 2. Create troubleshooting guide
cat > docs/TROUBLESHOOTING.md <<'EOF'
# Common Issues & Solutions

## Issue: "Module not found"
**Cause:** Python path not set correctly
**Fix:**
  export PYTHONPATH="${PYTHONPATH}:$(pwd)/ocp"
  export PYTHONPATH="${PYTHONPATH}:$(pwd)/ocp/core"

## Issue: "Database locked"
**Cause:** Multiple writers to SQLite
**Fix:** Use database queue or wait for current operation

## Issue: "Permission denied"
**Cause:** Insufficient authority level
**Fix:** Use higher-level key or get approval

[See full guide for 50+ issues]
EOF

# 3. Create video tutorials
# - 5-min: System overview
# - 10-min: First skill deployment
# - 15-min: CI/CD pipeline
# - 10-min: Incident response
```

**Deliverables:**
- [ ] 5-minute quick start guide
- [ ] Troubleshooting guide (50+ issues)
- [ ] Video tutorials (4 videos, 40 min total)
- [ ] Interactive tutorial

**Owner:** Documentation | **Effort:** 12 hours

---

## 📊 Week 1 Success Criteria

### Must-Have (P0)
- ✅ Production monitoring operational
- ✅ Automated backups configured & tested
- ✅ Critical infrastructure unit tests passing
- ✅ Quick start guide published

### Nice-to-Have (P1)
- ✅ Bash completion implemented
- ✅ Error messages improved
- ✅ Video tutorials recorded

---

## 🚀 Week 2 Preview (Feb 12-19, 2026)

### Focus Areas:
1. **Integration Tests** — End-to-end workflows
2. **Shell Completion** — Full bash/zsh support
3. **Advanced Monitoring** — Custom dashboards
4. **Penetration Testing** — Security audit kickoff

---

## 📋 Checklists

### Daily Standup Questions:
1. What did you accomplish yesterday?
2. What will you work on today?
3. Any blockers or dependencies?
4. Metrics update (progress, bugs, incidents)

### Week 1 Exit Criteria:
- [ ] All P0 items completed
- [ ] System availability > 99%
- [ ] Mean time to detect (MTTD) < 5 min
- [ ] Backup & restore tested
- [ ] Test coverage > 70%
- [ ] Documentation published

---

## 📞 Week 1 Responsibilities

| Role | Name | Responsibilities |
|------|------|-----------------|
| Week Lead | TBD | Coordination, blocker removal |
| DevOps | TBD | Monitoring, backups, infrastructure |
| QA | TBD | Unit tests, test coverage |
| Docs | TBD | Quick start, troubleshooting, videos |
| Core Team | TBD | CLI improvements, bug fixes |

---

## 🔄 Continuous Tasks

### Daily:
- [ ] Check system health (./startup.sh verify)
- [ ] Review overnight logs
- [ ] Backup verification
- [ ] Standup meeting (15 min)

### Weekly:
- [ ] Metrics review (MTTR, availability, error rate)
- [ ] Retro on completed items
- [ ] Next week planning
- [ ] Documentation updates

---

**Week 1 Start Date:** 2026-02-05
**Week 1 End Date:** 2026-02-12
**Overall Status:** 🟢 On Track

---

*This document will be updated daily. Check back for progress updates.*
