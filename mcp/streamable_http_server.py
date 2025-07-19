#!/usr/bin/env python3
import asyncio
import json
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from tools import get_tool_definitions, handle_tool_call

app = Server("systemd-mcp-server")

@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools for StreamableHTTP transport"""
    return get_tool_definitions()

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls for StreamableHTTP transport"""
    return await handle_tool_call(name, arguments)

async def json_response(arg: Any) -> str:
    """Convert response to JSON string"""
    return json.dumps(arg, indent=2)

async def run_streamable_http_server(host: str, port: int):
    """Run StreamableHTTP server"""
    import contextlib
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.types import Scope, Receive, Send
    from typing import AsyncIterator
    
    session_manager = StreamableHTTPSessionManager(
        app=app,
        event_store=None,
        json_response=json_response,
        stateless=True
    )
    
    async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)
    
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            print("✅ StreamableHTTP session manager started!")
            try:
                yield
            finally:
                print("🔄 StreamableHTTP session manager shutting down...")
    
    starlette_app = Starlette(
        debug=True,
        routes=[
            Mount("/", app=handle_streamable_http)
        ],
        lifespan=lifespan,
    )
    
    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    await server.serve()