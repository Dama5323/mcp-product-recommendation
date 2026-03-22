"""
Everyday Productivity Accelerators - Backend
Real Strands Agent integration with MCP servers
"""

import os
import json
import logging
import asyncio
import subprocess
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Strands imports
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters, stdio_client
from mcpmanager import mcp_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("boto3").setLevel(logging.WARNING)

# Store server logs
server_logs: Dict[str, List[str]] = {}
mcp_servers = {}  # Initialize early to avoid loading issues
mcp_clients = {}  # Store MCP client instances


def add_server_log(
    server_name: str, message: str, level: str = "info", details: Dict = None
):
    timestamp = datetime.now().isoformat()

    # Create structured log entry
    log_entry = {
        "timestamp": timestamp,
        "server": server_name,
        "level": level,
        "message": message,
        "details": details or {},
    }

    if server_name not in server_logs:
        server_logs[server_name] = []

    # Prevent duplicate consecutive messages (but allow tool executions)
    if server_logs[server_name] and not message.startswith("Executing "):
        last_log = server_logs[server_name][-1]
        if isinstance(last_log, dict) and last_log.get("message") == message:
            return  # Skip duplicate message

    server_logs[server_name].append(log_entry)

    # Keep only last 50 logs per server
    if len(server_logs[server_name]) > 50:
        server_logs[server_name] = server_logs[server_name][-50:]


# Global agent cache - session-based
session_agents = {}

# Global tools cache
cached_tools = []
tools_last_updated = None

# Session token tracking
session_token_usage = {}  # session_id -> {"total_input": int, "total_output": int}


def refresh_tools_cache():
    """Refresh the global tools cache"""
    global cached_tools, tools_last_updated

    try:
        cached_tools = mcp_manager.get_all_tools(active_only=True)
        tools_last_updated = datetime.now()
        add_server_log(
            "system",
            f"Tools cache refreshed: {len(cached_tools)} tools loaded",
            level="info",
            details={"tool_count": len(cached_tools)},
        )
    except Exception as e:
        add_server_log(
            "system",
            f"Error refreshing tools cache: {str(e)}",
            level="error",
            details={"error": str(e)},
        )
        cached_tools = []


def get_cached_tools():
    """Get cached tools, refresh if empty"""
    global cached_tools

    if not cached_tools:
        refresh_tools_cache()

    return cached_tools


# Initialize MCP manager after function definitions
mcp_manager.initialize_default_clients()
add_server_log(
    "system",
    f"MCP Manager initialized with clients: {mcp_manager.get_active_clients()}",
    level="info",
    details={"active_clients": mcp_manager.get_active_clients()},
)

# Pre-load tools cache
refresh_tools_cache()


def get_or_create_session_agent(session_id: str, model_id: str) -> Agent:
    """Get or create a cached agent for the given session and model"""
    agent_key = f"{session_id}:{model_id}"

    if agent_key not in session_agents:
        # Get cached tools (pre-loaded)
        tools = get_cached_tools()
        add_server_log(
            "system",
            f"Creating session agent with {len(tools)} cached tools for {session_id}:{model_id}",
            level="info",
            details={
                "session_id": session_id,
                "model_id": model_id,
                "tool_count": len(tools),
            },
        )

        # Simple system prompt with Nova thinking control
        base_system_prompt = "You are a helpful AI assistant. Use available tools when needed to answer user questions. Maintain conversation context across multiple turns."
        
        # Add thinking control for Nova models
        if "nova" in model_id.lower():
            system_prompt = base_system_prompt + "\n\nIMPORTANT: Do not use <thinking> tags or show your reasoning process. Provide direct, clear responses without exposing internal thought processes."
        else:
            system_prompt = base_system_prompt

        # Create agent with consistent configuration
        agent = create_strands_agent(model_id, system_prompt, tools)

        session_agents[agent_key] = agent
        add_server_log(
            "system",
            f"Session agent cached for {session_id}:{model_id}",
            level="info",
            details={"session_id": session_id, "model_id": model_id},
        )

    return session_agents[agent_key]


