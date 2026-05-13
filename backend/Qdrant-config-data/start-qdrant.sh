#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v qdrant >/dev/null 2>&1; then
  echo "[错误] 未在 PATH 中找到 qdrant。请先 brew install qdrant 或将官方二进制加入 PATH。" >&2
  exit 1
fi

mkdir -p storage snapshots static

echo "==============================="
echo "  Starting Qdrant Vector DB"
echo "  HTTP : http://localhost:6333"
echo "  WebUI: http://localhost:6333/dashboard"
echo "  config: $(pwd)/config-macos.yaml"
echo "==============================="

exec qdrant --config-path "$(pwd)/config-macos.yaml"
