# Rolling Updates & Rollbacks

> Task 5.1: Rolling Update Strategies in Docker Swarm

## Overview

Docker Swarm provides built-in rolling update capabilities that allow you to update services with zero downtime. This document demonstrates the update strategies and rollback procedures.

---

## Key Update Configuration Parameters

| Parameter | Description | Recommended Value |
|-----------|-------------|-------------------|
| `parallelism` | Number of tasks to update simultaneously | 1-2 for safety |
| `delay` | Wait time between updating batches | 10-30 seconds |
| `failure_action` | Action on update failure | `rollback` or `pause` |
| `monitor` | Time to monitor after update | 30-60 seconds |
| `max_failure_ratio` | Acceptable failure percentage | 0.1-0.3 (10-30%) |
| `order` | Task startup order | `start-first` for zero-downtime |

### Configuration in docker-compose.yml

```yaml
deploy:
  replicas: 3
  update_config:
    parallelism: 2          # Update 2 at a time
    delay: 15s              # Wait 15 seconds between batches
    failure_action: rollback # Rollback on failure
    monitor: 45s            # Monitor for 45s after update
    max_failure_ratio: 0.3  # Allow 30% failures
    order: start-first      # Start new before stopping old
  
  rollback_config:
    parallelism: 2          # Rollback 2 at a time
    delay: 10s
    failure_action: pause   # Pause rollback on failure
    monitor: 30s
```

---

## 1. Performing Zero-Downtime Rolling Update

### Step-by-Step Process

```bash
# 1. Check current service state
docker service ps myapp_backend

# 2. Update the service image (triggers rolling update)
docker service update \
  --image node:20-alpine \
  --update-parallelism 2 \
  --update-delay 15s \
  --update-failure-action rollback \
  myapp_backend

# 3. Monitor the rolling update in real-time
watch -n 1 "docker service ps myapp_backend"

# Alternative: Follow update progress
docker service update --detach=false myapp_backend

# 4. Verify update completed successfully
docker service ls --filter name=myapp_backend
docker service ps myapp_backend --filter "desired-state=running"
```

### Update Other Configuration

```bash
# Update environment variables
docker service update \
  --env-add NEW_VAR=value \
  --env-rm OLD_VAR \
  myapp_backend

# Update resource limits
docker service update \
  --limit-cpu 1.0 \
  --limit-memory 1024M \
  myapp_backend

# Update replica count
docker service scale myapp_backend=5

# Update multiple settings at once
docker service update \
  --image node:20-alpine \
  --replicas 5 \
  --env-add VERSION=2.0 \
  myapp_backend
```

---

## 2. Simulating Failed Deployment & Automatic Rollback

### Trigger a Failing Update

```bash
# Deploy with a bad image (will fail health checks)
docker service update \
  --image node:nonexistent-tag \
  --update-failure-action rollback \
  myapp_backend

# Watch the automatic rollback trigger
watch "docker service ps myapp_backend"
```

### Expected Behavior

1. Swarm starts updating tasks with new image
2. Tasks fail to start (image pull fails)
3. After `max_failure_ratio` exceeded, triggers rollback
4. Service returns to previous working state

### Inspect Rollback Status

```bash
# Check rollback status
docker service inspect myapp_backend --format '{{.UpdateStatus.State}}'

# View task history (shows failed tasks)
docker service ps myapp_backend --no-trunc

# Check specific task failure reason
docker inspect <task_id> --format '{{.Status.Err}}'
```

---

## 3. Understanding Update Parameters

### `update-parallelism`

**Purpose**: Controls how many tasks are updated simultaneously.

```bash
# Update 1 at a time (safest, slowest)
docker service update --update-parallelism 1 myapp_backend

# Update 2 at a time (balanced)
docker service update --update-parallelism 2 myapp_backend

# Update all at once (fastest, risky)
docker service update --update-parallelism 0 myapp_backend
```

**Trade-offs**:
- Lower = Safer but slower
- Higher = Faster but more risk if update fails
- 0 = All at once (big bang)

### `update-delay`

**Purpose**: Time to wait between updating batches.

```bash
# Wait 10 seconds between batches
docker service update --update-delay 10s myapp_backend

# Wait 1 minute (for slow-starting services)
docker service update --update-delay 1m myapp_backend
```

**Best Practice**: Set to at least your health check interval plus startup time.

### `update-failure-action`

**Purpose**: What to do when an update fails.

| Value | Behavior |
|-------|----------|
| `pause` | Stop the update, leave partially updated |
| `rollback` | Automatically revert to previous version |
| `continue` | Keep updating despite failures |

```bash
# Auto-rollback on failure (recommended for production)
docker service update \
  --update-failure-action rollback \
  myapp_backend

# Pause for manual investigation
docker service update \
  --update-failure-action pause \
  myapp_backend
```

### `update-order`

**Purpose**: Order of starting/stopping tasks during update.

| Value | Behavior |
|-------|----------|
| `stop-first` | Stop old task, then start new (brief downtime) |
| `start-first` | Start new task, then stop old (zero downtime) |

```bash
# Zero downtime updates
docker service update --update-order start-first myapp_backend
```

---

## 4. Manual Rollback

### Rollback to Previous Version

```bash
# Rollback service to previous version
docker service rollback myapp_backend

# Rollback and wait for completion
docker service rollback --detach=false myapp_backend

# Check rollback status
docker service inspect myapp_backend \
  --format '{{.UpdateStatus.State}} - {{.UpdateStatus.Message}}'
```

### Rollback to Specific Version

Docker Swarm only keeps the previous version for automatic rollback. For specific versions:

```bash
# Manually specify the previous image
docker service update \
  --image node:18-alpine \
  myapp_backend

# Or use image digest for immutable reference
docker service update \
  --image node@sha256:abc123... \
  myapp_backend
```

### View Update History

```bash
# View task history (shows all versions)
docker service ps myapp_backend --no-trunc

# Filter to see shutdown tasks (old versions)
docker service ps myapp_backend --filter "desired-state=shutdown"
```

---

## Complete Rolling Update Example

```bash
#!/bin/bash
# Rolling update script with validation

SERVICE_NAME="myapp_backend"
NEW_IMAGE="myregistry.com/backend:v2.0.0"

echo "Starting rolling update for ${SERVICE_NAME}..."

# Capture current state for potential manual rollback
CURRENT_IMAGE=$(docker service inspect ${SERVICE_NAME} \
  --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}')
echo "Current image: ${CURRENT_IMAGE}"

# Perform update with automatic rollback on failure
docker service update \
  --image ${NEW_IMAGE} \
  --update-parallelism 2 \
  --update-delay 15s \
  --update-failure-action rollback \
  --update-monitor 45s \
  --update-max-failure-ratio 0.2 \
  --update-order start-first \
  --detach=false \
  ${SERVICE_NAME}

# Check final status
UPDATE_STATE=$(docker service inspect ${SERVICE_NAME} \
  --format '{{.UpdateStatus.State}}')

if [ "$UPDATE_STATE" = "completed" ]; then
  echo "✓ Update completed successfully!"
elif [ "$UPDATE_STATE" = "rollback_completed" ]; then
  echo "✗ Update failed, rolled back to: ${CURRENT_IMAGE}"
  exit 1
else
  echo "⚠ Update state: ${UPDATE_STATE}"
  exit 1
fi
```