def get_session_messages_for_ui(session_id: str, model_id: str) -> List[Dict]:
    """Get session messages formatted for UI from the actual agent"""
    agent_key = f"{session_id}:{model_id}"

    if agent_key not in session_agents:
        return []

    agent = session_agents[agent_key]

    # Get messages from agent.messages
    if not hasattr(agent, "messages") or not agent.messages:
        return []

    ui_messages = []

    for msg in agent.messages:
        # Skip system messages
        if msg.get("role") == "system":
            continue
        
        # Skip tool result messages (they appear as user role but contain toolResult)
        content = msg.get("content", [])
        if isinstance(content, list):
            # Check if this is a tool result message
            has_tool_result = any(
                isinstance(item, dict) and "toolResult" in item 
                for item in content
            )
            if has_tool_result:
                continue  # Skip tool result messages from UI

        # Convert Strands message format to UI format
        if msg.get("role") in ["user", "assistant"]:
            message_content = ""

            # Extract content from Strands message format
            if isinstance(content, str):
                message_content = content
            elif isinstance(content, list):
                text_parts = []
                for content_item in content:
                    if isinstance(content_item, dict):
                        if "text" in content_item:
                            text_parts.append(content_item["text"])
                        elif "toolUse" in content_item:
                            tool_use = content_item["toolUse"]
                            text_parts.append(
                                f"🔧 Used tool: {tool_use.get('name', 'unknown')}"
                            )
                    else:
                        text_parts.append(str(content_item))
                message_content = "\n".join(text_parts)

            # Only add if there's actual content
            if message_content.strip():
                ui_messages.append(
                    {
                        "id": len(ui_messages) + 1,
                        "role": msg["role"],
                        "content": message_content,
                        "timestamp": datetime.now().isoformat(),
                        "model": model_id if msg["role"] == "assistant" else None,
                    }
                )

    return ui_messages


def refresh_agents():
    """Refresh tools cache and clear agent cache"""
    global session_agents

    # Refresh tools cache first
    refresh_tools_cache()

    # Clear agent cache so they get recreated with new tools
    session_agents.clear()
    add_server_log(
        "system",
        "Tools and agent cache refreshed - agents will recreate with new tools",
        level="info",
        details={"cleared_sessions": len(session_agents)},
    )


def load_mcp_config():
    """Load MCP configuration from mcp.json file"""
    global mcp_servers
    if mcp_servers:  # Already loaded
        return mcp_servers

    try:
        config_path = os.path.join(os.path.dirname(__file__), "mcp.json")
        with open(config_path, "r") as f:
            config = json.load(f)

        # Transform config to our internal format
        mcp_servers = {}

        # Check for both 'servers' and 'mcpServers' keys for compatibility
        servers_config = config.get("mcpServers", config.get("servers", {}))

        for server_name, server_config in servers_config.items():
            mcp_servers[server_name] = {
                "name": server_config.get(
                    "name", server_name.replace("_", " ").title()
                ),
                "enabled": server_config.get("enabled", True),
                "description": server_config.get(
                    "description", f"{server_name.replace('_', ' ').title()} MCP server"
                ),
                "status": "ready" if server_config.get("enabled", True) else "disabled",
                "command": server_config.get("command", ""),
                "args": server_config.get("args", []),
                "env": server_config.get("env", {}),
            }

        add_server_log("system", f"Loaded {len(mcp_servers)} MCP servers")
        return mcp_servers

    except Exception as e:
        logger.error(f"Error loading MCP config: {e}")
        add_server_log("system", f"Error loading MCP config: {e}")
        return {}


