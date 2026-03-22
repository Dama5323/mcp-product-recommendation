"""
MCP Client Manager for Strands Agents
Based on Strands official documentation examples
"""

import os
import json
import logging
from contextlib import contextmanager, ExitStack
from typing import Dict, List, Optional, Any
from mcp import stdio_client, StdioServerParameters
from strands.tools.mcp import MCPClient

logger = logging.getLogger(__name__)

class MCPClientManager:
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.active_clients: List[str] = []
        
    def add_client(self, name: str, client: MCPClient):
        """Add an MCP client"""
        self.clients[name] = client
        if name not in self.active_clients:
            self.active_clients.append(name)
        logger.info(f"Added MCP client: {name}")
    
    def remove_client(self, name: str):
        """Remove an MCP client"""
        if name in self.clients:
            del self.clients[name]
        if name in self.active_clients:
            self.active_clients.remove(name)
        logger.info(f"Removed MCP client: {name}")
    
    def get_client(self, name: str) -> Optional[MCPClient]:
        """Get a specific MCP client"""
        return self.clients.get(name)
    
    def get_active_clients(self) -> List[str]:
        """Get list of active client names"""
        return self.active_clients.copy()
    
    def set_client_active(self, name: str, active: bool):
        """Set a client as active or inactive"""
        if name in self.clients:
            if active and name not in self.active_clients:
                self.active_clients.append(name)
                logger.info(f"Activated MCP client: {name}")
            elif not active and name in self.active_clients:
                self.active_clients.remove(name)
                logger.info(f"Deactivated MCP client: {name}")
        else:
            logger.warning(f"Client {name} not found")
    
    def initialize_default_clients(self):
        """Initialize default MCP clients from config"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'mcp.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Clear existing clients
            self.clients.clear()
            self.active_clients.clear()
            
            # Get servers config (support both 'servers' and 'mcpServers' keys)
            servers_config = config.get('mcpServers', config.get('servers', {}))
            
            for server_name, server_config in servers_config.items():
                try:
                    # Check if it's a remote HTTP server (AgentCore)
                    if server_config.get('type') == 'http':
                        url = server_config.get('url', '')
                        
                        # Skip if URL is placeholder
                        if 'REPLACE_WITH' in url or not url.startswith('http'):
                            logger.info(f"Skipping {server_name}: URL not configured")
                            continue
                        
                        # Initialize remote HTTP client
                        self.initialize_http_client(server_name, url)
                    else:
                        # Local stdio server (existing code)
                        command = server_config.get('command', 'python3')
                        args = server_config.get('args', [])
                        
                        # Create MCPClient with lambda function as per Strands docs
                        mcp_client = MCPClient(
                            lambda cmd=command, arguments=args: stdio_client(
                                StdioServerParameters(
                                    command=cmd,
                                    args=arguments,
                                    cwd=os.path.dirname(__file__),
                                    env=os.environ
                                )
                            )
                        )
                        
                        self.add_client(server_name, mcp_client)
                    
                    # Set active state based on config
                    enabled = server_config.get('enabled', True)
                    if not enabled and server_name in self.active_clients:
                        self.active_clients.remove(server_name)
                    
                    logger.info(f"Initialized MCP client: {server_name} (enabled: {enabled})")
                    
                except Exception as e:
                    logger.error(f"Failed to initialize MCP client {server_name}: {e}")
            
            logger.info(f"Active MCP clients: {self.active_clients}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP clients: {e}")
    
    def initialize_http_client(self, server_name: str, url: str):
        """Initialize an HTTP MCP client for AgentCore Runtime with SigV4 auth"""
        try:
            from streamable_http_sigv4 import streamablehttp_client_with_sigv4
            import boto3
            import os
            
            session = boto3.Session()
            credentials = session.get_credentials()
            region = session.region_name
            
            # If region is not set in session, try to get from environment or use default
            if not region:
                region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
                if not region:
                    region = 'us-west-2'  # Default fallback
                    logger.warning(f"No region configured, using default: {region}")
            
            # Create remote MCP client with SigV4 authentication
            mcp_client = MCPClient(
                lambda: streamablehttp_client_with_sigv4(
                    url=url,
                    credentials=credentials,
                    service="bedrock-agentcore",
                    region=region,
                )
            )
            
            self.add_client(server_name, mcp_client)
            logger.info(f"Initialized HTTP MCP client with SigV4: {server_name} at {url}")
            
        except Exception as e:
            logger.error(f"Failed to initialize HTTP MCP client {server_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def get_all_tools(self, active_only: bool = True) -> List[Any]:
        """Get all tools from active MCP clients"""
        all_tools = []
        
        clients_to_use = self.active_clients if active_only else list(self.clients.keys())
        
        for client_name in clients_to_use:
            if client_name not in self.clients:
                continue
                
            client = self.clients[client_name]
            
            try:
                # Use client in context to get tools (Strands way)
                with client:
                    tools = client.list_tools_sync()
                    if tools:
                        all_tools.extend(tools)
                        logger.info(f"Loaded {len(tools)} tools from {client_name}")
            except Exception as e:
                logger.error(f"Error loading tools from {client_name}: {e}")
        
        return all_tools
    
    @contextmanager
    def get_active_context(self):
        """Get context manager for all active MCP clients"""
        # Use ExitStack to manage multiple context managers
        with ExitStack() as stack:
            contexts = []
            
            for client_name in self.active_clients:
                if client_name in self.clients:
                    try:
                        # Enter context for each client
                        stack.enter_context(self.clients[client_name])
                        contexts.append(client_name)
                    except Exception as e:
                        logger.error(f"Failed to enter context for {client_name}: {e}")
            
            logger.info(f"Entering context with active clients: {contexts}")
            yield contexts

# Global instance
mcp_manager = MCPClientManager() 