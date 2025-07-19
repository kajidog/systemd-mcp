#!/bin/bash
# Systemd MCP Server Uninstall Script

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
FORCE_REMOVE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_REMOVE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --force            Skip confirmation prompts"
            echo "  --dry-run          Test mode (no actual removal)"
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
   echo "Usage: sudo $0"
   exit 1
fi

SYSTEMD_DIR="/etc/systemd/system"
INSTALL_DIR="/opt/systemd-mcp-server"
SERVICE_NAME="systemd-mcp-server.service"

print_info "Systemd MCP Server Uninstall"
print_info "============================="

if [[ "$DRY_RUN" == "true" ]]; then
    print_warning "DRY RUN MODE - No actual changes will be made"
fi

# Check if installed
if [[ ! -d "$INSTALL_DIR" && ! -f "$SYSTEMD_DIR/$SERVICE_NAME" ]]; then
    print_warning "systemd-mcp-server does not appear to be installed"
    exit 0
fi

# Confirmation
if [[ "$FORCE_REMOVE" != "true" && "$DRY_RUN" != "true" ]]; then
    echo
    print_warning "This will completely remove the systemd-mcp-server installation:"
    echo "  - Stop and disable the systemd service"
    echo "  - Remove installation directory: $INSTALL_DIR"
    echo "  - Remove systemd service file: $SYSTEMD_DIR/$SERVICE_NAME"
    echo
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Uninstall cancelled"
        exit 0
    fi
fi

# Stop and disable service
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    print_info "Stopping $SERVICE_NAME..."
    if [[ "$DRY_RUN" != "true" ]]; then
        systemctl stop "$SERVICE_NAME"
    fi
    print_success "Service stopped"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    print_info "Disabling $SERVICE_NAME..."
    if [[ "$DRY_RUN" != "true" ]]; then
        systemctl disable "$SERVICE_NAME"
    fi
    print_success "Service disabled"
fi

# Remove systemd service file
if [[ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]]; then
    print_info "Removing systemd service file..."
    if [[ "$DRY_RUN" != "true" ]]; then
        rm -f "$SYSTEMD_DIR/$SERVICE_NAME"
        systemctl daemon-reload
    fi
    print_success "Service file removed"
fi

# Remove installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    print_info "Removing installation directory..."
    if [[ "$DRY_RUN" != "true" ]]; then
        rm -rf "$INSTALL_DIR"
    fi
    print_success "Installation directory removed: $INSTALL_DIR"
fi

# Check for any remaining traces
print_info "Checking for remaining traces..."
REMAINING_FILES=()

if [[ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]]; then
    REMAINING_FILES+=("$SYSTEMD_DIR/$SERVICE_NAME")
fi

if [[ -d "$INSTALL_DIR" ]]; then
    REMAINING_FILES+=("$INSTALL_DIR")
fi

if [[ ${#REMAINING_FILES[@]} -gt 0 ]]; then
    print_warning "Some files may still remain:"
    for file in "${REMAINING_FILES[@]}"; do
        echo "  - $file"
    done
else
    print_success "All systemd-mcp-server components have been removed"
fi

echo
print_success "Systemd MCP Server uninstall completed!"
echo
print_info "Note: This only removes the MCP server component."
print_info "The systemd-mcp manager is still installed and running."
print_info "To uninstall the complete system, run: sudo ../uninstall.sh"