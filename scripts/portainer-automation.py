#!/usr/bin/env python3
"""
Portainer API Automation Script
Task 3.2: Portainer Stack Management via API

This script provides automated stack management for Docker Swarm via Portainer API.
Features:
- Authenticate with Portainer
- List running stacks
- Deploy/update stacks from docker-compose.yml
- Validate deployment status
- Support multiple Portainer endpoints

Usage:
    python portainer-automation.py --help
    python portainer-automation.py list --url https://portainer:9443 --user admin --password secret
    python portainer-automation.py deploy --url https://portainer:9443 --user admin --password secret \
        --stack-name myapp --compose-file docker-compose.yml
"""

import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin

# Try to import requests, provide helpful error if not available
try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)


class PortainerClient:
    """Client for interacting with Portainer API."""
    
    def __init__(self, base_url: str, verify_ssl: bool = False):
        """
        Initialize Portainer client.
        
        Args:
            base_url: Portainer server URL (e.g., https://portainer:9443)
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.token: Optional[str] = None
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with Portainer and store JWT token.
        
        Args:
            username: Portainer username
            password: Portainer password
            
        Returns:
            True if authentication successful
        """
        url = f"{self.base_url}/api/auth"
        payload = {"username": username, "password": password}
        
        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            self.token = response.json().get('jwt')
            self.session.headers.update({'Authorization': f'Bearer {self.token}'})
            print(f"✓ Successfully authenticated as '{username}'")
            return True
        except requests.exceptions.RequestException as e:
            print(f"✗ Authentication failed: {e}")
            return False
    
    def get_endpoints(self) -> List[Dict]:
        """
        Get list of Portainer endpoints (environments).
        
        Returns:
            List of endpoint dictionaries
        """
        url = f"{self.base_url}/api/endpoints"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_endpoint_id(self, endpoint_name: Optional[str] = None) -> int:
        """
        Get endpoint ID by name, or return first Swarm endpoint.
        
        Args:
            endpoint_name: Optional name of endpoint to find
            
        Returns:
            Endpoint ID
        """
        endpoints = self.get_endpoints()
        
        if endpoint_name:
            for ep in endpoints:
                if ep['Name'] == endpoint_name:
                    return ep['Id']
            raise ValueError(f"Endpoint '{endpoint_name}' not found")
        
        # Return first Swarm endpoint (Type 2 = Swarm, Type 1 = Docker)
        for ep in endpoints:
            if ep.get('Type') in [1, 2]:  # Docker or Swarm
                return ep['Id']
        
        raise ValueError("No valid endpoint found")
    
    def get_swarm_id(self, endpoint_id: int) -> str:
        """
        Get Swarm cluster ID for an endpoint.
        
        Args:
            endpoint_id: Portainer endpoint ID
            
        Returns:
            Swarm cluster ID
        """
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/swarm"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json().get('ID', '')
    
    def list_stacks(self) -> List[Dict]:
        """
        List all stacks across all endpoints.
        
        Returns:
            List of stack dictionaries
        """
        url = f"{self.base_url}/api/stacks"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_stack(self, stack_id: int) -> Dict:
        """
        Get details of a specific stack.
        
        Args:
            stack_id: Stack ID
            
        Returns:
            Stack details dictionary
        """
        url = f"{self.base_url}/api/stacks/{stack_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def deploy_stack(
        self,
        name: str,
        compose_content: str,
        endpoint_id: int,
        env_vars: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Deploy a new stack from compose file content.
        
        Args:
            name: Stack name
            compose_content: Docker Compose file content
            endpoint_id: Portainer endpoint ID
            env_vars: Optional list of environment variables
            
        Returns:
            Deployed stack details
        """
        swarm_id = self.get_swarm_id(endpoint_id)
        
        url = f"{self.base_url}/api/stacks/create/swarm/string"
        params = {"endpointId": endpoint_id}
        
        payload = {
            "name": name,
            "stackFileContent": compose_content,
            "swarmID": swarm_id,
            "env": env_vars or []
        }
        
        response = self.session.post(url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    
    def update_stack(
        self,
        stack_id: int,
        compose_content: str,
        endpoint_id: int,
        env_vars: Optional[List[Dict]] = None,
        prune: bool = True
    ) -> Dict:
        """
        Update an existing stack.
        
        Args:
            stack_id: Stack ID to update
            compose_content: New Docker Compose file content
            endpoint_id: Portainer endpoint ID
            env_vars: Optional list of environment variables
            prune: Whether to prune old services
            
        Returns:
            Updated stack details
        """
        url = f"{self.base_url}/api/stacks/{stack_id}"
        params = {"endpointId": endpoint_id}
        
        payload = {
            "stackFileContent": compose_content,
            "env": env_vars or [],
            "prune": prune
        }
        
        response = self.session.put(url, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    
    def delete_stack(self, stack_id: int, endpoint_id: int) -> bool:
        """
        Delete a stack.
        
        Args:
            stack_id: Stack ID to delete
            endpoint_id: Portainer endpoint ID
            
        Returns:
            True if deletion successful
        """
        url = f"{self.base_url}/api/stacks/{stack_id}"
        params = {"endpointId": endpoint_id}
        
        response = self.session.delete(url, params=params)
        response.raise_for_status()
        return True
    
    def get_stack_services(self, endpoint_id: int, stack_name: str) -> List[Dict]:
        """
        Get services for a specific stack.
        
        Args:
            endpoint_id: Portainer endpoint ID
            stack_name: Name of the stack
            
        Returns:
            List of service dictionaries
        """
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/services"
        params = {"filters": json.dumps({"label": [f"com.docker.stack.namespace={stack_name}"]})}
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def validate_deployment(self, endpoint_id: int, stack_name: str, timeout: int = 120) -> bool:
        """
        Validate that all services in a stack are running correctly.
        
        Args:
            endpoint_id: Portainer endpoint ID
            stack_name: Name of the stack
            timeout: Maximum time to wait for services (seconds)
            
        Returns:
            True if all services are healthy
        """
        print(f"\n📋 Validating deployment of stack '{stack_name}'...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            services = self.get_stack_services(endpoint_id, stack_name)
            
            if not services:
                print("⏳ Waiting for services to appear...")
                time.sleep(5)
                continue
            
            all_healthy = True
            print(f"\n{'Service':<30} {'Replicas':<15} {'Status':<10}")
            print("-" * 55)
            
            for svc in services:
                name = svc['Spec']['Name']
                mode = svc['Spec'].get('Mode', {})
                
                if 'Replicated' in mode:
                    desired = mode['Replicated'].get('Replicas', 0)
                    running = svc.get('ServiceStatus', {}).get('RunningTasks', 0)
                    status = "✓ OK" if running >= desired else "⏳ Starting"
                    
                    if running < desired:
                        all_healthy = False
                    
                    print(f"{name:<30} {running}/{desired:<12} {status:<10}")
                else:
                    # Global mode
                    running = svc.get('ServiceStatus', {}).get('RunningTasks', 0)
                    print(f"{name:<30} {'global':<12} {'✓ OK' if running > 0 else '⏳':<10}")
                    
                    if running == 0:
                        all_healthy = False
            
            if all_healthy:
                print(f"\n✓ All services are running!")
                return True
            
            time.sleep(5)
        
        print(f"\n✗ Timeout waiting for services to become healthy")
        return False


def cmd_list(client: PortainerClient, args: argparse.Namespace) -> int:
    """List all stacks."""
    stacks = client.list_stacks()
    
    if not stacks:
        print("No stacks found.")
        return 0
    
    print(f"\n{'ID':<5} {'Name':<25} {'Type':<10} {'Status':<10} {'Endpoint':<10}")
    print("-" * 60)
    
    for stack in stacks:
        stack_type = "Swarm" if stack.get('Type') == 1 else "Compose"
        status = "Active" if stack.get('Status') == 1 else "Inactive"
        print(f"{stack['Id']:<5} {stack['Name']:<25} {stack_type:<10} {status:<10} {stack.get('EndpointId', 'N/A'):<10}")
    
    print(f"\nTotal: {len(stacks)} stacks")
    return 0


def cmd_deploy(client: PortainerClient, args: argparse.Namespace) -> int:
    """Deploy or update a stack."""
    # Read compose file
    if not os.path.exists(args.compose_file):
        print(f"✗ Compose file not found: {args.compose_file}")
        return 1
    
    with open(args.compose_file, 'r') as f:
        compose_content = f.read()
    
    # Parse environment variables
    env_vars = []
    if args.env:
        for env in args.env:
            if '=' in env:
                key, value = env.split('=', 1)
                env_vars.append({"name": key, "value": value})
    
    # Get endpoint ID
    try:
        endpoint_id = client.get_endpoint_id(args.endpoint)
        print(f"✓ Using endpoint ID: {endpoint_id}")
    except ValueError as e:
        print(f"✗ {e}")
        return 1
    
    # Check if stack exists
    existing_stack = None
    for stack in client.list_stacks():
        if stack['Name'] == args.stack_name and stack.get('EndpointId') == endpoint_id:
            existing_stack = stack
            break
    
    try:
        if existing_stack:
            print(f"📦 Updating existing stack '{args.stack_name}'...")
            result = client.update_stack(
                existing_stack['Id'],
                compose_content,
                endpoint_id,
                env_vars
            )
            print(f"✓ Stack updated successfully!")
        else:
            print(f"📦 Deploying new stack '{args.stack_name}'...")
            result = client.deploy_stack(
                args.stack_name,
                compose_content,
                endpoint_id,
                env_vars
            )
            print(f"✓ Stack deployed successfully!")
        
        # Validate deployment
        if not args.no_validate:
            if not client.validate_deployment(endpoint_id, args.stack_name):
                return 1
        
        return 0
        
    except requests.exceptions.HTTPError as e:
        print(f"✗ Deployment failed: {e}")
        if e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"  Details: {error_detail.get('message', error_detail)}")
            except:
                print(f"  Response: {e.response.text}")
        return 1


def cmd_delete(client: PortainerClient, args: argparse.Namespace) -> int:
    """Delete a stack."""
    endpoint_id = client.get_endpoint_id(args.endpoint)
    
    # Find stack by name
    for stack in client.list_stacks():
        if stack['Name'] == args.stack_name:
            if args.yes or input(f"Delete stack '{args.stack_name}'? [y/N]: ").lower() == 'y':
                client.delete_stack(stack['Id'], endpoint_id)
                print(f"✓ Stack '{args.stack_name}' deleted")
                return 0
            else:
                print("Cancelled")
                return 0
    
    print(f"✗ Stack '{args.stack_name}' not found")
    return 1


def main():
    parser = argparse.ArgumentParser(
        description='Portainer API Automation for Docker Swarm',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  List stacks:
    %(prog)s list --url https://portainer:9443 --user admin --password secret

  Deploy stack:
    %(prog)s deploy --url https://portainer:9443 --user admin --password secret \\
        --stack-name myapp --compose-file docker-compose.yml

  Deploy with environment variables:
    %(prog)s deploy --url https://portainer:9443 --user admin --password secret \\
        --stack-name myapp --compose-file docker-compose.yml \\
        --env NODE_ENV=production --env DEBUG=false

  Delete stack:
    %(prog)s delete --url https://portainer:9443 --user admin --password secret \\
        --stack-name myapp --yes
        """
    )
    
    # Global arguments
    parser.add_argument('--url', required=True, help='Portainer URL (e.g., https://portainer:9443)')
    parser.add_argument('--user', '-u', required=True, help='Portainer username')
    parser.add_argument('--password', '-p', required=True, help='Portainer password')
    parser.add_argument('--verify-ssl', action='store_true', help='Verify SSL certificates')
    parser.add_argument('--endpoint', help='Portainer endpoint name (default: first available)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all stacks')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy or update a stack')
    deploy_parser.add_argument('--stack-name', '-n', required=True, help='Stack name')
    deploy_parser.add_argument('--compose-file', '-f', required=True, help='Path to docker-compose.yml')
    deploy_parser.add_argument('--env', '-e', action='append', help='Environment variable (KEY=VALUE)')
    deploy_parser.add_argument('--no-validate', action='store_true', help='Skip deployment validation')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a stack')
    delete_parser.add_argument('--stack-name', '-n', required=True, help='Stack name to delete')
    delete_parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize client
    client = PortainerClient(args.url, verify_ssl=args.verify_ssl)
    
    # Authenticate
    if not client.authenticate(args.user, args.password):
        return 1
    
    # Execute command
    if args.command == 'list':
        return cmd_list(client, args)
    elif args.command == 'deploy':
        return cmd_deploy(client, args)
    elif args.command == 'delete':
        return cmd_delete(client, args)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
