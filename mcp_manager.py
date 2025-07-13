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
from datetime import datetime, timedelta

# --- 設定 ---
MCP_SERVER_CONFIG_FILE = "mcp_server.conf"
SOCKET_PATH = "/run/mcp_manager.sock"
RESTART_DELAY_SECONDS = 5
MONITOR_INTERVAL_SECONDS = 1
# ---

# グローバル変数: {Popenオブジェクト: {'command': list, 'start_time': datetime}} の形式でプロセスを管理
managed_processes = {}
# スレッドセーフな操作のためのロック
process_lock = threading.Lock()

def format_uptime(seconds):
    """秒を 'X days, HH:MM:SS' 形式の文字列に変換する"""
    if seconds < 0: return "00:00:00"
    d = timedelta(seconds=int(seconds))
    return str(d)

def handle_client_connection(conn):
    """クライアントからの接続を処理する"""
    try:
        request_data = conn.recv(1024)
        if not request_data:
            return
        
        request = json.loads(request_data.decode('utf-8'))
        command = request.get('command')
        payload = request.get('payload')
        response = {'status': 'error', 'message': '不明なコマンドです。'}

        if command == 'status':
            status_lines = []
            with process_lock:
                if not managed_processes:
                    status_lines.append("現在管理中のサーバーはありません。")
                else:
                    status_lines.append(f"{'PID':>7} {'UPTIME':>15} {'COMMAND'}")
                    status_lines.append(f"{'-'*7} {'-'*15} {'-'*40}")
                    now = datetime.now()
                    for proc, info in managed_processes.items():
                        uptime = format_uptime((now - info['start_time']).total_seconds())
                        cmd_str = ' '.join(info['command'])
                        status_lines.append(f"{proc.pid:>7} {uptime:>15} {cmd_str}")
            
            response = {'status': 'ok', 'message': '\n'.join(status_lines)}

        elif command == 'restart':
            restarted = False
            with process_lock:
                # 再起動対象のプロセスを探す
                proc_to_restart = None
                for proc, info in managed_processes.items():
                    if ' '.join(info['command']) == payload:
                        proc_to_restart = proc
                        break
                
                if proc_to_restart and proc_to_restart.poll() is None:
                    print(f"[{os.path.basename(__file__)}] mcpctlからの要求により、サーバー '{payload}' (PID: {proc_to_restart.pid}) を停止します。")
                    proc_to_restart.terminate() # 監視ループが再起動を処理する
                    restarted = True

            if restarted:
                response = {'status': 'ok', 'message': f"サーバー '{payload}' の再起動を要求しました。"}
            else:
                response = {'status': 'error', 'message': f"サーバー '{payload}' が見つからないか、既に停止しています。"}
        
        elif command == 'restart-all':
            with process_lock:
                print(f"[{os.path.basename(__file__)}] mcpctlからの要求により、全サーバーを再起動します。")
                for proc in managed_processes.keys():
                    if proc.poll() is None:
                        proc.terminate()
            response = {'status': 'ok', 'message': '全サーバーの再起動を要求しました。'}

        conn.sendall(json.dumps(response).encode('utf-8'))

    except Exception as e:
        print(f"[{os.path.basename(__file__)}] クライアント処理中にエラー: {e}", file=sys.stderr)
    finally:
        conn.close()

def socket_server_thread():
    """mcpctlからのコマンドを受け付けるソケットサーバー"""
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.bind(SOCKET_PATH)
        s.listen()
        print(f"[{os.path.basename(__file__)}] コマンド受付ソケットを {SOCKET_PATH} で起動しました。")
        while True:
            conn, addr = s.accept()
            # クライアントごとにスレッドを立てて処理
            client_handler = threading.Thread(target=handle_client_connection, args=(conn,))
            client_handler.start()

def signal_handler(signum, frame):
    print(f"[{os.path.basename(__file__)}] シグナル {signum} を受信。全サーバーを停止します...")
    with process_lock:
        for process in managed_processes.keys():
            if process.poll() is None:
                process.terminate()
    
    # ソケットファイルをクリーンアップ
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
    
    print(f"[{os.path.basename(__file__)}] マネージャーを終了します。")
    sys.exit(0)

def get_server_commands():
    commands = []
    try:
        with open(MCP_SERVER_CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    commands.append(shlex.split(line))
        return commands
    except FileNotFoundError:
        print(f"[{os.path.basename(__file__)}] エラー: 設定ファイル '{MCP_SERVER_CONFIG_FILE}' が見つかりません.", file=sys.stderr)
        return None

def start_server(command):
    try:
        print(f"[{os.path.basename(__file__)}] サーバーを起動します: {' '.join(command)}")
        process = subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr)
        return process
    except Exception as e:
        print(f"[{os.path.basename(__file__)}] サーバー '{' '.join(command)}' の起動に失敗しました: {e}", file=sys.stderr)
        return None

def main():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print(f"[{os.path.basename(__file__)}] MCPマルチサーバーマネージャーを起動しました (PID: {os.getpid()})。")

    # ソケットサーバーを別スレッドで起動
    sock_thread = threading.Thread(target=socket_server_thread, daemon=True)
    sock_thread.start()

    commands_to_run = get_server_commands()
    if commands_to_run is None:
        sys.exit(1)

    with process_lock:
        for cmd in commands_to_run:
            proc = start_server(cmd)
            if proc:
                managed_processes[proc] = {'command': cmd, 'start_time': datetime.now()}

    while True:
        dead_processes = []
        with process_lock:
            for process, info in managed_processes.items():
                if process.poll() is not None:
                    print(f"[{os.path.basename(__file__)}] サーバー '{' '.join(info['command'])}' が停止しました。")
                    dead_processes.append(process)

        if dead_processes:
            time.sleep(RESTART_DELAY_SECONDS)
            with process_lock:
                for process in dead_processes:
                    command_to_restart = managed_processes.pop(process)['command']
                    print(f"[{os.path.basename(__file__)}] サーバー '{' '.join(command_to_restart)}' を再起動します...")
                    new_proc = start_server(command_to_restart)
                    if new_proc:
                        managed_processes[new_proc] = {'command': command_to_restart, 'start_time': datetime.now()}
        
        time.sleep(MONITOR_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
