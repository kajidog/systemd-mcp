#!/bin/bash

# このスクリプトは管理対象となるMCPサーバーのダミーです。
# 起動時に与えられた引数を表示して、どのプロセスかを識別しやすくします。
SERVER_ID=$1
if [ -z "$SERVER_ID" ]; then
  SERVER_ID="Default"
fi

echo "[mcp_server-$SERVER_ID] MCPサーバーシミュレーターを開始します (PID: $$)"

# SIGTERMシグナルを受け取ったときに実行する関数を定義
cleanup() {
  echo "[mcp_server-$SERVER_ID] SIGTERMを受信しました。クリーンアップ処理を実行します..."
  sleep 2
  echo "[mcp_server-$SERVER_ID] クリーンアップが完了しました。サーバーを終了します。"
  exit 0
}

# trapコマンドでシグナルを補足
trap 'cleanup' TERM

# サーバーが動作していることを示すための無限ループ
count=0
while true; do
  echo "[mcp_server-$SERVER_ID] サーバーは正常に動作中です... (稼働時間: $((count * 5))秒)"
  count=$((count + 1))
  sleep 5
done
