#!/usr/bin/env bash
# ============================================================================
# 一键停止：MongoDB、Qdrant、天气 MCP、Backend、Frontend
#
# 策略：
#   1) 先读 logs/pids/*.pid 里记录的进程，逐个 TERM → 等 3s → 仍活的 KILL。
#   2) 再扫一次关键端口（27017 / 6333 / 8001 / 8000 / 5173），清理任何遗留监听。
# ============================================================================
set -u

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID_DIR="$SCRIPT_DIR/logs/pids"
PORTS=(27017 6333 6334 8001 8000 5173)

kill_pid() {
  local pid="$1" label="$2"
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    return 1
  fi
  # 对 shell 启动器发 TERM，它的子进程（真正的服务）会一起收到 HUP；
  # 为保险起见用进程组 kill：kill -TERM -$pid
  if kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null; then
    echo "[停止] $label (pid=$pid) → TERM"
  fi
  # 等待最多 6 秒让服务走完优雅关闭（mongod 刷 journal、uvicorn reloader 回收 worker 等）
  for _ in 1 2 3 4 5 6; do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 1
  done
  # 还活着就 KILL
  kill -KILL "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  echo "[停止] $label (pid=$pid) → KILL (未响应 TERM)"
  return 0
}

# ── 1) 通过 pid 文件停止 ───────────────────────────────────────────────
stopped_any=false
if [ -d "$PID_DIR" ]; then
  shopt -s nullglob
  for pidfile in "$PID_DIR"/*.pid; do
    name="$(basename "$pidfile" .pid)"
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if kill_pid "$pid" "$name"; then
      stopped_any=true
    fi
    rm -f "$pidfile"
  done
  shopt -u nullglob
fi
$stopped_any || echo "[信息] logs/pids/ 下无活动 PID。"

# ── 2) 按端口兜底清理 ─────────────────────────────────────────────────
echo "[检查] 扫描遗留端口 ${PORTS[*]} ..."
leftover_pids=()
for port in "${PORTS[@]}"; do
  while IFS= read -r pid; do
    [ -n "$pid" ] && leftover_pids+=("$pid:$port")
  done < <(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
done

if (( ${#leftover_pids[@]} == 0 )); then
  echo "[检查] 所有关键端口已释放。"
else
  # 去重 pid：用空格分隔字符串当集合，避免 declare -A
  # （macOS 系统 bash 仍是 3.2，associative array 要 bash 4+）
  seen=" "
  for entry in "${leftover_pids[@]}"; do
    pid="${entry%%:*}"
    port="${entry##*:}"
    case "$seen" in *" $pid "*) continue ;; esac
    seen="$seen$pid "
    kill_pid "$pid" "port:$port"
  done
fi

# ── 3) 清理 start-all.sh 遗留的日志聚合 tail 进程 ─────────────────────
# start-all.sh 结尾是 `exec tail -F logs/*.log`，前台运行才能看到日志；
# 脱离终端后这些 tail 会残留，这里一并清理。
tail_pids=$(pgrep -f "tail -n \+1 -F $SCRIPT_DIR/logs/" 2>/dev/null || true)
if [ -n "$tail_pids" ]; then
  echo "[停止] 日志聚合 tail 进程: $tail_pids"
  # shellcheck disable=SC2086
  kill $tail_pids 2>/dev/null || true
fi

echo "[完成] 已停止 MongoDB / Qdrant / MCP / Backend / Frontend。"
