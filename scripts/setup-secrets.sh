#!/bin/bash

# Script to set up Docker Swarm secrets and configs
# Task 1.3: Swarm Secrets & Configs Management

echo "Creating Docker Swarm secrets..."

# Create secrets from command line (in production, use files or secret management tools)
echo "mysecurepassword" | docker secret create db_password -
echo "appuser" | docker secret create db_user -
echo "api-key-12345" | docker secret create api_key -

echo "Secrets created successfully!"
echo ""
echo "Listing secrets:"
docker secret ls

echo ""
echo "Creating configs..."

# Create a sample config file
cat > /tmp/backend_config.json <<EOF
{
  "appName": "MyApp",
  "version": "1.0.0",
  "features": {
    "enableCache": true,
    "maxConnections": 100
  }
}
EOF

docker config create backend_config /tmp/backend_config.json

echo "Config created successfully!"
echo ""
echo "Listing configs:"
docker config ls

# Clean up temp file
rm /tmp/backend_config.json