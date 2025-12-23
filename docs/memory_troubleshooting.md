# Application Memory Issues and Troubleshooting

This guide covers memory management issues in production applications.

## Understanding Memory Usage

### JVM Memory (Java Applications)

The JVM divides memory into several regions:

- **Heap**: Where objects are allocated
  - Young Generation (Eden, Survivor spaces)
  - Old Generation (Tenured)
- **Metaspace**: Class metadata storage
- **Native Memory**: JNI, threads, buffers

### Container Memory

When running in containers:
- Container memory limit = JVM heap + metaspace + native memory + OS overhead
- Recommended: Set heap to 50-75% of container memory

## Common Memory Problems

### Memory Leaks

**Symptoms:**
- Gradual memory increase over time
- Eventually OOMKilled or OutOfMemoryError
- Performance degradation before crash

**Common Causes:**
- Unclosed resources (connections, streams)
- Growing collections without bounds
- Listener/callback not removed
- ThreadLocal not cleaned up

**Diagnosis:**
```bash
# Java: Take heap dump
jmap -dump:live,format=b,file=heap.hprof <pid>

# Analyze with tools
jhat heap.hprof
# Or use Eclipse MAT, VisualVM

# Python: Memory profiling
pip install memory_profiler
python -m memory_profiler script.py
```

### Heap Size Issues

**Too Small Heap:**
- Frequent garbage collection
- High CPU usage for GC
- Slow application response

**Too Large Heap:**
- Long GC pauses
- Container killed if exceeds limit
- Resource waste

**Tuning Guidelines:**
```bash
# Java heap settings
java -Xms2g -Xmx2g -XX:+UseG1GC -jar app.jar

# Container-aware settings (Java 11+)
java -XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -jar app.jar
```

### GC Pressure

**Symptoms:**
- High GC pause times
- Application stuttering
- CPU spikes during GC

**Diagnosis:**
```bash
# Enable GC logging
java -Xlog:gc*:file=gc.log:time -jar app.jar

# Analyze GC logs
# Look for:
# - Full GC frequency
# - Pause times
# - Memory reclaimed
```

**Solutions:**
- Increase heap size
- Tune GC settings
- Reduce object allocation rate
- Use object pooling

## Memory Monitoring

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Heap Used | Current heap usage | > 80% of max |
| GC Time | Time spent in GC | > 5% of total |
| GC Count | Number of GC events | Sudden spike |
| Old Gen | Old generation usage | Growing trend |

### Monitoring Commands

```bash
# Java memory usage
jstat -gc <pid> 1000

# Container memory
docker stats <container>

# Linux system memory
free -m
cat /proc/meminfo

# Process memory
ps aux --sort=-%mem | head -20
```

## Container Memory Configuration

### Kubernetes Memory Settings

```yaml
resources:
  requests:
    memory: "2Gi"
  limits:
    memory: "4Gi"
```

**Best Practices:**
- Set limits to prevent noisy neighbors
- Requests should match typical usage
- Leave headroom for garbage collection
- Monitor actual usage and adjust

### OOMKilled Prevention

When containers are OOMKilled:

1. Check if memory limit is appropriate
2. Review application memory configuration
3. Look for memory leaks
4. Consider vertical scaling

```bash
# Check why pod was killed
kubectl describe pod <name> | grep -A 5 "Last State"

# View container memory usage
kubectl top pod <name>
```

## Quick Troubleshooting Guide

1. **Is it a leak or just high usage?**
   - Monitor memory over time
   - Does it grow continuously or plateau?

2. **Where is memory going?**
   - Take heap dump
   - Analyze largest objects
   - Check for collection growth

3. **Is GC working efficiently?**
   - Check GC logs
   - Look at pause times
   - Verify memory is being reclaimed

4. **Container vs Application issue?**
   - Compare container limit to app config
   - Check for native memory usage
   - Review all memory components

## Prevention Best Practices

- Use bounded collections (queues, caches)
- Implement proper resource cleanup
- Set appropriate memory limits
- Monitor memory metrics continuously
- Profile during development
- Load test with realistic data
