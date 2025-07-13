# MCP Server Manager

## 概要

MCP Server Managerは、設定ファイル `mcp_server.conf` に基づいて複数のサーバープロセスを管理（起動、停止、監視、自動再起動）するためのデーモンツールです。

各サーバープロセスには、その起動コマンドから一意のIDが自動的に割り当てられます。`mcpctl` コマンドラインツールを使用することで、このIDを指定して個別のサーバーを操作できます。

`systemd` サービスとして動作し、意図せず終了したプロセスを自動で再起動することで、サービスの可用性を高めます。

## 主な機能

- **シンプルな設定ファイル:** 管理したいサーバーのコマンドを `mcp_server.conf` に記述するだけで利用できます。
- **IDの自動生成:** 各サーバーコマンドに対して、内容に基づいたユニークなID（ハッシュ）が自動で割り当てられます。
- **コマンドラインからの操作:** `mcpctl` を使い、`status` でIDを確認し、`start`, `stop`, `restart` で各サーバーを個別に操作できます。
- **プロセスの自動再起動:** `mcpctl stop` 以外でプロセスが終了した場合、デーモンが自動的に再起動します。
- **systemd連携:** `mcp-manager.service` を使って簡単にサービスとして登録できます。

## ワークフロー

1.  **設定:** `/etc/mcp/mcp_server.conf` を編集して、管理したいサーバーの起動コマンドを1行ずつ記述します。
2.  **リロード:** `sudo systemctl restart mcp-manager.service` を実行して、設定の変更をデーモンに反映させます。
3.  **確認:** `mcpctl status` を実行して、各サーバーの状態と自動生成されたIDを確認します。
4.  **操作:** 確認したIDを使って、`mcpctl start <ID>` や `mcpctl stop <ID>` などのコマンドで個別のサーバーを管理します。

## セットアップとインストール

### 自動インストール（推奨）

1. **インストールスクリプトの実行**
   ```bash
   sudo ./install.sh
   ```
   
   このスクリプトは以下の処理を自動で行います：
   - 必要なディレクトリの作成（`/usr/local/bin/mcp-manager/`、`/etc/mcp/`）
   - `mcp_manager.py`を`/usr/local/bin/mcp-manager/`にコピー
   - `mcpctl`を`/usr/local/bin/`にコピー（PATHに追加）
   - 設定ファイル`mcp_server.conf`を`/etc/mcp/`にコピー
   - systemdサービスファイルのインストールと登録
   - サービスの起動と自動起動の有効化

2. **インストール完了後の確認**
   ```bash
   mcpctl status
   ```

### 手動インストール

手動でインストールする場合は、以下の手順を実行してください：

1.  **実行権限の付与**
    プロジェクト内のスクリプトに実行権限を与えます。
    ```bash
    chmod +x mcp_manager.py mcpctl mcp_server.sh install.sh uninstall.sh
    ```

2.  **ディレクトリの作成**
    ```bash
    sudo mkdir -p /usr/local/lib/mcp-manager
    sudo mkdir -p /etc/mcp
    ```

3.  **ファイルの配置**
    ```bash
    sudo cp mcp_manager.py /usr/local/lib/mcp-manager/
    sudo cp mcpctl /usr/local/bin/
    sudo cp mcp_server.conf /etc/mcp/mcp_server.conf
    ```

4.  **設定ファイルの編集**
    必要に応じて設定ファイルを編集してください。
    ```bash
    sudo vi /etc/mcp/mcp_server.conf
    ```

5.  **systemdサービスファイルの確認と起動**
    `mcp-manager.service`を開き、パスが正しいことを確認してください。
    その後、以下のようにサービスを起動します。
    ```bash
    sudo cp mcp-manager.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl start mcp-manager.service
    sudo systemctl enable mcp-manager.service
    ```

## アンインストール

システムからMCP Server Managerを完全に削除するには：

```bash
sudo ./uninstall.sh
```

このスクリプトは以下の処理を行います：
- systemdサービスの停止と無効化
- サービスファイルの削除
- インストールされたファイルの削除
- 設定ファイルの削除（確認付き）

## `mcpctl` の使い方

- **状態を確認する:**
  `mcp_server.conf` に記述された全てのサーバーの状態とIDを表示します。
  ```bash
  mcpctl status
  ```
  **出力例:**
  ```
  ID       STATUS    PID          UPTIME COMMAND
  -------- --------- ------- --------------- --------------------------------
  a1b2c3d  Running   12345 0 days, 0:10:30 /data/systemd-mcp/mcp_server.sh
  e4f5g6h  Stopped     N/A             N/A /usr/bin/python3 /path/to/another/server
  ```

- **サーバーを起動する:**
  IDを使って、停止中 (`Stopped`) または待機中 (`Idle`) のサーバーを起動します。
  ```bash
  mcpctl start e4f5g6h
  ```

- **設定ファイルからすべてのサーバーを起動する:**
  設定ファイルを再読み込みして、すべてのサーバーを起動します。
  ```bash
  mcpctl apply
  ```

- **サーバーを停止する:**
  IDを使って、実行中 (`Running`) のサーバーを停止します。この方法で停止したサーバーは、自動再起動の対象外となります。
  ```bash
  mcpctl stop a1b2c3d
  ```

- **サーバーを再起動する:**
  IDを使って、実行中のサーバーを再起動します。
  ```bash
  mcpctl restart a1b2c3d
  ```
