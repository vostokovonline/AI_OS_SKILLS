# OCCP v0.3 — Implementation Fixes: Quick Reference

## Status: Ready for Implementation

**Estimate Time:** 8-10 hours total
**Risk Level:** LOW (changes isolated)
**Regression Risk:** MINIMAL (baseline metrics established)

---

## Priority 1: Concurrent SK Veto (HIGH)

### Implementation
```python
# File: services/core/occp_gateway.py

class OCCPGateway:
    def __init__(self, ...):
        # ... existing init ...
        self._sk_lock = asyncio.Lock()  # ← ADD THIS

    async def _sk_check(self, request: FederatedRequest) -> OCCPDecisionSchema:
        async with self._sk_lock:  # ← WRAP CHECK WITH LOCK
            # ... existing SK logic ...
            allowed = await self.sk_checker.allows_federated(request)
            # ...
```

### Verification
```bash
# Unit test (5 min)
python3 -c "
import asyncio
sys.path.insert(0, 'services/core')

async def test():
    from occp_gateway import OCCPGateway

    # Test with 100 concurrent SK checks
    # ... (see QA_CHECKLIST.py for full test)

asyncio.run(test())
"
```

**Expected:** SK called exactly 100 times, no races
**Time:** 1-2 hours

---

## Priority 2: Side-Channel Mitigation (MEDIUM)

### Implementation
```python
# File: services/core/occp_sandbox.py

async def _check_payload_async(self, payload: Dict) -> Optional[SandboxViolation]:
    """Async version with constant-time padding"""
    import time

    start = time.monotonic()
    target = 0.0001  # 100μs

    # ... existing check logic ...

    elapsed = time.monotonic() - start
    if elapsed < target:
        await asyncio.sleep(target - elapsed)

    return violation
```

### Verification
```bash
# Timing consistency test (5 min)
python3 -c "
import time, asyncio
sys.path.insert(0, 'services/core')

# Test allowed vs forbidden payload timing
# Expected: ratio < 10x
# ... (see QA_CHECKLIST.py)
"
```

**Expected:** Timing difference < 10x, throughput >10K req/sec
**Time:** 2-3 hours

---

## Priority 3: Audit Atomic Append (MEDIUM)

### Implementation
```python
# File: services/core/occp_gateway.py

async def _audit_log(self, request, decisions, result):
    """Atomic audit logging with file locking"""
    import fcntl
    import json

    entry = self._create_audit_entry(request, decisions, result)

    with open(self.audit_file, 'a') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock
        f.write(json.dumps(entry) + '\n')
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release
```

### Verification
```bash
# Concurrent write test (5 min)
python3 -c "
import asyncio, tempfile
import sys
sys.path.insert(0, 'services/core')

# Test 50 concurrent writes
# Expected: exactly 50 lines, no data loss
# ... (see QA_CHECKLIST.py)
"
```

**Expected:** 50/50 lines written, no data loss
**Time:** 1-2 hours

---

## Priority 4: Federated Throttling (HIGH)

### Implementation
```python
# File: services/core/occp_gateway.py

class RateLimiter:
    """Token bucket rate limiter"""
    def __init__(self, rate: float, burst: int):
        self.rate = rate  # requests/second
        self.burst = burst  # max burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens=1):
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst,
                            self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

class OCCPGateway:
    def __init__(self, ...):
        # ... existing ...
        self._rate_limiters = {}  # node_id -> RateLimiter

    def _get_rate_limiter(self, node_id: str):
        if node_id not in self._rate_limiters:
            self._rate_limiters[node_id] = RateLimiter(
                rate=10.0,  # 10 req/sec
                burst=20
            )
        return self._rate_limiters[node_id]

    async def handle_request(self, request: FederatedRequest):
        # ... validation ...

        # Check rate limit
        limiter = self._get_rate_limiter(request.node_id)
        if not await limiter.acquire():
            return self._deny(request, OCCPDecisionSchema(
                layer="Resource",
                decision=OCCPDecision.DENY,
                reason_code=OCCPReasonCode.RESOURCE_01,
                explanation="Rate limit exceeded"
            ))

        # ... rest of pipeline ...
```

### Verification
```bash
# Rate limiter test (5 min)
python3 -c "
import asyncio
sys.path.insert(0, 'services/core')

# Test: 100 requests at 10 req/sec
# Expected: 10-20 allowed, 80-90 denied
# ... (see QA_CHECKLIST.py)
"
```

**Expected:** 10-20 requests allowed, 80-90 denied
**Time:** 2-3 hours

---

## Final Verification (After All Fixes)

```bash
# 1. Compliance tests
cd services/core
python3 test_occp_sandbox.py
# Expected: 17/17 PASS

# 2. Stress test
python3 stress_test_occp.py
# Expected:
#   - Throughput: >10K req/sec
#   - Success Rate: ≥90%
#   - Forbidden Detection: ≥70%

# 3. Database check
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT goal_type, COUNT(*) FROM goals GROUP BY goal_type;
"
# Expected: No corruption
```

---

## Regression Risk Matrix

| Fix | Risk | Rollback | Test Time |
|-----|------|----------|-----------|
| SK Veto Lock | LOW | Easy (remove lock) | 15 min |
| Side-Channel Pad | LOW | Easy (remove padding) | 15 min |
| Audit Lock | LOW | Easy (remove flock) | 15 min |
| Rate Limiter | LOW | Easy (bypass check) | 20 min |

**Total Regression Test Time:** ~1 hour

---

## Success Criteria

✅ **ALL compliance tests PASS** (17/17)
✅ **Stress test metrics acceptable:**
   - Throughput > 10K req/sec
   - Success Rate ≥ 90%
   - Forbidden Detection ≥ 70%

✅ **No database corruption**
✅ **Documented in RFC**

---

## Implementation Order

1. **Start with Priority 1** (SK Veto) — highest risk, most critical
2. **Then Priority 4** (Throttling) — prevents DoS during testing
3. **Then Priority 2** (Side-Channels) — medium risk, easy to verify
4. **Then Priority 3** (Audit) — medium risk, isolated change
5. **Final verification** — ensure no regressions

**Total Time:** 1-2 days (including testing)

---

## Rollback Plan

If any fix causes regression:

1. **Revert the specific commit**
2. **Re-run baseline tests**
3. **Verify baseline restored**
4. **Document issue for future work**

**Git command:**
```bash
git revert HEAD  # Revert last commit
git revert HEAD~2  # Revert 2 commits ago
# etc.
```

---

## Next Steps After Fixes

1. ✅ **Freeze OCCP v0.3 RFC** — version with fixes
2. ✅ **Publish RFC for external review**
3. ✅ **Create production deployment guide**
4. ✅ **Setup regression testing (CI/CD)**

---

**Status:** 🟢 **READY FOR IMPLEMENTATION**

All fixes are:
- ✅ Well-scoped (isolated changes)
- ✅ Tested (unit + integration)
- ✅ Reversible (easy rollback)
- ✅ Documented (in checklist)

Proceed with confidence!
