# Swarm Cluster Operations Runbook

> Task 5.3: Swarm Cluster Management

This runbook covers essential Docker Swarm cluster management operations.

---

## Table of Contents

1. [Node Management](#1-node-management)
2. [Manager Operations](#2-manager-operations)
3. [Node Draining](#3-node-draining)
4. [Quorum Recovery](#4-quorum-recovery)
5. [Backup & Restore](#5-backup--restore)
6. [Node Labels & Scheduling](#6-node-labels--scheduling)

---

## 1. Node Management

### Adding Nodes to Swarm

```bash
# On manager node: Get join tokens
docker swarm join-token worker
docker swarm join-token manager

# On new worker node: Join the swarm
docker swarm join --token SWMTKN-xxx manager-ip:2377

# On new manager node: Join as manager
docker swarm join --token SWMTKN-xxx manager-ip:2377

# Verify node joined
docker node ls
```

### Removing Nodes from Swarm

```bash
# On the node being removed (graceful leave)
docker swarm leave

# If node was a manager, force leave
docker swarm leave --force

# On manager: Remove the node from swarm's knowledge
docker node rm <node_id>

# Force remove unreachable node
docker node rm --force <node_id>
```

### Node Information

```bash
# List all nodes with status
docker node ls

# Detailed node information
docker node inspect <node_id>

# Check node resources
docker node inspect <node_id> \
  --format 'CPU: {{.Description.Resources.NanoCPUs}} Memory: {{.Description.Resources.MemoryBytes}}'

# List tasks running on a node
docker node ps <node_id>
```

---

## 2. Manager Operations

### Promoting/Demoting Manager Nodes

```bash
# Promote worker to manager
docker node promote <node_id>

# Demote manager to worker
docker node demote <node_id>

# Verify manager status
docker node ls --filter role=manager
```

### Manager Quorum Requirements

| Total Managers | Required for Quorum | Fault Tolerance |
|----------------|---------------------|-----------------|
| 1 | 1 | 0 (no HA) |
| 2 | 2 | 0 (not recommended) |
| 3 | 2 | 1 |
| 5 | 3 | 2 |
| 7 | 4 | 3 |

### Best Practices for Managers

```bash
# Always use odd number of managers (3, 5, or 7)
# Maximum 7 managers recommended for performance

# Check manager status
docker info --format '{{.Swarm.Managers}}'

# View manager node distribution
docker node ls --filter role=manager \
  --format "table {{.Hostname}}\t{{.Status}}\t{{.Availability}}"
```

---

## 3. Node Draining

### Drain Node for Maintenance

```bash
# Drain node (moves all tasks to other nodes)
docker node update --availability drain <node_id>

# Verify tasks moved
docker node ps <node_id>

# Perform maintenance...

# Return node to active status
docker node update --availability active <node_id>
```

### Pause Node (No New Tasks)

```bash
# Pause: existing tasks continue, no new tasks scheduled
docker node update --availability pause <node_id>

# Return to active
docker node update --availability active <node_id>
```

### Drain All Services Before Maintenance

```bash
#!/bin/bash
# Graceful node drain script

NODE=$1
WAIT_TIME=30

echo "Draining node: $NODE"
docker node update --availability drain $NODE

echo "Waiting for tasks to migrate..."
sleep 5

# Wait for all tasks to leave
while [ $(docker node ps $NODE -q 2>/dev/null | wc -l) -gt 0 ]; do
  echo "Tasks still running on $NODE, waiting..."
  docker node ps $NODE --format "{{.Name}}: {{.DesiredState}}"
  sleep 5
done

echo "Node $NODE is fully drained. Safe for maintenance."
```

---

## 4. Quorum Recovery

### Recovering from Quorum Loss

**Scenario**: Majority of managers are lost (e.g., 2 of 3 managers down)

```bash
# On surviving manager: Force new cluster
docker swarm init --force-new-cluster --advertise-addr <IP>

# This creates a new single-node cluster with existing services

# Add new managers to restore HA
docker swarm join-token manager
# On new managers: docker swarm join ...
```

### Recovering from Complete Manager Loss

If all managers are lost but you have Swarm data backup:

```bash
# 1. Stop Docker on all nodes
sudo systemctl stop docker

# 2. Restore Swarm data to one node
sudo cp -r /backup/swarm/* /var/lib/docker/swarm/

# 3. Start Docker
sudo systemctl start docker

# 4. Reinitialize swarm
docker swarm init --force-new-cluster

# 5. Rejoin other nodes
docker swarm join-token worker
docker swarm join-token manager
```

### Check Raft Consensus Status

```bash
# View Raft status on manager
docker info --format '{{json .Swarm.Cluster.RootRotationInProgress}}'

# Check Raft log
docker node ls
```

---

## 5. Backup & Restore

### Backup Swarm State

```bash
#!/bin/bash
# Swarm backup script - Run on manager node

BACKUP_DIR="/backup/swarm-$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Stop Docker to ensure consistent backup
sudo systemctl stop docker

# Copy Swarm state
sudo cp -r /var/lib/docker/swarm $BACKUP_DIR/

# Restart Docker
sudo systemctl start docker

# Compress backup
tar -czvf ${BACKUP_DIR}.tar.gz -C /backup $(basename $BACKUP_DIR)
rm -rf $BACKUP_DIR

echo "Backup saved to ${BACKUP_DIR}.tar.gz"
```

### What's Backed Up

| Directory | Contents |
|-----------|----------|
| `/var/lib/docker/swarm/` | Raft logs, node certificates, cluster state |
| `/var/lib/docker/swarm/raft/` | Raft consensus data |
| `/var/lib/docker/swarm/certificates/` | TLS certificates |

### Restore Swarm State

```bash
#!/bin/bash
# Swarm restore script

BACKUP_FILE=$1
SWARM_DIR="/var/lib/docker/swarm"

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup.tar.gz>"
  exit 1
fi

# Stop Docker
sudo systemctl stop docker

# Remove existing swarm data
sudo rm -rf $SWARM_DIR

# Extract backup
sudo tar -xzvf $BACKUP_FILE -C /var/lib/docker/

# Start Docker
sudo systemctl start docker

# Reinitialize cluster
docker swarm init --force-new-cluster

echo "Swarm restored. Add other nodes using join tokens."
```

### Backup Secrets and Configs

```bash
# Secrets cannot be exported (by design)
# Document secret creation commands for recreation

# Export configs
docker config ls -q | while read config; do
  docker config inspect $config > configs/${config}.json
done
```

---

## 6. Node Labels & Scheduling

### Adding Node Labels

```bash
# Add single label
docker node update --label-add environment=production node1

# Add multiple labels
docker node update \
  --label-add environment=production \
  --label-add tier=frontend \
  --label-add datacenter=us-east \
  node1

# Remove label
docker node update --label-rm environment node1
```

### View Node Labels

```bash
# List all node labels
docker node ls -q | xargs -I {} sh -c 'echo "=== {} ===" && docker node inspect {} --format "{{json .Spec.Labels}}" | jq .'

# Check specific node
docker node inspect node1 --format '{{json .Spec.Labels}}' | jq .
```

### Constraint-Based Scheduling

```yaml
# In docker-compose.yml
deploy:
  placement:
    constraints:
      # Schedule on specific node labels
      - node.labels.environment == production
      - node.labels.tier == backend
      
      # Schedule on worker nodes only
      - node.role == worker
      
      # Schedule on specific node
      - node.hostname == node1
      
      # NOT conditions
      - node.labels.maintenance != true
```

### Placement Preferences (Spread)

```yaml
deploy:
  placement:
    preferences:
      # Spread across datacenters
      - spread: node.labels.datacenter
      
      # Spread across nodes (default behavior)
      - spread: node.id
```

### Common Label Patterns

| Label | Purpose | Example Values |
|-------|---------|----------------|
| `environment` | Deployment stage | production, staging, development |
| `tier` | Application tier | frontend, backend, database |
| `datacenter` | Location | us-east, eu-west |
| `ssd` | Storage type | true, false |
| `gpu` | GPU availability | true, nvidia-a100 |
| `maintenance` | Maintenance mode | true, false |

---

## Quick Reference Card

```bash
# Node Operations
docker swarm join-token worker|manager   # Get join token
docker node ls                           # List nodes
docker node promote <node>               # Make node a manager
docker node demote <node>                # Make manager a worker
docker node rm <node>                    # Remove node
docker node update --availability drain <node>  # Drain node

# Service Operations
docker service ls                        # List services
docker service ps <service>              # List service tasks
docker service logs <service>            # View logs
docker service update --force <service>  # Force redeploy
docker service rollback <service>        # Rollback to previous

# Cluster Operations
docker swarm init --force-new-cluster   # Recover quorum
docker info                              # Cluster info

# Labels
docker node update --label-add key=val <node>
docker node update --label-rm key <node>
```
