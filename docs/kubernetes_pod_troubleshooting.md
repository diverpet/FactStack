# Kubernetes Pod Troubleshooting Guide

This guide covers common issues and solutions for Kubernetes pod problems in production environments.

## Common Pod States

### CrashLoopBackOff

When a pod enters CrashLoopBackOff state, the container is repeatedly crashing and Kubernetes is backing off before restarting it.

**Diagnosis Steps:**
1. Check pod logs: `kubectl logs <pod-name> --previous`
2. Describe the pod: `kubectl describe pod <pod-name>`
3. Check resource limits: `kubectl get pod <pod-name> -o yaml | grep -A 10 resources`

**Common Causes:**
- Application startup failure
- Missing configuration or secrets
- Insufficient memory allocation
- Health check probe failures

### ImagePullBackOff

This occurs when Kubernetes cannot pull the container image.

**Diagnosis Steps:**
1. Check the image name and tag in the pod spec
2. Verify image registry credentials: `kubectl get secrets`
3. Test image pull manually: `docker pull <image>`

**Solutions:**
- Correct the image name/tag
- Create or update imagePullSecrets
- Check network connectivity to registry

## Memory and CPU Issues

### OOMKilled

Pods terminated with OOMKilled have exceeded their memory limits.

**Diagnosis:**
```bash
kubectl describe pod <pod-name> | grep -A 5 "Last State"
kubectl top pod <pod-name>
```

**Solutions:**
- Increase memory limits in pod spec
- Profile application memory usage
- Fix memory leaks in application code

### CPU Throttling

When pods are CPU throttled, they receive less CPU than requested.

**Symptoms:**
- Slow response times
- High latency
- Increased error rates

**Diagnosis:**
```bash
kubectl top pod <pod-name>
kubectl describe pod <pod-name> | grep -A 5 resources
```

## Network Troubleshooting

### DNS Resolution Failures

**Symptoms:**
- Service names not resolving
- Connection timeouts to other services

**Diagnosis Steps:**
1. Check CoreDNS pods: `kubectl get pods -n kube-system -l k8s-app=kube-dns`
2. Test DNS from pod: `kubectl exec -it <pod> -- nslookup kubernetes.default`
3. Check DNS config: `kubectl exec -it <pod> -- cat /etc/resolv.conf`

**Solutions:**
- Restart CoreDNS pods
- Check network policies
- Verify service exists and has endpoints

### Service Connectivity Issues

**Diagnosis Commands:**
```bash
kubectl get svc <service-name>
kubectl get endpoints <service-name>
kubectl exec -it <pod> -- curl <service-name>:<port>
```

## Health Check Failures

### Liveness Probe Failures

When liveness probes fail, Kubernetes restarts the container.

**Common Issues:**
- Probe timeout too short
- Application not responding on probe endpoint
- Incorrect port configuration

**Best Practices:**
- Set initialDelaySeconds appropriately for startup time
- Use appropriate timeout values
- Ensure probe endpoint is lightweight

### Readiness Probe Failures

Readiness probe failures remove the pod from service endpoints.

**Diagnosis:**
```bash
kubectl describe pod <pod-name> | grep -A 10 Readiness
kubectl logs <pod-name> | grep -i health
```

## Quick Reference Commands

| Issue | Command |
|-------|---------|
| Get pod events | `kubectl describe pod <name>` |
| View logs | `kubectl logs <pod> [-c container]` |
| Previous logs | `kubectl logs <pod> --previous` |
| Resource usage | `kubectl top pod <name>` |
| Exec into pod | `kubectl exec -it <pod> -- /bin/sh` |
| Get pod YAML | `kubectl get pod <name> -o yaml` |
