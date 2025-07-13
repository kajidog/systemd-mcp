# MCP Server Manager

## 概要

MCP Server Managerは、設定ファイルに基づいて複数のサーバープロセスを管理（起動、監視、自動再起動）するためのシンプルなデーモンツールです。

`systemd` サービスとしてバックグラウンドで動作し、管理対象のプロセスが何らかの理由で終了した場合でも自動的に再起動します。また、付属のコマンドラインツール `mcpctl` を使用して、管理下にあるプロセスの状態確認や再起動を簡単に行うことができます。

## 主な機能

- **設定ファイルに基づく複数プロセスの管理:** `mcp_server.conf` に起動したいコマンドを記述するだけで、複数のプロセスを同時に管理できます。
- **プロセスの自動再起動:** 管理下のプロセスが終了すると、自動的に再起動を行い、サービスの可用性を高めます。
- **systemd連携:** `mcp-manager.service` ファイルを使って、簡単にsystemdサービスとして登録・管理できます。
- **コマンドラインインターフェース:** `mcpctl` ツールを使って、以下の操作が可能です。
  - `status`: 管理中の全プロセスの稼働状態（PID、稼働時間など）を表示します。
  - `restart`: 特定のプロセスを再起動します。
  - `restart-all`: 管理中の全てのプロセスを再起動します。

## ファイル構成

```
.
├── mcp_manager.py        # メインの管理デーモンスクリプト
├── mcp_server.conf       # 管理したいサーバーの起動コマンドを記述する設定ファイル
├── mcp_server.sh         # 管理されるサーバープロセスのサンプルスクリプト
├── mcp-manager.service   # systemd用のサービスユニットファイル
└── mcpctl                # 操作用コマンドラインツール
```

- **`mcp_manager.py`**: 設定ファイルを読み込み、指定されたプロセスを起動・監視します。プロセスが停止した際の再起動ロジックや、`mcpctl` からのコマンドを受け付けるソケットサーバー機能も持ちます。
- **`mcp_server.conf`**: 管理したいプロセスの起動コマンドを1行に1つずつ記述します。
- **`mcp_server.sh`**: `mcp_server.conf` に記述するコマンドの一例です。実際には、管理したい任意のアプリケーションやスクリプトのパスを記述します。
- **`mcp-manager.service`**: `mcp_manager.py` をsystemdサービスとして登録するための設定ファイルです。
- **`mcpctl`**: `mcp_manager.py` デーモンと通信し、プロセスの状態確認や再起動を行うためのクライアントツールです。

## セットアップと使い方

### 1. 前提条件

- Python 3 がインストールされていること。
- `systemd` が利用可能なLinux環境であること。

### 2. 設定

1. **実行権限の付与**

  `mcpctl` と `mcp_server.sh` に実行権限を与えます。

  ```bash
  chmod +x mcpctl
  chmod +x mcp_server.sh
  ```

2.  **管理対象プロセスの設定**

  `mcp_server.conf` を編集し、管理したいサーバープロセスの起動コマンドを記述します。各コマンドは改行で区切ってください。

  **例:**
  ```
  # 1つ目のサーバー
  /path/to/your/server1 --port 8000

  # 2つ目のサーバー (このプロジェクトのサンプルスクリプト)
  /path/to/systemd-mcp/mcp_server.sh
  ```

3.  **systemdサービスファイルの編集**

  `mcp-manager.service` ファイルを開き、`ExecStart` と `WorkingDirectory` のパスを、実際のプロジェクトのパスに合わせて修正します。

  **例:**
  ```ini
  [Service]
  ...
  ExecStart=/usr/bin/python3 /path/to/your/project/mcp_manager.py
  WorkingDirectory=/path/to/your/project
  ...
  ```

### 3. サービスのインストールと起動

1.  **サービスファイルの配置**

  編集した `mcp-manager.service` ファイルを systemd のディレクトリにコピーします。
  ```bash
  sudo cp mcp-manager.service /etc/systemd/system/
  ```

2.  **systemdデーモンのリロード**

  サービスファイルを配置したら、systemdに新しい設定を認識させます。
  ```bash
  sudo systemctl daemon-reload
  ```

3.  **サービスの起動**

  以下のコマンドでMCP Server Managerを起動します。
  ```bash
  sudo systemctl start mcp-manager.service
  ```

4.  **（任意）OS起動時の自動起動設定**

   OSの起動と同時にサービスが自動で開始されるように設定します。
   ```bash
   sudo systemctl enable mcp-manager.service
   ```

## `mcpctl` の使い方

`mcpctl` ツールを使って、デーモンが管理するプロセスの状態を確認したり、再起動したりできます。

- **状態の確認:**
  ```bash
  ./mcpctl status
  ```
  **出力例:**
  ```
      PID          UPTIME COMMAND
  ------- --------------- ----------------------------------------
    12345 0 days, 0:10:30 /path/to/systemd-mcp/mcp_server.sh
  ```

- **特定のサーバーを再起動:**

  再起動したいサーバーのコマンド（`mcp_server.conf` に記述したもの）を引数に指定します。
  ```bash
  ./mcpctl restart "/path/to/systemd-mcp/mcp_server.sh"
  ```

- **全てのサーバーを再起動:**

  ```bash
  ./mcpctl restart-all
  ```

## 注意点

- **ソケットファイル**: `mcp_manager.py` と `mcpctl` は、デフォルトで `/run/mcp_manager.sock` というUNIXソケットファイルを使って通信します。このパスを変更する場合は、両方のスクリプトの `SOCKET_PATH` 変数を修正する必要があります。
- **権限**: `mcp_manager.py` を実行するユーザーは、ソケットファイルを作成するディレクトリ（デフォルトでは `/run`）への書き込み権限が必要です。systemdのシステムサービスとして実行する場合、通常は問題ありません。
