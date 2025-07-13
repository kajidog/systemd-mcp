#!/bin/bash
# MCP Server Manager Uninstallation Script

set -e  # エラー時に終了

# 色付きの出力関数
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

# root権限チェック
if [[ $EUID -ne 0 ]]; then
   print_error "このスクリプトはroot権限で実行する必要があります。"
   echo "使用方法: sudo $0"
   exit 1
fi

print_warning "=== MCP Server Manager アンインストール ==="
echo

# 確認
read -p "本当にMCP Server Managerをアンインストールしますか？ (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "アンインストールをキャンセルしました"
    exit 0
fi

# インストール先ディレクトリの定義
MCP_BIN_DIR="/usr/local/bin"
MCP_LIB_DIR="/usr/local/lib/mcp-manager"
MCP_CONFIG_DIR="/etc/mcp"
SYSTEMD_DIR="/etc/systemd/system"

# 1. サービスの停止と無効化
print_info "mcp-manager.serviceを停止中..."
if systemctl is-active --quiet mcp-manager.service; then
    systemctl stop mcp-manager.service
    print_success "サービスを停止しました"
fi

if systemctl is-enabled --quiet mcp-manager.service; then
    systemctl disable mcp-manager.service
    print_success "サービスを無効化しました"
fi

# 2. systemdサービスファイルの削除
print_info "systemdサービスファイルを削除中..."
if [[ -f "$SYSTEMD_DIR/mcp-manager.service" ]]; then
    rm -f "$SYSTEMD_DIR/mcp-manager.service"
    print_success "サービスファイルを削除しました"
fi

# systemdデーモンの再読み込み
systemctl daemon-reload

# 3. 実行ファイルの削除
print_info "実行ファイルを削除中..."

# mcpctl
if [[ -f "$MCP_BIN_DIR/mcpctl" ]]; then
    rm -f "$MCP_BIN_DIR/mcpctl"
    print_success "mcpctlを削除しました"
fi

# ライブラリディレクトリ
if [[ -d "$MCP_LIB_DIR" ]]; then
    rm -rf "$MCP_LIB_DIR"
    print_success "ライブラリディレクトリを削除しました"
fi

# 4. 設定ファイルの処理
print_info "設定ファイルの処理中..."
if [[ -d "$MCP_CONFIG_DIR" ]]; then
    read -p "設定ファイル ($MCP_CONFIG_DIR) も削除しますか？ (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$MCP_CONFIG_DIR"
        print_success "設定ディレクトリを削除しました"
    else
        print_info "設定ディレクトリは保持されました: $MCP_CONFIG_DIR"
    fi
fi

# 5. ソケットファイルの削除
print_info "一時ファイルを削除中..."
if [[ -S "/tmp/mcp_manager.sock" ]]; then
    rm -f "/tmp/mcp_manager.sock"
    print_success "ソケットファイルを削除しました"
fi

# 6. 完了メッセージ
echo
print_success "=== アンインストールが完了しました ==="
echo

if [[ -d "$MCP_CONFIG_DIR" ]]; then
    print_info "設定ファイルが残っています: $MCP_CONFIG_DIR"
    print_info "必要に応じて手動で削除してください"
fi

echo
print_info "MCP Server Managerのアンインストールが完了しました"
