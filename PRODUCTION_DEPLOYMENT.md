# AI_OS Production Deployment Guide

**Version:** 3.0.0  
**Date:** 2026-03-14  
**Status:** Production Ready

---

## 🚀 Quick Start

### Development Mode

```bash
# Start API server (no auth, no rate limiting)
python3 -m ai_os.control_api_server --port 8000

# Start frontend
cd ai_os/dashboard/frontend
npm install
npm start
```

### Production Mode

```bash
# Start API server (with auth, rate limiting, monitoring)
python3 -m ai_os.control_api_server --prod --port 8000

# Build and serve frontend
cd ai_os/dashboard/frontend
npm install
npm run build
npx serve -s build -l 3000
```

---

## 🔐 Production Features

### 1. Authentication (JWT)

**Enabled in production mode.**

**Default credentials:**
```
Username: admin
Password: admin
```

**⚠️ Change immediately in production!**

**Login:**
```bash
curl -X POST "http://localhost:8000/api/v2/auth/login?username=admin&password=admin"
```

**Response:**
```json
{
  "token": "abc123...",
  "expires_in": 86400
}
```

**Use token:**
```bash
curl -H "Authorization: Bearer abc123..." http://localhost:8000/api/v2/system/health
```

**Logout:**
```bash
curl -X POST -H "Authorization: Bearer abc123..." http://localhost:8000/api/v2/auth/logout
```

**Get current user:**
```bash
curl -H "Authorization: Bearer abc123..." http://localhost:8000/api/v2/auth/me
```

---

### 2. Rate Limiting

**Enabled in production mode.**

**Default limits:**

| User Type | Requests | Window |
|-----------|----------|--------|
| Anonymous | 100 | 1 minute |
| Authenticated | 500 | 1 minute |
| Admin | 1000 | 1 minute |

**Rate limit headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 60
```

**429 Response:**
```json
{
  "detail": "Rate limit exceeded",
  "limit": 100,
  "remaining": 0,
  "reset_seconds": 60
}
```

---

### 3. Monitoring & Metrics

**Enabled in production mode.**

**Get metrics:**
```bash
curl http://localhost:8000/api/v2/metrics
```

**Response:**
```json
{
  "uptime_seconds": 3600,
  "requests": {
    "total": 1234,
    "success": 1200,
    "error": 34,
    "success_rate": 0.972
  },
  "by_endpoint": {
    "/system/health": 500,
    "/capabilities": 300,
    ...
  },
  "response_times": {
    "avg_ms": 45.2,
    "p95_ms": 120.5
  },
  "rate_limiting": {
    "total_limited": 5
  },
  "authentication": {
    "failures": 3
  }
}
```

---

### 4. Logging

**Enabled in production mode.**

**Log files:**
```
./logs/
└── api.log
```

**Log format:**
```
2026-03-14 10:30:00 - ai_os.control_api - INFO - Production logging configured
2026-03-14 10:30:05 - ai_os.control_api - INFO - Generated token for user: admin
2026-03-14 10:30:10 - ai_os.control_api - WARNING - Rate limit exceeded for user: anonymous
```

---

## 📋 Deployment Checklist

### Pre-Deployment

- [ ] Change default admin password
- [ ] Configure CORS for production domain
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Set up monitoring alerts

### Deployment

- [ ] Install dependencies
- [ ] Set environment variables
- [ ] Start API server with `--prod` flag
- [ ] Build and deploy frontend
- [ ] Configure reverse proxy (nginx)
- [ ] Enable HTTPS
- [ ] Test authentication
- [ ] Test rate limiting
- [ ] Verify metrics endpoint

### Post-Deployment

- [ ] Verify all endpoints working
- [ ] Check logs for errors
- [ ] Monitor metrics
- [ ] Test failover procedures
- [ ] Document deployment details

---

## 🔧 Configuration

### Environment Variables

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_PRODUCTION=true

# Authentication
AUTH_SECRET_KEY=your-secret-key-here
AUTH_TOKEN_EXPIRY=86400  # 24 hours

# Rate Limiting
RATE_LIMIT_DEFAULT=100
RATE_LIMIT_AUTHENTICATED=500
RATE_LIMIT_ADMIN=1000

# CORS
CORS_ORIGINS=http://localhost:3000,https://your-domain.com

# Logging
LOG_LEVEL=INFO
LOG_DIR=./logs
```