def save_mcp_config(servers_config):
    """Save MCP configuration to mcp.json file"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), "mcp.json")

        # Load existing config
        with open(config_path, "r") as f:
            config = json.load(f)

        # Get the correct servers key
        servers_key = "mcpServers" if "mcpServers" in config else "servers"

        # Update server enabled states
        for server_name, server_info in servers_config.items():
            if server_name in config.get(servers_key, {}):
                config[servers_key][server_name]["enabled"] = server_info.get(
                    "enabled", True
                )

        # Save updated config
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        add_server_log("system", "Configuration saved")

    except Exception as e:
        logger.error(f"Error saving MCP config: {e}")
        add_server_log("system", f"Error saving config: {e}")


# Token estimation removed - we now rely on actual API response usage data

def create_bedrock_model(model_id: str, temperature: float = 0.7, region_name: str = None) -> BedrockModel:
    """Create a BedrockModel with consistent configuration.
    
    Args:
        model_id: The Bedrock model ID
        temperature: Temperature for generation (default: 0.7)
        region_name: AWS region name (optional)
    
    Returns:
        Configured BedrockModel instance
    """
    # Create simple model configuration
    model_config = {
        "model_id": model_id,
        "temperature": temperature,
    }
    
    # Add region if specified
    if region_name:
        model_config["region_name"] = region_name
    
    return BedrockModel(**model_config)

def create_strands_agent(model_id: str, system_prompt: str, tools: list = None, region_name: str = None) -> Agent:
    """Create a Strands Agent with consistent BedrockModel configuration.
    
    Args:
        model_id: The Bedrock model ID
        system_prompt: System prompt for the agent
        tools: List of tools to provide to the agent (optional)
        region_name: AWS region name (optional)
    
    Returns:
        Configured Strands Agent instance
    """
    model = create_bedrock_model(model_id, temperature=0.7, region_name=region_name)
    
    # Add thinking control instruction for Nova models via system prompt
    enhanced_system_prompt = system_prompt
    if "nova" in model_id.lower():
        enhanced_system_prompt += "\n\nIMPORTANT: Do not use <thinking> tags or show your reasoning process. Provide direct, clear responses without exposing internal thought processes."
    
    return Agent(
        model=model,
        system_prompt=enhanced_system_prompt,
        tools=tools or []
    )


def setup_mcp_servers():
    """Setup MCP servers using stdio transport"""
    global mcp_clients

    for server_name, server_config in mcp_servers.items():
        if not server_config.get("enabled", True):
            add_server_log(server_name, "Server disabled, skipping")
            continue

        try:
            # Prepare command - find available python commandㅂ
            def find_python_command():
                import shutil

                if shutil.which("python"):
                    return "python"
                elif shutil.which("python3"):
                    return "python3"
                else:
                    return "python"  # fallback

            default_python = find_python_command()
            command = server_config.get("command", default_python)
            args = server_config.get("args", [])

            # Build full command
            full_command = [command] + args

            add_server_log(
                server_name, f"Setting up MCP server: {' '.join(full_command)}"
            )

            # Create MCP Client for stdio transport (similar to the example)
            mcp_client = MCPClient(
                lambda: stdio_client(
                    StdioServerParameters(
                        command=command, args=args, cwd=os.path.dirname(__file__)
                    )
                )
            )

            mcp_clients[server_name] = mcp_client
            mcp_servers[server_name]["status"] = "ready"
            add_server_log(server_name, "MCP server ready")

        except Exception as e:
            add_server_log(server_name, f"Setup error: {str(e)}")
            mcp_servers[server_name]["status"] = "error"


def get_all_mcp_tools():
    """Get all tools from MCP servers"""
    all_tools = []

    for server_name, mcp_client in mcp_clients.items():
        try:
            # Note: We don't use 'with' here as tools are used later in the agent
            # The agent will handle the context when it uses the tools
            tools = mcp_client.list_tools_sync()
            if tools:
                all_tools.extend(tools)
                add_server_log(server_name, f"Loaded {len(tools)} tools")
        except Exception as e:
            add_server_log(server_name, f"Tool loading error: {str(e)}")

    return all_tools


# Available models with new Claude versions and GPT-OSS models
available_models = [
    {
        "id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "name": "Claude Sonnet 4.5",
        "description": "Most capable model for building real-world agents and handling complex, long-horizon tasks",
    },
    {
        "id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "name": "Claude Sonnet 4",
        "description": "Advanced Claude model with superior reasoning",
    },

    {
        "id": "us.amazon.nova-pro-v1:0",
        "name": "Amazon Nova Pro",
        "description": "High-performance multimodal model",
    },
    {
        "id": "openai.gpt-oss-20b-1:0",
        "name": "GPT-OSS 20B",
        "description": "Open-source GPT model with 20B parameters",
    },
    {
        "id": "openai.gpt-oss-120b-1:0",
        "name": "GPT-OSS 120B",
        "description": "Large open-source GPT model with 120B parameters",
    },
]

# Initialize Strands Agents for different models
agents_cache = {}


def create_mcp_agent_tools():
    """Create MCP tools that can be used by the agent"""
    from strands import tool

    mcp_tools = []

    for server_name, mcp_client in mcp_clients.items():
        if not mcp_servers[server_name].get("enabled", True):
            continue

        # Create a tool function for each MCP server
        @tool
        def mcp_server_tool(
            query: str, server_name=server_name, client=mcp_client
        ) -> str:
            f"""
            Interact with {server_name} MCP server

            Args:
                query: The user's query or command

            Returns:
                Response from the MCP server
            """
            try:
                with client:
                    tools = client.list_tools_sync()
                    if tools:
                        # For now, we'll use the first available tool
                        # In a real implementation, you'd parse the query and select the appropriate tool
                        return (
                            f"MCP server {server_name} has {len(tools)} available tools"
                        )
                    else:
                        return f"No tools available on {server_name} server"
            except Exception as e:
                return f"Error accessing {server_name} server: {str(e)}"

        # Set the tool name dynamically
        mcp_server_tool.__name__ = f"{server_name}_tool"
        mcp_tools.append(mcp_server_tool)

    return mcp_tools


def get_strands_agent(model_id: str):
    """Get or create a Strands agent for the specified model"""
    try:
        add_server_log("system", f"Creating agent for {model_id}")

        # Get MCP tools
        mcp_tools = create_mcp_agent_tools()

        # Create agent with MCP tools integration
        base_system_prompt = f"""You are a helpful AI assistant for AWS Productivity Accelerators. 
        You have access to various tools and services through MCP servers.
        
        Available MCP servers: {len(mcp_clients)} servers
        
        Always provide clear, accurate, and helpful responses in markdown format when appropriate.
        Use the available tools when relevant to answer user questions. Analyze the user's request
        and determine which tools would be most helpful to provide a complete response."""

        # Add thinking control for Nova models
        if "nova" in model_id.lower():
            system_prompt = base_system_prompt + "\n\nIMPORTANT: Do not use <thinking> tags or show your reasoning process. Provide direct, clear responses without exposing internal thought processes."
        else:
            system_prompt = base_system_prompt

        agent = create_strands_agent(
            model_id, 
            system_prompt, 
            mcp_tools, 
            region_name=os.environ.get("AWS_REGION", "us-west-2")
        )

        add_server_log(
            "system", f"Agent ready with {len(mcp_tools)} MCP tools: {model_id}"
        )
        return agent

    except Exception as e:
        logger.error(f"Error creating Strands agent for {model_id}: {e}")
        add_server_log("system", f"Agent error: {str(e)[:50]}...")
        raise


# Load MCP servers from configuration at startup
load_mcp_config()


def initialize_mcp_servers():
    """Initialize all MCP servers"""
    add_server_log("system", "Initializing MCP servers...")

    # Setup MCP servers
    setup_mcp_servers()

    add_server_log("system", "MCP initialization complete")


# FastAPI app setup
app = FastAPI(title="Productivity Accelerators API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class ImageData(BaseModel):
    data: str  # base64 encoded image data
    name: str  # filename


class ChatMessage(BaseModel):
    model_config = {"protected_namespaces": ()}

    message: str
    model_id: Optional[str] = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    session_id: Optional[str] = "default"
    images: Optional[List[ImageData]] = None


class ChatResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    response: str
    model_id: str
    tokens: Dict[str, int]


async def stream_ai_response_with_images(
    message: str,
    model_id: str,
    session_id: str = "default",
    images: List[ImageData] = None,
):
    """Stream AI response with image support using session-based cached Strands Agent"""

    accumulated_text = ""
    # Track tool executions to log only when complete
    active_tools = {}  # tool_id -> tool_info
    # Track if we got real tokens from metrics
    got_real_tokens = False
    # Track previous token usage to calculate incremental usage
    last_input_tokens = 0
    last_output_tokens = 0

    try:
        add_server_log(
            "system",
            f"Processing [{session_id}]: {message[:30]}{'... (with images)' if images else '...'}",
        )

        # Use MCP context for streaming with session agent
        with mcp_manager.get_active_context():
            # Get session-based cached agent (maintains conversation history)
            agent = get_or_create_session_agent(session_id, model_id)

            # Prepare message with images if provided
            if images and len(images) > 0:
                # For now, we'll include image information in the message
                # In a more advanced implementation, you'd convert images to proper format for the model
                image_info = f"\n[User provided {len(images)} image(s): {', '.join([img.name for img in images])}]"
                enhanced_message = message + image_info
                add_server_log(
                    "system", f"Enhanced message with {len(images)} image(s)"
                )
            else:
                enhanced_message = message

            # Use stream_async for real streaming
            agent_stream = agent.stream_async(enhanced_message)
            
            # Track the final response for token usage
            final_response = None

            async for event in agent_stream:
                # Handle streaming data (main content)
                if "data" in event:
                    text_data = event["data"]
                    accumulated_text += text_data
                    yield f"data: {json.dumps({'type': 'content', 'content': text_data})}\n\n"

                # Handle Strands Agent events
                elif "event" in event:
                    event_data = event["event"]

                    # Tool result handling - capture tool results from separate messages
                    if (
                        "messageStart" in event_data
                        and event_data["messageStart"].get("role") == "user"
                    ):
                        # This might be a tool result message, check if it follows a tool execution
                        pass

                    # Tool use start - store tool info
                    elif "contentBlockStart" in event_data:
                        start_data = event_data["contentBlockStart"]
                        if "start" in start_data and "toolUse" in start_data["start"]:
                            tool_use = start_data["start"]["toolUse"]
                            tool_id = tool_use.get("toolUseId", "unknown")
                            tool_name = tool_use.get("name", "unknown")

                            # Store tool info for completion logging
                            active_tools[tool_id] = {
                                "name": tool_name,
                                "input": "",  # Will be accumulated from deltas
                                "started_at": datetime.now().isoformat(),
                                "content_block_index": start_data.get(
                                    "contentBlockIndex", 0
                                ),
                            }

                            yield f"data: {json.dumps({'type': 'tool_use', 'tool_name': tool_name, 'input': {}})}\n\n"

                    # Tool input accumulation
                    elif "contentBlockDelta" in event_data:
                        delta_data = event_data["contentBlockDelta"]
                        if "delta" in delta_data and "toolUse" in delta_data["delta"]:
                            tool_input = delta_data["delta"]["toolUse"].get("input", "")
                            content_block_index = delta_data.get("contentBlockIndex", 0)

                            # Find the active tool by content block index
                            for tool_id, tool_info in active_tools.items():
                                if (
                                    tool_info.get("content_block_index")
                                    == content_block_index
                                ):
                                    tool_info["input"] += tool_input
                                    break

                    # Tool completion - log the completed execution
                    elif "contentBlockStop" in event_data:
                        content_block_index = event_data["contentBlockStop"].get(
                            "contentBlockIndex", 0
                        )

                        # Find and log the completed tool
                        for tool_id, tool_info in list(active_tools.items()):
                            if (
                                tool_info.get("content_block_index")
                                == content_block_index
                            ):
                                tool_name = tool_info["name"]
                                tool_input_str = tool_info["input"]

                                # Parse the accumulated input JSON
                                try:
                                    tool_input = (
                                        json.loads(tool_input_str)
                                        if tool_input_str
                                        else {}
                                    )
                                except:
                                    tool_input = {"raw_input": tool_input_str}

                                # Create readable parameter summary
                                param_summary = []
                                if (
                                    tool_input
                                    and isinstance(tool_input, dict)
                                    and len(tool_input) > 0
                                ):
                                    for key, value in tool_input.items():
                                        if isinstance(value, str) and len(value) > 100:
                                            param_summary.append(
                                                f"{key}: {value[:50]}..."
                                            )
                                        else:
                                            param_summary.append(f"{key}: {value}")

                                if param_summary:
                                    param_text = ", ".join(param_summary)
                                    log_message = f"Executed {tool_name}({param_text})"
                                else:
                                    log_message = f"Executed {tool_name}()"

                                # Log the completed tool execution
                                add_server_log(
                                    "tool_execution",
                                    log_message,
                                    level="info",
                                    details={
                                        "tool_name": tool_name,
                                        "parameters": (
                                            tool_input
                                            if tool_input and len(tool_input) > 0
                                            else None
                                        ),
                                        "execution_id": tool_id,
                                        "status": "completed",
                                        "user_session": session_id,
                                    },
                                )

                                # Remove from active tools
                                del active_tools[tool_id]
                                break

                # Handle tool result events
                elif "message" in event:

                    user_message = event["message"]
                    if user_message["role"] == "user":
                        if "toolResult" in user_message["content"][0]:
                            tool_result = user_message["content"][0]["toolResult"]
                            tool_content = tool_result["content"][0]["text"]
                            yield f"data: {json.dumps({'type': 'tool_result', 'result': tool_content })}\n\n"

                # Handle completion and get metrics
                elif event.get("complete", False):
                    # Store final response for token extraction
                    if "response" in event:
                        final_response = event["response"]
                    break

                # Handle metrics from stream events (fallback)
                elif "event_loop_metrics" in event:
                    metrics = event["event_loop_metrics"]

                    # Extract token usage from metrics
                    if (
                        hasattr(metrics, "accumulated_usage")
                        and metrics.accumulated_usage
                    ):
                        usage = metrics.accumulated_usage
                        input_tokens = usage.get("inputTokens", 0)
                        output_tokens = usage.get("outputTokens", 0)
                        total_tokens = usage.get("totalTokens", input_tokens + output_tokens)

                        # Only send token count when we have meaningful output
                        if output_tokens > 0 and not got_real_tokens:
                            got_real_tokens = True
                            yield f"data: {json.dumps({'type': 'tokens', 'input': input_tokens, 'output': output_tokens, 'total': total_tokens})}\n\n"

            # Extract token usage from final response only (no estimation)
            if not got_real_tokens:
                # Try to get usage from Strands Agent response
                if final_response and isinstance(final_response, dict) and 'usage' in final_response:
                    usage = final_response['usage']
                    input_tokens = usage.get('inputTokens', 0)
                    output_tokens = usage.get('outputTokens', 0)
                    total_tokens = usage.get('totalTokens', input_tokens + output_tokens)
                    yield f"data: {json.dumps({'type': 'tokens', 'input': input_tokens, 'output': output_tokens, 'total': total_tokens})}\n\n"
                # If no usage data available, don't send token info (better than wrong estimation)

        # End stream
        yield "data: [DONE]\n\n"

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        add_server_log("system", f"Stream error: {str(e)[:50]}...")

        yield f"data: {json.dumps({'type': 'content', 'content': error_msg})}\n\n"
        yield "data: [DONE]\n\n"


async def stream_plain_response(message: str, model_id: str):
    """Stream plain text response using Strands Agent - tool agnostic"""
    add_server_log("system", f"Starting plain text streaming for: {message[:50]}...")

    try:
        # Get tools from MCP manager
        tools = mcp_manager.get_all_tools(active_only=True)

        # Create system prompt with Nova thinking control
        base_prompt = "You are a helpful AI assistant. Use available tools when needed to answer user questions."
        if "nova" in model_id.lower():
            system_prompt = base_prompt + "\n\nIMPORTANT: Do not use <thinking> tags or show your reasoning process. Provide direct, clear responses without exposing internal thought processes."
        else:
            system_prompt = base_prompt

        # Create Strands agent with consistent configuration
        agent = create_strands_agent(model_id, system_prompt, tools)

        with mcp_manager.get_active_context():
            # Execute agent and get response
            response = agent(message)
            response_text = str(response)

            # Stream response in chunks
            chunk_size = 40
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i : i + chunk_size]
                yield chunk
                await asyncio.sleep(0.08)  # Small delay for streaming effect

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        add_server_log("system", f"Plain text streaming error: {str(e)[:50]}...")
        yield error_msg


@app.get("/")
async def root():
    return {
        "message": "Everyday Productivity Accelerators API",
        "status": "online",
        "version": "2.0",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/models")
async def get_models():
    return available_models


@app.get("/mcp/servers")
async def get_mcp_servers():
    """Get all MCP servers with their current status"""
    return mcp_servers


class ToggleRequest(BaseModel):
    enabled: bool


@app.post("/mcp/servers/{server_name}/toggle")
async def toggle_mcp_server(server_name: str, request: ToggleRequest):
    """Toggle MCP server enabled/disabled state"""
    global mcp_servers

    if server_name not in mcp_servers:
        raise HTTPException(status_code=404, detail="Server not found")

    enabled = request.enabled

    # Update server state
    mcp_servers[server_name]["enabled"] = enabled
    mcp_servers[server_name]["status"] = "ready" if enabled else "disabled"

    # Save to configuration file
    save_mcp_config(mcp_servers)

    # Update MCP client active state and refresh agent cache
    mcp_manager.set_client_active(server_name, enabled)
    refresh_agents()

    action = "enabled" if enabled else "disabled"
    add_server_log(server_name, f"Server {action}")

    return {"success": True, "server": server_name, "enabled": enabled}


@app.get("/mcp/logs")
async def get_mcp_logs():
    return server_logs


@app.delete("/mcp/logs")
async def clear_mcp_logs():
    global server_logs
    server_logs.clear()
    add_server_log("system", "Logs cleared")
    return {"message": "Logs cleared"}


@app.post("/mcp/initialize")
async def initialize_mcp():
    """Initialize all MCP servers"""
    try:
        initialize_mcp_servers()
        mcp_manager.initialize_default_clients()
        refresh_agents()  # This will refresh tools cache and clear agents
        return {"message": "MCP servers initialized", "status": "success"}
    except Exception as e:
        add_server_log("system", f"Initialization error: {str(e)}")
        return {"message": f"Initialization failed: {str(e)}", "status": "error"}


@app.get("/mcp/tools")
async def get_mcp_tools_endpoint():
    """Get all available MCP tools from cache"""
    try:
        tools = get_cached_tools()
        tool_info = []

        for tool in tools:
            # Extract tool information safely
            tool_data = {
                "name": getattr(tool, "name", "unknown"),
                "description": getattr(tool, "description", ""),
                "type": tool.__class__.__name__,
            }
            tool_info.append(tool_data)

        return {
            "tools": tool_info,
            "count": len(tools),
            "last_updated": (
                tools_last_updated.isoformat() if tools_last_updated else None
            ),
        }
    except Exception as e:
        return {"error": str(e), "tools": [], "count": 0}


@app.get("/agents/status")
async def get_agents_status():
    """Get cached session agents status"""
    agents_info = {}
    for agent_key, agent in session_agents.items():
        session_id, model_id = agent_key.split(":", 1)
        agents_info[agent_key] = {
            "session_id": session_id,
            "model_id": model_id,
            "created": True,
            "tools_count": (
                len(agent.tools) if hasattr(agent, "tools") and agent.tools else 0
            ),
        }

    return {"session_agents": agents_info, "count": len(session_agents)}


@app.post("/agents/refresh")
async def refresh_agents_endpoint():
    """Refresh all cached agents"""
    refresh_agents()
    return {"message": "Agent cache refreshed", "status": "success"}


@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear a specific session's agent"""
    global session_agents

    # Remove all agents for this session
    keys_to_remove = [
        key for key in session_agents.keys() if key.startswith(f"{session_id}:")
    ]
    for key in keys_to_remove:
        del session_agents[key]

    add_server_log("system", f"Cleared session: {session_id}")
    return {"message": f"Session {session_id} cleared", "status": "success"}


