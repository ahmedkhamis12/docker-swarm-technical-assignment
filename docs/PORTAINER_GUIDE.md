# Portainer Stack Management Guide

> Task 3.1: Portainer Deployment and Stack Management

## Installation on Docker Swarm

### Step 1: Deploy Portainer as a Swarm Service

```bash
# Create a volume for Portainer data persistence
docker volume create portainer_data

# Deploy Portainer as a Swarm stack
curl -L https://downloads.portainer.io/ce2-19/portainer-agent-stack.yml -o portainer-agent-stack.yml

# Or use this minimal deployment:
cat > portainer-stack.yml <<EOF
version: '3.8'

services:
  agent:
    image: portainer/agent:2.19.4
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/docker/volumes:/var/lib/docker/volumes
    networks:
      - agent_network
    deploy:
      mode: global
      placement:
        constraints: [node.platform.os == linux]

  portainer:
    image: portainer/portainer-ce:2.19.4
    command: -H tcp://tasks.agent:9001 --tlsskipverify
    ports:
      - "9443:9443"
      - "9000:9000"
      - "8000:8000"
    volumes:
      - portainer_data:/data
    networks:
      - agent_network
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints: [node.role == manager]

networks:
  agent_network:
    driver: overlay
    attachable: true

volumes:
  portainer_data:
EOF

# Deploy the stack
docker stack deploy -c portainer-stack.yml portainer
```

### Step 2: Initial Setup

1. Access Portainer at `https://<manager-ip>:9443`
2. Create admin user (first login)
3. Select "Docker Swarm" as the environment type
4. Portainer auto-connects to the local Swarm cluster

---

## Deploying Stacks via Portainer UI

### Method 1: Web Editor

1. Navigate to **Stacks** → **Add Stack**
2. Name your stack (e.g., `myapp`)
3. Select **Web editor**
4. Paste your `docker-compose.yml` content
5. Add environment variables if needed
6. Click **Deploy the stack**

### Method 2: Upload File

1. Navigate to **Stacks** → **Add Stack**
2. Name your stack
3. Select **Upload**
4. Choose your `docker-compose.yml` file
5. Configure environment variables
6. Click **Deploy the stack**

### Method 3: Git Repository

1. Navigate to **Stacks** → **Add Stack**
2. Name your stack
3. Select **Repository**
4. Enter Git URL: `https://github.com/user/repo.git`
5. Specify compose file path: `docker-compose.yml`
6. Enable **Automatic updates** for GitOps
7. Click **Deploy the stack**

---

## Deploying via Portainer API

### Authentication

```bash
# Get API token
PORTAINER_URL="https://localhost:9443"
USERNAME="admin"
PASSWORD="yourpassword"

# Authenticate and get JWT token
TOKEN=$(curl -sk -X POST "${PORTAINER_URL}/api/auth" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}" \
  | jq -r '.jwt')

echo "Token: ${TOKEN}"
```

### List Stacks

```bash
curl -sk -X GET "${PORTAINER_URL}/api/stacks" \
  -H "Authorization: Bearer ${TOKEN}" \
  | jq '.[] | {id: .Id, name: .Name, status: .Status}'
```

### Deploy New Stack

```bash
# Endpoint ID (usually 1 for local Swarm)
ENDPOINT_ID=1

# Stack name
STACK_NAME="myapp"

# Deploy stack from compose file content
COMPOSE_CONTENT=$(cat docker-compose.yml | jq -Rs .)

curl -sk -X POST "${PORTAINER_URL}/api/stacks/create/swarm/string?endpointId=${ENDPOINT_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"${STACK_NAME}\",
    \"stackFileContent\": ${COMPOSE_CONTENT},
    \"swarmID\": \"$(docker info --format '{{.Swarm.Cluster.ID}}')\",
    \"env\": [
      {\"name\": \"NODE_ENV\", \"value\": \"production\"}
    ]
  }"
```

### Update Existing Stack

```bash
STACK_ID=1  # Get from list stacks

curl -sk -X PUT "${PORTAINER_URL}/api/stacks/${STACK_ID}?endpointId=${ENDPOINT_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"stackFileContent\": ${COMPOSE_CONTENT},
    \"env\": [],
    \"prune\": true
  }"
```

---

## Managing Environment Variables

### In Portainer UI

1. Go to **Stacks** → Select your stack
2. Click **Editor** tab
3. Scroll to **Environment variables**
4. Add/Edit variables
5. Click **Update the stack**

### In API

```bash
# Include env array in stack creation/update
"env": [
  {"name": "DATABASE_URL", "value": "postgres://..."},
  {"name": "REDIS_URL", "value": "redis://redis:6379"},
  {"name": "NODE_ENV", "value": "production"}
]
```

---

## Best Practices for Portainer Stack Organization

### Naming Convention

| Pattern | Example | Use Case |
|---------|---------|----------|
| `<env>-<app>` | `prod-myapp` | Environment-prefixed |
| `<app>-<version>` | `myapp-v2` | Version tracking |
| `<team>-<app>` | `backend-api` | Team ownership |

### Tagging Strategy

Use Portainer's resource control for access management:

1. Create **Teams** for different access levels
2. Assign stacks to teams via **Resource Control**
3. Use **Edge Groups** for multi-cluster deployments

### Stack Templates

Create reusable templates:

1. Go to **App Templates** → **Custom Templates**
2. Define template with placeholder variables
3. Use `${VAR_NAME}` syntax for substitution
4. Teams can deploy standardized stacks

### Recommended Portainer Settings

- **Enable Edge Compute**: For managing remote clusters
- **Authentication**: Use OAuth/LDAP for enterprise
- **Backup Schedule**: Enable automatic backups
- **Activity Logs**: Enable for audit trail
