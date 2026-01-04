# Security Hardening Checklist for Docker Swarm

> Task 8.1: Swarm Security Hardening Checklist

This checklist provides security best practices for production Docker Swarm deployments with implementation examples.

---

## 1. Secrets Management

### ✅ DO: Use Swarm Secrets for Sensitive Data

Swarm secrets are encrypted at rest and in transit, and only exposed to services that need them.

```bash
# Create secrets (not from command line in production!)
# Use files or external secret managers
cat password.txt | docker secret create db_password -

# Or from file directly
docker secret create db_password ./password.txt

# In docker-compose.yml
secrets:
  db_password:
    external: true

services:
  backend:
    secrets:
      - db_password
    environment:
      # Reference file path, not the actual value
      DB_PASSWORD_FILE: /run/secrets/db_password
```

### ❌ DON'T: Use Environment Variables for Secrets

```yaml
# BAD - Secrets visible in process listing
environment:
  DB_PASSWORD: mysecretpassword

# GOOD - Read from secret file
environment:
  DB_PASSWORD_FILE: /run/secrets/db_password
```

### Implementation: Application Code to Read Secrets

```javascript
// Node.js example
const fs = require('fs');

function readSecret(name) {
  const secretPath = process.env[`${name}_FILE`] || `/run/secrets/${name}`;
  try {
    return fs.readFileSync(secretPath, 'utf8').trim();
  } catch (err) {
    console.error(`Failed to read secret: ${name}`);
    return process.env[name]; // Fallback for development
  }
}

const dbPassword = readSecret('db_password');
```

---

## 2. Network Security

### ✅ Encrypted Overlay Networks

```yaml
networks:
  backend:
    driver: overlay
    driver_opts:
      encrypted: "true"  # IPSec encryption
    internal: true       # No external access
```

### ✅ Network Segmentation

```yaml
# Tier-based isolation
networks:
  public:      # Ingress only
  frontend:    # Frontend ↔ Backend
  backend:     # Backend ↔ Database (internal)
  monitoring:  # Observability stack

services:
  database:
    networks:
      - backend  # Only backend network, not reachable from frontend
```

### Verify Network Isolation

```bash
# Test that frontend cannot reach database
docker exec frontend_container ping database
# Should fail if properly isolated
```

---

## 3. Image Security

### ✅ Use Trusted Registries

```yaml
services:
  backend:
    image: ghcr.io/myorg/backend:sha-abc123  # Specific digest
```

### ✅ Enable Docker Content Trust

```bash
# Enable content trust globally
export DOCKER_CONTENT_TRUST=1

# Sign images when pushing
docker trust sign myregistry.com/myapp:latest
```

### ✅ Scan Images for Vulnerabilities

```bash
# Using Trivy
trivy image myregistry.com/myapp:latest

# In CI/CD pipeline
- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: myapp:latest
    severity: 'CRITICAL,HIGH'
    exit-code: '1'
```

### ✅ Use Minimal Base Images

```dockerfile
# Use distroless or alpine
FROM node:18-alpine    # ~130MB vs ~900MB for debian

# Or even smaller
FROM gcr.io/distroless/nodejs18-debian11
```

---

## 4. Access Control

### ✅ TLS for Swarm Management

```bash
# Generate CA and certificates
docker swarm init --listen-addr <IP>:2377 --cert-expiry 8760h

# Rotate certificates
docker swarm ca --rotate

# View current certificate
docker swarm ca
```

### ✅ Role-Based Node Access

```bash
# Only managers can manage the swarm
# Workers can only run workloads

# Limit manager nodes
# Production: 3, 5, or 7 manager nodes (odd number)
```

### ✅ Certificate-Based Authentication

```bash
# Configure Docker daemon with TLS
dockerd --tlsverify \
  --tlscacert=/etc/docker/ca.pem \
  --tlscert=/etc/docker/server-cert.pem \
  --tlskey=/etc/docker/server-key.pem \
  -H=0.0.0.0:2376
```

---

## 5. Resource Isolation

### ✅ Set Resource Limits

Prevent any single service from monopolizing resources:

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'      # 1 CPU max
      memory: 1024M     # 1GB max
    reservations:
      cpus: '0.5'      # Guaranteed 0.5 CPU
      memory: 512M      # Guaranteed 512MB
```

### ✅ Use Memory Swap Limits

```yaml
deploy:
  resources:
    limits:
      memory: 1024M
    reservations:
      memory: 512M
# Also configure on Docker daemon:
# --default-ulimit nofile=65536:65536
```

---

## 6. Audit Logging

### ✅ Enable Docker Events Logging

```bash
# Monitor swarm events
docker events --filter type=service --since 24h

# Log to syslog
docker events --format '{{json .}}' | logger -t docker-events
```

### ✅ Track Deployments

```yaml
services:
  backend:
    deploy:
      labels:
        deployed.by: "${DEPLOYER:-unknown}"
        deployed.at: "${DEPLOY_TIME:-unknown}"
        version: "${VERSION:-unknown}"
```

### ✅ Log All API Actions

```bash
# Configure Docker daemon logging
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

---

## 7. Node Security

### ✅ OS Hardening

```bash
# Disable root SSH
# /etc/ssh/sshd_config
PermitRootLogin no

# Enable firewall
ufw allow 2377/tcp  # Swarm management
ufw allow 7946      # Node communication
ufw allow 4789/udp  # Overlay network

# Disable unused services
systemctl disable avahi-daemon
```

### ✅ Docker Daemon Security

```json
// /etc/docker/daemon.json
{
  "icc": false,              // Disable inter-container communication
  "no-new-privileges": true, // Prevent privilege escalation
  "userland-proxy": false,   // Use iptables
  "live-restore": true,      // Keep containers on daemon restart
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### ✅ Run Containers as Non-Root

```dockerfile
# In Dockerfile
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 appuser
USER appuser
```

```yaml
# Or in compose
services:
  backend:
    user: "1001:1001"
```

---

## 8. Container Security

### ✅ Read-Only Root Filesystem

```yaml
services:
  backend:
    read_only: true
    tmpfs:
      - /tmp
      - /var/run
```

### ✅ Drop Capabilities

```yaml
services:
  backend:
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if needed
```

### ✅ Security Options

```yaml
services:
  backend:
    security_opt:
      - no-new-privileges:true
      - seccomp:default
```

---

## Quick Security Checklist

| Category | Check | Status |
|----------|-------|--------|
| **Secrets** | Using Swarm secrets (not env vars) | ☐ |
| **Secrets** | Secrets rotated regularly | ☐ |
| **Network** | Overlay networks encrypted | ☐ |
| **Network** | Database on internal network | ☐ |
| **Images** | Using specific image tags/digests | ☐ |
| **Images** | Images scanned for vulnerabilities | ☐ |
| **Images** | Content trust enabled | ☐ |
| **Access** | TLS enabled for Swarm API | ☐ |
| **Access** | Manager nodes limited (3,5,7) | ☐ |
| **Resources** | CPU/memory limits set | ☐ |
| **Audit** | Deployment logging enabled | ☐ |
| **Node** | Docker daemon hardened | ☐ |
| **Container** | Running as non-root | ☐ |
| **Container** | Capabilities dropped | ☐ |
