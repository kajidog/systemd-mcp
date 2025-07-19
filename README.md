# MCP Server Manager

## Overview

MCP Server Manager is a daemon tool for managing multiple server processes (startup, shutdown, monitoring, and automatic restart) based on the configuration file `mcp_server.conf`.

Each server process is automatically assigned a unique ID based on its startup command. Using the `mcpctl` command-line tool, you can operate individual servers by specifying their IDs.

It operates as a `systemd` service and enhances service availability by automatically restarting processes that terminate unexpectedly.

## Key Features

- **Simple Configuration File:** Simply describe the commands of servers you want to manage in `mcp_server.conf`.
- **Flexible ID Management:** Each server command is automatically assigned a unique ID (hash) based on its content, or you can specify custom IDs.
- **Command-line Operations:** Use `mcpctl` to check IDs with `status` and operate individual servers with `start`, `stop`, and `restart`.
- **Automatic Process Restart:** When a process terminates for reasons other than `mcpctl stop`, the daemon automatically restarts it.
- **systemd Integration:** Easy service registration using `mcp-manager.service`.

## Workflow

1. **Configuration:** Edit `/etc/mcp/mcp_server.conf` to describe the startup commands of servers you want to manage, one per line.
2. **Reload:** Execute `sudo systemctl restart mcp-manager.service` to reflect configuration changes to the daemon.
3. **Check:** Run `mcpctl status` to check the status and automatically generated IDs of each server.
4. **Operations:** Use the confirmed IDs with commands like `mcpctl start <ID>` or `mcpctl stop <ID>` to manage individual servers.

## Setup and Installation

### Automatic Installation (Recommended)

1. **Install systemd-mcp Manager**
   ```bash
   sudo ./install.sh
   ```
   
   This script automatically performs the following tasks:
   - Creates necessary directories (`/usr/local/lib/mcp-manager/`, `/etc/mcp/`)
   - Copies `mcp_manager.py` to `/usr/local/lib/mcp-manager/`
   - Copies `mcpctl` to `/usr/local/bin/` (adds to PATH)
   - Copies configuration file with examples to `/etc/mcp/mcp_server.conf`
   - Installs and registers systemd service file
   - Prompts to enable and start the service (defaults to Yes)

2. **Optional: Install MCP Server for AI Integration**
   ```bash
   cd mcp
   sudo ./install.sh
   ```
   
   This provides systemd control tools for AI assistants like Claude Desktop.

3. **Verify Installation**
   ```bash
   mcpctl status
   ```
   
   If the service is running, you should see "No servers are defined in the configuration file." (normal for fresh install)

### Manual Installation

For manual installation, follow these steps:

1. **Grant Execute Permissions**
   Grant execute permissions to scripts in the project.
   ```bash
   chmod +x mcp_manager.py mcpctl mcp_server.sh install.sh uninstall.sh
   ```

2. **Create Directories**
   ```bash
   sudo mkdir -p /usr/local/lib/mcp-manager
   sudo mkdir -p /etc/mcp
   ```

3. **Deploy Files**
   ```bash
   sudo cp mcp_manager.py /usr/local/lib/mcp-manager/
   sudo cp mcpctl /usr/local/bin/
   sudo cp mcp_server.conf /etc/mcp/mcp_server.conf
   
   ```

4. **Edit Configuration File**
   The configuration file includes sample configurations that you can uncomment and modify:
   ```bash
   sudo nano /etc/mcp/mcp_server.conf
   ```
   
   **Sample configurations included:**
   ```
   # id=web-server /usr/bin/python3 -m http.server 8080
   # id=api-server node /path/to/api/server.js --port 3000
   # /usr/bin/python3 /path/to/worker.py  # Auto-generated hash ID
   # id=database redis-server /etc/redis/redis.conf
   ```

5. **Verify and Start systemd Service File**
   Open `mcp-manager.service` and verify the paths are correct.
   Then start the service as follows:
   ```bash
   sudo cp mcp-manager.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl start mcp-manager.service
   sudo systemctl enable mcp-manager.service
   ```

## Uninstallation

To completely remove MCP Server Manager from the system:

```bash
sudo ./uninstall.sh
```

This script performs the following tasks:
- Stops and disables the systemd service
- Removes service files
- Removes installed files
- Removes configuration files (with confirmation)

## Using `mcpctl`

- **Check Status:**
  Displays the status and IDs of all servers described in `mcp_server.conf`.
  ```bash
  mcpctl status
  ```
  **Example Output:**
  ```
  ID       STATUS    PID          UPTIME COMMAND
  -------- --------- ------- --------------- --------------------------------
  a1b2c3d  Running   12345 0 days, 0:10:30 /data/systemd-mcp/mcp_server.sh
  e4f5g6h  Stopped     N/A             N/A /usr/bin/python3 /path/to/another/server
  ```

- **Start Server:**
  Use ID to start a stopped (`Stopped`) or idle (`Idle`) server.
  ```bash
  mcpctl start e4f5g6h
  ```

- **Start All Servers from Configuration File:**
  Reload the configuration file and start all servers.
  ```bash
  mcpctl apply
  ```

- **Stop Server:**
  Use ID to stop a running (`Running`) server. Servers stopped this way are excluded from automatic restart.
  ```bash
  mcpctl stop a1b2c3d
  ```

- **Restart Server:**
  Use ID to restart a running server.
  ```bash
  mcpctl restart a1b2c3d
  ```
