# Incident Response Procedures

This document outlines the standard procedures for responding to production incidents.

## Incident Severity Levels

### SEV1 - Critical

**Definition:** Complete service outage or major data loss affecting all users.

**Response Time:** Immediate (within 5 minutes)
**Escalation:** Page on-call + engineering leadership
**Communication:** Status page update within 15 minutes

**Examples:**
- Production database down
- Payment processing failure
- Security breach detected
- Complete API unavailability

### SEV2 - High

**Definition:** Significant degradation affecting many users or critical feature broken.

**Response Time:** Within 15 minutes
**Escalation:** Page on-call engineer
**Communication:** Status page update within 30 minutes

**Examples:**
- 50%+ API error rate
- Major feature completely broken
- Significant performance degradation
- Partial data loss

### SEV3 - Medium

**Definition:** Minor service degradation or non-critical feature broken.

**Response Time:** Within 1 hour
**Escalation:** Slack notification to team
**Communication:** Internal update

**Examples:**
- Minor feature broken
- Slow response times (2-3x normal)
- Non-critical integration failure

### SEV4 - Low

**Definition:** Minor issues with workarounds available.

**Response Time:** Next business day
**Escalation:** Create ticket

## Incident Response Steps

### Step 1: Acknowledge and Assess

1. **Acknowledge the alert** within SLA
2. **Verify the incident** is real (not false alarm)
3. **Assess severity** using definitions above
4. **Create incident channel**: `#incident-YYYYMMDD-brief-description`

### Step 2: Communicate

```
INCIDENT DECLARED
Severity: SEV[1-4]
Impact: [Brief description of user impact]
Status: Investigating
Incident Commander: [Name]
Next Update: [Time]
```

### Step 3: Diagnose

**Initial Checks:**
1. Recent deployments?
2. Infrastructure changes?
3. Third-party service issues?
4. Traffic spike?

**Data Gathering:**
- Application logs
- Error rates
- Latency metrics
- Infrastructure metrics
- Recent changes

### Step 4: Mitigate

**Priority Order:**
1. Restore service (even partially)
2. Contain the blast radius
3. Prevent further damage
4. Then investigate root cause

**Common Mitigations:**
- Rollback recent deployment
- Scale up resources
- Enable circuit breakers
- Redirect traffic
- Disable problematic feature

### Step 5: Resolve and Verify

1. Implement fix or mitigation
2. Verify fix is working
3. Monitor for recurrence
4. Update status page
5. Close incident

### Step 6: Post-Incident

1. Schedule post-mortem (within 48 hours for SEV1/2)
2. Document timeline
3. Identify action items
4. Share learnings

## Communication Templates

### Status Page Update

```
[TIMESTAMP]
Status: [Investigating|Identified|Monitoring|Resolved]

We are currently [investigating/experiencing] [brief description].

Impact: [What users are affected, what's not working]

Next update in [X] minutes.
```

### Internal Update

```
Incident Update - [Timestamp]
Status: [Current status]
Impact: [User/business impact]
Cause: [Known/unknown cause]
Actions: [What we're doing]
Next Steps: [Planned actions]
ETA: [If known]
```

## Roles and Responsibilities

### Incident Commander

- Leads incident response
- Makes decisions on actions
- Coordinates communication
- Delegates tasks

### Technical Lead

- Leads technical investigation
- Proposes solutions
- Implements fixes

### Communications Lead

- Updates status page
- Coordinates with customer support
- Manages stakeholder communication

## Post-Mortem Template

```markdown
# Incident Post-Mortem: [Title]

## Summary
[1-2 sentence summary]

## Impact
- Duration: [X hours/minutes]
- Users affected: [Number/percentage]
- Revenue impact: [If applicable]

## Timeline
- [Time] - [Event]
- [Time] - [Event]
...

## Root Cause
[Detailed explanation]

## Resolution
[What fixed the issue]

## Action Items
- [ ] [Action] - Owner - Due Date
- [ ] [Action] - Owner - Due Date

## Lessons Learned
[What we learned]
```
