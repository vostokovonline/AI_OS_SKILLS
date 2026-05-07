# AI_OS - Immediate Action Plan
**Priority:** CRITICAL tasks for next 2 weeks

---

## 📊 System Analysis Summary

### Current State
```
✅ 1,556 Python files (644K LOC)
✅ 2,414 TypeScript files (126K LOC)
✅ 18 Docker containers running
✅ 183 API endpoints
✅ 3 Dashboard versions operational
✅ CogOS running with self-improvement
✅ Low technical debt (36 TODOs)
```

### Critical Issues
```
🔴 main.py = 7,516 lines (needs refactoring)
🔴 No test coverage reporting
🔴 No authentication on dashboards
🔴 LiteLLM container unhealthy
🔴 No rate limiting
🔴 No centralized logging
```

---

## 🎯 Week 1: Code Refactoring

### Day 1-2: Split main.py

**Goal:** Reduce main.py from 7,516 to <1,000 lines

**Tasks:**
```bash
# 1. Create new module structure
mkdir -p /home/onor/ai_os_final/services/core/api
cd /home/onor/ai_os_final/services/core/api

# Create module files
touch routes.py        # API route definitions
touch handlers.py      # Request handlers
touch middleware.py    # Custom middleware
touch dependencies.py  # Dependency injection
```

**Files to extract from main.py:**
1. All `@app.get`, `@app.post` routes → `routes.py`
2. All handler functions → `handlers.py`
3. All middleware → `middleware.py`
4. All dependencies → `dependencies.py`

**Estimated time:** 8-10 hours

---

### Day 3: Remove Dead Code

**Files to delete:**
```bash
cd /home/onor/ai_os_final/services/dashboard
rm -f app.py.backup app_backup.py app_current.py app_old.py
rm -f app_broken.py app_broken2.py

cd /home/onor/ai_os_final/services/core
# Find and remove backup files
find . -name "*_backup*" -o -name "*_old*" -o -name "*.bak"
```

**Estimated time:** 2 hours

---

### Day 4-5: Consolidate Dependencies

**Python:**
```bash
# Create single requirements.txt
cd /home/onor/ai_os_final
cat services/*/requirements.txt ai_os/*/requirements.txt 2>/dev/null | \
  sort -u > requirements.txt

# Remove duplicates, pin versions
```

**TypeScript:**
```bash
# Use npm workspaces
cd /home/onor/ai_os_final/services/dashboard_v2
# Add to package.json:
"workspaces": ["../dashboard_v2", "../../ai_os/*"]
```

**Estimated time:** 6 hours

---

## 🎯 Week 2: Testing Infrastructure

### Day 1-2: Setup pytest

**Install:**
```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock
```

**Create pytest.ini:**
```ini
# /home/onor/ai_os_final/pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --cov=services/core
    --cov=ai_os
    --cov-report=html
    --cov-report=term-missing
    --asyncio-mode=auto
```

**Estimated time:** 4 hours

---

### Day 3-5: Write First Tests

**Target:** 20 unit tests

**Test files to create:**
```python
# tests/unit/test_api_status.py
async def test_api_status():
    response = await client.get("/api/status")
    assert response.status_code == 200
    assert response.json()["status"] == "running"

# tests/unit/test_goals.py
async def test_get_goals():
    response = await client.get("/api/goals")
    assert response.status_code == 200
    assert "goals" in response.json()

# tests/unit/test_cognitive_os.py
def test_cogos_start():
    from ai_os.cognitive_os import start_kernel
    start_kernel()
    # Assert running
```

**Estimated time:** 12 hours

---

## 🎯 Week 3: Monitoring

### Day 1: Fix LiteLLM

**Check logs:**
```bash
docker logs ns_litellm --tail 100
```

**Common fixes:**
```bash
# Restart with correct config
docker restart ns_litellm

# Check health endpoint
curl http://localhost:4000/health
```

**Estimated time:** 2 hours

---

### Day 2-3: Add Prometheus

