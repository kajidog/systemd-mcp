#!/bin/bash
# Systemd MCP Server Installation Script

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

# Options handling
DRY_RUN=false
FORCE_REINSTALL=false
MCP_PORT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE_REINSTALL=true
            shift
            ;;
        --port)
            MCP_PORT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --dry-run          Test mode (no actual installation)"
            echo "  --force            Force reinstallation even if already installed"
            echo "  --port PORT        Port number for MCP server (default: 8000)"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root (use sudo)"
   echo "Usage: sudo -E $0"
   exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"
INSTALL_DIR="/opt/systemd-mcp-server"

print_info "Systemd MCP Server Installation"
print_info "================================"
print_info "Script directory: $SCRIPT_DIR"
print_info "Install directory: $INSTALL_DIR"

if [[ "$DRY_RUN" == "true" ]]; then
    print_warning "DRY RUN MODE - No actual changes will be made"
fi

# Check if already installed
if [[ -d "$INSTALL_DIR" && "$FORCE_REINSTALL" != "true" ]]; then
    print_warning "systemd-mcp-server is already installed at $INSTALL_DIR"
    print_info "Use --force to reinstall or uninstall first"
    exit 1
fi

# Check for required files
REQUIRED_FILES=("main.py" "stdio_server.py" "streamable_http_server.py" "tools.py" "pyproject.toml" "uv.lock")
for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$SCRIPT_DIR/$file" ]]; then
        print_error "Required file not found: $file"
        exit 1
    fi
done

# Install uv if not available
if ! command -v uv &> /dev/null; then
    print_info "Installing uv package manager..."
    if [[ "$DRY_RUN" != "true" ]]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    print_success "uv package manager installed"
else
    print_info "uv package manager already available"
fi

# Create installation directory
print_info "Creating installation directory..."
if [[ "$DRY_RUN" != "true" ]]; then
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    
    # Copy all MCP server files
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    
    # Set proper ownership and permissions
    chown -R root:root "$INSTALL_DIR"
    chmod +x "$INSTALL_DIR/main.py"
    chmod 644 "$INSTALL_DIR"/*.py
    chmod 644 "$INSTALL_DIR/pyproject.toml"
    chmod 644 "$INSTALL_DIR/uv.lock"
fi
print_success "Installation directory created: $INSTALL_DIR"

# Install Python dependencies
print_info "Installing Python dependencies..."
if [[ "$DRY_RUN" != "true" ]]; then
    cd "$INSTALL_DIR"
    export PATH="$HOME/.local/bin:$PATH"
    uv sync
fi
print_success "Python dependencies installed"

# Configure port
if [[ -z "$MCP_PORT" ]]; then
    if [[ "$DRY_RUN" != "true" ]]; then
        echo
        read -p "Enter port for MCP server (default: 8000): " user_port
        MCP_PORT="${user_port:-8000}"
    else
        MCP_PORT="8000"
    fi
fi

# Validate port
if ! [[ "$MCP_PORT" =~ ^[0-9]+$ ]] || [ "$MCP_PORT" -lt 1024 ] || [ "$MCP_PORT" -gt 65535 ]; then
    print_warning "Invalid port number. Must be between 1024 and 65535. Using default port 8000."
    MCP_PORT=8000
fi

print_info "MCP server will run on port: $MCP_PORT"

# Create systemd service file
print_info "Creating systemd service file..."
if [[ "$DRY_RUN" != "true" ]]; then
    cat > "$SYSTEMD_DIR/systemd-mcp-server.service" << EOF
[Unit]
Description=Systemd MCP Server
Documentation=https://github.com/your-repo/systemd-mcp
After=network.target mcp-manager.service

[Service]
Type=exec
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
Environment=PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/root/.local/bin/uv run python main.py --transport streamable-http --host 127.0.0.1 --port $MCP_PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
fi
print_success "systemd service file created: $SYSTEMD_DIR/systemd-mcp-server.service"

# Test installation
print_info "Testing installation..."
if [[ "$DRY_RUN" != "true" ]]; then
    cd "$INSTALL_DIR"
    export PATH="$HOME/.local/bin:$PATH"
    timeout 5s uv run python main.py --help > /dev/null
fi
print_success "Installation test passed"

# Reload systemd
print_info "Reloading systemd daemon..."
if [[ "$DRY_RUN" != "true" ]]; then
    systemctl daemon-reload
fi

# Ask about enabling the service
if [[ "$DRY_RUN" != "true" ]]; then
    echo
    read -p "Enable systemd-mcp-server.service for automatic startup? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Service not enabled. You can enable it later with: sudo systemctl enable systemd-mcp-server.service"
    else
        systemctl enable systemd-mcp-server.service
        print_success "systemd-mcp-server.service has been enabled"
        
        echo
        read -p "Start systemd-mcp-server.service now? (Y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            print_info "Service not started. You can start it later with: sudo systemctl start systemd-mcp-server.service"
        else
            systemctl start systemd-mcp-server.service
            print_success "systemd-mcp-server.service has been started"
            
            sleep 2
            echo
            print_info "Service status:"
            systemctl status systemd-mcp-server.service --no-pager -l
        fi
    fi
fi

echo
print_success "Systemd MCP Server installation completed!"
echo
echo "Installation summary:"
echo "  - Install directory: $INSTALL_DIR"
echo "  - Service name: systemd-mcp-server"
echo "  - Server endpoint: http://127.0.0.1:$MCP_PORT"
echo "  - Control with: sudo systemctl start/stop/status systemd-mcp-server"
echo "  - Logs: sudo journalctl -u systemd-mcp-server -f"
echo
echo "For Claude Desktop integration, add to your MCP settings:"
echo '{'
echo '  "mcpServers": {'
echo '    "systemd-mcp": {'
echo '      "command": "uv",'
echo '      "args": ["run", "python", "'"$INSTALL_DIR"'/main.py"],'
echo '      "cwd": "'"$INSTALL_DIR"'"'
echo '    }'
echo '  }'
echo '}'
echo
echo "For Claude Code integration:"
echo "  claude mcp add --transport http systemd http://127.0.0.1:$MCP_PORT/mcp"