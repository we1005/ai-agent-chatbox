#!/usr/bin/env bash
# ============================================================================
# 一键启动（macOS）：MongoDB → Qdrant → 天气 MCP → Backend → Frontend
#
# 每个服务后台运行，日志写入 ./logs/ 目录；脚本前台 tail -f 聚合输出。
# Ctrl+C 会停止 tail，但后台服务不会自动终止 —— 按提示用 kill 或再跑 stop-all.sh。
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$SCRIPT_DIR"
BACKEND="$ROOT/backend"
MCP_DIR="$ROOT/Gaode-weather-MCP-server"
FRONTEND="$ROOT/frontend"
VENV_ACTIVATE="$BACKEND/venv/bin/activate"
LOG_DIR="$ROOT/logs"
PID_DIR="$ROOT/logs/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

# ── 依赖探测 ───────────────────────────────────────────────────────────
missing=()
for bin in mongod qdrant node npm; do
  command -v "$bin" >/dev/null 2>&1 || missing+=("$bin")
done
if (( ${#missing[@]} > 0 )); then
  echo "[错误] 缺少以下依赖：${missing[*]}" >&2
  echo "       请先安装：brew install mongodb-community qdrant node" >&2
  exit 1
fi
if [ ! -f "$VENV_ACTIVATE" ]; then
  echo "[错误] 未找到 $VENV_ACTIVATE，请先在 backend 下创建 venv 并安装依赖。" >&2
  exit 1
fi

# ── 启动辅助 ───────────────────────────────────────────────────────────
start_service() {
  local name="$1"; shift
  local log="$LOG_DIR/$name.log"
  local pidfile="$PID_DIR/$name.pid"
  echo "[启动] $name → $log"
  # nohup + disown：让服务脱离当前 shell 的进程组，
  # 关闭 Terminal / Claude Code 会话中断 / 父 shell 收 HUP 时，服务不会被连带 kill。
  nohup bash -c '"$@"' _ "$@" >"$log" 2>&1 &
  local pid=$!
  echo "$pid" > "$pidfile"
  disown "$pid" 2>/dev/null || true
}

# ── 启动顺序：MongoDB → Qdrant → MCP → Backend → Frontend ──────────────

echo "[1/5] MongoDB"
start_service mongodb bash "$BACKEND/start-mongodb.sh"
sleep 2

echo "[2/5] Qdrant"
start_service qdrant bash "$BACKEND/Qdrant-config-data/start-qdrant.sh"
sleep 2

echo "[3/5] Weather MCP Server (port 8001)"
start_service mcp bash "$MCP_DIR/start-mcp-server.sh"
sleep 3

echo "[4/5] Backend (FastAPI / uvicorn, port 8000)"
start_service backend bash -c "
  source '$VENV_ACTIVATE'
  cd '$BACKEND'
  exec uvicorn main:app --reload --reload-dir app
"
sleep 3

echo "[5/5] Frontend (Vite, port 5173)"
start_service frontend bash -c "
  cd '$FRONTEND'
  exec npm run dev
"

cat <<EOF

==============================================================
所有服务已后台启动：
  • MongoDB        → 27017
  • Qdrant         → 6333    dashboard: http://localhost:6333/dashboard
  • Weather MCP    → 8001    SSE:       http://127.0.0.1:8001/sse
  • Backend        → 8000    API docs:  http://localhost:8000/docs
  • Frontend       → 5173    访问:       http://localhost:5173
日志目录: $LOG_DIR
PID 目录: $PID_DIR
==============================================================

Ctrl+C 将停止日志聚合，但后台服务仍在运行。
若要停止所有服务，执行：
  for f in $PID_DIR/*.pid; do kill "\$(cat "\$f")" 2>/dev/null; done

EOF

# ── 聚合日志 ────────────────────────────────────────────────────────────
exec tail -n +1 -F \
  "$LOG_DIR/mongodb.log" \
  "$LOG_DIR/qdrant.log" \
  "$LOG_DIR/mcp.log" \
  "$LOG_DIR/backend.log" \
  "$LOG_DIR/frontend.log"