### Production Server Configuration

**systemd service:**
```ini
[Unit]
Description=AI_OS Control API Server
After=network.target

[Service]
Type=simple
User=ai_os
WorkingDirectory=/opt/ai_os
Environment="PATH=/opt/ai_os/venv/bin"
ExecStart=/opt/ai_os/venv/bin/python -m ai_os.control_api_server --prod --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**nginx reverse proxy:**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/your-cert.crt;
    ssl_certificate_key /etc/ssl/private/your-key.key;

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 📊 Monitoring

### Prometheus Metrics

**Endpoint:** `/api/v2/metrics`

**Key metrics to monitor:**

1. **Request Rate**
   - `requests.total` - Total requests
   - `requests.success_rate` - Success rate

2. **Response Times**
   - `response_times.avg_ms` - Average response time
   - `response_times.p95_ms` - 95th percentile

3. **Errors**
   - `requests.error` - Error count
   - `authentication.failures` - Auth failures

4. **Rate Limiting**
   - `rate_limiting.total_limited` - Rate limited requests

### Alerting Rules

**High Error Rate:**
```yaml
alert: HighErrorRate
expr: rate(requests_error[5m]) / rate(requests_total[5m]) > 0.05
for: 5m
labels:
  severity: critical
annotations:
  summary: High error rate detected
```

**High Response Time:**
```yaml
alert: HighResponseTime
expr: response_times_p95_ms > 500
for: 5m
labels:
  severity: warning
annotations:
  summary: High response time detected
```

---

## 🔒 Security

### Best Practices

1. **Change default credentials immediately**
   ```bash
   # Generate new admin token
   python3 -c "from services.control_api.production_middleware import JWTAuthentication; auth = JWTAuthentication(); print(auth.generate_token('admin', ['admin']))"
   ```

2. **Use HTTPS in production**
   - Obtain SSL certificate (Let's Encrypt)
   - Configure nginx for HTTPS
   - Redirect HTTP to HTTPS

3. **Enable firewall**
   ```bash
   ufw allow 443/tcp  # HTTPS
   ufw allow 22/tcp   # SSH
   ufw enable
   ```

4. **Regular updates**
   ```bash
   pip install --upgrade -r requirements.txt
   npm update --prefix ai_os/dashboard/frontend
   ```

5. **Backup data**
   ```bash
   # Backup metrics
   cp -r .api_metrics /backup/metrics_$(date +%Y%m%d)
   
   # Backup logs
   tar -czf /backup/logs_$(date +%Y%m%d).tar.gz ./logs
   ```

---

## 🐛 Troubleshooting

### Authentication Issues

**Problem:** Can't login

**Solution:**
```bash
# Check server logs
tail -f logs/api.log | grep auth

# Reset authentication
rm -rf .api_metrics
python3 -m ai_os.control_api_server --prod
```

### Rate Limiting Issues

**Problem:** Getting 429 errors

**Solution:**
```bash
# Check current limits
curl http://localhost:8000/api/v2/metrics | python3 -m json.tool

# Increase limits (edit production_middleware.py)
# Restart server
```

### Performance Issues

**Problem:** Slow response times

**Solution:**
```bash
# Check metrics
curl http://localhost:8000/api/v2/metrics

# Check logs for errors
grep ERROR logs/api.log

# Monitor system resources
top
df -h
```

---

## 📈 Performance Tuning

### Recommended Settings

**For high traffic:**

```python
# Increase rate limits
limiter.set_limit("authenticated", requests=1000, window=60)
limiter.set_limit("admin", requests=5000, window=60)

# Enable caching
# Use Redis for token storage
# Use CDN for frontend assets
```

**For low latency:**

```python
# Reduce token expiry
auth.token_expiry = timedelta(hours=1)

# Enable response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.0.0 | 2026-03-14 | Production release with auth, rate limiting, monitoring |
| 2.0.0 | 2026-03-13 | Control API with Cognitive Control endpoints |
| 1.0.0 | 2026-03-12 | Initial release |

---

## 📞 Support

**Documentation:** See README.md files in each component

**Issues:** Check logs in `./logs/api.log`

**Metrics:** Access at `http://localhost:8000/api/v2/metrics`

---

**Last Updated:** 2026-03-14  
**Status:** Production Ready ✅
