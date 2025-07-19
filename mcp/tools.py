#!/usr/bin/env python3
import json
import socket
import subprocess
import os
import re
import logging
from typing import Dict, Any, Optional
import mcp.types as types

# Configure logging
LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("systemd-mcp-server")

# Configuration with environment variable support
SOCKET_PATH = os.getenv("MCP_MANAGER_SOCKET", "/tmp/mcp_manager.sock")
SOCKET_TIMEOUT = int(os.getenv("MCP_SOCKET_TIMEOUT", "30"))  # seconds
MAX_BUFFER_SIZE = int(os.getenv("MCP_MAX_BUFFER_SIZE", "65536"))  # 64KB
SYSTEMCTL_TIMEOUT = int(os.getenv("MCP_SYSTEMCTL_TIMEOUT", "30"))  # seconds
MAX_LOG_LINES = int(os.getenv("MCP_MAX_LOG_LINES", "10000"))
DEFAULT_LOG_LINES = int(os.getenv("MCP_DEFAULT_LOG_LINES", "50"))

# Security: Allowed systemctl operations and service name validation
ALLOWED_SYSTEMCTL_OPERATIONS = {
    "status", "start", "stop", "restart", "reload", "enable", "disable"
}

def validate_service_name(service_name: str) -> bool:
    """Validate service name for security"""
    # Only allow alphanumeric, hyphens, underscores, dots (standard systemd naming)
    pattern = r'^[a-zA-Z0-9._-]+\.service$|^[a-zA-Z0-9._-]+$'
    if not re.match(pattern, service_name):
        return False
    
    # Prevent path traversal and command injection
    dangerous_chars = ['..', '/', '\\', ';', '&', '|', '`', '$', '(', ')']
    return not any(char in service_name for char in dangerous_chars)

def is_privileged_operation(operation: str) -> bool:
    """Check if operation requires elevated privileges"""
    privileged_ops = {"start", "stop", "restart", "reload", "enable", "disable"}
    return operation in privileged_ops

def send_command_to_manager(command: str, payload: Optional[str] = None) -> Dict[str, Any]:
    """Send command to the MCP manager and return response"""
    logger.debug(f"Sending command to manager: {command} with payload: {payload}")
    sock = None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT)
        sock.connect(SOCKET_PATH)
        
        request = {"command": command}
        if payload:
            request["payload"] = payload
        
        request_data = json.dumps(request).encode('utf-8')
        sock.sendall(request_data)
        
        # Receive data with proper buffer handling
        response_data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
            if len(response_data) > MAX_BUFFER_SIZE:
                raise ValueError("Response too large")
            # Check if we have a complete JSON message
            try:
                json.loads(response_data.decode('utf-8'))
                break
            except json.JSONDecodeError:
                continue
        
        result = json.loads(response_data.decode('utf-8'))
        logger.debug(f"Received response from manager: {result}")
        return result
    except socket.timeout:
        error_msg = "Timeout communicating with manager"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except ConnectionRefusedError:
        error_msg = "MCP manager is not running"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except FileNotFoundError:
        error_msg = "MCP manager socket not found"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = f"Failed to communicate with manager: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    finally:
        if sock:
            sock.close()

def mcp_status() -> Dict[str, Any]:
    """Get status of all systemd MCP servers"""
    return send_command_to_manager("status")

def mcp_start(server_id: str) -> Dict[str, Any]:
    """Start a specific MCP server by ID"""
    return send_command_to_manager("start", server_id)

def mcp_stop(server_id: str) -> Dict[str, Any]:
    """Stop a specific MCP server by ID"""
    return send_command_to_manager("stop", server_id)

def mcp_restart(server_id: str) -> Dict[str, Any]:
    """Restart a specific MCP server by ID"""
    return send_command_to_manager("restart", server_id)

def mcp_apply() -> Dict[str, Any]:
    """Apply configuration and start all configured MCP servers"""
    return send_command_to_manager("apply")

def execute_systemctl_command(operation: str, service_name: str) -> Dict[str, Any]:
    """Execute systemctl command with security validation"""
    logger.info(f"Executing systemctl {operation} {service_name}")
    
    # Validate operation
    if operation not in ALLOWED_SYSTEMCTL_OPERATIONS:
        error_msg = f"Operation '{operation}' not allowed"
        logger.warning(error_msg)
        return {"status": "error", "message": error_msg}
    
    # Validate service name
    if not validate_service_name(service_name):
        error_msg = f"Invalid service name: {service_name}"
        logger.warning(error_msg)
        return {"status": "error", "message": error_msg}
    
    try:
        # Build command with sudo only for privileged operations
        cmd = ["systemctl", operation, service_name]
        if is_privileged_operation(operation):
            # Check if we're already running as root
            if os.geteuid() != 0:
                cmd = ["sudo"] + cmd
        
        logger.debug(f"Executing command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SYSTEMCTL_TIMEOUT
        )
        
        if result.returncode == 0:
            logger.info(f"systemctl {operation} {service_name} completed successfully")
        else:
            logger.warning(f"systemctl {operation} {service_name} failed with exit code {result.returncode}")
        
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        error_msg = f"Command timeout: systemctl {operation} {service_name}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except FileNotFoundError:
        error_msg = "systemctl command not found"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"systemctl {operation} {service_name} failed: {error_msg}")
        return {"status": "error", "message": error_msg}

