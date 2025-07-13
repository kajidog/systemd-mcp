#!/bin/bash

# This script is a dummy MCP server to be managed.
# It displays the arguments given at startup to make it easy to identify which process it is.
SERVER_ID=$1
if [ -z "$SERVER_ID" ]; then
  SERVER_ID="Default"
fi

echo "[mcp_server-$SERVER_ID] Starting MCP server simulator (PID: $$)"

# Define function to execute when SIGTERM signal is received
cleanup() {
  echo "[mcp_server-$SERVER_ID] Received SIGTERM. Executing cleanup process..."
  sleep 2
  echo "[mcp_server-$SERVER_ID] Cleanup completed. Shutting down server."
  exit 0
}

# Capture signals with trap command
trap 'cleanup' TERM

# Infinite loop to show server is running
count=0
while true; do
  echo "[mcp_server-$SERVER_ID] Server is running normally... (uptime: $((count * 5)) seconds)"
  count=$((count + 1))
  sleep 5
done
