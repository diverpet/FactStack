# Database Connection Pool Issues

This document covers troubleshooting database connection pool problems in production applications.

## Understanding Connection Pools

A connection pool maintains a cache of database connections that can be reused, reducing the overhead of creating new connections for each request.

### Key Metrics

- **Active Connections**: Number of connections currently in use
- **Idle Connections**: Connections available for use
- **Max Pool Size**: Maximum connections allowed
- **Wait Time**: Time requests wait for available connections

## Common Connection Pool Problems

### Connection Pool Exhaustion

**Symptoms:**
- Application hangs or timeouts
- "Cannot acquire connection from pool" errors
- Increasing response times

**Diagnosis Steps:**
1. Check current connections: `SELECT count(*) FROM pg_stat_activity;`
2. Monitor pool metrics via application metrics endpoint
3. Review connection leak warnings in logs

**Solutions:**
- Increase max pool size (carefully)
- Implement connection timeout
- Fix connection leaks in application code
- Use connection validation queries

### Connection Leaks

Connection leaks occur when connections are not properly returned to the pool.

**Common Causes:**
- Missing `finally` blocks to close connections
- Exceptions before connection close
- Not using try-with-resources (Java)

**Detection:**
```sql
-- PostgreSQL: Find long-running idle connections
SELECT pid, usename, application_name, state, query_start 
FROM pg_stat_activity 
WHERE state = 'idle' 
AND query_start < NOW() - INTERVAL '5 minutes';
```

**Prevention:**
- Always use try-with-resources or context managers
- Set connection timeout in pool config
- Enable leak detection logging

### Stale Connections

**Symptoms:**
- "Connection reset" errors
- Intermittent query failures
- Errors after period of inactivity

**Causes:**
- Firewall closing idle connections
- Database server restarts
- Network issues

**Solutions:**
- Enable connection validation on borrow
- Configure validation query: `SELECT 1`
- Set appropriate idle timeout
- Enable keepalive settings

## Configuration Best Practices

### Recommended Pool Settings

```yaml
# Connection pool configuration
pool:
  min-idle: 5
  max-active: 20
  max-wait: 30000  # 30 seconds
  validation-query: "SELECT 1"
  test-on-borrow: true
  test-while-idle: true
  time-between-eviction-runs: 60000  # 1 minute
  min-evictable-idle-time: 300000  # 5 minutes
```

### Sizing Guidelines

- **Small Application**: min=2, max=10
- **Medium Application**: min=5, max=20
- **High Traffic Application**: min=10, max=50

Formula: `connections = (core_count * 2) + effective_spindle_count`

## Monitoring Connection Pools

### Key Metrics to Watch

1. **Pool utilization**: active/max ratio
2. **Wait times**: How long requests wait for connections
3. **Connection creation rate**: Indicates pool churn
4. **Validation failures**: Connection health issues

### Alerting Thresholds

- Pool utilization > 80%: Warning
- Pool utilization > 95%: Critical
- Wait time > 5 seconds: Warning
- Connection creation spikes: Investigate

## Troubleshooting Commands

### PostgreSQL

```sql
-- Current connections
SELECT count(*), state FROM pg_stat_activity GROUP BY state;

-- Connections by application
SELECT application_name, count(*) 
FROM pg_stat_activity 
GROUP BY application_name;

-- Kill idle connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' 
AND query_start < NOW() - INTERVAL '10 minutes';
```

### MySQL

```sql
-- Show all connections
SHOW PROCESSLIST;

-- Connection status
SHOW STATUS LIKE 'Threads%';

-- Kill connection
KILL CONNECTION <id>;
```
