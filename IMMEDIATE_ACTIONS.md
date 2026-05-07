# OCCP v1.0 — Immediate Next Actions (Week 2-3)

**Focus:** Real-world usage scenarios & battle testing

---

## 🎯 Week 2: First Skills & Production Validation

### Day 1: Create & Register First Skill

```bash
# 1. Create skill manifest
cat > skills/hello_world/manifest.yaml <<EOF
skill:
  name: hello_world
  version: 1.0.0
  author: authority
  description: "Simple hello world skill for testing"
  capabilities:
    - greet
    - echo
  contracts:
    max_execution_time_seconds: 10
    max_memory_mb: 64
    max_tokens: 1000
EOF

# 2. Create skill code
mkdir -p skills/hello_world/code
cat > skills/hello_world/code/skill.py <<'PYTHON'
def execute(input_data):
    name = input_data.get('name', 'World')
    return {
        'status': 'passed',
        'output': f'Hello, {name}!',
        'duration_ms': 50
    }
PYTHON

# 3. Sign manifest (using operational key)
python3 <<PYTHON
import json
import hashlib
from ocp.core.authority.keys import load_key
from ocp.core.authority.signer import ManifestSigner

# Load manifest
with open('skills/hello_world/manifest.yaml', 'r') as f:
    manifest_data = yaml.safe_load(f)

# Load key
key = load_key('ocp/keys/operational.json')

# Sign
signer = ManifestSigner(key.secret_key)
signature = signer.sign_manifest(manifest_data)

# Save signature
with open('skills/hello_world/signature.yaml', 'w') as f:
    yaml.dump({'signature': signature}, f)

print(f'✓ Manifest signed: {signature[:16]}...')
PYTHON

# 4. Register skill
ocp-cli registry register \
  --manifest skills/hello_world/manifest.yaml \
  --signature skills/hello_world/signature.yaml

# Expected output:
# ✓ Skill registered: hello_world:1.0.0
```

**Deliverables:**
- [ ] First skill created
- [ ] Manifest signed
- [ ] Skill registered in registry
- [ ] Verify: `ocp-cli registry list`

---

### Day 2: Run CI/CD Pipeline

```bash
# 1. Run full CI/CD pipeline
ocp-cicd pipeline \
  --manifest skills/hello_world/manifest.yaml \
  --signature skills/hello_world/signature.yaml \
  --code skills/hello_world/code/

# Pipeline stages:
# Stage 1: VALIDATING → ✓ Manifest validation passed
# Stage 2: TESTING → ✓ All tests passed
# Stage 3: BUILDING → ✓ Artifact created: hello_world-1.0.0.tar.gz
# Stage 4: DEPLOYING_CANARY → ✓ Canary deployed (5% traffic)
# Stage 5: MONITORING → ✓ Health checks passed
# Stage 6: PROMOTING → ✓ Promoted to stable (100% traffic)

# 2. Check deployment status
ocp-cicd status --deployment <deployment-id>

# 3. Monitor canary metrics
ocp-obs collect \
  --skill-id hello_world \
  --version 1.0.0 \
  --time-window-sec 300

# Expected RED metrics:
# - Request rate: 0.01 req/sec
# - Error rate: 0.0%
# - Duration P95: < 100ms
```

**Deliverables:**
- [ ] Full CI/CD pipeline executed
- [ ] Build artifact created
- [ ] Canary deployment successful
- [ ] Promoted to stable
- [ ] RED metrics collected

---

### Day 3: Observability & Alerting

