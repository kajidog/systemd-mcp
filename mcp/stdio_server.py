#!/usr/bin/env python3
from mcp.server.fastmcp import FastMCP
from tools import register_tools

app = FastMCP("systemd-mcp-server")

# Register all tools from tools.py
register_tools(app)

def run_stdio_server():
    """Run stdio MCP server"""
    app.run()