def systemctl_status(service_name: str) -> Dict[str, Any]:
    """Get systemctl status for a service"""
    return execute_systemctl_command("status", service_name)

def systemctl_start(service_name: str) -> Dict[str, Any]:
    """Start a systemd service"""
    return execute_systemctl_command("start", service_name)

def systemctl_stop(service_name: str) -> Dict[str, Any]:
    """Stop a systemd service"""
    return execute_systemctl_command("stop", service_name)

def systemctl_enable(service_name: str) -> Dict[str, Any]:
    """Enable a systemd service"""
    return execute_systemctl_command("enable", service_name)

def systemctl_disable(service_name: str) -> Dict[str, Any]:
    """Disable a systemd service"""
    return execute_systemctl_command("disable", service_name)

def systemctl_restart(service_name: str) -> Dict[str, Any]:
    """Restart a systemd service"""
    return execute_systemctl_command("restart", service_name)

def systemctl_reload(service_name: str) -> Dict[str, Any]:
    """Reload a systemd service"""
    return execute_systemctl_command("reload", service_name)

def journalctl_logs(service_name: str, lines: int = 50) -> Dict[str, Any]:
    """Get journal logs for a service"""
    # Validate service name
    if not validate_service_name(service_name):
        return {"status": "error", "message": f"Invalid service name: {service_name}"}
    
    # Validate lines parameter
    if not isinstance(lines, int) or lines < 1 or lines > MAX_LOG_LINES:
        return {"status": "error", "message": f"Lines must be between 1 and {MAX_LOG_LINES}"}
    
    try:
        result = subprocess.run(
            ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=SYSTEMCTL_TIMEOUT
        )
        return {
            "status": "ok",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Command timeout: journalctl for {service_name}"}
    except FileNotFoundError:
        return {"status": "error", "message": "journalctl command not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Tool registration for FastMCP
def register_tools(app):
    """Register all tools with FastMCP app"""
    
    @app.tool()
    def status() -> Dict[str, Any]:
        """Get status of all systemd MCP servers"""
        return mcp_status()

    @app.tool()
    def start(server_id: str) -> Dict[str, Any]:
        """Start a specific MCP server by ID"""
        return mcp_start(server_id)

    @app.tool()
    def stop(server_id: str) -> Dict[str, Any]:
        """Stop a specific MCP server by ID"""
        return mcp_stop(server_id)

    @app.tool()
    def restart(server_id: str) -> Dict[str, Any]:
        """Restart a specific MCP server by ID"""
        return mcp_restart(server_id)

    @app.tool()
    def apply() -> Dict[str, Any]:
        """Apply configuration and start all configured MCP servers"""
        return mcp_apply()

    @app.tool()
    def service_status(service_name: str) -> Dict[str, Any]:
        """Get systemctl status for a service"""
        return systemctl_status(service_name)

    @app.tool()
    def service_start(service_name: str) -> Dict[str, Any]:
        """Start a systemd service"""
        return systemctl_start(service_name)

    @app.tool()
    def service_stop(service_name: str) -> Dict[str, Any]:
        """Stop a systemd service"""
        return systemctl_stop(service_name)

    @app.tool()
    def service_enable(service_name: str) -> Dict[str, Any]:
        """Enable a systemd service"""
        return systemctl_enable(service_name)

    @app.tool()
    def service_disable(service_name: str) -> Dict[str, Any]:
        """Disable a systemd service"""
        return systemctl_disable(service_name)

    @app.tool()
    def service_restart(service_name: str) -> Dict[str, Any]:
        """Restart a systemd service"""
        return systemctl_restart(service_name)

    @app.tool()
    def service_reload(service_name: str) -> Dict[str, Any]:
        """Reload a systemd service"""
        return systemctl_reload(service_name)

    @app.tool()
    def service_logs(service_name: str, lines: int = DEFAULT_LOG_LINES) -> Dict[str, Any]:
        """Get journal logs for a service"""
        return journalctl_logs(service_name, lines)

# Unified tool definitions
TOOL_DEFINITIONS = [
    {
        "name": "status",
        "description": "Get status of all systemd MCP servers",
        "function": mcp_status,
        "inputSchema": {"type": "object", "properties": {}},
        "required": []
    },
    {
        "name": "start", 
        "description": "Start a specific MCP server by ID",
        "function": mcp_start,
        "inputSchema": {
            "type": "object",
            "properties": {"server_id": {"type": "string", "description": "Server ID to start"}},
            "required": ["server_id"]
        },
        "required": ["server_id"]
    },
    {
        "name": "stop",
        "description": "Stop a specific MCP server by ID", 
        "function": mcp_stop,
        "inputSchema": {
            "type": "object",
            "properties": {"server_id": {"type": "string", "description": "Server ID to stop"}},
            "required": ["server_id"]
        },
        "required": ["server_id"]
    },
    {
        "name": "restart",
        "description": "Restart a specific MCP server by ID",
        "function": mcp_restart,
        "inputSchema": {
            "type": "object", 
            "properties": {"server_id": {"type": "string", "description": "Server ID to restart"}},
            "required": ["server_id"]
        },
        "required": ["server_id"]
    },
    {
        "name": "apply",
        "description": "Apply configuration and start all configured MCP servers",
        "function": mcp_apply,
        "inputSchema": {"type": "object", "properties": {}},
        "required": []
    },
    {
        "name": "service_status",
        "description": "Get systemctl status for a service",
        "function": systemctl_status,
        "inputSchema": {
            "type": "object",
            "properties": {"service_name": {"type": "string", "description": "Service name"}},
            "required": ["service_name"]
        },
        "required": ["service_name"]
    },
    {
        "name": "service_start",
        "description": "Start a systemd service",
        "function": systemctl_start,
        "inputSchema": {
            "type": "object",
            "properties": {"service_name": {"type": "string", "description": "Service name"}},
            "required": ["service_name"]
        },
        "required": ["service_name"]
    },
    {
        "name": "service_stop",
        "description": "Stop a systemd service",
        "function": systemctl_stop,
        "inputSchema": {
            "type": "object",
            "properties": {"service_name": {"type": "string", "description": "Service name"}},
            "required": ["service_name"]
        },
        "required": ["service_name"]
    },
    {
        "name": "service_enable",
        "description": "Enable a systemd service",
        "function": systemctl_enable,
        "inputSchema": {
            "type": "object",
            "properties": {"service_name": {"type": "string", "description": "Service name"}},
            "required": ["service_name"]
        },
        "required": ["service_name"]
    },
    {
        "name": "service_disable",
        "description": "Disable a systemd service",
        "function": systemctl_disable,
        "inputSchema": {
            "type": "object",
            "properties": {"service_name": {"type": "string", "description": "Service name"}},
            "required": ["service_name"]
        },
        "required": ["service_name"]
    },
    {
        "name": "service_restart",
        "description": "Restart a systemd service",
        "function": systemctl_restart,
        "inputSchema": {
            "type": "object",
            "properties": {"service_name": {"type": "string", "description": "Service name"}},
            "required": ["service_name"]
        },
        "required": ["service_name"]
    },
    {
        "name": "service_reload", 
        "description": "Reload a systemd service",
        "function": systemctl_reload,
        "inputSchema": {
            "type": "object",
            "properties": {"service_name": {"type": "string", "description": "Service name"}},
            "required": ["service_name"]
        },
        "required": ["service_name"]
    },
    {
        "name": "service_logs",
        "description": "Get journal logs for a service",
        "function": journalctl_logs,
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Service name"},
                "lines": {"type": "integer", "description": "Number of lines to retrieve", "default": DEFAULT_LOG_LINES}
            },
            "required": ["service_name"]
        },
        "required": ["service_name"]
    }
]

