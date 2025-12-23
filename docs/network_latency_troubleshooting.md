# Network Latency Troubleshooting

This guide covers diagnosing and resolving network latency issues in distributed systems.

## Understanding Network Latency

Network latency is the time delay in data communication over a network. High latency affects application performance and user experience.

### Latency Components

- **Propagation Delay**: Time for signal to travel physical distance
- **Transmission Delay**: Time to push packet onto network
- **Processing Delay**: Router/switch processing time
- **Queuing Delay**: Time waiting in network buffers

## Diagnosing Latency Issues

### Basic Diagnostics

```bash
# Test connectivity and latency
ping -c 10 target.example.com

# Trace network path
traceroute target.example.com

# Detailed path analysis
mtr target.example.com

# TCP connection timing
curl -o /dev/null -w "Connect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" https://api.example.com/health
```

### Application-Level Latency

```bash
# HTTP timing breakdown
curl -w "@curl-format.txt" -o /dev/null https://api.example.com/endpoint

# Where curl-format.txt contains:
#   time_namelookup:  %{time_namelookup}
#   time_connect:     %{time_connect}
#   time_appconnect:  %{time_appconnect}
#   time_pretransfer: %{time_pretransfer}
#   time_starttransfer: %{time_starttransfer}
#   time_total:       %{time_total}
```

## Common Latency Causes

### DNS Resolution Delays

**Symptoms:**
- First requests slow, subsequent requests fast
- High `time_namelookup` in curl

**Solutions:**
- Use DNS caching (local resolver)
- Reduce DNS TTL for frequently changed records
- Use connection pooling to reuse connections

### TCP Connection Overhead

**Symptoms:**
- High `time_connect` values
- Performance improves with connection reuse

**Solutions:**
- Enable HTTP keep-alive
- Use connection pools
- Consider HTTP/2 multiplexing

### TLS Handshake Latency

**Symptoms:**
- High `time_appconnect` values
- Additional round trips for new connections

**Solutions:**
- Enable TLS session resumption
- Use TLS 1.3 for 0-RTT
- Implement connection pooling

### Bandwidth Saturation

**Symptoms:**
- Latency increases under load
- Packet loss during peak times

**Diagnosis:**
```bash
# Check interface statistics
netstat -i

# Monitor bandwidth
iftop -i eth0

# Check for packet drops
cat /proc/net/dev
```

## Performance Optimization

### Connection Pooling

Reuse existing connections to avoid:
- DNS lookup (per connection)
- TCP handshake (3-way)
- TLS handshake (additional round trips)

### Geographic Distribution

- Deploy services closer to users
- Use CDN for static content
- Implement regional routing

### Protocol Optimization

- Use HTTP/2 for multiplexing
- Enable compression (gzip, brotli)
- Minimize request size

## Monitoring Latency

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| P50 Latency | Median response time | > 100ms |
| P95 Latency | 95th percentile | > 500ms |
| P99 Latency | 99th percentile | > 1000ms |
| Error Rate | Failed requests | > 1% |

### Monitoring Commands

```bash
# Monitor response times
while true; do
  curl -o /dev/null -s -w "%{time_total}\n" https://api.example.com/health
  sleep 1
done

# Aggregate latency stats
ab -n 1000 -c 10 https://api.example.com/health
```

## Troubleshooting Checklist

1. **Identify the latency source**
   - DNS? TCP? TLS? Application?
   
2. **Check network path**
   - Run traceroute/mtr
   - Look for packet loss or high hop latency

3. **Review application metrics**
   - Database query times
   - External API calls
   - Cache hit rates

4. **Check infrastructure**
   - CPU utilization
   - Memory pressure
   - Network interface saturation

5. **Test with baseline**
   - Compare to known good state
   - Test from multiple locations