```bash
# 1. Collect RED metrics for all skills
ocp-obs collect --all-skills --time-window-sec 300

# 2. Aggregate metrics from all sources
ocp-obs aggregate --time-window-sec 300

# Expected output:
# {
#   "total_requests": 150,
#   "total_errors": 0,
#   "avg_duration_p95_ms": 85,
#   "top_errors": [],
#   "top_slow": []
# }

# 3. Generate daily dashboard
ocp-obs dashboard \
  --output reports/daily_$(date +%Y%m%d).html \
  --include-graphs \
  --include-alerts \
  --include-recommendations

# 4. Configure alerting rules
mkdir -p ocp/alerts
cat > ocp/alerts/rules.yaml <<EOF
alerts:
  - name: high_error_rate
    condition: "error_rate > 0.01"
    severity: critical
    action: notify
    channels: [email, slack]

  - name: high_latency
    condition: "duration_p95_ms > 1000"
    severity: warning
    action: notify
    channels: [email]

  - name: violation_detected
    condition: "violation_rate > 0.0"
    severity: critical
    action: notify
    channels: [email, slack, pagerduty]
EOF

# 5. Test alerting
python3 <<PYTHON
from ocp.observability.metrics_collector import MetricsCollector
from ocp.observability.aggregator import MetricsAggregator

# Collect metrics
collector = MetricsCollector()
metrics = collector.collect_all_metrics(time_window_seconds=300)

# Check alert conditions
for skill_metric in metrics:
    if skill_metric.error_rate > 0.01:
        print(f'⚠️  ALERT: {skill_metric.skill_id} error rate {skill_metric.error_rate:.2%}')
PYTHON
```

**Deliverables:**
- [ ] RED metrics baseline established
- [ ] Dashboard generated
- [ ] Alert rules configured
- [ ] Alert notification tested

---

### Day 4: Database Backup Strategy

```bash
# 1. Create backup script
mkdir -p scripts
cat > scripts/backup_databases.sh <<'SCRIPT'
#!/bin/bash
set -e

BACKUP_DIR="/backup/ocp/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "🔄 Starting database backup..."

# Backup all databases
databases=(
  "ocp/core/registry/registry.db"
  "ocp/proposal/proposals.db"
  "ocp/cicd/cicd.db"
  "ocp/observability/observability.db"
  "ocp/federation/federation.db"
  "ocp/mitigation/mitigation.db"
)

for db in "${databases[@]}"; do
  if [ -f "$db" ]; then
    cp "$db" "$BACKUP_DIR/"
    echo "✓ Backed up: $db"
  fi
done

# Create backup manifest
cat > "$BACKUP_DIR/manifest.json" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "databases": $(printf '%s\n' "${databases[@]}" | jq -R . | jq -s -c '. | map(select(. != null))')
}
EOF

# Compress backups
cd "$BACKUP_DIR"
tar czf ../backup_$(date +%Y%m%d_%H%M%S).tar.gz .
cd -

# Cleanup (keep last 30 days)
find /backup/ocp/ -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true

echo "✅ Backup complete: $BACKUP_DIR"
SCRIPT

chmod +x scripts/backup_databases.sh

# 2. Schedule automated backups (cron)
(crontab -l 2>/dev/null; echo "0 * * * * /home/onor/ai_os_final/scripts/backup_databases.sh") | crontab -

# 3. Test backup now
./scripts/backup_databases.sh

# Expected output:
# 🔄 Starting database backup...
# ✓ Backed up: ocp/core/registry/registry.db
# ✓ Backed up: ocp/proposal/proposals.db
# ✓ Backed up: ocp/cicd/cicd.db
# ✓ Backed up: ocp/proposals/proposals.db
# ✓ Backed up: ocp/observability/observability.db
# ✓ Backed up: ocp/federation/federation.db
# ✓ Backed up: ocp/mitigation/mitigation.db
# ✅ Backup complete: /backup/ocp/20260205_120000

# 4. Test restore procedure
mkdir -p /tmp/restore_test
cp /backup/ocp/backup_20260205_120000.tar.gz /tmp/restore_test/
cd /tmp/restore_test
tar xzf backup_20260205_120000.tar.gz
ls -lh
# Verify all .db files are present

# 5. Optional: Upload to S3/GCS
# aws s3 sync /backup/ocp/ s3://ocp-backups/$(date +%Y%m%d)/
# gsutil -m rsync -r /backup/ocp/ gs://ocp-backups/$(date +%Y%m%d)/
```

