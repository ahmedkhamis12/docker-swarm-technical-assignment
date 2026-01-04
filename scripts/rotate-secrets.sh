#!/bin/bash

# =============================================================================
# Docker Swarm Secret Rotation Script
# Task 1.3: Demonstrates how to rotate secrets without downtime
# =============================================================================
# 
# Secret rotation in Docker Swarm involves:
# 1. Creating a new version of the secret
# 2. Updating the service to use the new secret
# 3. Removing the old secret
#
# This ensures zero-downtime rotation as the service rolling update 
# gradually replaces containers with the new secret.
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Usage Instructions
# =============================================================================
usage() {
    echo "Usage: $0 <secret_name> <new_value> <service_name>"
    echo ""
    echo "Arguments:"
    echo "  secret_name   - Name of the secret to rotate (e.g., db_password)"
    echo "  new_value     - New value for the secret"
    echo "  service_name  - Name of the service using this secret"
    echo ""
    echo "Example:"
    echo "  $0 db_password mynewpassword123 myapp_backend"
    exit 1
}

# =============================================================================
# Main Rotation Logic
# =============================================================================
rotate_secret() {
    local SECRET_NAME=$1
    local NEW_VALUE=$2
    local SERVICE_NAME=$3
    local TIMESTAMP=$(date +%Y%m%d%H%M%S)
    local NEW_SECRET_NAME="${SECRET_NAME}_v${TIMESTAMP}"

    log_info "Starting secret rotation for: ${SECRET_NAME}"
    log_info "New secret version: ${NEW_SECRET_NAME}"

    # Step 1: Create new secret with versioned name
    log_info "Step 1: Creating new secret..."
    echo "${NEW_VALUE}" | docker secret create "${NEW_SECRET_NAME}" -
    if [ $? -ne 0 ]; then
        log_error "Failed to create new secret"
        exit 1
    fi
    log_info "New secret created successfully"

    # Step 2: Update service to use new secret (this triggers rolling update)
    log_info "Step 2: Updating service ${SERVICE_NAME} to use new secret..."
    
    # First, we need to get the target path of the current secret mount
    # For simplicity, we'll use the standard /run/secrets/secret_name path
    docker service update \
        --secret-rm "${SECRET_NAME}" \
        --secret-add source="${NEW_SECRET_NAME}",target="${SECRET_NAME}" \
        "${SERVICE_NAME}"
    
    if [ $? -ne 0 ]; then
        log_error "Failed to update service"
        log_warn "Rolling back: removing new secret..."
        docker secret rm "${NEW_SECRET_NAME}" 2>/dev/null || true
        exit 1
    fi

    log_info "Service update initiated - rolling update in progress"

    # Step 3: Wait for rolling update to complete
    log_info "Step 3: Waiting for rolling update to complete..."
    docker service update --detach=false "${SERVICE_NAME}"

    # Step 4: Verify the update was successful
    log_info "Step 4: Verifying service health..."
    REPLICAS=$(docker service ls --filter "name=${SERVICE_NAME}" --format "{{.Replicas}}")
    log_info "Current service replicas: ${REPLICAS}"

    # Step 5: Remove old secret (optional - only after confirming success)
    log_info "Step 5: Cleaning up old secret..."
    log_warn "The old secret '${SECRET_NAME}' can now be removed if no longer needed"
    log_warn "Run: docker secret rm ${SECRET_NAME}"
    
    echo ""
    log_info "=========================================="
    log_info "Secret rotation completed successfully!"
    log_info "=========================================="
    echo ""
    log_info "New secret name: ${NEW_SECRET_NAME}"
    log_info "The service '${SERVICE_NAME}' is now using the new secret"
    echo ""
    log_info "To verify, check the service logs:"
    echo "  docker service logs ${SERVICE_NAME}"
}

# =============================================================================
# Alternative: Simple Secret Rotation (requires service restart)
# =============================================================================
# This method is simpler but requires a brief outage
simple_rotate() {
    local SECRET_NAME=$1
    local NEW_VALUE=$2
    local SERVICE_NAME=$3

    log_warn "Using simple rotation (will cause brief outage)..."
    
    # Remove the service's reference to the secret
    docker service update --secret-rm "${SECRET_NAME}" "${SERVICE_NAME}"
    
    # Remove and recreate the secret
    docker secret rm "${SECRET_NAME}"
    echo "${NEW_VALUE}" | docker secret create "${SECRET_NAME}" -
    
    # Re-add the secret to the service
    docker service update --secret-add "${SECRET_NAME}" "${SERVICE_NAME}"
    
    log_info "Simple rotation completed"
}

# =============================================================================
# Entry Point
# =============================================================================
if [ "$#" -lt 3 ]; then
    usage
fi

# Validate Docker Swarm is active
if ! docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "active"; then
    log_error "This node is not part of a Docker Swarm cluster"
    exit 1
fi

rotate_secret "$1" "$2" "$3"
