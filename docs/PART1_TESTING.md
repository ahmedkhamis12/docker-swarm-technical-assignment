# Part 1 Testing Guide

## Prerequisites
1. Go to https://labs.play-with-docker.com/
2. Login and click "Start"
3. Click "+ ADD NEW INSTANCE" to create first node

## Step-by-Step Commands

### 1. Initialize Docker Swarm
```bash
docker swarm init --advertise-addr eth0
```

### 2. Add More Nodes (Optional but recommended)
- Click "+ ADD NEW INSTANCE" 2 more times
- In each new node, run the `docker swarm join` command shown in node1

### 3. Label a Node for Database
```bash
docker node update --label-add database=true $(docker node ls -q | head -n1)
```

### 4. Create Secrets
```bash
echo "mysecurepassword" | docker secret create db_password -
echo "appuser" | docker secret create db_user -
echo "api-key-12345" | docker secret create api_key -
```

Verify:
```bash
docker secret ls
```

### 5. Create Config
```bash
cat > backend_config.json <<EOF
{
  "appName": "MyApp",
  "version": "1.0.0",
  "features": {
    "enableCache": true,
    "maxConnections": 100
  }
}
EOF

docker config create backend_config backend_config.json
```

Verify:
```bash
docker config ls
```

### 6. Deploy the Stack
```bash
# Copy your docker-compose.yml content to a file in PlayWithDocker
vi docker-compose.yml
# Paste the content and save (:wq)

# Deploy
docker stack deploy -c docker-compose.yml myapp
```

### 7. Verify Deployment
```bash
# Check stack
docker stack ls

# Check services
docker stack services myapp

# Check detailed service info
docker service ps myapp_backend

# Check logs
docker service logs myapp_backend
```

### 8. Test Updates and Rollbacks
```bash
# Update backend to newer version (simulated)
docker service update --image node:20-alpine myapp_backend

# Watch the rolling update
watch docker service ps myapp_backend

# Rollback if needed
docker service rollback myapp_backend
```

## Common Issues

1. **Services not starting**: Check logs with `docker service logs <service_name>`
2. **Network issues**: Ensure networks are created with `docker network ls`
3. **Secret not found**: Make sure secrets are created before deploying stack