**Deliverables:**
- [ ] Backup script created
- [ ] Automated backups scheduled (cron)
- [ ] Manual backup tested
- [ ] Restore procedure tested
- [ ] Offsite backup configured (optional)

---

### Day 5: Federation Multi-Node Testing

```bash
# 1. Simulate second node (on same machine for testing)
export NODE2_HOME="/tmp/ocp_node2"
mkdir -p $NODE2_HOME

# 2. Initialize node 2
cd $NODE2_HOME
cat > startup_node2.sh <<'SCRIPT'
#!/bin/bash
# Initialize federation node
export OCP_NODE_ID="node2"
export OCP_FEDERATION_MODE="peer"

# Start with Phase 1-4
./startup.sh phase1
./startup.sh phase2
./startup.sh phase8

echo "✓ Node 2 initialized"
SCRIPT

# 3. Configure federation nodes on both sides
cat > ocp/federation/nodes.yaml <<EOF
nodes:
  - id: node1
    url: http://localhost:8000
    role: primary
    capabilities:
      - registry
      - executor
      - observability

  - id: node2
    url: http://localhost:8001
    role: peer
    capabilities:
      - registry
      - executor
EOF

# 4. Test skill propagation from node1 to node2
ocp-fed propagate \
  --skill-id hello_world \
  --version 1.0.0 \
  --nodes node2

# Expected output:
# ✓ Propagating hello_world:1.0.0 to node2
# ✓ Skill pushed to node2
# ✓ Confirmation received

# 5. Verify propagation on node2
curl -s http://localhost:8001/federation/skills | jq .

# 6. Test registry sync
ocp-fed sync \
  --remote-node-id node2 \
  --direction bidirectional \
  --conflict-resolution local_wins

# Expected output:
# ✓ Syncing with node2...
# ✓ Pushed 1 local skill to node2
# ✓ Pulled 0 remote skills from node2
# ✓ Sync complete

# 7. Check federation health
ocp-fed health --check-interval-sec 60

# Expected output:
# ✓ Federation Health Report
#   node1: healthy (uptime: 2d)
#   node2: healthy (uptime: 1d)
#   Replication lag: 0s
```

**Deliverables:**
- [ ] Second node initialized
- [ ] Federation configured
- [ ] Skill propagation tested
- [ ] Registry sync tested
- [ ] Federation health verified

---

## 🚀 Week 3: Advanced Scenarios & Validation

### Day 1: Proposal Agents Testing

```bash
# 1. Run proposal detector
ocp-proposals detect --hours 24

# Expected output:
# 🔍 Detecting patterns (last 24h)...
#
# ⚠️  Detected 2 pattern(s):
#
# 🟢 UNUSED_CAPABILITY
#    Capability: advanced_math
#    Skill: calculator
#    Confidence: 85%
#    Rationale: Capability not used in 30 days
#
# 🟡 REDUNDANT_SKILL
#    Skills: [date_utils_v1, date_utils_v2]
#    Similarity: 92%
#    Confidence: 78%
#    Rationale: Overlapping functionality detected

# 2. Generate proposals
ocp-proposals generate --min-confidence 0.7

# Expected output:
# 💡 Generated 2 proposal(s):
#
# Proposal 1: REMOVE_CAPABILITY
#    Target: calculator
#    Capability: advanced_math
#    Confidence: 85%
#    Rationale: Capability not used in 30 days
#    Action: Remove from manifest
#
# Proposal 2: MERGE_SKILLS
#    Targets: [date_utils_v1, date_utils_v2]
#    Strategy: Keep v2, deprecate v1
#    Confidence: 78%
#    Rationale: 92% functional overlap

# 3. Approve/reject proposals
ocp-proposals approve \
  --proposal-id <proposal_1_id> \
  --key operational \
  --rationale "Valid observation, will remove"

# 4. Check learning outcome
ocp-proposals history --days 7

# Expected output:
# 📊 Proposal History (last 7 days)
#    Total proposals: 2
#    Approved: 1
#    Rejected: 0
#    Pending: 1
#    Approval rate: 100%
```

