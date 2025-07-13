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

# --- Configuration ---
MCP_SERVER_CONFIG_FILE = "/etc/mcp/mcp_server.conf"
SOCKET_PATH = "/tmp/mcp_manager.sock"
RESTART_DELAY_SECONDS = 5
MONITOR_INTERVAL_SECONDS = 1
# ---

# Global variables
managed_processes = {} # {server_id: {'proc': Popen, 'command': list, 'start_time': datetime}}
stopped_processes = {} # {server_id: {'command': list}}
configured_servers = {} # {server_id: command_list}
process_lock = threading.Lock()

def get_id_from_command(command_list):
    """Generate hash-based ID from command list"""
    command_str = ' '.join(command_list)
    return hashlib.sha1(command_str.encode()).hexdigest()[:7]

def format_uptime(seconds):
    """Convert seconds to 'X days, HH:MM:SS' format string"""
    if seconds is None: return 'N/A'
    if not isinstance(seconds, (int, float)) or seconds < 0: return "00:00:00"
    d = timedelta(seconds=int(seconds))
    return str(d)

def load_servers_from_conf():
    """Load servers from configuration file and update global variables"""
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
        print(f"[{os.path.basename(__file__)}] Configuration file '{MCP_SERVER_CONFIG_FILE}' not found.", file=sys.stderr)
    
    with process_lock:
        configured_servers = servers

def handle_client_connection(conn):
    """Handle client connections"""
    try:
        request_data = conn.recv(1024)
        if not request_data: return
        
        request = json.loads(request_data.decode('utf-8'))
        command = request.get('command')
        server_id = request.get('payload')
        response = {'status': 'error', 'message': 'Unknown command.'}

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
                response = {'status': 'error', 'message': f"ID '{server_id}' is not a valid ID."}
            elif command == 'stop':
                with process_lock:
                    if server_id in managed_processes:
                        print(f"[{os.path.basename(__file__)}] Stopping server with ID '{server_id}'.")
                        proc_info = managed_processes.pop(server_id)
                        proc_info['proc'].terminate()
                        stopped_processes[server_id] = {'command': proc_info['command']}
                        response = {'status': 'ok', 'message': f"Server with ID '{server_id}' has been stopped."}
                    else:
                        response = {'status': 'error', 'message': f"Server with ID '{server_id}' is not running."}
            elif command == 'start':
                with process_lock:
                    if server_id not in managed_processes:
                        print(f"[{os.path.basename(__file__)}] Starting server with ID '{server_id}'.")
                        command_to_run = configured_servers[server_id]
                        stopped_processes.pop(server_id, None)
                        new_proc = start_server(command_to_run)
                        if new_proc:
                            managed_processes[server_id] = {'proc': new_proc, 'command': command_to_run, 'start_time': datetime.now()}
                            response = {'status': 'ok', 'message': f"Server with ID '{server_id}' has been started."}
                        else:
                            response = {'status': 'error', 'message': f"Failed to start server with ID '{server_id}'."}
                    else:
                        response = {'status': 'error', 'message': f"Server with ID '{server_id}' is already running."}
            elif command == 'restart':
                 with process_lock:
                    if server_id in managed_processes:
                        print(f"[{os.path.basename(__file__)}] Restarting server with ID '{server_id}'.")
                        proc_info = managed_processes[server_id]
                        proc_info['proc'].terminate() # Monitoring loop handles restart
                        response = {'status': 'ok', 'message': f"Restart requested for server with ID '{server_id}'."}
                    else:
                        response = {'status': 'error', 'message': f"Server with ID '{server_id}' is not running."}
        
        elif command == 'apply':
            # Reload configuration file and start all servers
            print(f"[{os.path.basename(__file__)}] Reloading configuration file and starting servers.")
            load_servers_from_conf()
            started_count = 0
            error_count = 0
            
            with process_lock:
                for server_id, command_to_run in configured_servers.items():
                    if server_id not in managed_processes:
                        print(f"[{os.path.basename(__file__)}] Starting server with ID '{server_id}'.")
                        stopped_processes.pop(server_id, None)
                        new_proc = start_server(command_to_run)
                        if new_proc:
                            managed_processes[server_id] = {'proc': new_proc, 'command': command_to_run, 'start_time': datetime.now()}
                            started_count += 1
                        else:
                            error_count += 1
                    else:
                        print(f"[{os.path.basename(__file__)}] Server with ID '{server_id}' is already running.")
            
            if error_count > 0:
                response = {'status': 'error', 'message': f"Configuration applied. Started {started_count} servers, {error_count} servers had startup errors."}
            else:
                response = {'status': 'ok', 'message': f"Configuration applied. Started {started_count} servers."}
        
        conn.sendall(json.dumps(response).encode('utf-8'))
    except Exception as e:
        print(f"[{os.path.basename(__file__)}] Error during client processing: {e}", file=sys.stderr)
    finally:
        conn.close()

def socket_server_thread():
    if os.path.exists(SOCKET_PATH): os.remove(SOCKET_PATH)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.bind(SOCKET_PATH)
        # Set socket file permissions (accessible to all users)
        os.chmod(SOCKET_PATH, 0o666)
        s.listen()
        print(f"[{os.path.basename(__file__)}] Command receiving socket started at {SOCKET_PATH}.")
        while True:
            conn, _ = s.accept()
            threading.Thread(target=handle_client_connection, args=(conn,)).start()

def signal_handler(signum, frame):
    print(f"[{os.path.basename(__file__)}] Received signal {signum}. Stopping all servers...")
    with process_lock:
        for server_id in list(managed_processes.keys()):
            proc_info = managed_processes.pop(server_id)
            if proc_info['proc'].poll() is None:
                proc_info['proc'].terminate()
    if os.path.exists(SOCKET_PATH): os.remove(SOCKET_PATH)
    print(f"[{os.path.basename(__file__)}] Shutting down manager.")
    sys.exit(0)

def start_server(command):
    try:
        print(f"[{os.path.basename(__file__)}] Starting server: {' '.join(command)}")
        return subprocess.Popen(command, stdout=sys.stdout, stderr=sys.stderr)
    except Exception as e:
        print(f"[{os.path.basename(__file__)}] Failed to start server '{' '.join(command)}': {e}", file=sys.stderr)
        return None

def main():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    os.makedirs(os.path.dirname(MCP_SERVER_CONFIG_FILE), exist_ok=True)
    if not os.path.exists(MCP_SERVER_CONFIG_FILE):
        open(MCP_SERVER_CONFIG_FILE, 'a').close()

    print(f"[{os.path.basename(__file__)}] MCP Multi-Server Manager started (PID: {os.getpid()}).")
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
                print(f"[{os.path.basename(__file__)}] Server with ID '{server_id}' has stopped.")
                info = managed_processes.pop(server_id)
                # Restart after delay if not intentionally stopped
                if server_id not in stopped_processes:
                    print(f"[{os.path.basename(__file__)}] Restarting in {RESTART_DELAY_SECONDS} seconds...")
                    time.sleep(RESTART_DELAY_SECONDS)
                    print(f"[{os.path.basename(__file__)}] Restarting server with ID '{server_id}'...")
                    new_proc = start_server(info['command'])
                    if new_proc:
                        managed_processes[server_id] = {'proc': new_proc, 'command': info['command'], 'start_time': datetime.now()}

if __name__ == "__main__":
    main()