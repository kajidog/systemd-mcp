#!/bin/bash
# MCP Server Manager Uninstallation Script

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

print_warning "=== MCP Server Manager Uninstallation ==="
echo

# Confirmation
read -p "Are you sure you want to uninstall MCP Server Manager? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Uninstallation cancelled"
    exit 0
fi

# Installation directory definitions
MCP_BIN_DIR="/usr/local/bin"
MCP_LIB_DIR="/usr/local/lib/mcp-manager"
MCP_CONFIG_DIR="/etc/mcp"
SYSTEMD_DIR="/etc/systemd/system"

# 1. Stop and disable service
print_info "Stopping mcp-manager.service..."
if systemctl is-active --quiet mcp-manager.service; then
    systemctl stop mcp-manager.service
    print_success "Service stopped"
fi

if systemctl is-enabled --quiet mcp-manager.service; then
    systemctl disable mcp-manager.service
    print_success "Service disabled"
fi

# 2. Remove systemd service file
print_info "Removing systemd service file..."
if [[ -f "$SYSTEMD_DIR/mcp-manager.service" ]]; then
    rm -f "$SYSTEMD_DIR/mcp-manager.service"
    print_success "Service file removed"
fi

# Reload systemd daemon
systemctl daemon-reload

# 3. Remove executable files
print_info "Removing executable files..."

# mcpctl
if [[ -f "$MCP_BIN_DIR/mcpctl" ]]; then
    rm -f "$MCP_BIN_DIR/mcpctl"
    print_success "mcpctl removed"
fi

# Library directory
if [[ -d "$MCP_LIB_DIR" ]]; then
    rm -rf "$MCP_LIB_DIR"
    print_success "Library directory removed"
fi

# 4. Configuration file handling
print_info "Processing configuration files..."
if [[ -d "$MCP_CONFIG_DIR" ]]; then
    read -p "Delete configuration files ($MCP_CONFIG_DIR) as well? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$MCP_CONFIG_DIR"
        print_success "Configuration directory removed"
    else
        print_info "Configuration directory preserved: $MCP_CONFIG_DIR"
    fi
fi

# 5. Remove socket file
print_info "Removing socket file..."
if [[ -S "/tmp/mcp_manager.sock" ]]; then
    rm -f "/tmp/mcp_manager.sock"
    print_success "Socket file removed"
fi

# 6. Completion message
echo
print_success "=== Uninstallation completed ==="
echo

if [[ -d "$MCP_CONFIG_DIR" ]]; then
    print_info "Configuration files remain: $MCP_CONFIG_DIR"
    print_info "Please remove manually if needed"
fi

echo
print_info "MCP Server Manager uninstallation completed"