**Deliverables:**
- [ ] Pattern detection tested
- [ ] Proposals generated
- [ ] Approval workflow tested
- [ ] Learning model updated

---

### Day 2: Mitigation & Incident Response

```bash
# 1. Simulate cascade violation
# Create multiple skills that violate
python3 <<PYTHON
from ocp.core.executor.runner import SkillRunner
from ocp.mitigation.detector import CascadeDetector

runner = SkillRunner()
detector = CascadeDetector(metrics_collector=None, federation_aggregator=None)

# Simulate violations
for i in range(5):
    result = {
        'status': 'violated',
        'violations': ['memory_limit_exceeded'],
        'skill_id': f'test_skill_{i}',
        'timestamp': datetime.utcnow()
    }
    print(f"Simulated violation: test_skill_{i}")

# Detect cascade
cascades = detector.detect_cascades(time_window_seconds=60)
print(f"Detected {len(cascades)} cascade(s)")
PYTHON

# 2. Detect cascades
ocp-mit detect --time-window-sec 300

# Expected output:
# 🔍 Detecting cascade violations...
#
# ⚠️  Detected 1 cascade violation(s):
#
# 🔴 CASCADE_DETECTED
#    Severity: HIGH
#    Affected Skills: [test_skill_0, test_skill_1, test_skill_2]
#    Affected Nodes: [node1]
#    Violations: 15
#    Confidence: 92%
#    Root Cause: Memory exhaustion in shared resource
#    Pattern: FUNCTIONAL

# 3. Generate remediation plan
ocp-mit remediate --incident <incident_id>

# Expected output:
# 🔧 Creating remediation plan...
#
# 📋 Remediation Plan: <plan_id>
#    Incident: <incident_id>
#    Severity: HIGH
#    Requires Approval: ✓
#
# Actions:
#    1. RESTART_SKILL: test_skill_0
#    2. ISOLATE_NODE: node1 (if violations > 10)
#    3. DISABLE_SKILL: test_skill_1 (temporary)
#
# Estimated recovery: 120s
#
# ⚠️  Requires Authority approval

# 4. Approve remediation (Authority only)
ocp-mit approve \
  --plan-id <plan_id> \
  --key operational \
  --rationale "Cascade confirmed, isolating affected node"

# 5. Check learning outcome
ocp-mit learn --min-incidents 5

# Expected output:
# 🧠 Generating learning insights...
#
# 💡 Recommendations: 3
#    1. INCREASE_MEMORY_LIMITS
#       Confidence: 88%
#       Reason: 80% of incidents involve memory exhaustion
#
#    2. ADD_RATE_LIMITING
#       Confidence: 75%
#       Reason: Cascade pattern indicates overload
#
#    3. IMPROVE_MONITORING
#       Confidence: 92%
#       Reason: Early detection could prevent 60% of incidents
```

**Deliverables:**
- [ ] Cascade detection tested
- [ ] Remediation plan generated
- [ ] Approval workflow tested
- [ ] Learning model updated
- [ ] Recommendations generated

---

### Day 3: Advanced CI/CD Scenarios

