#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v mongod >/dev/null 2>&1; then
  echo "[错误] 未在 PATH 中找到 mongod。请先 brew install mongodb-community 并确认已加入 PATH。" >&2
  exit 1
fi

mkdir -p mongo-data-macos mongo-log

echo "==============================="
echo "  Starting MongoDB (127.0.0.1:27017)"
echo "  dbPath : ./mongo-data-macos"
echo "  log    : ./mongo-log/mongod-macos.log"
echo "  config : ./mongo-macos.conf"
echo "==============================="

# 说明：Windows 的 mongo-data 是 mongod 8.2 创建（featureCompatibilityVersion=8.2），
# macOS Homebrew 当前 mongod 为 8.0，无法加载，因此 macOS 使用独立 dbPath。
exec mongod --config mongo-macos.conf
