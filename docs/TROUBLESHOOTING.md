# Swarm Troubleshooting Guide

> Task 5.2: Service Failure Scenarios

## Scenario 1: Service Shows Running Replicas but Requests Fail

### Symptoms
- `docker service ls` shows `3/3` replicas
- Requests to the service return errors or timeouts
- Health checks may or may not be passing

### Investigation Commands

```bash
# 1. Check which replicas are actually healthy
docker service ps myapp_backend --format "table {{.Name}}\t{{.CurrentState}}\t{{.Error}}"

# 2. Get detailed task status
docker service ps myapp_backend --no-trunc

# 3. Check if tasks are restarting frequently
docker service ps myapp_backend --filter "desired-state=running" \
  --format "{{.Name}}: {{.CurrentState}}"

# 4. Inspect a specific task for errors
TASK_ID=$(docker service ps myapp_backend -q | head -1)
docker inspect $TASK_ID --format '{{.Status.Err}}'

# 5. Check container health status
docker ps --filter "label=com.docker.swarm.service.name=myapp_backend" \
  --format "table {{.ID}}\t{{.Status}}\t{{.Names}}"
```

### Check Individual Replica Logs

```bash
# Get logs from all replicas
docker service logs myapp_backend --tail 100

# Get logs from a specific task
docker service logs myapp_backend.1 --tail 50

# Follow logs in real-time
docker service logs myapp_backend -f

# Filter for errors
docker service logs myapp_backend 2>&1 | grep -i error
```

### Verify Health Checks

```bash
# Check health check configuration
docker service inspect myapp_backend \
  --format '{{json .Spec.TaskTemplate.ContainerSpec.Healthcheck}}' | jq

# Test health check manually inside container
docker exec -it <container_id> wget -qO- http://localhost:5000/health

# Check health status
docker inspect <container_id> --format '{{json .State.Health}}' | jq
```

### Force Restart Problematic Replica

```bash
# Option 1: Force update (restarts all replicas)
docker service update --force myapp_backend

# Option 2: Scale down and up specific replica
docker service scale myapp_backend=2  # Remove one
docker service scale myapp_backend=3  # Add it back

# Option 3: Kill specific container (Swarm will recreate)
docker kill <container_id>
```

### Common Causes & Solutions

| Cause | Solution |
|-------|----------|
| Health check too strict | Increase timeout/retries |
| Memory limit hit (OOM) | Increase memory limit |
| Connection pool exhausted | Increase pool size or replicas |
| Database connection timeouts | Check DB health, increase connections |
| Network issues | Check overlay network health |

---

## Scenario 2: Services Stuck in "Starting" State

### Symptoms
- `docker service ps` shows tasks in "Starting" or "Pending"
- Tasks never transition to "Running"
- May see tasks cycling through "Starting" → "Failed" → "Starting"

### Investigation Commands

```bash
# 1. Check task state and errors
docker service ps myapp_backend --no-trunc

# 2. Look for placement issues
docker service ps myapp_backend \
  --format "{{.Name}}: {{.CurrentState}} - {{.Error}}"

# 3. Check task inspection for detailed error
TASK_ID=$(docker service ps myapp_backend -q --filter "desired-state=running" | head -1)
docker inspect $TASK_ID | jq '.[].Status'

# 4. Check node availability
docker node ls

# 5. Check if image can be pulled
docker pull <image_name>
```

### Check Task History & Failure Reasons

```bash
# View complete task history (including failed attempts)
docker service ps myapp_backend --no-trunc --filter "is-task=true"

# Get specific error message
docker service ps myapp_backend --format "{{.Name}}: {{.Error}}" | grep -v "^$"

# Check Swarm events
docker events --filter type=service --since 10m
```

### Common Reasons for Services Failing to Start

#### 1. Image Pull Failures
```bash
# Error: "No such image"
# Solution: Verify image name and tag
docker pull myregistry.com/myapp:latest

# Check registry authentication
docker login myregistry.com
```

#### 2. Placement Constraints Not Met
```bash
# Error: "no suitable node"
# Check constraints in service
docker service inspect myapp_backend \
  --format '{{json .Spec.TaskTemplate.Placement.Constraints}}'

# Check node labels
docker node ls -q | xargs -I {} docker node inspect {} \
  --format '{{.Description.Hostname}}: {{.Spec.Labels}}'

# Add missing label
docker node update --label-add database=true node1
```

#### 3. Resource Constraints Not Met
```bash
# Error: "insufficient resources"
# Check resource requirements
docker service inspect myapp_backend \
  --format '{{json .Spec.TaskTemplate.Resources}}'

# Check node resources
docker node ls -q | xargs -I {} docker node inspect {} \
  --format '{{.Description.Hostname}}: CPU={{.Description.Resources.NanoCPUs}} Memory={{.Description.Resources.MemoryBytes}}'
```

#### 4. Secret/Config Not Found
```bash
# Error: "secret not found"
# List available secrets
docker secret ls

# Create missing secret
echo "value" | docker secret create my_secret -
```

#### 5. Network Issues
```bash
# Check network exists
docker network ls --filter driver=overlay

# Create missing network
docker network create --driver overlay my_network
```

### Quick Fixes

```bash
# Force redeploy all tasks
docker service update --force myapp_backend

# Restart entire stack
docker stack rm myapp
docker stack deploy -c docker-compose.yml myapp

# Increase allocation attempts
docker service update \
  --restart-delay 5s \
  --restart-max-attempts 5 \
  myapp_backend
```

---

## Debugging Checklist

### Service Not Starting
- [ ] Image exists and can be pulled
- [ ] All secrets/configs exist
- [ ] All networks exist
- [ ] Placement constraints are satisfiable
- [ ] Sufficient resources on nodes
- [ ] Port not in use by another service

### Service Running but Unhealthy
- [ ] Health check endpoint accessible
- [ ] Health check timeout sufficient
- [ ] Dependencies (DB, Redis) accessible
- [ ] Environment variables set correctly
- [ ] Memory/CPU limits not too restrictive

### Network/Connectivity Issues
- [ ] Services on same overlay network
- [ ] DNS resolution working (`nslookup service_name`)
- [ ] Ports exposed correctly
- [ ] No firewall blocking overlay traffic

---

## Diagnostic Script

```bash
#!/bin/bash
# Swarm service diagnostic script

SERVICE=$1

if [ -z "$SERVICE" ]; then
  echo "Usage: $0 <service_name>"
  exit 1
fi

echo "=== Service Status ==="
docker service ls --filter "name=$SERVICE"

echo ""
echo "=== Task Status ==="
docker service ps $SERVICE --no-trunc

echo ""
echo "=== Recent Logs ==="
docker service logs $SERVICE --tail 20 2>&1 | tail -20

echo ""
echo "=== Health Check Config ==="
docker service inspect $SERVICE \
  --format '{{json .Spec.TaskTemplate.ContainerSpec.Healthcheck}}' 2>/dev/null | jq .

echo ""
echo "=== Resource Limits ==="
docker service inspect $SERVICE \
  --format '{{json .Spec.TaskTemplate.Resources}}' | jq .

echo ""
echo "=== Placement Constraints ==="
docker service inspect $SERVICE \
  --format '{{json .Spec.TaskTemplate.Placement}}' | jq .

echo ""
echo "=== Networks ==="
docker service inspect $SERVICE \
  --format '{{json .Spec.TaskTemplate.Networks}}' | jq .
```