**Install in core:**
```bash
pip install prometheus-fastapi-instrumentator
```

**Add to main.py:**
```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

**Add to docker-compose.yml:**
```yaml
prometheus:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

**Estimated time:** 6 hours

---

### Day 4-5: Setup Grafana

**Add to docker-compose.yml:**
```yaml
grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
  volumes:
    - grafana_data:/var/lib/grafana
```

**Import dashboards:**
- FastAPI Dashboard (ID: 10860)
- Prometheus Stats (ID: 2)
- Docker Dashboard (ID: 179)

**Estimated time:** 6 hours

---

## 🎯 Week 4: Security Hardening

### Day 1-2: Add Authentication

**Install:**
```bash
pip install python-jose[cryptography] passlib[bcrypt]
```

**Create auth module:**
```python
# services/core/auth.py
from jose import JWTError, jwt

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

def create_access_token(data: dict):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

**Estimated time:** 8 hours

---

### Day 3-4: Add Rate Limiting

**Install:**
```bash
pip install slowapi
```

**Add to main.py:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/status")
@limiter.limit("100/minute")
async def api_status(request: Request):
    ...
```

**Estimated time:** 4 hours

---

### Day 5: Add Audit Logging

**Create audit module:**
```python
# services/core/audit.py
import logging
from datetime import datetime

audit_logger = logging.getLogger("audit")

def log_action(user_id: str, action: str, resource: str, details: dict = None):
    audit_logger.info({
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "action": action,
        "resource": resource,
        "details": details or {}
    })
```

**Estimated time:** 4 hours

---

## 📈 Success Criteria

### Week 1 (Refactoring)
- [ ] main.py < 1,000 lines
- [ ] No backup files
- [ ] Single requirements.txt
- [ ] All tests passing

### Week 2 (Testing)
- [ ] pytest configured
- [ ] 20+ unit tests
- [ ] Coverage report generated
- [ ] CI pipeline working

### Week 3 (Monitoring)
- [ ] LiteLLM healthy
- [ ] Prometheus collecting metrics
- [ ] Grafana dashboards working
- [ ] Alerts configured

### Week 4 (Security)
- [ ] JWT authentication working
- [ ] Rate limiting active
- [ ] Audit logging enabled
- [ ] Security scan passed

---

## 🚀 Quick Wins (Do Today)

1. **Restart unhealthy containers:**
   ```bash
   docker restart ns_litellm
   ```

2. **Check disk space:**
   ```bash
   df -h
   docker system df
   ```

3. **Backup current state:**
   ```bash
   tar -czf ai_os_backup_$(date +%Y%m%d).tar.gz \
     --exclude='infra/*_data' \
     --exclude='venv' \
     --exclude='node_modules' \
     /home/onor/ai_os_final
   ```

4. **Update documentation:**
   ```bash
   echo "## Last Updated: $(date)" >> README.md
   ```

---

## 📞 Support & Resources

### Documentation
- [STRATEGIC_ROADMAP_2026.md](./STRATEGIC_ROADMAP_2026.md) - Full roadmap
- [SYSTEM_STATUS.md](./SYSTEM_STATUS.md) - Current status
- [FIXES_COMPLETE.md](./FIXES_COMPLETE.md) - Recent fixes

### Key Contacts
- Core API: `services/core/main.py`
- Dashboard v1: `services/dashboard/app.py`
- Dashboard v2: `services/dashboard_v2/src/`
- Dashboard v3: `ai_os/dashboard/`
- CogOS: `ai_os/cognitive_os/`

### Monitoring URLs
- Dashboard v1: http://localhost:8501/
- Dashboard v2: http://localhost:3000/
- Dashboard v3: http://localhost:8081/
- Core API: http://localhost:8000/docs
- Prometheus: http://localhost:9090/ (after setup)
- Grafana: http://localhost:3000/ (after setup)

---

**Last Updated:** 2026-03-13  
**Next Review:** Daily standups at 10:00
