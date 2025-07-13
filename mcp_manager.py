#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import signal
import subprocess
import sys
import time
import os
import shlex
import socket
import threading
import json
import hashlib
from datetime import datetime, timedelta

# --- 設定 ---
MCP_SERVER_CONFIG_FILE = "/etc/mcp/mcp_server.conf"
SOCKET_PATH = "/tmp/mcp_manager.sock"
RESTART_DELAY_SECONDS = 5
MONITOR_INTERVAL_SECONDS = 1
# ---

# グローバル変数
managed_processes = {} # {server_id: {'proc': Popen, 'command': list, 'start_time': datetime}}
stopped_processes = {} # {server_id: {'command': list}}
configured_servers = {} # {server_id: command_list}
process_lock = threading.Lock()

def get_id_from_command(command_list):
    """コマンドリストからハッシュベースのIDを生成"""
    command_str = ' '.join(command_list)
    return hashlib.sha1(command_str.encode()).hexdigest()[:7]

def format_uptime(seconds):
    """秒を 'X days, HH:MM:SS' 形式の文字列に変換する"""
    if seconds is None: return 'N/A'
    if not isinstance(seconds, (int, float)) or seconds < 0: return "00:00:00"
    d = timedelta(seconds=int(seconds))
    return str(d)

def load_servers_from_conf():
    """設定ファイルからサーバーを読み込み、グローバル変数を更新"""
    global configured_servers
    servers = {}
    
    try:
        with open(MCP_SERVER_CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    command_list = shlex.split(line)
                    server_id = get_id_from_command(command_list)
                    servers[server_id] = command_list
    except FileNotFoundError:
        print(f"[{os.path.basename(__file__)}] 設定ファイル '{MCP_SERVER_CONFIG_FILE}' が見つかりません。", file=sys.stderr)
    
    with process_lock:
        configured_servers = servers

def handle_client_connection(conn):
    """クライアントからの接続を処理する"""
    try:
        request_data = conn.recv(1024)
        if not request_data: return
        
        request = json.loads(request_data.decode('utf-8'))
        command = request.get('command')
        server_id = request.get('payload')
        response = {'status': 'error', 'message': '不明なコマンドです。'}

        if command == 'status':
            process_list = []
            with process_lock:
                now = datetime.now()
                for sid, cmd_list in configured_servers.items():
                    cmd_str = ' '.join(cmd_list)
                    if sid in managed_processes:
                        info = managed_processes[sid]
                        uptime = format_uptime((now - info['start_time']).total_seconds())
                        process_list.append({'id': sid, 'status': 'Running', 'pid': info['proc'].pid, 'uptime': uptime, 'command': cmd_str})
                    elif sid in stopped_processes:
                        process_list.append({'id': sid, 'status': 'Stopped', 'pid': 'N/A', 'uptime': 'N/A', 'command': cmd_str})
                    else:
                        process_list.append({'id': sid, 'status': 'Idle', 'pid': 'N/A', 'uptime': 'N/A', 'command': cmd_str})
            response = {'status': 'ok', 'payload': process_list}

        elif command in ['start', 'stop', 'restart']:
            if not server_id or server_id not in configured_servers:
                response = {'status': 'error', 'message': f"ID '{server_id}' は有効なIDではありません。"}
            elif command == 'stop':
                with process_lock:
                    if server_id in managed_processes:
                        print(f"[{os.path.basename(__file__)}] ID '{server_id}' のサーバーを停止します。")
                        proc_info = managed_processes.pop(server_id)
                        proc_info['proc'].terminate()
                        stopped_processes[server_id] = {'command': proc_info['command']}
                        response = {'status': 'ok', 'message': f"ID '{server_id}' のサーバーを停止しました。"}
                    else:
                        response = {'status': 'error', 'message': f"ID '{server_id}' のサーバーは実行中ではありません。"}
            elif command == 'start':
                with process_lock:
                    if server_id not in managed_processes:
                        print(f"[{os.path.basename(__file__)}] ID '{server_id}' のサーバーを起動します。")
                        command_to_run = configured_servers[server_id]
                        stopped_processes.pop(server_id, None)
                        new_proc = start_server(command_to_run)
                        if new_proc:
                            managed_processes[server_id] = {'proc': new_proc, 'command': command_to_run, 'start_time': datetime.now()}
                            response = {'status': 'ok', 'message': f"ID '{server_id}' のサーバーを起動しました。"}
                        else:
                            response = {'status': 'error', 'message': f"ID '{server_id}' のサーバーの起動に失敗しまし���。"}
                    else:
                        response = {'status': 'error', 'message': f"ID '{server_id}' のサーバーは既に実行中です。"}
            elif command == 'restart':
                 with process_lock:
                    if server_id in managed_processes:
                        print(f"[{os.path.basename(__file__)}] ID '{server_id}' のサーバーを再起動します。")
                        proc_info = managed_processes[server_id]
                        proc_info['proc'].terminate() # 監視ループが再起動を処理
                        response = {'status': 'ok', 'message': f"ID '{server_id}' のサーバーの再起動を要求しました。"}
                    else:
                        response = {'status': 'error', 'message': f"ID '{server_id}' のサーバーは実行中ではありません。"}
        
        elif command == 'apply':
            # 設定ファイルを再読み込みして、すべてのサーバーを起動
            print(f"[{os.path.basename(__file__)}] 設定ファイルを再読み込みしてサーバーを起動します。")
            load_servers_from_conf()
            started_count = 0
            error_count = 0
            
            with process_lock:
                for server_id, command_to_run in configured_servers.items():
                    if server_id not in managed_processes:
                        print(f"[{os.path.basename(__file__)}] ID '{server_id}' のサーバーを起動します。")
                        stopped_processes.pop(server_id, None)
                        new_proc = start_server(command_to_run)
                        if new_proc:
                            managed_processes[server_id] = {'proc': new_proc, 'command': command_to_run, 'start_time': datetime.now()}
                            started_count += 1
                        else:
                            error_count += 1
                    else:
                        print(f"[{os.path.basename(__file__)}] ID '{server_id}' のサーバーは既に実行中です。")
            
            if error_count > 0:
                response = {'status': 'error', 'message': f"設定を適用しました。{started_count}個のサーバーを起動、{error_count}個のサーバーで起動エラーが発生しました。"}
            else:
                response = {'status': 'ok', 'message': f"設定を適用しました。{started_count}個のサーバーを起動しました。"}
        
        conn.sendall(json.dumps(response).encode('utf-8'))
    except Exception as e:
        print(f"[{os.path.basename(__file__)}] クライアント処理中にエラー: {e}", file=sys.stderr)
    finally:
        conn.close()

def socket_server_thread():
    if os.path.exists(SOCKET_PATH): os.remove(SOCKET_PATH)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.bind(SOCKET_PATH)
        # ソケットファイルの権限を設定（全ユーザーがアクセス可能）
        os.chmod(SOCKET_PATH, 0o666)
        s.listen()
        print(f"[{os.path.basename(__file__)}] コマンド受付ソケットを {SOCKET_PATH} で起動しました。")
        while True:
            conn, _ = s.accept()
            threading.Thread(target=handle_client_connection, args=(conn,)).start()

def signal_handler(signum, frame):
    print(f"[{os.path.basename(__file__)}] シグナル {signum} を受信。全サーバーを停止します...")
    with process_lock:
        for server_id in list(managed_processes.keys()):
            proc_info = managed_processes.pop(server_id)
            if proc_info['proc'].poll() is None:
                proc_info['proc'].terminate()
    if os.path.exists(SOCKET_PATH): os.remove(SOCKET_PATH)
    print(f"[{os.path.basename(__file__)}] マネージャーを終了します。")
    sys.exit(0)

def start_server(command):
    try:
        print(f"[{os.path.basename(__file__)}] サーバーを起動します: {' '.join(command)}")
        return subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr)
    except Exception as e:
        print(f"[{os.path.basename(__file__)}] サーバー '{' '.join(command)}' の起動に失敗: {e}", file=sys.stderr)
        return None

