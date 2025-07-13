#!/bin/bash
# MCP Server Manager Installation Script

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

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
print_info "インストールを開始します..."
print_info "プロジェクトディレクトリ: $SCRIPT_DIR"

# インストール先ディレクトリの定義
MCP_BIN_DIR="/usr/local/bin"
MCP_LIB_DIR="/usr/local/lib/mcp-manager"
MCP_CONFIG_DIR="/etc/mcp"
SYSTEMD_DIR="/etc/systemd/system"

# 1. ディレクトリの作成
print_info "必要なディレクトリを作成中..."
mkdir -p "$MCP_LIB_DIR"
mkdir -p "$MCP_CONFIG_DIR"

# 2. 実行ファイルのコピーと権限設定
print_info "実行ファイルをコピー中..."

# mcp_manager.pyをライブラリディレクトリにコピー
cp "$SCRIPT_DIR/mcp_manager.py" "$MCP_LIB_DIR/"
chmod +x "$MCP_LIB_DIR/mcp_manager.py"

# mcpctlをbinディレクトリにコピー
cp "$SCRIPT_DIR/mcpctl" "$MCP_BIN_DIR/"
chmod +x "$MCP_BIN_DIR/mcpctl"

# mcp_server.shもライブラリディレクトリにコピー（サンプルとして）
if [[ -f "$SCRIPT_DIR/mcp_server.sh" ]]; then
    cp "$SCRIPT_DIR/mcp_server.sh" "$MCP_LIB_DIR/"
    chmod +x "$MCP_LIB_DIR/mcp_server.sh"
fi

print_success "実行ファイルのコピーが完了しました"

# 3. 設定ファイルのコピー（存在しない場合のみ）
print_info "設定ファイルをセットアップ中..."

if [[ ! -f "$MCP_CONFIG_DIR/mcp_server.conf" ]]; then
    cp "$SCRIPT_DIR/mcp_server.conf" "$MCP_CONFIG_DIR/"
    print_success "設定ファイルをコピーしました: $MCP_CONFIG_DIR/mcp_server.conf"
else
    print_warning "設定ファイルが既に存在します: $MCP_CONFIG_DIR/mcp_server.conf"
    print_info "バックアップを作成してから更新します..."
    cp "$MCP_CONFIG_DIR/mcp_server.conf" "$MCP_CONFIG_DIR/mcp_server.conf.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$SCRIPT_DIR/mcp_server.conf" "$MCP_CONFIG_DIR/mcp_server.conf.new"
    print_info "新しい設定ファイルを $MCP_CONFIG_DIR/mcp_server.conf.new として保存しました"
    print_info "必要に応じて手動でマージしてください"
fi

# 4. systemdサービスファイルのセットアップ
print_info "systemdサービスをセットアップ中..."

# サービスファイルのパスを更新
SERVICE_FILE="$SYSTEMD_DIR/mcp-manager.service"
cp "$SCRIPT_DIR/mcp-manager.service" "$SERVICE_FILE"

# ExecStartとWorkingDirectoryのパスを実際のインストール先に更新
sed -i "s|ExecStart=.*mcp_manager.py|ExecStart=$MCP_LIB_DIR/mcp_manager.py|" "$SERVICE_FILE"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$MCP_LIB_DIR|" "$SERVICE_FILE"

print_success "systemdサービスファイルを更新しました"

# 5. systemdの設定を再読み込み
print_info "systemdデーモンを再読み込み中..."
systemctl daemon-reload

# 6. サービスの有効化（オプション）
read -p "mcp-manager.serviceを有効化して自動起動を設定しますか？ (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl enable mcp-manager.service
    print_success "mcp-manager.serviceが有効化されました"
    
    read -p "今すぐサービスを開始しますか？ (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl start mcp-manager.service
        print_success "mcp-manager.serviceが開始されました"
        
        # サービス状態を表示
        print_info "サービス状態:"
        systemctl status mcp-manager.service --no-pager -l
    fi
fi

# 7. インストール完了メッセージ
echo
print_success "=== インストールが完了しました ==="
echo
print_info "インストールされたファイル:"
echo "  - 実行ファイル: $MCP_LIB_DIR/mcp_manager.py"
echo "  - CLIツール: $MCP_BIN_DIR/mcpctl"
echo "  - 設定ファイル: $MCP_CONFIG_DIR/mcp_server.conf"
echo "  - サービスファイル: $SERVICE_FILE"
echo

print_info "使用方法:"
echo "  1. 設定ファイルを編集: sudo nano $MCP_CONFIG_DIR/mcp_server.conf"
echo "  2. サービスを開始: sudo systemctl start mcp-manager.service"
echo "  3. 状態を確認: mcpctl status"
echo "  4. サーバー操作: mcpctl start/stop/restart <ID>"
echo "  5. 設定適用: mcpctl apply"
echo

if systemctl is-active --quiet mcp-manager.service; then
    print_success "mcp-manager.serviceは現在実行中です"
    echo "mcpctl status を実行して状態を確認できます"
else
    print_info "サービスを開始するには: sudo systemctl start mcp-manager.service"
fi

echo
print_info "詳細な使用方法については README.md を参照してください"