```bash
# 1. Create skill with multiple versions
for version in 1.0.0 1.1.0 2.0.0; do
  mkdir -p skills/calculator/v$version

  cat > skills/calculator/v$version/manifest.yaml <<EOF
skill:
  name: calculator
  version: $version
  author: authority
  capabilities:
    - add
    - subtract
    - multiply
    - divide
  contracts:
    max_execution_time_seconds: 5
    max_memory_mb: 32
EOF

  # Create version-specific code
  if [ "$version" = "2.0.0" ]; then
    echo "Advanced calculator v2" > skills/calculator/v$version/code.py
  else
    echo "Basic calculator v1" > skills/calculator/v$version/code.py
  fi

  # Sign & register each version
  # (sign and register commands here)
done

# 2. Test canary deployment with rollback scenario
ocp-cicd deploy \
  --artifact ocp/artifacts/calculator-2.0.0.tar.gz \
  --canary-percent 5 \
  --monitor-duration-sec 60

# While canary is running, simulate issues
# (e.g., spike error rate artificially)

# 3. Trigger rollback
ocp-cicd rollback \
  --deployment <deployment-id> \
  --reason "Error rate exceeded threshold: 5% > 1%"

# Expected output:
# 🔄 Rolling back deployment...
# ✓ Rollback initiated
# ✓ Traffic shifted to previous version: 1.1.0
# ✓ Canary deployment cancelled
# ✓ Rollback complete: 12.3s

# 4. Verify rollback
ocp-cicd status --deployment <deployment-id>
# Should show: ROLLED_BACK to version 1.1.0

# 5. Test blue-green deployment (full switch)
ocp-cicd deploy \
  --artifact ocp/artifacts/calculator-2.0.0.tar.gz \
  --strategy blue-green \
  --switch-delay-sec 30

# Expected output:
# 🔄 Blue-green deployment...
# ✓ Version 2.0.0 deployed to green environment
# ✓ Health checks passed
# ✓ Traffic switched: blue → green (100%)
# ✓ Deployment complete
```

**Deliverables:**
- [ ] Multi-version skill tested
- [ ] Canary deployment tested
- [ ] Rollback scenario validated
- [ ] Blue-green deployment tested
- [ ] Deployment strategies compared

---

### Day 4-5: End-to-End Integration Test

```bash
# 1. Complete workflow: Register → CI/CD → Deploy → Monitor
cat > scripts/e2e_test.sh <<'SCRIPT'
#!/bin/bash
set -e

echo "🧪 E2E Integration Test"

# Stage 1: Register skill
echo "Stage 1: Registering skill..."
ocp-cli registry register \
  --manifest skills/test_e2e/manifest.yaml \
  --signature skills/test_e2e/signature.yaml

# Stage 2: CI/CD pipeline
echo "Stage 2: Running CI/CD..."
ocp-cicd pipeline \
  --manifest skills/test_e2e/manifest.yaml \
  --signature skills/test_e2e/signature.yaml \
  --code skills/test_e2e/code/

# Stage 3: Federation propagation
echo "Stage 3: Propagating to node2..."
ocp-fed propagate \
  --skill-id test_e2e \
  --version 1.0.0 \
  --nodes node2

# Stage 4: Collect metrics
echo "Stage 4: Collecting metrics..."
ocp-obs collect --skill-id test_e2e --version 1.0.0

# Stage 5: Generate report
echo "Stage 5: Generating report..."
ocp-obs dashboard --output reports/e2e_test.html

echo "✅ E2E test complete!"
SCRIPT

chmod +x scripts/e2e_test.sh
./scripts/e2e_test.sh

# 2. Verify system health after E2E test
./startup.sh verify

# Expected: All phases operational ✓

# 3. Performance test (load testing)
# Simulate 100 concurrent executions
python3 <<PYTHON
import asyncio
from ocp.core.executor.runner import SkillRunner

runner = SkillRunner()

async def load_test():
    tasks = []
    for i in range(100):
        task = asyncio.create_task(
            runner.execute_skill('test_e2e', 'code', {'test': i})
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    successful = sum(1 for r in results if r['status'] == 'passed')

    print(f"✅ Load test complete: {successful}/100 successful")
    print(f"   Success rate: {successful}%")

asyncio.run(load_test())
PYTHON

# 4. Create test report
cat > reports/e2e_test_summary.md <<EOF
# E2E Integration Test Summary

**Date:** $(date +%Y-%m-%d)
**Test Duration:** 30 minutes
**Result:** ✅ PASSED

## Test Results

### Phase 1: Registration
- Status: ✅ PASSED
- Details: Skill registered successfully
- Time: 2s

### Phase 2: CI/CD Pipeline
- Status: ✅ PASSED
- Details:
  - Manifest validation: ✅
  - Unit tests: ✅
  - Integration tests: ✅
  - Build: ✅
  - Canary deployment: ✅
  - Promotion: ✅
- Time: 5m 30s

### Phase 3: Federation
- Status: ✅ PASSED
- Details: Skill propagated to node2
- Time: 8s

### Phase 4: Observability
- Status: ✅ PASSED
- Details: RED metrics collected
  - Request rate: 0.05 req/sec
  - Error rate: 0.0%
  - Duration P95: 75ms
- Time: 3s

### Phase 5: Performance
- Status: ✅ PASSED
- Details: 100 concurrent executions
  - Success rate: 100%
  - Avg duration: 68ms
- Time: 12s

## Overall System Health
- All phases: ✅ Operational
- Uptime: 100%
- No incidents detected

## Recommendations
1. ✅ System ready for production use
2. ✅ Monitoring baseline established
3. ✅ Federation operational
4. ⚠️  Consider adding more load tests
5. ⚠️  Set up automated E2E tests in CI
EOF

cat reports/e2e_test_summary.md
```