@app.get("/sessions")
async def get_sessions():
    """Get all active sessions"""
    sessions = {}
    for agent_key in session_agents.keys():
        session_id, model_id = agent_key.split(":", 1)
        if session_id not in sessions:
            sessions[session_id] = []
        sessions[session_id].append(model_id)

    return {"sessions": sessions, "count": len(sessions)}


@app.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str, model_id: str = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
):
    """Get conversation history for a session from the actual agent"""
    try:
        # Get messages from the actual agent
        messages = get_session_messages_for_ui(session_id, model_id)

        agent_key = f"{session_id}:{model_id}"
        exists = agent_key in session_agents

        add_server_log(
            "system",
            f"Session history request: {session_id} - Found {len(messages)} messages, exists: {exists}",
        )

        return {
            "messages": messages,
            "session_id": session_id,
            "model_id": model_id,
            "exists": exists,
            "count": len(messages),
        }

    except Exception as e:
        add_server_log("system", f"Error getting session history: {str(e)}")
        return {
            "messages": [],
            "session_id": session_id,
            "exists": False,
            "error": str(e),
        }


@app.post("/chat")
async def chat_endpoint(chat_message: ChatMessage, request: Request):
    """Chat endpoint using Strands Agent with streaming and image support"""
    try:
        # Check if model is available
        model_ids = [model["id"] for model in available_models]
        if chat_message.model_id not in model_ids:
            raise HTTPException(status_code=400, detail="Model not available")

        # Log image information if present
        if chat_message.images:
            add_server_log("system", f"Received {len(chat_message.images)} image(s)")

        # Check if client accepts streaming
        accept_header = request.headers.get("accept", "")
        if "text/event-stream" in accept_header:
            # Return SSE streaming response with image support
            return StreamingResponse(
                stream_ai_response_with_images(
                    chat_message.message,
                    chat_message.model_id,
                    chat_message.session_id,
                    chat_message.images,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "X-Accel-Buffering": "no",
                },
            )
        elif "text/plain" in accept_header:
            # Return plain text streaming
            return StreamingResponse(
                stream_plain_response(chat_message.message, chat_message.model_id),
                media_type="text/plain",
            )
        else:
            # Default SSE streaming with image support
            return StreamingResponse(
                stream_ai_response_with_images(
                    chat_message.message,
                    chat_message.model_id,
                    chat_message.session_id,
                    chat_message.images,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                },
            )

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        add_server_log("system", f"Chat error: {str(e)[:50]}...")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Initialize MCP servers on startup"""
    try:
        initialize_mcp_servers()
    except Exception as e:
        logger.error(f"Failed to initialize MCP servers: {e}")
        add_server_log("system", f"Startup MCP init failed: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup MCP servers on shutdown"""
    add_server_log("system", "Shutting down MCP servers...")
    # Clean shutdown for stdio-based servers happens automatically


if __name__ == "__main__":
    import uvicorn

    # Set AWS region if not set
    if not os.environ.get("AWS_REGION"):
        os.environ["AWS_REGION"] = "us-west-2"

    add_server_log("system", "Backend starting...")
    print("🚀 Starting Productivity Accelerators Backend")
    print("📊 Using Strands Agents for AI processing")
    print("🔧 MCP servers will initialize automatically (stdio transport)")
    print(f"🌍 AWS Region: {os.environ.get('AWS_REGION', 'us-west-2')}")

    uvicorn.run(app, host="0.0.0.0", port=8000)
