#!/usr/bin/env python3
import argparse
import asyncio

def main():
    parser = argparse.ArgumentParser(description="Systemd MCP Server")
    parser.add_argument(
        "--transport", 
        choices=["stdio", "streamable-http"], 
        default="stdio",
        help="Transport method (default: stdio)"
    )
    parser.add_argument(
        "--host", 
        default="127.0.0.1",
        help="Host to bind to for StreamableHTTP transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Port to bind to for StreamableHTTP transport (default: 8000)"
    )
    
    args = parser.parse_args()
    
    if args.transport == "streamable-http":
        from streamable_http_server import run_streamable_http_server
        asyncio.run(run_streamable_http_server(args.host, args.port))
    else:
        from stdio_server import run_stdio_server
        run_stdio_server()

if __name__ == "__main__":
    main()