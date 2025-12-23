# Service Deployment Runbook

This runbook provides step-by-step procedures for deploying services to production.

## Pre-Deployment Checklist

Before starting any deployment, verify:

- [ ] All tests passing in CI pipeline
- [ ] Code review approved
- [ ] Changelog updated
- [ ] Database migrations tested (if applicable)
- [ ] Rollback plan documented
- [ ] Monitoring alerts configured
- [ ] On-call engineer notified

## Standard Deployment Procedure

### Step 1: Prepare the Release

```bash
# Tag the release
git tag -a v1.x.x -m "Release v1.x.x"
git push origin v1.x.x

# Build the container image
docker build -t myapp:v1.x.x .
docker push registry.example.com/myapp:v1.x.x
```

### Step 2: Deploy to Staging

```bash
# Update staging deployment
kubectl set image deployment/myapp myapp=registry.example.com/myapp:v1.x.x -n staging

# Wait for rollout
kubectl rollout status deployment/myapp -n staging --timeout=300s

# Run smoke tests
./scripts/smoke-test.sh staging
```

### Step 3: Verify Staging

1. Check application logs for errors
2. Verify key metrics in dashboard
3. Test critical user flows manually
4. Wait for minimum soak time (15 minutes)

### Step 4: Production Deployment

```bash
# Deploy to production (canary first)
kubectl set image deployment/myapp-canary myapp=registry.example.com/myapp:v1.x.x -n production

# Monitor canary (wait 10 minutes)
watch kubectl get pods -n production -l app=myapp-canary

# If canary healthy, proceed with full rollout
kubectl set image deployment/myapp myapp=registry.example.com/myapp:v1.x.x -n production

# Monitor rollout
kubectl rollout status deployment/myapp -n production --timeout=600s
```

### Step 5: Post-Deployment Verification

1. Verify all pods are running and healthy
2. Check error rates in monitoring
3. Verify no increase in latency
4. Confirm critical functionality
5. Update deployment log

## Rollback Procedure

### Immediate Rollback

If critical issues are detected:

```bash
# Rollback to previous version
kubectl rollout undo deployment/myapp -n production

# Verify rollback
kubectl rollout status deployment/myapp -n production

# Check pod status
kubectl get pods -n production -l app=myapp
```

### Rollback to Specific Version

```bash
# List rollout history
kubectl rollout history deployment/myapp -n production

# Rollback to specific revision
kubectl rollout undo deployment/myapp -n production --to-revision=<revision>
```

## Database Migration Procedure

### Before Migration

1. Create database backup
2. Test migration on staging database
3. Estimate migration duration
4. Schedule maintenance window if needed

### Migration Steps

```bash
# Create backup
pg_dump -h db.example.com -U admin mydb > backup_$(date +%Y%m%d).sql

# Run migration
./manage.py migrate --plan  # Preview
./manage.py migrate         # Execute

# Verify migration
./manage.py showmigrations
```

### Migration Rollback

```bash
# Rollback last migration
./manage.py migrate myapp <previous_migration>

# Or restore from backup
psql -h db.example.com -U admin mydb < backup_YYYYMMDD.sql
```

## Emergency Procedures

### Service Degradation

1. Enable circuit breakers
2. Scale up healthy instances
3. Redirect traffic if needed
4. Engage incident response

### Complete Service Outage

1. **Assess**: Check all dependencies
2. **Communicate**: Update status page
3. **Isolate**: Remove from load balancer
4. **Diagnose**: Review logs and metrics
5. **Fix or Rollback**: Apply fix or rollback
6. **Verify**: Confirm service recovery
7. **Post-mortem**: Document incident

## Contact Information

- **On-Call Engineer**: Check PagerDuty
- **Platform Team**: #platform-support
- **Database Team**: #database-oncall
- **Security Team**: #security-incidents