def main():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    os.makedirs(os.path.dirname(MCP_SERVER_CONFIG_FILE), exist_ok=True)
    if not os.path.exists(MCP_SERVER_CONFIG_FILE):
        open(MCP_SERVER_CONFIG_FILE, 'a').close()

    print(f"[{os.path.basename(__file__)}] MCPマルチサーバーマネージャーを起動しました (PID: {os.getpid()})。")
    load_servers_from_conf()
    
    sock_thread = threading.Thread(target=socket_server_thread, daemon=True)
    sock_thread.start()

    with process_lock:
        for server_id, command in configured_servers.items():
            proc = start_server(command)
            if proc:
                managed_processes[server_id] = {'proc': proc, 'command': command, 'start_time': datetime.now()}

    while True:
        time.sleep(MONITOR_INTERVAL_SECONDS)
        with process_lock:
            dead_server_ids = [sid for sid, info in managed_processes.items() if info['proc'].poll() is not None]
            
            for server_id in dead_server_ids:
                print(f"[{os.path.basename(__file__)}] ID '{server_id}' のサーバーが停止しました。")
                info = managed_processes.pop(server_id)
                # 意図的に停止されたものでなければ、遅延後に再起動
                if server_id not in stopped_processes:
                    print(f"[{os.path.basename(__file__)}] {RESTART_DELAY_SECONDS}秒後に再起動します...")
                    time.sleep(RESTART_DELAY_SECONDS)
                    print(f"[{os.path.basename(__file__)}] ID '{server_id}' のサーバーを再起動します...")
                    new_proc = start_server(info['command'])
                    if new_proc:
                        managed_processes[server_id] = {'proc': new_proc, 'command': info['command'], 'start_time': datetime.now()}

if __name__ == "__main__":
    main()