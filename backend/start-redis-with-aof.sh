#!/usr/bin/env bash
# 一键开启 Redis AOF 持久化（macOS Homebrew）
#
# 做什么：
#   1. 检测 $(brew --prefix)/etc/redis.conf 是否已开启 appendonly yes
#   2. 没开则追加 AOF 相关配置（备份原文件为 redis.conf.bak.TIMESTAMP）
#   3. brew services restart redis
#   4. 用 redis-cli 验证 CONFIG GET appendonly == yes
#
# 用法：
#   bash backend/start-redis-with-aof.sh

set -euo pipefail

if ! command -v brew &>/dev/null; then
  echo "❌ 未检测到 Homebrew。本脚本仅适用于 macOS Homebrew 安装的 Redis。"
  echo "   请手动运行：redis-server backend/redis.conf"
  exit 1
fi

if ! command -v redis-cli &>/dev/null; then
  echo "❌ 未检测到 redis-cli。请先：brew install redis"
  exit 1
fi

BREW_PREFIX=$(brew --prefix)
REDIS_CONF="$BREW_PREFIX/etc/redis.conf"

if [[ ! -f "$REDIS_CONF" ]]; then
  echo "⚠️  未找到 $REDIS_CONF"
  echo "   Homebrew 可能未安装 Redis。请先：brew install redis"
  exit 1
fi

echo "📍 Homebrew Redis 配置：$REDIS_CONF"

# 检测是否已有 appendonly yes（非注释行）
if grep -Eq '^[[:space:]]*appendonly[[:space:]]+yes' "$REDIS_CONF"; then
  echo "✅ AOF 已启用（$REDIS_CONF 中 appendonly yes 已存在）"
else
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  BACKUP="$REDIS_CONF.bak.$TIMESTAMP"
  cp "$REDIS_CONF" "$BACKUP"
  echo "📦 已备份原配置到：$BACKUP"

  cat >> "$REDIS_CONF" <<'EOF'

# === 玄鉴 · Celery 队列持久化（start-redis-with-aof.sh 自动追加）===
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
EOF
  echo "✏️  已追加 AOF 配置到 $REDIS_CONF"
fi

echo "🔄 brew services restart redis..."
brew services restart redis

# 等待 Redis 就绪
for i in {1..10}; do
  if redis-cli ping &>/dev/null; then
    break
  fi
  sleep 0.5
done

if ! redis-cli ping &>/dev/null; then
  echo "❌ Redis 未在 5 秒内就绪，请运行 'brew services list' 检查"
  exit 1
fi

APPENDONLY=$(redis-cli CONFIG GET appendonly | tail -n1)
if [[ "$APPENDONLY" == "yes" ]]; then
  echo "✅ Redis AOF 持久化已启用"
  echo "   验证：redis-cli CONFIG GET appendonly → $APPENDONLY"
else
  echo "⚠️  Redis 启动成功但 AOF 未生效（appendonly=$APPENDONLY）"
  echo "   请检查 $REDIS_CONF 是否有语法错误"
  exit 1
fi