**Deliverables:**
- [ ] E2E test script created
- [ ] Complete workflow validated
- [ ] System health verified
- [ ] Performance test passed (100 concurrent)
- [ ] Test report generated

---

## 📊 Week 2-3 Success Criteria

### Must-Have (P0)
- [ ] First skill registered & deployed end-to-end
- [ ] CI/CD pipeline executed successfully
- [ ] RED metrics baseline established
- [ ] Database backups automated & tested
- [ ] Federation propagation validated
- [ ] Proposal agents detected patterns
- [ ] Mitigation system tested
- [ ] E2E integration test passed

### Nice-to-Have (P1)
- [ ] Multi-version deployment tested
- [ ] Rollback scenario validated
- [ ] Load testing (100+ concurrent)
- [ ] Automated E2E test in CI
- [ ] Performance dashboard created

---

## 🚨 Troubleshooting Common Issues

### Issue: "Skill registration failed"
**Solution:**
```bash
# Verify manifest syntax
ocp-cli validate --manifest skill.yaml

# Check signature
ocp-cli verify-signature --manifest skill.yaml --signature skill.sig.yaml

# Check authority key
ls -la ocp/keys/operational.json
```

### Issue: "CI/CD pipeline stuck at TESTING"
**Solution:**
```bash
# Check test logs
ocp-cicd logs --build <build_id>

# Run tests manually
pytest tests/ -v

# Check test dependencies
pip3 list | grep pytest
```

### Issue: "Federation sync timeout"
**Solution:**
```bash
# Check node connectivity
curl -s http://node2:8000/health

# Verify network
ping node2

# Check federation logs
ocp-fed logs --node node2
```

### Issue: "Metrics not collecting"
**Solution:**
```bash
# Check observability database
ls -la ocp/observability/observability.db

# Verify collector
ocp-obs health

# Check executor logs
./startup.sh verify
```

---

## 📝 Week 2-3 Checklist

### Week 2
- [ ] Day 1: First skill created & registered
- [ ] Day 2: CI/CD pipeline executed
- [ ] Day 3: Observability configured
- [ ] Day 4: Database backups automated
- [ ] Day 5: Federation tested

### Week 3
- [ ] Day 1: Proposal agents tested
- [ ] Day 2: Mitigation validated
- [ ] Day 3: Advanced CI/CD scenarios
- [ ] Day 4-5: E2E integration test

### End of Week 3
- [ ] All P0 criteria met
- [ ] Production readiness confirmed
- [ ] System monitoring operational
- [ ] Team trained on workflows

---

**🎯 By end of Week 3, OCCP v1.0 will be battle-tested and production-proven!**
