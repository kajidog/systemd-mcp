# Systemd MCP Server

Model Context Protocol (MCP) server for managing systemd services and MCP server instances.

## Features

### MCP Server Management
- `status()` - Get status of all systemd MCP servers
- `start(server_id)` - Start a specific MCP server by ID
- `stop(server_id)` - Stop a specific MCP server by ID  
- `restart(server_id)` - Restart a specific MCP server by ID
- `apply()` - Apply configuration and start all configured MCP servers

### Systemd Service Management
- `service_status(service_name)` - Get systemctl status for a service
- `service_start(service_name)` - Start a systemd service
- `service_stop(service_name)` - Stop a systemd service
- `service_enable(service_name)` - Enable a systemd service
- `service_disable(service_name)` - Disable a systemd service
- `service_restart(service_name)` - Restart a systemd service
- `service_reload(service_name)` - Reload a systemd service
- `service_logs(service_name, lines=50)` - Get journal logs for a service

## Transport Methods

### stdio
For direct integration with AI assistants (Claude Desktop, mcp-client) through standard input/output.

**Use case:** AI assistant spawns the server process on-demand.

```bash
uv run python main.py --transport stdio
```

### streamable-http
HTTP-based transport for persistent server integration. **Used by systemd service installation.**

**Use case:** Server runs as persistent service, clients connect via HTTP.

```bash
uv run python main.py --transport streamable-http --host 127.0.0.1 --port 8000
```

## Installation

### Standalone Installation (Recommended)
Install only the MCP server:

```bash
# Clone repository and navigate to MCP directory
git clone <repository-url>
cd systemd-mcp/mcp

# Run dedicated installer
sudo ./install.sh
```

### Combined Installation
Install the systemd-mcp manager first, then the MCP server:

```bash
# Clone repository
git clone <repository-url>
cd systemd-mcp

# Install systemd-mcp manager
sudo ./install.sh

# Install MCP server
cd mcp
sudo ./install.sh
```

### Prerequisites
- Python 3.10+
- uv package manager (automatically installed by install.sh)
- systemd (Linux systems)

### Manual Setup (Development)
```bash
# Install dependencies
uv sync

# Run stdio server
uv run python main.py

# Run HTTP server
uv run python main.py --transport streamable-http --port 8000
```

### Installation Options
- `sudo ./install.sh` - Install MCP server only
- `sudo ./install.sh --dry-run` - Test installation without changes
- `sudo ./install.sh --force` - Force reinstallation

### Uninstallation
```bash
# Uninstall MCP server
sudo ./uninstall.sh

# Force uninstall without confirmation
sudo ./uninstall.sh --force

# Test uninstall (dry run)
sudo ./uninstall.sh --dry-run
```

## File Structure

```
mcp/
├── main.py                    # Entry point and transport selection
├── stdio_server.py           # FastMCP stdio server
├── streamable_http_server.py  # StreamableHTTP server  
├── tools.py                   # Tool implementations and definitions
├── pyproject.toml            # Project configuration
├── install.sh                # Installation script
├── uninstall.sh              # Uninstallation script
├── __init__.py               # Package initialization
└── README.md                 # This file
```

## Usage Examples

### With AI Assistants (stdio - on-demand)
Configure in your AI assistant's MCP settings for direct process spawning:

```json
{
  "mcpServers": {
    "systemd-mcp": {
      "command": "uv",
      "args": ["run", "python", "/opt/systemd-mcp-server/main.py"],
      "cwd": "/opt/systemd-mcp-server"
    }
  }
}
```

### HTTP Integration (persistent service)
When installed via `sudo ./install.sh`, the server runs as a systemd service:

- **Install location:** `/opt/systemd-mcp-server`
- **Endpoint:** `http://localhost:8000` (default)
- **Service:** `sudo systemctl status systemd-mcp-server`
- **Logs:** `sudo journalctl -u systemd-mcp-server -f`

### Claude Code Integration
```bash
# Add to Claude Code
claude mcp add --transport http systemd http://127.0.0.1:8000/mcp
```

## Dependencies

- **mcp[cli]>=0.5.0** - MCP Python SDK
- **uvicorn>=0.30.0** - ASGI server for HTTP transport
- **starlette>=0.47.0** - Web framework for HTTP transport

All dependencies are automatically installed via `uv sync` or the system installer.

## Configuration

The server communicates with the systemd MCP manager through a Unix socket at `/tmp/mcp_manager.sock`. Ensure the main systemd-mcp manager is running before using this server.

## Development

### Adding New Tools
1. Add the tool implementation function to `tools.py`
2. Register the tool in `register_tools()` for FastMCP
3. Add the tool definition to `get_tool_definitions()` for StreamableHTTP
4. Add the tool handler to `handle_tool_call()` for StreamableHTTP

### Testing
```bash
# Test imports
uv run python -c "import tools; print('✅ All imports successful')"

# Test server startup
uv run python main.py --help

# Test stdio server (Ctrl+C to exit)
uv run python main.py --transport stdio

# Test HTTP server (Ctrl+C to exit)
uv run python main.py --transport streamable-http --port 8001
```

### Service Management
```bash
# Check service status
sudo systemctl status systemd-mcp-server

# Start/stop service
sudo systemctl start systemd-mcp-server
sudo systemctl stop systemd-mcp-server

# View logs
sudo journalctl -u systemd-mcp-server -f
```