# Tool definitions for StreamableHTTP
def get_tool_definitions() -> list[types.Tool]:
    """Get list of all available tools for StreamableHTTP"""
    return [
        types.Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["inputSchema"]
        ) for tool in TOOL_DEFINITIONS
    ]

# Tool handler for StreamableHTTP
async def handle_tool_call(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls - shared logic for StreamableHTTP"""
    
    arguments = arguments or {}
    
    try:
        # Find tool in unified definitions
        tool_def = next((tool for tool in TOOL_DEFINITIONS if tool["name"] == name), None)
        if not tool_def:
            raise ValueError(f"Unknown tool: {name}")
        
        # Get function and call it with appropriate arguments
        func = tool_def["function"]
        required_args = tool_def.get("required", [])
        
        # Validate required arguments
        for arg in required_args:
            if arg not in arguments:
                raise ValueError(f"Missing required argument: {arg}")
        
        # Call function with appropriate arguments
        if name in ["status", "apply"]:
            result = func()
        elif name in ["start", "stop", "restart"]:
            result = func(arguments["server_id"])
        elif name.startswith("service_") and name != "service_logs":
            result = func(arguments["service_name"])
        elif name == "service_logs":
            lines = arguments.get("lines", DEFAULT_LOG_LINES)
            result = func(arguments["service_name"], lines)
        else:
            # Fallback for any new tools
            result = func(**arguments)
        
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except KeyError as e:
        error_result = {"status": "error", "message": f"Missing required argument: {str(e)}"}
        return [types.TextContent(type="text", text=json.dumps(error_result, indent=2))]
    except Exception as e:
        error_result = {"status": "error", "message": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_result, indent=2))]