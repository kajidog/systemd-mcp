#!/bin/bash
# MCP Server Manager Installation Script

set -e  # Exit on error

# Colored output functions
print_info() {
    echo -e "\033[34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[33m[WARNING]\033[0m $1"
}

# Root permission check
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run with root privileges."
   echo "Usage: sudo $0"
   exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
print_info "Starting installation..."
print_info "Project directory: $SCRIPT_DIR"

# Define installation directories
MCP_BIN_DIR="/usr/local/bin"
MCP_LIB_DIR="/usr/local/lib/mcp-manager"
MCP_CONFIG_DIR="/etc/mcp"
SYSTEMD_DIR="/etc/systemd/system"

# 1. Create directories
print_info "Creating necessary directories..."
mkdir -p "$MCP_LIB_DIR"
mkdir -p "$MCP_CONFIG_DIR"

# 2. Copy executable files and set permissions
print_info "Copying executable files..."

# Copy mcp_manager.py to library directory
cp "$SCRIPT_DIR/mcp_manager.py" "$MCP_LIB_DIR/"
chmod +x "$MCP_LIB_DIR/mcp_manager.py"

# Copy mcpctl to bin directory
cp "$SCRIPT_DIR/mcpctl" "$MCP_BIN_DIR/"
chmod +x "$MCP_BIN_DIR/mcpctl"

# Also copy mcp_server.sh to library directory (as sample)
if [[ -f "$SCRIPT_DIR/mcp_server.sh" ]]; then
    cp "$SCRIPT_DIR/mcp_server.sh" "$MCP_LIB_DIR/"
    chmod +x "$MCP_LIB_DIR/mcp_server.sh"
fi

print_success "Executable files copying completed"

# 3. Copy configuration file (only if it doesn't exist)
print_info "Setting up configuration file..."

if [[ ! -f "$MCP_CONFIG_DIR/mcp_server.conf" ]]; then
    cp "$SCRIPT_DIR/mcp_server.conf" "$MCP_CONFIG_DIR/"
    print_success "Configuration file copied: $MCP_CONFIG_DIR/mcp_server.conf"
else
    print_warning "Configuration file already exists: $MCP_CONFIG_DIR/mcp_server.conf"
    print_info "Creating backup before update..."
    cp "$MCP_CONFIG_DIR/mcp_server.conf" "$MCP_CONFIG_DIR/mcp_server.conf.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$SCRIPT_DIR/mcp_server.conf" "$MCP_CONFIG_DIR/mcp_server.conf.new"
    print_info "Saved new configuration file as $MCP_CONFIG_DIR/mcp_server.conf.new"
    print_info "Please merge manually as needed"
fi

# 4. Setup systemd service file
print_info "Setting up systemd service..."

# Update service file path
SERVICE_FILE="$SYSTEMD_DIR/mcp-manager.service"
cp "$SCRIPT_DIR/mcp-manager.service" "$SERVICE_FILE"

# Update ExecStart and WorkingDirectory paths to actual installation destination
sed -i "s|ExecStart=.*mcp_manager.py|ExecStart=/usr/bin/python3 $MCP_LIB_DIR/mcp_manager.py|" "$SERVICE_FILE"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$MCP_LIB_DIR|" "$SERVICE_FILE"

print_success "Updated systemd service file"

# 5. Reload systemd configuration
print_info "Reloading systemd daemon..."
systemctl daemon-reload

# 6. Service enablement (optional)
read -p "Enable mcp-manager.service for automatic startup? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl enable mcp-manager.service
    print_success "mcp-manager.service has been enabled"
    
    read -p "Start the service now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl start mcp-manager.service
        print_success "mcp-manager.service has been started"
        
        # Display service status
        print_info "Service status:"
        systemctl status mcp-manager.service --no-pager -l
    fi
fi

# 7. Installation completion message
echo
print_success "=== Installation completed ==="
echo
print_info "Installed files:"
echo "  - Executable: $MCP_LIB_DIR/mcp_manager.py"
echo "  - CLI tool: $MCP_BIN_DIR/mcpctl"
echo "  - Configuration: $MCP_CONFIG_DIR/mcp_server.conf"
echo "  - Service file: $SERVICE_FILE"
echo

print_info "Usage:"
echo "  1. Edit configuration: sudo nano $MCP_CONFIG_DIR/mcp_server.conf"
echo "  2. Start service: sudo systemctl start mcp-manager.service"
echo "  3. Check status: mcpctl status"
echo "  4. Control servers: mcpctl start/stop/restart <ID>"
echo "  5. Apply configuration: mcpctl apply"
echo

if systemctl is-active --quiet mcp-manager.service; then
    print_success "mcp-manager.service is currently running"
    echo "You can check the status with: mcpctl status"
else
    print_info "To start the service: sudo systemctl start mcp-manager.service"
fi

echo
print_info "For detailed usage instructions, see README.md"
