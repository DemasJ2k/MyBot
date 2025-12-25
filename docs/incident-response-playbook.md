# Incident Response Playbook

**Prompt 18 - Production Deployment**

This playbook provides guidance for responding to incidents affecting the Flowrex trading platform.

---

## Table of Contents

1. [Severity Levels](#severity-levels)
2. [Incident Response Process](#incident-response-process)
3. [Common Incidents](#common-incidents)
4. [Runbooks](#runbooks)
5. [Communication Templates](#communication-templates)
6. [Post-Incident](#post-incident)

---

## Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| **P0 - Critical** | Complete system outage, data loss, security breach | Immediate | All services down, trading blocked, credential leak |
| **P1 - High** | Partial outage, significant degradation | 15 minutes | Single service down, 50%+ error rate, trade failures |
| **P2 - Medium** | Minor degradation, non-critical feature broken | 1 hour | Slow responses, minor feature broken, warning alerts |
| **P3 - Low** | Cosmetic issues, nice-to-have features | Next business day | UI glitches, documentation errors |

### Escalation Matrix

| Severity | On-Call Engineer | Team Lead | Management |
|----------|------------------|-----------|------------|
| P0 | Immediate | Immediate | Within 15 min |
| P1 | Immediate | Within 15 min | Within 1 hour |
| P2 | Within 1 hour | If unresolved in 4h | N/A |
| P3 | Next business day | N/A | N/A |

---

## Incident Response Process

### 1. Detection

Incidents can be detected through:
- **Automated alerts**: Prometheus/Grafana, Sentry
- **User reports**: Support tickets, direct communication
- **Monitoring**: Dashboard anomalies, log patterns

### 2. Triage

1. **Assess severity** using the levels above
2. **Assign incident commander** (usually on-call engineer)
3. **Create incident channel**: `#incident-YYYYMMDD-HHMM`
4. **Page additional responders** (P0/P1 only)
5. **Start incident timeline** in the channel

### 3. Investigation

**Quick diagnostic commands:**

```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps

# Check recent logs
docker-compose -f docker-compose.prod.yml logs --tail=100 backend
docker-compose -f docker-compose.prod.yml logs --tail=100 frontend

# Check error logs specifically
docker-compose -f docker-compose.prod.yml logs backend 2>&1 | grep -i error

# Check database connectivity
docker-compose -f docker-compose.prod.yml exec postgres pg_isready

# Check Redis connectivity
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping

# Check resource usage
docker stats --no-stream
```

**Investigation checklist:**
- [ ] Check service health endpoints
- [ ] Review Grafana dashboards
- [ ] Check Sentry for new errors
- [ ] Review recent deployments
- [ ] Check external service status (TwelveData, brokers)
- [ ] Check infrastructure metrics (CPU, memory, disk)

### 4. Mitigation

**Immediate actions by severity:**

**P0/P1:**
- Enable maintenance mode if needed
- Scale up resources if capacity issue
- Rollback to previous version if deployment-related
- Block problematic traffic if attack

**P2/P3:**
- Apply hotfix if known issue
- Document workaround for users
- Schedule fix for next maintenance window

### 5. Resolution

1. **Deploy permanent fix** (if hotfix was temporary)
2. **Verify resolution** through health checks
3. **Monitor for regression** for 30+ minutes
4. **Update status page** and close incident channel

### 6. Post-Mortem

See [Post-Incident](#post-incident) section.

---

## Common Incidents

### Database Connection Pool Exhausted

**Symptoms:**
- `flowrex_database_connections` metric at max
- Slow API responses (>5s)
- 500 errors with "connection pool" in logs

**Investigation:**
```bash
# Check active connections
docker-compose -f docker-compose.prod.yml exec postgres \
    psql -U flowrex -c "SELECT count(*) FROM pg_stat_activity;"

# Check long-running queries
docker-compose -f docker-compose.prod.yml exec postgres \
    psql -U flowrex -c "SELECT pid, now() - query_start AS duration, query 
    FROM pg_stat_activity WHERE state = 'active' 
    ORDER BY duration DESC LIMIT 10;"

# Check blocked queries
docker-compose -f docker-compose.prod.yml exec postgres \
    psql -U flowrex -c "SELECT blocked_locks.pid AS blocked_pid,
    blocking_locks.pid AS blocking_pid, blocked_activity.query AS blocked_query
    FROM pg_catalog.pg_locks blocked_locks
    JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
    JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
    WHERE NOT blocked_locks.granted;"
```

**Mitigation:**
```bash
# Kill long-running queries (>5 minutes)
docker-compose -f docker-compose.prod.yml exec postgres \
    psql -U flowrex -c "SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE state = 'active' AND now() - query_start > interval '5 minutes';"

# Restart backend to reset connection pool
docker-compose -f docker-compose.prod.yml restart backend
```

---

### High Error Rate (5xx Errors)

**Symptoms:**
- Error rate > 5% on Grafana
- Sentry alerts
- User reports of failures

**Investigation:**
```bash
# Check recent errors
docker-compose -f docker-compose.prod.yml logs --tail=200 backend | grep -i "error\|exception"

# Check error distribution
docker-compose -f docker-compose.prod.yml logs backend 2>&1 | grep "HTTP" | awk '{print $NF}' | sort | uniq -c

# Check Sentry for stack traces
# https://sentry.io/organizations/flowrex/issues/
```

**Mitigation:**
- If known bug: Deploy hotfix
- If external service: Check status page, implement circuit breaker
- If unknown: Rollback to previous version

```bash
# Quick rollback
./scripts/rollback.sh <previous_version>
```

---

### Trade Execution Failures

**Symptoms:**
- `flowrex_trades_failed_total` increasing
- User reports trades not executing
- Alerts on trade failure rate

**Investigation:**
```bash
# Check recent failed trades
docker-compose -f docker-compose.prod.yml exec postgres \
    psql -U flowrex -c "SELECT id, symbol, side, status, error_message, created_at 
    FROM trades WHERE status = 'failed' 
    ORDER BY created_at DESC LIMIT 20;"

# Check broker connectivity
docker-compose -f docker-compose.prod.yml exec backend \
    python -c "from app.execution.adapters import get_adapter; 
    import asyncio; 
    adapter = get_adapter(); 
    print(asyncio.run(adapter.check_connection()))"

# Check risk engine blocks
docker-compose -f docker-compose.prod.yml logs backend | grep -i "risk\|blocked\|rejected"
```

**Mitigation:**
- Check broker API status pages
- Verify API credentials haven't expired
- Check if risk limits are being hit legitimately
- Contact broker support if persistent

---

### WebSocket Disconnections

**Symptoms:**
- `flowrex_websocket_connections` dropping
- Users report real-time updates not working
- Frontend shows "disconnected" status

**Investigation:**
```bash
# Check WebSocket errors in logs
docker-compose -f docker-compose.prod.yml logs backend | grep -i "websocket"

# Check NGINX WebSocket configuration
docker-compose -f docker-compose.prod.yml exec nginx cat /etc/nginx/nginx.conf | grep -A 20 "location /ws"

# Check backend memory (WebSocket can leak)
docker stats flowrex-backend --no-stream
```

**Mitigation:**
```bash
# Restart backend with graceful WebSocket close
docker-compose -f docker-compose.prod.yml restart backend

# If NGINX issue, reload config
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

### High Memory Usage

**Symptoms:**
- Memory > 85% on Grafana
- OOM kills in container logs
- Services becoming unresponsive

**Investigation:**
```bash
# Check container memory
docker stats --no-stream

# Check for memory leaks (compare over time)
docker-compose -f docker-compose.prod.yml exec backend \
    python -c "import tracemalloc; tracemalloc.start(); 
    # ... run for a while ...
    snapshot = tracemalloc.take_snapshot(); 
    top_stats = snapshot.statistics('lineno')[:10];
    print(top_stats)"

# Check Redis memory
docker-compose -f docker-compose.prod.yml exec redis redis-cli INFO memory
```

**Mitigation:**
```bash
# Clear Redis cache if needed
docker-compose -f docker-compose.prod.yml exec redis redis-cli FLUSHDB

# Restart service to free memory
docker-compose -f docker-compose.prod.yml restart backend

# Scale up replicas to distribute load
docker-compose -f docker-compose.prod.yml up -d --scale backend=7
```

---

### SSL Certificate Expiry

**Symptoms:**
- SSL warnings in browser
- Monitoring alerts on certificate expiry
- Connection failures from clients

**Mitigation:**
```bash
# Check certificate expiry
openssl s_client -connect flowrex.app:443 -servername flowrex.app 2>/dev/null | openssl x509 -noout -dates

# Renew Let's Encrypt certificates
docker-compose -f docker-compose.prod.yml run --rm certbot renew

# Reload NGINX
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## Runbooks

### Service Restart Procedure

```bash
# 1. Check current status
docker-compose -f docker-compose.prod.yml ps

# 2. Graceful restart (zero-downtime)
docker-compose -f docker-compose.prod.yml up -d --scale backend=6 backend
sleep 30
docker-compose -f docker-compose.prod.yml up -d --scale backend=5 backend

# 3. Verify health
curl -f http://localhost:8000/health/ready
```

### Emergency Database Restore

```bash
# 1. Stop application
docker-compose -f docker-compose.prod.yml stop backend frontend

# 2. List available backups
ls -la backups/postgres/

# 3. Restore from backup
./scripts/rollback.sh <version> <backup_name>

# 4. Restart services
docker-compose -f docker-compose.prod.yml up -d
```

### Enable Maintenance Mode

```bash
# Update NGINX to serve maintenance page
cat > nginx/maintenance.html << 'EOF'
<!DOCTYPE html>
<html>
<head><title>Maintenance</title></head>
<body>
<h1>Scheduled Maintenance</h1>
<p>Flowrex is currently undergoing maintenance. Please check back shortly.</p>
</body>
</html>
EOF

# Enable maintenance mode in NGINX config
# Add: return 503; to server block

docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## Communication Templates

### Initial Incident Notification

```
🚨 INCIDENT DETECTED

Severity: P[X]
Service: [affected service]
Impact: [user impact description]
Started: [HH:MM UTC]

Investigation in progress. Updates to follow.
```

### Status Update

```
📋 INCIDENT UPDATE

Status: [Investigating/Identified/Mitigating/Resolved]
Impact: [current user impact]
Root Cause: [if known]
ETA: [estimated resolution time]

Next update in [X] minutes.
```

### Resolution Notification

```
✅ INCIDENT RESOLVED

Duration: [total time]
Impact: [summary of impact]
Root Cause: [brief description]
Resolution: [what was done]

Post-mortem scheduled for [date/time].
```

---

## Post-Incident

### Post-Mortem Template

```markdown
# Post-Mortem: [Incident Title]

**Date:** YYYY-MM-DD
**Duration:** HH:MM - HH:MM UTC (X hours Y minutes)
**Severity:** P[X]
**Author:** [name]

## Summary
[1-2 sentence summary of what happened]

## Timeline
- HH:MM - [event]
- HH:MM - [event]
- HH:MM - [event]

## Root Cause
[Detailed explanation of what caused the incident]

## Impact
- Users affected: [number/percentage]
- Revenue impact: [if applicable]
- Data loss: [if any]

## Detection
How was the incident detected? How could we detect it faster?

## Response
What went well? What could be improved?

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| [action] | [owner] | [date] | [status] |

## Lessons Learned
[Key takeaways for the team]
```

### Post-Mortem Meeting Agenda

1. **Timeline review** (10 min)
2. **Root cause analysis** (15 min)
3. **Impact assessment** (5 min)
4. **Response review** (10 min)
5. **Action items** (15 min)
6. **Lessons learned** (5 min)

---

## Appendix

### Useful Commands Cheat Sheet

```bash
# Service management
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f [service]
docker-compose -f docker-compose.prod.yml restart [service]
docker-compose -f docker-compose.prod.yml exec [service] [command]

# Database
docker-compose -f docker-compose.prod.yml exec postgres psql -U flowrex
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U flowrex flowrex > backup.sql

# Redis
docker-compose -f docker-compose.prod.yml exec redis redis-cli
docker-compose -f docker-compose.prod.yml exec redis redis-cli INFO

# Logs
docker-compose -f docker-compose.prod.yml logs --tail=100 -f
docker-compose -f docker-compose.prod.yml logs --since="1h" backend

# Metrics
curl http://localhost:8000/metrics
curl http://localhost:9090/api/v1/query?query=up
```

### Contact Information

| Role | Contact |
|------|---------|
| On-Call Primary | [phone/slack] |
| On-Call Secondary | [phone/slack] |
| Team Lead | [phone/slack] |
| Database Admin | [phone/slack] |
| Security | [phone/slack] |

### External Service Status Pages

- TwelveData: https://status.twelvedata.com
- OANDA: https://www.oanda.com/system-status
- AWS: https://status.aws.amazon.com
- Cloudflare: https://www.cloudflarestatus.com
